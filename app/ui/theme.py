"""统一 QSS 主题（浅色现代风）。"""

APP_QSS = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: #1F2937;
}
QMainWindow, QDialog { background: #F4F6FB; }

#header { background: #FFFFFF; border-bottom: 1px solid #E7EBF3; }
#appTitle { font-size: 21px; font-weight: 700; color: #111827; }
#appSubtitle { font-size: 12px; color: #8A93A6; }
#versionBadge {
    color: #4F6BFF; background: #EEF1FF; border: 1px solid #DCE3FF;
    border-radius: 11px; padding: 3px 10px; font-size: 11px; font-weight: 600;
}

#card {
    background: #FFFFFF; border: 1px solid #E7EBF3; border-radius: 14px;
}
#cardTitle { font-size: 14px; font-weight: 700; color: #111827; }
#cardHint { font-size: 11px; color: #9AA3B2; }
#fieldLabel { font-size: 12px; color: #6B7280; font-weight: 600; }

QPushButton {
    background: #FFFFFF; color: #374151; border: 1px solid #DDE3ED;
    border-radius: 8px; padding: 8px 14px; min-height: 18px;
}
QPushButton:hover { background: #F7F9FF; border-color: #B9C6FF; color: #3348B8; }
QPushButton:pressed { background: #EEF1FF; }
QPushButton:disabled { color: #B7BDC9; background: #F7F8FA; border-color: #E8EAF0; }

QPushButton#primary {
    background: #4F6BFF; color: #FFFFFF; border: 1px solid #4F6BFF;
    font-weight: 700; padding: 11px 18px;
}
QPushButton#primary:hover { background: #3F5BEF; border-color: #3F5BEF; }
QPushButton#primary:pressed { background: #3350DC; }
QPushButton#primary:disabled { background: #B9C4F8; border-color: #B9C4F8; color: #F4F6FF; }

QPushButton#danger {
    background: #FFFFFF; color: #DC2626; border: 1px solid #F3C7C7; font-weight: 600;
}
QPushButton#danger:hover { background: #FEF2F2; border-color: #EBA8A8; }
QPushButton#warning {
    background: #FFFFFF; color: #B45309; border: 1px solid #F4D6A8; font-weight: 600;
}
QPushButton#warning:hover { background: #FFFBEB; border-color: #ECC07C; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF; border: 1px solid #DDE3ED; border-radius: 8px;
    padding: 7px 10px; color: #1F2937; selection-background-color: #4F6BFF;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #8CA0FF; outline: none;
}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    background: #F7F8FA; color: #AAB0BC;
}
QComboBox { min-height: 18px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #8A93A6; margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF; border: 1px solid #DDE3ED; border-radius: 8px;
    selection-background-color: #EEF1FF; selection-color: #3348B8; padding: 4px;
}

QCheckBox { spacing: 8px; color: #4B5563; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid #CBD2DE; background: #FFFFFF;
}
QCheckBox::indicator:checked { background: #4F6BFF; border-color: #4F6BFF; }
QCheckBox::indicator:hover { border-color: #8CA0FF; }

#videoList, #imageList {
    background: #FBFCFF; border: 1px dashed #D5DDEB; border-radius: 10px;
    padding: 6px; color: #374151;
}
#videoList::item, #imageList::item {
    padding: 9px 10px; border-radius: 7px; margin: 2px 3px;
}
#videoList::item:selected, #imageList::item:selected { background: #E9EDFF; color: #3348B8; }
#videoList::item:hover:!selected, #imageList::item:hover:!selected { background: #F2F5FC; }

QTabWidget::pane {
    border: 1px solid #E7EBF3; border-radius: 12px; background: #F4F6FB;
    top: -1px;
}
QTabBar::tab {
    background: transparent; color: #6B7280; border: none;
    padding: 9px 22px; margin-right: 6px; border-radius: 8px;
    font-size: 13px; font-weight: 600;
}
QTabBar::tab:hover { background: #EBEEF8; color: #3348B8; }
QTabBar::tab:selected { background: #FFFFFF; color: #4F6BFF; border: 1px solid #E7EBF3; }

#aboutRoot, #aboutPage { background: #F4F6FB; }
#aboutCard {
    background: #FFFFFF; border: 1px solid #E7EBF3; border-radius: 16px;
}
#aboutTitle { font-size: 24px; font-weight: 700; color: #111827; }
#aboutDesc { font-size: 13px; color: #6B7280; line-height: 150%; }
#accountName { font-size: 17px; font-weight: 700; color: #4F6BFF; }
#aboutFooter { font-size: 11px; color: #AAB0BC; }

#previewBox {
    background: #0F1420; border-radius: 10px; border: 1px solid #E7EBF3;
}
#previewPlaceholder { color: #7C869A; font-size: 13px; }
#previewMeta { color: #6B7280; font-size: 12px; }

QProgressBar {
    background: #EDF0F6; border-radius: 7px; height: 14px;
    text-align: center; color: #374151; font-size: 11px; font-weight: 600;
}
QProgressBar::chunk { background: #4F6BFF; border-radius: 7px; }
QProgressBar#overall::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4F6BFF, stop:1 #7C8CFF); }

QSlider::groove:horizontal { height: 5px; background: #E5E9F2; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #8CA0FF; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: #4F6BFF; border: 2px solid #FFFFFF;
}

#logBox {
    background: #FBFCFF; border: 1px solid #E7EBF3; border-radius: 10px;
    font-family: "Consolas", "Microsoft YaHei UI", monospace; font-size: 12px;
    padding: 6px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #D7DDE8; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #BFC8D8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #D7DDE8; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: transparent; }

QSplitter::handle { background: #F4F6FB; width: 10px; }
QStatusBar { background: #FFFFFF; color: #8A93A6; border-top: 1px solid #E7EBF3; }
QToolTip {
    background: #1F2937; color: #FFFFFF; border: none; padding: 6px 8px; border-radius: 6px;
}
"""


def log_html(level: str, message: str) -> str:
    color = {
        "info": "#4B5563",
        "success": "#0F9D58",
        "warn": "#C2760A",
        "error": "#DC2626",
    }.get(level, "#4B5563")
    text = (message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f'<span style="color:{color}">{text}</span>'
