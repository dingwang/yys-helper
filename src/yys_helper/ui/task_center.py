"""Task selection and offline screenshot calibration. Never sends device input."""
from pathlib import Path
import sqlite3
import time

from PIL import Image
from PySide6.QtCore import QThread, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QLineEdit,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QFormLayout, QProgressBar, QFileDialog, QScrollArea, QMessageBox,
)

from yys_helper.automation.catalog import TASKS, TaskProfile
from yys_helper.application.runtime import classify_scene, classify_task_scene
from yys_helper.infrastructure.vision import VisionService, RapidOcrEngine

SCENE_NAMES = {'starting': '识别预检', 'ready': '等待挑战', 'prepare': '队伍准备',
               'battle': '战斗中', 'settlement': '领取结算', 'repeat': '等待再次挑战',
               'home': '庭院', 'chapter_select': '章节选择', 'explore_map': '探索地图',
               'soul_ready': '御魂挑战页', 'stamina_empty': '体力不足',
               'resource_empty': '次数或材料不足', 'purchase': '购买弹窗',
               'defeat': '战斗失败', 'network_error': '连接异常', 'login': '登录页',
               'inventory_full': '仓库已满'}


def panel():
    widget = QFrame()
    widget.setObjectName('card')
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return widget, layout


class ScreenshotCheck(QThread):
    result = Signal(str)

    def __init__(self, filename, profile, parent=None):
        super().__init__(parent)
        self.filename, self.profile = filename, profile

    def run(self):
        try:
            with Image.open(self.filename) as image:
                boxes = VisionService(RapidOcrEngine()).read(image.convert('RGB'))
            scene = classify_task_scene(boxes, self.profile) if self.profile else classify_scene(boxes)
            text = ' / '.join(box.text for box in boxes if box.confidence >= .92)
            self.result.emit(f'截图识别：{SCENE_NAMES.get(scene, "未匹配，请调整关键词")}\n文字：{text[:500] or "没有高置信度文字"}')
        except Exception as exc:
            self.result.emit(f'截图预检失败：{exc}')


