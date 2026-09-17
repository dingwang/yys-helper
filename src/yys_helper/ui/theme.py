APP_STYLE = """
QWidget {
    color: #EEF2FF;
    background: #0B1020;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
QMainWindow { background: #080D19; }
QFrame#sidebar { background: #11182A; border-right: 1px solid #24304A; }
QFrame#card {
    background: #151E33;
    border: 1px solid #263452;
    border-radius: 12px;
}
QLabel#brand { font-size: 23px; font-weight: 700; color: #F6C453; }
QLabel#muted { color: #8E9BB7; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#metric { font-size: 26px; font-weight: 700; color: #F6C453; }
QPushButton {
    background: #293758;
    border: 1px solid #3B4D75;
    border-radius: 8px;
    padding: 9px 14px;
}
QPushButton:hover { background: #35476F; }
QPushButton:pressed { background: #202B46; }
QPushButton#primary { background: #6D5CE7; border-color: #8576F2; font-weight: 600; }
QPushButton#primary:hover { background: #7A69F0; }
QPushButton#danger { background: #B83D52; border-color: #DD5A70; font-weight: 700; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 11px 15px; }
QPushButton#nav:hover { background: #1B2741; }
QPushButton#nav:checked { background: #2B3860; color: #F6C453; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #0E1526;
    border: 1px solid #344464;
    border-radius: 7px;
    padding: 7px;
    selection-background-color: #6D5CE7;
}
QTableWidget {
    background: #10182A;
    alternate-background-color: #131D31;
    border: 1px solid #263452;
    border-radius: 9px;
    gridline-color: #263452;
}
QHeaderView::section {
    background: #1D2943;
    color: #BFC9DD;
    border: none;
    border-right: 1px solid #2B3957;
    padding: 8px;
}
QTabBar::tab { padding: 9px 15px; }
QScrollBar:vertical { background: #0E1526; width: 10px; }
QScrollBar::handle:vertical { background: #344464; border-radius: 5px; }
"""
