"""Performance Setting page, laid out like RK's web driver.

Tabs under the keyboard: Normal Travel Setting, Rapid Trigger Setting, Advanced Setting,
Keyboard Adjusting and Select Axis; the Travel Test card and the quick-select buttons sit on
the right. Click keys to check or uncheck them; every change applies to the checked keys as soon
as you let go of a slider, and is read back from the keyboard to confirm it.
"""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from app import axes as axis_table
from app import protocol as p
from app.kbconfig import write_global, write_keys, write_order, write_polling
from app.layout import RK_KEYS as KEYS
from kbui.travel import Switch, TravelTestCard
from kbui.travelslider import TravelSlider
from kbui.widgets import card, label, restyle

from .panels import Panel

TABS = ["Normal Travel Setting", "Rapid Trigger Setting", "Advanced Setting", "Keyboard Adjusting",
        "Select Axis"]
WASD = {0x1A, 0x04, 0x16, 0x07}
NUMBERS = set(range(0x1E, 0x28))
LETTERS = set(range(0x04, 0x1E))
AXIS_COLOURS = ["#2a9d8f", "#e76f51", "#457b9d", "#e9c46a", "#8d6cab", "#f4a261", "#6c757d", "#43aa8b"]


class PerformancePage(Panel):
    title = "Performance"
    hint = "Click keys to check them; changes apply to the checked keys."
    toggle_select = True

    def __init__(self, win):
        super().__init__(win)
        self.lay.setSpacing(14)

        bar = QHBoxLayout()
        bar.addStretch()
        self.tab_group = QButtonGroup(self)
        for i, name in enumerate(TABS):
            b = QPushButton(name.upper())
            b.setObjectName("tab")
            b.setCheckable(True)
            self.tab_group.addButton(b, i)
            bar.addWidget(b)
        bar.addStretch()
        self.tab_group.idClicked.connect(self._tab)
        self.lay.addLayout(bar)

        body = QHBoxLayout()
        body.setSpacing(18)
        c, cv = card()
        c.setMinimumWidth(460)
        self.stack = QStackedWidget()
        for build in (self._normal, self._rapid, self._advanced, self._adjusting, self._axis):
            self.stack.addWidget(build())
        cv.addWidget(self.stack)
        self.status = label("", "note")
        self.status.setWordWrap(True)
        cv.addWidget(self.status)
        body.addWidget(c, 1, Qt.AlignTop)

        self.travel_card = TravelTestCard()
        body.addWidget(self.travel_card, 0, Qt.AlignTop)

        quick = QVBoxLayout()
        quick.setSpacing(10)
        for text, fn in (("SELECT ALL", self._select_all), ("WASD", lambda: self._select_ids(WASD)),
                         ("NUMBER KEY", lambda: self._select_ids(NUMBERS)),
                         ("LETTER KEY", lambda: self._select_ids(LETTERS)), ("UNCHECK", self._uncheck),
                         ("RESET TRAVEL", self._reset_travel)):
            b = QPushButton(text)
            b.setObjectName("quick")
            b.clicked.connect(fn)
            quick.addWidget(b)
        quick.addStretch()
        body.addLayout(quick)
        self.lay.addLayout(body)
        self.lay.addStretch()
        self.tab_group.button(0).setChecked(True)

    # ---------- tabs ----------

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(16)
        return w, v

    def _normal(self):
        w, v = self._page()
        self.global_travel = TravelSlider(
            "Global Travel", "Set the global trigger travel. Keys without their own travel (and not in "
            "rapid trigger) use it; it is not shown on the keys.")
        self.global_travel.committed.connect(self._write_global)
        v.addWidget(self.global_travel)
        self.single_travel = TravelSlider(
            "Single Key Travel  (Check Key)", "Set the trigger travel of the checked keys. The green value "
            "in the top-left corner of a key shows it.")
        self.single_travel.committed.connect(self._write_single)
        v.addWidget(self.single_travel)
        v.addStretch()
        return w

    def _rapid(self):
        w, v = self._page()
        h = QHBoxLayout()
        h.addWidget(label("Rapid Trigger", "heading"))
        h.addStretch()
        self.rt_switch = Switch()
        self.rt_switch.clicked.connect(self._write_rt_switch)
        h.addWidget(self.rt_switch)
        v.addLayout(h)
        v.addWidget(label("Turns rapid trigger on or off for the checked keys.", "muted"))
        self.rt_first = TravelSlider("First trigger stroke (checked keys)",
                                     "Where the key first fires, shown green in the top-left corner.")
        self.rt_first.committed.connect(lambda val: self._write_keys({"actuation": val}, "First trigger stroke"))
        self.rt_press = TravelSlider("Dynamic Trigger Travel (Press)",
                                     "How far the key must go down again to re-fire, shown blue in the "
                                     "bottom-left corner.", 0.01, 2.0)
        self.rt_press.committed.connect(lambda val: self._write_keys({"rt_press": val}, "Press travel"))
        self.rt_release = TravelSlider("Dynamic Reset Travel (Release)",
                                       "How far the key must come up to release, shown orange in the "
                                       "bottom-right corner.", 0.01, 2.0)
        self.rt_release.committed.connect(lambda val: self._write_keys({"rt_release": val}, "Release travel"))
        for s in (self.rt_first, self.rt_press, self.rt_release):
            v.addWidget(s)
        v.addStretch()
        return w

    def _advanced(self):
        w, v = self._page()
        v.addWidget(label("Dead Band Setting", "heading"))
        t = label("Dead zones are per key. To avoid false or broken contact, at least 0.2 mm is advised.", "muted")
        t.setWordWrap(True)
        v.addWidget(t)
        h = QHBoxLayout()
        opt = QPushButton("Apply 0.2 mm to the checked keys")
        opt.setObjectName("link")
        opt.clicked.connect(lambda: self._write_keys({"dead_press": 0.2, "dead_release": 0.2}, "Dead zones"))
        h.addWidget(opt)
        h.addStretch()
        v.addLayout(h)
        self.dead_press = TravelSlider("", "Press (top dead zone): travel ignored at the top.", 0.0, 1.0)
        self.dead_press.committed.connect(lambda val: self._write_keys({"dead_press": val}, "Top dead zone"))
        self.dead_release = TravelSlider("", "Release (bottom dead zone): travel ignored at the bottom.", 0.0, 1.0)
        self.dead_release.committed.connect(lambda val: self._write_keys({"dead_release": val}, "Bottom dead zone"))
        v.addWidget(self.dead_press)
        v.addWidget(self.dead_release)
        line = QFrame()
        line.setObjectName("rule")
        v.addWidget(line)
        h = QHBoxLayout()
        h.addWidget(label("Polling Rate", "heading"))
        h.addStretch()
        self.polling = QComboBox()
        self.polling.activated.connect(self._set_polling)
        h.addWidget(self.polling)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(label("Top dead zone switch", "heading"))
        h.addStretch()
        self.top_dead = Switch()
        self.top_dead.clicked.connect(self._set_top_dead)
        h.addWidget(self.top_dead)
        v.addLayout(h)
        v.addStretch()
        return w

    def _adjusting(self):
        w, v = self._page()
        v.addWidget(label("Adjusting Instruction", "heading"))
        for text in ("Calibrate for a better experience.",
                     "Click Start Adjusting, then press every key all the way down and hold it for 1 to 2 "
                     "seconds while rocking it slightly. Pressing and lifting quickly gives inaccurate "
                     "results. Click Save Adjusting when every key is done.",
                     "Turn on Travel Test on the right to watch the real-time travel."):
            t = label(text, "muted")
            t.setWordWrap(True)
            v.addWidget(t)
        h = QHBoxLayout()
        self.btn_start = QPushButton("Start Adjusting")
        self.btn_start.setObjectName("save")
        self.btn_start.setProperty("dirty", True)
        self.btn_start.clicked.connect(self._cal_start)
        self.btn_save = QPushButton("Save Adjusting")
        self.btn_save.clicked.connect(self._cal_save)
        h.addWidget(self.btn_start)
        h.addWidget(self.btn_save)
        h.addStretch()
        v.addLayout(h)
        v.addStretch()
        self.calibrating = False
        return w

    def _axis(self):
        w, v = self._page()
        h = QHBoxLayout()
        h.setSpacing(24)
        col = QVBoxLayout()
        col.addWidget(label("Custom Axis", "heading"))
        col.addWidget(label("Pick the switch fitted in the checked keys.", "muted"))
        self.axis_box = QVBoxLayout()
        self.axis_box.setSpacing(6)
        col.addLayout(self.axis_box)
        col.addStretch()
        h.addLayout(col, 1)
        info = QVBoxLayout()
        info.addWidget(label("Axis Info", "heading"))
        grid = QGridLayout()
        grid.addWidget(label("Axis Name", "muted"), 0, 0)
        self.axis_name = label("—", "value")
        grid.addWidget(self.axis_name, 0, 1)
        grid.addWidget(label("Range Of Travel", "muted"), 1, 0)
        self.axis_range = label("—", "value")
        grid.addWidget(self.axis_range, 1, 1)
        info.addLayout(grid)
        info.addStretch()
        h.addLayout(info, 1)
        v.addLayout(h)
        self.axis_buttons: list[QPushButton] = []
        return w

    def _tab(self, i):
        self.stack.setCurrentIndex(i)
        self.render()

    # ---------- selection ----------

    def _select_ids(self, ids):
        s = self.win.settings
        if not s:
            return
        self.win.selection = {slot for slot, k in s["keys"].items() if k["id"] in ids and slot in KEYS}
        self.win.current = min(self.win.selection) if self.win.selection else None
        self.win.refresh()

    def _select_all(self):
        self.win._select_all()

    def _uncheck(self):
        self.win._clear_selection()

    def _reset_travel(self):
        if not self._checked("Reset Travel"):
            return
        if self.win.ask(f"Put the {len(self.win.selection)} checked key(s) back on the global travel "
                        "(rapid trigger off)?"):
            self._write_keys({"touch": "global"}, "Reset travel")

    def _checked(self, what: str) -> bool:
        if not self.win.selection:
            self.status.setText(f"{what}: check one or more keys first.")
            return False
        return True

    # ---------- writes ----------

    def _write_keys(self, changes: dict, what: str):
        if not self._checked(what):
            self.render()
            return
        keys = self.win.selected_keys()
        self.status.setText(f"{what}: writing {len(keys)} key(s)…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"{what} failed: {result}")
            else:
                for k in result:
                    self.win.settings["keys"][self.win.slot_of(k["id"])] = k
                self.status.setText(f"{what}: written to {len(result)} key(s) and verified.")
            self.win.refresh()

        self.win.run(lambda req: write_keys(req, keys, changes), done)

    def _write_single(self, value):
        # keys in rapid trigger keep it; the rest switch to their own (single) travel
        if not self._checked("Single key travel"):
            self.render()
            return
        keys = self.win.selected_keys()
        rt = [k for k in keys if k["mode"]["touch"] == "rt"]
        other = [k for k in keys if k["mode"]["touch"] != "rt"]
        self.status.setText(f"Single key travel: writing {len(keys)} key(s)…")

        def work(req):
            out = []
            if other:
                out += write_keys(req, other, {"touch": "single", "actuation": value})
            if rt:
                out += write_keys(req, rt, {"actuation": value})
            return out

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Single key travel failed: {result}")
            else:
                for k in result:
                    self.win.settings["keys"][self.win.slot_of(k["id"])] = k
                self.status.setText(f"Single key travel {value:.3f} mm written to {len(result)} key(s).")
            self.win.refresh()

        self.win.run(work, done)

    def _write_rt_switch(self, on):
        self._write_keys({"touch": "rt" if on else "single"}, "Rapid trigger " + ("on" if on else "off"))

    def _write_global(self, value):
        g = self.win.settings["global"]

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Global travel failed: {result}")
            else:
                self.win.settings["global"] = result
                self.status.setText(f"Global travel {value:.3f} mm written and verified.")
            self.win.refresh()

        self.status.setText("Global travel: writing…")
        self.win.run(lambda req: write_global(req, value, g["press_dead_mm"], g["release_dead_mm"]), done)

    def _set_polling(self, index):
        s = self.win.settings
        if index == s["system"]["polling_raw"]:
            return
        if not self.win.ask(f"Set polling rate to {self.polling.currentText()}? The keyboard restarts and "
                            "reconnects; keys stop for a moment."):
            self.render()
            return
        self.status.setText("Switching polling rate; waiting for the keyboard to come back…")

        def work(req):
            write_polling(req, index)
            self.win.link.close()
            time.sleep(3.0)

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Polling rate failed: {result}")
                self.win.refresh()
            else:
                self.win.read(force=True)

        self.win.run(work, done)

    def _set_top_dead(self, on):
        def work(req):
            write_order(req, p.ORDER_TOP_DEAD_SWITCH, 1 if on else 0, p.ORDER_TOP_DEAD_SWITCH, 1 if on else 0)
            self.win.settings["system"]["top_dead_switch"] = on

        def done(result):
            self.status.setText(f"Failed: {result}" if isinstance(result, Exception) else "Top dead zone switch set.")
            self.win.refresh()

        self.win.run(work, done)

    def _cal_start(self):
        if not self.win.ask("Start adjusting (calibration) now? Then press every key fully, hold 1-2 seconds, "
                            "and click Save Adjusting."):
            return
        self.calibrating = True
        self.win.panels[4].calibrating = True   # the window asks before quitting mid-calibration

        def done(result):
            self.status.setText(f"Failed: {result}" if isinstance(result, Exception) else
                                "Adjusting: press every key fully and hold 1-2 seconds, then Save Adjusting.")
            self.win.refresh()

        self.win.run(lambda req: req(p.req_order(p.ORDER_START_CALIBRATION)), done)

    def _cal_save(self):
        self.calibrating = False
        self.win.panels[4].calibrating = False

        def done(result):
            self.status.setText(f"Failed: {result}" if isinstance(result, Exception) else "Adjusting saved.")
            self.win.refresh()

        self.win.run(lambda req: req(p.req_order(p.ORDER_CLOSE_CALIBRATION)), done)

    def _pick_axis(self, index: int):
        name = axis_table.name(self.win.settings["system"]["axes"][index])
        self._write_keys({"axis": index}, f"Switch {name}")

    # ---------- view ----------

    def values(self):
        out = {}
        for slot, k in (self.win.settings or {}).get("keys", {}).items():
            touch = k["mode"]["touch"]
            if touch == "single":
                out[slot] = (f"{k['actuation']:.3f}", "", "")
            elif touch == "rt":
                out[slot] = (f"{k['actuation']:.3f}", f"{k['rt_press']:g}", f"{k['rt_release']:g}")
        return out

    def render(self):
        s = self.win.settings
        if not s:
            return
        busy = self.win.busy
        k = self.win.primary_key()
        checked = bool(self.win.selection)
        g = s["global"]
        sysd = s["system"]
        axes = sysd.get("axes", [])

        self.global_travel.set(g["actuation_mm"])
        self.global_travel.setEnabled(not busy)
        if k:
            self.single_travel.set(k["actuation"])
            self.rt_first.set(k["actuation"])
            self.rt_press.set(k["rt_press"])
            self.rt_release.set(k["rt_release"])
            self.dead_press.set(k["dead_press"])
            self.dead_release.set(k["dead_release"])
            self.rt_switch.setChecked(k["mode"]["touch"] == "rt")
        for w in (self.single_travel, self.rt_first, self.rt_press, self.rt_release, self.rt_switch,
                  self.dead_press, self.dead_release):
            w.setEnabled(checked and not busy)

        rates = p.POLLING_RATES_1K if s.get("key_type") == 4 else p.POLLING_RATES
        self.polling.blockSignals(True)
        self.polling.clear()
        self.polling.addItems(rates)
        if 0 <= sysd["polling_raw"] < len(rates):
            self.polling.setCurrentIndex(sysd["polling_raw"])
        self.polling.blockSignals(False)
        self.polling.setEnabled(not busy)
        self.top_dead.setChecked(sysd["top_dead_switch"])
        self.top_dead.setEnabled(not busy)
        self.btn_start.setEnabled(not busy and not self.calibrating)
        self.btn_save.setEnabled(not busy and self.calibrating)

        self._render_axes(axes, k, checked, busy)

    def _render_axes(self, axes, k, checked, busy):
        if len(self.axis_buttons) != len(axes):
            for b in self.axis_buttons:
                b.deleteLater()
            self.axis_buttons = []
            for i, a in enumerate(axes):
                b = QPushButton(f"●  {axis_table.name(a)}")
                b.setObjectName("axis")
                b.setCheckable(True)
                b.setStyleSheet(f"QPushButton#axis {{ color: {AXIS_COLOURS[i % len(AXIS_COLOURS)]}; }}")
                b.clicked.connect(lambda _=False, i=i: self._pick_axis(i))
                self.axis_box.addWidget(b)
                self.axis_buttons.append(b)
        current = k.get("axis", 0) if k else None
        for i, b in enumerate(self.axis_buttons):
            b.setChecked(i == current)
            b.setEnabled(checked and not busy)
            restyle(b)
        if axes and current is not None and current < len(axes):
            a = axes[current]
            self.axis_name.setText(axis_table.name(a))
            lo, hi = axis_table.AXES.get(a, ("", 10, 3300))[1:]
            self.axis_range.setText(f"{lo / 1000:g}mm - {hi / 1000:g}mm")
        else:
            self.axis_name.setText("—" if axes else "This keyboard reports no switch list.")
            self.axis_range.setText("—")
