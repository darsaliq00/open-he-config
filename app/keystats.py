"""Key press counts for the heatmap, from a Windows low-level keyboard hook.

Only how many times each physical key went down is kept (by scan code): no order, no timing, no
text. The hook thread sleeps until a key event arrives, so it costs nothing while idle, and it
never blocks or changes a key. Counts are saved to key_stats.json in the app's data folder.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import threading
import time
from pathlib import Path

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP = 0x0100, 0x0104, 0x0101, 0x0105
WM_QUIT, WM_TIMER = 0x0012, 0x0113
LLKHF_EXTENDED, LLKHF_INJECTED = 0x01, 0x10
REHOOK_MS = 5000
SAVE_EVERY = 30.0       # seconds between saves while counting


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)


class KeyCounter:
    """Counts key-downs per scan code (0xE0xx for extended keys) while running."""

    def __init__(self, path: Path):
        self.path = path
        self.counts: dict[int, int] = {}
        self.since = time.time()
        self._down: set[int] = set()
        self._thread: threading.Thread | None = None
        self._thread_id = None
        self._hook = None
        self._dirty = False
        self._last_save = time.monotonic()
        self.load()

    # ---- storage ----

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            self.counts = {int(k): int(v) for k, v in data.get("counts", {}).items()}
            self.since = float(data.get("since", time.time()))
        except (OSError, ValueError):
            self.counts, self.since = {}, time.time()

    def save(self):
        if not self._dirty:
            return
        try:
            self.path.write_text(json.dumps({"since": self.since,
                                             "counts": {str(k): v for k, v in list(self.counts.items())}}))
            self._dirty = False
        except OSError:
            pass
        self._last_save = time.monotonic()

    def reset(self):
        self.counts, self.since, self._dirty = {}, time.time(), True
        self.save()

    def count(self, scan: int, down: bool):
        """One key event (also used by the tests)."""
        if down:
            if scan not in self._down:          # held keys auto-repeat; count the press once
                self._down.add(scan)
                self.counts[scan] = self.counts.get(scan, 0) + 1
                self._dirty = True
        else:
            self._down.discard(scan)

    # ---- hook ----

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if not self.running:
            self._thread = threading.Thread(target=self._run, name="key-stats", daemon=True)
            self._thread.start()

    def stop(self):
        if self.running and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(1.0)
        self._thread = None
        self.save()

    def _callback(self, code, wparam, lparam):
        if code == 0:
            k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if not k.flags & LLKHF_INJECTED:
                scan = (0xE000 if k.flags & LLKHF_EXTENDED else 0) | (k.scanCode & 0xFF)
                if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self.count(scan, True)
                elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                    self.count(scan, False)
        return self._user32.CallNextHookEx(None, code, wparam, lparam)

    def _install(self):
        u = self._user32
        if self._hook:
            u.UnhookWindowsHookEx(self._hook)
        self._hook = u.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, ctypes.windll.kernel32.GetModuleHandleW(None), 0)

    def _run(self):
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
        u.SetWindowsHookExW.restype = wt.HHOOK
        u.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        u.CallNextHookEx.restype = LRESULT
        u.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
        u.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
        ctypes.windll.kernel32.GetModuleHandleW.restype = wt.HMODULE
        self._user32 = u
        self._proc = HOOKPROC(self._callback)          # keep a reference so it is not collected
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self._install()
        u.SetTimer(None, 0, REHOOK_MS, None)
        msg = wt.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_TIMER:
                self._install()                        # Windows drops slow hooks; keep it alive
                if time.monotonic() - self._last_save > SAVE_EVERY:
                    self.save()
        if self._hook:
            u.UnhookWindowsHookEx(self._hook)
            self._hook = None
        self._thread_id = None
