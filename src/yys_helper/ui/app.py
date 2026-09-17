from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from yys_helper.demo import DemoState, create_demo_state, create_state
from yys_helper.domain.models import BuildRequirement
from yys_helper.domain.scoring import DEFAULT_PROFILES
from yys_helper.infrastructure.repository import AppRepository

from .main_window import MainWindow
from .theme import APP_STYLE


def load_initial_state(
    repository: AppRepository, *, demo_mode: bool
) -> DemoState:
    if demo_mode:
        return create_demo_state()
    real_requirement = BuildRequirement(weights=DEFAULT_PROFILES["output"])
    return create_state(repository.list_souls(), real_requirement)


def run_app(*, demo_mode: bool = False) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("御魂匠")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLE)
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "app-icon.png"
    application.setWindowIcon(QIcon(str(icon_path)))
    repository = AppRepository(Path.cwd() / "data" / "yys-helper.db")
    application.aboutToQuit.connect(repository.close)
    window = MainWindow(
        load_initial_state(repository, demo_mode=demo_mode),
        demo_mode=demo_mode,
        repository=repository,
    )
    window.show()
    return application.exec()
