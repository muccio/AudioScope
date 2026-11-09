"""AudioScope Professional Dark Theme QSS & Color Palette.

Pro Audio console aesthetic inspired by high-end mastering and broadcast software.
"""

DARK_THEME_QSS = """
/* Global Window & Base Styles */
QWidget {
    background-color: #12141a;
    color: #e2e6f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}

QMainWindow {
    background-color: #0d0f14;
}

/* Header & Cards */
QFrame#GlobalHeader {
    background-color: #161922;
    border-bottom: 1px solid #282d3c;
    padding: 10px 16px;
}

QFrame#HeaderDropArea {
    background-color: #1a1e29;
    border: 2px dashed #343c4f;
    border-radius: 8px;
    padding: 8px 16px;
}

QFrame#HeaderDropArea:hover {
    border-color: #00d2ff;
    background-color: #1d2332;
}

QFrame.card-frame {
    background-color: #181b24;
    border: 1px solid #282d3b;
    border-radius: 8px;
}

/* Tab Widget & Bar */
QTabWidget::pane {
    border: 1px solid #262b3a;
    background-color: #151821;
    border-radius: 0 0 6px 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #161922;
    color: #8c93a8;
    border: 1px solid #262b3a;
    border-bottom: none;
    padding: 10px 22px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 13px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #1f2432;
    color: #00d2ff;
    border-top: 2px solid #00d2ff;
    border-bottom: 1px solid #1f2432;
}

QTabBar::tab:hover:!selected {
    background-color: #1a1e29;
    color: #c0c6d8;
}

/* Buttons */
QPushButton {
    background-color: #242938;
    color: #e6ebf5;
    border: 1px solid #373e52;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2e3547;
    border-color: #00d2ff;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1a1e29;
    border-color: #0099cc;
}

QPushButton:disabled {
    background-color: #181b24;
    color: #555b6e;
    border-color: #232734;
}

QPushButton#PrimaryButton {
    background-color: #0d47a1;
    border: 1px solid #1976d2;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background-color: #1565c0;
    border-color: #00d2ff;
}

/* Inputs & Search Bars */
QLineEdit {
    background-color: #1b1e28;
    color: #f0f4fc;
    border: 1px solid #2e3546;
    border-radius: 5px;
    padding: 6px 12px;
    selection-background-color: #005a9e;
}

QLineEdit:focus {
    border: 1px solid #00d2ff;
    background-color: #1e2230;
}

QComboBox {
    background-color: #222634;
    color: #f0f4fc;
    border: 1px solid #343c50;
    border-radius: 5px;
    padding: 6px 12px;
    font-weight: 500;
}

QComboBox:focus, QComboBox:hover {
    border-color: #00d2ff;
}

QComboBox QAbstractItemView {
    background-color: #1b1e28;
    color: #f0f4fc;
    border: 1px solid #343c50;
    selection-background-color: #00d2ff;
    selection-color: #0d0f14;
}

/* Tables & Trees */
QTableView, QTreeView, QTreeWidget {
    background-color: #161922;
    alternate-background-color: #1a1d27;
    color: #d8deec;
    border: 1px solid #262b3a;
    border-radius: 6px;
    gridline-color: #222635;
    outline: none;
}

QTableView::item, QTreeView::item, QTreeWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #1e2230;
}

QTableView::item:selected, QTreeView::item:selected, QTreeWidget::item:selected {
    background-color: #1e3a5f;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1e222f;
    color: #9aa1b5;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #2c3244;
    border-right: 1px solid #262a3a;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #14161f;
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #2f3547;
    min-height: 24px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #00d2ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #14161f;
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #2f3547;
    min-width: 24px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #00d2ff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Progress Bar */
QProgressBar {
    background-color: #1b1e29;
    border: 1px solid #2c3345;
    border-radius: 5px;
    text-align: center;
    color: #e6ebf5;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0099cc, stop:1 #00e676);
    border-radius: 4px;
}

/* Status Bar */
QStatusBar {
    background-color: #101217;
    border-top: 1px solid #202430;
    color: #8c93a8;
    font-size: 12px;
    padding: 4px 8px;
}

/* Splitter */
QSplitter::handle {
    background-color: #242938;
}

QSplitter::handle:hover {
    background-color: #00d2ff;
}

/* Badges and Meter Accents */
.badge-pass {
    background-color: #004d26;
    color: #00e676;
    border: 1px solid #00b050;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 700;
}

.badge-fail {
    background-color: #4a1525;
    color: #ff3d71;
    border: 1px solid #d92550;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 700;
}

.badge-info {
    background-color: #132f4c;
    color: #00d2ff;
    border: 1px solid #1e5c8a;
    border-radius: 4px;
    padding: 3px 8px;
    font-weight: 600;
}
"""
