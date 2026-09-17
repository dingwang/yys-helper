import unittest
from types import SimpleNamespace
from unittest.mock import patch

from yys_helper.infrastructure.vision import (
    OcrBox,
    RapidOcrEngine,
    VisionService,
    normalized_to_pixels,
)


class FakeOcr:
    def __init__(self, boxes):
        self.boxes = boxes

    def read(self, image):
        return self.boxes


class VisionTests(unittest.TestCase):
    def test_normalized_point_scales_to_actual_frame(self):
        self.assertEqual((960, 540), normalized_to_pixels((0.75, 0.75), (1280, 720)))

    def test_normalized_point_rejects_out_of_range_value(self):
        with self.assertRaises(ValueError):
            normalized_to_pixels((1.1, 0.5), (1280, 720))

    def test_find_text_rejects_result_below_threshold(self):
        vision = VisionService(FakeOcr([OcrBox("挑战", 0.80, (10, 20, 30, 40))]))
        self.assertIsNone(vision.find_text(object(), "挑战", min_confidence=0.92))

    def test_find_text_returns_highest_confidence_match(self):
        vision = VisionService(
            FakeOcr(
                [
                    OcrBox("挑战", 0.93, (0, 0, 10, 10)),
                    OcrBox("再次挑战", 0.98, (20, 20, 40, 40)),
                ]
            )
        )
        self.assertEqual((20, 20, 40, 40), vision.find_text(object(), "挑战").bounds)

    def test_rapidocr_adapter_selects_mnn_for_all_stages(self):
        captured = {}

        class FakeRapidOCR:
            def __init__(self, *, params):
                captured.update(params)

        fake_module = SimpleNamespace(
            RapidOCR=FakeRapidOCR,
            EngineType=SimpleNamespace(MNN="mnn"),
        )
        with patch.dict("sys.modules", {"rapidocr": fake_module}):
            RapidOcrEngine()._load()
        self.assertEqual(
            {
                "Det.engine_type": "mnn",
                "Cls.engine_type": "mnn",
                "Rec.engine_type": "mnn",
            },
            captured,
        )


if __name__ == "__main__":
    unittest.main()
