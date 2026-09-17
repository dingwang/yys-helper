from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

from yys_helper.domain.models import StopReason, TaskLimits, TaskOutcome


class SceneObserver(Protocol):
    def observe(self) -> str | None: ...


class ActionActor(Protocol):
    def perform(self, action: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class Transition:
    action: str
    expected_scenes: tuple[str, ...]
    round_completed: bool = False
    poll_delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class Workflow:
    name: str
    transitions: dict[str, Transition]
    terminal_scenes: frozenset[str] = frozenset()
    stop_scenes: dict[str, StopReason] = field(default_factory=dict)

    def next_state(self, state: str, action: str) -> str | None:
        transition = self.transitions.get(state)
        if transition and transition.action == action and transition.expected_scenes:
            return transition.expected_scenes[0]
        return None


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class AutomationEngine:
    def __init__(
        self,
        observer: SceneObserver,
        actor: ActionActor,
        *,
        clock=time.monotonic,
        sleeper=time.sleep,
    ) -> None:
        self.observer = observer
        self.actor = actor
        self.clock = clock
        self.sleeper = sleeper

    def run(
        self,
        workflow: Workflow,
        limits: TaskLimits,
        cancel_token: CancellationToken | None = None,
    ) -> TaskOutcome:
        token = cancel_token or CancellationToken()
        started = self.clock()
        rounds = 0
        last_scene = "starting"
        unknown_count = 0
        expected_scenes: tuple[str, ...] | None = None

        while True:
            elapsed = self.clock() - started
            if token.is_cancelled():
                return TaskOutcome(StopReason.CANCELLED, last_scene, rounds, elapsed)
            if elapsed >= limits.max_duration_seconds:
                return TaskOutcome(StopReason.MAX_DURATION, last_scene, rounds, elapsed)

            try:
                scene = self.observer.observe()
            except Exception as exc:
                return TaskOutcome(
                    StopReason.ADB_DISCONNECTED, last_scene, rounds, elapsed, str(exc)
                )

            if scene in workflow.stop_scenes:
                return TaskOutcome(workflow.stop_scenes[scene], scene or last_scene, rounds, elapsed)

            if scene is None or (expected_scenes is not None and scene not in expected_scenes):
                unknown_count += 1
                if unknown_count >= 3:
                    return TaskOutcome(
                        StopReason.UNRECOGNIZED_SCENE,
                        scene or last_scene,
                        rounds,
                        self.clock() - started,
                    )
                continue

            last_scene = scene
            expected_scenes = None
            unknown_count = 0
            if scene in workflow.terminal_scenes:
                return TaskOutcome(
                    StopReason.COMPLETED, scene, rounds, self.clock() - started
                )

            transition = workflow.transitions.get(scene)
            if transition is None:
                unknown_count = 1
                expected_scenes = ("__no_valid_transition__",)
                continue

            if not self.actor.perform(transition.action):
                return TaskOutcome(
                    StopReason.ACTION_FAILED,
                    scene,
                    rounds,
                    self.clock() - started,
                    transition.action,
                )
            if transition.poll_delay_seconds > 0:
                self.sleeper(transition.poll_delay_seconds)
            expected_scenes = transition.expected_scenes
            if transition.round_completed:
                rounds += 1
                if rounds >= limits.max_rounds:
                    return TaskOutcome(
                        StopReason.MAX_ROUNDS, scene, rounds, self.clock() - started
                    )
