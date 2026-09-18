import random
import unittest

from yys_helper.automation.pacing import PacingPolicy, PacingController
from yys_helper.automation.engine import AutomationEngine, CancellationToken, Workflow, Transition
from yys_helper.domain.models import TaskLimits, StopReason
from tests.test_engine import FakeObserver, RecordingActor


class Clock:
    def __init__(self):
        self.now = 0.
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


class PacingTests(unittest.TestCase):
    def test_finish_requested_during_delay_or_refresh_never_starts_new_battle(self):
        for phase in ('wait', 'refresh'):
            with self.subTest(phase=phase):
                token = CancellationToken()
                clock = Clock()
                actor = RecordingActor()
                class Observer:
                    calls = 0
                    def observe(self):
                        self.calls += 1
                        if phase == 'refresh' and self.calls == 2:
                            token.finish_round()
                        return 'ready'
                def wait(seconds):
                    clock.sleep(seconds)
                    if phase == 'wait':
                        token.finish_round()
                result = AutomationEngine(Observer(), actor, clock=clock, sleeper=wait,
                    pacing=PacingController()).run(Workflow('task', {'ready': Transition('start', ('battle',))}),
                                                   TaskLimits(max_duration_seconds=5), token)
                self.assertEqual(StopReason.COMPLETED, result.reason)
                self.assertEqual([], actor.actions)

    def test_composite_action_rechecks_guard_before_second_tap(self):
        from yys_helper.application.runtime import OcrMumuRuntime
        from yys_helper.infrastructure.vision import OcrBox
        from tests.test_activity_replay import ReplayAdb, ReplayVision
        adb = ReplayAdb()
        runtime = OcrMumuRuntime(adb, ReplayVision([[OcrBox('困难', .99, (10, 10, 30, 30))]]), sleeper=lambda _: None)
        runtime.last_boxes = [OcrBox('第二十八章', .99, (10, 10, 30, 30))]
        runtime.input_guard = lambda: len(adb.taps) == 0
        self.assertFalse(runtime.perform('select_chapter_28_hard'))
        self.assertEqual(1, len(adb.taps))

    def test_rest_is_clamped_to_deadline_and_never_launches_new_round(self):
        clock = Clock()
        actor = RecordingActor()
        controller = PacingController(PacingPolicy(rest_rounds=(1, 1), rest_seconds=(20, 20)), random.Random(2))
        workflow = Workflow('loop', {
            'battle': Transition('wait_battle', ('settlement',)),
            'settlement': Transition('again', ('battle',), round_completed=True),
        }, track_battles=True)
        result = AutomationEngine(FakeObserver(['battle', 'settlement']), actor,
            clock=clock, sleeper=clock.sleep, pacing=controller).run(workflow, TaskLimits(max_duration_seconds=5))
        self.assertEqual(StopReason.MAX_DURATION, result.reason)
        self.assertEqual(1, result.rounds)
        self.assertEqual(['wait_battle'], actor.actions)
        self.assertEqual(5, clock.now)

    def test_random_waits_vary_inside_declared_bounds(self):
        controller = PacingController(PacingPolicy(), random.Random(42))
        delays = [controller.action_delay() for _ in range(100)]
        self.assertTrue(all(.4 <= delay <= 1.2 for delay in delays))
        self.assertGreater(len(set(delays)), 90)

    def test_random_clicks_stay_near_center_and_never_leave_box(self):
        controller = PacingController(PacingPolicy(), random.Random(7))
        points = [controller.point((100, 50, 200, 90)) for _ in range(100)]
        self.assertTrue(all(138 <= x <= 162 and 65 <= y <= 75 for x, y in points))
        self.assertGreater(len(set(points)), 5)
        with self.assertRaises(ValueError):
            controller.point((10, 20, 10, 30))

    def test_rest_once_per_completed_batch(self):
        controller = PacingController(PacingPolicy(rest_rounds=(2, 2), rest_seconds=(10, 20)), random.Random(9))
        self.assertEqual(0, controller.rest_duration(1))
        self.assertTrue(10 <= controller.rest_duration(2) <= 20)
        self.assertEqual(0, controller.rest_duration(2))
        self.assertEqual(0, controller.rest_duration(3))

    def test_limits_reject_nonfinite_and_excessive_session_duration(self):
        for duration in (float('nan'), float('inf'), 7201, 0):
            with self.assertRaises(ValueError):
                TaskLimits(max_duration_seconds=duration)

    def test_expiry_during_random_wait_never_clicks(self):
        clock = Clock()
        actor = RecordingActor()
        workflow = Workflow('single', {'ready': Transition('tap', ('battle',))})
        controller = PacingController(PacingPolicy(action_seconds=(2, 3)), random.Random(1))
        result = AutomationEngine(FakeObserver(['ready']), actor, clock=clock, sleeper=clock.sleep,
                                  pacing=controller).run(workflow, TaskLimits(max_duration_seconds=1))
        self.assertEqual(StopReason.MAX_DURATION, result.reason)
        self.assertEqual([], actor.actions)
        self.assertEqual(1, clock.now)

    def test_changed_scene_after_delay_never_uses_stale_action(self):
        clock = Clock()
        actor = RecordingActor()
        workflow = Workflow('single', {'ready': Transition('tap', ('battle',))})
        result = AutomationEngine(FakeObserver(['ready', 'wrong', None, None, None]), actor,
            clock=clock, sleeper=clock.sleep, pacing=PacingController()).run(workflow, TaskLimits())
        self.assertEqual(StopReason.UNRECOGNIZED_SCENE, result.reason)
        self.assertEqual([], actor.actions)

    def test_finish_round_waits_for_settlement_without_clicking_again(self):
        token = CancellationToken()
        class Observer:
            scenes = iter(['battle', 'settlement'])
            def observe(self):
                token.finish_round()
                return next(self.scenes)
        workflow = Workflow('round', {
            'battle': Transition('wait_battle', ('battle', 'settlement')),
            'settlement': Transition('again', ('battle',), round_completed=True),
        }, track_battles=True)
        actor = RecordingActor()
        result = AutomationEngine(Observer(), actor, sleeper=lambda _: None).run(workflow, TaskLimits(), token)
        self.assertEqual(1, result.rounds)
        self.assertEqual(['wait_battle'], actor.actions)
        self.assertEqual(StopReason.COMPLETED, result.reason)
