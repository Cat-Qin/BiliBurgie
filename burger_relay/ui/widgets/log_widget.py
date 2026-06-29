"""Log output widget with color-coded levels and category filters."""
from __future__ import annotations
from PyQt5.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QCheckBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QTextCursor

COLORS = {"INFO": "#5D4037", "WARNING": "#E65100", "ERROR": "#D32F2F",
          "SUCCESS": "#558B2F", "DEBUG": "#8D6E63", "GIFT": "#7B1FA2"}

# Category definitions: (display_name, icon, match_prefixes)
CATEGORIES = [
    ("danmaku",  "弹幕",     ("DANMAKU:",)),
    ("gift",     "礼物",     ("GIFT:",)),  # also level=GIFT from old code
    ("order",    "指令",     ("ORDER:", "COMPLAINT:", "INTERACT:")),
    ("like",     "点赞",     ("❤",)),
    ("notice",   "公告",     ("📢",)),
    ("system",   "系统",     ()),  # catch-all: doesn't match any other category
]


class LogWidget(QWidget):
    """Scrollable log viewer with category filter checkboxes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[tuple[str, str, str]] = []  # (html, plain_text, category_key)
        self._auto_scroll = True
        self._visible_categories: set[str] = {c[0] for c in CATEGORIES}
        self._setup_ui()

    # ---- UI setup ----

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Row 1: search + buttons
        toolbar1 = QHBoxLayout()
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("搜索日志...")
        self._filter_edit.textChanged.connect(self._on_filter)
        toolbar1.addWidget(self._filter_edit)

        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.clear)
        toolbar1.addWidget(btn_clear)

        btn_auto = QPushButton("自动滚动")
        btn_auto.setCheckable(True)
        btn_auto.setChecked(True)
        btn_auto.toggled.connect(lambda v: setattr(self, "_auto_scroll", v))
        toolbar1.addWidget(btn_auto)
        layout.addLayout(toolbar1)

        # Row 2: category checkboxes
        toolbar2 = QHBoxLayout()
        self._category_checks: dict[str, QCheckBox] = {}
        for key, label, _ in CATEGORIES:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, k=key: self._on_category_toggle(k, checked))
            cb.setStyleSheet("QCheckBox { color: #5D4037; font-size: 12px; spacing: 4px; }")
            self._category_checks[key] = cb
            toolbar2.addWidget(cb)
        toolbar2.addStretch()
        layout.addLayout(toolbar2)

        # Text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(10000)
        self._text.setStyleSheet(
            "QPlainTextEdit { background-color: #FFFAF5; color: #5D4037; "
            "border: 1px solid #E8C9A0; border-radius: 6px; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }")
        layout.addWidget(self._text)

    # ---- Public API ----

    @pyqtSlot(str, str)
    def append_log(self, message: str, level: str = "INFO") -> None:
        category = self._classify(message)
        color = COLORS.get(level.upper(), COLORS["INFO"])
        html = f'<span style="color:{color}">{message}</span>'
        self._entries.append((html, message, category))

        if category in self._visible_categories and self._matches_filter(message):
            self._text.appendHtml(html)
            if self._auto_scroll:
                self._text.moveCursor(QTextCursor.End)

    def clear(self) -> None:
        self._entries.clear()
        self._text.clear()

    def get_entries_for_export(self) -> list[tuple[str, str, str]]:
        """Return all stored log entries for export."""
        return list(self._entries)

    # ---- Filtering ----

    def _classify(self, text: str) -> str:
        """Determine the category of a log message from its content prefix.
        Messages are formatted as 'HH:MM:SS [LEVEL] MESSAGE', so we check
        for category prefixes after the level tag.
        """
        # Strip timestamp+level prefix: "HH:MM:SS [LEVEL] "
        bracket = text.find("] ")
        body = text[bracket + 2:] if bracket != -1 else text
        for key, _, prefixes in CATEGORIES:
            for p in prefixes:
                if body.startswith(p):
                    return key
        return "system"  # catch-all

    def _on_category_toggle(self, key: str, checked: bool) -> None:
        if checked:
            self._visible_categories.add(key)
        else:
            self._visible_categories.discard(key)
        self._rebuild_display()

    def _on_filter(self, text: str) -> None:
        self._rebuild_display()

    def _matches_filter(self, plain: str) -> bool:
        ft = self._filter_edit.text().strip()
        if not ft:
            return True
        return ft.lower() in plain.lower()

    def _rebuild_display(self) -> None:
        self._text.clear()
        for html, plain, cat in self._entries:
            if cat in self._visible_categories and self._matches_filter(plain):
                self._text.appendHtml(html)
        if self._auto_scroll:
            self._text.moveCursor(QTextCursor.End)
