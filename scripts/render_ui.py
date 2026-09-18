"""Render UI with synthetic data only. Does not connect to any device."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from yys_helper.demo import create_demo_state
from yys_helper.ui.main_window import MainWindow
from yys_helper.ui.theme import APP_STYLE

app = QApplication([])
for font in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
app.setStyle('Fusion')
app.setStyleSheet(APP_STYLE)
window = MainWindow(create_demo_state(), demo_mode=True)
window.resize(1280, 860)
window.show()
output = Path('data/ui-previews')
output.mkdir(parents=True, exist_ok=True)
for index, name in enumerate(('overview', 'scheme', 'inventory', 'upgrade', 'tasks')):
    window._navigate(index)
    app.processEvents()
    window.grab().save(str(output / f'{name}.png'))
window.dailies_page.search.setText('单关')
app.processEvents()
window.grab().save(str(output / 'activity.png'))
window.resize(1050, 680)
app.processEvents()
window.grab().save(str(output / 'activity-small.png'))
print(output.resolve())
window.close()
