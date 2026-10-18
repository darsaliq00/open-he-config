"""RK M75 HE configuration protocol (SparkLink KB2).

Ported from the vendor web SDK (@sparklinkplayjoy/sdk-keyboard 1.0.24).
Every message is one 64-byte report:

    [0x5C, len, cmd, checksum, payload...]   zero padded to 64 bytes

checksum = (53 + 0x5C + len + cmd + last payload byte) & 0xFF. The reply
carries cmd | 0x80 in byte 2; its payload (byte 4 on) mirrors the request
layout, so parsers below index the reply payload, not the whole report.

Payload byte 0 of a request is the access flag: 0 = read, 1 = write.
Writes are stored by the firmware straight away; there is no separate save
except for per-key custom colours (see req_save_key_colors).
Bootloader / firmware-update commands are deliberately left out.
"""

from dataclasses import dataclass

HEADER = 0x5C
REPORT_LEN = 64

# commands (KB2_CMD_*)
CMD_INFO = 0x00
CMD_SYNC = 0x01
CMD_RM6X21 = 0x12
CMD_PRGB = 0x18
CMD_LOGORGB = 0x19
CMD_MACRO = 0x20
CMD_MACRO_MODE = 0x21
CMD_KEY = 0x23
CMD_MT = 0x24
CMD_TGL = 0x25
CMD_DKS = 0x26
CMD_MPT = 0x27
CMD_END = 0x28
CMD_DB = 0x29
CMD_KRGB = 0x2A
CMD_DEFKEY = 0x2B
CMD_SOCD = 0x2C
CMD_RS = 0x2D
CMD_FAIL = 0xFF

# order types for CMD_INFO (ORDER_TYPE_*)
ORDER_PROTOCOL_VERSION = 1
ORDER_SAVE_PARAMETERS = 2
ORDER_KEYBOARD_NAME = 38
ORDER_PRECISION = 37
ORDER_QUERY_WIN_MODE = 33
ORDER_START_CALIBRATION = 12
ORDER_CLOSE_CALIBRATION = 13
ORDER_FACTORY_RESET = 17
ORDER_LOCK_WIN_KEY = 32
ORDER_SET_WIN_MODE = 48
ORDER_SET_MAC_MODE = 49
ORDER_TOP_DEAD_SWITCH = 52
ORDER_POLLING = 80          # ORDER_TYPE_ROES ("rate of return")
ORDER_LIGHT_SATURATION = 68
ORDER_CONFIG = 112
ORDER_AXES = 118
ORDER_CURRENT_AXIS = 117

# per-key layout fields for CMD_KEY (KeyLayout)
LAYOUT_FN0, LAYOUT_FN1, LAYOUT_FN2, LAYOUT_FN3 = 0, 1, 2, 3
LAYOUT_DB0, LAYOUT_DB1, LAYOUT_DB2, LAYOUT_DB3 = 4, 5, 6, 7   # DB0 = actuation travel
LAYOUT_MODE = 8
LAYOUT_RTP, LAYOUT_RTR = 20, 21     # rapid trigger press / release travel
LAYOUT_DP, LAYOUT_DR = 22, 23       # press / release deadzone
LAYOUT_AXIS = 25

TOUCH_MODES = {0: "global", 1: "single", 2: "rt"}
ADVANCED_MODES = {0: "none", 1: "DKS", 2: "MPT", 3: "MT", 4: "TGL", 5: "END", 6: "MCR", 8: "SOCD", 9: "RS"}

# diagnostic data types for CMD_RM6X21, verified on the keyboard
DIAG_TRAVEL = 2      # calibrated travel, micrometres (0..~3300)
DIAG_STATUS = 3      # key status grid
DIAG_DEPTH_ADC = 4   # rest ADC minus current ADC
DIAG_ADC = 6         # raw ADC, falls as the key goes down
DIAG_THRESHOLD = 7   # per-key ADC level below rest (purpose not confirmed)
DIAG_REST = 8        # calibrated rest ADC


