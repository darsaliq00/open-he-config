"""Board data for RK's non-HE keyboards (USB VID 0x258A), read from RK's own Windows software.

RK Keyboard Software ships one folder per board in `<install>/Dev/<PID>/`:

- `KB.ini`: `[OPT]` board options and `[KEY]` key lines
  `K<n>=left,top,right,bottom, type, vk, extra, index[, ...]`
  where the rectangle is in `keyimg.png` pixels, `type` 0x02 means `vk` is a Windows
  virtual-key code, and `index` is the key's position in the keyboard's key-map and LED buffers.
- `keyimg.png` / `kbled.png`: photos of the board.

`Cfg.ini` (UTF-16) holds `VID`, the `PID` list and `DevName<n>=<pid>,<name>` lines, and
`Dev/<lang>/led.xml` names the lighting modes.

Nothing from RK is bundled with this app: the files are read at run time from the user's own
install of RK's software.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from . import protocol as p

VID = 0x258A


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if len(raw) > 1 and raw[1:2] == b"\x00":
        return raw.decode("utf-16-le", errors="replace")
    for enc in ("utf-8-sig", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _int(s: str) -> int | None:
    s = s.strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s)
    except ValueError:
        return None


def _sections(text: str) -> dict[str, list[tuple[str, str, str]]]:
    """{section: [(key, value, comment above it)]}; INI parsing that keeps duplicate keys."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    sec, comment = "", ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            sec, comment = line[1:-1].upper(), ""
            out.setdefault(sec, [])
            continue
        if line.startswith(";"):
            comment = line[1:].strip()
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out.setdefault(sec, []).append((k.strip(), v.strip(), comment))
            comment = ""
    return out


# Windows virtual-key code (as RK's KB.ini uses it) -> key-map code for the keyboard.
# Codes follow the keyboard's 4-byte format, see protocol.py.
_VK_USAGE = {
    0x08: 0x2A, 0x09: 0x2B, 0x0D: 0x28, 0x13: 0x48, 0x14: 0x39, 0x1B: 0x29, 0x20: 0x2C,
    0x21: 0x4B, 0x22: 0x4E, 0x23: 0x4D, 0x24: 0x4A, 0x25: 0x50, 0x26: 0x52, 0x27: 0x4F,
    0x28: 0x51, 0x2C: 0x46, 0x2D: 0x49, 0x2E: 0x4C, 0x5D: 0x65,
    0x60: 0x62, 0x6A: 0x55, 0x6B: 0x57, 0x6D: 0x56, 0x6E: 0x63, 0x6F: 0x54, 0x90: 0x53,
    0x91: 0x47, 0xBA: 0x33, 0xBB: 0x2E, 0xBC: 0x36, 0xBD: 0x2D, 0xBE: 0x37, 0xBF: 0x38,
    0xC0: 0x35, 0xDB: 0x2F, 0xDC: 0x31, 0xDD: 0x30, 0xDE: 0x34,
    # RK's own codes for keys Windows has no VK for
    0xE0: 0x2C,   # second space bar
    0xE2: 0x64,   # ISO key next to left Shift
    0xFD: 0x58,   # numpad Enter
    0xC1: 0x87,   # JIS Ro
    0xC3: 0x89,   # JIS Yen
    0xEB: 0x88,   # JIS Kana
    0xDA: 0x8A,   # JIS Henkan
    0xD7: 0x8B,   # JIS Muhenkan
}
for _i in range(26):
    _VK_USAGE[0x41 + _i] = 0x04 + _i                  # A-Z
for _i in range(9):
    _VK_USAGE[0x31 + _i] = 0x1E + _i                  # 1-9
    _VK_USAGE[0x61 + _i] = 0x59 + _i                  # numpad 1-9
_VK_USAGE[0x30] = 0x27
for _i in range(12):
    _VK_USAGE[0x70 + _i] = 0x3A + _i                  # F1-F12

