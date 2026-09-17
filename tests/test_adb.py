import subprocess
import unittest

from yys_helper.infrastructure.adb import AdbClient, AdbError


class RecordingRunner:
    def __init__(self, stdout=b"", returncode=0):
        self.stdout = stdout
        self.returncode = returncode
        self.calls = []

    def __call__(self, args, *, timeout):
        self.calls.append((tuple(args), timeout))
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, b"")


class AdbTests(unittest.TestCase):
    def test_screenshot_uses_selected_serial_and_returns_png(self):
        runner = RecordingRunner(stdout=b"\x89PNG\r\n\x1a\ncontent")
        client = AdbClient("adb.exe", "127.0.0.1:16384", runner=runner)
        self.assertTrue(client.screenshot().startswith(b"\x89PNG"))
        self.assertEqual(
            ("adb.exe", "-s", "127.0.0.1:16384", "exec-out", "screencap", "-p"),
            runner.calls[0][0],
        )

    def test_screenshot_rejects_non_png_output(self):
        client = AdbClient("adb.exe", "device", runner=RecordingRunner(b"oops"))
        with self.assertRaisesRegex(AdbError, "PNG"):
            client.screenshot()

    def test_devices_parses_only_ready_devices(self):
        output = b"List of devices attached\r\nA\tdevice\r\nB\toffline\r\n\r\n"
        client = AdbClient("adb.exe", runner=RecordingRunner(output))
        self.assertEqual(["A"], client.devices())

    def test_tap_rejects_negative_coordinates(self):
        client = AdbClient("adb.exe", "device", runner=RecordingRunner())
        with self.assertRaises(ValueError):
            client.tap(-1, 20)


if __name__ == "__main__":
    unittest.main()
