"""App-wide options kept by the app (not the keyboard): knob remap, tray, start with Windows."""

import json
import sys

from app.paths import data_dir

DEFAULTS = {"knob_turn": "volume", "knob_press": "mute", "tray_on_close": True, "start_with_windows": False}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Open HE Config"


def _file():
    return data_dir() / "app_settings.json"


def load() -> dict:
    try:
        data = json.loads(_file().read_text())
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def save(settings: dict):
    try:
        _file().write_text(json.dumps(settings, indent=1))
    except OSError:
        pass


def can_start_with_windows() -> bool:
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def set_start_with_windows(on: bool) -> bool:
    """Adds or removes the app (started hidden in the tray) in the user's Run key. Returns success."""
    if not can_start_with_windows():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" --tray')
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
