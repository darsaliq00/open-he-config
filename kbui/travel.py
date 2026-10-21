"""Travel Test card: live key depth on a 0-4 mm ruler, like RK's web driver shows it."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QVBoxLayout, QWidget

from . import theme
from .widgets import card, label

FULL_MM = 4.0


class Switch(QAbstractButton):
    """Small on/off toggle."""

    def __init__(self, on: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(on)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(38, 20)

    def sizeHint(self):
        return QSize(38, 20)

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor(theme.ACCENT if on else "#9aa3b1"))
        qp.drawRoundedRect(QRectF(0, 3, 38, 14), 7, 7)
        qp.setBrush(QColor("white"))
        qp.setPen(QPen(QColor("#d5dae2"), 1))
        x = 19 if on else 0
        qp.drawEllipse(QRectF(x + 0.5, 0.5, 19, 19))


class TravelGauge(QWidget):
    """Vertical bar filled to the key depth, ruler with 0.1 mm ticks and a label every 1.0 mm."""

    TOP, BOTTOM = 14, 14

    def __init__(self):
        super().__init__()
        self.mm = 0.0
        self.actuation: float | None = None
        self.release: float | None = None
        self.setFixedSize(190, 290)

    def set_values(self, mm: float, actuation: float | None = None, release: float | None = None):
        if (mm, actuation, release) != (self.mm, self.actuation, self.release):
            self.mm, self.actuation, self.release = mm, actuation, release
            self.update()

    def _y(self, mm: float) -> float:
        h = self.height() - self.TOP - self.BOTTOM
        return self.TOP + h * max(0.0, min(FULL_MM, mm)) / FULL_MM

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        # bar
        bar = QRectF(8, self._y(0) - 8, 30, self._y(FULL_MM) - self._y(0) + 16)
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor("#eef1f6"))
        qp.drawRoundedRect(bar, 15, 15)
        if self.mm > 0.01:
            fill = QRectF(bar.left(), bar.top(), bar.width(), max(bar.width(), self._y(self.mm) - bar.top()))
            qp.setBrush(QColor(theme.ACCENT))
            qp.drawRoundedRect(fill.intersected(bar), 15, 15)
        # ruler
        x0 = 54
        qp.setPen(QPen(QColor("#2b3340"), 1.6))
        for i in range(int(FULL_MM * 10) + 1):
            y = self._y(i / 10)
            major = i % 10 == 0
            half = i % 5 == 0
            qp.drawLine(int(x0), int(y), int(x0 + (46 if major else 22 if half else 16)), int(y))
        f = QFont()
        f.setFamilies(["Segoe UI"])
        f.setPointSizeF(9)
        f.setBold(True)
        qp.setFont(f)
        for mm in range(int(FULL_MM) + 1):
            y = self._y(mm)
            qp.drawText(QRectF(x0 + 52, y - 9, 70, 18), Qt.AlignLeft | Qt.AlignVCenter, f"{mm:.1f}mm")
        # actuation / release markers
        for value, colour in ((self.actuation, theme.DANGER), (self.release, theme.OK)):
            if value is not None and 0 < value <= FULL_MM:
                y = self._y(value)
                qp.setPen(QPen(QColor(colour), 2))
                qp.drawLine(int(bar.left() - 4), int(y), int(x0 + 46), int(y))


class TravelTestCard(QWidget):
    """Card: title, on/off switch, gauge, and the key being shown with its depth."""

    toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        c, v = card()
        h = QHBoxLayout()
        h.addWidget(label("Travel Test", "heading"))
        h.addStretch()
        self.switch = Switch(False)
        self.switch.toggled.connect(self._toggled)
        h.addWidget(self.switch)
        v.addLayout(h)
        self.gauge = TravelGauge()
        v.addWidget(self.gauge, 0, Qt.AlignHCenter)
        self.readout = label("Switch on, then press a key.", "muted")
        self.readout.setAlignment(Qt.AlignCenter)
        v.addWidget(self.readout)
        self.legend = label("red line: actuation point of this key", "note")
        self.legend.setAlignment(Qt.AlignCenter)
        v.addWidget(self.legend)
        outer.addWidget(c)
        self.setFixedWidth(260)
        self._toggled(False)

    @property
    def on(self) -> bool:
        return self.switch.isChecked()

    def _toggled(self, on: bool):
        self.gauge.setEnabled(on)
        self.legend.setVisible(on)
        if not on:
            self.gauge.set_values(0.0)
            self.readout.setText("Switch on, then press a key.")
        self.toggled.emit(on)

    def show_key(self, name: str | None, mm: float, actuation=None, release=None):
        if not self.on:
            return
        self.gauge.set_values(mm, actuation, release)
        self.readout.setText(f"{name}  {mm:.2f} mm" if name else "Press a key.")
