"""Key Health page: sensor check (at rest and full presses) and a press graph for one key."""

import threading
import time

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app import health as H
from app import protocol as p
from app.layout import RK_KEYS as KEYS
from kbui import theme
from kbui.widgets import card, label

REST_SECONDS = 2.0
FULL_SECONDS = 20.0
GRAPH_SECONDS = 3.0
FULL_MM = 4.0


class Bridge(QObject):
    progress = Signal(str)
    rest_done = Signal(object)
    full_done = Signal(object)
    graph_done = Signal(object)


class PressGraph(QWidget):
    """Travel over time, the actuation point, and where the keyboard sends press / release."""

    def __init__(self):
        super().__init__()
        self.trace: list[tuple[float, float]] = []
        self.events: list[tuple[float, bool]] = []
        self.actuation: float | None = None
        self.setMinimumSize(620, 260)

    def show_trace(self, trace, events, actuation):
        self.trace, self.events, self.actuation = trace, events, actuation
        self.update()

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        r = QRectF(48, 12, self.width() - 60, self.height() - 40)
        qp.setPen(QPen(QColor(theme.LINE), 1))
        qp.setBrush(QColor("#fafbfc"))
        qp.drawRoundedRect(r, 6, 6)
        f = QFont()
        f.setFamilies(["Segoe UI"])
        f.setPointSizeF(8)
        qp.setFont(f)
        span = max(GRAPH_SECONDS, self.trace[-1][0]) if self.trace else GRAPH_SECONDS
        x_of = lambda t: r.left() + r.width() * t / span
        y_of = lambda mm: r.top() + r.height() * min(FULL_MM, max(0.0, mm)) / FULL_MM
        for mm in range(int(FULL_MM) + 1):
            y = y_of(mm)
            qp.setPen(QPen(QColor(theme.LINE), 1))
            qp.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            qp.setPen(QColor(theme.MUTED))
            qp.drawText(QRectF(0, y - 8, 42, 16), Qt.AlignRight | Qt.AlignVCenter, f"{mm} mm")
        for s in range(int(span) + 1):
            qp.drawText(QRectF(x_of(s) - 20, r.bottom() + 4, 40, 16), Qt.AlignCenter, f"{s} s")
        # pressed spans
        down_at = None
        for t, pressed in self.events + [(span, False)]:
            if pressed and down_at is None:
                down_at = t
            elif not pressed and down_at is not None:
                qp.setPen(Qt.NoPen)
                qp.setBrush(QColor(34, 160, 107, 40))
                qp.drawRect(QRectF(x_of(down_at), r.top(), x_of(t) - x_of(down_at), r.height()))
                down_at = None
        if self.actuation is not None:
            qp.setPen(QPen(QColor(theme.DANGER), 1.5, Qt.DashLine))
            y = y_of(self.actuation)
            qp.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        if self.trace:
            path = QPainterPath(QPointF(x_of(self.trace[0][0]), y_of(self.trace[0][1])))
            for t, mm in self.trace[1:]:
                path.lineTo(x_of(t), y_of(mm))
            qp.setPen(QPen(QColor(theme.ACCENT), 2))
            qp.setBrush(Qt.NoBrush)
            qp.drawPath(path)
        for t, pressed in self.events:
            qp.setPen(QPen(QColor(theme.OK if pressed else theme.DANGER), 1.5))
            qp.drawLine(QPointF(x_of(t), r.top()), QPointF(x_of(t), r.bottom()))
        if not self.trace:
            qp.setPen(QColor(theme.FAINT))
            qp.drawText(r, Qt.AlignCenter, "Pick a key, click Record, then press it a few times.")


class HealthPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.bridge = Bridge()
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(16)
        v.addWidget(label("Key Health", "bigheading"))

        c, cv = card()
        c.setMaximumWidth(760)
        cv.addWidget(label("Sensor check", "heading"))
        t = label("Finds keys that read pressed while untouched (they can press themselves with a light actuation "
                  "or rapid trigger) and keys that never get to the bottom.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        h = QHBoxLayout()
        self.btn_rest = QPushButton("Check at rest (hands off)")
        self.btn_rest.setObjectName("save")
        self.btn_rest.setProperty("dirty", True)
        self.btn_rest.clicked.connect(self.check_rest)
        self.btn_full = QPushButton(f"Check full presses ({FULL_SECONDS:.0f} s)")
        self.btn_full.clicked.connect(self.check_full)
        h.addWidget(self.btn_rest)
        h.addWidget(self.btn_full)
        h.addStretch()
        cv.addLayout(h)
        self.results = QVBoxLayout()
        self.results.setSpacing(6)
        cv.addLayout(self.results)
        v.addWidget(c)

        c, cv = card()
        c.setMaximumWidth(760)
        cv.addWidget(label("Press graph", "heading"))
        t = label("Records one key for 3 seconds at about 500 readings a second. Green bands show when the "
                  "keyboard sends the key as pressed; the dashed red line is its actuation point.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        h = QHBoxLayout()
        self.key_pick = QComboBox()
        for slot, k in sorted(KEYS.items(), key=lambda kv: kv[0]):
            self.key_pick.addItem(k["label"], slot)
        self.key_pick.setCurrentIndex(max(0, self.key_pick.findText("W")))
        h.addWidget(label("Key", "muted"))
        h.addWidget(self.key_pick)
        self.btn_graph = QPushButton("Record")
        self.btn_graph.clicked.connect(self.record)
        h.addWidget(self.btn_graph)
        h.addStretch()
        cv.addLayout(h)
        self.graph = PressGraph()
        cv.addWidget(self.graph)
        self.graph_info = label("", "note")
        self.graph_info.setWordWrap(True)
        cv.addWidget(self.graph_info)
        v.addWidget(c)

        self.status = label("", "note")
        v.addWidget(self.status)
        v.addStretch()
        self.bridge.progress.connect(self.status.setText)
        self.bridge.rest_done.connect(self._rest_done)
        self.bridge.full_done.connect(self._full_done)
        self.bridge.graph_done.connect(self._graph_done)

    # ---------- sampling ----------

    def _ready(self) -> bool:
        if not self.win.settings or self.win.busy or not self.win.link.connected:
            self.status.setText("Connect the keyboard and wait for it to be read first.")
            return False
        return True

    def _sample(self, seconds: float, pages=(1, 2), on_values=None):
        """Read travel pages for `seconds`; on_values(slot_base, values, t) for each page read."""
        link, t0 = self.win.link, time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            for page in pages:
                vals = link.diag(p.DIAG_TRAVEL, page)
                if vals:
                    on_values((page - 1) * 63, vals, time.perf_counter() - t0)

    def _run(self, job):
        """Run job() on a thread with the window's own live reading paused."""
        self.win.busy = True
        for b in (self.btn_rest, self.btn_full, self.btn_graph):
            b.setEnabled(False)
        was = self.win._live_on
        self.win._live_on = False

        def target():
            try:
                job()
            finally:
                self.win._live_on = was
                self.win.busy = False

        threading.Thread(target=target, name="key-health", daemon=True).start()

    def _done_buttons(self):
        for b in (self.btn_rest, self.btn_full, self.btn_graph):
            b.setEnabled(True)

    def _clear_results(self):
        while self.results.count():
            w = self.results.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _show(self, findings, ok_text):
        self._clear_results()
        if not findings:
            self.results.addWidget(label(ok_text, "chip"))
        for f in findings:
            name = KEYS.get(f["slot"], {}).get("label", f"slot {f['slot']}")
            lb = label(f"{name}: {f['text']}", "warn" if f["level"] == "danger" else "muted")
            lb.setWordWrap(True)
            self.results.addWidget(lb)

    # ---------- sensor check ----------

    def check_rest(self):
        if not self._ready():
            return
        self.status.setText("Hands off the keyboard… reading for 2 seconds.")
        samples: dict[int, list[float]] = {s: [] for s in KEYS}

        def keep(base, vals, _t):
            for i, v in enumerate(vals):
                if base + i in samples:
                    samples[base + i].append(v / 1000)

        def job():
            time.sleep(0.5)       # time to lift the hands after the click
            self._sample(REST_SECONDS, on_values=keep)
            self.bridge.rest_done.emit(samples)

        self._run(job)

    def _rest_done(self, samples):
        self._done_buttons()
        s = self.win.settings
        findings = H.check_rest(samples, s["keys"], s["global"]["actuation_mm"])
        self._show(findings, "Every key reads about 0 mm at rest.")
        self.status.setText(f"Checked {len(samples)} keys at rest.")

    def check_full(self):
        if not self._ready():
            return
        self.status.setText(f"Press every key you use all the way down, one after another ({FULL_SECONDS:.0f} s)…")
        maximum: dict[int, float] = {}
        state = {"next": 0.0}

        def keep(base, vals, t):
            for i, v in enumerate(vals):
                slot = base + i
                if slot in KEYS and v / 1000 > maximum.get(slot, 0.0):
                    maximum[slot] = v / 1000
            if t > state["next"]:
                state["next"] = t + 1.0
                touched = sum(1 for m in maximum.values() if m > 1.0)
                self.bridge.progress.emit(f"{FULL_SECONDS - t:.0f} s left · {touched} keys pressed so far")

        def job():
            self._sample(FULL_SECONDS, on_values=keep)
            self.bridge.full_done.emit(maximum)

        self._run(job)

    def _full_done(self, maximum):
        self._done_buttons()
        pressed = {s for s, m in maximum.items() if m > 1.0}
        findings = H.check_bottom(maximum, pressed)
        self._show(findings, f"All {len(pressed)} pressed keys reached the bottom.")
        self.status.setText(f"{len(pressed)} keys were pressed during the check.")

    # ---------- press graph ----------

    def record(self):
        if not self._ready():
            return
        slot = self.key_pick.currentData()
        page = 1 if slot < 63 else 2
        idx = slot - (page - 1) * 63
        trace: list[tuple[float, float]] = []
        self.status.setText(f"Recording {self.key_pick.currentText()}: press it a few times…")

        def keep(base, vals, t):
            trace.append((t, vals[idx] / 1000))

        def job():
            self._sample(GRAPH_SECONDS, pages=(page,), on_values=keep)
            self.bridge.graph_done.emit((slot, trace))

        self._run(job)

    def _graph_done(self, result):
        self._done_buttons()
        slot, trace = result
        s = self.win.settings
        k = s["keys"].get(slot, {})
        g = s["global"]["actuation_mm"]
        touch = k.get("mode", {}).get("touch", "global")
        act = g if touch == "global" else k.get("actuation", g)
        events = H.simulate(trace, k, g)
        self.graph.show_trace(trace, events, act)
        presses = sum(1 for _, pressed in events if pressed)
        rate = len(trace) / GRAPH_SECONDS
        mode = {"rt": f"rapid trigger ({k.get('rt_press', 0):g} / {k.get('rt_release', 0):g} mm)",
                "single": "own actuation", "global": "global actuation"}[touch]
        deepest = max((x for _, x in trace), default=0)
        self.graph_info.setText(f"{self.key_pick.currentText()}: {mode} at {act:.2f} mm · sent {presses} press(es) · "
                                f"deepest {deepest:.2f} mm · {rate:.0f} readings/s")
        self.status.setText("")
