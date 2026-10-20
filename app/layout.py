"""Physical layouts: matrix slot, label, key width (units), scan code.

Supports the RK M75 HE (hand-made layout), every other RK board in RK's web
driver list (drawn from the key map the keyboard reports) and the AJAZZ AK680
V2. The keyboard plugged in is picked when this module is first imported.

M75: slot = row * 21 + column. Skipped slots (75, 85, 108-110, ...) are ISO or
unused matrix positions; the bottom three rows were verified by pressing each
key. Scan codes are PS/2 set 1; 0xE0xx marks an extended key. They let the key
blocker recognise which physical key Windows reports.
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

# AJAZZ AK680 V2 (65%): slot = the key value AJAZZ's own driver uses (row * 16 + column)
AK680_ROWS = [
    [(0, "Esc", 1, 0x01), (17, "1", 1, 0x02), (18, "2", 1, 0x03), (19, "3", 1, 0x04), (20, "4", 1, 0x05),
     (21, "5", 1, 0x06), (22, "6", 1, 0x07), (23, "7", 1, 0x08), (24, "8", 1, 0x09), (25, "9", 1, 0x0A),
     (26, "0", 1, 0x0B), (27, "-", 1, 0x0C), (28, "=", 1, 0x0D), (92, "Bksp", 2, 0x0E), (104, "Home", 1, 0xE047)],
    [(32, "Tab", 1.5, 0x0F), (33, "Q", 1, 0x10), (34, "W", 1, 0x11), (35, "E", 1, 0x12), (36, "R", 1, 0x13),
     (37, "T", 1, 0x14), (38, "Y", 1, 0x15), (39, "U", 1, 0x16), (40, "I", 1, 0x17), (41, "O", 1, 0x18),
     (42, "P", 1, 0x19), (43, "[", 1, 0x1A), (44, "]", 1, 0x1B), (60, "\\", 1.5, 0x2B), (106, "Del", 1, 0xE053)],
    [(48, "Caps", 1.75, 0x3A), (49, "A", 1, 0x1E), (50, "S", 1, 0x1F), (51, "D", 1, 0x20), (52, "F", 1, 0x21),
     (53, "G", 1, 0x22), (54, "H", 1, 0x23), (55, "J", 1, 0x24), (56, "K", 1, 0x25), (57, "L", 1, 0x26),
     (58, ";", 1, 0x27), (59, "'", 1, 0x28), (76, "Enter", 2.25, 0x1C), (105, "PgUp", 1, 0xE049)],
    [(64, "Shift", 2.25, 0x2A), (65, "Z", 1, 0x2C), (66, "X", 1, 0x2D), (67, "C", 1, 0x2E), (68, "V", 1, 0x2F),
     (69, "B", 1, 0x30), (70, "N", 1, 0x31), (71, "M", 1, 0x32), (72, ",", 1, 0x33), (73, ".", 1, 0x34),
     (74, "/", 1, 0x35), (75, "Shift", 1.75, 0x36), (90, "Up", 1, 0xE048), (108, "PgDn", 1, 0xE051)],
    [(80, "Ctrl", 1.25, 0x1D), (81, "Win", 1.25, 0xE05B), (82, "Alt", 1.25, 0x38), (83, "Space", 6.25, 0x39),
     (84, "Alt", 1, 0xE038), (85, "Fn", 1, None), (87, "Ctrl", 1, 0xE01D), (88, "Left", 1, 0xE04B),
     (89, "Down", 1, 0xE050), (91, "Right", 1, 0xE04D)],
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


def _detect() -> tuple[str, list | None]:
    """('m75' | 'rk:<pid>' | 'ak680', rows built from the keyboard for other RK boards).

    The RK M75 HE keeps its hand-made layout; any other RK board in RK's list is
    drawn from its own key map. The AJAZZ AK680 V2 is used only if no RK board is in.
    """
    try:
        import hid

        from .device import PID, find
        rk = find()
        if rk:
            if rk[1] == PID:
                return "m75", None
            return f"rk:{rk[1]:04x}", rk_rows_from_keyboard(rk[0])
        if any(d["usage_page"] == 0xFF68 for d in hid.enumerate(0x0C45, 0x80BC)):
            return "ak680", None
    except Exception:
        pass
    return "m75", None


def keys_of(rows) -> dict[int, dict]:
    return {k[0]: {"slot": k[0], "label": k[1], "w": k[2], "scan": k[3]} for row in rows for k in row if k}


M75_KEYS = keys_of(M75_ROWS)
AK680_KEYS = keys_of(AK680_ROWS)

MODEL, _built = _detect()
if MODEL.startswith("rk:") and not _built:
    MODEL = "m75"   # could not read the key map; the M75 layout is the closest guess
# layout of the RK board plugged in (M75 Config uses this whatever Analog Drive detects)
RK_ROWS = _built or M75_ROWS
RK_KEYS = keys_of(RK_ROWS)
ROWS = AK680_ROWS if MODEL == "ak680" else RK_ROWS
KEYS = keys_of(ROWS)


def slot_of(label: str) -> int:
    return next(s for s, k in KEYS.items() if k["label"] == label)


def for_model(profile: dict) -> dict:
    """Return profile with its slots moved to the keyboard plugged in.

    Slot ids differ between keyboards (W is 44 on the M75, 34 on the AK680), so
    a profile records the model it was made on; profiles without one come from
    the M75. Keys are matched by scan code, and bindings for keys this keyboard
    lacks are dropped.
    """
    src = profile.get("model", "m75")
    if src == MODEL:
        return profile
    # other RK boards are not known here; their bindings carry the scan code instead
    src_rows = {"ak680": AK680_ROWS, "m75": M75_ROWS}.get(src)
    scan_of = {k[0]: k[3] for row in src_rows for k in row if k} if src_rows else {}
    slot_by_scan = {k["scan"]: s for s, k in KEYS.items() if k["scan"]}
    bindings = []
    for b in profile.get("bindings", []):
        slot = slot_by_scan.get(b.get("scan") or scan_of.get(b["slot"]))
        if slot is not None:
            bindings.append({**b, "slot": slot})
    return {**profile, "model": MODEL, "bindings": bindings}


def for_ui() -> list[list[dict]]:
    return [[({"gap": 0.5} if k is None else {"slot": k[0], "label": k[1], "w": k[2]}) for k in row] for row in ROWS]
