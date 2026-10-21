"""Settings window for RK's non-HE keyboards (VID 0x258A): lighting, key colours and remapping.

These boards cannot report their settings, so the window keeps the full state per board in a
JSON file and sends it whole with "Send to keyboard".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QHBoxLayout,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QTabWidget,
                               QVBoxLayout, QWidget)

from app.paths import data_dir as app_data_dir
from kbui import theme
from kbui.widgets import SliderRow, card, label, row

from . import keys as names
from . import protocol as p
from .link import ClassicLink, SendError, connected
from .rkdata import Board, RKSoftware, find_install


def data_dir() -> Path:
    base = app_data_dir() / "rk_classic"
    base.mkdir(parents=True, exist_ok=True)
    return base


class Settings:
    """Per-board state that the keyboard itself cannot store for us to read."""

    def __init__(self, pid: int):
        self.path = data_dir() / f"{pid:04x}.json"
        self.mode = 1
        self.brightness = 5
        self.speed = 3
        self.sleep = 5
        self.colour = (255, 255, 255)
        self.random = False
        self.key_colours: dict[int, tuple[int, int, int]] = {}
        self.remap: dict[int, int] = {}
        self.writes_allowed = False
        try:
            d = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        self.mode = int(d.get("mode", self.mode))
        self.brightness = int(d.get("brightness", self.brightness))
        self.speed = int(d.get("speed", self.speed))
        self.sleep = int(d.get("sleep", self.sleep))
        self.colour = tuple(d.get("colour", self.colour))
        self.random = bool(d.get("random", False))
        self.key_colours = {int(k): tuple(v) for k, v in d.get("key_colours", {}).items()}
        self.remap = {int(k): int(v) for k, v in d.get("remap", {}).items()}
        self.writes_allowed = bool(d.get("writes_allowed", False))

    def save(self):
        self.path.write_text(json.dumps({
            "mode": self.mode, "brightness": self.brightness, "speed": self.speed,
            "sleep": self.sleep, "colour": list(self.colour), "random": self.random,
            "key_colours": {str(k): list(v) for k, v in self.key_colours.items()},
            "remap": {str(k): v for k, v in self.remap.items()},
            "writes_allowed": self.writes_allowed}, indent=1))


def _app_settings() -> dict:
    try:
        return json.loads((data_dir() / "app.json").read_text())
    except (OSError, ValueError):
        return {}


def _save_app_settings(d: dict):
    (data_dir() / "app.json").write_text(json.dumps(d, indent=1))


class PhotoKeyboard(QWidget):
    """RK's board photo with clickable key rectangles; plain rectangles when there is no photo."""

    clicked = Signal(int, bool)   # key buffer index, ctrl held

    MAX_W = 980

    def __init__(self):
        super().__init__()
        self.board: Board | None = None
        self.photo: QPixmap | None = None
        self.scale = 1.0
        self.selection: set[int] = set()
        self.colours: dict[int, QColor] = {}
        self.badges: dict[int, str] = {}
        self.setCursor(Qt.PointingHandCursor)

    def set_board(self, board: Board | None):
        self.board = board
        self.photo = QPixmap(str(board.photo)) if board and board.photo else None
        if self.photo is not None and self.photo.isNull():
            self.photo = None
        if not board or not board.keys:
            self.setFixedSize(400, 120)
        else:
            w = self.photo.width() if self.photo else max(k.rect[2] for k in board.keys) + 20
            h = self.photo.height() if self.photo else max(k.rect[3] for k in board.keys) + 20
            self.scale = min(1.0, self.MAX_W / w) if w else 1.0
            self.setFixedSize(int(w * self.scale), int(h * self.scale))
        self.update()

    def _rect(self, k) -> QRectF:
        l, t, r, b = k.rect
        s = self.scale
        return QRectF(l * s, t * s, (r - l) * s, (b - t) * s)

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        if not self.board:
            qp.setPen(QColor(theme.MUTED))
            qp.drawText(self.rect(), Qt.AlignCenter, "No board")
            return
        if self.photo:
            qp.drawPixmap(self.rect(), self.photo)
        f = QFont()
        f.setFamilies(["Segoe UI"])
        f.setPointSizeF(7)
        qp.setFont(f)
        for k in self.board.keys:
            rc = self._rect(k)
            if not self.photo:
                qp.setPen(QPen(QColor("#cdd2da"), 1))
                qp.setBrush(QColor("#f4f5f7"))
                qp.drawRoundedRect(rc, 4, 4)
                qp.setPen(QColor("#2b3340"))
                qp.drawText(rc, Qt.AlignCenter, k.name)
            c = self.colours.get(k.index)
            if c is not None:
                fill = QColor(c)
                fill.setAlpha(150)
                qp.setPen(Qt.NoPen)
                qp.setBrush(fill)
                qp.drawRoundedRect(rc.adjusted(2, 2, -2, -2), 3, 3)
            if k.index in self.selection:
                qp.setPen(QPen(QColor(theme.ACCENT), 2.5))
                qp.setBrush(Qt.NoBrush)
                qp.drawRoundedRect(rc.adjusted(1, 1, -1, -1), 4, 4)
            badge = self.badges.get(k.index)
            if badge:
                br = QRectF(rc.left(), rc.bottom() - 13, rc.width(), 13)
                qp.setPen(Qt.NoPen)
                qp.setBrush(QColor(theme.ACCENT))
                qp.drawRoundedRect(br, 3, 3)
                qp.setPen(QColor("white"))
                qp.drawText(br, Qt.AlignCenter, badge)

    def mousePressEvent(self, e):
        if not self.board:
            return
        for k in self.board.keys:
            if self._rect(k).contains(e.position()):
                self.clicked.emit(k.index, bool(e.modifiers() & Qt.ControlModifier))
                return


