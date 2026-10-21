"""Reads and writes the keyboard's own stored settings (firmware side, not the gamepad profile).

`request` is any callable that sends one protocol report and returns the reply
payload or None, e.g. config_app.link.Link.request.
"""

import time

from . import protocol as p

# per-key fields read in bulk; distances are stored in micrometres
DISTANCES = {
    "actuation": p.LAYOUT_DB0,
    "rt_press": p.LAYOUT_RTP,
    "rt_release": p.LAYOUT_RTR,
    "dead_press": p.LAYOUT_DP,
    "dead_release": p.LAYOUT_DR,
}
LAYERS = {"fn0": p.LAYOUT_FN0, "fn1": p.LAYOUT_FN1, "fn2": p.LAYOUT_FN2, "fn3": p.LAYOUT_FN3}
FIELDS = {"mode": p.LAYOUT_MODE, **DISTANCES, **LAYERS, "axis": p.LAYOUT_AXIS}
_NAMES = {v: k for k, v in FIELDS.items()}


class ReadError(Exception):
    pass


def _ask(request, report):
    reply = request(report)
    if reply is None:
        raise ReadError("keyboard did not answer")
    return reply


def read_key_ids(request) -> dict[int, int]:
    """slot -> key id (HID usage code) for every key in the matrix."""
    ids = {}
    for rows in ((0, 1), (2, 3), (4, 5)):
        for row, col, key in p.parse_key_map(_ask(request, p.req_key_map(*rows))):
            ids[row * 21 + col] = key
    return ids


def _order(request, order):
    return _ask(request, p.req_order(order))[2]


def read_system(request) -> dict:
    return {
        "os": "win" if _order(request, p.ORDER_QUERY_WIN_MODE) == 1 else "mac",
        "win_lock": bool(_order(request, p.ORDER_LOCK_WIN_KEY)),
        "top_dead_switch": bool(_order(request, p.ORDER_TOP_DEAD_SWITCH)),
        "polling_raw": _order(request, p.ORDER_POLLING),
        "config": _order(request, p.ORDER_CONFIG),
        "axes": read_axes(request),
    }


def read_axes(request) -> list[int]:
    """Switch type ids the keyboard offers (see app/axes.py); a key's "axis" indexes this list."""
    reply = request(p.req_order(p.ORDER_AXES))
    if reply is None:
        return []
    axes = []
    for a in p.parse_order(p.ORDER_AXES, reply):
        if a in (0, 0xFFFF):
            break
        axes.append(a)
    return axes


def read_settings(request) -> dict:
    """Everything the config app shows, in millimetres where it is a distance."""
    info = p.parse_sync(_ask(request, p.req_sync()))
    out = {
        "name": p.parse_order(p.ORDER_KEYBOARD_NAME, _ask(request, p.req_order(p.ORDER_KEYBOARD_NAME))),
        "firmware": info.app_version,
        "serial": info.serial,
        "key_type": info.key_type,
        "protocol": p.parse_order(p.ORDER_PROTOCOL_VERSION, _ask(request, p.req_order(p.ORDER_PROTOCOL_VERSION))),
        "global": p.parse_global_travel(_ask(request, p.req_global_travel())),
        "lighting": p.parse_lighting(_ask(request, p.req_lighting())),
        "system": read_system(request),
        "keys": {},
    }
    ids = read_key_ids(request)
    by_id = {key: slot for slot, key in ids.items()}
    wanted = [(key, layout) for key in ids.values() for layout in FIELDS.values()]
    for i in range(0, len(wanted), p.KEY_FIELDS_PER_REPORT):
        chunk = wanted[i:i + p.KEY_FIELDS_PER_REPORT]
        for key, layout, value in p.parse_key_fields(_ask(request, p.req_key_fields(chunk))):
            slot = by_id.get(key)
            if slot is None or layout not in _NAMES:
                continue
            _store(out["keys"].setdefault(slot, {"id": key}), layout, value)
    for slot, k in out["keys"].items():
        k["color"] = p.parse_key_color(_ask(request, p.req_key_color(k["id"])))[1:]
        if k.get("mode", {}).get("advanced") == "SOCD":
            k["socd"] = p.parse_socd(_ask(request, p.req_socd(k["id"])))
    return out


def _store(k: dict, layout: int, value: int):
    if layout == p.LAYOUT_MODE:
        k["mode"], k["mode_raw"] = p.parse_mode(value), value
    elif layout in LAYERS.values() or layout == p.LAYOUT_AXIS:
        k[_NAMES[layout]] = value
    else:
        k[_NAMES[layout]] = value / 1000


