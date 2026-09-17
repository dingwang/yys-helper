import tempfile
import unittest
from pathlib import Path

from yys_helper.application.schemes import (
    InvalidSchemeCode,
    SchemeService,
    normalize_scheme_code,
)


class RecordingSchemeActor:
    def __init__(self):
        self.text_codes = []
        self.qr_paths = []

    def import_text(self, code):
        self.text_codes.append(code)
        return True

    def import_qr(self, path):
        self.qr_paths.append(path)
        return True


class SchemeTests(unittest.TestCase):
    def test_normalizes_ta_code_whitespace(self):
        self.assertEqual("|TA|abc123", normalize_scheme_code("  |TA|abc123\n"))

    def test_rejects_shell_metacharacters(self):
        with self.assertRaises(InvalidSchemeCode):
            normalize_scheme_code("|TA|abc;rm")

    def test_service_passes_normalized_code_as_data(self):
        actor = RecordingSchemeActor()
        self.assertTrue(SchemeService(actor).import_text(" |TA|a1b2c3 "))
        self.assertEqual(["|TA|a1b2c3"], actor.text_codes)

    def test_qr_import_accepts_local_png(self):
        actor = RecordingSchemeActor()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scheme.png"
            path.write_bytes(b"fake image")
            self.assertTrue(SchemeService(actor).import_qr(path))
            self.assertEqual([path.resolve()], actor.qr_paths)


if __name__ == "__main__":
    unittest.main()