_VK_MODS = {0xA2: 0x01, 0xA0: 0x02, 0xA4: 0x04, 0x5B: 0x08, 0x5C: 0x80,
            0xA3: 0x10, 0xA1: 0x20, 0xA5: 0x40}

_VK_CONSUMER = {0x89: 0xCD, 0x8A: 0xB7, 0x8B: 0xB6, 0x8C: 0xB5, 0x8D: 0xE9, 0x8E: 0xEA,
                0x8F: 0xE2, 0x99: 0x192}

_VK_SHORTCUT = {0xB8: (0x01, 0x1B), 0xB9: (0x01, 0x06), 0xD8: (0x01, 0x19),   # cut copy paste
                0xD9: (0x01, 0x04), 0xC6: (0x01, 0x19), 0xC7: (0x01, 0x16)}   # all paste save


def vk_code(vk: int) -> int | None:
    """Key-map code for a Windows VK from KB.ini, or None when unknown."""
    if vk in _VK_MODS:
        return p.key(0, _VK_MODS[vk])
    if vk in _VK_USAGE:
        return p.key(_VK_USAGE[vk])
    if vk in _VK_CONSUMER:
        return p.consumer(_VK_CONSUMER[vk])
    if vk in _VK_SHORTCUT:
        mods, usage = _VK_SHORTCUT[vk]
        return p.key(usage, mods)
    if vk == 0xFA:
        return p.FN
    return None


@dataclass
class Key:
    index: int                           # position in the key-map and LED buffers
    rect: tuple[int, int, int, int]      # left, top, right, bottom in keyimg.png pixels
    name: str                            # RK's comment for the key, e.g. "Esc"
    vk: int | None                       # Windows VK RK lists for it (type 0x02 only)
    default: int | None                  # key-map code the key sends out of the box


@dataclass
class Board:
    pid: int
    name: str
    folder: Path
    rgb: bool
    rgb_order: tuple[int, int, int]
    keys: list[Key] = field(default_factory=list)
    options: dict[str, str] = field(default_factory=dict)
    photo_folder: Path | None = None     # another board's folder when KB.ini says KbImgUse

    @property
    def photo(self) -> Path | None:
        for d in (self.folder, self.photo_folder):
            if d and (d / "keyimg.png").exists():
                return d / "keyimg.png"
        return None

    @property
    def can_remap(self) -> bool:
        """The key map is written whole, so every key needs a known default code."""
        return bool(self.keys) and all(k.default is not None for k in self.keys) \
            and max(k.index for k in self.keys) < p.KEYMAP_SLOTS

    def mode_options(self, mode: int) -> dict[str, bool]:
        """Which controls RK shows for a lighting mode (KB.ini LedOpt<n>)."""
        raw = self.options.get(f"LedOpt{mode}")
        names = ("animation", "speed", "brightness", "direction", "random", "colours")
        vals = [_int(x) for x in raw.split(",")] if raw else []
        if len(vals) < 3:
            return {n: True for n in names}
        return {n: bool(v) for n, v in zip(names, vals + [0] * 6)}


def parse_board(folder: Path, pid: int, name: str) -> Board:
    ini = _sections(_read_text(folder / "KB.ini"))
    opts = {k: v for k, v, _ in ini.get("OPT", [])}
    order = tuple(_int(x) or 0 for x in opts.get("RGBIndex", "0,1,2").split(","))[:3]
    if sorted(order) != [0, 1, 2]:
        order = (0, 1, 2)
    keys = []
    for k, v, comment in ini.get("KEY", []):
        if not re.fullmatch(r"K\d+", k):
            continue
        f = [x.strip() for x in v.split(",")]
        if len(f) < 8:
            continue
        nums = [_int(x) for x in f[:8]]
        if None in nums[:4] or nums[7] is None:
            continue
        kind, vk = nums[4], nums[5]
        known_vk = vk if kind == 0x02 else None
        keys.append(Key(index=nums[7], rect=tuple(nums[:4]), name=comment or "",
                        vk=known_vk, default=vk_code(known_vk) if known_vk is not None else None))
    return Board(pid=pid, name=name, folder=folder, rgb=opts.get("RGBKb", "0").strip() == "1",
                 rgb_order=order, keys=keys, options=opts)


