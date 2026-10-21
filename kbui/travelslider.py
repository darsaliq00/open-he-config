"""Slider with a millimetre box and -/+ buttons, laid out like RK's web driver. Emits `committed`
once the user lets go of the slider or finishes typing, not on every step."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QPushButton, QSlider, QVBoxLayout, QWidget

from .widgets import label


class TravelSlider(QWidget):
    committed = Signal(float)

    def __init__(self, title: str, text: str = "", lo: float = 0.1, hi: float = 3.3, step: float = 0.01,
                 decimals: int = 3):
        super().__init__()
        self.lo, self.hi, self.step = lo, hi, step
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        if title:
            v.addWidget(label(title, "heading"))
        if text:
            t = label(text, "muted")
            t.setWordWrap(True)
            v.addWidget(t)
        h = QHBoxLayout()
        h.setSpacing(8)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, round((hi - lo) / step))
        self.slider.valueChanged.connect(self._slid)
        self.slider.sliderReleased.connect(self._commit)
        h.addWidget(self.slider, 1)
        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        for b in (self.minus, self.plus):
            b.setFixedWidth(30)
        self.box = QDoubleSpinBox()
        self.box.setRange(lo, hi)
        self.box.setDecimals(decimals)
        self.box.setSingleStep(step)
        self.box.setSuffix(" mm")
        # own -/+ buttons; the spin arrows are hidden by the theme (NoButtons breaks styled spin boxes)
        self.box.setFixedWidth(124)
        self.box.setAlignment(Qt.AlignCenter)
        self.box.editingFinished.connect(self._typed)
        self.minus.clicked.connect(lambda: self._nudge(-1))
        self.plus.clicked.connect(lambda: self._nudge(1))
        h.addWidget(self.minus)
        h.addWidget(self.box)
        h.addWidget(self.plus)
        v.addLayout(h)
        self._value = lo

    def value(self) -> float:
        return self._value

    def set(self, value: float):
        self._value = max(self.lo, min(self.hi, value))
        for w in (self.slider, self.box):
            w.blockSignals(True)
        self.slider.setValue(round((self._value - self.lo) / self.step))
        self.box.setValue(self._value)
        for w in (self.slider, self.box):
            w.blockSignals(False)

    def _slid(self, i):
        self._value = round(self.lo + i * self.step, 3)
        self.box.blockSignals(True)
        self.box.setValue(self._value)
        self.box.blockSignals(False)
        if not self.slider.isSliderDown():   # keyboard or click on the groove
            self._commit()

    def _typed(self):
        v = round(self.box.value(), 3)
        if abs(v - self._value) > 1e-6:
            self.set(v)
            self._commit()

    def _nudge(self, direction):
        self.set(round(self._value + direction * self.step, 3))
        self._commit()

    def _commit(self):
        self.committed.emit(self._value)
