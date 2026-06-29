"""Auth/permission configuration tab."""
from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QLineEdit, QHeaderView, QLabel)
from ...utils.config_loader import get_config, save_config


class AuthTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.load_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Gift permission ----
        gift = QGroupBox("礼物权限控制")
        gf = QFormLayout(gift)

        gift_desc = QLabel(
            "观众发送<b>付费礼物</b>后可获得一段时间的大模型指令白名单资格。<br>"
            "<b>开启</b>：只有送过礼物的观众才能通过大模型发送游戏指令<br>"
            "<b>关闭</b>：所有观众都能直接使用大模型，无需先送礼物<br>"
            "<b>最低价格</b>：礼物总价需达到设定值才计入（免费银瓜子礼物自动过滤）<br>"
            "<b>允许礼物</b>：只有列表中的礼物名才计入，留空则所有付费礼物都计入<br>"
            "<b>有效期</b>：白名单持续时间，过期后需重新送礼<br>"
            "<i style='color:#8D6E63;'>注：1000 金瓜子 = 1 元。</i>"
        )
        gift_desc.setWordWrap(True)
        gift_desc.setStyleSheet("color: #5D4037; font-size: 12px; padding: 4px;")
        gf.addRow(gift_desc)

        self._require_gift = QCheckBox("启用礼物权限（关闭则所有人可用大模型）")
        gf.addRow(self._require_gift)
        self._gift_expire = QSpinBox()
        self._gift_expire.setRange(1, 1440)
        self._gift_expire.setSuffix(" 分钟")
        gf.addRow("白名单有效期:", self._gift_expire)

        # Gift price / name filters
        self._min_gift_price = QSpinBox()
        self._min_gift_price.setRange(0, 999999)
        self._min_gift_price.setSuffix(" 金瓜子")
        self._min_gift_price.setToolTip("0 表示不限制。1000 金瓜子 = 1 元")
        self._min_gift_price.setSpecialValueText("不限")
        gf.addRow("最低礼物价格:", self._min_gift_price)

        self._allowed_gifts = QLineEdit()
        self._allowed_gifts.setPlaceholderText("如：小电视, B坷垃, 舰长 (逗号分隔，留空=全部允许)")
        self._allowed_gifts.setToolTip("只有这些礼物才能进入白名单，留空则不限制")
        gf.addRow("允许的礼物名:", self._allowed_gifts)
        layout.addWidget(gift)

        # ---- Whitelist ----
        wl = QGroupBox("白名单用户")
        wf = QVBoxLayout(wl)
        self._whitelist_table = QTableWidget(0, 3)
        self._whitelist_table.setHorizontalHeaderLabels(["用户", "平台", "剩余时间(分)"])
        self._whitelist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._whitelist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._whitelist_table.setSelectionBehavior(QTableWidget.SelectRows)
        wf.addWidget(self._whitelist_table)
        add_row = QHBoxLayout()
        self._wl_input = QLineEdit()
        self._wl_input.setPlaceholderText("手动添加用户名（测试用）")
        add_row.addWidget(self._wl_input)
        btn_add = QPushButton("添加")
        btn_remove = QPushButton("移除选中")
        add_row.addWidget(btn_add)
        add_row.addWidget(btn_remove)
        wf.addLayout(add_row)
        layout.addWidget(wl)

        btn_add.clicked.connect(self._on_add_whitelist)
        btn_remove.clicked.connect(self._on_remove_whitelist)

    def load_config(self) -> None:
        cfg = get_config()
        a = cfg.get("auth", {})
        self._require_gift.setChecked(a.get("require_gift", True))
        self._gift_expire.setValue(a.get("gift_expire_minutes", 60))
        self._min_gift_price.setValue(a.get("min_gift_price", 0))
        self._allowed_gifts.setText(a.get("allowed_gift_names", ""))

    def save_config(self) -> None:
        cfg = get_config()
        cfg["auth"]["require_gift"] = self._require_gift.isChecked()
        cfg["auth"]["gift_expire_minutes"] = self._gift_expire.value()
        cfg["auth"]["min_gift_price"] = self._min_gift_price.value()
        cfg["auth"]["allowed_gift_names"] = self._allowed_gifts.text()
        save_config(cfg)

    def update_whitelist(self, entries: list[dict]) -> None:
        self._whitelist_table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self._whitelist_table.setItem(i, 0, QTableWidgetItem(e.get("user_name", "")))
            self._whitelist_table.setItem(i, 1, QTableWidgetItem(e.get("platform", "")))
            self._whitelist_table.setItem(i, 2, QTableWidgetItem(str(e.get("remaining_minutes", 0))))

    def _on_add_whitelist(self) -> None:
        name = self._wl_input.text().strip()
        if name:
            row = self._whitelist_table.rowCount()
            self._whitelist_table.insertRow(row)
            self._whitelist_table.setItem(row, 0, QTableWidgetItem(name))
            self._whitelist_table.setItem(row, 1, QTableWidgetItem("Manual"))
            self._whitelist_table.setItem(row, 2, QTableWidgetItem("-"))
            self._wl_input.clear()

    def _on_remove_whitelist(self) -> None:
        for row in sorted(set(i.row() for i in self._whitelist_table.selectedIndexes()), reverse=True):
            self._whitelist_table.removeRow(row)