def checksum(length: int, cmd: int, payload: list[int]) -> int:
    s = 53 + HEADER + length + cmd
    if 0 < length <= 252:
        s += payload[-1]
    return s & 0xFF


def packet(cmd: int, payload: list[int]) -> bytes:
    n = len(payload)
    if n > REPORT_LEN - 4:
        raise ValueError("payload too long for one report")
    p = bytes([HEADER, n, cmd, checksum(n, cmd, payload), *payload])
    return p.ljust(REPORT_LEN, b"\0")


def reply_payload(report: bytes, cmd: int) -> bytes | None:
    """Payload of a reply to `cmd`, or None if the report is something else."""
    if len(report) < 4 or report[0] != HEADER or report[2] != (cmd | 0x80):
        return None
    return bytes(report[4:])


def _u16(b: bytes, i: int) -> int:
    return b[i] | (b[i + 1] << 8)


# ---- request builders ----

def req_sync() -> bytes:
    return packet(CMD_SYNC, [1, 2, 3, 4, 0xFF, 0xFF])


def req_order(order: int, args: list[int] = ()) -> bytes:
    return packet(CMD_INFO, [order, *args, 0xFF, 0xFF])


def req_diag(data_type: int, page: int) -> bytes:
    return packet(CMD_RM6X21, [data_type, page, 0xFF, 0xFF])


def req_global_travel() -> bytes:
    return packet(CMD_DB, [0] + [0] * 14)


def req_key_field(key: int, layout: int) -> bytes:
    """`key` is the key's HID usage code (W = 0x1A), as CMD_DEFKEY reports it."""
    return packet(CMD_KEY, [0, key, layout, 0, 0])


KEY_FIELDS_PER_REPORT = 14  # 4-byte records after the access flag


def req_key_fields(fields: list[tuple[int, int]]) -> bytes:
    """Read several (key, layout) fields in one report."""
    if len(fields) > KEY_FIELDS_PER_REPORT:
        raise ValueError("too many fields for one report")
    return packet(CMD_KEY, [0] + [b for key, layout in fields for b in (key, layout, 0, 0)])


def req_set_key_fields(fields: list[tuple[int, int, int]]) -> bytes:
    """Write several (key, layout, value) fields in one report.

    The firmware stores them right away (the SDK never sends a separate save),
    so every call is a flash write: send on an explicit apply, not per slider move.
    """
    if len(fields) > KEY_FIELDS_PER_REPORT:
        raise ValueError("too many fields for one report")
    return packet(CMD_KEY, [1] + [b for key, layout, value in fields
                                  for b in (key, layout, value & 0xFF, value >> 8 & 0xFF)])


def mode_value(touch: str, advanced_bits: int) -> int:
    """Layout_MODE value: trigger mode in the high nibble, advanced key kept as is."""
    code = {v: k for k, v in TOUCH_MODES.items()}[touch]
    return code << 4 | (advanced_bits & 15)


def req_key_map(row_a: int, row_b: int) -> bytes:
    return packet(CMD_DEFKEY, [0, row_a, row_b])


def req_key_color(key: int) -> bytes:
    return packet(CMD_KRGB, [0, key])


def req_lighting() -> bytes:
    # the SDK's read request is an empty lighting block: no colours, all fields 0
    return packet(CMD_PRGB, [0] * 15)


# ---- reply parsers (take the reply payload) ----

@dataclass
class BoardInfo:
    board_id: int
    key_type: int
    layout: int
    run_mode: int
    serial: str
    app_version: str


def parse_sync(p: bytes) -> BoardInfo:
    # strings are length-prefixed; the SDK's fixed offsets cut the version short.
    # The build date that follows overlaps other fields on this firmware, so it is skipped.
    def text(at):
        return p[at + 1:at + 1 + p[at]].split(b"\0")[0].decode("ascii", "replace").strip()
    return BoardInfo(
        board_id=int.from_bytes(p[1:5], "little"), key_type=p[3], layout=p[4], run_mode=p[7],
        serial=text(8), app_version=text(25))


