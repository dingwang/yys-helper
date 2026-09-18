import unittest

from yys_helper.automation.catalog import TASKS, TaskProfile, workflow_for
from yys_helper.application.runtime import classify_task_scene
from yys_helper.automation.engine import AutomationEngine, CancellationToken
from yys_helper.domain.models import TaskLimits, StopReason
from yys_helper.infrastructure.vision import OcrBox
from tests.test_engine import FakeObserver, RecordingActor, one_step_workflow


def boxes(*texts):
    return [OcrBox(text, .99, (0, 0, 100, 40)) for text in texts]


class TaskCatalogTests(unittest.TestCase):
    def test_all_modes_have_a_workflow_and_unknown_is_rejected(self):
        self.assertGreaterEqual(len(TASKS), 10)
        for task in TASKS:
            self.assertTrue(workflow_for(task.id).transitions)
        with self.assertRaises(ValueError):
            workflow_for('invalid')

    def test_profile_requires_title_and_exact_button(self):
        profile = TaskProfile(('活动试炼',))
        self.assertEqual('ready', classify_task_scene(boxes('活动试炼', '挑战'), profile))
        self.assertIsNone(classify_task_scene(boxes('别的活动', '挑战'), profile))
        self.assertEqual('resource_empty', classify_task_scene(boxes('活动试炼', '挑战次数不足'), profile))
        self.assertEqual('stamina_empty', classify_task_scene(boxes('活动试炼', '挑战', '体力不足'), profile))
        self.assertEqual('resource_empty', classify_task_scene(boxes('活动试炼', '挑战', '门票不足'), profile))
        self.assertEqual('defeat', classify_task_scene(boxes('战斗失败', '再次挑战'), profile))

    def test_profile_serialization_validates_and_round_trips(self):
        p = TaskProfile(('活动试炼',), start=('开始挑战',))
        self.assertEqual(p, TaskProfile.from_json(p.to_json()))
        with self.assertRaises(ValueError):
            TaskProfile.from_json('{"title": []}')

    def test_title_cannot_be_the_action_button(self):
        for title in ('挑战', '战', '再次挑战'):
            with self.assertRaises(ValueError):
                TaskProfile((title,))

    def test_two_start_buttons_fail_scene_preflight(self):
        self.assertIsNone(classify_task_scene(boxes('活动试炼', '挑战', '挑战'), TaskProfile(('活动试炼',))))

    def test_cancel_during_observation_never_sends_input(self):
        token = CancellationToken()
        class Observer:
            def observe(self):
                token.cancel()
                return 'explore_map'
        actor = RecordingActor()
        result = AutomationEngine(Observer(), actor).run(one_step_workflow(), TaskLimits(), token)
        self.assertEqual(StopReason.CANCELLED, result.reason)
        self.assertEqual([], actor.actions)

    def test_activity_counts_once_across_multi_page_rewards_and_no_extra_battle(self):
        actor = RecordingActor()
        scenes = ['ready', 'prepare', 'battle', 'settlement', 'settlement', 'repeat',
                  'battle', 'repeat']
        result = AutomationEngine(FakeObserver(scenes), actor, sleeper=lambda _: None).run(
            workflow_for('event_stage'), TaskLimits(max_rounds=2))
        self.assertEqual(StopReason.MAX_ROUNDS, result.reason)
        self.assertEqual(2, result.rounds)
        self.assertEqual(1, actor.actions.count('task_repeat'))

    def test_stamina_and_failure_stop_without_input(self):
        for scene in ('stamina_empty', 'resource_empty', 'defeat', 'purchase'):
            actor = RecordingActor()
            result = AutomationEngine(FakeObserver([scene]), actor, sleeper=lambda _: None).run(
                workflow_for('event_stage'), TaskLimits())
            self.assertEqual([], actor.actions)
            self.assertNotEqual(StopReason.MAX_ROUNDS, result.reason)
