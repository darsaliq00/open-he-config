"""Entry point of Open HE Config, the RK keyboard settings app.

One copy runs at a time; starting it again shows the running window. Closing the window can keep
the app in the tray, where it only remaps the volume knob (see app/knob.py) and reads nothing from
the keyboard. `--tray` starts it hidden (used by "Start with Windows").
"""

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon, QVBoxLayout

from app.knob import KnobRemapper

from . import appsettings
from .knobpage import KnobPage

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
INSTANCE = "OpenHEConfig.SingleInstance"


class CloseToTray(QObject):
    """Turns the window's close button into "hide to tray" while the tray option is on."""

    def __init__(self, window, settings):
        super().__init__(window)
        self.window, self.settings = window, settings
        self.quitting = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Close and not self.quitting and self.settings["tray_on_close"]:
            event.ignore()
            self.window.hide()
            return True
        return False


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, INSTANCE)   # the installer checks this name
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenHEConfig.App")

    app = QApplication(sys.argv)
    app.setApplicationName("Open HE Config")
    app.setQuitOnLastWindowClosed(False)

    # second launch: wake the running copy (two copies polling the keyboard confuse each other)
    probe = QLocalSocket()
    probe.connectToServer(INSTANCE)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.waitForBytesWritten(300)
        return
    QLocalServer.removeServer(INSTANCE)
    server = QLocalServer()
    server.listen(INSTANCE)

    icon = QIcon(str(ROOT / "assets" / "icon.png"))
    app.setWindowIcon(icon)
    settings = appsettings.load()
    remapper = KnobRemapper()
    remapper.configure(settings["knob_turn"], settings["knob_press"])

    holder = {"window": None, "closer": None}

    def window():
        """The settings window is built on first use, so a copy started in the tray stays small."""
        if holder["window"] is None:
            from .window import ConfigWindow   # imported late: it reads the keyboard's layout
            w = _pick_window(icon)
            if isinstance(w, ConfigWindow):
                w.attach_knob_page(KnobPage(remapper, settings))
            holder["closer"] = CloseToTray(w, settings)
            w.installEventFilter(holder["closer"])
            holder["window"] = w
        return holder["window"]

    def show_window():
        w = window()
        w.showNormal()
        w.raise_()
        w.activateWindow()

    def knob_dialog():
        dlg = QDialog(holder["window"])
        dlg.setWindowTitle("Knob")
        dlg.setWindowIcon(icon)
        from kbui import theme
        dlg.setStyleSheet(theme.STYLE)
        QVBoxLayout(dlg).addWidget(KnobPage(remapper, settings))
        dlg.exec()

    def quit_app():
        w, closer = holder["window"], holder["closer"]
        if w is not None:
            closer.quitting = True
            if not w.close():   # the window may still ask about unsaved changes
                closer.quitting = False
                return
        remapper.stop()
        tray.hide()
        app.quit()

    tray = QSystemTrayIcon(icon)
    tray.setToolTip("Open HE Config")
    menu = QMenu()
    for text, fn in (("Open", show_window), ("Knob…", knob_dialog), (None, None), ("Quit", quit_app)):
        if text is None:
            menu.addSeparator()
            continue
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show_window() if reason in (
        QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show()
    server.newConnection.connect(lambda: (server.nextPendingConnection(), show_window()))

    if "--tray" not in sys.argv:
        show_window()
    code = app.exec()
    remapper.stop()
    sys.exit(code)


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
    from .window import ConfigWindow
    return ConfigWindow(icon)
