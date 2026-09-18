"""Task selection and offline screenshot calibration. Never sends device input."""
from pathlib import Path
import sqlite3

from PIL import Image
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QLineEdit,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QFormLayout, QProgressBar, QFileDialog, QScrollArea,
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

    def __init__(self, repository=None):
        super().__init__()
        self.repository = repository
        self._task_active = False
        self.check_worker = None
        self._profiles = {}
        self.selected_task = TASKS[0]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(14)
        title = QLabel('让重复的事，自动完成。')
        title.setObjectName('title')
        subtitle = QLabel('任务中心  /  选择玩法，确认识别，再开始循环')
        subtitle.setObjectName('muted')
        outer.addWidget(title)
        outer.addWidget(subtitle)
        body = QHBoxLayout()
        body.setSpacing(18)
        outer.addLayout(body, 1)
        library, left = panel()
        library.setFixedWidth(244)
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
        self.minutes.setRange(1, 720)
        self.minutes.setValue(self._saved_number('task_minutes', 60, 720))
        self.minutes.setSuffix(' 分钟')
        controls.addWidget(QLabel('最多'))
        controls.addWidget(self.rounds)
        controls.addWidget(QLabel('最长'))
        controls.addWidget(self.minutes)
        controls.addStretch()
        overview_layout.addWidget(self.settings)
        right.addWidget(overview)

        self.config_panel, config = panel()
        config.addWidget(QLabel('识别配置'))
        tip = QLabel('填写画面中的原文，多个词用 / 分隔。标题可包含匹配，按钮需完整匹配。')
        tip.setObjectName('muted')
        tip.setWordWrap(True)
        config.addWidget(tip)
        form = QFormLayout()
        form.setSpacing(8)
        self.fields = {}
        for key, label in [('title', '关卡标题'), ('start', '挑战按钮'), ('prepare', '准备按钮'),
                           ('settlement', '结算标识'), ('confirm', '继续按钮'), ('repeat', '再战按钮')]:
            edit = QLineEdit()
            edit.setMaxLength(480)
            self.fields[key] = edit
            form.addRow(label, edit)
        config.addLayout(form)
        buttons = QHBoxLayout()
        self.save_button = QPushButton('保存配置')
        self.reset_button = QPushButton('恢复预设')
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch()
        config.addLayout(buttons)
        right.addWidget(self.config_panel)
        run_panel, run = panel()
        self.preflight = QPushButton('导入截图预检')
        self.preflight.setToolTip('仅读取本地截图，不连接 MuMu、不发送点击。')
        run.addWidget(self.preflight)
        self.check_result = QLabel('启动时会再次预检。新增玩法需从所选关卡的挑战页开始。')
        self.check_result.setObjectName('muted')
        self.check_result.setWordWrap(True)
        self.check_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        run.addWidget(self.check_result)
        self.risk_ack = QCheckBox('我理解自动操作可能带来账号处罚风险')
        self.risk_ack.setObjectName('riskCheck')
        run.addWidget(self.risk_ack)
        self.start_button = QPushButton('开始循环')
        self.start_button.setObjectName('primary')
        self.start_button.setMinimumHeight(42)
        self.start_button.setEnabled(False)
        self.task_buttons = [self.start_button]
        run.addWidget(self.start_button)
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
        right_shell.addWidget(run_panel)
        right.addStretch()
        self.search.textChanged.connect(self._filter)
        self.category.currentTextChanged.connect(self._filter)
        self.task_list.currentRowChanged.connect(self._select)
        self.risk_ack.toggled.connect(self._update_enabled)
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button.clicked.connect(self._reset)
        self.start_button.clicked.connect(self._start)
        self.preflight.clicked.connect(self._check_screenshot)
        self._filter()

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
            settings = {'task_rounds': str(self.rounds.value()), 'task_minutes': str(self.minutes.value())}
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
        self.start_button.setEnabled(self.risk_ack.isChecked() and not self._task_active and not checking and self.task_list.count() > 0)

    def set_task_active(self, active):
        self._task_active = active
        for widget in (self.settings, self.task_list, self.search, self.category,
                       self.config_panel, self.risk_ack, self.preflight):
            widget.setEnabled(not active)
        self._update_enabled()
        if active:
            self.progress.setRange(0, self.rounds.value())
            self.progress.setValue(0)
            self.status.setText('识别预检中 · 未发送点击')

    def _start(self):
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
        self.check_worker.result.connect(self.check_result.setText)
        self.check_worker.finished.connect(self._check_finished)
        self.check_worker.start()

    def _check_finished(self):
        for widget in (self.task_list, self.search, self.category, self.config_panel):
            widget.setEnabled(not self._task_active)
        self.preflight.setEnabled(not self._task_active)
        self._update_enabled()
