"""Entry point of Open HE Config, the RK keyboard settings app."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .window import ConfigWindow

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Open HE Config")
    icon = QIcon(str(ROOT / "assets" / "icon.png"))
    app.setWindowIcon(icon)
    window = _pick_window(icon)
    window.show()
    sys.exit(app.exec())


def _pick_window(icon):
    """HE boards get the full window; a non-HE RK board (VID 0x258A) gets the classic one."""
    if "--classic" in sys.argv:
        from rk_classic.window import ClassicWindow
        return ClassicWindow(icon)
    from app.device import find
    if not find():
        from rk_classic.link import connected
        if connected():
            from rk_classic.window import ClassicWindow
            return ClassicWindow(icon)
    return ConfigWindow(icon)
