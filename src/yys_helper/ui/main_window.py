from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from yys_helper.application.runtime import CaptureError, OcrMumuRuntime
from yys_helper.application.inventory_capture import (
    SchemeParseError,
    SchemeRequirementParser,
    SoulDetailParser,
    SoulParseError,
)
from yys_helper.application.inventory_import import (
    ImportPreview,
    InventoryImportError,
    load_inventory_file,
)
from yys_helper.application.schemes import (
    InvalidSchemeCode,
    decode_qr_scheme,
    normalize_scheme_code,
)
from yys_helper.automation.engine import AutomationEngine, CancellationToken
from yys_helper.automation.catalog import get_task, workflow_for
from yys_helper.ui.task_center import TaskCenterPage
from yys_helper.demo import DemoState, create_state
from yys_helper.domain.models import BuildRequirement, Stat, StopReason, TaskLimits, UpgradeBudget
from yys_helper.domain.upgrade import rank_upgrade_candidates
from yys_helper.domain.safety import protection_reasons
from yys_helper.domain.scoring import DEFAULT_PROFILES, score_soul
from yys_helper.infrastructure.adb import AdbClient, AdbError, discover_adb
from yys_helper.infrastructure.diagnostics import CaptureEvidenceWriter
from yys_helper.infrastructure.repository import AppRepository
from yys_helper.infrastructure.vision import OcrBox, RapidOcrEngine, VisionService


STAT_LABELS = {
    Stat.ATTACK: "攻击",
    Stat.HP: "生命",
    Stat.DEFENSE: "防御",
    Stat.SPEED: "速度",
    Stat.CRIT_RATE: "暴击",
    Stat.CRIT_DAMAGE: "暴伤",
    Stat.ATTACK_PCT: "攻击加成",
    Stat.HP_PCT: "生命加成",
    Stat.DEFENSE_PCT: "防御加成",
    Stat.EFFECT_HIT: "效果命中",
    Stat.EFFECT_RESIST: "效果抵抗",
}


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    return frame, layout


def page_title(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 22)
    heading = QLabel(title)
    heading.setObjectName("title")
    sub = QLabel(subtitle)
    sub.setObjectName("muted")
    sub.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(sub)
    layout.addSpacing(10)
    return page, layout


