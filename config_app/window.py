"""Main window of M75 Config: sidebar (device, onboard configs, sections), keyboard on top, settings below."""

import threading
import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QLineEdit, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from app import protocol as p
from app.kbconfig import ReadError, read_settings, write_keys
from app.layout import M75_KEYS as KEYS, M75_ROWS
from kbui.widgets import card, label, rule

from kbui import theme
from .advanced import AdvancedPanel
from kbui.keycaps import KeycapView
from kbui.lightfx import LightSim
from .link import Link
from .panels import LightingPanel, PerformancePanel, RemapPanel, SystemPanel

FULL_TRAVEL_UM = 3300
LIVE_INTERVAL = 0.03
PRESSED_UM = 400

# sidebar sections, in the order shown, mapped to panel indexes
SECTIONS = [("Light Setting", 2), ("Performance Setting", 0), ("Custom Key", 1), ("Advanced Key", 3),
            ("System", 4)]


class KeyEater(QObject):
    """Stops key presses from driving the main window (PgDn scrolling, Space clicking buttons, arrows
    changing drop-downs): you press keys here to test them, not to control the app. Number and text
    fields and dialogs still get their keys."""

    TYPES = (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride)

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event):
        if event.type() in self.TYPES and QApplication.activeWindow() is self.window:
            focus = QApplication.focusWidget()
            if isinstance(focus, (QAbstractSpinBox, QLineEdit)) or (
                    focus and isinstance(focus.parent(), QAbstractSpinBox)):
                return False
            return True
        return False


class Bridge(QObject):
    """Results from worker threads, delivered on the UI thread."""
    done = Signal(object, object)   # (callback, result or exception)