def parse_order(order: int, p: bytes):
    if order == ORDER_KEYBOARD_NAME:
        return bytes(c for c in p[2:34] if c).decode("utf-8", "replace")
    if order == ORDER_PROTOCOL_VERSION:
        return f"{p[3] & 15}.{p[2] >> 4 & 15}.{p[2] & 15}"
    if order == ORDER_PRECISION:
        return {"precision_mm": p[2] / 1000, "min_travel_mm": _u16(p, 3) / 1000, "max_travel_mm": _u16(p, 5) / 1000}
    if order == ORDER_QUERY_WIN_MODE:
        return {1: "win", 0: "mac"}.get(p[2])
    if order == ORDER_CONFIG:
        return p[2]
    if order == ORDER_CURRENT_AXIS:
        return _u16(p, 2)
    if order == ORDER_AXES:
        axes = []
        for i in range(1, 9):
            v = (p[2 * i] << 8) | p[2 * i + 1]
            if v == 0xFFFF:
                break
            axes.append(v)
        return axes
    return bytes(p)


def parse_diag(p: bytes) -> list[int]:
    """63 little-endian values of one page (3 rows x 21 columns)."""
    return [_u16(p, 2 + 2 * i) for i in range(63)]


def parse_global_travel(p: bytes) -> dict:
    return {"actuation_mm": _u16(p, 3) / 1000, "press_dead_mm": _u16(p, 5) / 1000,
            "release_dead_mm": _u16(p, 7) / 1000}


def parse_key_field(p: bytes) -> tuple[int, int, int]:
    """(key, layout, value) of a CMD_KEY reply."""
    return p[1], p[2], _u16(p, 3)


def parse_key_fields(p: bytes) -> list[tuple[int, int, int]]:
    """(key, layout, value) records of a CMD_KEY reply; 0xFF marks unused records."""
    out = []
    for i in range(1, len(p) - 3, 4):
        key, layout = p[i], p[i + 1]
        if key in (0, 0xFF) or layout == 0xFF:
            continue
        out.append((key, layout, _u16(p, i + 2)))
    return out


def parse_mode(value: int) -> dict:
    v = value & 0xFF
    return {"touch": TOUCH_MODES.get(v >> 4 & 15, "global"), "advanced": ADVANCED_MODES.get(v & 15, str(v & 15))}


def parse_key_map(p: bytes) -> list[tuple[int, int, int]]:
    """(row, col, key id) for the two matrix rows in a CMD_DEFKEY reply; 0 = no key."""
    out = []
    for row, start in ((p[1], 2), (p[23], 24)):
        for col in range(21):
            k = p[start + col]
            if k:
                out.append((row, col, k))
    return out


def parse_key_color(p: bytes) -> tuple[int, int, int, int]:
    return p[1], p[2], p[3], p[4]


def parse_lighting(p: bytes) -> dict:
    colors = []
    for i in range(7):
        b, g, r = p[5 + 4 * i], p[6 + 4 * i], p[7 + 4 * i]
        colors.append(f"#{r:02x}{g:02x}{b:02x}")
    flags, mode = p[37], p[39]
    return {"on": bool(flags & 1), "reverse": bool(flags & 2), "fast_response": bool(flags & 16), "flags": flags,
            "brightness": p[38], "mode": mode,
            "type": "static" if mode == 0 else "dynamic" if mode <= 20 else "custom",
            "speed": p[40], "sleep": p[41], "static_color": p[42], "palette": p[43], "colors": colors}


# ---- global travel ----

def req_set_global_travel(actuation_mm: float, press_dead_mm: float, release_dead_mm: float) -> bytes:
    vals = [round(v * 1000) for v in (actuation_mm, press_dead_mm, release_dead_mm)]
    return packet(CMD_DB, [1, 0, 0] + [b for v in vals for b in (v & 0xFF, v >> 8 & 0xFF)] + [0] * 6)


# ---- key remap (layout fields Fn0..Fn3) ----

KEY_NONE = 0x0001   # what unbound Fn-layer slots read as