class TaskCenterPage(QWidget):
    start_requested = Signal(str, int, int)
    stop_requested = Signal()
    finish_requested = Signal()

    def __init__(self, repository=None, *, demo_mode=False):
        super().__init__()
        self.repository = repository
        self.demo_mode = demo_mode
        self._connected = False
        self._started_at = None
        self._check_text = ''
        self._task_active = False
        self.check_worker = None
        self._profiles = {}
        self.selected_task = TASKS[0]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(14)
        title = QLabel('任务中心')
        title.setObjectName('title')
        subtitle = QLabel('01 选择玩法    →    02 设置节奏与上限    →    03 识别后运行')
        subtitle.setObjectName('muted')
        outer.addWidget(title)
        outer.addWidget(subtitle)
        body = QHBoxLayout()
        body.setSpacing(18)
        outer.addLayout(body, 1)
        library, left = panel()
        library.setFixedWidth(220)
        left.addWidget(QLabel('玩法资料库'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索玩法…')
        self.category = QComboBox()
        self.category.addItems(['全部玩法', '日常', '材料', '活动'])
        self.task_list = QListWidget()
        self.task_list.setObjectName('taskList')
        self.task_list.setSpacing(3)
        left.addWidget(self.search)
        left.addWidget(self.category)
        left.addWidget(self.task_list, 1)
        note = QLabel('新增玩法为识别预设\n需先验证你的游戏画面')
        note.setObjectName('muted')
        left.addWidget(note)
        body.addWidget(library)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail = QWidget()
        right = QVBoxLayout(detail)
        right.setContentsMargins(0, 0, 2, 0)
        right.setSpacing(14)
        scroll.setWidget(detail)
        right_shell = QVBoxLayout()
        right_shell.setSpacing(14)
        right_shell.addWidget(scroll, 1)
        body.addLayout(right_shell, 1)
        overview, overview_layout = panel()
        self.task_title = QLabel()
        self.task_title.setObjectName('sectionTitle')
        self.description = QLabel()
        self.description.setObjectName('muted')
        self.description.setWordWrap(True)
        overview_layout.addWidget(self.task_title)
        overview_layout.addWidget(self.description)
        self.settings = QWidget()
        self.settings.setObjectName('transparent')
        controls = QHBoxLayout(self.settings)
        controls.setContentsMargins(0, 4, 0, 0)
        self.rounds = QSpinBox()
        self.rounds.setRange(1, 500)
        self.rounds.setValue(self._saved_number('task_rounds', 30, 500))
        self.rounds.setSuffix(' 轮')
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 120)
        self.minutes.setValue(self._saved_number('task_minutes', 45, 120))
        self.minutes.setSuffix(' 分钟')
        controls.addWidget(QLabel('最多'))
        controls.addWidget(self.rounds)
        controls.addWidget(QLabel('最长'))
        controls.addWidget(self.minutes)
        controls.addStretch()
        overview_layout.addWidget(self.settings)
        self.pace_mode = QComboBox()
        self.pace_mode.addItem('标准节奏 · 每 8–12 轮休息 20–45 秒', 'standard')
        self.pace_mode.addItem('舒缓节奏 · 每 5–8 轮休息 30–60 秒', 'relaxed')
        saved_pace = self.repository.get_setting('task_pace', 'standard') if self.repository else 'standard'
        self.pace_mode.setCurrentIndex(max(0, self.pace_mode.findData(saved_pace)))
        overview_layout.addWidget(self.pace_mode)
        self.session_hint = QLabel()
        self.session_hint.setObjectName('muted')
        self.session_hint.setWordWrap(True)
        overview_layout.addWidget(self.session_hint)
        right.addWidget(overview)

        self.config_panel, config = panel()
        config.addWidget(QLabel('关卡识别'))
        tip = QLabel('填写画面中的原文，多个词用 / 分隔。标题可包含匹配，按钮需完整匹配。')
        tip.setObjectName('muted')
        tip.setWordWrap(True)
        config.addWidget(tip)
        title_form = QFormLayout()
        config.addLayout(title_form)
        self.advanced_toggle = QPushButton('高级识别设置  ›')
        self.advanced_toggle.setCheckable(True)
        config.addWidget(self.advanced_toggle)
        self.advanced = QWidget()
        self.advanced.setObjectName('transparent')
        form = QFormLayout(self.advanced)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.fields = {}
        for key, label in [('title', '关卡标题'), ('start', '挑战按钮'), ('prepare', '准备按钮'),
                           ('settlement', '结算标识'), ('confirm', '继续按钮'), ('repeat', '再战按钮')]:
            edit = QLineEdit()
            edit.setMaxLength(480)
            self.fields[key] = edit
            (title_form if key == 'title' else form).addRow(label, edit)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        self.advanced_toggle.toggled.connect(lambda opened: self.advanced_toggle.setText('高级识别设置  ﹀' if opened else '高级识别设置  ›'))
        config.addWidget(self.advanced)
        buttons = QHBoxLayout()
        self.save_button = QPushButton('保存配置')
        self.reset_button = QPushButton('恢复预设')
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch()
        config.addLayout(buttons)
        right.addWidget(self.config_panel)
        run_panel, run = panel()
        self.readiness = QLabel()
        self.readiness.setObjectName('statusPill')
        self.readiness.setWordWrap(True)
        self.preflight = QPushButton('导入截图预检')
        self.preflight.setToolTip('仅读取本地截图，不连接 MuMu、不发送点击。')
        check_row = QHBoxLayout()
        check_row.addWidget(self.preflight)
        self.check_details = QPushButton('识别详情')
        self.check_details.setEnabled(False)
        self.check_details.clicked.connect(lambda: QMessageBox.information(self, '本地截图识别', self._check_text))
        check_row.addWidget(self.check_details)
        run.addLayout(check_row)
        self.check_result = QLabel('启动时会再次预检。新增玩法需从所选关卡的挑战页开始。')
        self.check_result.setObjectName('muted')
        self.check_result.setWordWrap(True)
        self.check_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        run.addWidget(self.check_result)
        self.risk_ack = QCheckBox('我理解自动操作可能带来账号处罚风险')
        self.risk_ack.setObjectName('riskCheck')
        run.addWidget(self.risk_ack)
        right.addWidget(run_panel)
        control_panel, run = panel()
        run.setContentsMargins(16, 12, 16, 12)
        run.setSpacing(8)
        run.addWidget(self.readiness)
        self.start_button = QPushButton('开始循环')
        self.start_button.setObjectName('primary')
        self.start_button.setMinimumHeight(42)
        self.start_button.setEnabled(False)
        self.task_buttons = [self.start_button]
        stop_row = QHBoxLayout()
        self.finish_button = QPushButton('本轮后停止')
        self.finish_button.setToolTip('等待当前战斗结束，不再开始下一轮。时长上限始终优先。')
        self.stop_button = QPushButton('立即停止')
        self.stop_button.setObjectName('danger')
        self.finish_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.finish_button.clicked.connect(self.finish_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        stop_row.addWidget(self.start_button, 1)
        stop_row.addWidget(self.finish_button)
        stop_row.addWidget(self.stop_button)
        run.addLayout(stop_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, self.rounds.value())
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        run.addWidget(self.progress)
        self.status = QLabel('准备就绪 · 尚未启动')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        run.addWidget(self.status)
        self.activity_label = QLabel('不自动续跑 · 等待与休息均计入总时长')
        self.activity_label.setObjectName('muted')
        run.addWidget(self.activity_label)
        self.countdown = QLabel()
        self.countdown.setObjectName('muted')
        self.countdown.hide()
        run.addWidget(self.countdown)
        right_shell.addWidget(control_panel)
        right.addStretch()
        self.search.textChanged.connect(self._filter)
        self.category.currentTextChanged.connect(self._filter)
        self.task_list.currentRowChanged.connect(self._select)
        self.risk_ack.toggled.connect(self._update_enabled)
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button.clicked.connect(self._reset)
        self.start_button.clicked.connect(self._start)
        self.preflight.clicked.connect(self._check_screenshot)
        self.minutes.valueChanged.connect(self._session_summary)
        self.rounds.valueChanged.connect(self._session_summary)
        for edit in self.fields.values():
            edit.textChanged.connect(self._update_enabled)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self._session_summary()
        self._filter()

    def _session_summary(self, *_):
        self.session_hint.setText(f'先到即停：{self.rounds.value()} 轮 / {self.minutes.value()} 分钟。随机节奏不代表防封。')

    def set_connected(self, connected):
        self._connected = connected
        self._update_enabled()

    def _tick(self):
        if self._started_at is not None:
            remaining = max(0, self.minutes.value() * 60 - int(time.monotonic() - self._started_at))
            self.countdown.setText(f'会话剩余上限  {remaining // 60:02d}:{remaining % 60:02d}  · 到时停止发送新操作')

    def update_activity(self, kind, seconds):
        names = {'resting': '阶段休息', 'thinking': '操作间隔', 'waiting': '等待画面'}
        self.activity_label.setText(f'{names.get(kind, kind)} · {max(0, seconds):.0f} 秒')

    def _saved_number(self, key, fallback, upper):
        try:
            return max(1, min(upper, int(self.repository.get_setting(key)))) if self.repository else fallback
        except (ValueError, TypeError):
            return fallback

    def _remember_editor(self):
        if self.selected_task.profile:
            try:
                self._profiles[self.selected_task.id] = self.current_profile()
            except ValueError:
                pass

    def _filter(self, *_):
        self._remember_editor()
        self.task_list.blockSignals(True)
        self.task_list.clear()
        for task in TASKS:
            if self.search.text().strip() not in task.title:
                continue
            if self.category.currentIndex() and self.category.currentText() != task.category:
                continue
            item = QListWidgetItem(task.title + '\n' + task.category)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.task_list.addItem(item)
        self.task_list.blockSignals(False)
        if self.task_list.count():
            self.task_list.setCurrentRow(0)
        else:
            self.description.setText('没有匹配的玩法，请换个关键词。')
            self._update_enabled()

    def _select(self, row):
        item = self.task_list.item(row)
        if item is None:
            return
        self._remember_editor()
        self.selected_task = item.data(Qt.ItemDataRole.UserRole)
        task = self.selected_task
        self.task_title.setText(task.title)
        self.description.setText(task.description)
        self.config_panel.setVisible(task.profile is not None)
        profile = self._profiles.get(task.id, task.profile)
        if task.id not in self._profiles and task.profile and self.repository:
            value = self.repository.get_setting('task_profile_' + task.id)
            if value:
                try:
                    profile = TaskProfile.from_json(value)
                except ValueError:
                    self.check_result.setText('已保存的识别配置无效，已恢复预设。')
        if profile:
            for key, field in self.fields.items():
                field.setText(' / '.join(getattr(profile, key)))
        self._update_enabled()

    def current_profile(self):
        if not self.selected_task.profile:
            return None
        return TaskProfile(**{key: tuple(v.strip() for v in edit.text().split('/') if v.strip())
                              for key, edit in self.fields.items()})

    def save_settings(self):
        try:
            profile = self.current_profile()
            settings = {'task_rounds': str(self.rounds.value()), 'task_minutes': str(self.minutes.value()),
                        'task_pace': self.pace_mode.currentData()}
            if profile:
                settings['task_profile_' + self.selected_task.id] = profile.to_json()
            if self.repository:
                self.repository.set_settings(settings)
            if profile:
                self._profiles[self.selected_task.id] = profile
            self.check_result.setText('设置已保存到本地。可导入挑战页截图检查识别结果。')
            return True
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            self.check_result.setText(str(exc))
            return False

    def _reset(self):
        if self.selected_task.profile:
            for key, field in self.fields.items():
                field.setText(' / '.join(getattr(self.selected_task.profile, key)))
            self.save_settings()

    def _update_enabled(self, *_):
        checking = self.check_worker and self.check_worker.isRunning()
        problem = ''
        try:
            profile = self.current_profile()
            if profile and '请填写' in ''.join(profile.title):
                problem = '请填写本期具体关卡标题'
        except ValueError as exc:
            problem = str(exc)
        ready = self._connected and not self.demo_mode and not problem and self.task_list.count() > 0
        self.start_button.setEnabled(bool(ready and self.risk_ack.isChecked() and not self._task_active and not checking))
        if self._task_active:
            hint = '运行中 · 设置已锁定'
        elif self.demo_mode:
            hint = '演示模式 · 不会向游戏发送操作'
        elif not self.task_list.count():
            hint = '没有匹配玩法 · 请修改搜索条件'
        elif problem:
            hint = problem
        elif not self._connected:
            hint = '未连接 MuMu · 可先配置和预检截图'
        elif checking:
            hint = '正在预检本地截图…'
        elif not self.risk_ack.isChecked():
            hint = '已连接 · 请确认游戏前台与账号风险'
        else:
            hint = '可以开始 · 首次运行建议先测试 1–3 轮'
        self.readiness.setText(hint)

    def set_task_active(self, active):
        self._task_active = active
        for widget in (self.settings, self.task_list, self.search, self.category,
                       self.config_panel, self.risk_ack, self.preflight):
            widget.setEnabled(not active)
        self.pace_mode.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.finish_button.setEnabled(active)
        self.start_button.setText('运行中…' if active else '开始循环')
        self.countdown.setVisible(active)
        self._update_enabled()
        if active:
            self._started_at = time.monotonic()
            self.timer.start()
            self._tick()
            self.progress.setRange(0, self.rounds.value())
            self.progress.setValue(0)
            self.status.setText('识别预检中 · 未发送点击')
        else:
            self.timer.stop()
            self._started_at = None
            self.countdown.clear()
            self.activity_label.setText('已停止 · 不会自动续跑')

    def _start(self):
        if not self.start_button.isEnabled():
            return
        if self.save_settings():
            self.start_requested.emit(self.selected_task.id, self.rounds.value(), self.minutes.value())

    def update_progress(self, scene, rounds, elapsed):
        self.progress.setValue(rounds)
        self.status.setText(f'{SCENE_NAMES.get(scene, scene)} · 已完成 {rounds} / {self.rounds.value()} 轮 · {int(elapsed)//60:02d}:{int(elapsed)%60:02d}')

    def _check_screenshot(self):
        if self.check_worker and self.check_worker.isRunning():
            return
        try:
            profile = self.current_profile()
        except ValueError as exc:
            self.check_result.setText(str(exc))
            return
        filename, _ = QFileDialog.getOpenFileName(self, '选择游戏截图（不操作游戏）', '', '图片 (*.png *.jpg *.jpeg)')
        if not filename:
            return
        self.preflight.setEnabled(False)
        self.start_button.setEnabled(False)
        self.check_result.setText('正在识别本地截图…')
        self.check_worker = ScreenshotCheck(Path(filename), profile, self)
        for widget in (self.task_list, self.search, self.category, self.config_panel):
            widget.setEnabled(False)
        self.check_worker.result.connect(self._show_check_result)
        self.check_worker.finished.connect(self._check_finished)
        self.check_worker.start()
        self._update_enabled()

    def _show_check_result(self, result):
        self._check_text = result
        self.check_result.setText(result.split('\n')[0])
        self.check_details.setEnabled(True)

    def _check_finished(self):
        for widget in (self.task_list, self.search, self.category, self.config_panel):
            widget.setEnabled(not self._task_active)
        self.preflight.setEnabled(not self._task_active)
        self._update_enabled()
