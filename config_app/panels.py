"""Side panels of M75 Config, one per tab. Each panel reads from and writes through the window."""

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget,
)

from app import protocol as p
from app.kbconfig import write_global, write_key_colors, write_keys, write_lighting, write_order, write_polling
from app.layout import M75_KEYS as KEYS
from kbui.widgets import SliderRow, label, restyle, rule

from kbui.lightfx import STYLES

TOUCH_NOTES = {
    "global": "Fires at the global actuation ({g:g} mm); the key's own actuation is unused.",
    "single": "Fires once at its own actuation point, releases when it comes back above it.",
    "rt": "Fires at the actuation point, then re-fires and releases on any movement past the RT distances.",
}
mm = lambda v: f"{v:.2f} mm"


def row(title: str, value: QWidget) -> QHBoxLayout:
    h = QHBoxLayout()
    h.addWidget(label(title, "muted"))
    h.addStretch()
    h.addWidget(value)
    return h


def write_buttons(panel, on_write, on_revert):
    h = QHBoxLayout()
    panel.btn_write = QPushButton("Write to keyboard")
    panel.btn_write.setObjectName("save")
    panel.btn_write.clicked.connect(on_write)
    panel.btn_revert = QPushButton("Revert")
    panel.btn_revert.clicked.connect(on_revert)
    h.addWidget(panel.btn_write)
    h.addWidget(panel.btn_revert)
    h.addStretch()
    return h


def set_dirty(panel, dirty: bool):
    panel.btn_write.setEnabled(dirty)
    panel.btn_revert.setEnabled(dirty)
    panel.btn_write.setProperty("dirty", dirty)
    restyle(panel.btn_write)


class Panel(QWidget):
    title = ""
    hint = ""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.pending: dict = {}
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(12)

    def tags(self) -> dict[int, str]:
        return {}

    def swatches(self) -> dict[int, QColor]:
        return {}

    def render(self):
        pass

    def discard(self):
        self.pending = {}


# ---------------------------------------------------------------- performance

