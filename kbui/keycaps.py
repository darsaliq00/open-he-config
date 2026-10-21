"""Keyboard map drawn as light keycaps with tag badges, for the light theme."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme

CAP = QColor("#f4f5f7")
CAP_EDGE = QColor("#cdd2da")
CAP_TOP = QColor("#ffffff")
LABEL = QColor("#2b3340")
BADGE = QColor(theme.ACCENT)
SELECT = QColor(theme.ACCENT)
PRESSED = QColor("#ffcf6e")
BED = QColor("#e9f3fb")
LIVE = QColor("#e8590c")           # live travel readout
VALUE_TOP = QColor("#1f9d55")       # actuation (green, like RK's web driver)
VALUE_PRESS = QColor("#2563eb")     # rapid trigger press (blue)
VALUE_RELEASE = QColor("#ea580c")   # rapid trigger release (orange)


def _font(size, bold=False):
    f = QFont()
    f.setFamilies(["Segoe UI"])
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


class KeycapView(QWidget):
    """rows: list of rows of (slot, label, width in units, scan code) or None for a gap."""

    selected = Signal(int)
    UNIT, GAP, ROW_GAP, SPACER, PAD = 46, 4, 6, 16, 12

    def __init__(self, rows):
        super().__init__()
        self.depth: dict[int, float] = {}
        self.targets: dict[int, str] = {}       # tag badge per key
        self.swatches: dict[int, QColor] = {}   # colour strip per key
        self.leds: dict[int, QColor] = {}       # lit key face (lighting preview)
        self.values: dict[int, tuple] = {}      # (top, bottom-left, bottom-right) numbers, RK web style
        self.live_mm: dict[int, float] = {}     # live travel of pressed keys, drawn on the keycap
        self.current: int | None = None
        self.selection: set[int] = set()
        self.rects: list[tuple[int, str, QRectF]] = []
        self._row_of: dict[int, int] = {}
        y = 1.0
        for r, row in enumerate(rows):
            x = 1.0
            for k in row:
                if k is None:
                    x += self.SPACER
                    continue
                slot, text, w = k[0], k[1], k[2]
                width = w * self.UNIT + (w - 1) * self.GAP
                self.rects.append((slot, text, QRectF(x, y, width, self.UNIT)))
                self._row_of[slot] = r
                x += width + self.GAP
            y += self.UNIT + self.ROW_GAP + (6 if r == 0 and len(rows) > 5 else 0)
        size = QSize(int(max(rc.right() for *_, rc in self.rects)) + 2, int(y))
        self.setFixedSize(size.width() + 2 * self.PAD, size.height() + 2 * self.PAD)
        self.setCursor(Qt.PointingHandCursor)

    def _set(self, name, value):
        if getattr(self, name) != value:
            setattr(self, name, value)
            self.update()

    def set_depth(self, depth):
        self._set("depth", depth)

    def set_targets(self, targets):
        self._set("targets", targets)

    def set_swatches(self, swatches):
        self._set("swatches", swatches)

    def set_live(self, live_mm):
        """slot -> current travel in mm for keys being pressed (empty dict clears)."""
        self._set("live_mm", live_mm)

    def set_values(self, values):
        """slot -> (top text, bottom-left text, bottom-right text); any may be empty."""
        self._set("values", values)

    def set_leds(self, leds):
        self._set("leds", leds)

    def set_current(self, slot):
        self._set("current", slot)

    def set_selection(self, slots):
        self._set("selection", set(slots))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(BED)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
        p.translate(self.PAD, self.PAD)
        label_font, badge_font, value_font = _font(8.5), _font(6.5, True), _font(6, True)
        for slot, label, r in self.rects:
            d = self.depth.get(slot, 0.0)
            led = self.leds.get(slot)
            sink = 2 * min(1.0, d * 3)
            # keycap: darker base, lighter top face that sinks while pressed
            p.setPen(Qt.NoPen)
            p.setBrush(CAP_EDGE)
            p.drawRoundedRect(r, 5, 5)
            top = QRectF(r.left() + 2, r.top() + 1 + sink, r.width() - 4, r.height() - 6)
            face = CAP_TOP
            if led is not None and led.value() > 8:
                face = QColor(led)
                face.setAlpha(min(255, 90 + led.value()))
            elif d > 0.05:
                face = PRESSED
            p.setBrush(CAP)
            p.drawRoundedRect(top.adjusted(0, 0, 0, 2), 4, 4)
            p.setBrush(face)
            p.drawRoundedRect(top, 4, 4)
            sw = self.swatches.get(slot)
            if sw is not None:
                p.setBrush(sw)
                p.drawRoundedRect(QRectF(top.left() + 5, top.bottom() - 5, top.width() - 10, 3), 1, 1)
            if slot == self.current or slot in self.selection:
                p.setPen(QPen(SELECT, 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)
            p.setFont(label_font)
            light_face = led is not None and led.lightness() < 110 and led.value() > 8
            p.setPen(QColor("white") if light_face else LABEL)
            text_rect = QRectF(top.left(), top.top() + 4, top.width(), top.height() - 4)
            p.drawText(text_rect, Qt.AlignCenter, label)
            live = self.live_mm.get(slot)
            if live is not None:
                # travel bar down the right edge and the depth in mm over the key face
                bar = QRectF(top.right() - 5, top.top() + 3, 3, top.height() - 6)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 170))
                p.drawRoundedRect(bar, 1.5, 1.5)
                fill = QRectF(bar.left(), bar.top(), bar.width(), bar.height() * min(1.0, live / 4.0))
                p.setBrush(LIVE)
                p.drawRoundedRect(fill, 1.5, 1.5)
                tag_r = QRectF(top.left() + 2, top.bottom() - 13, top.width() - 9, 12)
                p.setBrush(LIVE)
                p.drawRoundedRect(tag_r, 3, 3)
                p.setFont(badge_font)
                p.setPen(QColor("white"))
                p.drawText(tag_r, Qt.AlignCenter, f"{live:.2f}mm")
            vals = self.values.get(slot) if live is None else None
            if vals:
                p.setFont(value_font)
                top_t, bl, br = (tuple(vals) + ("", "", ""))[:3]
                if top_t:
                    p.setPen(VALUE_TOP)
                    p.drawText(QRectF(top.left() + 3, top.top(), top.width() - 6, 10), Qt.AlignLeft | Qt.AlignTop, top_t)
                if bl:
                    p.setPen(VALUE_PRESS)
                    p.drawText(QRectF(top.left() + 3, top.bottom() - 10, top.width() / 2, 10),
                               Qt.AlignLeft | Qt.AlignBottom, bl)
                if br:
                    p.setPen(VALUE_RELEASE)
                    p.drawText(QRectF(top.center().x(), top.bottom() - 10, top.width() / 2 - 3, 10),
                               Qt.AlignRight | Qt.AlignBottom, br)
            tag = self.targets.get(slot)
            if tag:
                p.setFont(badge_font)
                w = min(top.width() - 4, p.fontMetrics().horizontalAdvance(tag) + 8)
                b = QRectF(top.center().x() - w / 2, top.top() + 1, w, 11)
                p.setPen(Qt.NoPen)
                p.setBrush(BADGE)
                p.drawRoundedRect(b, 3, 3)
                p.setPen(QColor("white"))
                p.drawText(b, Qt.AlignCenter, tag)

    def mousePressEvent(self, e):
        pos = e.position()
        pos.setX(pos.x() - self.PAD)
        pos.setY(pos.y() - self.PAD)
        for slot, _, r in self.rects:
            if r.contains(pos):
                self.selected.emit(slot)
                return

    def key_centres(self) -> dict[int, tuple[float, float, int]]:
        """slot -> (x, y, row) of each key's centre, for effects that move across the board."""
        return {s: (r.center().x() + self.PAD, r.center().y() + self.PAD, self._row_of[s]) for s, _, r in self.rects}