class ClassicWindow(QMainWindow):
    def __init__(self, icon=None):
        super().__init__()
        self.setWindowTitle("Open HE Config: RK keyboards (non-HE)")
        if icon:
            self.setWindowIcon(icon)
        self.setStyleSheet(theme.STYLE)
        self.link = ClassicLink()
        self.app_settings = _app_settings()
        self.rk: RKSoftware | None = None
        self.board: Board | None = None
        self.path: bytes | None = None
        self.connected_pid: int | None = None
        self.state: Settings | None = None
        self.modes: dict[int, str] = {}
        self.selection: set[int] = set()
        self.keymap_dirty = False

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        top = QHBoxLayout()
        col = QVBoxLayout()
        self.device = label("Looking for a keyboard…", "device")
        self.status = label("", "disconnected")
        col.addWidget(self.device)
        col.addWidget(self.status)
        top.addLayout(col)
        top.addStretch()
        self.board_pick = QComboBox()
        self.board_pick.setMinimumWidth(260)
        self.board_pick.currentIndexChanged.connect(self._pick_board)
        top.addWidget(self.board_pick)
        folder = QPushButton("RK software folder…")
        folder.clicked.connect(self._choose_folder)
        top.addWidget(folder)
        self.send_btn = QPushButton("Send to keyboard")
        self.send_btn.setObjectName("save")
        self.send_btn.clicked.connect(self._send)
        top.addWidget(self.send_btn)
        outer.addLayout(top)

        self.notice = label("", "note")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)

        kb_card, kb_lay = card()
        self.photo = PhotoKeyboard()
        self.photo.clicked.connect(self._key_clicked)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.photo)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setMinimumHeight(260)
        kb_lay.addWidget(self.scroll)
        kb_lay.addWidget(label("Click a key to select it, Ctrl+click to select several.", "note"))
        outer.addWidget(kb_card, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._lighting_tab(), "Lighting")
        self.tabs.addTab(self._remap_tab(), "Remap")
        self.tabs.currentChanged.connect(lambda _: self._refresh_photo())
        outer.addWidget(self.tabs)

        self.resize(1080, 820)
        self._load_rk()
        self.timer = QTimer(self, interval=2000, timeout=self._scan)
        self.timer.start()
        self._scan()

    # ---- building ----

    def _lighting_tab(self) -> QWidget:
        w, lay = card()
        self.mode_pick = QComboBox()
        self.mode_pick.currentIndexChanged.connect(self._mode_changed)
        lay.addLayout(row("Effect", self.mode_pick))
        self.bright = SliderRow("Brightness", 0, 5, 1, lambda v: p.BRIGHTNESS[int(v)])
        self.bright.moved.connect(lambda v: self._set("brightness", int(v)))
        self.speed = SliderRow("Speed", 1, 5, 1, lambda v: p.SPEEDS[int(v) - 1])
        self.speed.moved.connect(lambda v: self._set("speed", int(v)))
        self.sleep = SliderRow("Lights off after", 1, 5, 1, lambda v: p.SLEEP[int(v) - 1])
        self.sleep.moved.connect(lambda v: self._set("sleep", int(v)))
        for s in (self.bright, self.speed, self.sleep):
            lay.addWidget(s)
        h = QHBoxLayout()
        self.colour_btn = QPushButton("Colour")
        self.colour_btn.clicked.connect(self._pick_colour)
        self.random = QCheckBox("Random colours")
        self.random.toggled.connect(lambda v: self._set("random", v))
        h.addWidget(self.colour_btn)
        h.addWidget(self.random)
        h.addStretch()
        lay.addLayout(h)
        h = QHBoxLayout()
        self.key_colour_btn = QPushButton("Colour selected keys")
        self.key_colour_btn.clicked.connect(self._colour_keys)
        self.key_clear_btn = QPushButton("Clear selected keys")
        self.key_clear_btn.clicked.connect(self._clear_key_colours)
        self.custom_note = label("", "note")
        h.addWidget(self.key_colour_btn)
        h.addWidget(self.key_clear_btn)
        h.addWidget(self.custom_note)
        h.addStretch()
        lay.addLayout(h)
        return w

    def _remap_tab(self) -> QWidget:
        w, lay = card()
        self.remap_info = label("Select a key on the board.", "muted")
        lay.addWidget(self.remap_info)
        h = QHBoxLayout()
        self.target = QComboBox()
        self.target.setMaxVisibleItems(24)
        for group, items in names.GROUPS:
            self.target.addItem(f"— {group} —", None)
            self.target.model().item(self.target.count() - 1).setEnabled(False)
            for n, code in items:
                self.target.addItem(n, code)
        h.addWidget(self.target, 1)
        apply_btn = QPushButton("Set selected keys")
        apply_btn.clicked.connect(self._apply_remap)
        reset_btn = QPushButton("Restore selected keys")
        reset_btn.clicked.connect(self._reset_remap)
        reset_all = QPushButton("Restore all keys")
        reset_all.clicked.connect(self._reset_all)
        for b in (apply_btn, reset_btn, reset_all):
            h.addWidget(b)
        lay.addLayout(h)
        self.remap_note = label("", "note")
        self.remap_note.setWordWrap(True)
        lay.addWidget(self.remap_note)
        return w

    # ---- RK software and device ----

    def _load_rk(self):
        extra = [Path(self.app_settings["rk_dir"])] if self.app_settings.get("rk_dir") else []
        self.rk = find_install(extra)
        self.board_pick.blockSignals(True)
        self.board_pick.clear()
        if self.rk:
            for pid in self.rk.boards():
                self.board_pick.addItem(f"{self.rk.names.get(pid, 'RK board')} ({pid:04X})", pid)
        self.board_pick.blockSignals(False)
        if not self.rk:
            self.notice.setText("RK Keyboard Software was not found. Install it from rkgaming.com "
                                "(Download page), or point to its folder with \"RK software folder…\". "
                                "Board layouts, photos and effect names are read from it.")
        else:
            self.notice.setText(f"Board data from RK software at {self.rk.root}")

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "RK Keyboard Software folder")
        if not d:
            return
        rk = find_install([Path(d)])
        if not rk:
            QMessageBox.warning(self, "Not found", "That folder has no Cfg.ini and Dev folder.")
            return
        self.app_settings["rk_dir"] = str(rk.root)
        _save_app_settings(self.app_settings)
        self._load_rk()
        self._scan(force=True)

    def _scan(self, force: bool = False):
        found = connected()
        hit = found[0] if found else None
        self.connected_pid = hit[1] if hit else None
        if hit and self.rk:
            path, pid = hit
            if force or self.path != path:
                self.path = path
                i = self.board_pick.findData(pid)
                if i >= 0:
                    self.board_pick.setCurrentIndex(i)
                    self._pick_board(i)
                else:
                    self.device.setText(f"RK keyboard {pid:04X}")
                    self.status.setText("Connected, but RK's software has no data for this board")
            return
        if hit:
            self.path = hit[0]
            self.device.setText(f"RK keyboard {hit[1]:04X}")
        else:
            self.path = None
        self._show_status()

    def _pick_board(self, i: int):
        pid = self.board_pick.itemData(i)
        if pid is None or not self.rk:
            return
        self.board = self.rk.board(pid)
        self.state = Settings(pid)
        self.modes = self.rk.mode_names(self.board.rgb)
        self.selection.clear()
        self.keymap_dirty = False
        self.device.setText(self.board.name)
        self.photo.set_board(self.board)
        self.scroll.setMinimumHeight(min(self.photo.height() + 8, 560))
        self.mode_pick.blockSignals(True)
        self.mode_pick.clear()
        for n, title in self.modes.items():
            self.mode_pick.addItem(title, n)
        if not self.modes:
            for n in range(1, 21):
                self.mode_pick.addItem(f"Effect {n}", n)
        i = self.mode_pick.findData(self.state.mode)
        self.mode_pick.setCurrentIndex(max(i, 0))
        self.mode_pick.blockSignals(False)
        self.bright.set(self.state.brightness)
        self.speed.set(self.state.speed)
        self.sleep.set(self.state.sleep)
        self.random.blockSignals(True)
        self.random.setChecked(self.state.random)
        self.random.blockSignals(False)
        self._update_colour_btn()
        self._mode_changed()
        if not self.board.can_remap:
            self.remap_note.setText("Remapping is off for this board: RK's data has keys whose default "
                                    "code is unknown, and the key map can only be written whole.")
        else:
            self.remap_note.setText("The whole key map is sent each time, so every key gets its "
                                    "default code unless you changed it here.")
        self._show_status()

    def _show_status(self):
        online = self.board is not None and self.connected_pid == self.board.pid
        self.status.setObjectName("connected" if online else "disconnected")
        self.status.setText("Connected" if online else "Not connected (you can still prepare settings)")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.send_btn.setEnabled(online)

    # ---- editing ----

    def _set(self, name, value):
        if self.state:
            setattr(self.state, name, value)
            self.state.save()

    def _custom_mode(self) -> bool:
        return "custom" in self.modes.get(self.state.mode, "").lower() if self.state else False

    def _mode_changed(self, *_):
        if not self.state or self.mode_pick.currentData() is None:
            return
        self._set("mode", int(self.mode_pick.currentData()))
        opts = self.board.mode_options(self.state.mode)
        self.speed.setEnabled(opts["speed"])
        self.bright.setEnabled(opts["brightness"])
        self.colour_btn.setEnabled(opts["colours"] or not self.board.rgb)
        self.random.setEnabled(opts["random"])
        custom = self._custom_mode()
        self.key_colour_btn.setEnabled(custom)
        self.key_clear_btn.setEnabled(custom)
        self.custom_note.setText("" if custom else "Per-key colours are used by the custom effect.")
        self._refresh_photo()

    def _update_colour_btn(self):
        r, g, b = self.state.colour
        fg = "black" if r * 0.3 + g * 0.59 + b * 0.11 > 150 else "white"
        self.colour_btn.setStyleSheet(f"background: rgb({r},{g},{b}); color: {fg};")

    def _pick_colour(self):
        c = QColorDialog.getColor(QColor(*self.state.colour), self, "Effect colour")
        if c.isValid():
            self._set("colour", (c.red(), c.green(), c.blue()))
            self._update_colour_btn()

    def _colour_keys(self):
        if not self.selection:
            return
        c = QColorDialog.getColor(QColor(*self.state.colour), self, "Key colour")
        if not c.isValid():
            return
        for i in self.selection:
            self.state.key_colours[i] = (c.red(), c.green(), c.blue())
        self.state.save()
        self._refresh_photo()

    def _clear_key_colours(self):
        for i in self.selection:
            self.state.key_colours.pop(i, None)
        self.state.save()
        self._refresh_photo()

    def _key_clicked(self, index: int, add: bool):
        if add:
            self.selection ^= {index}
        else:
            self.selection = {index}
        self._refresh_photo()
        keys = [k for k in self.board.keys if k.index in self.selection]
        if len(keys) == 1:
            k = keys[0]
            now = self.state.remap.get(k.index, k.default)
            self.remap_info.setText(f"{k.name or 'Key'}: sends {names.name(now) if now is not None else 'unknown'}"
                                    + ("  (changed)" if k.index in self.state.remap else ""))
        else:
            self.remap_info.setText(f"{len(keys)} keys selected" if keys else "Select a key on the board.")

    def _apply_remap(self):
        code = self.target.currentData()
        if code is None or not self.selection or not self.board.can_remap:
            return
        for k in self.board.keys:
            if k.index in self.selection:
                if code == k.default:
                    self.state.remap.pop(k.index, None)
                else:
                    self.state.remap[k.index] = code
        self.keymap_dirty = True
        self.state.save()
        self._refresh_photo()

    def _reset_remap(self):
        for i in self.selection:
            self.state.remap.pop(i, None)
        self.keymap_dirty = True
        self.state.save()
        self._refresh_photo()

    def _reset_all(self):
        self.state.remap.clear()
        self.keymap_dirty = True
        self.state.save()
        self._refresh_photo()

    def _refresh_photo(self):
        self.photo.selection = set(self.selection)
        lighting = self.tabs.currentIndex() == 0
        if self.state and lighting and self._custom_mode():
            self.photo.colours = {i: QColor(*c) for i, c in self.state.key_colours.items()}
        else:
            self.photo.colours = {}
        self.photo.badges = ({i: names.name(c) for i, c in self.state.remap.items()}
                             if self.state and not lighting else {})
        self.photo.update()

    # ---- sending ----

    def _confirm_writes(self) -> bool:
        if self.state.writes_allowed:
            return True
        ok = QMessageBox.question(
            self, "Untested keyboard",
            f"{self.board.name} has not been tested with this app yet. The settings protocol "
            "comes from RK's own software, but writing could still set something unexpected "
            "(you can fix it again with RK's software).\n\nSend settings to this keyboard?")
        if ok != QMessageBox.Yes:
            return False
        self._set("writes_allowed", True)
        return True

    def _send(self):
        if not (self.board and self.state and self.path) or self.connected_pid != self.board.pid:
            return
        if not self._confirm_writes():
            return
        s, b = self.state, self.board
        reports = [p.lighting(s.mode, s.brightness, s.speed, s.colour, s.random, s.sleep, b.rgb_order)]
        if self._custom_mode():
            reports += p.key_colours(s.key_colours, b.rgb_order)
        if b.can_remap and (s.remap or self.keymap_dirty):
            codes = {k.index: k.default for k in b.keys}
            codes.update(s.remap)
            reports += p.key_map(codes)
        try:
            self.link.send(self.path, reports)
        except SendError as e:
            QMessageBox.warning(self, "Not sent", str(e))
            return
        self.keymap_dirty = False
        self.status.setText(f"Sent ({len(reports)} reports)")


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = ClassicWindow()
    w.show()
    sys.exit(app.exec())