def _raw(key: dict, name: str, value) -> tuple[int, int, int]:
    if name == "touch":
        return key["id"], p.LAYOUT_MODE, p.mode_value(value, key["mode_raw"])
    if name == "clear_advanced":
        return key["id"], p.LAYOUT_MODE, p.mode_value(key["mode"]["touch"], 0)
    if name in LAYERS:
        return key["id"], LAYERS[name], value
    if name == "axis":
        return key["id"], p.LAYOUT_AXIS, int(value)
    return key["id"], DISTANCES[name], round(value * 1000)


def write_keys(request, keys: list[dict], changes: dict) -> list[dict]:
    """Write the same changes to several keys, then read them back.

    `keys` are entries of read_settings()["keys"]; `changes` maps field names to
    new values: "touch" -> "global"/"single"/"rt", distances in millimetres,
    "fn0".."fn3" -> key codes, "clear_advanced" -> True.
    Returns the updated entries. Raises ReadError if the keyboard does not
    answer or a value does not read back as written.
    """
    fields = [_raw(k, name, value) for k in keys for name, value in changes.items()]
    for i in range(0, len(fields), p.KEY_FIELDS_PER_REPORT):
        _ask(request, p.req_set_key_fields(fields[i:i + p.KEY_FIELDS_PER_REPORT]))
    got = {}
    for i in range(0, len(fields), p.KEY_FIELDS_PER_REPORT):
        chunk = [(k, layout) for k, layout, _ in fields[i:i + p.KEY_FIELDS_PER_REPORT]]
        got.update({(k, layout): v for k, layout, v in p.parse_key_fields(_ask(request, p.req_key_fields(chunk)))})
    updated = {k["id"]: {kk: vv for kk, vv in k.items() if not (kk == "socd" and "clear_advanced" in changes)}
               for k in keys}
    for key_id, layout, value in fields:
        if got.get((key_id, layout)) != value:
            raise ReadError(f"{_NAMES[layout]} of key 0x{key_id:02X} reads back as {got.get((key_id, layout))}, "
                            f"wrote {value}")
        _store(updated[key_id], layout, value)
    return [updated[k["id"]] for k in keys]


def write_key(request, key: dict, changes: dict) -> dict:
    return write_keys(request, [key], changes)[0]


def write_global(request, actuation: float, press_dead: float, release_dead: float) -> dict:
    _ask(request, p.req_set_global_travel(actuation, press_dead, release_dead))
    got = p.parse_global_travel(_ask(request, p.req_global_travel()))
    want = {"actuation_mm": actuation, "press_dead_mm": press_dead, "release_dead_mm": release_dead}
    if any(abs(got[k] - v) > 0.0005 for k, v in want.items()):
        raise ReadError(f"global travel reads back as {got}")
    return got


def write_lighting(request, light: dict) -> dict:
    _ask(request, p.req_set_lighting(light))
    got = p.parse_lighting(_ask(request, p.req_lighting()))
    for k in ("on", "brightness", "mode", "speed", "sleep", "static_color", "colors", "reverse"):
        if got[k] != light[k]:
            raise ReadError(f"lighting {k} reads back as {got[k]}, wrote {light[k]}")
    return got


def write_key_colors(request, colors: dict[int, tuple[int, int, int]]) -> None:
    """key id -> (r, g, b); stored with one save at the end."""
    items = [(k, *rgb) for k, rgb in colors.items()]
    for i in range(0, len(items), p.KEY_COLORS_PER_REPORT):
        _ask(request, p.req_set_key_colors(items[i:i + p.KEY_COLORS_PER_REPORT]))
    # the save sends no reply, and right after it the keyboard is busy writing flash and may
    # answer with stale values, so wait a moment and retry a mismatch before calling it a failure
    request(p.req_save_key_colors())
    time.sleep(0.3)
    for k, rgb in colors.items():
        got = None
        for _ in range(15):
            reply = request(p.req_key_color(k))
            if reply is not None:
                got = tuple(p.parse_key_color(reply)[1:])
                if got == tuple(rgb):
                    break
            time.sleep(0.05)
        if got != tuple(rgb):
            raise ReadError(f"colour of key 0x{k:02X} reads back as {got}, wrote {rgb}")


def write_order(request, order: int, value: int, query: int | None = None, expect: int | None = None) -> None:
    _ask(request, p.req_set_order(order, value))
    if query is not None:
        got = _order(request, query)
        if got != expect:
            raise ReadError(f"setting reads back as {got}, wanted {expect}")


def write_socd(request, key1: int, key2: int, mode: int, delay: int = 0) -> dict:
    _ask(request, p.req_set_socd(key1, key2, mode, delay=delay))
    got = p.parse_socd(_ask(request, p.req_socd(key1)))
    if (got["key1"], got["key2"]) != (key1, key2) or got["mode"] != p.SOCD_MODES[mode]:
        raise ReadError(f"SOCD reads back as {got}")
    return got


