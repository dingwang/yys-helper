APP_STYLE = """
QWidget {
    color: #F3F5FB;
    background: #090E19;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
QMainWindow { background: #070B14; }
QFrame#sidebar {
    background: #0D1424;
    border-right: 1px solid #25314B;
}
QFrame#card {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #151E32, stop:1 #11192A);
    border: 1px solid #293752;
    border-radius: 14px;
}
QLabel#brand { font-size: 22px; font-weight: 800; color: #F5C86B; }
QLabel#muted { color: #91A0BD; }
QLabel#title { font-size: 25px; font-weight: 800; color: #FAFBFF; }
QLabel#metric { font-size: 28px; font-weight: 800; color: #F5C86B; }
QLabel#safePill {
    color: #88E1B6;
    background: #102C27;
    border: 1px solid #245B4E;
    border-radius: 11px;
    padding: 4px 10px;
    font-weight: 600;
}
QLabel#statusPill {
    color: #B9C7E3;
    background: #0C1424;
    border: 1px solid #2D3E60;
    border-radius: 9px;
    padding: 7px 10px;
}
QPushButton {
    background: #263552;
    border: 1px solid #3A4E75;
    border-radius: 9px;
    padding: 9px 15px;
    font-weight: 600;
}
QPushButton:hover { background: #31466D; border-color: #5870A1; }
QPushButton:pressed { background: #202B46; }
QPushButton:disabled { color: #596780; background: #161E2E; border-color: #27334A; }
QPushButton#primary {
    color: #0D1320;
    background: #F2C262;
    border-color: #FFD986;
    font-weight: 800;
}
QPushButton#primary:hover { background: #FFD478; border-color: #FFE2A2; }
QPushButton#danger { background: #A9374A; border-color: #D55268; font-weight: 800; }
QPushButton#danger:hover { background: #BD4057; }
QPushButton#nav {
    text-align: left;
    border: 1px solid transparent;
    background: transparent;
    padding: 11px 15px;
    font-weight: 600;
}
QPushButton#nav:hover { background: #17233B; }
QPushButton#nav:checked {
    background: #202E4A;
    border-color: #34476B;
    color: #F5C86B;
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #0B1220;
    border: 1px solid #344769;
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #6D5CE7;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #6D86BD;
}
QTableWidget {
    background: #0D1525;
    alternate-background-color: #111B2E;
    border: 1px solid #293752;
    border-radius: 10px;
    gridline-color: #23314B;
    selection-background-color: #2C4169;
}
QHeaderView::section {
    background: #192640;
    color: #C8D2E6;
    border: none;
    border-right: 1px solid #2D3B58;
    padding: 9px;
    font-weight: 700;
}
QCheckBox#riskCheck { color: #F0B3BC; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QTabBar::tab { padding: 9px 15px; }
QScrollBar:vertical { background: #0E1526; width: 10px; }
QScrollBar::handle:vertical { background: #344464; border-radius: 5px; }
QToolTip { color: #F4F6FA; background: #172238; border: 1px solid #42567B; padding: 6px; }
"""
