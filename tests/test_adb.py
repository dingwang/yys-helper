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

    def test_connect_uses_global_adb_command_and_accepts_already_connected(self):
        runner = RecordingRunner(stdout=b"already connected to 127.0.0.1:16384\n")
        client = AdbClient("adb.exe", runner=runner)
        self.assertTrue(client.connect("127.0.0.1:16384"))
        self.assertEqual(
            ("adb.exe", "connect", "127.0.0.1:16384"), runner.calls[0][0]
        )

    def test_current_package_parses_the_top_activity(self):
        output = (
            b"topResumedActivity=ActivityRecord{abc u0 "
            b"app.lawnchair/.LawnchairLauncher t2}\n"
        )
        runner = RecordingRunner(stdout=output)
        client = AdbClient("adb.exe", "emulator-5556", runner=runner)

        self.assertEqual("app.lawnchair", client.current_package())
        self.assertEqual(
            (
                "adb.exe",
                "-s",
                "emulator-5556",
                "shell",
                "dumpsys",
                "activity",
                "activities",
            ),
            runner.calls[0][0],
        )

    def test_current_package_ignores_background_launcher_activity(self):
        output = (
            b"ACTIVITY app.lawnchair/.LawnchairLauncher pid=1072\n"
            b"topResumedActivity=ActivityRecord{abc u0 "
            b"com.netease.onmyoji.wyzymnqsd_cps/com.netease.onmyoji.Client t8}\n"
        )
        client = AdbClient(
            "adb.exe", "emulator-5556", runner=RecordingRunner(stdout=output)
        )

        self.assertEqual(
            "com.netease.onmyoji.wyzymnqsd_cps", client.current_package()
        )


if __name__ == "__main__":
    unittest.main()
