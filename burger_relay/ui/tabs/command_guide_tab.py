"""Built-in hard-match command rules — read-only reference."""
from __future__ import annotations
import webbrowser
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QPushButton, QLabel, QTextEdit)
from ...core.command_mappings import (
    BURGER_TRIGGERS, INGREDIENT_MAP, _EXCLUDE_PREFIXES,
    COMPLAINT_MAP, INTERACT_MAP,
)

_GAME_CMD_URL = "https://heynaugames.com/burgie-commands"

_TABLE_CSS = (
    "border-collapse:collapse; width:100%; margin-bottom:10px; font-size:12px;"
)
_TH_CSS = (
    "background:#FFE0C0; color:#5D4037; padding:4px 8px; text-align:left;"
    "font-weight:bold; border:1px solid #E8C9A0;"
)
_TD_CSS = (
    "padding:3px 8px; border:1px solid #E8C9A0; color:#5D4037;"
)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    h = "".join(f'<th style="{_TH_CSS}">{hd}</th>' for hd in headers)
    r = "".join(
        "<tr>" + "".join(f'<td style="{_TD_CSS}">{c}</td>' for c in row) + "</tr>"
        for row in rows
    )
    return f'<table style="{_TABLE_CSS}"><tr>{h}</tr>{r}</table>'


def _build_html() -> str:
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    p = ['<div style="font-size:12px;">']

    p.append('<h4 style="color:#D08040; margin:6px 0 3px;">点单触发词</h4>')
    p.append(_table(
        ["中文关键词", "自动转换为"],
        [["、".join(esc(t) for t in BURGER_TRIGGERS), "!Burgie"]]
    ))

    prefixes = [x for x in _EXCLUDE_PREFIXES if x not in ("without", "no")]
    p.append('<h4 style="color:#D08040; margin:6px 0 3px;">排除前缀</h4>')
    p.append(_table(
        ["中文关键词", "效果"],
        [["、".join(esc(x) for x in prefixes), "后跟食材自动加 without"]]
    ))

    p.append('<h4 style="color:#D08040; margin:6px 0 3px;">食材映射（中文 → 英文）</h4>')
    categories = [
        ("熟度", ["raw", "medium", "well done"]),
        ("素食", ["vegan"]),
        ("配料", ["meat", "onion", "grilled onion", "tomato", "lettuce",
                   "cheese", "extra cheese"]),
        ("酱料", ["ketchup", "mustard", "mayo", "fav sauce", "without sauce"]),
        ("饮料", ["cola", "lemonade", "orange soda"]),
        ("特殊", ["smash"]),
    ]
    seen: set[str] = set()
    rows = []
    for cat, vals in categories:
        for v in vals:
            if v in seen:
                continue
            seen.add(v)
            cns = [ch for ch, en in INGREDIENT_MAP.items() if en == v]
            rows.append([f"<i>{cat}</i>", "、".join(esc(c) for c in cns), esc(v)])
    p.append(_table(["分类", "中文关键词", "英文配料"], rows))

    p.append('<h4 style="color:#D08040; margin:6px 0 3px;">举报指令</h4>')
    c_by_cmd: dict[str, list[str]] = {}
    for kw, cmd in COMPLAINT_MAP.items():
        c_by_cmd.setdefault(cmd, []).append(kw)
    p.append(_table(
        ["输出指令", "触发关键词"],
        [[esc(c), "、".join(esc(k) for k in ks)] for c, ks in c_by_cmd.items()]
    ))

    p.append('<h4 style="color:#D08040; margin:6px 0 3px;">交互指令</h4>')
    i_by_cmd: dict[str, list[str]] = {}
    for kw, cmd in INTERACT_MAP.items():
        i_by_cmd.setdefault(cmd, []).append(kw)
    p.append(_table(
        ["输出指令", "触发关键词"],
        [[esc(c), "、".join(esc(k) for k in ks)] for c, ks in i_by_cmd.items()]
    ))

    p.append("</div>")
    return "".join(p)


class CommandGuideTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        desc = QLabel(
            "观众弹幕包含以下中文关键词时，直接转换为游戏指令，无需等待大模型。<br>"
            "格式：用空格分隔关键词，如「点单 全熟 芝士 可乐」"
            "→ <b>!Burgie + well done + cheese + cola</b>")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #5D4037; font-size: 12px; padding: 4px;")
        layout.addWidget(desc)

        self._display = QTextEdit()
        self._display.setReadOnly(True)
        self._display.setHtml(_build_html())
        self._display.setStyleSheet(
            "QTextEdit { background: #FFFAF5; color: #5D4037; border: 1px solid #E8C9A0; }")
        layout.addWidget(self._display)

        link_row = QHBoxLayout()
        btn = QPushButton("📖 查看游戏官方指令指南")
        btn.setStyleSheet(
            "QPushButton { color: #D08040; text-decoration: underline;"
            "border: none; background: transparent; padding: 2px; }")
        btn.clicked.connect(lambda: webbrowser.open(_GAME_CMD_URL))
        link_row.addWidget(btn)
        link_row.addStretch()
        layout.addLayout(link_row)