CONSUMER = 0x1000   # 0x1000 | consumer-page usage (media keys)
FN_KEY = 0xF001     # 0xF0xx..0xF3xx are keyboard-internal functions (Fn, lighting, ...)

CONSUMER_NAMES = {
    0xB5: "Next track", 0xB6: "Previous track", 0xB7: "Stop", 0xCD: "Play/Pause", 0xE2: "Mute",
    0xE9: "Volume up", 0xEA: "Volume down", 0x183: "Media player", 0x18A: "Mail", 0x192: "Calculator",
    0x194: "My computer", 0x221: "Search", 0x223: "Browser home", 0x224: "Browser back",
    0x225: "Browser forward", 0x6F: "Brightness up", 0x70: "Brightness down",
}


COMBO = 0x6000      # 0x6000 | modifiers << 8 | key code (RK web driver "combination key")
COMBO_MODS = (("Ctrl", 1), ("Shift", 2), ("Alt", 4), ("Win", 8))


def combo_code(mods: int, key: int) -> int:
    return COMBO | (mods & 15) << 8 | (key & 0xFF)


def keycode_name(value: int) -> str:
    if value == KEY_NONE:
        return ""
    if value & 0xF000 == COMBO:
        mods = "+".join(n for n, bit in COMBO_MODS if value >> 8 & bit)
        return f"{mods}+{HID_NAMES.get(value & 0xFF, hex(value & 0xFF))}"
    if value in HID_NAMES:
        return HID_NAMES[value]
    if value & 0xF000 == CONSUMER and value & 0xFFF in CONSUMER_NAMES:
        return CONSUMER_NAMES[value & 0xFFF]
    if value == FN_KEY:
        return "Fn"
    if value >= 0xF000:
        return f"Fn func {value:04X}"
    return f"0x{value:04X}"


def keycode_choices() -> list[tuple[str, int]]:
    """Codes a key can be remapped to, in menu order."""
    out = [(n, c) for c, n in HID_NAMES.items()]
    out += [(n, CONSUMER | c) for c, n in CONSUMER_NAMES.items()]
    return out


HID_NAMES = {
    **{0x04 + i: chr(ord("A") + i) for i in range(26)},
    **{0x1E + i: str((i + 1) % 10) for i in range(10)},
    0x28: "Enter", 0x29: "Esc", 0x2A: "Bksp", 0x2B: "Tab", 0x2C: "Space", 0x2D: "-", 0x2E: "=",
    0x2F: "[", 0x30: "]", 0x31: "\\", 0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",", 0x37: ".", 0x38: "/",
    0x39: "Caps", **{0x3A + i: f"F{i + 1}" for i in range(12)},
    0x46: "PrtSc", 0x47: "ScrLk", 0x48: "Pause", 0x49: "Ins", 0x4A: "Home", 0x4B: "PgUp", 0x4C: "Del",
    0x4D: "End", 0x4E: "PgDn", 0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up", 0x53: "NumLk",
    0x54: "KP /", 0x55: "KP *", 0x56: "KP -", 0x57: "KP +", 0x58: "KP Enter",
    **{0x59 + i: f"KP {(i + 1) % 10}" for i in range(10)}, 0x63: "KP .", 0x65: "Menu",
    **{0x68 + i: f"F{13 + i}" for i in range(12)},
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LWin", 0xE4: "RCtrl", 0xE5: "RShift",
    0xE6: "RAlt", 0xE7: "RWin",
}


# ---- lighting ----

def req_set_lighting(light: dict, cmd: int = CMD_PRGB) -> bytes:
    """light: on, reverse, fast_response, brightness, mode, speed, sleep, static_color, colors (7 x '#rrggbb')."""
    colors = []
    for c in light["colors"][:7]:
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        colors += [b, g, r, 0xFF]
    # keep flag bits this code does not know about (the firmware sets 0x40 / 0x80 by default)
    flags = light.get("flags", 0) & ~0x13
    flags |= (1 if light["on"] else 0) | (2 if light["reverse"] else 0) | (16 if light["fast_response"] else 0)
    return packet(cmd, [1, 0, 0, 0, 0, *colors, 0, 0, 0, 0, flags, light["brightness"], light["mode"],
                        light["speed"], light["sleep"], light["static_color"]])


