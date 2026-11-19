"""Backup page: save the keyboard's configs to a file, load them back, share a setup."""

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QInputDialog, QPushButton, QVBoxLayout, QWidget

from app import backup as B
from app.kbconfig import read_settings
from app.paths import data_dir
from kbui.widgets import card, label


def _macro_copies() -> dict:
    try:
        return json.loads((data_dir() / "macros.json").read_text())
    except (OSError, ValueError):
        return {}


class BackupPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 0)
        v.setSpacing(16)
        v.addWidget(label("Backup", "bigheading"))

        c, cv = card()
        c.setMaximumWidth(720)
        cv.addWidget(label("Save to a file", "heading"))
        t = label("Saves everything a config holds: actuation, rapid trigger, dead zones, switch type, remaps on "
                  "all Fn layers, advanced keys, macros and lighting. Use it as a backup before a factory reset, "
                  "or send the file to a friend with the same keyboard.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        h = QHBoxLayout()
        self.btn_one = QPushButton("Save this config…")
        self.btn_one.setObjectName("save")
        self.btn_one.setProperty("dirty", True)
        self.btn_one.clicked.connect(self.save_current)
        self.btn_all = QPushButton("Back up all 4 configs…")
        self.btn_all.clicked.connect(self.save_all)
        h.addWidget(self.btn_one)
        h.addWidget(self.btn_all)
        h.addStretch()
        cv.addLayout(h)
        n = label("Backing up all 4 switches the keyboard through each config for a second and then back.", "note")
        n.setWordWrap(True)
        cv.addWidget(n)
        v.addWidget(c)

        c, cv = card()
        c.setMaximumWidth(720)
        cv.addWidget(label("Load from a file", "heading"))
        t = label("Restores a saved config. Only settings that differ are written, and each one is read back to "
                  "check it.", "muted")
        t.setWordWrap(True)
        cv.addWidget(t)
        h = QHBoxLayout()
        self.btn_load = QPushButton("Load from file…")
        self.btn_load.clicked.connect(self.load)
        h.addWidget(self.btn_load)
        h.addStretch()
        cv.addLayout(h)
        n = label("Macro steps are only in the file if the macro was made with this app (the keyboard cannot "
                  "report them); other macro keys are left as they are.", "note")
        n.setWordWrap(True)
        cv.addWidget(n)
        v.addWidget(c)

        self.status = label("", "note")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        v.addStretch()

    # ---------- helpers ----------

    def _say(self, text):
        self.status.setText(text)

    def _default_name(self, what: str) -> str:
        s = self.win.settings or {}
        name = (s.get("name") or "keyboard").replace(" ", "-")
        return str(Path.home() / f"{name}-{what}-{datetime.now():%Y-%m-%d}.ohe.json")

    def _ready(self) -> bool:
        if not self.win.settings or self.win.busy:
            self._say("Connect the keyboard and wait for it to be read first.")
            return False
        return True

    def _progress(self, text):
        self.win.bridge.done.emit(lambda _: self._say(text), None)

    # ---------- save ----------

    def save_current(self):
        if not self._ready():
            return
        cfg = self.win.settings["system"]["config"] + 1
        path, _ = QFileDialog.getSaveFileName(self, "Save config", self._default_name(f"config{cfg}"),
                                              "Open HE Config backup (*.ohe.json)")
        if not path:
            return
        self._say("Reading the config…")

        def work(req):
            s = read_settings(req)
            data = B.header(s, {str(cfg): B.capture(req, _macro_copies(), s)})
            B.save(path, data)
            return path

        self.win.run(work, lambda r: self._say(f"Failed: {r}" if isinstance(r, Exception) else
                                               f"Saved config {cfg} to {r}"))

    def save_all(self):
        if not self._ready():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Back up all configs", self._default_name("all-configs"),
                                              "Open HE Config backup (*.ohe.json)")
        if not path:
            return
        self._say("Reading all four configs…")

        def work(_req):
            data = B.capture_all(self.win.link, _macro_copies(), self._progress)
            B.save(path, data)
            return path

        def done(r):
            self._say(f"Failed: {r}" if isinstance(r, Exception) else f"Saved all four configs to {r}")
            self.win.read(force=True)

        self.win.run(work, done)

    # ---------- load ----------

    def load(self):
        if not self._ready():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load config", str(Path.home()),
                                              "Open HE Config backup (*.ohe.json *.json)")
        if not path:
            return
        try:
            data = B.load(path)
        except (OSError, ValueError) as e:
            self._say(f"Could not read the file: {e}")
            return
        s = self.win.settings
        configs = sorted(data["configs"], key=int)
        here = s["system"]["config"] + 1
        kb = data.get("keyboard", {})
        other = kb.get("name") and kb.get("name") != s["name"]
        if len(configs) == 1:
            choice = (configs[0], "here")
        else:
            items = [f"All {len(configs)} configs, each into its own slot"] + \
                    [f"Config {c} from the file, into the current config ({here})" for c in configs]
            item, ok = QInputDialog.getItem(self, "Load configs", "What to restore:", items, 0, False)
            if not ok:
                return
            choice = ("all", None) if items.index(item) == 0 else (configs[items.index(item) - 1], "here")
        warn = f"\n\nThis file is from a {kb['name']}, not a {s['name']}." if other else ""
        if choice[0] == "all":
            question = f"Restore all {len(configs)} configs from the file? Each config slot is replaced.{warn}"
        else:
            pl = B.plan(data["configs"][choice[0]], s)
            question = (f"Restore config {choice[0]} from the file into config {here}?\n\n"
                        f"It changes: {B.summary(pl)}.{warn}")
        if not self.win.ask(question):
            return
        if choice[0] == "all":
            self._restore_all(data)
        else:
            self._restore_one(data["configs"][choice[0]])

    def _restore_one(self, snapshot):
        self._say("Restoring…")

        def work(req):
            return B.restore(req, snapshot, read_settings(req), self._progress)

        def done(r):
            self._say(f"Restore failed: {r}" if isinstance(r, Exception) else
                      f"Restored and checked: {B.summary(r)}.")
            self.win.read(force=True)

        self.win.run(work, done)

    def _restore_all(self, data):
        self._say("Restoring all configs…")
        link = self.win.link

        def work(_req):
            start = read_settings(link.request)["system"]["config"]
            done_cfgs = []
            try:
                for c in sorted(data["configs"], key=int):
                    i = int(c) - 1
                    self._progress(f"Config {c}: switching…")
                    if B.read_settings_config(link) != i:
                        B.switch_config(link, i)
                    B.restore(link.request, data["configs"][c], read_settings(link.request),
                              lambda t, c=c: self._progress(f"Config {c}: {t}"))
                    done_cfgs.append(c)
            finally:
                if B.read_settings_config(link) != start:
                    B.switch_config(link, start)
            return done_cfgs

        def done(r):
            self._say(f"Restore failed: {r}" if isinstance(r, Exception) else
                      f"Restored configs {', '.join(r)} and checked them.")
            self.win.read(force=True)

        self.win.run(work, done)
