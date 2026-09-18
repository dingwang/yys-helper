import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from yys_helper.application.inventory_capture import SchemeParseError
from yys_helper.application.inventory_import import ImportPreview
from yys_helper.application.runtime import CaptureError
from yys_helper.demo import create_demo_state, create_state
from yys_helper.domain.models import BuildRequirement, Soul, Stat, StopReason, TaskOutcome
from yys_helper.infrastructure.repository import AppRepository
from yys_helper.infrastructure.vision import OcrBox
from yys_helper.ui.app import load_initial_state
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
        self.window.dailies_page.risk_ack.setChecked(True)
        with patch("yys_helper.ui.main_window.QMessageBox.information"):
            self.window.start_task("chapter28", 30, 60)

        self.assertIsNone(self.window.worker)
        self.assertIn("MuMu 当前前台不是《阴阳师》", self.window.log.toPlainText())

    def test_normal_mode_uses_empty_real_inventory_instead_of_demo(self):
        repository = AppRepository(":memory:")
        try:
            state = load_initial_state(repository, demo_mode=False)
            window = MainWindow(state, demo_mode=False, repository=repository)
            try:
                self.assertEqual(0, len(state.inventory))
                self.assertEqual({}, state.requirement.set_counts)
                self.assertEqual({}, state.requirement.min_stats)
                self.assertEqual(0, window.inventory_page.table.rowCount())
                self.assertIn("尚未采集", window.inventory_page.capture_status.text())
            finally:
                window.close()
        finally:
            repository.close()

    def test_normal_mode_loads_existing_real_inventory(self):
        repository = AppRepository(":memory:")
        soul = Soul(
            id="real-001",
            set_name="招财猫",
            slot=2,
            rarity=6,
            level=6,
            main_stat=Stat.SPEED,
            main_value=24,
            substats={Stat.CRIT_RATE: 6},
        )
        repository.save_souls([soul])
        try:
            state = load_initial_state(repository, demo_mode=False)
            self.assertEqual(["real-001"], [item.id for item in state.inventory])
        finally:
            repository.close()

    def test_connect_prefers_saved_adb_path_without_file_picker(self):
        class SuccessfulAdbClient:
            executables: list[str] = []

            def __init__(self, executable: str, serial: str | None = None):
                self.executables.append(executable)
                self.serial = serial

            @staticmethod
            def devices():
                return ["127.0.0.1:16384"]

            @staticmethod
            def screenshot():
                return b"png"

        repository = AppRepository(":memory:")
        with tempfile.TemporaryDirectory() as folder:
            saved_adb = Path(folder) / "adb.exe"
            saved_adb.touch()
            repository.set_setting("adb_path", str(saved_adb))
            window = MainWindow(
                load_initial_state(repository, demo_mode=False),
                demo_mode=False,
                repository=repository,
            )
            try:
                with (
                    patch("yys_helper.ui.main_window.discover_adb", return_value=[]),
                    patch("yys_helper.ui.main_window.AdbClient", SuccessfulAdbClient),
                    patch("yys_helper.ui.main_window.RapidOcrEngine"),
                    patch("yys_helper.ui.main_window.OcrMumuRuntime"),
                    patch.object(window.dashboard, "set_screenshot"),
                    patch(
                        "yys_helper.ui.main_window.QFileDialog.getOpenFileName"
                    ) as file_picker,
                ):
                    window.connect_mumu()

                file_picker.assert_not_called()
                self.assertEqual(str(saved_adb), SuccessfulAdbClient.executables[0])
                self.assertEqual(str(saved_adb), repository.get_setting("adb_path"))
            finally:
                window.close()
                repository.close()

    def test_connect_remembers_manually_selected_adb_path(self):
        class SuccessfulAdbClient:
            def __init__(self, executable: str, serial: str | None = None):
                self.executable = executable
                self.serial = serial

            @staticmethod
            def devices():
                return ["127.0.0.1:16384"]

            @staticmethod
            def screenshot():
                return b"png"

        repository = AppRepository(":memory:")
        with tempfile.TemporaryDirectory() as folder:
            selected_adb = Path(folder) / "adb.exe"
            selected_adb.touch()
            window = MainWindow(
                load_initial_state(repository, demo_mode=False),
                demo_mode=False,
                repository=repository,
            )
            try:
                with (
                    patch("yys_helper.ui.main_window.discover_adb", return_value=[]),
                    patch("yys_helper.ui.main_window.AdbClient", SuccessfulAdbClient),
                    patch("yys_helper.ui.main_window.RapidOcrEngine"),
                    patch("yys_helper.ui.main_window.OcrMumuRuntime"),
                    patch.object(window.dashboard, "set_screenshot"),
                    patch(
                        "yys_helper.ui.main_window.QFileDialog.getOpenFileName",
                        return_value=(str(selected_adb), ""),
                    ) as file_picker,
                ):
                    window.connect_mumu()

                file_picker.assert_called_once()
                self.assertEqual(
                    str(selected_adb), repository.get_setting("adb_path")
                )
            finally:
                window.close()
                repository.close()

    def test_selecting_a_record_loads_its_slot_and_rarity_for_update(self):
        repository = AppRepository(":memory:")
        soul = Soul(
            id="real-update",
            set_name="招财猫",
            slot=4,
            rarity=5,
            level=6,
            main_stat=Stat.HP_PCT,
            main_value=18,
            substats={Stat.SPEED: 6},
        )
        repository.save_souls([soul])
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        try:
            window.inventory_page.set_override.setText("过期覆盖值")
            window.inventory_page.table.selectRow(0)

            self.assertEqual("招财猫", window.inventory_page.set_override.text())
            self.assertEqual(4, window.inventory_page.slot.value())
            self.assertEqual(5, window.inventory_page.rarity.value())
            self.assertTrue(window.inventory_page.capture_update.isEnabled())
        finally:
            window.close()
            repository.close()

    def test_read_only_capture_persists_and_refreshes_real_inventory(self):
        class GameAdb:
            @staticmethod
            def current_package():
                return "com.netease.onmyoji"

        class CaptureRuntime:
            adb = GameAdb()

            @staticmethod
            def capture_evidence():
                return b"png", (
                    OcrBox("御魂详情", 0.99, (900, 35, 1200, 65)),
                    OcrBox("招财猫", 0.99, (900, 80, 1200, 110)),
                    OcrBox("+6", 0.98, (900, 130, 1200, 160)),
                    OcrBox("速度 24", 0.97, (900, 210, 1200, 240)),
                    OcrBox("暴击 +6%", 0.96, (900, 280, 1200, 310)),
                )

        repository = AppRepository(":memory:")
        requirement = create_demo_state().requirement
        window = MainWindow(
            create_state([], requirement), demo_mode=False, repository=repository
        )
        window.runtime = CaptureRuntime()
        try:
            window.capture_current_soul("", 2, 6)

            self.assertEqual(1, window.inventory_page.table.rowCount())
            self.assertEqual(1, len(repository.list_souls()))
            self.assertIn("已采集 1 枚真实御魂", window.inventory_page.capture_status.text())
        finally:
            window.close()
            repository.close()

    def test_identical_souls_can_coexist_and_selected_record_can_update(self):
        class GameAdb:
            @staticmethod
            def current_package():
                return "com.netease.onmyoji"

        class CaptureRuntime:
            adb = GameAdb()

            @staticmethod
            def capture_evidence():
                return b"png", (
                    OcrBox("御魂详情", 0.99, (900, 35, 1200, 65)),
                    OcrBox("招财猫", 0.99, (900, 80, 1200, 110)),
                    OcrBox("+6", 0.98, (900, 130, 1200, 160)),
                    OcrBox("速度 24", 0.97, (900, 210, 1200, 240)),
                    OcrBox("暴击 +6%", 0.96, (900, 280, 1200, 310)),
                )

        repository = AppRepository(":memory:")
        window = MainWindow(
            create_state([], create_demo_state().requirement),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = CaptureRuntime()
        try:
            window.capture_current_soul("", 2, 6)
            window.capture_current_soul("", 2, 6)
            records = repository.list_souls()

            self.assertEqual(2, len(records))
            self.assertNotEqual(records[0].id, records[1].id)

            window.capture_current_soul("", 2, 6, records[0].id)

            self.assertEqual(2, len(repository.list_souls()))
            self.assertEqual(2, window.inventory_page.table.rowCount())
        finally:
            window.close()
            repository.close()

    def test_failed_capture_does_not_write_inventory(self):
        class GameAdb:
            @staticmethod
            def current_package():
                return "com.netease.onmyoji"

        class EmptyRuntime:
            adb = GameAdb()

            @staticmethod
            def capture_evidence():
                return b"png", (OcrBox("御魂详情", 0.99, (10, 10, 100, 40)),)

        repository = AppRepository(":memory:")
        window = MainWindow(
            create_state([], create_demo_state().requirement),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = EmptyRuntime()
        try:
            with patch("yys_helper.ui.main_window.QMessageBox.warning"):
                window.capture_current_soul("", 2, 6)

            self.assertEqual([], repository.list_souls())
            self.assertEqual(0, window.inventory_page.table.rowCount())
            self.assertIn("只读采集失败", window.log.toPlainText())
        finally:
            window.close()
            repository.close()

    def test_capture_rejects_wrong_foreground_before_screenshot(self):
        class LauncherAdb:
            @staticmethod
            def current_package():
                return "app.lawnchair"

        class GuardRuntime:
            adb = LauncherAdb()

            @staticmethod
            def capture_evidence():
                raise AssertionError("must not capture a non-game foreground")

        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = GuardRuntime()
        try:
            with patch("yys_helper.ui.main_window.QMessageBox.information"):
                window.capture_current_soul("", 2, 6)

            self.assertEqual([], repository.list_souls())
        finally:
            window.close()
            repository.close()

    def test_inventory_import_replaces_local_inventory_after_confirmation(self):
        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        payload = {
            "format": "yys-helper.inventory.v1",
            "souls": [
                {
                    "id": "imported-1",
                    "set_name": "火灵",
                    "slot": 6,
                    "rarity": 6,
                    "level": 0,
                    "main_stat": "crit_rate",
                    "main_value": 10,
                    "substats": {"speed": 3},
                }
            ],
        }
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "inventory.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with patch.object(
                    window, "_confirm_inventory_import", return_value=True
                ):
                    window.import_inventory(path)

            self.assertEqual(1, window.inventory_page.table.rowCount())
            self.assertEqual("火灵", repository.list_souls()[0].set_name)
            self.assertIn("导入 1 枚", window.log.toPlainText())
        finally:
            window.close()
            repository.close()

    def test_failed_capture_saves_evidence_and_logs_its_folder(self):
        class GameAdb:
            serial = "emulator-5556"

            @staticmethod
            def current_package():
                return "com.netease.onmyoji"

        class EmptyRuntime:
            adb = GameAdb()

            @staticmethod
            def capture_evidence():
                return b"png", (OcrBox("普通页面", 0.99, (10, 10, 100, 40)),)

        class RecordingWriter:
            def __init__(self):
                self.calls = []

            def write(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return Path("data/diagnostics/failure")

        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = EmptyRuntime()
        writer = RecordingWriter()
        window.evidence_writer = writer
        try:
            with patch("yys_helper.ui.main_window.QMessageBox.warning"):
                window.capture_current_soul("", 2, 6)

            self.assertEqual(1, len(writer.calls))
            self.assertIn("data\\diagnostics\\failure", window.log.toPlainText())
            self.assertIn("error", writer.calls[0][1])
        finally:
            window.close()
            repository.close()

    def test_ocr_failure_after_screenshot_still_saves_raw_evidence(self):
        class GameAdb:
            serial = "emulator-5556"

            @staticmethod
            def current_package():
                return "com.netease.onmyoji"

        class FailingRuntime:
            adb = GameAdb()

            @staticmethod
            def capture_evidence():
                raise CaptureError(
                    "OCR failed", stage="ocr", png=b"raw-png"
                )

        class RecordingWriter:
            def __init__(self):
                self.calls = []

            def write(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return Path("data/diagnostics/ocr-failure")

        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = FailingRuntime()
        writer = RecordingWriter()
        window.evidence_writer = writer
        try:
            with patch("yys_helper.ui.main_window.QMessageBox.warning"):
                window.capture_current_soul("", 2, 6)

            self.assertEqual(b"raw-png", writer.calls[0][0][1])
            self.assertIn("ocr: OCR failed", writer.calls[0][1]["error"])
        finally:
            window.close()
            repository.close()

    def test_import_preview_reports_low_confidence_count(self):
        soul = Soul(
            id="review-import",
            set_name="招财猫",
            slot=2,
            rarity=6,
            level=0,
            main_stat=Stat.SPEED,
            main_value=12,
            substats={},
            confidence=0.80,
        )
        preview = ImportPreview("yys-helper", (soul,))

        with patch(
            "yys_helper.ui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            self.window._confirm_inventory_import(preview)

        self.assertIn("待复核（置信度低于 92%）：1 枚", question.call_args.args[2])

    def test_unknown_task_stop_saves_last_runtime_evidence(self):
        class GameAdb:
            serial = "emulator-5556"

        class RuntimeWithEvidence:
            adb = GameAdb()
            last_capture_png = b"png"
            last_boxes = [OcrBox("未知页面", 0.99, (10, 10, 100, 40))]

        class RecordingWriter:
            def __init__(self):
                self.calls = []

            def write(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return Path("data/diagnostics/unknown")

        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = RuntimeWithEvidence()
        writer = RecordingWriter()
        window.evidence_writer = writer
        try:
            window._task_completed(
                TaskOutcome(
                    StopReason.UNRECOGNIZED_SCENE,
                    "starting",
                    0,
                    3.0,
                )
            )

            self.assertEqual("automation-unknown", writer.calls[0][0][0])
            self.assertIn("data\\diagnostics\\unknown", window.log.toPlainText())
        finally:
            window.close()
            repository.close()

    def test_automation_ocr_failure_saves_last_failed_capture(self):
        class GameAdb:
            serial = "emulator-5556"

        class RuntimeWithFailureEvidence:
            adb = GameAdb()
            last_capture_png = b"raw-png"
            last_boxes = []
            last_capture_error = "OCR 识别失败：engine unavailable"

        class RecordingWriter:
            def __init__(self):
                self.calls = []

            def write(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return Path("data/diagnostics/automation-error")

        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        window.runtime = RuntimeWithFailureEvidence()
        writer = RecordingWriter()
        window.evidence_writer = writer
        try:
            window._task_failed("OCR 识别失败")

            self.assertEqual("automation-error", writer.calls[0][0][0])
            self.assertEqual(b"raw-png", writer.calls[0][0][1])
            self.assertIn("automation-error", window.log.toPlainText())
        finally:
            window.close()
            repository.close()

    def test_user_can_delete_an_incorrect_local_record(self):
        repository = AppRepository(":memory:")
        soul = Soul(
            id="incorrect-001",
            set_name="招财猫",
            slot=1,
            rarity=6,
            level=0,
            main_stat=Stat.ATTACK,
            main_value=486,
            substats={},
        )
        repository.save_souls([soul])
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        try:
            with patch(
                "yys_helper.ui.main_window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.delete_soul_record(soul.id)

            self.assertEqual([], repository.list_souls())
            self.assertEqual(0, window.inventory_page.table.rowCount())
        finally:
            window.close()
            repository.close()

    def test_window_has_application_icon(self):
        self.assertFalse(self.window.windowIcon().isNull())

    def test_demo_mode_disables_all_live_read_controls(self):
        self.assertFalse(self.window.connect_button.isEnabled())
        self.assertFalse(self.window.scheme_page.read_game.isEnabled())
        self.assertFalse(self.window.inventory_page.capture_new.isEnabled())

    def test_running_task_disables_capture_scheme_connect_and_new_tasks(self):
        repository = AppRepository(":memory:")
        window = MainWindow(
            load_initial_state(repository, demo_mode=False),
            demo_mode=False,
            repository=repository,
        )
        try:
            window.dailies_page.risk_ack.setChecked(True)
            window._set_task_active(True)

            self.assertFalse(window.connect_button.isEnabled())
            self.assertFalse(window.scheme_page.read_game.isEnabled())
            self.assertFalse(window.inventory_page.capture_new.isEnabled())
            self.assertTrue(
                all(
                    not button.isEnabled()
                    for button in window.dailies_page.task_buttons
                )
            )

            window._set_task_active(False)
            self.assertTrue(window.connect_button.isEnabled())
            self.assertTrue(window.scheme_page.read_game.isEnabled())
            self.assertTrue(window.inventory_page.capture_new.isEnabled())
        finally:
            window.close()
            repository.close()

    def test_low_confidence_inventory_row_is_marked_for_review(self):
        soul = Soul(
            id="review-001",
            set_name="招财猫",
            slot=1,
            rarity=6,
            level=0,
            main_stat=Stat.ATTACK,
            main_value=486,
            substats={Stat.HP_PCT: 3},
            confidence=0.85,
        )

        self.window.inventory_page.populate(
            create_state([soul], create_demo_state().requirement), demo_mode=False
        )

        self.assertEqual(
            "待复核", self.window.inventory_page.table.item(0, 7).text()
        )

    def test_daily_buttons_require_explicit_risk_acknowledgement(self):
        self.assertTrue(
            all(not button.isEnabled() for button in self.window.dailies_page.task_buttons)
        )

        self.window.dailies_page.risk_ack.setChecked(True)

        self.assertTrue(
            all(button.isEnabled() for button in self.window.dailies_page.task_buttons)
        )

    def test_task_without_risk_ack_does_not_query_device(self):
        class GuardAdb:
            @staticmethod
            def current_package():
                raise AssertionError("device must not be queried before acknowledgement")

        class GuardRuntime:
            adb = GuardAdb()

        self.window.runtime = GuardRuntime()
        with patch("yys_helper.ui.main_window.QMessageBox.information"):
            self.window.start_task("chapter28", 30, 60)

        self.assertIsNone(self.window.worker)
        self.assertIn("尚未确认账号风险", self.window.log.toPlainText())

    def test_panel_thresholds_are_converted_to_soul_only_values(self):
        requirement = BuildRequirement(
            min_stats={Stat.SPEED: 115},
            weights={Stat.SPEED: 1},
        )

        converted = MainWindow._convert_panel_thresholds(
            requirement, base_speed=100
        )

        self.assertEqual(15.0, converted.min_stats[Stat.SPEED])

        with self.assertRaisesRegex(SchemeParseError, "基础速度"):
            MainWindow._convert_panel_thresholds(requirement, base_speed=0)

        unsupported = BuildRequirement(min_stats={Stat.CRIT_RATE: 100})
        with self.assertRaisesRegex(SchemeParseError, "暂不支持.*暴击"):
            MainWindow._convert_panel_thresholds(unsupported, base_speed=100)


if __name__ == "__main__":
    unittest.main()
