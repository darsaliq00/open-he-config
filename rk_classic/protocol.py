"""Feature reports for RK's non-HE keyboards (USB VID 0x258A).

These boards only take settings; they never report them back, so the app keeps the full state
and sends it whole. Every message is one or more 65-byte feature reports with report id 0x0A:

    byte 0  report id 0x0A
    byte 1  number of reports in this message
    byte 2  number of this report, from 1
    then    the message header (first report only) and the data, continued across reports

Messages:

- lighting   1 report,  header 02 29:    mode, 0, speed, brightness, R, G, B, random colour, sleep
- key colours 7 reports, header 03 7E 01: R, G, B per key buffer index
- key map    9 reports, header 01 F8:    4 bytes (big-endian code) per key buffer index

Key-map codes, as 32-bit numbers:
    0x0000UU00  keyboard usage UU            0x00MM0000  modifier bits MM (left Ctrl 01, Shift 02,
    0x01000UUU  consumer usage (media keys)               Alt 04, Win 08, right ones 10 20 40 80)
    0x0000B000  Fn                           modifiers and a usage can be OR-ed into a shortcut
"""

REPORT_ID = 0x0A
REPORT_LEN = 65

LIGHT_HEADER = bytes([0x02, 0x29])
COLOURS_HEADER = bytes([0x03, 0x7E, 0x01])
KEYMAP_HEADER = bytes([0x01, 0xF8])
COLOURS_REPORTS = 7
KEYMAP_REPORTS = 9

FN = 0xB000

BRIGHTNESS = ("Off", "Very low", "Low", "Medium", "High", "Full")   # 0-5
SPEEDS = ("Very slow", "Slow", "Normal", "Fast", "Very fast")       # 1-5
SLEEP = ("5 min", "10 min", "20 min", "30 min", "Never")            # 1-5


def _capacity(reports: int, header: bytes) -> int:
    return reports * (REPORT_LEN - 3) - len(header)


KEYMAP_SLOTS = _capacity(KEYMAP_REPORTS, KEYMAP_HEADER) // 4
COLOUR_SLOTS = _capacity(COLOURS_REPORTS, COLOURS_HEADER) // 3


def key(usage: int, mods: int = 0) -> int:
    return (mods & 0xFF) << 16 | (usage & 0xFF) << 8


def consumer(usage: int) -> int:
    return 0x01000000 | (usage & 0xFFFF)


def split(code: int) -> tuple[str, int, int]:
    """('fn' | 'consumer' | 'key', usage, modifier bits) of a key-map code."""
    if code == FN:
        return "fn", 0, 0
    if code >> 24 == 0x01:
        return "consumer", code & 0xFFFF, 0
    return "key", (code >> 8) & 0xFF, (code >> 16) & 0xFF


def _message(header: bytes, data: bytes, reports: int) -> list[bytes]:
    stream = header + data
    room = reports * (REPORT_LEN - 3)
    if len(stream) > room:
        raise ValueError("data does not fit the message")
    stream = stream.ljust(room, b"\x00")
    out = []
    for i in range(reports):
        chunk = stream[i * (REPORT_LEN - 3):(i + 1) * (REPORT_LEN - 3)]
        out.append(bytes([REPORT_ID, reports, i + 1]) + chunk)
    return out


def lighting(mode: int, brightness: int, speed: int, colour: tuple[int, int, int],
             random_colour: bool, sleep: int, order=(0, 1, 2)) -> bytes:
    if not 0 <= brightness <= 5 or not 1 <= speed <= 5 or not 1 <= sleep <= 5:
        raise ValueError("brightness 0-5, speed 1-5, sleep 1-5")
    rgb = ordered(colour, order)
    body = bytes([mode & 0xFF, 0, speed, brightness, *rgb, 1 if random_colour else 0, sleep])
    return _message(LIGHT_HEADER, body, 1)[0]


def ordered(colour: tuple[int, int, int], order=(0, 1, 2)) -> bytes:
    """Colour bytes in the board's channel order (KB.ini RGBIndex)."""
    return bytes(colour[i] & 0xFF for i in order)


def key_colours(colours: dict[int, tuple[int, int, int]], order=(0, 1, 2)) -> list[bytes]:
    """{key buffer index: (r, g, b)}; keys left out stay dark."""
    data = bytearray(COLOUR_SLOTS * 3)
    for index, c in colours.items():
        if not 0 <= index < COLOUR_SLOTS:
            raise ValueError(f"key index {index} out of range")
        data[index * 3:index * 3 + 3] = ordered(c, order)
    return _message(COLOURS_HEADER, bytes(data), COLOURS_REPORTS)


def key_map(codes: dict[int, int]) -> list[bytes]:
    """{key buffer index: code}; every key of the board must be in it, slots left out are 0."""
    data = bytearray(KEYMAP_SLOTS * 4)
    for index, code in codes.items():
        if not 0 <= index < KEYMAP_SLOTS:
            raise ValueError(f"key index {index} out of range")
        data[index * 4:index * 4 + 4] = (code & 0xFFFFFFFF).to_bytes(4, "big")
    return _message(KEYMAP_HEADER, bytes(data), KEYMAP_REPORTS)
