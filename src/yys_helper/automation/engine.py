from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

from yys_helper.domain.models import StopReason, TaskLimits, TaskOutcome
from .pacing import PacingController


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
    track_battles: bool = False

    def next_state(self, state: str, action: str) -> str | None:
        transition = self.transitions.get(state)
        if transition and transition.action == action and transition.expected_scenes:
            return transition.expected_scenes[0]
        return None


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._finish_event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> None:
        self._event.wait(seconds)

    def finish_round(self) -> None:
        self._finish_event.set()

    def finishing(self) -> bool:
        return self._finish_event.is_set()


class AutomationEngine:
    def __init__(
        self,
        observer: SceneObserver,
        actor: ActionActor,
        *,
        clock=time.monotonic,
        sleeper=time.sleep,
        progress=None,
        pacing: PacingController | None = None,
        activity=None,
    ) -> None:
        self.observer = observer
        self.actor = actor
        self.clock = clock
        self.sleeper = sleeper
        self.progress = progress or (lambda _scene, _rounds, _elapsed: None)
        self.pacing = pacing
        self.activity = activity or (lambda _kind, _seconds: None)

    def run(
        self,
        workflow: Workflow,
        limits: TaskLimits,
        cancel_token: CancellationToken | None = None,
    ) -> TaskOutcome:
        token = cancel_token or CancellationToken()
        started = self.clock()
        deadline = started + limits.max_duration_seconds
        rounds = 0
        last_scene = "starting"
        unknown_count = 0
        expected_scenes: tuple[str, ...] | None = None
        battle_open = False
        scene_since = started
        previous_scene = None
        wait = token.wait if self.sleeper is time.sleep else self.sleeper

        def interrupted():
            elapsed = self.clock() - started
            if token.is_cancelled():
                return TaskOutcome(StopReason.CANCELLED, last_scene, rounds, elapsed)
            if self.clock() >= deadline:
                return TaskOutcome(StopReason.MAX_DURATION, last_scene, rounds, elapsed)
            return None

        def paced_wait(seconds, kind='waiting'):
            remaining = seconds
            while remaining > 0 and interrupted() is None:
                if kind == 'resting' and token.finishing():
                    return TaskOutcome(StopReason.COMPLETED, last_scene, rounds, self.clock() - started, '本轮结束，已停止。')
                # No single wait can outlive the session deadline. Stop wakes token.wait immediately.
                self.activity(kind, remaining)
                chunk = min(remaining, max(0., deadline - self.clock()), 1. if self.pacing else remaining)
                wait(chunk)
                remaining -= chunk
            return interrupted()

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

            elapsed = self.clock() - started
            if token.is_cancelled():
                return TaskOutcome(StopReason.CANCELLED, last_scene, rounds, elapsed)
            if elapsed >= limits.max_duration_seconds:
                return TaskOutcome(StopReason.MAX_DURATION, last_scene, rounds, elapsed)

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
                outcome = paced_wait(self.pacing.poll_delay(1.) if self.pacing else 1.)
                if outcome:
                    return outcome
                continue

            last_scene = scene
            expected_scenes = None
            unknown_count = 0
            if scene != previous_scene:
                scene_since = self.clock()
                previous_scene = scene
            elif scene != 'battle' and self.clock() - scene_since > 30:
                return TaskOutcome(StopReason.UNRECOGNIZED_SCENE, scene, rounds, elapsed, '页面超过 30 秒未变化')
            if scene == 'battle':
                battle_open = True
            self.progress(scene, rounds, elapsed)
            if scene in workflow.terminal_scenes:
                return TaskOutcome(
                    StopReason.COMPLETED, scene, rounds, self.clock() - started
                )

            transition = workflow.transitions.get(scene)
            if transition is None:
                unknown_count = 1
                expected_scenes = ("__no_valid_transition__",)
                continue

            just_completed = transition.round_completed and (not workflow.track_battles or battle_open)
            if just_completed:
                rounds += 1
                battle_open = False
                self.progress(scene, rounds, elapsed)
                if rounds >= limits.max_rounds:
                    return TaskOutcome(StopReason.MAX_ROUNDS, scene, rounds, self.clock() - started)
            safe_boundary = just_completed or scene in ('ready', 'soul_ready', 'explore_map', 'home', 'chapter_select', 'repeat', 'settlement')
            if token.finishing() and safe_boundary:
                return TaskOutcome(StopReason.COMPLETED, scene, rounds, self.clock() - started, '本轮结束，已停止；不会自动续跑。')
            if self.pacing and transition.action != 'wait_battle':
                rest = self.pacing.rest_duration(rounds) if just_completed else 0.
                if rest:
                    outcome = paced_wait(rest, 'resting')
                    if outcome:
                        return outcome
                outcome = paced_wait(self.pacing.action_delay(), 'thinking')
                if outcome:
                    return outcome
                if token.finishing() and safe_boundary:
                    return TaskOutcome(StopReason.COMPLETED, scene, rounds, self.clock() - started, '本轮结束，已停止。')
                # Waiting invalidates old screenshot coordinates. Refresh before any input.
                try:
                    fresh_scene = self.observer.observe()
                except Exception as exc:
                    return TaskOutcome(StopReason.ADB_DISCONNECTED, scene, rounds, self.clock() - started, str(exc))
                outcome = interrupted()
                if outcome:
                    return outcome
                if token.finishing() and safe_boundary:
                    return TaskOutcome(StopReason.COMPLETED, scene, rounds, self.clock() - started, '本轮结束，已停止。')
                if fresh_scene in workflow.stop_scenes:
                    return TaskOutcome(workflow.stop_scenes[fresh_scene], fresh_scene, rounds, self.clock() - started)
                if fresh_scene != scene:
                    expected_scenes = (scene,) + transition.expected_scenes
                    continue
                # A long boundary rest is not a stuck-page timeout.
                if rest:
                    scene_since = self.clock()
            # A completed last round must never press "challenge again".
            if token.is_cancelled():
                return TaskOutcome(StopReason.CANCELLED, scene, rounds, self.clock() - started)
            if token.finishing() and safe_boundary:
                return TaskOutcome(StopReason.COMPLETED, scene, rounds, self.clock() - started, '本轮结束，已停止。')
            try:
                performed = self.actor.perform(transition.action)
            except Exception as exc:
                return TaskOutcome(StopReason.ACTION_FAILED, scene, rounds, self.clock() - started, str(exc))
            outcome = interrupted()
            if outcome:
                return outcome
            if not performed:
                if token.finishing() and safe_boundary:
                    return TaskOutcome(StopReason.COMPLETED, scene, rounds, self.clock() - started, '本轮结束，已停止。')
                return TaskOutcome(
                    StopReason.ACTION_FAILED,
                    scene,
                    rounds,
                    self.clock() - started,
                    transition.action,
                )
            if transition.poll_delay_seconds > 0:
                delay = self.pacing.poll_delay(transition.poll_delay_seconds) if self.pacing else transition.poll_delay_seconds
                outcome = paced_wait(delay)
                if outcome:
                    return outcome
            expected_scenes = transition.expected_scenes