class DashboardPage(QWidget):
    navigate_requested = Signal(int)

    def __init__(self, demo: DemoState) -> None:
        super().__init__()
        page, layout = page_title("今天，也轻松一点。", "整理御魂，规划配装，让重复的操作更少一些。")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        metrics = QHBoxLayout()
        self.metric_values: list[QLabel] = []
        for label, value in (
            ("已扫描御魂", str(len(demo.inventory))),
            ("当前缺口", str(len(demo.closest_build.shortfalls))),
            ("强化候选", str(len(demo.upgrade_candidates))),
        ):
            frame, inner = card()
            number = QLabel(value)
            number.setObjectName("metric")
            self.metric_values.append(number)
            inner.addWidget(number)
            name = QLabel(label)
            name.setObjectName("muted")
            inner.addWidget(name)
            metrics.addWidget(frame)
        layout.addLayout(metrics)

        quick_actions = QHBoxLayout()
        for label, destination in (('整理我的御魂', 2), ('查看配装方案', 1), ('选择挂机玩法', 4)):
            button = QPushButton(label)
            if destination == 4:
                button.setObjectName('primary')
            button.clicked.connect(lambda _checked=False, page=destination: self.navigate_requested.emit(page))
            quick_actions.addWidget(button)
        layout.addLayout(quick_actions)

        preview_card, preview_layout = card()
        caption = QLabel("设备预览 · 连接时截图")
        caption.setStyleSheet("font-weight: 700; font-size: 15px")
        self.preview = QLabel("尚未连接模拟器\n\n点击右上角“连接 MuMu”开始")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(360)
        self.preview.setStyleSheet(
            "background:#F6F8FB;border:1px dashed #D1D9E4;border-radius:12px;color:#8590A1"
        )
        preview_layout.addWidget(caption)
        preview_layout.addWidget(self.preview, 1)
        layout.addWidget(preview_card, 1)

    def update_state(self, state: DemoState) -> None:
        values = (
            len(state.inventory),
            len(state.closest_build.shortfalls),
            len(state.upgrade_candidates),
        )
        for label, value in zip(self.metric_values, values, strict=True):
            label.setText(str(value))

    def set_screenshot(self, png: bytes) -> None:
        image = QImage.fromData(png, "PNG")
        pixmap = QPixmap.fromImage(image)
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class SchemePage(QWidget):
    analyze_requested = Signal(str)
    qr_requested = Signal(Path)
    read_game_requested = Signal(int)

    def __init__(self, demo: DemoState, *, demo_mode: bool) -> None:
        super().__init__()
        self.demo_mode = demo_mode
        page, layout = page_title(
            "方案配装",
            "导入他人的文字码或二维码；先匹配现有御魂，未达标时转入强化建议。",
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        input_card, inner = card()
        inner.addWidget(QLabel("文字方案码"))
        self.code = QPlainTextEdit()
        self.code.setPlaceholderText("粘贴以 |TA| 开头的方案码")
        self.code.setMaximumHeight(100)
        inner.addWidget(self.code)
        row = QHBoxLayout()
        analyze = QPushButton("校验并复制")
        analyze.setObjectName("primary")
        analyze.clicked.connect(lambda: self.analyze_requested.emit(self.code.toPlainText()))
        qr = QPushButton("选择二维码图片")
        qr.clicked.connect(self._choose_qr)
        self.read_game = QPushButton("读取当前游戏方案")
        self.read_game.setToolTip("只读取当前 MuMu 截图，不发送点击")
        self.read_game.setEnabled(not demo_mode)
        self.read_game.clicked.connect(
            lambda: self.read_game_requested.emit(self.base_speed.value())
        )
        row.addWidget(analyze)
        row.addWidget(qr)
        row.addWidget(self.read_game)
        row.addStretch()
        inner.addLayout(row)
        base_row = QHBoxLayout()
        base_hint = QLabel("面板阈值换算")
        base_hint.setObjectName("muted")
        base_row.addWidget(base_hint)
        base_row.addWidget(QLabel("式神基础速度"))
        self.base_speed = QSpinBox()
        self.base_speed.setRange(0, 300)
        self.base_speed.setSpecialValueText("未填写")
        base_row.addWidget(self.base_speed)
        base_row.addStretch()
        inner.addLayout(base_row)
        layout.addWidget(input_card)

        result_card, result_layout = card()
        self.result_caption = QLabel(
            "演示库存结果" if demo_mode else "真实库存结果"
        )
        result_layout.addWidget(self.result_caption)
        status = self._status_text(demo)
        self.result = QLabel(status)
        self.result.setStyleSheet("font-size:18px;font-weight:700;color:#007AFF")
        result_layout.addWidget(self.result)
        details = []
        for stat, gap in demo.closest_build.shortfalls.items():
            label = STAT_LABELS.get(stat, stat.value)
            details.append(
                f"{label} 还差 {gap:g}"
                if gap >= 0
                else f"{label} 超过上限 {-gap:g}"
            )
        self.details = QLabel("；".join(details) or self._empty_or_satisfied(demo))
        self.details.setWordWrap(True)
        result_layout.addWidget(self.details)
        layout.addWidget(result_card)
        layout.addStretch()

    @staticmethod
    def _status_text(state: DemoState) -> str:
        if not state.inventory:
            return "等待真实御魂数据"
        return "满足全部条件" if state.closest_build.satisfied else "现有御魂未完全达标"

    @staticmethod
    def _empty_or_satisfied(state: DemoState) -> str:
        return "请先到御魂仓库采集详情" if not state.inventory else "可直接应用六件套"

    def update_state(self, state: DemoState, *, demo_mode: bool) -> None:
        self.result_caption.setText("演示库存结果" if demo_mode else "真实库存结果")
        self.result.setText(self._status_text(state))
        details = []
        for stat, gap in state.closest_build.shortfalls.items():
            label = STAT_LABELS.get(stat, stat.value)
            details.append(
                f"{label} 还差 {gap:g}"
                if gap >= 0
                else f"{label} 超过上限 {-gap:g}"
            )
        self.details.setText("；".join(details) or self._empty_or_satisfied(state))

    def set_live_enabled(self, enabled: bool) -> None:
        self.read_game.setEnabled(enabled and not self.demo_mode)

    def _choose_qr(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择方案码图片", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if filename:
            self.qr_requested.emit(Path(filename))


class InventoryPage(QWidget):
    capture_requested = Signal(str, int, int, str)
    delete_requested = Signal(str)
    import_requested = Signal(object)
    diagnostic_requested = Signal()
    open_diagnostics_requested = Signal()

    def __init__(self, demo: DemoState, *, demo_mode: bool) -> None:
        super().__init__()
        self.demo_mode = demo_mode
        self._live_enabled = not demo_mode
        page, layout = page_title(
            "御魂仓库", "只读采集当前御魂详情；受保护的御魂永远不会自动弃置或作为材料。"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        capture_card, capture_layout = card()
        capture_title = QLabel("真实数据采集")
        capture_title.setStyleSheet("font-size:16px;font-weight:700")
        capture_layout.addWidget(capture_title)
        capture_hint = QLabel(
            "在游戏中手动打开一枚御魂详情，确认位置与星级后读取。助手只截屏，不会点击游戏。"
        )
        capture_hint.setObjectName("muted")
        capture_hint.setWordWrap(True)
        capture_layout.addWidget(capture_hint)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("套装名覆盖"))
        self.set_override = QLineEdit()
        self.set_override.setPlaceholderText("留空自动识别")
        self.set_override.setMaximumWidth(180)
        controls.addWidget(self.set_override)
        controls.addWidget(QLabel("位置"))
        self.slot = QSpinBox()
        self.slot.setRange(1, 6)
        self.slot.setValue(1)
        controls.addWidget(self.slot)
        controls.addWidget(QLabel("星级"))
        self.rarity = QSpinBox()
        self.rarity.setRange(1, 6)
        self.rarity.setValue(6)
        controls.addWidget(self.rarity)
        self.capture_new = QPushButton("新增读取")
        self.capture_new.setObjectName("primary")
        self.capture_new.clicked.connect(
            lambda: self.capture_requested.emit(
                self.set_override.text(), self.slot.value(), self.rarity.value(), ""
            )
        )
        controls.addWidget(self.capture_new)
        controls.addStretch()
        capture_layout.addLayout(controls)
        record_controls = QHBoxLayout()
        record_hint = QLabel("选中表格中的记录后，可重新读取覆盖或从本地仓库删除。")
        record_hint.setObjectName("muted")
        record_hint.setWordWrap(True)
        capture_layout.addWidget(record_hint)
        self.import_json = QPushButton("导入库存 JSON")
        self.import_json.clicked.connect(self._choose_inventory)
        record_controls.addWidget(self.import_json)
        self.save_diagnostic = QPushButton("保存诊断采集")
        self.save_diagnostic.clicked.connect(self.diagnostic_requested.emit)
        record_controls.addWidget(self.save_diagnostic)
        self.open_diagnostics = QPushButton("打开诊断目录")
        self.open_diagnostics.clicked.connect(
            self.open_diagnostics_requested.emit
        )
        record_controls.addWidget(self.open_diagnostics)
        self.capture_update = QPushButton("更新选中")
        self.capture_update.clicked.connect(self._emit_update)
        record_controls.addWidget(self.capture_update)
        self.delete_selected = QPushButton("删除选中记录")
        self.delete_selected.setObjectName("danger")
        self.delete_selected.clicked.connect(self._emit_delete)
        record_controls.addWidget(self.delete_selected)
        record_controls.addStretch()
        capture_layout.addLayout(record_controls)
        self.capture_status = QLabel()
        self.capture_status.setObjectName("statusPill")
        capture_layout.addWidget(self.capture_status)
        layout.addWidget(capture_card)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["套装", "位置", "星级", "等级", "主属性", "速度", "输出分", "保护状态"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_record_buttons)
        self.populate(demo, demo_mode=demo_mode)
        layout.addWidget(self.table, 1)
        self.set_live_enabled(not demo_mode)

    def populate(self, demo: DemoState, *, demo_mode: bool) -> None:
        self._souls_by_id = {soul.id: soul for soul in demo.inventory}
        self.table.setRowCount(len(demo.inventory))
        for row, soul in enumerate(demo.inventory):
            reasons = protection_reasons(soul, demo.requirement.referenced_soul_ids)
            review_state = (
                "待复核"
                if "low_confidence" in reasons
                else "已保护" if reasons else "可评估"
            )
            values = (
                soul.set_name,
                str(soul.slot),
                f"{soul.rarity}星",
                f"+{soul.level}",
                STAT_LABELS.get(soul.main_stat, soul.main_stat.value),
                f"{soul.stat_value(Stat.SPEED):g}",
                f"{score_soul(soul, DEFAULT_PROFILES['output']):.1f}",
                review_state,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, soul.id)
                self.table.setItem(row, column, item)
        if demo_mode:
            self.capture_status.setText(f"演示模式 · {len(demo.inventory)} 枚样例御魂")
        elif demo.inventory:
            self.capture_status.setText(f"已采集 {len(demo.inventory)} 枚真实御魂 · 数据仅保存在本机")
        else:
            self.capture_status.setText("尚未采集真实御魂")
        self._update_record_buttons()

    def selected_soul_id(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else ""

    def _emit_update(self) -> None:
        soul_id = self.selected_soul_id()
        if soul_id:
            self.capture_requested.emit(
                self.set_override.text(),
                self.slot.value(),
                self.rarity.value(),
                soul_id,
            )

    def _emit_delete(self) -> None:
        soul_id = self.selected_soul_id()
        if soul_id:
            self.delete_requested.emit(soul_id)

    def _choose_inventory(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择御魂库存 JSON", "", "JSON (*.json)"
        )
        if filename:
            self.import_requested.emit(Path(filename))

    def _update_record_buttons(self) -> None:
        soul_id = self.selected_soul_id()
        has_selection = bool(soul_id)
        selected = self._souls_by_id.get(soul_id)
        if selected is not None:
            self.set_override.setText(selected.set_name)
            self.slot.setValue(selected.slot)
            self.rarity.setValue(selected.rarity)
        enabled = self._live_enabled and not self.demo_mode
        self.capture_update.setEnabled(enabled and has_selection)
        self.delete_selected.setEnabled(enabled and has_selection)

    def set_live_enabled(self, enabled: bool) -> None:
        self._live_enabled = enabled
        available = enabled and not self.demo_mode
        self.capture_new.setEnabled(available)
        self.import_json.setEnabled(available)
        self.save_diagnostic.setEnabled(available)
        self.set_override.setEnabled(available)
        self.slot.setEnabled(available)
        self.rarity.setEnabled(available)
        self._update_record_buttons()


class UpgradePage(QWidget):
    def __init__(self, demo: DemoState) -> None:
        super().__init__()
        page, layout = page_title(
            "强化建议", "按对方案缺口的贡献/金币成本排序；每次只强化 3 级并重新判断。"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        budget_card, budget_layout = card()
        budget_row = QHBoxLayout()
        budget_row.addWidget(QLabel("金币预算"))
        self.coins = QSpinBox()
        self.coins.setRange(0, 99_999_999)
        self.coins.setValue(800_000)
        self.coins.setSingleStep(100_000)
        budget_row.addWidget(self.coins)
        budget_row.addWidget(QLabel("最多胚子"))
        self.max_souls = QSpinBox()
        self.max_souls.setRange(1, 50)
        self.max_souls.setValue(5)
        budget_row.addWidget(self.max_souls)
        budget_row.addStretch()
        budget_layout.addLayout(budget_row)
        layout.addWidget(budget_card)

        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["优先级", "套装/位置", "当前", "下一检查点", "预计金币", "命中目标"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.populate(demo)
        self.coins.valueChanged.connect(lambda _: self.populate(self._state))
        self.max_souls.valueChanged.connect(lambda _: self.populate(self._state))
        layout.addWidget(self.table, 1)

    def populate(self, demo: DemoState) -> None:
        self._state = demo
        ranked = rank_upgrade_candidates(demo.inventory, demo.requirement, UpgradeBudget(
            max_coins=self.coins.value(), max_materials=40,
            max_souls=len(demo.inventory), max_level=15, min_expected_gain=.1))
        candidates = []
        remaining = self.coins.value()
        for candidate in ranked:
            if candidate.estimated_coins <= remaining and len(candidates) < self.max_souls.value():
                candidates.append(candidate)
                remaining -= candidate.estimated_coins
        self.table.setRowCount(len(candidates))
        for row, candidate in enumerate(candidates):
            values = (
                str(row + 1),
                f"{candidate.soul.set_name} · {candidate.soul.slot}号位",
                f"+{candidate.soul.level}",
                f"+{candidate.next_level}",
                f"{candidate.estimated_coins:,}",
                " / ".join(STAT_LABELS.get(Stat(reason), reason) for reason in candidate.reasons),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))




class TaskWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, float)

    def __init__(
        self,
        runtime: OcrMumuRuntime,
        mode: str,
        limits: TaskLimits,
        token: CancellationToken,
        profile=None,
    ):
        super().__init__()
        self.runtime = runtime
        self.mode = mode
        self.limits = limits
        self.token = token
        self.profile = profile

    def run(self) -> None:
        try:
            workflow = workflow_for(self.mode)
            self.runtime.task_profile = self.profile
            self._first_observation = True
            self.progress.emit('starting', 0, 0.)
            result = AutomationEngine(self, self.runtime, progress=self.progress.emit).run(
                workflow, self.limits, self.token
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.runtime.task_profile = None

    def observe(self):
        package = self.runtime.adb.current_package()
        if not package or 'onmyoji' not in package.lower():
            raise RuntimeError('游戏已不在前台，已停止。')
        scene = self.runtime.observe()
        if self._first_observation and self.profile is not None and scene != 'ready':
            raise ValueError('启动预检未通过：请进入所选关卡挑战页，并核对标题和挑战按钮。未发送点击。')
        self._first_observation = False
        return scene


class MainWindow(QMainWindow):
    def __init__(
        self,
        demo: DemoState,
        *,
        demo_mode: bool = False,
        repository: AppRepository | None = None,
    ) -> None:
        super().__init__()
        self.demo = demo
        self.current_requirement = demo.requirement
        self.demo_mode = demo_mode
        self.repository = repository
        self.evidence_writer = CaptureEvidenceWriter(
            Path.cwd() / "data" / "diagnostics"
        )
        self.runtime: OcrMumuRuntime | None = None
        self.worker: TaskWorker | None = None
        self.cancel_token = CancellationToken()
        self.setWindowTitle("御魂匠 · 阴阳师助手")
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "app-icon.png"
        self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1280, 820)
        self.setMinimumSize(1050, 680)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(202)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(18, 22, 18, 18)
        brand_row = QHBoxLayout()
        brand_icon = QLabel()
        brand_icon.setPixmap(
            QPixmap(str(icon_path)).scaled(
                52,
                52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        brand_copy = QVBoxLayout()
        brand = QLabel("御魂匠")
        brand.setObjectName("brand")
        tagline = QLabel("你的平安京工作台")
        tagline.setObjectName("muted")
        brand_copy.addWidget(brand)
        brand_copy.addWidget(tagline)
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_copy)
        brand_row.addStretch()
        nav_layout.addLayout(brand_row)
        nav_layout.addSpacing(24)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(demo)
        self.scheme_page = SchemePage(demo, demo_mode=demo_mode)
        self.inventory_page = InventoryPage(demo, demo_mode=demo_mode)
        self.upgrade_page = UpgradePage(demo)
        self.dailies_page = TaskCenterPage(repository)
        pages = [
            ("总览", self.dashboard),
            ("方案配装", self.scheme_page),
            ("御魂仓库", self.inventory_page),
            ("强化建议", self.upgrade_page),
            ("日常任务", self.dailies_page),
        ]
        self.nav_buttons = []
        for index, (label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, value=index: self._navigate(value))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        self.nav_buttons[0].setChecked(True)
        nav_layout.addStretch()
        risk = QLabel("仅使用画面识别与 ADB\n不注入 · 不付费 · 可急停")
        risk.setObjectName("muted")
        nav_layout.addWidget(risk)
        root_layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        header = QFrame()
        header.setStyleSheet("QFrame{background:#FAFBFD;border-bottom:1px solid #E3E5EA}")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 12, 22, 12)
        self.connection = QLabel("● 未连接 MuMu" if not demo_mode else "● 演示模式")
        self.connection.setStyleSheet("color:#8B7356")
        header_layout.addWidget(self.connection)
        privacy = QLabel("只读采集 · 本地存储")
        privacy.setObjectName("safePill")
        header_layout.addWidget(privacy)
        header_layout.addStretch()
        self.connect_button = QPushButton("连接 MuMu")
        self.connect_button.setEnabled(not demo_mode)
        self.connect_button.clicked.connect(self.connect_mumu)
        stop = QPushButton("F12 紧急停止")
        stop.setObjectName("danger")
        stop.clicked.connect(self.stop_task)
        header_layout.addWidget(self.connect_button)
        header_layout.addWidget(stop)
        content_layout.addWidget(header)
        content_layout.addWidget(self.stack, 1)

        log_frame = QFrame()
        log_frame.setStyleSheet("QFrame{background:#F5F5F7;border-top:1px solid #E3E5EA}")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(18, 8, 18, 10)
        self.log_toggle = QPushButton('运行记录  ›')
        self.log_toggle.setCheckable(True)
        self.log_toggle.setStyleSheet('text-align:left;border:none;color:#727681;font-weight:400;padding:2px')
        log_layout.addWidget(self.log_toggle)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setMaximumBlockCount(500)
        self.log.hide()
        self.log_toggle.toggled.connect(self.log.setVisible)
        self.log_toggle.toggled.connect(lambda opened: self.log_toggle.setText('运行记录  ﹀' if opened else '运行记录  ›'))
        log_layout.addWidget(self.log)
        content_layout.addWidget(log_frame)
        root_layout.addWidget(content, 1)

        QShortcut(QKeySequence("F12"), self, activated=self.stop_task)
        self.scheme_page.analyze_requested.connect(self.analyze_scheme)
        self.scheme_page.qr_requested.connect(self.import_qr)
        self.scheme_page.read_game_requested.connect(self.read_current_scheme)
        self.inventory_page.capture_requested.connect(self.capture_current_soul)
        self.inventory_page.delete_requested.connect(self.delete_soul_record)
        self.inventory_page.import_requested.connect(self.import_inventory)
        self.inventory_page.diagnostic_requested.connect(
            self.save_capture_diagnostic
        )
        self.inventory_page.open_diagnostics_requested.connect(
            self.open_diagnostics_directory
        )
        self.dailies_page.start_requested.connect(self.start_task)
        self.dashboard.navigate_requested.connect(self._navigate)
        for index in range(5):
            QShortcut(QKeySequence(f'Ctrl+{index + 1}'), self, activated=lambda value=index: self._navigate(value))
        if demo_mode:
            self.add_log("助手已启动；当前为演示库存，不会向 MuMu 发送输入。")
        elif demo.inventory:
            self.add_log(f"已加载 {len(demo.inventory)} 枚本地真实御魂记录。")
        else:
            self.add_log("真实仓库为空；请在游戏内手动打开御魂详情后使用只读采集。")

    def _navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def add_log(self, message: str) -> None:
        self.log.appendPlainText(message)
        if self.repository is not None:
            self.repository.add_audit("ui_log", {"message": message})

    def _task_running(self) -> bool:
        return bool(self.worker and self.worker.isRunning())

    def _set_task_active(self, active: bool) -> None:
        self.connect_button.setEnabled(not active and not self.demo_mode)
        self.scheme_page.set_live_enabled(not active)
        self.inventory_page.set_live_enabled(not active)
        self.dailies_page.set_task_active(active)

    def _require_game_foreground(self, action_name: str) -> bool:
        if self.runtime is None:
            QMessageBox.information(
                self, "尚未连接", f"请先连接 MuMu，再{action_name}。"
            )
            return False
        try:
            foreground_package = self.runtime.adb.current_package()
        except AdbError as exc:
            QMessageBox.warning(self, "连接异常", str(exc))
            self.add_log(f"无法确认 MuMu 前台应用：{exc}")
            return False
        if not foreground_package or "onmyoji" not in foreground_package.lower():
            message = f"MuMu 当前前台不是《阴阳师》，无法{action_name}。"
            QMessageBox.information(self, "游戏未在前台", message)
            self.add_log(message)
            return False
        return True

    def _adb_candidates(self) -> list[str]:
        candidates: list[str] = []
        if self.repository is not None:
            saved = self.repository.get_setting("adb_path")
            if saved and Path(saved).is_file():
                candidates.append(saved)
        candidates.extend(discover_adb())

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(Path(candidate)).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    def connect_mumu(self) -> None:
        if self.demo_mode:
            QMessageBox.information(self, "演示模式", "请用普通模式启动后再连接 MuMu。")
            return
        if self._task_running():
            QMessageBox.information(self, "任务运行中", "请先停止当前任务。")
            return
        candidates = self._adb_candidates()
        if not candidates:
            filename, _ = QFileDialog.getOpenFileName(
                self, "选择 MuMu 的 adb.exe", "", "adb.exe (adb.exe)"
            )
            if not filename:
                self.add_log("未找到 ADB；已取消连接。")
                return
            candidates = [filename]
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            probe = AdbClient(candidates[0])
            devices = probe.devices()
            if not devices:
                for endpoint in ("127.0.0.1:16384", "127.0.0.1:7555"):
                    try:
                        probe.connect(endpoint)
                    except AdbError:
                        continue
                devices = probe.devices()
            if not devices:
                raise AdbError("ADB 未发现在线设备；请在 MuMu 设置中开启调试并启动游戏。")
            preferred = next(
                (device for device in devices if device.startswith("127.0.0.1:")),
                devices[0],
            )
            adb = AdbClient(candidates[0], preferred)
            png = adb.screenshot()
            self.runtime = OcrMumuRuntime(adb, VisionService(RapidOcrEngine()))
            self.dashboard.set_screenshot(png)
            if self.repository is not None:
                self.repository.set_setting("adb_path", candidates[0])
            self.connection.setText(f"● 已连接 {preferred}")
            self.connection.setStyleSheet("color:#29805A")
            self.add_log(f"已连接 MuMu 设备 {preferred}，截图校验成功。")
        except Exception as exc:
            QMessageBox.warning(self, "连接失败", str(exc))
            self.add_log(f"连接失败：{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def analyze_scheme(self, value: str) -> None:
        try:
            code = normalize_scheme_code(value)
        except InvalidSchemeCode as exc:
            QMessageBox.warning(self, "方案码无效", str(exc))
            return
        QApplication.clipboard().setText(code)
        self.add_log("方案码校验通过并已复制。请在游戏阵容助手中导入、计算并打开方案详情。")
        self.scheme_page.result.setText("方案码已复制，等待读取游戏计算结果")

    def import_qr(self, path: Path) -> None:
        try:
            code = decode_qr_scheme(path)
        except InvalidSchemeCode as exc:
            QMessageBox.warning(self, "图片无效", str(exc))
            return
        self.scheme_page.code.setPlainText(code)
        self.analyze_scheme(code)
        self.add_log(f"已从 {path.name} 解码方案码。")

    def start_task(self, mode: str, rounds: int, minutes: int) -> None:
        if self.runtime is None:
            QMessageBox.information(self, "尚未连接", "请先连接 MuMu，并把游戏停在可识别的入口页面。")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "任务运行中", "请先停止当前任务。")
            return
        if not self.dailies_page.risk_ack.isChecked():
            QMessageBox.information(
                self,
                "需要风险确认",
                "自动刷图可能违反游戏规则。请先阅读并勾选风险确认。",
            )
            self.add_log("自动任务未启动：尚未确认账号风险。")
            return
        try:
            foreground_package = self.runtime.adb.current_package()
        except AdbError as exc:
            QMessageBox.warning(self, "连接异常", str(exc))
            self.add_log(f"无法确认 MuMu 前台应用：{exc}")
            return
        if not foreground_package or "onmyoji" not in foreground_package.lower():
            message = "MuMu 当前前台不是《阴阳师》；请先打开游戏并停在庭院或探索地图。"
            QMessageBox.information(self, "游戏未在前台", message)
            self.add_log(message)
            return
        try:
            task = get_task(mode)
            profile = self.dailies_page.current_profile() if task.profile else None
            if task.profile and self.dailies_page.selected_task.id != mode:
                raise ValueError('任务与识别配置不一致，请重新选择玩法。')
            if profile and '请填写' in ''.join(profile.title):
                raise ValueError('请先填写本期关卡标题，并导入截图预检。')
        except ValueError as exc:
            QMessageBox.information(self, '请检查任务配置', str(exc))
            return
        self.cancel_token = CancellationToken()
        limits = TaskLimits(max_rounds=rounds, max_duration_seconds=minutes * 60)
        self.worker = TaskWorker(self.runtime, mode, limits, self.cancel_token, profile)
        self.worker.progress.connect(self.dailies_page.update_progress)
        self.worker.completed.connect(self._task_completed)
        self.worker.failed.connect(self._task_failed)
        self.worker.finished.connect(lambda: self._set_task_active(False))
        self._set_task_active(True)
        try:
            self.worker.start()
        except Exception:
            self._set_task_active(False)
            raise
        label = task.title
        self.add_log(f"已启动{label}：最多 {rounds} 轮 / {minutes} 分钟。")

    def stop_task(self) -> None:
        self.cancel_token.cancel()
        self.add_log("已请求紧急停止；不会再发送新的点击。")

    def _task_completed(self, result) -> None:
        self._set_task_active(False)
        self.dailies_page.update_progress(result.final_state, result.rounds, result.elapsed_seconds)
        reasons = {StopReason.MAX_ROUNDS: '已达到轮数上限', StopReason.MAX_DURATION: '已达到时长上限',
                   StopReason.CANCELLED: '已停止', StopReason.UNRECOGNIZED_SCENE: '画面未识别，已停止',
                   StopReason.INSUFFICIENT_STAMINA: '体力不足，已停止', StopReason.ACTION_FAILED: '操作条件不满足',
                   StopReason.ADB_DISCONNECTED: '设备或识别异常', StopReason.NETWORK_ERROR: '连接异常',
                   StopReason.INVENTORY_FULL: '仓库已满', StopReason.COMPLETED: '已完成'}
        self.dailies_page.status.setText(f'{reasons.get(result.reason, result.reason.value)} · 完成 {result.rounds} 轮\n{result.message}')
        evidence_note = ""
        if (
            result.reason in (StopReason.UNRECOGNIZED_SCENE, StopReason.ACTION_FAILED, StopReason.ADB_DISCONNECTED)
            and self.runtime is not None
            and self.runtime.last_capture_png is not None
        ):
            evidence_path = self._write_capture_evidence(
                "automation-unknown",
                self.runtime.last_capture_png,
                tuple(self.runtime.last_boxes),
                error=(
                    f"stop={result.reason.value}; state={result.final_state}; "
                    f"rounds={result.rounds}"
                ),
            )
            if evidence_path is not None:
                evidence_note = f"；诊断：{evidence_path}"
        self.add_log(
            f"任务停止：{result.reason.value}，完成 {result.rounds} 轮，"
            f"最终场景 {result.final_state}{evidence_note}。{result.message}"
        )

    def _task_failed(self, message: str) -> None:
        self._set_task_active(False)
        self.dailies_page.status.setText(f'已停止 · {message}')
        evidence_note = ""
        if (
            self.runtime is not None
            and getattr(self.runtime, "last_capture_error", None)
            and getattr(self.runtime, "last_capture_png", None) is not None
        ):
            evidence_path = self._write_capture_evidence(
                "automation-error",
                self.runtime.last_capture_png,
                tuple(self.runtime.last_boxes),
                error=self.runtime.last_capture_error,
            )
            if evidence_path is not None:
                evidence_note = f"；诊断：{evidence_path}"
        self.add_log(f"任务异常：{message}{evidence_note}")

    def closeEvent(self, event) -> None:
        checking = self.dailies_page.check_worker
        if self._task_running() or (checking and checking.isRunning()):
            self.cancel_token.cancel()
            self.add_log('正在停止或完成识别，请稍后再次关闭窗口。')
            event.ignore()
            return
        event.accept()

    def refresh_state(self, state: DemoState) -> None:
        self.demo = state
        self.current_requirement = state.requirement
        self.dashboard.update_state(state)
        self.scheme_page.update_state(state, demo_mode=self.demo_mode)
        self.inventory_page.populate(state, demo_mode=self.demo_mode)
        self.upgrade_page.populate(state)

    @staticmethod
    def _convert_panel_thresholds(
        requirement: BuildRequirement, *, base_speed: int
    ) -> BuildRequirement:
        constrained = set(requirement.min_stats) | set(requirement.max_stats)
        unsupported = constrained - {Stat.SPEED}
        if unsupported:
            labels = "、".join(
                STAT_LABELS.get(stat, stat.value)
                for stat in sorted(unsupported, key=lambda item: item.value)
            )
            raise SchemeParseError(
                f"暂不支持把面板{labels}换算为御魂属性；本次方案不会应用"
            )
        if Stat.SPEED in constrained and base_speed <= 0:
            raise SchemeParseError("方案包含面板速度，请先填写目标式神的基础速度")
        base_values = {Stat.SPEED: float(base_speed)}

        def gear_values(values):
            return {
                stat: max(0.0, value - base_values.get(stat, 0.0))
                for stat, value in values.items()
            }

        return BuildRequirement(
            set_counts=requirement.set_counts,
            main_stats=requirement.main_stats,
            min_stats=gear_values(requirement.min_stats),
            max_stats=gear_values(requirement.max_stats),
            weights=requirement.weights,
            referenced_soul_ids=requirement.referenced_soul_ids,
        )

    @staticmethod
    def _requirement_summary(requirement: BuildRequirement) -> str:
        lines: list[str] = []
        if requirement.set_counts:
            lines.append(
                "套装："
                + "，".join(
                    f"{name} × {count}"
                    for name, count in requirement.set_counts.items()
                )
            )
        for slot, stats in sorted(requirement.main_stats.items()):
            labels = "/".join(STAT_LABELS.get(stat, stat.value) for stat in stats)
            lines.append(f"{slot}号位主属性：{labels}")
        for stat, value in requirement.min_stats.items():
            lines.append(f"御魂提供 {STAT_LABELS.get(stat, stat.value)} ≥ {value:g}")
        for stat, value in requirement.max_stats.items():
            lines.append(f"御魂提供 {STAT_LABELS.get(stat, stat.value)} ≤ {value:g}")
        return "\n".join(lines)

    def capture_current_soul(
        self, set_name_override: str, slot: int, rarity: int, record_id: str = ""
    ) -> None:
        if self.demo_mode:
            QMessageBox.information(
                self,
                "演示模式",
                "演示数据与真实仓库完全隔离；请用普通模式进行采集。",
            )
            return
        if self._task_running():
            QMessageBox.information(self, "任务运行中", "请先停止任务，再读取御魂。")
            return
        if self.repository is None:
            QMessageBox.warning(self, "无法保存", "本地数据库未初始化。")
            return
        if not self._require_game_foreground("读取御魂详情"):
            return
        cursor_active = True
        png: bytes | None = None
        boxes: tuple[OcrBox, ...] = ()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            png, boxes = self.runtime.capture_evidence()
            soul = SoulDetailParser().parse(
                boxes,
                slot=slot,
                rarity=rarity,
                set_name_override=set_name_override,
            )
            soul = replace(
                soul,
                id=record_id or f"local-{uuid4().hex}",
            )
            self.repository.save_souls([soul])
            state = create_state(
                self.repository.list_souls(), self.current_requirement
            )
            self.refresh_state(state)
            evidence_path = self._write_capture_evidence(
                "soul-detail", png, boxes
            )
            evidence_note = f"；证据：{evidence_path}" if evidence_path else ""
            self.add_log(
                f"只读{'更新' if record_id else '新增'}成功："
                f"{soul.set_name} {soul.slot}号位 +{soul.level}，"
                f"OCR 置信度 {soul.confidence:.1%}{evidence_note}。"
            )
        except CaptureError as exc:
            QApplication.restoreOverrideCursor()
            cursor_active = False
            evidence_path = self._write_capture_evidence(
                "soul-detail",
                exc.png,
                exc.boxes,
                error=f"{exc.stage}: {exc}",
            )
            location = f"；诊断：{evidence_path}" if evidence_path else ""
            QMessageBox.warning(self, "采集失败", f"{exc}{location}")
            self.add_log(f"只读采集异常：{exc}{location}")
        except SoulParseError as exc:
            QApplication.restoreOverrideCursor()
            cursor_active = False
            evidence_path = self._write_capture_evidence(
                "soul-detail", png, boxes, error=f"{exc.stage}: {exc}"
            )
            location = f"；诊断：{evidence_path}" if evidence_path else ""
            QMessageBox.warning(
                self, "无法识别御魂详情", f"{exc}{location}"
            )
            self.add_log(f"只读采集失败：{exc}{location}")
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            cursor_active = False
            evidence_path = self._write_capture_evidence(
                "soul-detail", png, boxes, error=str(exc)
            )
            location = f"；诊断：{evidence_path}" if evidence_path else ""
            QMessageBox.warning(self, "采集失败", f"{exc}{location}")
            self.add_log(f"只读采集异常：{exc}{location}")
        finally:
            if cursor_active:
                QApplication.restoreOverrideCursor()

    def _write_capture_evidence(
        self,
        purpose: str,
        png: bytes | None,
        boxes: tuple[OcrBox, ...],
        *,
        error: str | None = None,
    ) -> Path | None:
        if png is None:
            return None
        try:
            serial = (
                getattr(self.runtime.adb, "serial", None)
                if self.runtime is not None
                else None
            )
            return self.evidence_writer.write(
                purpose,
                png,
                boxes,
                {"serial": serial or "unknown"},
                error=error,
            )
        except OSError as exc:
            self.add_log(f"诊断证据保存失败：{exc}")
            return None

    def save_capture_diagnostic(self) -> None:
        if self.demo_mode:
            return
        if self.runtime is None:
            QMessageBox.information(self, "尚未连接", "请先连接 MuMu，再保存诊断采集。")
            return
        if self._task_running():
            QMessageBox.information(self, "任务运行中", "请先停止任务，再保存诊断采集。")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            png, boxes = self.runtime.capture_evidence()
            path = self._write_capture_evidence("manual-diagnostic", png, boxes)
            if path is None:
                raise OSError("诊断目录不可写")
            self.add_log(f"已保存只读诊断采集：{path}")
            QMessageBox.information(self, "诊断采集已保存", str(path))
        except CaptureError as exc:
            path = self._write_capture_evidence(
                "manual-diagnostic",
                exc.png,
                exc.boxes,
                error=f"{exc.stage}: {exc}",
            )
            location = f"；截图已保存：{path}" if path else ""
            QMessageBox.warning(self, "诊断采集失败", f"{exc}{location}")
            self.add_log(f"诊断采集失败：{exc}{location}")
        except Exception as exc:
            QMessageBox.warning(self, "诊断采集失败", str(exc))
            self.add_log(f"诊断采集失败：{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def open_diagnostics_directory(self) -> None:
        try:
            self.evidence_writer.root.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.evidence_writer.root.resolve()))
            )
            if not opened:
                raise OSError("系统没有可用的文件管理器")
        except OSError as exc:
            QMessageBox.warning(self, "无法打开诊断目录", str(exc))
            self.add_log(f"无法打开诊断目录：{exc}")

    def _confirm_inventory_import(self, preview: ImportPreview) -> bool:
        locked = sum(soul.locked for soul in preview.souls)
        discarded = sum(soul.marked_discard for soul in preview.souls)
        low_confidence = sum(soul.confidence < 0.92 for soul in preview.souls)
        warnings = "\n".join(preview.warnings[:3])
        warning_text = (
            f"\n\n已跳过 {len(preview.warnings)} 条：\n{warnings}"
            if preview.warnings
            else ""
        )
        answer = QMessageBox.question(
            self,
            "确认导入库存",
            f"格式：{preview.format_name}\n"
            f"有效御魂：{len(preview.souls)} 枚\n"
            f"已锁定：{locked} 枚\n"
            f"已标记弃置：{discarded} 枚"
            f"\n待复核（置信度低于 92%）：{low_confidence} 枚"
            f"{warning_text}\n\n"
            "这会替换助手本地库存，不会修改游戏。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def import_inventory(self, path: Path) -> None:
        if self.demo_mode or self.repository is None or self._task_running():
            return
        try:
            preview = load_inventory_file(Path(path))
            if not self._confirm_inventory_import(preview):
                self.add_log("已取消导入御魂库存。")
                return
            self.repository.replace_souls(preview.souls)
            self.refresh_state(
                create_state(
                    self.repository.list_souls(), self.current_requirement
                )
            )
            warning_note = (
                f"，跳过 {len(preview.warnings)} 条异常记录"
                if preview.warnings
                else ""
            )
            self.add_log(
                f"已从 {Path(path).name} 导入 {len(preview.souls)} 枚真实御魂"
                f"（{preview.format_name}）{warning_note}。"
            )
        except (OSError, sqlite3.DatabaseError, InventoryImportError) as exc:
            QMessageBox.warning(self, "库存导入失败", str(exc))
            self.add_log(f"库存导入失败：{exc}")

    def delete_soul_record(self, soul_id: str) -> None:
        if self.demo_mode or self.repository is None or self._task_running():
            return
        answer = QMessageBox.question(
            self,
            "删除本地记录",
            "只删除助手本地数据库中的这条记录，不会操作游戏。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repository.delete_soul(soul_id)
        self.refresh_state(
            create_state(self.repository.list_souls(), self.current_requirement)
        )
        self.add_log("已删除一条本地御魂记录；未向游戏发送任何操作。")

    def read_current_scheme(self, base_speed: int = 0) -> None:
        if self.demo_mode:
            QMessageBox.information(
                self,
                "演示模式",
                "演示数据与真实方案完全隔离；请用普通模式读取游戏方案。",
            )
            return
        if self._task_running():
            QMessageBox.information(self, "任务运行中", "请先停止任务，再读取方案。")
            return
        if not self._require_game_foreground("读取方案详情"):
            return
        cursor_active = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            boxes = self.runtime.capture_boxes()
            requirement = SchemeRequirementParser().parse(
                boxes,
                weights=DEFAULT_PROFILES["output"],
            )
            requirement = self._convert_panel_thresholds(
                requirement, base_speed=base_speed
            )
            summary = self._requirement_summary(requirement)
            QApplication.restoreOverrideCursor()
            cursor_active = False
            answer = QMessageBox.question(
                self,
                "确认识别结果",
                f"即将应用以下御魂约束：\n\n{summary}\n\n确认无误后继续。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.add_log("已取消应用本次方案识别结果。")
                return
            inventory = self.repository.list_souls() if self.repository else ()
            self.refresh_state(create_state(inventory, requirement))
            self.add_log(
                "已从当前游戏画面读取方案约束，并用本地真实库存重新计算。"
            )
        except SchemeParseError as exc:
            if cursor_active:
                QApplication.restoreOverrideCursor()
                cursor_active = False
            QMessageBox.warning(self, "无法识别方案", str(exc))
            self.add_log(f"方案读取失败：{exc}")
        except Exception as exc:
            if cursor_active:
                QApplication.restoreOverrideCursor()
                cursor_active = False
            QMessageBox.warning(self, "读取失败", str(exc))
            self.add_log(f"方案读取异常：{exc}")
        finally:
            if cursor_active:
                QApplication.restoreOverrideCursor()
