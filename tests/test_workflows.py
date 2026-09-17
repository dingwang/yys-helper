import unittest

from yys_helper.automation.engine import AutomationEngine
from yys_helper.automation.workflows import chapter_28_workflow, soul_dungeon_workflow
from yys_helper.domain.models import StopReason, TaskLimits

from tests.test_engine import FakeObserver, RecordingActor


class WorkflowTests(unittest.TestCase):
    def test_chapter_28_returns_to_map_after_settlement(self):
        workflow = chapter_28_workflow()
        self.assertEqual("explore_map", workflow.next_state("settlement", "confirm"))

    def test_soul_dungeon_returns_to_ready_after_settlement(self):
        workflow = soul_dungeon_workflow()
        self.assertEqual("soul_ready", workflow.next_state("settlement", "challenge_again"))

    def test_stamina_empty_stops_without_tapping(self):
        actor = RecordingActor()
        result = AutomationEngine(FakeObserver(["stamina_empty"]), actor).run(
            soul_dungeon_workflow(), TaskLimits()
        )
        self.assertEqual(StopReason.INSUFFICIENT_STAMINA, result.reason)
        self.assertEqual([], actor.actions)

    def test_chapter_28_stops_at_round_limit(self):
        scenes = ["explore_map", "battle", "settlement", "explore_map"]
        actor = RecordingActor()
        result = AutomationEngine(FakeObserver(scenes), actor).run(
            chapter_28_workflow(), TaskLimits(max_rounds=1)
        )
        self.assertEqual(StopReason.MAX_ROUNDS, result.reason)
        self.assertEqual(1, result.rounds)


if __name__ == "__main__":
    unittest.main()
