"""Knob page: what the volume knob does, and how the app keeps running in the tray."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.knob import PRESS, TURN
from kbui.widgets import card, label, restyle, row

from . import appsettings


class KnobPage(QWidget):
    def __init__(self, remapper, settings: dict):
        super().__init__()
        self.remapper = remapper
        self.settings = settings
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(16)
        v.addWidget(label("Knob", "bigheading"))

        c, cv = card()
        c.setMaximumWidth(640)
        note = label("The knob is fixed in the keyboard's firmware to volume up / down and mute. This app "
                     "turns those into other actions on this PC while it runs (also from the tray). Other "
                     "volume keys and buttons, for example on a headset, are changed the same way.", "muted")
        note.setWordWrap(True)
        cv.addWidget(note)
        self.turn = QComboBox()
        for key, (text, *_rest) in TURN.items():
            self.turn.addItem(text, key)
        self.turn.setCurrentIndex(max(0, self.turn.findData(settings["knob_turn"])))
        self.turn.activated.connect(self._edited)
        cv.addLayout(row("Turn", self.turn))
        self.press = QComboBox()
        for key, (text, _a) in PRESS.items():
            self.press.addItem(text, key)
        self.press.setCurrentIndex(max(0, self.press.findData(settings["knob_press"])))
        self.press.activated.connect(self._edited)
        cv.addLayout(row("Press", self.press))
        h = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("save")
        self.btn_save.clicked.connect(self._changed)
        self.btn_revert = QPushButton("Revert")
        self.btn_revert.clicked.connect(self._revert)
        h.addWidget(self.btn_save)
        h.addWidget(self.btn_revert)
        h.addStretch()
        cv.addLayout(h)
        cv.addWidget(label("Saved in the app on this PC: the keyboard itself has no setting for the knob.",
                           "note"))
        v.addWidget(c)

        c, cv = card()
        c.setMaximumWidth(640)
        cv.addWidget(label("Background", "heading"))
        self.tray = QCheckBox("Keep running in the tray when the window is closed")
        self.tray.setChecked(settings["tray_on_close"])
        self.tray.toggled.connect(self._tray)
        cv.addWidget(self.tray)
        self.autostart = QCheckBox("Start with Windows (hidden in the tray)")
        self.autostart.setChecked(settings["start_with_windows"])
        self.autostart.setEnabled(appsettings.can_start_with_windows())
        self.autostart.toggled.connect(self._autostart)
        cv.addWidget(self.autostart)
        lite = label("In the tray the app stops reading the keyboard and redrawing; it only waits for knob "
                     "events, so it uses almost no CPU.", "note")
        lite.setWordWrap(True)
        cv.addWidget(lite)
        self.status = label("", "note")
        cv.addWidget(self.status)
        v.addWidget(c)
        v.addStretch()
        self._dirty(False)

    def _dirty(self, on: bool):
        self.btn_save.setEnabled(on)
        self.btn_revert.setEnabled(on)
        self.btn_save.setProperty("dirty", on)
        restyle(self.btn_save)

    def _edited(self, *_):
        s = self.settings
        self._dirty((self.turn.currentData(), self.press.currentData()) != (s["knob_turn"], s["knob_press"]))
        self.status.setText("Not saved yet.")

    def _revert(self):
        self.turn.setCurrentIndex(max(0, self.turn.findData(self.settings["knob_turn"])))
        self.press.setCurrentIndex(max(0, self.press.findData(self.settings["knob_press"])))
        self._dirty(False)
        self.status.setText("")

    def _changed(self, *_):
        s = self.settings
        s["knob_turn"], s["knob_press"] = self.turn.currentData(), self.press.currentData()
        appsettings.save(s)
        self.remapper.configure(s["knob_turn"], s["knob_press"])
        self._dirty(False)
        self.status.setText("Saved. The knob works this way now, also from the tray.")

    def _tray(self, on):
        self.settings["tray_on_close"] = on
        appsettings.save(self.settings)
        self.status.setText("Closing the window keeps the app in the tray." if on else
                            "Closing the window quits the app.")

    def _autostart(self, on):
        if appsettings.set_start_with_windows(on):
            self.settings["start_with_windows"] = on
            appsettings.save(self.settings)
            self.status.setText("Starts with Windows." if on else "No longer starts with Windows.")
        else:
            self.status.setText("Could not change the Windows startup entry.")
