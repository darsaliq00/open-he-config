"""Keyboard map drawn as light keycaps with tag badges, for the light theme."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from app.widgets import KeyboardView

from . import theme

CAP = QColor("#f4f5f7")
CAP_EDGE = QColor("#cdd2da")
CAP_TOP = QColor("#ffffff")
LABEL = QColor("#2b3340")
BADGE = QColor(theme.ACCENT)
SELECT = QColor(theme.ACCENT)
PRESSED = QColor("#ffcf6e")
BED = QColor("#e9f3fb")


def _font(size, bold=False):
    f = QFont()
    f.setFamilies(["Segoe UI"])
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


class KeycapView(KeyboardView):
    UNIT, GAP, ROW_GAP, SPACER = 46, 4, 6, 16

    def __init__(self):
        super().__init__()
        self.setFixedSize(self._size.width() + 24, self._size.height() + 24)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(BED)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
        p.translate(12, 12)
        label_font, badge_font = _font(8.5), _font(6.5, True)
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
        pos.setX(pos.x() - 12)
        pos.setY(pos.y() - 12)
        for slot, _, r in self.rects:
            if r.contains(pos):
                self.selected.emit(slot)
                return

    def key_centres(self):
        return {s: (x + 12, y + 12, row) for s, (x, y, row) in super().key_centres().items()}
