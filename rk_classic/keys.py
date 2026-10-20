"""Remap targets for non-HE RK boards: (label, key-map code)."""

from . import protocol as p

_LETTERS = [(chr(ord("A") + i), p.key(0x04 + i)) for i in range(26)]
_DIGITS = [(str((i + 1) % 10), p.key(0x1E + i)) for i in range(10)]
_F = [(f"F{i + 1}", p.key(0x3A + i)) for i in range(12)]

GROUPS: list[tuple[str, list[tuple[str, int]]]] = [
    ("Letters", _LETTERS),
    ("Numbers", _DIGITS),
    ("Function keys", _F),
    ("Editing", [("Esc", p.key(0x29)), ("Tab", p.key(0x2B)), ("Caps Lock", p.key(0x39)),
                 ("Space", p.key(0x2C)), ("Enter", p.key(0x28)), ("Backspace", p.key(0x2A)),
                 ("Insert", p.key(0x49)), ("Delete", p.key(0x4C)), ("Home", p.key(0x4A)),
                 ("End", p.key(0x4D)), ("Page Up", p.key(0x4B)), ("Page Down", p.key(0x4E)),
                 ("Print Screen", p.key(0x46)), ("Scroll Lock", p.key(0x47)), ("Pause", p.key(0x48)),
                 ("Menu", p.key(0x65))]),
    ("Arrows", [("Up", p.key(0x52)), ("Down", p.key(0x51)), ("Left", p.key(0x50)), ("Right", p.key(0x4F))]),
    ("Symbols", [("-", p.key(0x2D)), ("=", p.key(0x2E)), ("[", p.key(0x2F)), ("]", p.key(0x30)),
                 ("\\", p.key(0x31)), (";", p.key(0x33)), ("'", p.key(0x34)), ("`", p.key(0x35)),
                 (",", p.key(0x36)), (".", p.key(0x37)), ("/", p.key(0x38)), ("ISO \\", p.key(0x64))]),
    ("Modifiers", [("Left Ctrl", p.key(0, 0x01)), ("Left Shift", p.key(0, 0x02)),
                   ("Left Alt", p.key(0, 0x04)), ("Left Win", p.key(0, 0x08)),
                   ("Right Ctrl", p.key(0, 0x10)), ("Right Shift", p.key(0, 0x20)),
                   ("Right Alt", p.key(0, 0x40)), ("Right Win", p.key(0, 0x80)), ("Fn", p.FN)]),
    ("Numpad", [(f"Num {(i + 1) % 10}", p.key(0x59 + i)) for i in range(10)]
     + [("Num /", p.key(0x54)), ("Num *", p.key(0x55)), ("Num -", p.key(0x56)), ("Num +", p.key(0x57)),
        ("Num Enter", p.key(0x58)), ("Num .", p.key(0x63)), ("Num Lock", p.key(0x53))]),
    ("Media", [("Play / Pause", p.consumer(0xCD)), ("Stop", p.consumer(0xB7)),
               ("Previous", p.consumer(0xB6)), ("Next", p.consumer(0xB5)),
               ("Volume up", p.consumer(0xE9)), ("Volume down", p.consumer(0xEA)),
               ("Mute", p.consumer(0xE2)), ("Calculator", p.consumer(0x192)),
               ("File Explorer", p.consumer(0x194))]),
    ("Shortcuts", [("Copy", p.key(0x06, 0x01)), ("Paste", p.key(0x19, 0x01)), ("Cut", p.key(0x1B, 0x01)),
                   ("Select all", p.key(0x04, 0x01)), ("Undo", p.key(0x1D, 0x01)), ("Save", p.key(0x16, 0x01)),
                   ("Show desktop", p.key(0x07, 0x08)), ("Lock PC", p.key(0x0F, 0x08)),
                   ("Switch window", p.key(0x2B, 0x04)), ("Close window", p.key(0x3D, 0x04))]),
    ("Other", [("Disabled", 0)]),
]

_NAMES = {code: name for _, items in GROUPS for name, code in items}
_MOD_NAMES = ((0x01, "Ctrl"), (0x02, "Shift"), (0x04, "Alt"), (0x08, "Win"),
              (0x10, "RCtrl"), (0x20, "RShift"), (0x40, "RAlt"), (0x80, "RWin"))
_USAGE_NAMES = {(code >> 8) & 0xFF: name for name, code in
                _LETTERS + _DIGITS + _F + GROUPS[3][1] + GROUPS[4][1] + GROUPS[5][1]}


def name(code: int) -> str:
    if code in _NAMES:
        return _NAMES[code]
    kind, usage, mods = p.split(code)
    if kind == "consumer":
        return f"Media 0x{usage:03X}"
    parts = [n for bit, n in _MOD_NAMES if mods & bit]
    if usage:
        parts.append(_USAGE_NAMES.get(usage, f"0x{usage:02X}"))
    return "+".join(parts) or "Disabled"
