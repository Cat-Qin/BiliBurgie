"""Status bar with connection indicators and stats."""
from __future__ import annotations
from PyQt5.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout

class StatusIndicator(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._dot = QLabel("⚪")
        self._dot.setFixedWidth(20)
        self._text = QLabel(label)
        layout.addWidget(self._dot)
        layout.addWidget(self._text)

    def set_connected(self, connected: bool) -> None:
        self._dot.setText("🟢" if connected else "🔴")
        self._text.setStyleSheet(
            "color: #558B2F" if connected else "color: #D32F2F")

    def set_available(self, available: bool | None) -> None:
        if available is None:
            self._dot.setText("⚪")
            self._text.setStyleSheet("color: #8D6E63")
        elif available:
            self._dot.setText("🟢")
            self._text.setStyleSheet("color: #558B2F")
        else:
            self._dot.setText("🔴")
            self._text.setStyleSheet("color: #D32F2F")

class AppStatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._irc = StatusIndicator("IRC")
        self._bili = StatusIndicator("B站")
        self._llm = StatusIndicator("大模型")
        self._stats = QLabel("弹幕:0 订单:0")
        self.addPermanentWidget(self._irc)
        self.addPermanentWidget(self._bili)
        self.addPermanentWidget(self._llm)
        self.addPermanentWidget(self._stats)

    def set_irc(self, connected: bool) -> None:
        self._irc.set_connected(connected)

    def set_bilibili(self, connected: bool) -> None:
        self._bili.set_connected(connected)

    def set_llm(self, available: bool | None) -> None:
        self._llm.set_available(available)

    def set_stats(self, danmaku: int, orders: int) -> None:
        self._stats.setText(f"弹幕:{danmaku} 订单:{orders}")
