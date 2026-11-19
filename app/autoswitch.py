"""Switch the keyboard's onboard config to match the program in front (a game, say).

Rules map a program's file name (TslGame.exe) to a config 1-4. A program must stay in front for
a moment before the switch, so alt-tabbing past it does not flip the keyboard back and forth.
Windows only: it reads the foreground window's process with user32 / kernel32.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STABLE_TICKS = 2          # the same program in front for this many checks (about 1 s each)

if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    kernel32.OpenProcess.restype = wt.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]


def foreground_exe() -> str | None:
    """File name of the program owning the window in front, e.g. 'TslGame.exe'."""
    if os.name != "nt":
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return exe_of(pid.value)


def exe_of(pid: int) -> str | None:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(h)
    return None


def windowed_programs() -> list[str]:
    """File names of programs that have a visible window right now (to pick a game from)."""
    if os.name != "nt":
        return []
    names = set()
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            name = exe_of(pid.value)
            if name:
                names.add(name)
        return True

    user32.EnumWindows(WNDENUMPROC(each), 0)
    return sorted(names, key=str.lower)


class Chooser:
    """Decides which config the keyboard should be on, from the programs seen in front."""

    def __init__(self, rules: list[dict], default: int):
        self.rules = {r["exe"].lower(): int(r["config"]) for r in rules if r.get("exe")}
        self.default = int(default)      # 0 = leave the keyboard as it is when no rule matches
        self._last = None
        self._count = 0
        self.wanted: int | None = None   # config 1-4 last decided on

    def target(self, exe: str | None, own: bool = False) -> int | None:
        """Config the rules ask for while `exe` is in front (None = no change)."""
        if own or exe is None:
            return None                  # this app, the desktop or a locked screen: keep what we have
        return self.rules.get(exe.lower()) or (self.default or None)

    def tick(self, exe: str | None, own: bool = False) -> int | None:
        """Feed one check; returns a config to switch to once the program has stayed in front."""
        if exe != self._last:
            self._last, self._count = exe, 0
        self._count += 1
        want = self.target(exe, own)
        if want is None or self._count < STABLE_TICKS or want == self.wanted:
            return None
        self.wanted = want
        return want
