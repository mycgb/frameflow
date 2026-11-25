"""可复用的「关于」页组件。

新软件直接复制本文件调用 create_about_widget(...) 即可；
二维码图片请复制进项目资源目录，用相对路径传入，不要写死 F:\\ 绝对路径。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

ACCOUNT_NAME = "前沿软智"


def create_about_widget(
    app_name: str,
    version: str = "1.0",
    description: str = "",
    qr_path: str = "",
    account_name: str = ACCOUNT_NAME,
    icon_path: str = "",
) -> QWidget:
    """生成居中的关于页：软件信息 + 公众号二维码 + 公众号名称。"""
    page = QWidget()
    page.setObjectName("aboutPage")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(24, 24, 24, 24)
    outer.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

    card = QFrame()
    card.setObjectName("aboutCard")
    card.setMaximumWidth(620)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(34, 30, 34, 30)
    layout.setSpacing(14)
    layout.setAlignment(Qt.AlignHCenter)

    if icon_path and os.path.isfile(icon_path):
        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon.setPixmap(pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(icon)

    title = QLabel(app_name)
    title.setObjectName("aboutTitle")
    title.setAlignment(Qt.AlignCenter)
    layout.addWidget(title)

    badge = QLabel(f"版本 {version}")
    badge.setObjectName("versionBadge")
    badge.setAlignment(Qt.AlignCenter)
    layout.addWidget(badge)

    if description:
        desc = QLabel(description)
        desc.setObjectName("aboutDesc")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

    layout.addSpacing(6)

    if qr_path and os.path.isfile(qr_path):
        pixmap = QPixmap(qr_path)
        if not pixmap.isNull():
            qr = QLabel()
            qr.setAlignment(Qt.AlignCenter)
            qr.setPixmap(
                pixmap.scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            layout.addWidget(qr)

    account = QLabel(account_name)
    account.setObjectName("accountName")
    account.setAlignment(Qt.AlignCenter)
    layout.addWidget(account)

    tip = QLabel("扫描上方二维码关注公众号，获取更多工具与更新")
    tip.setObjectName("cardHint")
    tip.setAlignment(Qt.AlignCenter)
    layout.addWidget(tip)

    footer = QLabel(f"© {app_name} · 保留所有权利")
    footer.setObjectName("aboutFooter")
    footer.setAlignment(Qt.AlignCenter)
    layout.addSpacing(10)
    layout.addWidget(footer)

    outer.addWidget(card, 0, Qt.AlignHCenter | Qt.AlignVCenter)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setWidget(page)
    holder = QWidget()
    h = QHBoxLayout(holder)
    h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(scroll)
    holder.setObjectName("aboutRoot")
    return holder
