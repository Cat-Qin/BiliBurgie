"""Main application window — warm cream theme with custom title bar."""
from __future__ import annotations
import logging
import os
import sys
from typing import Optional
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QSystemTrayIcon, QMenu, QAction, QFileDialog,
    QSplitter, QLabel, QStyle)
from PyQt5.QtCore import Qt, QPoint, pyqtSlot, QTimer
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QMouseEvent, QRegion, QPainterPath, QIcon

from .widgets.log_widget import LogWidget
from .widgets.status_bar import AppStatusBar
from .tabs.platform_tab import PlatformTab
from .tabs.llm_tab import LLMTab
from .tabs.auth_tab import AuthTab
from .tabs.stats_tab import StatsTab
from .tabs.command_guide_tab import CommandGuideTab
from .async_worker import AsyncWorker
from ..core.event_processor import EventProcessor
from ..utils.logger import setup_logging, get_logger
from ..utils.config_loader import load_config, save_config

logger = logging.getLogger("BurgerRelay.main")

_CORNER_RADIUS = 14
_BORDER_COLOR = "#C8A882"
_BORDER_WIDTH = 2


def _find_logo() -> str:
    """Find logo.png next to the exe or in the source directory."""
    # PyInstaller bundle: next to the exe
    if getattr(sys, "frozen", False):
        path = os.path.join(os.path.dirname(sys.executable), "logo.png")
        if os.path.exists(path):
            return path
    # Development: in the project root
    path = os.path.join(os.path.dirname(__file__), "..", "..", "logo.png")
    path = os.path.abspath(path)
    if os.path.exists(path):
        return path
    return ""


