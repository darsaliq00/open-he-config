"""Small widgets shared by the config apps."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget


def label(text: str, name: str = "") -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    return lb


def rule(vertical: bool = False) -> QFrame:
    f = QFrame()
    f.setObjectName("vrule" if vertical else "rule")
    return f


def restyle(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


def card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(18, 16, 18, 16)
    v.setSpacing(10)
    return f, v


def row(title: str, value: QWidget) -> QHBoxLayout:
    h = QHBoxLayout()
    h.addWidget(label(title, "muted"))
    h.addStretch()
    h.addWidget(value)
    return h


class SliderRow(QWidget):
    moved = Signal(float)

    def __init__(self, title: str, lo: float, hi: float, step: float, fmt):
        super().__init__()
        self.lo, self.step, self.fmt = lo, step, fmt
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.addWidget(label(title, "muted"))
        top.addStretch()
        self.value = label("", "value")
        top.addWidget(self.value)
        lay.addLayout(top)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, round((hi - lo) / step))
        self.slider.valueChanged.connect(self._changed)
        lay.addWidget(self.slider)

    def set(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(round((v - self.lo) / self.step))
        self.slider.blockSignals(False)
        self.value.setText(self.fmt(v))

    def _changed(self, i):
        v = round(self.lo + i * self.step, 3)
        self.value.setText(self.fmt(v))
        self.moved.emit(v)
