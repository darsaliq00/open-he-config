"""Key Stats page: a heatmap of how often each key is pressed (counted only when switched on)."""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.layout import RK_KEYS as KEYS, RK_ROWS
from kbui.keycaps import KeycapView
from kbui.widgets import card, label

from . import appsettings


def heat(f: float) -> QColor:
    """0..1 to a cool-to-hot colour (blue, green, yellow, red)."""
    stops = [(0.0, (219, 234, 254)), (0.35, (134, 239, 172)), (0.7, (253, 224, 71)), (1.0, (248, 113, 113))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if f <= b:
            t = (f - a) / (b - a) if b > a else 0
            return QColor(*(round(x + (y - x) * t) for x, y in zip(ca, cb)))
    return QColor(*stops[-1][1])


class StatsPage(QWidget):
    def __init__(self, counter, settings: dict):
        super().__init__()
        self.counter, self.settings = counter, settings
        self.slot_of_scan = {k["scan"]: s for s, k in KEYS.items() if k.get("scan")}
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(16)
        v.addWidget(label("Key Stats", "bigheading"))

        c, cv = card()
        t = label("Counts how many times each key is pressed, while the app runs (also from the tray). Only the "
                  "totals per key are kept on this PC: not what you type, not in what order.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        h = QHBoxLayout()
        self.enable = QCheckBox("Count key presses")
        self.enable.setChecked(settings.get("key_stats", False))
        self.enable.toggled.connect(self._enabled)
        h.addWidget(self.enable)
        h.addStretch()
        reset = QPushButton("Reset counts")
        reset.setObjectName("danger")
        reset.clicked.connect(self._reset)
        h.addWidget(reset)
        cv.addLayout(h)
        self.view = KeycapView(RK_ROWS)
        cv.addWidget(self.view, 0, Qt.AlignHCenter)
        self.summary = label("", "muted")
        self.summary.setWordWrap(True)
        cv.addWidget(self.summary)
        v.addWidget(c)
        v.addStretch()
        self.timer = QTimer(self, interval=1000, timeout=self.render)

    def showEvent(self, e):
        self.render()
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _enabled(self, on: bool):
        self.settings["key_stats"] = on
        appsettings.save(self.settings)
        if on:
            self.counter.start()
        else:
            self.counter.stop()
        self.render()

    def _reset(self):
        self.counter.reset()
        self.render()

    def render(self):
        per_slot: dict[int, int] = {}
        for scan, n in list(self.counter.counts.items()):   # the hook thread may be adding
            slot = self.slot_of_scan.get(scan)
            if slot is not None:
                per_slot[slot] = per_slot.get(slot, 0) + n
        top = max(per_slot.values(), default=0)
        self.view.set_leds({s: heat(n / top) for s, n in per_slot.items()} if top else {})
        self.view.set_values({s: (f"{n:,}", "", "") for s, n in per_slot.items()})
        total = sum(per_slot.values())
        best = sorted(per_slot.items(), key=lambda kv: -kv[1])[:8]
        since = datetime.fromtimestamp(self.counter.since).strftime("%d %b %Y")
        on = self.counter.running
        if not total:
            self.summary.setText("No presses counted yet." + ("" if on else " Switch on Count key presses."))
            return
        self.summary.setText(f"{total:,} presses since {since}{'' if on else ' (counting is off)'}. Most used: "
                             + ", ".join(f"{KEYS[s]['label']} {n * 100 / total:.0f}%" for s, n in best))