class ConfigWindow(QMainWindow):
    def __init__(self, icon):
        super().__init__()
        self.link = Link()
        self.settings = None
        self.current: int | None = None       # key whose values the panels show
        self.selection: set[int] = set()     # all selected keys (Ctrl+click adds)
        self.busy = False
        self.travel = [0] * 126
        self._live_on = True
        self.history: list[int] = []

        self.setWindowTitle("M75 Config")
        self.setWindowIcon(icon)
        self.resize(1480, 920)
        self.setMinimumSize(1280, 760)
        self.setStyleSheet(theme.STYLE)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(18)
        outer.addWidget(self._sidebar())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 4, 0)
        mv.setSpacing(18)
        mv.addWidget(self._board_card(), 0, Qt.AlignHCenter)
        mv.addLayout(self._lower())
        mv.addStretch()
        scroll.setWidget(main)
        outer.addWidget(scroll, 1)

        self.bridge = Bridge()
        self.bridge.done.connect(lambda cb, result: cb(result))
        self.key_eater = KeyEater(self)
        QApplication.instance().installEventFilter(self.key_eater)

        threading.Thread(target=self._live_loop, name="live-travel", daemon=True).start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self._set_enabled(False)
        self._section(1)
        QTimer.singleShot(0, self.read)

    # ---------- building ----------

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(290)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        c, cv = card()
        h = QHBoxLayout()
        self.dev_name = label("M75 Config", "device")
        h.addWidget(self.dev_name)
        h.addSpacing(6)
        self.dev_state = label("● Not connected", "disconnected")
        h.addWidget(self.dev_state)
        h.addStretch()
        cv.addLayout(h)
        self.dev_info = label("", "note")
        self.dev_info.setWordWrap(True)
        cv.addWidget(self.dev_info)
        self.btn_read = QPushButton("Read from keyboard")
        self.btn_read.clicked.connect(lambda: self.read())
        cv.addWidget(self.btn_read)
        v.addWidget(c)

        c, cv = card()
        h = QHBoxLayout()
        h.addWidget(label("Config List", "bigheading"))
        h.addStretch()
        self.cfg_current = label("", "muted")
        h.addWidget(self.cfg_current)
        cv.addLayout(h)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.cfg_group = QButtonGroup(self)
        for i in range(4):
            b = QPushButton(f"  {i + 1}   Config")
            b.setObjectName("config")
            b.setCheckable(True)
            self.cfg_group.addButton(b, i)
            grid.addWidget(b, i // 2, i % 2)
        self.cfg_group.idClicked.connect(self._switch_config)
        cv.addLayout(grid)
        cv.addWidget(label("Four complete setups stored in the keyboard. Switching takes a second.", "note"))
        cv.itemAt(cv.count() - 1).widget().setWordWrap(True)
        v.addWidget(c)

        c, cv = card()
        cv.setSpacing(8)
        self.nav_group = QButtonGroup(self)
        for i, (name, _) in enumerate(SECTIONS):
            b = QPushButton(name)
            b.setObjectName("nav")
            b.setCheckable(True)
            self.nav_group.addButton(b, i)
            cv.addWidget(b)
        self.nav_group.idClicked.connect(self._section)
        v.addWidget(c)
        v.addStretch()
        v.addWidget(label("Settings live in the keyboard and work everywhere, with or without this app. "
                          "Don't edit with the RK web app at the same time: it overwrites keys from its own "
                          "cached copy.", "note"))
        v.itemAt(v.count() - 1).widget().setWordWrap(True)
        return side

    def _board_card(self) -> QWidget:
        c, v = card()
        v.setContentsMargins(22, 18, 22, 18)
        h = QHBoxLayout()
        self.board_title = label("Keys", "heading")
        h.addWidget(self.board_title)
        h.addSpacing(8)
        self.board_hint = label("", "note")
        h.addWidget(self.board_hint)
        h.addStretch()
        for text, fn in (("Select all", self._select_all), ("Clear selection", self._clear_selection)):
            b = QPushButton(text)
            b.setObjectName("link")
            b.clicked.connect(fn)
            h.addWidget(b)
        v.addLayout(h)
        self.board = KeycapView(M75_ROWS)
        self.board.selected.connect(self._clicked)
        self.sim = LightSim(self.board.key_centres())
        self._down: set[int] = set()
        v.addWidget(self.board, 0, Qt.AlignHCenter)
        return c

    def _lower(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(18)
        c, v = card()
        c.setFixedWidth(400)
        self.stack = QStackedWidget()
        self.stack.setFixedWidth(362)  # keeps long notes wrapping instead of widening the panel
        self.panels = [PerformancePanel(self), RemapPanel(self), LightingPanel(self), AdvancedPanel(self),
                       SystemPanel(self)]
        for panel in self.panels:
            self.stack.addWidget(panel)
        v.addWidget(self.stack)
        h.addWidget(c, 0, Qt.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(18)
        self.adv_cards = QWidget()
        self.adv_grid = QGridLayout(self.adv_cards)
        self.adv_grid.setContentsMargins(0, 0, 0, 0)
        self.adv_grid.setSpacing(12)
        right.addWidget(self.adv_cards)

        kc, kv = card()
        kv.addWidget(label("Key Test", "heading"))
        self.test_now = label("Press any key…", "muted")
        self.test_now.setWordWrap(True)
        self.test_now.setMinimumHeight(40)
        kv.addWidget(self.test_now)
        kv.addWidget(rule())
        kv.addWidget(label("Recent", "caps"))
        self.test_recent = label("", "muted")
        self.test_recent.setWordWrap(True)
        kv.addWidget(self.test_recent)
        right.addWidget(kc)
        right.addStretch()
        h.addLayout(right, 1)
        return h

    @property
    def panel(self):
        return self.panels[self.stack.currentIndex()]

    # ---------- helpers for panels ----------

    def run(self, work, callback):
        """Run work(request) on a thread, then callback(result or exception) on the UI thread."""
        if self.busy:
            return
        self.busy = True
        self.refresh()

        def target():
            try:
                result = work(self.link.request)
            except (ReadError, OSError, ValueError) as err:
                result = err
            self.bridge.done.emit(self._finish(callback), result)

        threading.Thread(target=target, name="keyboard-io", daemon=True).start()

    def _finish(self, callback):
        def cb(result):
            self.busy = False
            callback(result)
        return cb

    def ask(self, text: str) -> bool:
        return QMessageBox.question(self, "M75 Config", text) == QMessageBox.Yes

    def primary_key(self) -> dict | None:
        return (self.settings or {}).get("keys", {}).get(self.current)

    def selected_keys(self) -> list[dict]:
        keys = (self.settings or {}).get("keys", {})
        return [keys[s] for s in sorted(self.selection) if s in keys]

    def slot_of(self, key_id: int) -> int:
        return next(s for s, k in self.settings["keys"].items() if k["id"] == key_id)

    def _has_pending(self) -> bool:
        return any(panel.pending or getattr(panel, "color_pending", None) or getattr(panel, "g_pending", None)
                   for panel in self.panels)

    # ---------- keyboard I/O ----------

    def _live_loop(self):
        """Highlights pressed keys from the firmware's own travel readings."""
        while True:
            if not self._live_on or self.busy:
                time.sleep(0.2)
                continue
            if not self.link.connected and not self.link.open():
                time.sleep(1.0)
                continue
            for page in (1, 2):
                vals = self.link.diag(p.DIAG_TRAVEL, page)
                if vals:
                    self.travel[(page - 1) * 63:page * 63] = vals
            time.sleep(LIVE_INTERVAL)

    def read(self, force: bool = False):
        if self.busy and not force:
            return
        if not force and self._has_pending() and not self.ask("Discard changes not written to the keyboard?"):
            return
        for panel in self.panels:
            panel.discard()
        self.busy = True
        self.btn_read.setEnabled(False)
        self.dev_info.setText("Reading settings…")

        def work():
            if not self.link.open():
                result = ReadError("keyboard not found")
            else:
                try:
                    result = read_settings(self.link.request)
                except ReadError as err:
                    result = err
            self.bridge.done.emit(self._read_done, result)

        threading.Thread(target=work, name="read", daemon=True).start()

    def _read_done(self, result):
        self.busy = False
        self.btn_read.setEnabled(True)
        if isinstance(result, Exception):
            self.dev_info.setText(f"Could not read settings: {result}. Close the RK web app and try again.")
            self._set_enabled(False)
            self.refresh()
            return
        self.settings = result
        self.dev_name.setText(result["name"])
        self.dev_info.setText(f"SN: {result['serial']}\n{result['firmware']} · protocol {result['protocol']}")
        self._set_enabled(True)
        self.refresh()

    def _switch_config(self, index: int):
        if not self.settings or index == self.settings["system"].get("config"):
            return
        if self._has_pending() and not self.ask("Switching config discards changes not written yet. Continue?"):
            self.refresh()
            return
        self.dev_info.setText(f"Switching to config {index + 1}…")

        def work(req):
            req(p.req_set_order(p.ORDER_CONFIG, index))
            # the keyboard reloads and stops answering for a moment
            self.link.close()
            for _ in range(20):
                time.sleep(0.5)
                if self.link.open() and self.link.request(p.req_order(p.ORDER_CONFIG)) is not None:
                    return True
                self.link.close()
            raise ReadError("keyboard did not come back after switching config")

        def done(result):
            if isinstance(result, Exception):
                self.dev_info.setText(f"Switch failed: {result}")
                self.refresh()
            else:
                self.read(force=True)

        self.run(work, done)

    # ---------- selection & sections ----------

    def _clicked(self, slot: int):
        if not self.settings:
            return
        if QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            if slot in self.selection and len(self.selection) > 1:
                self.selection.discard(slot)
                if self.current == slot:
                    self.current = next(iter(self.selection))
            else:
                self.selection.add(slot)
                self.current = slot
        else:
            if self.panel.pending and slot != self.current and not isinstance(self.panel, LightingPanel):
                if not self.ask("Discard changes not written to the keyboard?"):
                    return
                self.panel.discard()
            self.selection = {slot}
            self.current = slot
        self.refresh()

    def _select_all(self):
        if self.settings:
            self.selection = {s for s in self.settings["keys"] if s in KEYS}
            if self.current is None:
                self.current = min(self.selection)
            self.refresh()

    def _clear_selection(self):
        self.selection = set()
        self.current = None
        self.refresh()

    def _section(self, nav_index: int):
        index = SECTIONS[nav_index][1]
        if self.stack.currentIndex() != index and self.panel.pending:
            if not self.ask("Discard changes not written to the keyboard?"):
                self.nav_group.button(self._nav_index()).setChecked(True)
                return
            self.panel.discard()
        self.stack.setCurrentIndex(index)
        self.nav_group.button(nav_index).setChecked(True)
        self.refresh()

    def _nav_index(self) -> int:
        return next(i for i, (_, idx) in enumerate(SECTIONS) if idx == self.stack.currentIndex())

    def _set_enabled(self, on: bool):
        self.stack.setEnabled(on)
        for b in (*self.nav_group.buttons(), *self.cfg_group.buttons()):
            b.setEnabled(on)

    # ---------- rendering ----------

    def refresh(self):
        connected = self.link.connected
        self.dev_state.setText("● Connected" if connected else "● Not connected")
        self.dev_state.setObjectName("connected" if connected else "disconnected")
        self.dev_state.style().unpolish(self.dev_state)
        self.dev_state.style().polish(self.dev_state)
        self.btn_read.setEnabled(not self.busy)
        for b in self.cfg_group.buttons():
            b.setEnabled(bool(self.settings) and not self.busy)
        if not self.settings:
            return
        cfg = self.settings["system"].get("config", 0)
        self.cfg_current.setText(f"Current: {cfg + 1}")
        for i, b in enumerate(self.cfg_group.buttons()):
            b.setChecked(i == cfg)
        panel = self.panel
        self.board_title.setText(panel.title)
        self.board_hint.setText(panel.hint)
        self.board.set_targets({s: t for s, t in panel.tags().items() if s in KEYS})
        self.board.set_swatches(panel.swatches())
        self.board.set_current(self.current)
        self.board.set_selection(self.selection)
        panel.render()
        self._render_adv_cards()

    def _render_adv_cards(self):
        while self.adv_grid.count():
            w = self.adv_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        show = isinstance(self.panel, AdvancedPanel)
        self.adv_cards.setVisible(show)
        if not show:
            return
        keys = self.settings["keys"]
        n = 0
        for slot, k in sorted(keys.items()):
            kind = k.get("mode", {}).get("advanced", "none")
            if kind == "none" or slot not in KEYS:
                continue
            c, v = card()
            c.setFixedWidth(210)
            h = QHBoxLayout()
            h.addWidget(label(KEYS[slot]["label"], "heading"))
            h.addWidget(label(kind, "badge"))
            h.addStretch()
            v.addLayout(h)
            detail = ""
            if kind == "SOCD" and k.get("socd"):
                s = k["socd"]
                a = KEYS.get(self.slot_of(s["key1"]), {}).get("label", "?")
                b = KEYS.get(self.slot_of(s["key2"]), {}).get("label", "?")
                detail = f"{a}  ⇄  {b}"
            v.addWidget(label(detail or p.keycode_name(k["id"]), "muted"))
            row = QHBoxLayout()
            edit = QPushButton("Edit")
            edit.clicked.connect(lambda _=False, s=slot: self._clicked(s))
            delete = QPushButton("Delete")
            delete.setObjectName("danger")
            delete.clicked.connect(lambda _=False, key=k: self._delete_advanced(key))
            delete.setEnabled(not self.busy)
            row.addWidget(edit)
            row.addWidget(delete)
            v.addLayout(row)
            self.adv_grid.addWidget(c, n // 3, n % 3)
            n += 1
        if n == 0:
            c, v = card()
            v.addWidget(label("No advanced keys yet. Click a key and pick a function.", "muted"))
            self.adv_grid.addWidget(c, 0, 0)

    def _delete_advanced(self, key: dict):
        label_ = KEYS[self.slot_of(key["id"])]["label"]
        if not self.ask(f"Remove the {key['mode']['advanced']} function from {label_}?"):
            return

        def done(result):
            if isinstance(result, Exception):
                self.dev_info.setText(f"Delete failed: {result}")
            else:
                for k in result:
                    self.settings["keys"][self.slot_of(k["id"])] = k
                self.panels[3].discard()
            self.refresh()

        self.run(lambda req: write_keys(req, [key], {"clear_advanced": True}), done)

    def _tick(self):
        now = time.monotonic()
        down = {s for s in KEYS if self.travel[s] > PRESSED_UM}
        for s in down - self._down:
            self.sim.press(s, now)
            self.history = ([s] + [x for x in self.history if x != s])[:14]
        if down != self._down:
            self.test_now.setText("   ".join(KEYS[s]["label"] for s in sorted(down)) or "Press any key…")
            self.test_recent.setText("   ".join(KEYS[s]["label"] for s in self.history))
        self._down = down
        lighting = self.settings and isinstance(self.panel, LightingPanel)
        if lighting:
            panel = self.panel
            light = panel.light()
            self.board.set_leds(self.sim.frame(now, panel.style_for(light["mode"]), light, panel.preview_colors()))
        elif self.board.leds:
            self.board.set_leds({})
        depth = {} if lighting else {s: min(1.0, self.travel[s] / FULL_TRAVEL_UM) for s in KEYS if self.travel[s] > 10}
        self.board.set_depth(depth)
        if self.settings and isinstance(self.panel, PerformancePanel):
            self.panel.tick(self.travel)
        connected = self.link.connected
        if connected != getattr(self, "_connected", None):
            self._connected = connected
            self.refresh()

    # ---------- window ----------

    def showEvent(self, e):
        self._live_on = True
        self.timer.start(33)
        super().showEvent(e)

    def hideEvent(self, e):
        self._live_on = False
        self.timer.stop()
        super().hideEvent(e)

    def closeEvent(self, e):
        if self.panels[4].calibrating and not self.ask("Calibration is still running. Quit anyway? "
                                                         "Finish calibration first if you can."):
            e.ignore()
            return
        if self._has_pending() and not self.ask("Quit without writing your changes to the keyboard?"):
            e.ignore()
            return
        self._live_on = False
        self.link.close()
        e.accept()