class PerformancePanel(Panel):
    title = "Performance"
    hint = "Ctrl+click to select several keys; changes go to all of them."

    def __init__(self, win):
        super().__init__(win)
        L = self.lay
        self.sel_label = label("", "muted")
        L.addWidget(self.sel_label)
        L.addWidget(label("Trigger mode", "muted"))
        self.touch = QComboBox()
        for value, text in (("global", "Global actuation"), ("single", "Per-key actuation"), ("rt", "Rapid trigger")):
            self.touch.addItem(text, value)
        self.touch.activated.connect(lambda _: self.edit("touch", self.touch.currentData()))
        L.addWidget(self.touch)
        self.sliders = {
            "actuation": SliderRow("Actuation", 0.1, 3.5, 0.01, mm),
            "rt_press": SliderRow("Rapid trigger press", 0.01, 2.0, 0.01, mm),
            "rt_release": SliderRow("Rapid trigger release", 0.01, 2.0, 0.01, mm),
            "dead_press": SliderRow("Top deadzone", 0.0, 1.0, 0.01, mm),
            "dead_release": SliderRow("Bottom deadzone", 0.0, 1.0, 0.01, mm),
        }
        for name, s in self.sliders.items():
            s.moved.connect(lambda v, name=name: self.edit(name, v))
            L.addWidget(s)
        self.note = label("", "note")
        self.note.setWordWrap(True)
        L.addWidget(self.note)
        self.travel = label("—", "value")
        L.addLayout(row("Travel now", self.travel))
        L.addLayout(write_buttons(self, self.write, self.revert))
        self.status = label("", "note")
        self.status.setWordWrap(True)
        L.addWidget(self.status)

        L.addWidget(rule())
        L.addWidget(label("Global actuation (keys in Global mode)", "heading"))
        self.g_sliders = {
            "actuation_mm": SliderRow("Actuation", 0.1, 3.5, 0.01, mm),
            "press_dead_mm": SliderRow("Top deadzone", 0.0, 1.0, 0.01, mm),
            "release_dead_mm": SliderRow("Bottom deadzone", 0.0, 1.0, 0.01, mm),
        }
        self.g_pending = {}
        for name, s in self.g_sliders.items():
            s.moved.connect(lambda v, name=name: self.edit_global(name, v))
            L.addWidget(s)
        h = QHBoxLayout()
        self.btn_global = QPushButton("Write global")
        self.btn_global.setObjectName("save")
        self.btn_global.clicked.connect(self.write_global)
        h.addWidget(self.btn_global)
        h.addStretch()
        L.addLayout(h)
        L.addStretch()

    def tags(self):
        s = self.win.settings
        g = s["global"]["actuation_mm"]
        out = {}
        for slot, k in s["keys"].items():
            if "actuation" not in k:
                continue
            mode = k["mode"]
            tag = f"{g if mode['touch'] == 'global' else k['actuation']:g}"
            if mode["touch"] == "rt":
                tag += " RT"
            if mode["advanced"] != "none":
                tag += "+"
            out[slot] = tag
        return out

    def edit(self, name, value):
        k = self.win.primary_key()
        if not k:
            return
        current = k["mode"]["touch"] if name == "touch" else k.get(name)
        if value == current and len(self.win.selection) == 1:
            self.pending.pop(name, None)
        else:
            self.pending[name] = value
        self.status.setText("Not written yet.")
        self.render()

    def edit_global(self, name, value):
        self.g_pending[name] = value
        self.render()

    def revert(self):
        self.pending = {}
        self.status.setText("")
        self.render()

    def write(self):
        keys = self.win.selected_keys()
        changes = dict(self.pending)
        self.status.setText("Writing…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Write failed: {result}")
            else:
                for k in result:
                    slot = self.win.slot_of(k["id"])
                    self.win.settings["keys"][slot] = k
                self.pending = {}
                self.status.setText(f"Written to {len(result)} key(s) and verified.")
            self.win.refresh()

        self.win.run(lambda req: write_keys(req, keys, changes), done)

    def write_global(self):
        g = {**self.win.settings["global"], **self.g_pending}

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Global write failed: {result}")
            else:
                self.win.settings["global"] = result
                self.g_pending = {}
                self.status.setText("Global actuation written and verified.")
            self.win.refresh()

        self.win.run(lambda req: write_global(req, g["actuation_mm"], g["press_dead_mm"], g["release_dead_mm"]), done)

    def render(self):
        s = self.win.settings
        g = {**s["global"], **self.g_pending}
        for name, sl in self.g_sliders.items():
            sl.set(g[name])
        self.btn_global.setEnabled(bool(self.g_pending) and not self.win.busy)
        self.btn_global.setProperty("dirty", bool(self.g_pending))
        restyle(self.btn_global)

        k = self.win.primary_key()
        n = len(self.win.selection)
        self.sel_label.setText("Click a key on the left." if not k else
                               f"{n} keys selected (showing {KEYS[self.win.current]['label']})" if n > 1 else
                               f"Key {KEYS[self.win.current]['label']}")
        enabled = bool(k) and not self.win.busy
        self.touch.setEnabled(enabled)
        for sl in self.sliders.values():
            sl.setEnabled(enabled)
        if not k:
            set_dirty(self, False)
            return
        shown = {**k, **{n_: v for n_, v in self.pending.items() if n_ != "touch"}}
        touch = self.pending.get("touch", k["mode"]["touch"])
        self.touch.setCurrentIndex(max(0, self.touch.findData(touch)))
        for name, sl in self.sliders.items():
            if name in shown:
                sl.set(shown[name])
        self.sliders["actuation"].setVisible(touch != "global")
        self.sliders["rt_press"].setVisible(touch == "rt")
        self.sliders["rt_release"].setVisible(touch == "rt")
        self.note.setText(TOUCH_NOTES[touch].format(g=s["global"]["actuation_mm"]))
        set_dirty(self, bool(self.pending) and not self.win.busy)

    def tick(self, travel):
        if self.win.current is not None:
            self.travel.setText(f"{travel[self.win.current] / 1000:.2f} mm")


# ---------------------------------------------------------------- remap

