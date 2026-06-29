"""Burger Relay - Main entry point."""
from __future__ import annotations
import ctypes
import os
import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from burger_relay.ui.main_window import MainWindow, _find_logo


def main() -> None:
    # Tell Windows this is a standalone app (not python.exe)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "BurgerRelay.BurgerRelay")
    except Exception:
        pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Burger Relay")
    app.setOrganizationName("BurgerRelay")

    # Set app icon for taskbar
    logo = _find_logo()
    if logo:
        app.setWindowIcon(QIcon(logo))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
