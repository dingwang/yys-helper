import unittest
from io import BytesIO

from PIL import Image

from yys_helper.application.runtime import OcrMumuRuntime, classify_scene, resolve_action_text
from yys_helper.infrastructure.vision import VisionService
from yys_helper.infrastructure.vision import OcrBox


def box(text, confidence=0.99):
    return OcrBox(text, confidence, (0, 0, 20, 20))


class RuntimeTests(unittest.TestCase):
    def test_safety_scenes_take_priority_over_normal_scene(self):
        scene = classify_scene([box("再次挑战"), box("体力不足")])
        self.assertEqual("stamina_empty", scene)

    def test_recognizes_settlement_and_soul_ready(self):
        self.assertEqual("settlement", classify_scene([box("战斗胜利"), box("获得奖励")]))
        self.assertEqual("soul_ready", classify_scene([box("御魂副本"), box("挑战")]))

    def test_low_confidence_text_does_not_define_scene(self):
        self.assertIsNone(classify_scene([box("体力不足", 0.80)]))

    def test_action_text_map_never_supplies_payment_labels(self):
        self.assertEqual(("再次挑战",), resolve_action_text("challenge_again"))
        all_labels = [label for action in ("open_explore", "start_battle", "confirm") for label in resolve_action_text(action)]
        self.assertNotIn("购买", all_labels)
        self.assertNotIn("勾玉", all_labels)

    def test_chapter_selection_taps_chapter_then_hard_mode(self):
        stream = BytesIO()
        Image.new("RGB", (100, 100), "white").save(stream, format="PNG")

        class FakeAdb:
            def __init__(self):
                self.taps = []

            def screenshot(self):
                return stream.getvalue()

            def tap(self, x, y):
                self.taps.append((x, y))

        class SequencedOcr:
            def __init__(self):
                self.calls = 0

            def read(self, _image):
                self.calls += 1
                if self.calls == 1:
                    return [OcrBox("第二十八章", 0.99, (0, 0, 20, 20))]
                return [OcrBox("困难", 0.99, (40, 40, 60, 60))]

        adb = FakeAdb()
        runtime = OcrMumuRuntime(adb, VisionService(SequencedOcr()), sleeper=lambda _: None)
        runtime.observe()
        self.assertTrue(runtime.perform("select_chapter_28_hard"))
        self.assertEqual([(10, 10), (50, 50)], adb.taps)

    def test_read_only_capture_does_not_replace_automation_observation(self):
        stream = BytesIO()
        Image.new("RGB", (100, 100), "white").save(stream, format="PNG")

        class FakeAdb:
            @staticmethod
            def screenshot():
                return stream.getvalue()

        class SequencedOcr:
            def __init__(self):
                self.calls = 0

            def read(self, _image):
                self.calls += 1
                if self.calls == 1:
                    return [OcrBox("探索地图", 0.99, (0, 0, 20, 20))]
                return [OcrBox("御魂详情", 0.99, (40, 40, 60, 60))]

        runtime = OcrMumuRuntime(FakeAdb(), VisionService(SequencedOcr()))
        runtime.observe()

        captured = runtime.capture_boxes()

        self.assertEqual("御魂详情", captured[0].text)
        self.assertEqual("探索地图", runtime.last_boxes[0].text)


if __name__ == "__main__":
    unittest.main()
