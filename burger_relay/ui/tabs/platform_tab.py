"""Live platform configuration tab."""
from __future__ import annotations
import webbrowser
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QLineEdit, QPushButton, QHBoxLayout, QLabel,
    QAbstractSpinBox)
from PyQt5.QtCore import Qt
from ...utils.config_loader import get_config, save_config

COOKIE_HELP = (
    '<div style="color:#a6adc8;font-size:12px;line-height:1.5;'
    'background:#FFF0E0;border-radius:8px;padding:8px;">'
    '<b style="color:#89b4fa;">如何获取 B站 Cookie：</b><br>'
    '1. 用浏览器打开 <a href="https://www.bilibili.com" style="color:#f9e2af;">'
    'bilibili.com</a> 并<b>登录</b><br>'
    '2. 按 <b>F12</b> 打开开发者工具 → <b>Application</b> 标签<br>'
    '3. 左侧 Storage → Cookies → 点击 <b>bilibili.com</b><br>'
    '4. 找到并复制以下三个值：<br>'
    '&nbsp;&nbsp;&nbsp;• <b>SESSDATA</b> — 登录会话（必填）<br>'
    '&nbsp;&nbsp;&nbsp;• <b>bili_jct</b> — CSRF Token<br>'
    '&nbsp;&nbsp;&nbsp;• <b>buvid3</b> — 设备标识<br>'
    '5. 粘贴到下方对应输入框，保存配置后重启<br>'
    '<i style="color:#8D6E63;">不填则游客模式，用户名会被打码显示</i>'
    '</div>'
)


class PlatformTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.load_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Bilibili
        bili = QGroupBox("B站配置")
        bf = QFormLayout(bili)

        self._bili_room = QSpinBox()
        self._bili_room.setRange(1, 99999999)
        self._bili_room.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._bili_room.setToolTip("直播间ID（URL中的数字）")
        bf.addRow("直播间ID:", self._bili_room)

        # Cookie help section
        help_label = QLabel(COOKIE_HELP)
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.RichText)
        help_label.setOpenExternalLinks(True)
        bf.addRow(help_label)

        # Open browser button
        btn_row = QHBoxLayout()
        self._btn_open_bili = QPushButton("🔗 打开B站 → 登录后按F12获取Cookie")
        self._btn_open_bili.clicked.connect(
            lambda: webbrowser.open("https://www.bilibili.com"))
        btn_row.addWidget(self._btn_open_bili)
        btn_row.addStretch()
        bf.addRow(btn_row)

        self._bili_sessdata = QLineEdit()
        self._bili_sessdata.setPlaceholderText("必填 — 从浏览器 Cookie 复制")
        self._bili_sessdata.setEchoMode(QLineEdit.Password)
        bf.addRow("SESSDATA:", self._bili_sessdata)

        self._bili_jct = QLineEdit()
        self._bili_jct.setPlaceholderText("从浏览器 Cookie 复制")
        bf.addRow("bili_jct:", self._bili_jct)

        self._bili_buvid3 = QLineEdit()
        self._bili_buvid3.setPlaceholderText("从浏览器 Cookie 复制")
        bf.addRow("buvid3:", self._bili_buvid3)

        self._bili_status = QLabel("未连接")
        bf.addRow("状态:", self._bili_status)
        layout.addWidget(bili)

        layout.addStretch()

    def load_config(self) -> None:
        cfg = get_config()
        b = cfg.get("bilibili", {})
        self._bili_room.setValue(b.get("room_id", 0))
        self._bili_sessdata.setText(b.get("sessdata", ""))
        self._bili_jct.setText(b.get("bili_jct", ""))
        self._bili_buvid3.setText(b.get("buvid3", ""))

    def save_config(self) -> None:
        cfg = get_config()
        cfg["bilibili"]["room_id"] = self._bili_room.value()
        cfg["bilibili"]["sessdata"] = self._bili_sessdata.text()
        cfg["bilibili"]["bili_jct"] = self._bili_jct.text()
        cfg["bilibili"]["buvid3"] = self._bili_buvid3.text()
        save_config(cfg)

    def set_bilibili_status(self, connected: bool) -> None:
        self._bili_status.setText("已连接" if connected else "未连接")
