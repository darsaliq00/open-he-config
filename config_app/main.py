"""Entry point of M75 Config, the keyboard settings app (separate from Analog Drive)."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .window import ConfigWindow

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("M75 Config")
    icon = QIcon(str(ROOT / "assets" / "icon.png"))
    app.setWindowIcon(icon)
    window = ConfigWindow(icon)
    window.show()
    sys.exit(app.exec())