class RKSoftware:
    """An install (or unpacked copy) of RK Keyboard Software: the folder holding Cfg.ini and Dev/."""

    def __init__(self, root: Path):
        self.root = Path(root)
        cfg = _sections(_read_text(self.root / "Cfg.ini"))
        opt = {k: v for k, v, _ in cfg.get("OPT", [])}
        self.vid = _int(opt.get("VID", "0x258A")) or VID
        self.pids = [x for x in (_int("0x" + s.strip()) for s in opt.get("PID", "").split(",") if s.strip())
                     if x is not None]
        self.names: dict[int, str] = {}
        for sec in cfg.values():
            for k, v, _ in sec:
                if k.startswith("DevName") and "," in v:
                    pid, name = v.split(",", 1)
                    n = _int("0x" + pid.strip())
                    if n is not None:
                        self.names[n] = name.strip()

    def folder(self, pid: int) -> Path | None:
        dev = self.root / "Dev"
        if not dev.is_dir():
            return None
        want = f"{pid:04x}"
        for d in dev.iterdir():
            if d.is_dir() and d.name.lower() == want and (d / "KB.ini").exists():
                return d
        return None

    def boards(self) -> list[int]:
        """PIDs that have a board folder."""
        return sorted(pid for pid in set(self.pids) | set(self.names) if self.folder(pid))

    def board(self, pid: int) -> Board | None:
        d = self.folder(pid)
        if not d:
            return None
        board = parse_board(d, pid, self.names.get(pid, f"RK board {pid:04X}"))
        shared = _int(board.options.get("KbImgUse", ""))
        if shared is not None:
            board.photo_folder = self.folder(shared)
        return board

    def mode_names(self, rgb: bool, lang: str = "en") -> dict[int, str]:
        """{mode number: name} from RK's led.xml (mode numbers are what the keyboard expects)."""
        f = self.root / "Dev" / lang / "led.xml"
        if not f.exists():
            return {}
        try:
            root = ET.fromstring(_read_text(f).replace('encoding="utf-16"', ""))
        except ET.ParseError:
            return {}
        tag = re.compile(r"tc_led_mode(\d+)$" if rgb else r"tc_led(\d+)$")
        out = {}
        for el in root.iter():
            m = tag.match(el.tag)
            if m and el.text:
                out[int(m.group(1))] = el.text.strip().replace("_", " ")
        return dict(sorted(out.items()))


def _looks_like_install(d: Path) -> bool:
    return (d / "Cfg.ini").exists() and (d / "Dev").is_dir()


def _registry_dirs() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    out = []
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            base = winreg.OpenKey(hive, path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(base)[0]):
            try:
                sub = winreg.OpenKey(base, winreg.EnumKey(base, i))
                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                if "RK" not in str(name).upper():
                    continue
                out.append(Path(winreg.QueryValueEx(sub, "InstallLocation")[0]))
            except OSError:
                continue
    return out


def find_install(extra: list[Path] | None = None) -> RKSoftware | None:
    """Look for RK Keyboard Software: given folders, $RK_SOFTWARE_DIR, the uninstall registry, then
    the usual Program Files folders."""
    cands = list(extra or [])
    if os.environ.get("RK_SOFTWARE_DIR"):
        cands.append(Path(os.environ["RK_SOFTWARE_DIR"]))
    cands += _registry_dirs()
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(env):
            pf = Path(os.environ[env])
            cands += [d for d in pf.glob("RK*") if d.is_dir()]
    for d in cands:
        for c in (d, d / "app"):
            if _looks_like_install(c):
                try:
                    return RKSoftware(c)
                except OSError:
                    continue
    return None
