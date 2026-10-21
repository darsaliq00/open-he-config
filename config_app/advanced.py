"""Advanced keys tab: DKS, multi-point, mod-tap, toggle, END, SOCD, rappy snappy and macros."""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from app import protocol as p
from app.kbconfig import read_advanced, write_advanced, write_keys, write_socd
from app.layout import RK_KEYS as KEYS
from app.paths import data_dir
from kbui.widgets import SliderRow, label, rule

from .panels import Panel, row

KINDS = [("None", 0), ("DKS – actions at two depths", p.ADV_DKS), ("Multi-point – 3 keys at 3 depths", p.ADV_MPT),
         ("Mod-tap – tap / hold", p.ADV_MT), ("Toggle", p.ADV_TGL), ("END – fire again on release", p.ADV_END),
         ("SOCD pair", p.ADV_SOCD), ("Rappy snappy pair", p.ADV_RS), ("Macro", p.ADV_MACRO)]
HELP = {
    0: "No advanced function on this key.",
    p.ADV_DKS: "Dynamic keystroke: each row sends a key at the ticked points of one press. "
               "The 1st point is the shallow depth, the 2nd the deep one.",
    p.ADV_MPT: "Multi-point: sends a different key at each of three depths.",
    p.ADV_MT: "Mod-tap: a short tap sends the tap key, holding past the delay sends the hold key.",
    p.ADV_TGL: "Toggle: a tap latches the key down, the next tap releases it; holding past the delay acts normally.",
    p.ADV_END: "END: sends the key again when you let go.",
    p.ADV_SOCD: "SOCD: decides what is sent while two opposite keys are both held.",
    p.ADV_RS: "Rappy snappy: of this key and its partner, the one pressed deeper wins.",
    p.ADV_MACRO: "Macro: plays a sequence of presses and releases. The keyboard cannot report macro steps back, "
                 "so this app keeps a copy in macros.json. Up to 8 macro keys.",
}




COMBO_ITEM = -1


