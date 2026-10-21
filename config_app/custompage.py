"""Custom Key page, laid out like RK's web driver: WIN/MAC and FN0-FN3 under the keyboard, then
tabs of round key buttons (Letter, Number Key, Symbolic Key, Basic Key, Function Key, Keyboard
Control, Mouse, Combination Key). Check keys on the keyboard, then click what they should send on
the chosen layer; it is written at once and read back to confirm.

The key lists and codes follow RK's web driver.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QGridLayout, QHBoxLayout, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from app import protocol as p
from app.kbconfig import write_keys, write_order
from kbui.widgets import label

from .panels import SHORT_TAGS, Panel

C = p.CONSUMER
NAMES = {
    **{0x04 + i: chr(ord("A") + i) for i in range(26)},
    **{0x1E + i: str((i + 1) % 10) for i in range(10)},
    **{0x59 + i: f"Pad{(i + 1) % 10}" for i in range(10)},
    0x54: "Pad /", 0x55: "Pad *", 0x56: "Pad -", 0x57: "Pad +", 0x6235: "~", 0x2D: "-", 0x2E: "=",
    0x2F: "[", 0x30: "]", 0x31: "\\", 0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",", 0x37: ".", 0x38: "/",
    0x39: "Caps",
    0x00: "Disable", 0x28: "Enter", 0x29: "Esc", 0x2A: "BackSpace", 0x2B: "Tab", 0x2C: "Space",
    0x4F: "→", 0x50: "←", 0x51: "↓", 0x52: "↑", 0xE0: "L-Ctrl", 0xE1: "L-Shift", 0xE2: "L-Alt",
    0xE3: "L-Win", 0xE4: "R-Ctrl", 0xE5: "R-Shift", 0xE6: "R-Alt", 0xE7: "R-Win",
    **{0x3A + i: f"F{i + 1}" for i in range(12)}, **{0x68 + i: f"F{i + 13}" for i in range(12)},
    0x46: "Print Screen", 0x47: "Scroll Lock", 0x48: "Pause", 0x49: "Insert", 0x4A: "Home",
    0x4B: "PgUp", 0x4C: "Del", 0x4D: "End", 0x4E: "PgDn", 0xF001: "Fn1", 0xF002: "Fn2", 0xF003: "Fn3",
    C | 0xE9: "Volume+", C | 0xEA: "Volume-", C | 0x6F: "Screen Brightness+", C | 0x70: "Screen Brightness-",
    C | 0xB5: "Next Track", C | 0xB6: "Previous Track", C | 0xB7: "Stop", C | 0xCD: "Play",
    C | 0xE2: "Mute", C | 0x183: "Media", C | 0x18A: "Email", C | 0x192: "Calculator", C | 0x194: "File",
    C | 0x223: "Web Browser",
    0xF100: "Reset", 0xF101: "Win", 0xF102: "Mac", 0xF103: "Calibration", 0xF108: "Config1",
    0xF109: "Config2", 0xF10A: "Config3", 0xF10C: "Config4", 0xF10B: "WASD Switch", 0xF309: "LockWin",
    0xF310: "Light Effect+", 0xF311: "Light Direction", 0xF312: "Light Brightness+",
    0xF313: "Light Brightness-", 0xF314: "Light Speed+", 0xF315: "Light Speed-", 0xF317: "Light Switch",
    0xF325: "Ambient Light Effect+", 0xF326: "Ambient Light Switch", 0xF327: "Ambient Light Direction",
    0xF328: "Ambient Light Speed+", 0xF329: "Ambient Light Speed-", 0xF32A: "Ambient Light Brightness+",
    0xF32B: "Ambient Light Brightness-", 0xF32C: "Ambient Light Effect-", 0xF32F: "Light Effect-",
    0x7301: "Mouse Left Click", 0x7302: "Mouse Right Click", 0x7303: "Mouse Middle Click",
    0x7304: "Mouse Move Left", 0x7305: "Mouse Move Right", 0x7306: "Mouse Move Up",
    0x7307: "Mouse Move Down", 0x7308: "Scroll Wheel Up", 0x7309: "Scroll Wheel Down",
    0x730A: "Forward", 0x730B: "Back",
}

LETTERS = list(range(0x04, 0x1E))
NUMBERS = list(range(0x1E, 0x28)) + list(range(0x59, 0x63))
SYMBOLS = [0x54, 0x55, 0x56, 0x57, 0x6235, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38,
           0x39]
BASIC = [0x00, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x4F, 0x50, 0x51, 0x52, *range(0xE0, 0xE8)]
FUNCTION = [*range(0x3A, 0x46), *range(0x68, 0x74), *range(0x46, 0x4F), 0xF001, 0xF002, 0xF003,
            C | 0xE9, C | 0xEA, C | 0x6F, C | 0x70, C | 0xB5, C | 0xB6, C | 0xB7, C | 0xCD, C | 0xE2,
            C | 0x183, C | 0x18A, C | 0x192, C | 0x194, C | 0x223]
CONTROL = [0xF100, 0xF101, 0xF102, 0xF103, 0xF108, 0xF109, 0xF10A, 0xF10C, 0xF10B, 0xF309, 0xF310, 0xF311,
           0xF312, 0xF313, 0xF314, 0xF315, 0xF317, 0xF325, 0xF326, 0xF327, 0xF328, 0xF329, 0xF32A, 0xF32B,
           0xF32C, 0xF32F]
HOLD_3S = {0xF100, 0xF101, 0xF102, 0xF103, 0xF108, 0xF109, 0xF10A, 0xF10C, 0xF10B}
MOUSE = list(range(0x7301, 0x730C))
COMBO_KEYS = [c for c in LETTERS + NUMBERS + SYMBOLS + BASIC if 0 < c <= 0xFF and c < 0xE0]

TABS = [("Letter", LETTERS), ("Number Key", NUMBERS), ("Symbolic Key", SYMBOLS), ("Basic Key", BASIC),
        ("Function Key", FUNCTION), ("Keyboard Control", CONTROL), ("Mouse", MOUSE),
        ("Combination Key", None)]
LAYERS = ["fn0", "fn1", "fn2", "fn3"]
COMBO_MODS = [("CTRL", 1), ("SHIFT", 2), ("WIN", 8), ("ALT", 4)]


def name(code: int) -> str:
    return NAMES.get(code) or SHORT_TAGS.get(code) or p.keycode_name(code) or f"0x{code:04X}"


class CustomKeyPage(Panel):
    title = "Custom Key"
    hint = "Click keys to check them, then pick what they send below."
    toggle_select = True

    def __init__(self, win):
        super().__init__(win)
        self.layer = "fn0"
        self.lay.setSpacing(14)

        bar = QHBoxLayout()
        bar.addStretch()
        self.os_group = QButtonGroup(self)
        for i, text in enumerate(("WIN", "MAC")):
            b = QPushButton(text)
            b.setObjectName("pill")
            b.setCheckable(True)
            self.os_group.addButton(b, i)
            bar.addWidget(b)
        self.os_group.idClicked.connect(self._set_os)
        bar.addSpacing(18)
        self.layer_group = QButtonGroup(self)
        for i, layer in enumerate(LAYERS):
            b = QPushButton(layer.upper())
            b.setObjectName("pill")
            b.setCheckable(True)
            self.layer_group.addButton(b, i)
            bar.addWidget(b)
        self.layer_group.button(0).setChecked(True)
        self.layer_group.idClicked.connect(self._set_layer)
        bar.addStretch()
        self.lay.addLayout(bar)

        tabs = QHBoxLayout()
        tabs.addStretch()
        self.tab_group = QButtonGroup(self)
        for i, (text, _) in enumerate(TABS):
            b = QPushButton(text.upper())
            b.setObjectName("tab")
            b.setCheckable(True)
            self.tab_group.addButton(b, i)
            tabs.addWidget(b)
        tabs.addStretch()
        self.tab_group.button(0).setChecked(True)
        self.tab_group.idClicked.connect(lambda i: self.stack.setCurrentIndex(i))
        self.lay.addLayout(tabs)

        self.stack = QStackedWidget()
        for text, codes in TABS:
            self.stack.addWidget(self._grid(codes, hold_note=codes is CONTROL) if codes else self._combo())
        self.lay.addWidget(self.stack)
        self.status = label("", "note")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignCenter)
        self.lay.addWidget(self.status)
        self.lay.addStretch()

    # ---------- building ----------

    def _key_button(self, code: int, wide=False) -> QPushButton:
        b = QPushButton(name(code))
        b.setObjectName("keyhold" if code in HOLD_3S else "keybtn")
        b.setFixedHeight(44)
        if wide:
            b.setFixedWidth(max(60, b.fontMetrics().horizontalAdvance(b.text()) + 30))
        else:
            b.setFixedWidth(max(50, b.fontMetrics().horizontalAdvance(b.text()) + 26))
        b.clicked.connect(lambda _=False, c=code: self._assign(c))
        return b

    def _grid(self, codes, hold_note=False) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        wide = not all(len(name(c)) <= 6 for c in codes)
        rows, current, row_w = [], [], 0
        for c in codes:
            b = self._key_button(c, wide=wide)
            bw = b.width() + 10
            if current and (len(current) >= 14 or row_w + bw > 1040):
                rows.append(current)
                current, row_w = [], 0
            current.append(b)
            row_w += bw
        if current:
            rows.append(current)
        for buttons in rows:
            h = QHBoxLayout()
            h.setSpacing(10)
            h.addStretch()
            for b in buttons:
                h.addWidget(b)
            h.addStretch()
            v.addLayout(h)
        if hold_note:
            n = label("■ The orange keys need to be held for more than 3 s to act.", "holdnote")
            n.setAlignment(Qt.AlignCenter)
            v.addWidget(n)
        return page

    def _combo(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch()
        mods = QVBoxLayout()
        self.mod_buttons = {}
        for text, bit in COMBO_MODS:
            b = QPushButton(text)
            b.setObjectName("pill")
            b.setCheckable(True)
            b.setChecked(bit == 1)
            mods.addWidget(b)
            self.mod_buttons[bit] = b
        mods.addStretch()
        h.addLayout(mods)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.combo_group = QButtonGroup(self)
        for i, c in enumerate(COMBO_KEYS):
            b = QPushButton(name(c))
            b.setObjectName("keybtn")
            b.setCheckable(True)
            b.setFixedSize(max(50, b.fontMetrics().horizontalAdvance(b.text()) + 26), 44)
            self.combo_group.addButton(b, c)
            grid.addWidget(b, i // 12, i % 12)
        h.addLayout(grid)
        bind = QVBoxLayout()
        bind.addStretch()
        btn = QPushButton("Bind Combination")
        btn.clicked.connect(self._bind_combo)
        bind.addWidget(btn)
        h.addLayout(bind)
        h.addStretch()
        return w

    # ---------- actions ----------

    def _set_layer(self, i):
        self.layer = LAYERS[i]
        self.win.refresh()

    def _set_os(self, i):
        os_name = "win" if i == 0 else "mac"
        if not self.win.settings or self.win.settings["system"]["os"] == os_name:
            return
        order = p.ORDER_SET_WIN_MODE if os_name == "win" else p.ORDER_SET_MAC_MODE

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Switching to {os_name.upper()} failed: {result}")
                self.win.refresh()
            else:
                self.win.read(force=True)   # the key map can differ per system

        self.status.setText(f"Switching the keyboard to {os_name.upper()} mode…")
        self.win.run(lambda req: write_order(req, order, 1, p.ORDER_QUERY_WIN_MODE, 1 if os_name == "win" else 0),
                     done)

    def _bind_combo(self):
        key = self.combo_group.checkedId()
        mods = sum(bit for bit, b in self.mod_buttons.items() if b.isChecked())
        if key < 0 or not mods:
            self.status.setText("Pick at least one of CTRL / SHIFT / WIN / ALT and a key first.")
            return
        self._assign(p.combo_code(mods, key))

    def _assign(self, code: int):
        if not self.win.selection:
            self.status.setText("Check one or more keys on the keyboard first.")
            return
        keys = self.win.selected_keys()
        if self.layer == "fn0" and any(k.get("fn0") == p.FN_KEY or k["id"] == p.KEY_NONE for k in keys):
            if not self.win.ask("One of the checked keys is the Fn key. Changing it on FN0 removes access to the "
                                "Fn layer until you set it back. Continue?"):
                return
        self.status.setText(f"Writing {name(code)} to {len(keys)} key(s) on {self.layer.upper()}…")

        def done(result):
            if isinstance(result, Exception):
                self.status.setText(f"Write failed: {result}")
            else:
                for k in result:
                    self.win.settings["keys"][self.win.slot_of(k["id"])] = k
                self.status.setText(f"{name(code)} set on {len(result)} key(s), {self.layer.upper()}. Verified.")
            self.win.refresh()

        layer = self.layer
        self.win.run(lambda req: write_keys(req, keys, {layer: code}), done)

    # ---------- view ----------

    def tags(self):
        out = {}
        for slot, k in (self.win.settings or {}).get("keys", {}).items():
            v = k.get(self.layer, p.KEY_NONE)
            if self.layer == "fn0" and v == k["id"]:
                continue
            if v == p.KEY_NONE:
                continue
            out[slot] = name(v)[:7]
        return out

    def render(self):
        s = self.win.settings
        if not s:
            return
        self.os_group.button(0 if s["system"]["os"] == "win" else 1).setChecked(True)
        busy = self.win.busy
        for b in self.stack.findChildren(QPushButton):
            b.setEnabled(not busy)