class _TitleBar(QWidget):
    """Custom frameless title bar with drag, minimize, and close."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 5, 8, 5)

        icon = QLabel("🍔")
        icon.setStyleSheet("font-size:18px; background:transparent; border:none;")
        layout.addWidget(icon)

        title = QLabel("BiliBurgie")
        title.setStyleSheet(
            "font-size:14px; font-weight:bold; color:#5D4037;"
            "background:transparent; border:none;")
        layout.addWidget(title)
        layout.addStretch()

        # Always-visible minimize button
        btn_min = QPushButton("─")
        btn_min.setFixedSize(34, 28)
        btn_min.setToolTip("最小化")
        btn_min.setStyleSheet(_title_btn_style("#E8C9A0", "#8D6E63"))
        btn_min.clicked.connect(parent.showMinimized)
        layout.addWidget(btn_min)

        # Always-visible close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(34, 28)
        btn_close.setToolTip("关闭")
        btn_close.setStyleSheet(_title_btn_style("#FFCCBB", "#D32F2F"))
        btn_close.clicked.connect(parent.close)
        layout.addWidget(btn_close)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self._parent.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self._parent.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()


def _title_btn_style(bg: str, fg: str) -> str:
    return (
        f"QPushButton {{"
        f"  background: {bg}; color: {fg}; border: 1px solid #D0B090;"
        f"  border-radius: 6px; font-size: 16px; font-weight: bold;"
        f"  padding: 0;"
        f"}}"
        f"QPushButton:hover {{ background: {fg}; color: #FFF; border-color: {fg}; }}"
    )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    _border_width = 4  # px from edge where resize cursor activates

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BiliBurgie")
        self.resize(1020, 900)
        self._logo_path = _find_logo()
        if self._logo_path:
            self.setWindowIcon(QIcon(self._logo_path))
        self.setMinimumSize(720, 500)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._processor = EventProcessor()
        self._worker: Optional[AsyncWorker] = None
        self._running = False
        self._quitting = False

        self._setup_ui()
        self._apply_rounded_mask()
        self._connect_signals()
        self._setup_tray()
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_stats_display)
        self._stats_timer.start(2000)

    # ------------------------------------------------------------------
    # Rounded corners + resize
    # ------------------------------------------------------------------

    def _apply_rounded_mask(self) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                            _CORNER_RADIUS, _CORNER_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_rounded_mask()

    def nativeEvent(self, event_type, message) -> tuple[bool, int]:
        """Handle WM_NCHITTEST for border-based resize."""
        import ctypes
        import ctypes.wintypes as wtypes

        if event_type == "windows_generic_MSG":
            msg = ctypes.cast(ctypes.c_void_p(int(message)), ctypes.POINTER(wtypes.MSG))
            if msg.contents.message == 0x0084:  # WM_NCHITTEST
                x = msg.contents.pt.x
                y = msg.contents.pt.y
                geo = self.frameGeometry()
                left = x < geo.left() + self._border_width
                right = x > geo.right() - self._border_width
                top = y < geo.top() + self._border_width
                bottom = y > geo.bottom() - self._border_width

                if top and left:
                    return True, 13  # HTTOPLEFT
                if top and right:
                    return True, 14  # HTTOPRIGHT
                if bottom and left:
                    return True, 16  # HTBOTTOMLEFT
                if bottom and right:
                    return True, 17  # HTBOTTOMRIGHT
                if left:
                    return True, 10  # HTLEFT
                if right:
                    return True, 11  # HTRIGHT
                if top:
                    return True, 12  # HTTOP
                if bottom:
                    return True, 15  # HTBOTTOM
        return False, 0

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Outer wrapper — holds the border + rounded corners
        outer = QWidget()
        outer.setObjectName("outer")
        outer.setStyleSheet(
            f"QWidget#outer {{"
            f"  background: #FFF5EE;"
            f"  border: {_BORDER_WIDTH}px solid {_BORDER_COLOR};"
            f"  border-radius: {_CORNER_RADIUS}px;"
            f"}}"
        )
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Title bar
        self._titlebar = _TitleBar(self)
        outer_layout.addWidget(self._titlebar)

        # Content
        central = QWidget()
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)

        self._log = LogWidget()

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self._btn_start = QPushButton("▶ 启动")
        self._btn_start.clicked.connect(self._on_start)
        tb.addWidget(self._btn_start)
        self._btn_stop = QPushButton("⏹ 停止")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        tb.addWidget(self._btn_stop)
        btn_clear = QPushButton("🗑 清空日志")
        btn_clear.clicked.connect(self._log.clear)
        tb.addWidget(btn_clear)
        btn_save = QPushButton("💾 保存配置")
        btn_save.clicked.connect(self._on_save)
        tb.addWidget(btn_save)
        btn_export = QPushButton("📋 导出日志")
        btn_export.clicked.connect(self._on_export_log)
        tb.addWidget(btn_export)
        tb.addStretch()
        layout.addLayout(tb)

        splitter = QSplitter(Qt.Vertical)
        self._tabs = QTabWidget()
        self._platform_tab = PlatformTab()
        self._llm_tab = LLMTab()
        self._auth_tab = AuthTab()
        self._guide_tab = CommandGuideTab()
        self._stats_tab = StatsTab()
        self._tabs.addTab(self._platform_tab, "🍔 直播平台")
        self._tabs.addTab(self._llm_tab, "🤖 大模型")
        self._tabs.addTab(self._auth_tab, "🔐 权限")
        self._tabs.addTab(self._guide_tab, "📖 指令指南")
        self._tabs.addTab(self._stats_tab, "📊 统计")
        splitter.addWidget(self._tabs)
        splitter.addWidget(self._log)
        splitter.setSizes([320, 360])
        layout.addWidget(splitter)

        self._status_bar = AppStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        layout.addWidget(self._status_bar)

        outer_layout.addWidget(central)
        self.setCentralWidget(outer)
        self.setStyleSheet(_global_theme())

    def _connect_signals(self) -> None:
        log_signal = setup_logging()
        log_signal.log_message.connect(self._log.append_log)
        self._processor.stats_updated.connect(self._stats_tab.update_stats)
        self._processor.whitelist_updated.connect(self._auth_tab.update_whitelist)

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------

    def _setup_tray(self) -> None:
        if self._logo_path:
            icon = QIcon(self._logo_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu()
        menu.addAction("显示主窗口", self.show)
        menu.addAction("退出", self._on_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self.show() if r == QSystemTrayIcon.DoubleClick else None)
        self._tray.show()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        self._on_save()
        self._processor.configure()
        self._worker = AsyncWorker(self._processor)
        self._worker.irc_status.connect(self._status_bar.set_irc)
        self._worker.bilibili_status.connect(self._status_bar.set_bilibili)
        self._worker.bilibili_status.connect(self._platform_tab.set_bilibili_status)
        self._worker.llm_status.connect(self._status_bar.set_llm)
        self._worker.started.connect(lambda: self._set_running(True))
        self._worker.finished.connect(lambda: self._set_running(False))
        self._worker.start()
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        logger.info("All services starting...")

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.stop_worker()
            self._worker = None
        self._set_running(False)
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status_bar.set_irc(False)
        self._status_bar.set_bilibili(False)
        self._status_bar.set_llm(None)
        self._status_bar.set_stats(0, 0)
        self._platform_tab.set_bilibili_status(False)
        logger.info("All services stopped")

    def _set_running(self, running: bool) -> None:
        self._running = running

    def _on_save(self) -> None:
        self._platform_tab.save_config()
        self._llm_tab.save_config()
        self._auth_tab.save_config()
        save_config()
        logger.info("Configuration saved")

    def _on_export_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "relay_export.txt", "Text (*.txt)")
        if not path:
            return
        try:
            entries = self._log.get_entries_for_export()
            with open(path, "w", encoding="utf-8") as f:
                for _, plain, _ in entries:
                    f.write(plain + "\n")
            logger.info(f"Log exported to {path} ({len(entries)} lines)")
        except Exception as e:
            logger.error(f"Log export failed: {e}")

    def _update_stats_display(self) -> None:
        if self._running:
            s = self._processor.stats
            self._status_bar.set_stats(s.total_danmaku, s.total_orders)

    def _on_quit(self) -> None:
        self._on_save()
        self._on_stop()
        self._tray.hide()
        self._quitting = True
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
        else:
            event.ignore()
            self.hide()
            self._tray.showMessage("BiliBurgie", "程序已最小化到系统托盘",
                                   QSystemTrayIcon.Information, 2000)


# ---------------------------------------------------------------------------
# Global theme
# ---------------------------------------------------------------------------

def _global_theme() -> str:
    return """
    QWidget {
        color: #5D4037;
        font-size: 13px;
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    QWidget#central {
        background: #FFF5EE;
    }

    /* ---- Title bar ---- */
    _TitleBar {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #FFE0C0, stop:1 #FFD0A8);
    }

    /* ---- Tabs ---- */
    QTabWidget::pane {
        border: 1px solid #E0C8A8;
        border-radius: 8px;
        background: #FFFAF5;
    }
    QTabBar::tab {
        background: #FFE8D6;
        color: #8D6E63;
        padding: 7px 18px;
        margin-right: 3px;
        border: 1px solid #E0C8A8;
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-weight: bold;
    }
    QTabBar::tab:selected {
        background: #FFFAF5;
        color: #5D4037;
        border-bottom: 2px solid #FF8C42;
    }
    QTabBar::tab:hover:!selected {
        background: #FFF0E5;
    }

    /* ---- Group boxes ---- */
    QGroupBox {
        border: 1px solid #E0C8A8;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 14px;
        color: #5D4037;
        font-weight: bold;
        background: #FFFAF5;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 8px;
    }

    /* ---- Buttons ---- */
    QPushButton {
        background: #FFE0C0;
        color: #5D4037;
        border: 1px solid #E0C8A8;
        border-radius: 8px;
        padding: 6px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #FFD0A0;
        border-color: #FF8C42;
    }
    QPushButton:pressed {
        background: #FFC080;
    }
    QPushButton:disabled {
        background: #F5E6D8;
        color: #BCAAA4;
        border-color: #E0D0C0;
    }

    /* ---- Inputs ---- */
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
        background: #FFFAF5;
        color: #5D4037;
        border: 1px solid #E0C8A8;
        border-radius: 6px;
        padding: 5px 8px;
        selection-background-color: #FFD0A0;
    }
    QSpinBox:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
        border-color: #FF8C42;
    }

    /* Spinbox buttons */
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        border: none;
        border-left: 1px solid #E0C8A8;
        border-bottom: 1px solid #E0C8A8;
        border-top-right-radius: 5px;
        background: #FFE8D6;
        width: 22px;
    }
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        border: none;
        border-left: 1px solid #E0C8A8;
        border-bottom-right-radius: 5px;
        background: #FFE8D6;
        width: 22px;
    }
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
        background: #FFD0A0;
    }
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
        image: url(data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'><path fill='%235D4037' d='M6 0L0 8h12z'/></svg>);
        width: 10px;
        height: 6px;
    }
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
        image: url(data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'><path fill='%235D4037' d='M0 0h12L6 8z'/></svg>);
        width: 10px;
        height: 6px;
    }

    /* Combo box */
    QComboBox::drop-down {
        border: none;
        padding-right: 6px;
    }
    QComboBox QAbstractItemView {
        background: #FFFAF5;
        border: 1px solid #E0C8A8;
        selection-background-color: #FFE0C0;
    }

    /* ---- Checkboxes ---- */
    QCheckBox {
        color: #5D4037;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border: 2px solid #C8A882;
        border-radius: 4px;
        background: #FFFAF5;
    }
    QCheckBox::indicator:checked {
        background: #FF8C42;
        border-color: #E07030;
        image: url(data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='white' d='M6 11L2.5 7.5 3.9 6.1 6 8.2 12.1 2.1 13.5 3.5z'/></svg>);
    }

    /* ---- Tables ---- */
    QTableWidget {
        background: #FFFAF5;
        color: #5D4037;
        gridline-color: #F0D8C0;
        border: 1px solid #E0C8A8;
        border-radius: 6px;
    }
    QTableWidget::item {
        padding: 4px 8px;
    }
    QHeaderView::section {
        background: #FFE8D6;
        color: #5D4037;
        border: 1px solid #E0C8A8;
        padding: 5px 8px;
        font-weight: bold;
    }

    /* ---- Slider ---- */
    QSlider::groove:horizontal {
        background: #F0D8C0;
        height: 6px;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #FF8C42;
        width: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }

    /* ---- Status bar ---- */
    QStatusBar {
        background: #FFE8D6;
        color: #8D6E63;
        border-top: 1px solid #E0C8A8;
    }

    /* ---- Splitter ---- */
    QSplitter::handle {
        background: #E0C8A8;
        margin: 0 2px;
    }
    QSplitter::handle:hover {
        background: #FF8C42;
    }

    /* ---- Scroll bars ---- */
    QScrollBar:vertical {
        background: #FFF5EE;
        width: 10px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background: #E0C8A8;
        border-radius: 5px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #D0B098;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }

    /* ---- Tooltips ---- */
    QToolTip {
        background: #FFF8E1;
        color: #5D4037;
        border: 1px solid #E0C8A8;
        border-radius: 6px;
        padding: 4px 8px;
    }
    """