class ComboDialog(QDialog):
    """Modifier(s) + key, sent together as one key code."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Combination key")
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        self.mods = []
        for name, bit in p.COMBO_MODS:
            cb = QCheckBox(name)
            cb.setChecked(name == "Shift")
            self.mods.append((cb, bit))
            h.addWidget(cb)
        v.addLayout(h)
        self.key = QComboBox()
        self.key.setMaxVisibleItems(20)
        for name, code in p.HID_NAMES.items():
            self.key.addItem(name, code)
        v.addWidget(self.key)
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        v.addWidget(ok)

    def code(self) -> int:
        mods = sum(bit for cb, bit in self.mods if cb.isChecked())
        return p.combo_code(mods, self.key.currentData()) if mods else self.key.currentData()


class CodeBox(QComboBox):
    """Picks a key code; 0 = nothing."""

    def __init__(self, none_text="— nothing —"):
        super().__init__()
        self.setMaxVisibleItems(20)
        self.addItem(none_text, 0)
        self.addItem("Combination (modifier + key)…", COMBO_ITEM)
        for name, code in p.keycode_choices():
            self.addItem(name, code)
        self._last = 0
        self.activated.connect(self._picked)

    def _picked(self, _):
        if self.currentData() != COMBO_ITEM:
            self._last = self.currentData()
            return
        dlg = ComboDialog(self)
        self.set_value(dlg.code() if dlg.exec() else self._last)

    def value(self) -> int:
        return self.currentData()

    def set_value(self, code: int):
        i = self.findData(code)
        if i < 0:
            self.addItem(p.keycode_name(code) or f"0x{code:04X}", code)
            i = self.count() - 1
        self.setCurrentIndex(i)
        self._last = code


def ms_spin(maximum: int, step: int = 10) -> QSpinBox:
    s = QSpinBox()
    s.setRange(0, maximum)
    s.setSingleStep(step)
    s.setSuffix(" ms")
    return s


class AdvancedPanel(Panel):
    title = "Advanced keys"
    hint = "Tags show which keys have an advanced function. Click one to see or change it."

    def __init__(self, win):
        super().__init__(win)
        self.details: dict = {}       # read from the keyboard for the current key
        self.loaded_for = None
        L = self.lay
        self.sel_label = label("", "muted")
        L.addWidget(self.sel_label)
        L.addWidget(label("Function", "muted"))
        self.kind = QComboBox()
        for text, value in KINDS:
            self.kind.addItem(text, value)
        self.kind.activated.connect(lambda _: self._show_editor())
        L.addWidget(self.kind)
        self.help = label("", "note")
        self.help.setWordWrap(True)
        L.addWidget(self.help)

        self.editors = {
            p.ADV_DKS: self._dks_editor(), p.ADV_MPT: self._mpt_editor(), p.ADV_MT: self._mt_editor(),
            p.ADV_TGL: self._tgl_editor(), p.ADV_END: self._end_editor(), p.ADV_SOCD: self._pair_editor("socd"),
            p.ADV_RS: self._pair_editor("rs"), p.ADV_MACRO: self._macro_editor(),
        }
        for w in self.editors.values():
            L.addWidget(w)
            w.setVisible(False)

        h = QHBoxLayout()
        self.btn_write = QPushButton("Write to keyboard")
        self.btn_write.setObjectName("save")
        self.btn_write.clicked.connect(self.write)
        h.addWidget(self.btn_write)
        h.addStretch()
        L.addLayout(h)
        self.status = label("", "note")
        self.status.setWordWrap(True)
        L.addWidget(self.status)
        L.addStretch()

    # ---------- editors ----------

    def _box(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(rule())
        return w, v

    def _dks_editor(self):
        w, v = self._box()
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)
        for c, name in enumerate(("↓1", "→", "↓2", "→", "↑2", "→", "↑1")):
            lb = label(name, "caps")
            lb.setToolTip(p.DKS_CELL_NAMES[c])
            grid.addWidget(lb, 0, 1 + c)
        self.dks_codes, self.dks_cells = [], []
        for r in range(4):
            box = CodeBox()
            box.setFixedWidth(110)
            grid.addWidget(box, 1 + r, 0)
            self.dks_codes.append(box)
            cells = []
            for c in range(7):
                cb = QCheckBox()
                cb.setToolTip(p.DKS_CELL_NAMES[c])
                grid.addWidget(cb, 1 + r, 1 + c)
                cells.append(cb)
            self.dks_cells.append(cells)
        v.addLayout(grid)
        v.addWidget(label("↓1 press past 1st point · ↓2 bottom out · ↑2 leave bottom · ↑1 release past 1st point · "
                          "→ keep held in between. The keyboard puts the 2nd point at bottom-out (about 3.2 mm).", "note"))
        v.itemAt(v.count() - 1).widget().setWordWrap(True)
        preset = QPushButton("Preset: sprint (key held, Shift added at full press)")
        preset.clicked.connect(self._sprint_preset)
        v.addWidget(preset)
        self.dks_first = SliderRow("1st point", 0.1, 3.5, 0.01, lambda x: f"{x:.2f} mm")
        self.dks_second = SliderRow("2nd point", 0.1, 3.5, 0.01, lambda x: f"{x:.2f} mm")
        v.addWidget(self.dks_first)
        v.addWidget(self.dks_second)
        return w

    def _sprint_preset(self):
        k = self.win.primary_key()
        if not k:
            return
        rows = [(k["id"], (1, 1, 1, 1, 1, 1, 1)), (0xE1, (0, 0, 1, 1, 1, 0, 0))]
        for r in range(4):
            code, cells = rows[r] if r < len(rows) else (0, (0,) * 7)
            self.dks_codes[r].set_value(code)
            for cb, on in zip(self.dks_cells[r], cells):
                cb.setChecked(bool(on))
        self.dks_first.set(k.get("actuation") or 1.0)
        self.status.setText("Sprint preset filled in: the key is held from the 1st point, Shift is added while "
                            "the key is bottomed out. Write to keyboard to use it.")

    def _mpt_editor(self):
        w, v = self._box()
        self.mpt_codes, self.mpt_depths = [], []
        for i in range(3):
            box = CodeBox()
            v.addWidget(label(f"Point {i + 1}", "muted"))
            v.addWidget(box)
            s = SliderRow("Depth", 0.1, 3.5, 0.01, lambda x: f"{x:.2f} mm")
            v.addWidget(s)
            self.mpt_codes.append(box)
            self.mpt_depths.append(s)
        return w

    def _mt_editor(self):
        w, v = self._box()
        self.mt_tap, self.mt_hold = CodeBox(), CodeBox()
        self.mt_delay = ms_spin(2550)
        v.addWidget(label("Tap sends", "muted"))
        v.addWidget(self.mt_tap)
        v.addWidget(label("Hold sends", "muted"))
        v.addWidget(self.mt_hold)
        v.addLayout(row("Hold after", self.mt_delay))
        return w

    def _tgl_editor(self):
        w, v = self._box()
        self.tgl_code = CodeBox()
        self.tgl_delay = ms_spin(2550)
        v.addWidget(label("Key to toggle", "muted"))
        v.addWidget(self.tgl_code)
        v.addLayout(row("Hold for normal press after", self.tgl_delay))
        return w

    def _end_editor(self):
        w, v = self._box()
        self.end_code = CodeBox()
        v.addWidget(label("Key sent on release", "muted"))
        v.addWidget(self.end_code)
        return w

    def _pair_editor(self, kind):
        w, v = self._box()
        v.addWidget(label("Partner key", "muted"))
        partner = QComboBox()
        partner.setMaxVisibleItems(20)
        v.addWidget(partner)
        if kind == "socd":
            self.socd_partner = partner
            v.addWidget(label("When both are held", "muted"))
            self.socd_mode = QComboBox()
            for m, text in p.SOCD_MODES.items():
                self.socd_mode.addItem(text, m)
            v.addWidget(self.socd_mode)
        else:
            self.rs_partner = partner
        return w

    def _macro_editor(self):
        w, v = self._box()
        self.macro_rows_box = QVBoxLayout()
        self.macro_rows_box.setSpacing(4)
        v.addLayout(self.macro_rows_box)
        h = QHBoxLayout()
        add_tap = QPushButton("Add key tap")
        add_tap.clicked.connect(lambda: (self._add_step(0x04, True, 20), self._add_step(0x04, False, 20)))
        add_step = QPushButton("Add step")
        add_step.clicked.connect(lambda: self._add_step(0x04, True, 20))
        h.addWidget(add_tap)
        h.addWidget(add_step)
        h.addStretch()
        v.addLayout(h)
        v.addWidget(label("Plays", "muted"))
        self.macro_mode = QComboBox()
        for m, text in p.MACRO_MODES.items():
            self.macro_mode.addItem(text, m)
        v.addWidget(self.macro_mode)
        self.macro_repeat = QSpinBox()
        self.macro_repeat.setRange(1, 65530)
        v.addLayout(row("Repeat count", self.macro_repeat))
        self.macro_interval = ms_spin(16777215, 1)
        self.macro_interval.setMinimum(1)
        v.addLayout(row("Repeat interval", self.macro_interval))
        self.macro_steps: list[tuple[QWidget, CodeBox, QComboBox, QSpinBox]] = []
        return w

    def _add_step(self, code, pressed, delay):
        if len(self.macro_steps) >= 60:
            return
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        box = CodeBox()
        box.setFixedWidth(110)
        box.set_value(code)
        act = QComboBox()
        act.addItems(["press", "release"])
        act.setCurrentIndex(0 if pressed else 1)
        act.setFixedWidth(84)
        delay_box = ms_spin(16777215, 10)
        delay_box.setValue(delay)
        delay_box.setFixedWidth(84)
        rm = QPushButton("×")
        rm.setFixedWidth(26)
        entry = (w, box, act, delay_box)
        rm.clicked.connect(lambda: self._remove_step(entry))
        for x in (box, act, delay_box, rm):
            h.addWidget(x)
        self.macro_rows_box.addWidget(w)
        self.macro_steps.append(entry)

    def _remove_step(self, entry):
        self.macro_steps.remove(entry)
        entry[0].deleteLater()

    def _clear_steps(self):
        for entry in self.macro_steps:
            entry[0].deleteLater()
        self.macro_steps = []

    # ---------- macro copies on disk ----------

    def _macro_file(self) -> Path:
        return data_dir() / "macros.json"

    def _load_macros(self) -> dict:
        try:
            return json.loads(self._macro_file().read_text())
        except (OSError, ValueError):
            return {}

    def _save_macro(self, key_id: int, data: dict):
        macros = self._load_macros()
        macros[str(key_id)] = data
        try:
            self._macro_file().write_text(json.dumps(macros, indent=1))
        except OSError:
            pass

    # ---------- behaviour ----------

    def tags(self):
        return {slot: k["mode"]["advanced"] for slot, k in self.win.settings["keys"].items()
                if k.get("mode", {}).get("advanced", "none") != "none"}

    def discard(self):
        self.loaded_for = None
        self.details = {}

    def _partners(self, box: QComboBox, own: int):
        box.clear()
        for slot, other in sorted(self.win.settings["keys"].items()):
            if other["id"] != own and slot in KEYS:
                box.addItem(KEYS[slot]["label"], other["id"])

    def _load(self):
        """Fetch the selected key's advanced data, then fill the editor."""
        k = self.win.primary_key()
        if not k or self.win.busy:
            return
        self.loaded_for = k["id"]
        self.status.setText("Reading…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Could not read: {result}")
                self.details = {}
            else:
                self.details = result
                self.status.setText("")
            self._fill()
            self.win.refresh()

        self.win.run(lambda req: read_advanced(req, k), done)

    def _fill(self):
        k = self.win.primary_key()
        kind = k["mode_raw"] & 15
        d = self.details
        self.kind.setCurrentIndex(max(0, self.kind.findData(kind)))
        self._partners(self.socd_partner, k["id"])
        self._partners(self.rs_partner, k["id"])
        if kind == p.ADV_DKS and d:
            for r in range(4):
                self.dks_codes[r].set_value(d["codes"][r] if d["codes"][r] != 0x4143 else 0)
                for c, bit in enumerate(p.DKS_CELLS):
                    self.dks_cells[r][c].setChecked(d["trps"][r] & bit == bit)
            self.dks_first.set(d["first_mm"] or 1.4)
            self.dks_second.set(min(3.5, d["second_mm"] or 3.0))
        else:
            for r in range(4):
                self.dks_codes[r].set_value(0)
                for cb in self.dks_cells[r]:
                    cb.setChecked(False)
            self.dks_first.set(1.4)
            self.dks_second.set(3.0)
        mpt = d if kind == p.ADV_MPT and d else {"codes": [0, 0, 0], "depths": [0.5, 1.5, 2.5]}
        for i in range(3):
            self.mpt_codes[i].set_value(mpt["codes"][i])
            self.mpt_depths[i].set(mpt["depths"][i] or 0.5 + i)
        mt = d if kind == p.ADV_MT and d else {"tap": k["id"], "hold": 0xE0, "delay_ms": 200}
        self.mt_tap.set_value(mt["tap"])
        self.mt_hold.set_value(mt["hold"])
        self.mt_delay.setValue(mt["delay_ms"])
        tgl = d if kind == p.ADV_TGL and d else {"code": k["id"], "delay_ms": 200}
        self.tgl_code.set_value(tgl["code"])
        self.tgl_delay.setValue(tgl["delay_ms"])
        end = d if kind == p.ADV_END and d else {"code": k["id"]}
        self.end_code.set_value(end["code"])
        if kind == p.ADV_SOCD and d:
            partner = d["key2"] if d["key1"] == k["id"] else d["key1"]
            self.socd_partner.setCurrentIndex(max(0, self.socd_partner.findData(partner)))
            self.socd_mode.setCurrentIndex(max(0, self.socd_mode.findText(d["mode"])))
        if kind == p.ADV_RS and d:
            self.rs_partner.setCurrentIndex(max(0, self.rs_partner.findData(d["key2"])))
        self._clear_steps()
        saved = self._load_macros().get(str(k["id"]))
        if kind == p.ADV_MACRO and saved:
            for code, pressed, delay in saved["events"]:
                self._add_step(code, pressed, delay)
            self.macro_mode.setCurrentIndex(max(0, self.macro_mode.findData(saved["mode"])))
            self.macro_repeat.setValue(saved["repeat"])
            self.macro_interval.setValue(saved["interval_ms"])
        else:
            if kind == p.ADV_MACRO:
                self.status.setText("This macro was not made with this app, so its steps are unknown. "
                                    "You can replace it.")
            self.macro_mode.setCurrentIndex(0)
            self.macro_repeat.setValue(1)
            self.macro_interval.setValue(10)
        self._show_editor()

    def _show_editor(self):
        kind = self.kind.currentData()
        for t, w in self.editors.items():
            w.setVisible(t == kind)
        self.help.setText(HELP.get(kind, ""))

    def _collect(self, kind) -> dict:
        if kind == p.ADV_DKS:
            trps = []
            for cells in self.dks_cells:
                v = 0
                for cb, bit in zip(cells, p.DKS_CELLS):
                    if cb.isChecked():
                        v |= bit
                trps.append(v)
            return {"codes": [b.value() for b in self.dks_codes], "trps": trps,
                    "first_mm": self.dks_first_value(), "second_mm": self.dks_second_value()}
        if kind == p.ADV_MPT:
            return {"codes": [b.value() for b in self.mpt_codes],
                    "depths": [round(s.lo + s.slider.value() * s.step, 3) for s in self.mpt_depths]}
        if kind == p.ADV_MT:
            return {"tap": self.mt_tap.value(), "hold": self.mt_hold.value(), "delay_ms": self.mt_delay.value()}
        if kind == p.ADV_TGL:
            return {"code": self.tgl_code.value(), "delay_ms": self.tgl_delay.value()}
        if kind == p.ADV_END:
            return {"code": self.end_code.value()}
        if kind == p.ADV_RS:
            return {"key2": self.rs_partner.currentData()}
        if kind == p.ADV_SOCD:
            return {"key2": self.socd_partner.currentData(), "mode": self.socd_mode.currentData()}
        if kind == p.ADV_MACRO:
            return {"events": [(b.value(), a.currentIndex() == 0, d.value()) for _, b, a, d in self.macro_steps],
                    "mode": self.macro_mode.currentData(), "repeat": self.macro_repeat.value(),
                    "interval_ms": self.macro_interval.value()}
        return {}

    def dks_first_value(self):
        s = self.dks_first
        return round(s.lo + s.slider.value() * s.step, 3)

    def dks_second_value(self):
        s = self.dks_second
        return round(s.lo + s.slider.value() * s.step, 3)

    def write(self):
        k = self.win.primary_key()
        kind = self.kind.currentData()
        if not k:
            return
        data = self._collect(kind)
        if kind == p.ADV_MACRO and not data["events"]:
            self.status.setText("Add at least one step.")
            return
        if kind == p.ADV_DKS and data["first_mm"] >= data["second_mm"]:
            self.status.setText("The 2nd point must be deeper than the 1st.")
            return
        settings = self.win.settings
        self.status.setText("Writing…")

        def work(req):
            if kind == 0:
                return {"keys": write_keys(req, [k], {"clear_advanced": True})}
            if kind == p.ADV_SOCD:
                delay = (k.get("socd") or {}).get("delay", 0)
                write_socd(req, k["id"], data["key2"], data["mode"], delay)
                other = settings["keys"][self.win.slot_of(data["key2"])]
                # the web driver marks both keys of the pair as SOCD keys
                req(p.req_set_key_fields([(key["id"], p.LAYOUT_MODE, p.mode_value(key["mode"]["touch"], p.ADV_SOCD))
                                          for key in (k, other)]))
                return {"reread": True}
            if kind == p.ADV_MACRO:
                used = set()
                for other in settings["keys"].values():
                    if other["id"] != k["id"] and other["mode_raw"] & 15 == p.ADV_MACRO:
                        used.add(read_advanced(req, other)["id"])
                free = [i for i in range(p.MAX_MACROS) if i not in used]
                if not free:
                    raise ValueError("all 8 macro slots are in use; remove a macro key first")
                data["id"] = free[0]
            updated = write_advanced(req, k, kind, data)
            if kind == p.ADV_RS:
                partner = settings["keys"][self.win.slot_of(data["key2"])]
                return {"keys": [updated, write_advanced(req, partner, p.ADV_RS, {"key2": k["id"]})]}
            return {"keys": [updated]}

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Write failed: {result}")
                self.win.refresh()
                return
            if kind == p.ADV_MACRO:
                self._save_macro(k["id"], {kk: data[kk] for kk in ("events", "mode", "repeat", "interval_ms")})
            if result.get("reread"):
                self.win.read(force=True)
                return
            for key in result["keys"]:
                settings["keys"][self.win.slot_of(key["id"])] = key
            self.status.setText("Written. Press the key to try it." if kind else "Advanced function removed.")
            self.loaded_for = None
            self.win.refresh()

        self.win.run(work, done)

    def render(self):
        k = self.win.primary_key()
        busy = self.win.busy
        for w in (self.kind, self.btn_write, *self.editors.values()):
            w.setEnabled(bool(k) and not busy)
        if not k:
            self.sel_label.setText("Click a key on the left.")
            self.help.setText("")
            for w in self.editors.values():
                w.setVisible(False)
            return
        self.sel_label.setText(f"Key {KEYS[self.win.current]['label']}")
        if self.loaded_for != k["id"] and not busy:
            self._load()
