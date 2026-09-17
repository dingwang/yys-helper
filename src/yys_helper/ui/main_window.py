from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

from yys_helper.application.runtime import OcrMumuRuntime
from yys_helper.application.schemes import (
    InvalidSchemeCode,
    decode_qr_scheme,
    normalize_scheme_code,
)
from yys_helper.automation.engine import AutomationEngine, CancellationToken
from yys_helper.automation.workflows import chapter_28_workflow, soul_dungeon_workflow
from yys_helper.demo import DemoState
from yys_helper.domain.models import Stat, TaskLimits
from yys_helper.domain.safety import protection_reasons
from yys_helper.domain.scoring import DEFAULT_PROFILES, score_soul
from yys_helper.infrastructure.adb import AdbClient, AdbError, discover_adb
from yys_helper.infrastructure.repository import AppRepository
from yys_helper.infrastructure.vision import RapidOcrEngine, VisionService


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
    def __init__(self, demo: DemoState) -> None:
        super().__init__()
        page, layout = page_title("运行总览", "连接 MuMu 后可预览画面并启动安全自动化。")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        metrics = QHBoxLayout()
        for label, value in (
            ("已扫描御魂", str(len(demo.inventory))),
            ("当前缺口", str(len(demo.closest_build.shortfalls))),
            ("强化候选", str(len(demo.upgrade_candidates))),
        ):
            frame, inner = card()
            number = QLabel(value)
            number.setObjectName("metric")
            inner.addWidget(number)
            name = QLabel(label)
            name.setObjectName("muted")
            inner.addWidget(name)
            metrics.addWidget(frame)
        layout.addLayout(metrics)

        preview_card, preview_layout = card()
        caption = QLabel("MuMu 实时画面")
        caption.setStyleSheet("font-weight: 700; font-size: 15px")
        self.preview = QLabel("尚未连接模拟器\n\n点击右上角“连接 MuMu”开始")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(360)
        self.preview.setStyleSheet(
            "background:#080D19;border:1px dashed #3B4D75;border-radius:10px;color:#7887A6"
        )
        preview_layout.addWidget(caption)
        preview_layout.addWidget(self.preview, 1)
        layout.addWidget(preview_card, 1)

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

    def __init__(self, demo: DemoState) -> None:
        super().__init__()
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
        analyze = QPushButton("验证并分析")
        analyze.setObjectName("primary")
        analyze.clicked.connect(lambda: self.analyze_requested.emit(self.code.toPlainText()))
        qr = QPushButton("选择二维码图片")
        qr.clicked.connect(self._choose_qr)
        row.addWidget(analyze)
        row.addWidget(qr)
        row.addStretch()
        inner.addLayout(row)
        layout.addWidget(input_card)

        result_card, result_layout = card()
        result_layout.addWidget(QLabel("当前库存模拟结果"))
        status = "满足全部条件" if demo.closest_build.satisfied else "现有御魂未完全达标"
        self.result = QLabel(status)
        self.result.setStyleSheet("font-size:18px;font-weight:700;color:#F6C453")
        result_layout.addWidget(self.result)
        details = []
        for stat, gap in demo.closest_build.shortfalls.items():
            details.append(f"{STAT_LABELS.get(stat, stat.value)} 还差 {gap:g}")
        result_layout.addWidget(QLabel("；".join(details) or "可直接应用六件套"))
        layout.addWidget(result_card)
        layout.addStretch()

    def _choose_qr(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择方案码图片", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if filename:
            self.qr_requested.emit(Path(filename))


class InventoryPage(QWidget):
    def __init__(self, demo: DemoState) -> None:
        super().__init__()
        page, layout = page_title(
            "御魂仓库", "按输出模板评分；受保护的御魂永远不会自动弃置或作为材料。"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["套装", "位置", "星级", "等级", "主属性", "速度", "输出分", "保护状态"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.populate(demo)
        layout.addWidget(self.table, 1)

    def populate(self, demo: DemoState) -> None:
        self.table.setRowCount(len(demo.inventory))
        for row, soul in enumerate(demo.inventory):
            reasons = protection_reasons(soul, demo.requirement.referenced_soul_ids)
            values = (
                soul.set_name,
                str(soul.slot),
                f"{soul.rarity}星",
                f"+{soul.level}",
                STAT_LABELS.get(soul.main_stat, soul.main_stat.value),
                f"{soul.stat_value(Stat.SPEED):g}",
                f"{score_soul(soul, DEFAULT_PROFILES['output']):.1f}",
                "已保护" if reasons else "可评估",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))


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

        table = QTableWidget(len(demo.upgrade_candidates), 6)
        table.setHorizontalHeaderLabels(["优先级", "套装/位置", "当前", "下一检查点", "预计金币", "命中目标"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        for row, candidate in enumerate(demo.upgrade_candidates):
            values = (
                str(row + 1),
                f"{candidate.soul.set_name} · {candidate.soul.slot}号位",
                f"+{candidate.soul.level}",
                f"+{candidate.next_level}",
                f"{candidate.estimated_coins:,}",
                " / ".join(candidate.reasons),
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(table, 1)


class DailiesPage(QWidget):
    start_requested = Signal(str, int, int)

    def __init__(self) -> None:
        super().__init__()
        page, layout = page_title(
            "日常任务", "达到次数/时长上限、体力不足或三次识别失败时自动停止。"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        settings, settings_layout = card()
        row = QHBoxLayout()
        row.addWidget(QLabel("最大循环"))
        self.rounds = QSpinBox()
        self.rounds.setRange(1, 500)
        self.rounds.setValue(30)
        row.addWidget(self.rounds)
        row.addWidget(QLabel("最长分钟"))
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 720)
        self.minutes.setValue(60)
        row.addWidget(self.minutes)
        row.addStretch()
        settings_layout.addLayout(row)
        layout.addWidget(settings)

        choices = QHBoxLayout()
        for task_id, title, description in (
            ("chapter28", "困 28 经验", "循环选怪、战斗、结算；首版不自动更换狗粮。"),
            ("soul", "御魂副本", "循环挑战与结算，保留阵容，不触发付费补充体力。"),
        ):
            task_card, inner = card()
            name = QLabel(title)
            name.setStyleSheet("font-size:18px;font-weight:700")
            copy = QLabel(description)
            copy.setObjectName("muted")
            copy.setWordWrap(True)
            button = QPushButton("启动任务")
            button.setObjectName("primary")
            button.clicked.connect(
                lambda _checked=False, value=task_id: self.start_requested.emit(
                    value, self.rounds.value(), self.minutes.value()
                )
            )
            inner.addWidget(name)
            inner.addWidget(copy)
            inner.addStretch()
            inner.addWidget(button)
            choices.addWidget(task_card)
        layout.addLayout(choices)
        layout.addStretch()


class TaskWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, runtime: OcrMumuRuntime, mode: str, limits: TaskLimits, token: CancellationToken):
        super().__init__()
        self.runtime = runtime
        self.mode = mode
        self.limits = limits
        self.token = token

    def run(self) -> None:
        try:
            workflow = chapter_28_workflow() if self.mode == "chapter28" else soul_dungeon_workflow()
            result = AutomationEngine(self.runtime, self.runtime).run(workflow, self.limits, self.token)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


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
        self.demo_mode = demo_mode
        self.repository = repository
        self.runtime: OcrMumuRuntime | None = None
        self.worker: TaskWorker | None = None
        self.cancel_token = CancellationToken()
        self.setWindowTitle("御魂匠 · 阴阳师助手")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 680)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("御魂匠")
        brand.setObjectName("brand")
        nav_layout.addWidget(brand)
        tagline = QLabel("YYS HELPER · LOCAL")
        tagline.setObjectName("muted")
        nav_layout.addWidget(tagline)
        nav_layout.addSpacing(24)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(demo)
        self.scheme_page = SchemePage(demo)
        self.inventory_page = InventoryPage(demo)
        self.upgrade_page = UpgradePage(demo)
        self.dailies_page = DailiesPage()
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
        header.setStyleSheet("background:#0E1526;border-bottom:1px solid #24304A")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 12, 22, 12)
        self.connection = QLabel("● 未连接 MuMu" if not demo_mode else "● 演示模式")
        self.connection.setStyleSheet("color:#F0A95A")
        header_layout.addWidget(self.connection)
        header_layout.addStretch()
        connect = QPushButton("连接 MuMu")
        connect.clicked.connect(self.connect_mumu)
        stop = QPushButton("F12 紧急停止")
        stop.setObjectName("danger")
        stop.clicked.connect(self.stop_task)
        header_layout.addWidget(connect)
        header_layout.addWidget(stop)
        content_layout.addWidget(header)
        content_layout.addWidget(self.stack, 1)

        log_frame = QFrame()
        log_frame.setStyleSheet("background:#0A0F1C;border-top:1px solid #24304A")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(18, 8, 18, 10)
        log_layout.addWidget(QLabel("运行日志"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        log_layout.addWidget(self.log)
        content_layout.addWidget(log_frame)
        root_layout.addWidget(content, 1)

        QShortcut(QKeySequence("F12"), self, activated=self.stop_task)
        self.scheme_page.analyze_requested.connect(self.analyze_scheme)
        self.scheme_page.qr_requested.connect(self.import_qr)
        self.dailies_page.start_requested.connect(self.start_task)
        self.add_log("助手已启动；当前为演示库存。连接 MuMu 后才会发送输入。")

    def _navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def add_log(self, message: str) -> None:
        self.log.appendPlainText(message)
        if self.repository is not None:
            self.repository.add_audit("ui_log", {"message": message})

    def connect_mumu(self) -> None:
        candidates = discover_adb()
        if not candidates:
            filename, _ = QFileDialog.getOpenFileName(self, "选择 MuMu 的 adb.exe", "", "adb.exe (adb.exe)")
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
            self.connection.setText(f"● 已连接 {preferred}")
            self.connection.setStyleSheet("color:#65D6A0")
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
        self.add_log("方案码校验通过并已复制；当前演示库存已完成最近似六件套求解。")
        self.scheme_page.result.setText(
            "现有御魂可直接达标" if self.demo.closest_build.satisfied else "未完全达标，已生成分段强化候选"
        )

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
        self.cancel_token = CancellationToken()
        limits = TaskLimits(max_rounds=rounds, max_duration_seconds=minutes * 60)
        self.worker = TaskWorker(self.runtime, mode, limits, self.cancel_token)
        self.worker.completed.connect(self._task_completed)
        self.worker.failed.connect(lambda message: self.add_log(f"任务异常：{message}"))
        self.worker.start()
        label = "困28" if mode == "chapter28" else "御魂副本"
        self.add_log(f"已启动{label}：最多 {rounds} 轮 / {minutes} 分钟。")

    def stop_task(self) -> None:
        self.cancel_token.cancel()
        self.add_log("已请求紧急停止；不会再发送新的点击。")

    def _task_completed(self, result) -> None:
        self.add_log(f"任务停止：{result.reason.value}，完成 {result.rounds} 轮，最终场景 {result.final_state}。")
