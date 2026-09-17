from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from yys_helper.demo import create_demo_state
from yys_helper.infrastructure.repository import AppRepository

from .main_window import MainWindow
from .theme import APP_STYLE


def run_app(*, demo_mode: bool = False) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("御魂匠")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLE)
    repository = AppRepository(Path.cwd() / "data" / "yys-helper.db")
    application.aboutToQuit.connect(repository.close)
    window = MainWindow(
        create_demo_state(), demo_mode=demo_mode, repository=repository
    )
    window.show()
    return application.exec()
