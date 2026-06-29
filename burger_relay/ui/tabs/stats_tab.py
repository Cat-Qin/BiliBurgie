"""Statistics panel tab."""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSlot
from ...utils.models import AppStats

class StatsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        cards = QHBoxLayout()
        self._cards: dict[str, QLabel] = {}
        for name in ("总弹幕", "总订单", "总投诉", "总互动", "大模型调用", "在线用户"):
            g = QGroupBox(name)
            g.setFixedHeight(80)
            gv = QVBoxLayout(g)
            lbl = QLabel("0")
            lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
            lbl.setAlignment(Qt.AlignCenter)  # AlignCenter
            gv.addWidget(lbl)
            cards.addWidget(g)
            self._cards[name] = lbl
        layout.addLayout(cards)

        users_box = QGroupBox("用户排行")
        uv = QVBoxLayout(users_box)
        self._user_table = QTableWidget(0, 4)
        self._user_table.setHorizontalHeaderLabels(["用户", "弹幕数", "订单数", "送礼数"])
        self._user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        uv.addWidget(self._user_table)
        layout.addWidget(users_box)

    @pyqtSlot(object)
    def update_stats(self, stats: AppStats) -> None:
        self._cards["总弹幕"].setText(str(stats.total_danmaku))
        self._cards["总订单"].setText(str(stats.total_orders))
        self._cards["总投诉"].setText(str(stats.total_complaints))
        self._cards["总互动"].setText(str(stats.total_interacts))
        self._cards["大模型调用"].setText(str(stats.llm_calls))
        self._cards["在线用户"].setText(str(stats.online_users))

        sorted_users = sorted(stats.users.values(), key=lambda u: u.order_count, reverse=True)
        self._user_table.setRowCount(len(sorted_users))
        for i, u in enumerate(sorted_users):
            self._user_table.setItem(i, 0, QTableWidgetItem(u.user_name))
            self._user_table.setItem(i, 1, QTableWidgetItem(str(u.danmaku_count)))
            self._user_table.setItem(i, 2, QTableWidgetItem(str(u.order_count)))
            self._user_table.setItem(i, 3, QTableWidgetItem(str(u.gift_count)))


