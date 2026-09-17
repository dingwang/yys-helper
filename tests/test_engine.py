import unittest

from yys_helper.automation.engine import (
    AutomationEngine,
    CancellationToken,
    Transition,
    Workflow,
)
from yys_helper.domain.models import StopReason, TaskLimits


class FakeObserver:
    def __init__(self, scenes):
        self.scenes = iter(scenes)

    def observe(self):
        return next(self.scenes, None)


class RecordingActor:
    def __init__(self):
        self.actions = []

    def perform(self, action):
        self.actions.append(action)
        return True


def one_step_workflow():
    return Workflow(
        name="one-step",
        transitions={"explore_map": Transition("tap_monster", ("battle",))},
        terminal_scenes=frozenset({"battle"}),
    )


class EngineTests(unittest.TestCase):
    def test_action_occurs_only_after_expected_scene_is_observed(self):
        actor = RecordingActor()
        engine = AutomationEngine(FakeObserver(["explore_map", "battle"]), actor)
        result = engine.run(one_step_workflow(), TaskLimits())
        self.assertEqual(["tap_monster"], actor.actions)
        self.assertEqual("battle", result.final_state)
        self.assertEqual(StopReason.COMPLETED, result.reason)

    def test_three_unknown_scenes_stop_without_input(self):
        actor = RecordingActor()
        engine = AutomationEngine(FakeObserver([None, None, None]), actor)
        result = engine.run(one_step_workflow(), TaskLimits())
        self.assertEqual(StopReason.UNRECOGNIZED_SCENE, result.reason)
        self.assertEqual([], actor.actions)

    def test_unexpected_scene_after_action_does_not_trigger_another_action(self):
        actor = RecordingActor()
        engine = AutomationEngine(
            FakeObserver(["explore_map", "home", "home", "home"]), actor
        )
        result = engine.run(one_step_workflow(), TaskLimits())
        self.assertEqual(["tap_monster"], actor.actions)
        self.assertEqual(StopReason.UNRECOGNIZED_SCENE, result.reason)

    def test_cancelled_token_stops_before_input(self):
        token = CancellationToken()
        token.cancel()
        actor = RecordingActor()
        result = AutomationEngine(FakeObserver(["explore_map"]), actor).run(
            one_step_workflow(), TaskLimits(), token
        )
        self.assertEqual(StopReason.CANCELLED, result.reason)
        self.assertEqual([], actor.actions)

    def test_transition_uses_configured_poll_delay(self):
        delays = []
        workflow = Workflow(
            name="paced",
            transitions={
                "explore_map": Transition(
                    "tap_monster", ("battle",), poll_delay_seconds=1.25
                )
            },
            terminal_scenes=frozenset({"battle"}),
        )
        engine = AutomationEngine(
            FakeObserver(["explore_map", "battle"]),
            RecordingActor(),
            sleeper=delays.append,
        )
        engine.run(workflow, TaskLimits())
        self.assertEqual([1.25], delays)


if __name__ == "__main__":
    unittest.main()
