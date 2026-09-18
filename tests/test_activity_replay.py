"""Replay real runtime boundaries with generated PNGs and recorded OCR output."""
from io import BytesIO
import unittest
from PIL import Image

from yys_helper.application.runtime import OcrMumuRuntime
from yys_helper.automation.catalog import TaskProfile, workflow_for
from yys_helper.automation.engine import AutomationEngine
from yys_helper.domain.models import TaskLimits, StopReason
from tests.test_task_catalog import boxes


class ReplayAdb:
    def __init__(self):
        image = BytesIO()
        Image.new('RGB', (1280, 720)).save(image, format='PNG')
        self.png = image.getvalue()
        self.taps = []

    def screenshot(self):
        return self.png

    def tap(self, x, y):
        self.taps.append((x, y))

    def current_package(self):
        return 'com.netease.onmyoji'


class ReplayVision:
    def __init__(self, frames):
        self.frames = iter(frames)

    def read(self, _image):
        return next(self.frames, [])


class ActivityReplayTests(unittest.TestCase):
    def runtime(self, frames):
        runtime = OcrMumuRuntime(ReplayAdb(), ReplayVision(frames))
        runtime.task_profile = TaskProfile(('月海试炼',))
        return runtime

    def test_full_loop_to_final_reward_does_not_start_extra_battle(self):
        runtime = self.runtime([
            boxes('月海试炼', '挑战'), boxes('准备'), boxes('自动', '回合'),
            boxes('获得奖励', '继续'), boxes('获得奖励', '继续'), boxes('再次挑战'),
            boxes('自动', '回合'), boxes('战斗胜利', '再次挑战'),
        ])
        result = AutomationEngine(runtime, runtime, sleeper=lambda _: None).run(
            workflow_for('event_stage'), TaskLimits(max_rounds=2))
        self.assertEqual(StopReason.MAX_ROUNDS, result.reason)
        self.assertEqual(2, result.rounds)
        self.assertEqual(5, len(runtime.adb.taps))

    def test_ambiguous_button_is_not_clicked(self):
        runtime = self.runtime([boxes('月海试炼', '挑战', '挑战')])
        result = AutomationEngine(runtime, runtime, sleeper=lambda _: None).run(
            workflow_for('event_stage'), TaskLimits())
        self.assertEqual(StopReason.UNRECOGNIZED_SCENE, result.reason)
        self.assertEqual([], runtime.adb.taps)

    def test_purchase_dialog_and_low_confidence_never_click(self):
        for frame in (boxes('月海试炼', '挑战', '购买'),
                      [type(box) (box.text, .6, box.bounds) for box in boxes('月海试炼', '挑战')]):
            runtime = self.runtime([frame] * 3)
            result = AutomationEngine(runtime, runtime, sleeper=lambda _: None).run(
                workflow_for('event_stage'), TaskLimits())
            self.assertIn(result.reason, (StopReason.ACTION_FAILED, StopReason.UNRECOGNIZED_SCENE))
            self.assertEqual([], runtime.adb.taps)

    def test_worker_cancel_during_preflight_reports_stopped(self):
        from yys_helper.ui.main_window import TaskWorker
        from yys_helper.automation.engine import CancellationToken
        token = CancellationToken()
        runtime = self.runtime([boxes('月海试炼', '挑战')])
        original = runtime.observe
        def cancel_observe():
            scene = original()
            token.cancel()
            return scene
        runtime.observe = cancel_observe
        worker = TaskWorker(runtime, 'event_stage', TaskLimits(), token, runtime.task_profile)
        results = []
        worker.completed.connect(results.append)
        worker.run()
        self.assertEqual(1, len(results))
        self.assertEqual(StopReason.CANCELLED, results[0].reason)
        self.assertEqual([], runtime.adb.taps)

    def test_session_rechecks_game_foreground_without_clicking_other_app(self):
        from yys_helper.ui.main_window import TaskWorker
        from yys_helper.automation.engine import CancellationToken
        runtime = self.runtime([boxes('月海试炼', '挑战')])
        runtime.adb.current_package = lambda: 'other.app'
        worker = TaskWorker(runtime, 'event_stage', TaskLimits(), CancellationToken(), runtime.task_profile)
        results = []
        worker.completed.connect(results.append)
        worker.run()
        self.assertTrue(results)
        self.assertIn('前台', results[0].message)
        self.assertEqual([], runtime.adb.taps)