LAYER_NAMES = {"fn0": "Base layer", "fn1": "Fn layer", "fn2": "Layer 2", "fn3": "Layer 3"}
SHORT_TAGS = {p.CONSUMER | c: t for c, t in {
    0xB5: "Next", 0xB6: "Prev", 0xB7: "Stop", 0xCD: "Play", 0xE2: "Mute", 0xE9: "Vol+", 0xEA: "Vol-",
    0x183: "Media", 0x18A: "Mail", 0x192: "Calc", 0x194: "MyPC", 0x221: "Search", 0x223: "Web",
    0x224: "Back", 0x225: "Fwd", 0x6F: "Bri+", 0x70: "Bri-"}.items()}


class RemapPanel(Panel):
    title = "Remap"
    hint = "Pick a layer, click a key, choose what it sends. Tags show the layer's mapping."

    def __init__(self, win):
        super().__init__(win)
        L = self.lay
        L.addWidget(label("Layer", "muted"))
        self.layer = QComboBox()
        for k, v in LAYER_NAMES.items():
            self.layer.addItem(v, k)
        self.layer.activated.connect(lambda _: (self.discard(), self.win.refresh()))
        L.addWidget(self.layer)
        self.sel_label = label("", "muted")
        L.addWidget(self.sel_label)
        self.current = label("—", "value")
        L.addLayout(row("Sends now", self.current))
        L.addWidget(label("Send instead", "muted"))
        self.code = QComboBox()
        self.code.setMaxVisibleItems(20)
        self.code.activated.connect(lambda _: self.pick())
        L.addWidget(self.code)
        self.warn = label("", "warn")
        self.warn.setWordWrap(True)
        L.addWidget(self.warn)
        L.addLayout(write_buttons(self, self.write, self.revert))
        self.status = label("", "note")
        self.status.setWordWrap(True)
        L.addWidget(self.status)
        L.addStretch()

    def layer_key(self) -> str:
        return self.layer.currentData()

    def tags(self):
        lk = self.layer_key()
        out = {}
        for slot, k in self.win.settings["keys"].items():
            v = k.get(lk, p.KEY_NONE)
            if lk == "fn0" and v == k["id"]:
                continue  # unchanged base key
            name = SHORT_TAGS.get(v) or (f"{v:04X}" if v >= 0xF000 and v != p.FN_KEY else p.keycode_name(v))
            if name:
                out[slot] = name[:7]
        return out

    def _fill_codes(self, k):
        self.code.blockSignals(True)
        self.code.clear()
        lk = self.layer_key()
        if lk == "fn0":
            self.code.addItem(f"Default ({p.keycode_name(k['id'])})", k["id"])
        else:
            self.code.addItem("Nothing (unbound)", p.KEY_NONE)
        for name, code in p.keycode_choices():
            self.code.addItem(name, code)
        value = self.pending.get("code", k.get(lk, p.KEY_NONE))
        i = self.code.findData(value)
        if i < 0:
            self.code.addItem(p.keycode_name(value) or f"0x{value:04X}", value)
            i = self.code.count() - 1
        self.code.setCurrentIndex(i)
        self.code.blockSignals(False)

    def pick(self):
        k = self.win.primary_key()
        if not k:
            return
        value = self.code.currentData()
        if value == k.get(self.layer_key()):
            self.pending = {}
        else:
            self.pending = {"code": value}
        self.status.setText("Not written yet." if self.pending else "")
        self.render()

    def revert(self):
        self.pending = {}
        self.status.setText("")
        self.render()

    def write(self):
        keys = [self.win.primary_key()]
        changes = {self.layer_key(): self.pending["code"]}
        self.status.setText("Writing…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Write failed: {result}")
            else:
                self.win.settings["keys"][self.win.slot_of(result[0]["id"])] = result[0]
                self.pending = {}
                self.status.setText("Written and verified.")
            self.win.refresh()

        self.win.run(lambda req: write_keys(req, keys, changes), done)

    def render(self):
        k = self.win.primary_key()
        enabled = bool(k) and not self.win.busy
        self.code.setEnabled(enabled)
        if not k:
            self.sel_label.setText("Click a key on the left.")
            self.current.setText("—")
            self.warn.setText("")
            set_dirty(self, False)
            return
        lk = self.layer_key()
        self.sel_label.setText(f"Key {KEYS[self.win.current]['label']}")
        self.current.setText(p.keycode_name(k.get(lk, p.KEY_NONE)) or "nothing")
        self._fill_codes(k)
        is_fn = k.get("fn0") == p.FN_KEY
        self.warn.setText("This is the Fn key. Remapping it on the base layer removes access to the Fn layer "
                          "until you change it back here." if is_fn and lk == "fn0" else "")
        set_dirty(self, bool(self.pending) and not self.win.busy)


