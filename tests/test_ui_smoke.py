import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from yys_helper.demo import create_demo_state
from yys_helper.ui.main_window import MainWindow


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow(create_demo_state(), demo_mode=True)

    def tearDown(self):
        self.window.close()

    def test_main_window_contains_five_product_pages(self):
        self.assertEqual(5, self.window.stack.count())
        self.assertEqual(
            ["总览", "方案配装", "御魂仓库", "强化建议", "日常任务"],
            [button.text() for button in self.window.nav_buttons],
        )

    def test_emergency_stop_cancels_current_token(self):
        self.window.stop_task()
        self.assertTrue(self.window.cancel_token.is_cancelled())

    def test_invalid_scheme_does_not_reach_clipboard(self):
        QApplication.clipboard().setText("sentinel")
        with patch("yys_helper.ui.main_window.QMessageBox.warning"):
            self.window.analyze_scheme("|TA|bad;value")
        self.assertEqual("sentinel", QApplication.clipboard().text())

    def test_task_does_not_start_when_game_is_not_foreground(self):
        class LauncherAdb:
            @staticmethod
            def current_package():
                return "app.lawnchair"

        class LauncherRuntime:
            adb = LauncherAdb()

        self.window.runtime = LauncherRuntime()
        with patch("yys_helper.ui.main_window.QMessageBox.information"):
            self.window.start_task("chapter28", 30, 60)

        self.assertIsNone(self.window.worker)
        self.assertIn("MuMu 当前前台不是《阴阳师》", self.window.log.toPlainText())


if __name__ == "__main__":
    unittest.main()