KEY_COLORS_PER_REPORT = 14


def req_set_key_colors(colors: list[tuple[int, int, int, int]]) -> bytes:
    """(key, r, g, b) per key; held in RAM until req_save_key_colors()."""
    if len(colors) > KEY_COLORS_PER_REPORT:
        raise ValueError("too many keys for one report")
    data = [1] + [v for c in colors for v in c]
    pkt = bytearray(packet(CMD_KRGB, data))
    pkt[4 + len(data):] = b"\xff" * (REPORT_LEN - 4 - len(data))  # SDK pads custom colours with 0xFF
    return bytes(pkt)


def req_save_key_colors() -> bytes:
    return packet(CMD_KRGB, [1, 254, 254, 254, 254])


# ---- system ----

def req_set_order(order: int, value: int) -> bytes:
    return req_order(order, [value])


# ---- advanced keys ----

def req_socd(key: int) -> bytes:
    return packet(CMD_SOCD, [0, key])


def parse_socd(p: bytes) -> dict:
    """Protocol >= 1.0.7 layout: the two keys, how they are matched and which one wins."""
    return {"key1": p[1], "key2": p[2], "code1": _u16(p, 3), "code2": _u16(p, 5),
            "by": "key" if p[7] else "position", "mode": SOCD_MODES.get(p[8], str(p[8])), "delay": _u16(p, 9)}


SOCD_MODES = {0: "last pressed wins", 1: "first key wins", 2: "second key wins", 3: "neutral (both cancel)"}


def req_set_socd(key1: int, key2: int, mode: int, by_key: bool = False, delay: int = 0) -> bytes:
    return packet(CMD_SOCD, [1, key1, key2, 0, 0, 0, 0, 1 if by_key else 0, mode, delay & 0xFF, delay >> 8 & 0xFF])


def clear_advanced_value(touch: str) -> int:
    """Layout_MODE value that keeps the trigger mode and removes any advanced function."""
    return mode_value(touch, 0)


# ---- advanced keys, protocol >= 1.0.3 layouts (as RK's web driver sends them) ----
# Advanced type numbers in the Layout_MODE low nibble: 1 DKS, 2 MPT, 3 MT, 4 TGL, 5 END, 6 macro, 8 SOCD, 9 RS.
ADV_DKS, ADV_MPT, ADV_MT, ADV_TGL, ADV_END, ADV_MACRO, ADV_SOCD, ADV_RS = 1, 2, 3, 4, 5, 6, 8, 9
LAYOUT_DKS = (9, 10, 11, 12)      # DKS / mod-tap key codes
LAYOUT_TRPS = (13, 14, 15, 16)    # DKS trigger-point bitmasks
LAYOUT_MT_DELAY = 19              # mod-tap hold delay, x10 ms

# DKS timeline: 7 cells per action, bit values as RK's web driver sets them
DKS_CELLS = (1, 2, 4, 24, 32, 64, 128)
DKS_CELL_NAMES = ("press to 1st point", "held to bottom", "bottom out", "held at bottom",
                  "release from bottom", "held to 1st point", "release past 1st point")


def _u16le(v: int) -> list[int]:
    return [v & 0xFF, v >> 8 & 0xFF]


def req_set_dks(key: int, codes: list[int], trps: list[int], first_mm: float, second_mm: float) -> bytes:
    return packet(CMD_DKS, [1, key, *[b for c in codes for b in _u16le(c)], *trps,
                            *_u16le(round(first_mm * 1000)), *_u16le(round(second_mm * 1000))])


def req_mpt(key: int) -> bytes:
    return packet(CMD_MPT, [0, key])


def parse_mpt(p: bytes) -> dict:
    return {"codes": [_u16(p, 2 + 2 * i) for i in range(3)], "depths": [_u16(p, 8 + 2 * i) / 1000 for i in range(3)]}


