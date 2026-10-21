"""Macro Management page, laid out like RK's web driver: a macro list on the left, the selected
macro's steps on the right, and Start Recording / Delete Macro / Copy Macro buttons.

The keyboard only stores macros attached to keys, so this library is kept by the app
(macro_library.json in its data folder). Advanced Key > Macro loads a macro from here onto a key.
"""

import json
import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app import keycodes, protocol as p
from app.paths import data_dir
from kbui.widgets import card, label

MAX_EVENTS = 60   # what one key macro can hold


def library_file():
    return data_dir() / "macro_library.json"


def load_library() -> list[dict]:
    """[{name, created, events: [[code, pressed, delay_ms], ...]}]"""
    try:
        data = json.loads(library_file().read_text())
        return [m for m in data if isinstance(m, dict) and "events" in m]
    except (OSError, ValueError):
        return []


def save_library(macros: list[dict]):
    library_file().write_text(json.dumps(macros, indent=1))


# Windows scan code (from Qt's nativeScanCode, 0x100 = extended) -> HID usage
_SCAN_TO_USAGE = {}
for _usage, (_, _scan) in keycodes._KEYS.items():
    _SCAN_TO_USAGE.setdefault(_scan, _usage)


def usage_from_scan(native: int) -> int | None:
    scan = 0xE000 | (native & 0xFF) if native & 0x100 else native & 0xFF
    return _SCAN_TO_USAGE.get(scan)


def key_name(code: int) -> str:
    return p.keycode_name(code) or keycodes.describe(code)[0] or f"0x{code:02X}"


class MacroPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.macros = load_library()
        self.recording = False
        self._rec_events: list[list] = []
        self._rec_last = 0.0

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(12)
        v.addWidget(label("Macro Management", "bigheading"))
        h = QHBoxLayout()
        self.btn_record = QPushButton("▸  Start Recording")
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_delete = QPushButton("Delete Macro")
        self.btn_delete.setObjectName("dangerfill")
        self.btn_delete.clicked.connect(self._delete)
        self.btn_copy = QPushButton("Copy Macro")
        self.btn_copy.clicked.connect(self._copy)
        for b in (self.btn_record, self.btn_delete, self.btn_copy):
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)

        tables = QHBoxLayout()
        tables.setSpacing(18)
        c, cv = card()
        cv.setContentsMargins(0, 0, 0, 0)
        self.list = QTableWidget(0, 4)
        self.list.setHorizontalHeaderLabels(["", "Macro Name", "Date Created", "Operation Length"])
        self._style_table(self.list)
        self.list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.list.setColumnWidth(0, 34)
        self.list.setColumnWidth(2, 130)
        self.list.setColumnWidth(3, 130)
        self.list.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.list.itemChanged.connect(self._renamed)
        self.list.currentCellChanged.connect(lambda *_: self._show_events())
        cv.addWidget(self.list)
        tables.addWidget(c, 3)

        c, cv = card()
        cv.setContentsMargins(0, 0, 0, 0)
        self.events = QTableWidget(0, 4)
        self.events.setHorizontalHeaderLabels(["Key", "Status", "delay", "Operation"])
        self._style_table(self.events)
        self.events.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.events.setColumnWidth(1, 90)
        self.events.setColumnWidth(2, 140)
        self.events.setColumnWidth(3, 90)
        self.events.setEditTriggers(QAbstractItemView.NoEditTriggers)
        cv.addWidget(self.events)
        tables.addWidget(c, 3)
        v.addLayout(tables, 1)

        self.status = label("Double-click a name to rename it. Recorded macros can be put on a key "
                            "in Advanced Key > Macro.", "note")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self._fill()

    @staticmethod
    def _style_table(t: QTableWidget):
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(44)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setShowGrid(False)
        t.setAlternatingRowColors(False)
        t.setMinimumHeight(460)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        t.setFocusPolicy(Qt.NoFocus)

    # ---- list ----

    def _selected(self) -> int | None:
        r = self.list.currentRow()
        return r if 0 <= r < len(self.macros) else None

    def _checked(self) -> list[int]:
        out = []
        for r in range(self.list.rowCount()):
            it = self.list.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                out.append(r)
        return out

    def _fill(self, select: int | None = None):
        self.list.blockSignals(True)
        self.list.setRowCount(len(self.macros))
        for r, m in enumerate(self.macros):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked)
            self.list.setItem(r, 0, chk)
            self.list.setItem(r, 1, QTableWidgetItem(m.get("name", f"Macro {r + 1}")))
            for col, text in ((2, m.get("created", "")), (3, str(len(m["events"])))):
                it = QTableWidgetItem(text)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.list.setItem(r, col, it)
        if self.macros:
            self.list.selectRow(min(select if select is not None else 0, len(self.macros) - 1))
        self.list.blockSignals(False)
        self._show_events()
        self._buttons()

    def _buttons(self):
        has = self._selected() is not None or bool(self._checked())
        self.btn_delete.setEnabled(has and not self.recording)
        self.btn_copy.setEnabled(self._selected() is not None and not self.recording)

    def _renamed(self, item: QTableWidgetItem):
        if item.column() == 1 and item.row() < len(self.macros):
            self.macros[item.row()]["name"] = item.text().strip() or f"Macro {item.row() + 1}"
            save_library(self.macros)

    def _delete(self):
        rows = self._checked() or ([self._selected()] if self._selected() is not None else [])
        if not rows:
            return
        names = ", ".join(self.macros[r].get("name", "") for r in rows)
        if not self.win.ask(f"Delete {names}?"):
            return
        for r in sorted(rows, reverse=True):
            del self.macros[r]
        save_library(self.macros)
        self._fill(min(rows))

    def _copy(self):
        r = self._selected()
        if r is None:
            return
        m = json.loads(json.dumps(self.macros[r]))
        m["name"] = f"{m.get('name', 'Macro')} copy"
        m["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.macros.insert(r + 1, m)
        save_library(self.macros)
        self._fill(r + 1)

    # ---- steps ----

    def _show_events(self):
        r = self._selected()
        events = self.macros[r]["events"] if r is not None else []
        self.events.setRowCount(0)   # drops the old row widgets
        self.events.setRowCount(len(events))
        for i, (code, pressed, delay) in enumerate(events):
            self.events.setItem(i, 0, QTableWidgetItem(key_name(code)))
            self.events.setItem(i, 1, QTableWidgetItem("press" if pressed else "release"))
            spin = QSpinBox()
            spin.setRange(1, 65535)
            spin.setSuffix(" ms")
            spin.setValue(int(delay))
            spin.valueChanged.connect(lambda val, i=i, r=r: self._set_delay(r, i, val))
            self.events.setCellWidget(i, 2, spin)
            rm = QPushButton("Delete")
            rm.setObjectName("link")
            rm.clicked.connect(lambda _=False, i=i, r=r: self._remove_event(r, i))
            self.events.setCellWidget(i, 3, rm)
        self._buttons()

    def _set_delay(self, r, i, val):
        self.macros[r]["events"][i][2] = val
        save_library(self.macros)

    def _remove_event(self, r, i):
        del self.macros[r]["events"][i]
        save_library(self.macros)
        self._fill(r)

    # ---- recording ----

    def _toggle_recording(self):
        if not self.recording:
            self.recording = True
            self._rec_events = []
            self._rec_last = 0.0
            self.btn_record.setText("■  Stop Recording")
            self.btn_record.setObjectName("dangerfill")
            self.status.setText("Recording: type the keys now (up to 30 presses), then press Stop Recording.")
        else:
            self.recording = False
            self.btn_record.setText("▸  Start Recording")
            self.btn_record.setObjectName("")
            if self._rec_events:
                self._rec_events[-1][2] = 10
                self.macros.append({"name": f"Macro {len(self.macros) + 1}",
                                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "events": self._rec_events})
                save_library(self.macros)
                self._fill(len(self.macros) - 1)
                self.status.setText("Saved. Double-click the name to rename it.")
            else:
                self.status.setText("Nothing was recorded.")
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self._buttons()

    def record_key(self, native_scan: int, pressed: bool):
        """Called by the window for every key press and release while recording."""
        code = usage_from_scan(native_scan)
        if code is None or len(self._rec_events) >= MAX_EVENTS:
            return
        now = time.perf_counter()
        if self._rec_events:
            # each step's delay is the wait before the next step
            self._rec_events[-1][2] = max(1, min(65535, round((now - self._rec_last) * 1000)))
        self._rec_events.append([code, pressed, 10])
        self._rec_last = now
        self.status.setText("Recording: " + " ".join(
            ("↓" if e[1] else "↑") + key_name(e[0]) for e in self._rec_events[-12:]))
