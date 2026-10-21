"""Volume knob remapping on the PC side.

The RK M75 HE's knob is fixed in firmware to Volume up / Volume down (turn) and Mute (press), and
the settings protocol has no command to change it. Windows delivers those as the virtual keys
VK_VOLUME_UP / DOWN / MUTE, so a low-level keyboard hook can swallow them and do something else.

The hook thread sleeps in GetMessage and only wakes when a key event arrives, so it costs no CPU
while idle. Windows cannot tell the knob apart from other volume keys, so those are remapped too.
"""

import ctypes
import ctypes.wintypes as wt
import threading

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP = 0x0100, 0x0104, 0x0101, 0x0105
WM_QUIT, WM_TIMER = 0x0012, 0x0113
REHOOK_MS = 5000
LLKHF_INJECTED = 0x10
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x0001, 0x0002
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000
VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN = 0x11, 0x10, 0x12, 0x5B

# what turning the knob does: (label, action for "up", action for "down")
# an action is ("wheel", amount) / ("hwheel", amount) / ("keys", [vk, ...]) / ("pass",)
TURN = {
    "volume": ("System volume (default)", ("pass",), ("pass",)),
    "scroll": ("Scroll up / down", ("wheel", 120), ("wheel", -120)),
    "hscroll": ("Scroll left / right", ("hwheel", -120), ("hwheel", 120)),
    "zoom": ("Zoom in / out (Ctrl + wheel)", ("keys_wheel", [VK_CONTROL], 120), ("keys_wheel", [VK_CONTROL], -120)),
    "track": ("Next / previous track", ("keys", [0xB0]), ("keys", [0xB1])),
    "arrows_lr": ("Right / left arrow", ("keys", [0x27]), ("keys", [0x25])),
    "arrows_ud": ("Up / down arrow", ("keys", [0x26]), ("keys", [0x28])),
    "page": ("Page up / page down", ("keys", [0x21]), ("keys", [0x22])),
    "tabs": ("Next / previous browser tab", ("keys", [VK_CONTROL, 0x09]), ("keys", [VK_CONTROL, VK_SHIFT, 0x09])),
    "desktops": ("Next / previous virtual desktop", ("keys", [VK_LWIN, VK_CONTROL, 0x27]),
                 ("keys", [VK_LWIN, VK_CONTROL, 0x25])),
    "brackets": ("] / [ (brush size in editors)", ("keys", [0xDD]), ("keys", [0xDB])),
    "undo": ("Redo / undo", ("keys", [VK_CONTROL, 0x59]), ("keys", [VK_CONTROL, 0x5A])),
}

# what pressing the knob does
PRESS = {
    "mute": ("Mute (default)", ("pass",)),
    "play": ("Play / pause", ("keys", [0xB3])),
    "next": ("Next track", ("keys", [0xB0])),
    "enter": ("Enter", ("keys", [0x0D])),
    "esc": ("Esc", ("keys", [0x1B])),
    "zoom_reset": ("Reset zoom (Ctrl + 0)", ("keys", [VK_CONTROL, 0x30])),
    "task_view": ("Task view (Win + Tab)", ("keys", [VK_LWIN, 0x09])),
    "screenshot": ("Screenshot (Win + Shift + S)", ("keys", [VK_LWIN, VK_SHIFT, 0x53])),
    "mic": ("Discord mute (Ctrl + Shift + M)", ("keys", [VK_CONTROL, VK_SHIFT, 0x4D])),
    "nothing": ("Nothing", ("none",)),
}

EXTENDED_VKS = {0x21, 0x22, 0x25, 0x26, 0x27, 0x28, VK_LWIN, 0xB0, 0xB1, 0xB3}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
kernel32.GetModuleHandleW.restype = wt.HMODULE


def _key(vk: int, up: bool) -> INPUT:
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0)
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, dwFlags=flags)
    return i


def _wheel(amount: int, horizontal=False) -> INPUT:
    i = INPUT(type=INPUT_MOUSE)
    i.u.mi = MOUSEINPUT(mouseData=ctypes.c_uint32(amount).value,
                        dwFlags=MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL)
    return i


def _send(events: list[INPUT]):
    if events:
        arr = (INPUT * len(events))(*events)
        user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def perform(action):
    kind = action[0]
    if kind == "wheel":
        _send([_wheel(action[1])])
    elif kind == "hwheel":
        _send([_wheel(action[1], horizontal=True)])
    elif kind == "keys":
        vks = action[1]
        _send([_key(v, False) for v in vks] + [_key(v, True) for v in reversed(vks)])
    elif kind == "keys_wheel":
        vks = action[1]
        _send([_key(v, False) for v in vks] + [_wheel(action[2])] + [_key(v, True) for v in reversed(vks)])


class KnobRemapper:
    """Swallows volume-key events and runs the chosen actions instead."""

    def __init__(self):
        self.turn = "volume"
        self.press = "mute"
        self._proc = HOOKPROC(self._callback)   # keep a reference so it is not garbage collected
        self._hook = None
        self._thread_id = None
        self._thread: threading.Thread | None = None

    @property
    def active(self) -> bool:
        return self.turn != "volume" or self.press != "mute"

    def configure(self, turn: str, press: str):
        self.turn = turn if turn in TURN else "volume"
        self.press = press if press in PRESS else "mute"
        if self.active and not (self._thread and self._thread.is_alive()):
            self._thread = threading.Thread(target=self._run, name="knob-hook", daemon=True)
            self._thread.start()
        elif not self.active:
            self.stop()   # nothing to remap: no hook at all

    def stop(self):
        if self._thread and self._thread.is_alive() and self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(1.0)
        self._thread = None

    def _action_for(self, vk: int):
        if vk == VK_VOLUME_UP:
            return TURN[self.turn][1]
        if vk == VK_VOLUME_DOWN:
            return TURN[self.turn][2]
        if vk == VK_VOLUME_MUTE:
            return PRESS[self.press][1]
        return None

    def _callback(self, code, wparam, lparam):
        if code == 0:
            k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if not k.flags & LLKHF_INJECTED:
                action = self._action_for(k.vkCode)
                if action and action[0] != "pass":
                    if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN) and action[0] != "none":
                        # run it off the hook thread: a hook callback must return quickly
                        threading.Thread(target=perform, args=(action,), daemon=True).start()
                    return 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _install(self):
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._install()
        # Windows drops a low-level hook whose callback was ever too slow; re-install now and then
        user32.SetTimer(None, 0, REHOOK_MS, None)
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_TIMER:
                self._install()
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