def req_set_mpt(key: int, codes: list[int], depths_mm: list[float]) -> bytes:
    return packet(CMD_MPT, [1, key, *[b for c in codes for b in _u16le(c)],
                            *[b for d in depths_mm for b in _u16le(round(d * 1000))]])


def req_set_mt(key: int, hold: int, tap: int, delay_ms: int) -> bytes:
    return packet(CMD_MT, [1, key, *_u16le(hold), *_u16le(tap), max(0, min(255, delay_ms // 10))])


def req_tgl(key: int) -> bytes:
    return packet(CMD_TGL, [0, key, 0, 0, 0])


def parse_tgl(p: bytes) -> dict:
    return {"code": _u16(p, 2), "delay_ms": p[4] * 10}


def req_set_tgl(key: int, code: int, delay_ms: int) -> bytes:
    return packet(CMD_TGL, [1, key, *_u16le(code), max(0, min(255, delay_ms // 10))])


def req_end(key: int) -> bytes:
    return packet(CMD_END, [0, key, 0, 0, 0, 0])


def parse_end(p: bytes) -> dict:
    return {"code": _u16(p, 2), "delay": _u16(p, 4)}


def req_set_end(key: int, code: int) -> bytes:
    # The web driver appends a 16-bit delay for protocol >= 1.0.7, but this firmware reads those
    # bytes as another (key, code) record and puts END on whatever key the delay value names.
    return packet(CMD_END, [1, key, *_u16le(code)])


def req_rs(key: int) -> bytes:
    return packet(CMD_RS, [0, key, 0, 0, key])


def parse_rs(p: bytes) -> dict:
    return {"key1": p[1], "key2": p[2]}


def req_set_rs(key1: int, key2: int) -> bytes:
    # both directions in one report, as the web driver does
    return packet(CMD_RS, [1, key1, key2, key2, key1])


# ---- macros (macroV2) ----
MACRO_BUFFER = 256          # events go to this buffer, then MACROMODE stores them under a macro id
MACRO_EVENTS_PER_REPORT = 9
MACRO_MODES = {0: "Run once per press (repeat count)", 1: "Tap to start repeating, tap again to stop",
               2: "Repeat while held, stop at once on release", 3: "Repeat while held, finish the run on release"}
MAX_MACROS = 8


def req_macro_events(start: int, events: list[tuple[int, bool, int]]) -> bytes:
    """events: (key code, pressed, delay ms after it)."""
    data = [1, *_u16le(start), len(events)]
    for code, pressed, delay in events:
        v = (1 if pressed else 8) << 24 | (delay & 0xFFFFFF)
        data += [*_u16le(code), v & 0xFF, v >> 8 & 0xFF, v >> 16 & 0xFF, v >> 24 & 0xFF]
    return packet(CMD_MACRO, data)


def req_macro_mode(key: int) -> bytes:
    return packet(CMD_MACRO_MODE, [0, key, 0, 0, 0, 0, 0, 0, 0, 0, 0])


def parse_macro_mode(p: bytes) -> dict:
    return {"id": _u16(p, 2), "length": p[4], "mode": p[5], "repeat": _u16(p, 6),
            "interval_ms": p[8] | p[9] << 8 | p[10] << 16}


def req_set_macro_mode(key: int, macro_id: int, length: int, mode: int, repeat: int, interval_ms: int) -> bytes:
    return packet(CMD_MACRO_MODE, [1, key, *_u16le(macro_id), length, mode, *_u16le(repeat),
                                   interval_ms & 0xFF, interval_ms >> 8 & 0xFF, interval_ms >> 16 & 0xFF])


POLLING_RATES = ("8 kHz", "4 kHz", "2 kHz", "1 kHz", "500 Hz", "250 Hz", "125 Hz")   # index = ORDER_POLLING value
POLLING_RATES_1K = ("1 kHz", "500 Hz", "250 Hz", "125 Hz")                         # boards with key type 4