ADV_NAMES = {p.ADV_DKS: "DKS", p.ADV_MPT: "MPT", p.ADV_MT: "MT", p.ADV_TGL: "TGL", p.ADV_END: "END",
             p.ADV_MACRO: "MCR", p.ADV_SOCD: "SOCD", p.ADV_RS: "RS"}


def _fields(request, key_id: int, layouts) -> dict[int, int]:
    return {layout: v for _, layout, v in p.parse_key_fields(_ask(request, p.req_key_fields(
        [(key_id, layout) for layout in layouts])))}


def read_advanced(request, key: dict) -> dict:
    """Details of the key's advanced function, read fresh from the keyboard."""
    kind = key["mode_raw"] & 15
    k = key["id"]
    if kind == p.ADV_DKS:
        f = _fields(request, k, (*p.LAYOUT_DKS, *p.LAYOUT_TRPS, p.LAYOUT_DB1, p.LAYOUT_DB2))
        return {"codes": [f.get(x, 0) for x in p.LAYOUT_DKS], "trps": [f.get(x, 0) & 0xFF for x in p.LAYOUT_TRPS],
                "first_mm": f.get(p.LAYOUT_DB1, 0) / 1000, "second_mm": f.get(p.LAYOUT_DB2, 0) / 1000}
    if kind == p.ADV_MT:
        f = _fields(request, k, (p.LAYOUT_DKS[0], p.LAYOUT_DKS[1], p.LAYOUT_MT_DELAY))
        return {"hold": f.get(p.LAYOUT_DKS[0], 0), "tap": f.get(p.LAYOUT_DKS[1], 0),
                "delay_ms": f.get(p.LAYOUT_MT_DELAY, 0) * 10}
    if kind == p.ADV_MPT:
        return p.parse_mpt(_ask(request, p.req_mpt(k)))
    if kind == p.ADV_TGL:
        return p.parse_tgl(_ask(request, p.req_tgl(k)))
    if kind == p.ADV_END:
        return p.parse_end(_ask(request, p.req_end(k)))
    if kind == p.ADV_RS:
        return p.parse_rs(_ask(request, p.req_rs(k)))
    if kind == p.ADV_SOCD:
        return p.parse_socd(_ask(request, p.req_socd(k)))
    if kind == p.ADV_MACRO:
        return p.parse_macro_mode(_ask(request, p.req_macro_mode(k)))
    return {}


def write_advanced(request, key: dict, kind: int, data: dict) -> dict:
    """Store an advanced function on a key and return the key entry with its new mode."""
    k = key["id"]
    if kind == p.ADV_DKS:
        _ask(request, p.req_set_dks(k, data["codes"], data["trps"], data["first_mm"], data["second_mm"]))
    elif kind == p.ADV_MPT:
        _ask(request, p.req_set_mpt(k, data["codes"], data["depths"]))
    elif kind == p.ADV_MT:
        _ask(request, p.req_set_mt(k, data["hold"], data["tap"], data["delay_ms"]))
    elif kind == p.ADV_TGL:
        _ask(request, p.req_set_tgl(k, data["code"], data["delay_ms"]))
    elif kind == p.ADV_END:
        _ask(request, p.req_set_end(k, data["code"]))
    elif kind == p.ADV_RS:
        _ask(request, p.req_set_rs(k, data["key2"]))
    elif kind == p.ADV_MACRO:
        events = data["events"]
        for i in range(0, len(events), p.MACRO_EVENTS_PER_REPORT):
            _ask(request, p.req_macro_events(p.MACRO_BUFFER + i, events[i:i + p.MACRO_EVENTS_PER_REPORT]))
        _ask(request, p.req_set_key_fields([(k, p.LAYOUT_MODE, p.mode_value(key["mode"]["touch"], p.ADV_MACRO))]))
        _ask(request, p.req_set_macro_mode(k, data["id"], len(events), data["mode"], data["repeat"],
                                           data["interval_ms"]))
    else:
        raise ValueError(f"unknown advanced type {kind}")
    mode = _fields(request, k, (p.LAYOUT_MODE,)).get(p.LAYOUT_MODE)
    if mode is None or mode & 15 != kind:
        # the firmware marks the key itself for every type tested; set it if it did not
        _ask(request, p.req_set_key_fields([(k, p.LAYOUT_MODE, p.mode_value(key["mode"]["touch"], kind))]))
        mode = _fields(request, k, (p.LAYOUT_MODE,)).get(p.LAYOUT_MODE)
        if mode is None or mode & 15 != kind:
            raise ReadError(f"key mode reads back as {mode}, wanted advanced type {kind}")
    updated = dict(key)
    _store(updated, p.LAYOUT_MODE, mode)
    return updated


def write_polling(request, index: int) -> None:
    """Changes the polling rate; the keyboard restarts and reconnects afterwards."""
    request(p.req_set_order(p.ORDER_POLLING, index))
