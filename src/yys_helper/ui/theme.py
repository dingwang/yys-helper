"""Light, native-feeling desktop palette; no platform-specific blur dependency."""
APP_STYLE = """
QWidget { color: #202124; background: #F5F5F7; font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 13px; }
QMainWindow { background: #F5F5F7; }
QLabel, QCheckBox { background: transparent; }
QFrame#sidebar { background: #EBEDF1; border-right: 1px solid #DDDFE4; }
QFrame#card { background: #FFFFFF; border: 1px solid #E4E5EA; border-radius: 16px; }
QWidget#transparent { background: transparent; }
QLabel#brand { font-size: 22px; font-weight: 700; color: #202124; }
QLabel#muted { color: #727681; }
QLabel#title { font-size: 27px; font-weight: 700; color: #1D1D1F; }
QLabel#sectionTitle { font-size: 21px; font-weight: 700; }
QLabel#metric { font-size: 32px; font-weight: 700; color: #007AFF; }
QLabel#safePill { color: #29805A; background: #E8F5EC; border-radius: 10px; padding: 4px 10px; font-size: 11px; }
QLabel#statusPill { color: #576171; background: #EFF3F8; border-radius: 9px; padding: 8px 12px; }
QPushButton { background: #FFFFFF; color: #323842; border: 1px solid #DDE0E6; border-radius: 8px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #F0F5FF; border-color: #B9D4FA; }
QPushButton:pressed { background: #E0ECFD; }
QPushButton:disabled { color: #A4A8B0; background: #EFF0F3; border-color: #E8E9ED; }
QPushButton#primary { color: white; background: #007AFF; border: 1px solid #007AFF; }
QPushButton#primary:hover { background: #006AE0; }
QPushButton#primary:disabled { color: #98B6D8; background: #E3EDFA; border-color: #E3EDFA; }
QPushButton#danger { color: #C44747; background: #FFF3F2; border-color: #F2D6D4; }
QPushButton#danger:hover { background: #FCE1DF; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px 16px; font-weight: 500; }
QPushButton#nav:hover { background: #E1E5EC; }
QPushButton#nav:checked { color: #006CE5; background: #DBE8FA; font-weight: 700; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox,
QFrame#card QLineEdit, QFrame#card QSpinBox, QFrame#card QComboBox {
 background: #F8F9FB; border: 1px solid #DDDFE5; border-radius: 7px; padding: 7px; selection-background-color: #CCE3FF; selection-color: #164C83;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #007AFF; }
QComboBox QAbstractItemView { background: white; selection-background-color: #E2EDFF; color: #252A32; }
QTableWidget { background: white; alternate-background-color: #F8F9FC; border: 1px solid #E2E4E9; border-radius: 10px; gridline-color: #EEF0F4; selection-background-color: #DFECFF; selection-color: #174677; }
QTableWidget::item { padding: 6px; }
QHeaderView::section { background: #F1F3F7; color: #747A85; border: none; border-bottom: 1px solid #E1E4EB; padding: 10px; font-weight: 600; }
QListWidget#taskList { background: transparent; border: none; outline: none; }
QListWidget#taskList::item { padding: 12px 10px; border-radius: 9px; color: #515864; }
QListWidget#taskList::item:selected { background: #E4EEFD; color: #0067D8; }
QListWidget#taskList::item:hover { background: #F0F4FA; }
QCheckBox#riskCheck { color: #767D87; spacing: 8px; font-size: 12px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { background: white; border: 1px solid #BAC1CC; border-radius: 4px; }
QCheckBox::indicator:checked { background: #007AFF; border: 1px solid #007AFF; border-radius: 4px; }
QProgressBar { border: none; border-radius: 2px; background: #E8ECF1; }
QProgressBar::chunk { background: #007AFF; border-radius: 2px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #C5C9D1; min-height: 25px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { color: #313641; background: white; border: 1px solid #D7DDE6; padding: 6px; }
"""
