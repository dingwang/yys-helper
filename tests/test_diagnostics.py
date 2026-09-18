import json
import tempfile
import unittest
from pathlib import Path

from yys_helper.infrastructure.diagnostics import CaptureEvidenceWriter
from yys_helper.infrastructure.vision import OcrBox


class CaptureEvidenceWriterTests(unittest.TestCase):
    def test_writer_saves_png_and_machine_readable_ocr(self):
        png = b"\x89PNG\r\n\x1a\ncontent"
        with tempfile.TemporaryDirectory() as folder:
            output = CaptureEvidenceWriter(Path(folder)).write(
                "soul/detail",
                png,
                [OcrBox("招财猫", 0.88, (1, 2, 3, 4))],
                {"serial": "emulator-5556"},
                error="missing level",
            )

            self.assertEqual(png, (output / "screen.png").read_bytes())
            payload = json.loads((output / "ocr.json").read_text("utf-8"))
            self.assertEqual("soul-detail", payload["purpose"])
            self.assertEqual("emulator-5556", payload["metadata"]["serial"])
            self.assertEqual("招财猫", payload["boxes"][0]["text"])
            self.assertEqual([1, 2, 3, 4], payload["boxes"][0]["bounds"])
            self.assertEqual("missing level", payload["error"])


if __name__ == "__main__":
    unittest.main()