# ---------------------------------------------------------------- lighting

EFFECTS = [("Static colour", 0)] + [(f"Effect {i}", i) for i in range(1, 21)] + [("Custom per-key colours", 21)]


class LightingPanel(Panel):
    title = "Lighting"
    hint = "Strips under the keys show their custom colours. Ctrl+click to colour several keys."

    def __init__(self, win):
        super().__init__(win)
        L = self.lay
        self.on = QCheckBox("Lighting on")
        self.on.toggled.connect(lambda v: self.edit("on", v))
        L.addWidget(self.on)
        L.addWidget(label("Effect", "muted"))
        self.mode = QComboBox()
        for text, value in EFFECTS:
            self.mode.addItem(text, value)
        self.mode.activated.connect(lambda _: self.edit("mode", self.mode.currentData()))
        L.addWidget(self.mode)
        lvl = lambda v: f"{int(v)}"
        self.sliders = {
            "brightness": SliderRow("Brightness", 0, 5, 1, lvl),
            "speed": SliderRow("Speed", 0, 5, 1, lvl),
            "sleep": SliderRow("Sleep after (raw value)", 0, 30, 1, lvl),
        }
        for name, s in self.sliders.items():
            s.moved.connect(lambda v, name=name: self.edit(name, int(v)))
            L.addWidget(s)
        self.reverse = QCheckBox("Reverse direction")
        self.reverse.toggled.connect(lambda v: self.edit("reverse", v))
        L.addWidget(self.reverse)
        L.addWidget(label("Palette (click to change, ● = static colour)", "muted"))
        pal = QHBoxLayout()
        pal.setSpacing(4)
        self.swatch_btns = []
        for i in range(7):
            b = QPushButton()
            b.setFixedSize(34, 24)
            b.clicked.connect(lambda _=False, i=i: self.pick_palette(i))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            self.swatch_btns.append(b)
            pal.addWidget(b)
        pal.addStretch()
        L.addLayout(pal)
        self.static_box = QComboBox()
        for i in range(7):
            self.static_box.addItem(f"Static colour = palette {i + 1}", i)
        self.static_box.activated.connect(lambda _: self.edit("static_color", self.static_box.currentData()))
        L.addWidget(self.static_box)

        self.preview_box = QWidget()
        pv = QVBoxLayout(self.preview_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(6)
        pv.addWidget(label("This effect looks like (for the preview)", "muted"))
        self.style_box = QComboBox()
        self.style_box.addItem("— not matched yet —", "")
        for key, text in STYLES.items():
            self.style_box.addItem(text, key)
        self.style_box.activated.connect(lambda _: self.set_style(self.style_box.currentData()))
        pv.addWidget(self.style_box)
        note = label("The keyboard does not say what its effects look like. Write the effect, watch the "
                     "keyboard (press a few keys too) and pick the matching style once; it is remembered.", "note")
        note.setWordWrap(True)
        pv.addWidget(note)
        L.addWidget(self.preview_box)
        L.addLayout(write_buttons(self, self.write, self.revert))
        self.status = label("", "note")
        self.status.setWordWrap(True)
        L.addWidget(self.status)

        L.addWidget(rule())
        L.addWidget(label("Per-key colours (used by the Custom effect)", "heading"))
        h = QHBoxLayout()
        self.paint = QPushButton("Pick colour")
        self.paint_color = QColor("#f2a516")
        self.paint.clicked.connect(self.pick_paint)
        self.apply_paint = QPushButton("Colour selected keys")
        self.apply_paint.clicked.connect(self.paint_selected)
        h.addWidget(self.paint)
        h.addWidget(self.apply_paint)
        h.addStretch()
        L.addLayout(h)
        h = QHBoxLayout()
        self.btn_colors = QPushButton("Write colours")
        self.btn_colors.setObjectName("save")
        self.btn_colors.clicked.connect(self.write_colors)
        self.btn_colors_revert = QPushButton("Revert")
        self.btn_colors_revert.clicked.connect(lambda: (self.color_pending.clear(), self.win.refresh()))
        h.addWidget(self.btn_colors)
        h.addWidget(self.btn_colors_revert)
        h.addStretch()
        L.addLayout(h)
        self.color_pending: dict[int, tuple[int, int, int]] = {}
        L.addStretch()

    def _styles_file(self):
        from .advanced import data_dir
        return data_dir() / "effects.json"

    def styles(self) -> dict:
        if not hasattr(self, "_styles"):
            try:
                self._styles = json.loads(self._styles_file().read_text())
            except (OSError, ValueError):
                self._styles = {}
        return self._styles

    def style_for(self, mode: int) -> str | None:
        return self.styles().get(str(mode)) or None

    def set_style(self, style: str):
        styles = self.styles()
        mode = str(self.light()["mode"])
        if style:
            styles[mode] = style
        else:
            styles.pop(mode, None)
        try:
            self._styles_file().write_text(json.dumps(styles, indent=1))
        except OSError:
            pass

    def preview_colors(self) -> dict[int, QColor]:
        keys = self.win.settings["keys"]
        out = {}
        for slot, k in keys.items():
            rgb = self.color_pending.get(slot, k.get("color"))
            if rgb:
                out[slot] = QColor(*rgb)
        return out

    def light(self) -> dict:
        return {**self.win.settings["lighting"], **self.pending}

    def swatches(self):
        out = {}
        for slot, k in self.win.settings["keys"].items():
            rgb = self.color_pending.get(slot, k.get("color"))
            if rgb and any(rgb):
                out[slot] = QColor(*rgb)
        return out

    def edit(self, name, value):
        if self.win.settings["lighting"].get(name) == value:
            self.pending.pop(name, None)
        else:
            self.pending[name] = value
        self.status.setText("Not written yet." if self.pending else "")
        self.render()

    def pick_palette(self, i):
        colors = list(self.light()["colors"])
        c = QColorDialog.getColor(QColor(colors[i]), self, "Palette colour")
        if c.isValid():
            colors[i] = c.name()
            self.edit("colors", colors)

    def pick_paint(self):
        c = QColorDialog.getColor(self.paint_color, self, "Key colour")
        if c.isValid():
            self.paint_color = c
            self.render()

    def paint_selected(self):
        for slot in self.win.selection:
            if slot in self.win.settings["keys"]:
                self.color_pending[slot] = (self.paint_color.red(), self.paint_color.green(), self.paint_color.blue())
        self.win.refresh()

    def revert(self):
        self.pending = {}
        self.status.setText("")
        self.render()

    def discard(self):
        self.pending = {}
        self.color_pending = {}

    def write(self):
        light = self.light()
        self.status.setText("Writing…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Write failed: {result}")
            else:
                self.win.settings["lighting"] = result
                self.pending = {}
                self.status.setText("Lighting written and verified.")
            self.win.refresh()

        self.win.run(lambda req: write_lighting(req, light), done)

    def write_colors(self):
        keys = self.win.settings["keys"]
        colors = {keys[s]["id"]: rgb for s, rgb in self.color_pending.items()}
        self.status.setText("Writing colours…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Colour write failed: {result}")
            else:
                for s, rgb in self.color_pending.items():
                    keys[s]["color"] = rgb
                self.color_pending = {}
                self.status.setText("Key colours written and saved.")
            self.win.refresh()

        self.win.run(lambda req: write_key_colors(req, colors), done)

    def render(self):
        light = self.light()
        busy = self.win.busy
        for w in (self.on, self.mode, self.reverse, self.static_box, *self.sliders.values(), *self.swatch_btns):
            w.setEnabled(not busy)
            w.blockSignals(True)
        self.on.setChecked(light["on"])
        self.reverse.setChecked(light["reverse"])
        i = self.mode.findData(light["mode"])
        if i < 0:
            self.mode.addItem(f"Mode {light['mode']}", light["mode"])
            i = self.mode.count() - 1
        self.mode.setCurrentIndex(i)
        for name, s in self.sliders.items():
            s.set(light[name])
        for i, b in enumerate(self.swatch_btns):
            mark = "●" if i == light["static_color"] else ""
            b.setText(mark)
            b.setStyleSheet(f"background: {light['colors'][i]}; color: #151514; border: 1px solid #2e2d2a;")
        self.static_box.setCurrentIndex(max(0, light["static_color"]))
        self.preview_box.setVisible(light["mode"] not in (0, 21))
        self.style_box.setCurrentIndex(max(0, self.style_box.findData(self.style_for(light["mode"]) or "")))
        for w in (self.on, self.mode, self.reverse, self.static_box, *self.sliders.values(), *self.swatch_btns):
            w.blockSignals(False)
        set_dirty(self, bool(self.pending) and not busy)
        self.paint.setStyleSheet(f"border-left: 14px solid {self.paint_color.name()};")
        self.apply_paint.setEnabled(bool(self.win.selection))
        dirty = bool(self.color_pending) and not busy
        self.btn_colors.setEnabled(dirty)
        self.btn_colors_revert.setEnabled(dirty)
        self.btn_colors.setProperty("dirty", dirty)
        restyle(self.btn_colors)


# ---------------------------------------------------------------- system

class SystemPanel(Panel):
    title = "System"
    hint = "Keyboard-wide settings."

    def __init__(self, win):
        super().__init__(win)
        L = self.lay
        self.info = label("", "note")
        self.info.setWordWrap(True)
        L.addWidget(self.info)
        L.addWidget(rule())
        L.addWidget(label("Operating system mode", "muted"))
        h = QHBoxLayout()
        self.btn_win = QPushButton("Windows")
        self.btn_mac = QPushButton("macOS")
        for b in (self.btn_win, self.btn_mac):
            b.setObjectName("seg")
            b.setCheckable(True)
            h.addWidget(b)
        h.addStretch()
        self.btn_win.clicked.connect(lambda: self.set_os("win"))
        self.btn_mac.clicked.connect(lambda: self.set_os("mac"))
        L.addLayout(h)
        self.top_dead = QCheckBox("Top dead-zone switch")
        self.top_dead.clicked.connect(self.set_top_dead)
        L.addWidget(self.top_dead)
        self.win_lock = label("—", "value")
        L.addLayout(row("Windows key lock (Fn shortcut)", self.win_lock))
        self.polling = QComboBox()
        h = QHBoxLayout()
        h.addWidget(label("Polling rate", "muted"))
        h.addStretch()
        h.addWidget(self.polling)
        self.btn_polling = QPushButton("Set")
        self.btn_polling.clicked.connect(self.set_polling)
        h.addWidget(self.btn_polling)
        L.addLayout(h)
        L.addWidget(label("Changing the polling rate restarts the keyboard; it reconnects by itself.", "note"))
        L.itemAt(L.count() - 1).widget().setWordWrap(True)

        L.addWidget(rule())
        L.addWidget(label("Calibration", "heading"))
        L.addWidget(label("Start, press every key slowly all the way down once, then Finish. "
                          "Keys behave oddly until you finish.", "note"))
        L.itemAt(L.count() - 1).widget().setWordWrap(True)
        h = QHBoxLayout()
        self.btn_cal_start = QPushButton("Start calibration")
        self.btn_cal_end = QPushButton("Finish calibration")
        self.btn_cal_start.clicked.connect(self.cal_start)
        self.btn_cal_end.clicked.connect(self.cal_end)
        h.addWidget(self.btn_cal_start)
        h.addWidget(self.btn_cal_end)
        h.addStretch()
        L.addLayout(h)

        L.addWidget(rule())
        h = QHBoxLayout()
        self.btn_reset = QPushButton("Factory reset…")
        self.btn_reset.setObjectName("danger")
        self.btn_reset.clicked.connect(self.factory_reset)
        h.addWidget(self.btn_reset)
        h.addStretch()
        L.addLayout(h)
        self.status = label("", "note")
        self.status.setWordWrap(True)
        L.addWidget(self.status)
        L.addStretch()
        self.calibrating = False

    def _order(self, text, work, then_read=False):
        self.status.setText(text)

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Failed: {result}")
                self.win.refresh()
            elif then_read:
                self.win.read(force=True)
            else:
                self.status.setText("Done.")
                self.win.refresh()

        self.win.run(work, done)

    def set_os(self, os_name):
        order = p.ORDER_SET_WIN_MODE if os_name == "win" else p.ORDER_SET_MAC_MODE
        expect = 1 if os_name == "win" else 0

        def work(req):
            write_order(req, order, 1, p.ORDER_QUERY_WIN_MODE, expect)
            self.win.settings["system"]["os"] = os_name

        self._order("Switching…", work)

    def set_top_dead(self, on):
        def work(req):
            write_order(req, p.ORDER_TOP_DEAD_SWITCH, 1 if on else 0, p.ORDER_TOP_DEAD_SWITCH, 1 if on else 0)
            self.win.settings["system"]["top_dead_switch"] = on

        self._order("Writing…", work)

    def set_polling(self):
        index = self.polling.currentIndex()
        if index == self.win.settings["system"]["polling_raw"]:
            self.status.setText("That is already the polling rate.")
            return
        if not self.win.ask(f"Set polling rate to {self.polling.currentText()}? The keyboard restarts and "
                            "reconnects; keys stop for a moment."):
            return
        self.status.setText("Switching polling rate; waiting for the keyboard to come back…")

        def work(req):
            import time
            write_polling(req, index)
            self.win.link.close()
            time.sleep(3.0)

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Failed: {result}")
                self.win.refresh()
            else:
                self.win.read(force=True)

        self.win.run(work, done)

    def cal_start(self):
        if not self.win.ask("Start calibration now? Then press every key slowly all the way down once "
                            "and click Finish calibration."):
            return
        self.calibrating = True
        self._order("Calibrating: press every key fully once, then click Finish.",
                    lambda req: req(p.req_order(p.ORDER_START_CALIBRATION)))
        self.status.setText("Calibrating: press every key fully once, then click Finish.")

    def cal_end(self):
        self.calibrating = False
        self._order("Finishing calibration…", lambda req: req(p.req_order(p.ORDER_CLOSE_CALIBRATION)))

    def factory_reset(self):
        if not self.win.ask("Factory reset erases every setting on the keyboard: actuation, rapid trigger, "
                            "remaps, advanced keys, macros and lighting. This cannot be undone.\n\nReset now?"):
            return
        self._order("Resetting…", lambda req: req(p.req_order(p.ORDER_FACTORY_RESET)), then_read=True)

    def render(self):
        s = self.win.settings
        sysd = s["system"]
        self.info.setText(f"{s['name']} · {s['firmware']} · protocol {s['protocol']} · serial {s['serial']}")
        self.btn_win.setChecked(sysd["os"] == "win")
        self.btn_mac.setChecked(sysd["os"] == "mac")
        self.top_dead.setChecked(sysd["top_dead_switch"])
        self.win_lock.setText("on" if sysd["win_lock"] else "off")
        rates = p.POLLING_RATES_1K if s.get("key_type") == 4 else p.POLLING_RATES
        self.polling.clear()
        self.polling.addItems(rates)
        if 0 <= sysd["polling_raw"] < len(rates):
            self.polling.setCurrentIndex(sysd["polling_raw"])
        busy = self.win.busy
        for w in (self.btn_win, self.btn_mac, self.top_dead, self.btn_cal_start, self.btn_reset, self.polling,
                  self.btn_polling):
            w.setEnabled(not busy and not self.calibrating)
        self.btn_cal_end.setEnabled(not busy and self.calibrating)
