"""Auto Switch page: pick which onboard config each game uses; the app switches while it runs
(also from the tray)."""

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QPushButton,
                               QTableWidget, QVBoxLayout, QWidget)

from app import autoswitch as A
from kbui.widgets import card, label, row

from . import appsettings

OWN_EXES = {"openheconfig.exe", "python.exe", "pythonw.exe"}   # this app itself: never a reason to switch


class AutoSwitcher(QObject):
    """Watches the program in front once a second and switches the keyboard's config by the rules."""

    switched = Signal(int)          # config 1-4 the keyboard was just switched to
    status = Signal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.chooser = A.Chooser([], 0)
        self.timer = QTimer(self, interval=1000, timeout=self._check)
        self.busy = False
        self.last_exe = None
        self.reload()

    def reload(self):
        s = self.settings
        self.chooser = A.Chooser(s["auto_rules"], s["auto_default"])
        if s["auto_switch"] and (s["auto_rules"] or s["auto_default"]):
            self.timer.start()
        else:
            self.timer.stop()

    def _check(self):
        if self.busy:
            return
        exe = A.foreground_exe()
        own = (exe or "").lower() in OWN_EXES
        if exe != self.last_exe and not own:
            self.last_exe = exe
            want = self.chooser.target(exe)
            self.status.emit(f"In front: {exe or 'nothing'}" + (f", wants config {want}" if want else ""))
        want = self.chooser.tick(exe, own)
        if want:
            self._switch(want)

    def _switch(self, config: int):
        import threading
        self.busy = True

        def work():
            from app import backup as B
            from .link import Link
            link = Link()
            try:
                if link.open() and B.read_settings_config(link) != config - 1:
                    B.switch_config(link, config - 1)
                    self.switched.emit(config)
            except Exception as e:      # keyboard unplugged, busy: try again on the next change
                self.status.emit(f"Could not switch to config {config}: {e}")
                self.chooser.wanted = None
            finally:
                link.close()
                self.busy = False

        threading.Thread(target=work, name="auto-switch", daemon=True).start()


class AutoSwitchPage(QWidget):
    def __init__(self, switcher: AutoSwitcher, settings: dict):
        super().__init__()
        self.switcher, self.settings = switcher, settings
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(16)
        v.addWidget(label("Auto Switch", "bigheading"))

        c, cv = card()
        c.setMaximumWidth(720)
        t = label("Give each game its own onboard config. While the app runs (also from the tray), the keyboard "
                  "switches when the game comes to the front, and back when it does not.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        self.enable = QCheckBox("Switch configs automatically")
        self.enable.setChecked(settings["auto_switch"])
        self.enable.toggled.connect(self._enabled)
        cv.addWidget(self.enable)
        self.default = QComboBox()
        self.default.addItem("Leave it as it is", 0)
        for i in range(1, 5):
            self.default.addItem(f"Config {i}", i)
        self.default.setCurrentIndex(max(0, self.default.findData(settings["auto_default"])))
        self.default.activated.connect(self._changed)
        cv.addLayout(row("When no game below is in front", self.default))
        v.addWidget(c)

        c, cv = card()
        c.setMaximumWidth(720)
        cv.addWidget(label("Games", "heading"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Program", "Config", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 90)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setMinimumHeight(220)
        cv.addWidget(self.table)
        h = QHBoxLayout()
        self.pick = QComboBox()
        self.pick.setEditable(True)
        self.pick.setMinimumWidth(280)
        self.pick.lineEdit().setPlaceholderText("Game's program, e.g. TslGame.exe")
        h.addWidget(self.pick, 1)
        refresh = QPushButton("Running programs")
        refresh.clicked.connect(self._fill_running)
        h.addWidget(refresh)
        self.pick_cfg = QComboBox()
        for i in range(1, 5):
            self.pick_cfg.addItem(f"Config {i}", i)
        h.addWidget(self.pick_cfg)
        add = QPushButton("Add")
        add.setObjectName("save")
        add.setProperty("dirty", True)
        add.clicked.connect(self._add)
        h.addWidget(add)
        cv.addLayout(h)
        tip = label("Start the game first, then pick it from Running programs. The name is the game's .exe "
                    "file, for example TslGame.exe for PUBG.", "note")
        tip.setWordWrap(True)
        cv.addWidget(tip)
        v.addWidget(c)

        self.status = label("", "note")
        v.addWidget(self.status)
        v.addStretch()
        switcher.status.connect(self.status.setText)
        switcher.switched.connect(lambda c: self.status.setText(f"Switched the keyboard to config {c}."),
                                  Qt.QueuedConnection)
        self._fill_running()
        self._render()

    # ---------- table ----------

    def _render(self):
        rules = self.settings["auto_rules"]
        self.table.setRowCount(0)
        self.table.setRowCount(len(rules))
        for r, rule in enumerate(rules):
            self.table.setCellWidget(r, 0, label(rule["exe"], "value"))
            box = QComboBox()
            for i in range(1, 5):
                box.addItem(f"Config {i}", i)
            box.setCurrentIndex(rule["config"] - 1)
            box.activated.connect(lambda _=0, r=r, box=box: self._set_config(r, box.currentData()))
            self.table.setCellWidget(r, 1, box)
            rm = QPushButton("Remove")
            rm.setObjectName("link")
            rm.clicked.connect(lambda _=False, r=r: self._remove(r))
            self.table.setCellWidget(r, 2, rm)

    def _fill_running(self):
        current = self.pick.currentText()
        self.pick.clear()
        names = [n for n in A.windowed_programs() if n.lower() not in OWN_EXES | {"explorer.exe"}]
        self.pick.addItems(names)
        self.pick.setEditText(current)

    def _add(self):
        exe = self.pick.currentText().strip()
        if not exe:
            return
        if not exe.lower().endswith(".exe"):
            exe += ".exe"
        rules = [r for r in self.settings["auto_rules"] if r["exe"].lower() != exe.lower()]
        rules.append({"exe": exe, "config": self.pick_cfg.currentData()})
        self.settings["auto_rules"] = rules
        self.pick.setEditText("")
        self._changed()
        self._render()

    def _remove(self, r):
        del self.settings["auto_rules"][r]
        self._changed()
        self._render()

    def _set_config(self, r, config):
        self.settings["auto_rules"][r]["config"] = config
        self._changed()

    # ---------- saving ----------

    def _enabled(self, on):
        self.settings["auto_switch"] = on
        self._changed()

    def _changed(self, *_):
        self.settings["auto_default"] = self.default.currentData()
        appsettings.save(self.settings)
        self.switcher.reload()
        on = self.settings["auto_switch"]
        self.status.setText("Saved." + ("" if on else " Turn on \"Switch configs automatically\" to use it."))
