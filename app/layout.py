"""Physical layouts of RK boards: matrix slot, label, key width (units), scan code.

The RK M75 HE has a hand-made layout; every other RK board in RK's web driver list
is drawn from the key map the keyboard reports. The board plugged in is picked
when this module is first imported.

M75: slot = row * 21 + column. Skipped slots (75, 85, 108-110, ...) are ISO or
unused matrix positions; the bottom three rows were verified by pressing each
key. Scan codes are PS/2 set 1; 0xE0xx marks an extended key.
"""

import time

M75_ROWS = [
    [(0, "Esc", 1, 0x01), None, (1, "F1", 1, 0x3B), (2, "F2", 1, 0x3C), (3, "F3", 1, 0x3D), (4, "F4", 1, 0x3E), None,
     (5, "F5", 1, 0x3F), (6, "F6", 1, 0x40), (7, "F7", 1, 0x41), (8, "F8", 1, 0x42), None,
     (9, "F9", 1, 0x43), (10, "F10", 1, 0x44), (11, "F11", 1, 0x57), (12, "F12", 1, 0x58), None,
     (13, "Del", 1, 0xE053)],
    [(21, "`", 1, 0x29), (22, "1", 1, 0x02), (23, "2", 1, 0x03), (24, "3", 1, 0x04), (25, "4", 1, 0x05),
     (26, "5", 1, 0x06), (27, "6", 1, 0x07), (28, "7", 1, 0x08), (29, "8", 1, 0x09), (30, "9", 1, 0x0A),
     (31, "0", 1, 0x0B), (32, "-", 1, 0x0C), (33, "=", 1, 0x0D), (34, "Bksp", 2, 0x0E), (35, "Home", 1, 0xE047)],
    [(42, "Tab", 1.5, 0x0F), (43, "Q", 1, 0x10), (44, "W", 1, 0x11), (45, "E", 1, 0x12), (46, "R", 1, 0x13),
     (47, "T", 1, 0x14), (48, "Y", 1, 0x15), (49, "U", 1, 0x16), (50, "I", 1, 0x17), (51, "O", 1, 0x18),
     (52, "P", 1, 0x19), (53, "[", 1, 0x1A), (54, "]", 1, 0x1B), (55, "\\", 1.5, 0x2B), (56, "PgUp", 1, 0xE049)],
    [(63, "Caps", 1.75, 0x3A), (64, "A", 1, 0x1E), (65, "S", 1, 0x1F), (66, "D", 1, 0x20), (67, "F", 1, 0x21),
     (68, "G", 1, 0x22), (69, "H", 1, 0x23), (70, "J", 1, 0x24), (71, "K", 1, 0x25), (72, "L", 1, 0x26),
     (73, ";", 1, 0x27), (74, "'", 1, 0x28), (76, "Enter", 2.25, 0x1C), (77, "PgDn", 1, 0xE051)],
    [(84, "Shift", 2.25, 0x2A), (86, "Z", 1, 0x2C), (87, "X", 1, 0x2D), (88, "C", 1, 0x2E), (89, "V", 1, 0x2F),
     (90, "B", 1, 0x30), (91, "N", 1, 0x31), (92, "M", 1, 0x32), (93, ",", 1, 0x33), (94, ".", 1, 0x34),
     (95, "/", 1, 0x35), (96, "Shift", 1.75, 0x36), (97, "Up", 1, 0xE048)],
    [(105, "Ctrl", 1.25, 0x1D), (106, "Win", 1.25, 0xE05B), (107, "Alt", 1.25, 0x38), (111, "Space", 6.25, 0x39),
     (114, "Alt", 1.25, 0xE038), (115, "Fn", 1, None), (116, "Ctrl", 1.25, 0xE01D), (117, "Left", 1, 0xE04B),
     (118, "Down", 1, 0xE050), (119, "Right", 1, 0xE04D)],
]

def rk_rows_from_keyboard(path: bytes) -> list[list[tuple]] | None:
    """Rows built from the key map an RK keyboard reports (row, column, key code per key).

    Slot = row * 21 + column, the same matrix numbering the M75 uses, so the
    diagnostic ADC pages line up. Labels, scan codes and widths come from the
    key codes; physical gaps between key groups are not reported, so none are drawn.
    """
    try:
        import hid

        from . import protocol as p
        dev = hid.device()
        dev.open_path(path)
        try:
            dev.set_nonblocking(True)
            keys = []
            for rows in ((0, 1), (2, 3), (4, 5)):
                while dev.read(64):
                    pass
                dev.write([0, *p.req_key_map(*rows)])
                reply, end = None, time.perf_counter() + 0.3
                while time.perf_counter() < end and reply is None:
                    r = dev.read(64)
                    if r and r[0] == p.HEADER and r[2] == p.CMD_DEFKEY | 0x80:
                        reply = bytes(r[4:])
                    elif not r:
                        time.sleep(0.001)
                if reply is None:
                    return None
                keys += p.parse_key_map(reply)
        finally:
            dev.close()
    except Exception:
        return None
    out = []
    for row in range(6):
        cells = sorted((col, code) for r, col, code in keys if r == row)
        if cells:
            out.append([(row * 21 + col, *_cell(code)) for col, code in cells])
    return out or None


def _cell(code: int) -> tuple:
    from .keycodes import describe
    label, scan, width = describe(code)
    return label, width, scan


def _detect() -> list | None:
    """Rows built from the key map of the RK board plugged in, or None for the M75 HE / no board."""
    try:
        from .device import PID, find
        rk = find()
        if rk and rk[1] != PID:
            return rk_rows_from_keyboard(rk[0])
    except Exception:
        pass
    return None


def keys_of(rows) -> dict[int, dict]:
    return {k[0]: {"slot": k[0], "label": k[1], "w": k[2], "scan": k[3]} for row in rows for k in row if k}


M75_KEYS = keys_of(M75_ROWS)
# layout of the RK board plugged in; the M75 layout when it is the M75 HE or the key map cannot be read
RK_ROWS = _detect() or M75_ROWS
RK_KEYS = keys_of(RK_ROWS)
