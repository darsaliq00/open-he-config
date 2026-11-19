"""Backups of the keyboard's onboard configs, as plain JSON files.

A snapshot holds everything a config stores: global travel, lighting, and per key the trigger
mode, distances, Fn layers, switch type, colour and advanced function (DKS, multi-point,
mod-tap, toggle, END, SOCD, rappy snappy, macro). The keyboard cannot report macro steps, so
those come from the app's own copy (macros.json) when it has one.

Restoring compares the snapshot with what the keyboard holds now and writes only what differs,
then reads it back. The same file format is used to share a setup with someone else.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from . import protocol as p
from .kbconfig import (DISTANCES, LAYERS, ReadError, _ask, _fields, read_advanced, read_settings,
                       write_global, write_key_colors, write_lighting, write_socd)

FORMAT = 1
LIGHT_KEYS = ("on", "reverse", "fast_response", "flags", "brightness", "mode", "speed", "sleep",
              "static_color", "colors")
SOCD_MODE_IDS = {v: k for k, v in p.SOCD_MODES.items()}


# ---------------------------------------------------------------- capture

def capture(request, macro_copies: dict | None = None, settings: dict | None = None) -> dict:
    """Snapshot of the config that is active now."""
    s = settings or read_settings(request)
    keys = {}
    for k in s["keys"].values():
        entry = {"mode_raw": k["mode_raw"], "axis": k.get("axis", 0), "color": list(k.get("color", (0, 0, 0)))}
        for name in (*DISTANCES, *LAYERS):
            if name in k:
                entry[name] = k[name]
        if k["mode"]["advanced"] != "none":
            adv = read_advanced(request, k)
            if k["mode_raw"] & 15 == p.ADV_MACRO and macro_copies and str(k["id"]) in macro_copies:
                adv = {**adv, "steps": macro_copies[str(k["id"])]}
            entry["advanced"] = adv
        keys[str(k["id"])] = entry
    return {"global": s["global"], "lighting": {x: s["lighting"][x] for x in LIGHT_KEYS if x in s["lighting"]},
            "keys": keys}


def header(settings: dict, configs: dict) -> dict:
    return {"app": "Open HE Config", "format": FORMAT, "saved": datetime.now().isoformat(timespec="seconds"),
            "keyboard": {"name": settings["name"], "firmware": settings["firmware"],
                         "protocol": settings["protocol"]},
            "configs": configs}


def switch_config(link, index: int, settle: float = 0.5) -> None:
    """Make onboard config `index` (0-3) active; the keyboard restarts its USB link, so reconnect."""
    link.request(p.req_set_order(p.ORDER_CONFIG, index))
    link.close()
    for _ in range(24):
        time.sleep(settle)
        if link.open() and link.request(p.req_order(p.ORDER_CONFIG)) is not None:
            return
        link.close()
    raise ReadError("keyboard did not come back after switching config")


def capture_all(link, macro_copies: dict | None = None, progress=lambda text: None) -> dict:
    """Snapshots of all four onboard configs; ends on the config that was active before."""
    first = read_settings(link.request)
    start = first["system"]["config"]
    configs = {}
    try:
        for i in range(4):
            if i != start:
                progress(f"Reading config {i + 1}…")
                switch_config(link, i)
                configs[str(i + 1)] = capture(link.request, macro_copies)
            else:
                progress(f"Reading config {i + 1}…")
                configs[str(i + 1)] = capture(link.request, macro_copies, first)
    finally:
        if read_settings_config(link) != start:
            progress("Switching back…")
            switch_config(link, start)
    return header(first, configs)


def read_settings_config(link) -> int | None:
    reply = link.request(p.req_order(p.ORDER_CONFIG))
    return p.parse_order(p.ORDER_CONFIG, reply) if reply else None


# ---------------------------------------------------------------- files

def save(path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def load(path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("app") != "Open HE Config" or not isinstance(data.get("configs"), dict) or not data["configs"]:
        raise ValueError("not an Open HE Config backup file")
    if data.get("format", 0) > FORMAT:
        raise ValueError("this file was saved by a newer version of the app")
    return data


# ---------------------------------------------------------------- restore

def _same_advanced(want: dict, now: dict) -> bool:
    keys = [x for x in want if x != "steps"]
    return all(want[x] == now.get(x) for x in keys)


def plan(snapshot: dict, settings: dict, request=None) -> dict:
    """What restoring `snapshot` would change on the keyboard as it is now.

    With `request`, advanced keys are read from the keyboard so unchanged ones are skipped."""
    now = {str(k["id"]): k for k in settings["keys"].values()}
    out = {"global": False, "lighting": False, "fields": [], "colors": {}, "advanced": [], "modes": [],
           "missing": [], "no_macro_steps": []}
    g = snapshot["global"]
    out["global"] = any(abs(g[x] - settings["global"][x]) > 0.0005 for x in g)
    out["lighting"] = any(snapshot["lighting"].get(x) != settings["lighting"].get(x)
                          for x in snapshot["lighting"] if x != "flags")
    for kid, want in snapshot["keys"].items():
        k = now.get(kid)
        if k is None:
            out["missing"].append(int(kid))
            continue
        key_id = int(kid)
        for name, layout in (*DISTANCES.items(), *LAYERS.items()):
            if name in want and want[name] != k.get(name):
                value = round(want[name] * 1000) if name in DISTANCES else want[name]
                out["fields"].append((key_id, layout, value))
        if want.get("axis", 0) != k.get("axis", 0):
            out["fields"].append((key_id, p.LAYOUT_AXIS, want["axis"]))
        if tuple(want["color"]) != tuple(k.get("color", ())):
            out["colors"][key_id] = tuple(want["color"])
        adv_want = want["mode_raw"] & 15
        rewrite = False
        if adv_want and "advanced" in want:
            if adv_want == p.ADV_MACRO and "steps" not in want["advanced"]:
                if k["mode_raw"] & 15 != p.ADV_MACRO:
                    out["no_macro_steps"].append(key_id)
                    continue          # cannot rebuild this macro: leave the key's mode alone
            else:
                same = (k["mode_raw"] & 15 == adv_want and request is not None
                        and _same_advanced(want["advanced"], read_advanced(request, k)))
                if not same:
                    out["advanced"].append((k, adv_want, want["advanced"]))
                    rewrite = True
        if want["mode_raw"] != k["mode_raw"] or rewrite:
            out["modes"].append((key_id, want["mode_raw"]))
    return out


def summary(pl: dict) -> str:
    parts = []
    if pl["global"]:
        parts.append("global travel")
    if pl["lighting"]:
        parts.append("lighting effect")
    keys = {f[0] for f in pl["fields"]} | {m[0] for m in pl["modes"]} | set(pl["colors"])
    if keys:
        parts.append(f"{len(keys)} key(s)")
    if pl["advanced"]:
        parts.append(f"{len(pl['advanced'])} advanced key(s)")
    text = ", ".join(parts) if parts else "nothing: the keyboard already matches"
    if pl["no_macro_steps"]:
        text += f". {len(pl['no_macro_steps'])} macro key(s) have no saved steps and are left as they are"
    if pl["missing"]:
        text += f". {len(pl['missing'])} key(s) in the file are not on this keyboard"
    return text


def _write_advanced(request, key: dict, kind: int, d: dict, macro_ids_in_use: set[int]):
    k = key["id"]
    if kind == p.ADV_DKS:
        _ask(request, p.req_set_dks(k, d["codes"], d["trps"], d["first_mm"], d["second_mm"]))
    elif kind == p.ADV_MPT:
        _ask(request, p.req_set_mpt(k, d["codes"], d["depths"]))
    elif kind == p.ADV_MT:
        _ask(request, p.req_set_mt(k, d["hold"], d["tap"], d["delay_ms"]))
    elif kind == p.ADV_TGL:
        _ask(request, p.req_set_tgl(k, d["code"], d["delay_ms"]))
    elif kind == p.ADV_END:
        _ask(request, p.req_set_end(k, d["code"]))
    elif kind == p.ADV_RS:
        _ask(request, p.req_set_rs(k, d["key2"]))
    elif kind == p.ADV_SOCD:
        write_socd(request, d["key1"], d["key2"], SOCD_MODE_IDS.get(d["mode"], 0), d.get("delay", 0))
    elif kind == p.ADV_MACRO:
        steps = d["steps"]
        events = [tuple(e) for e in steps["events"]]
        mid = d.get("id", 0)
        if mid in macro_ids_in_use:
            mid = next(i for i in range(p.MAX_MACROS) if i not in macro_ids_in_use)
        macro_ids_in_use.add(mid)
        for i in range(0, len(events), p.MACRO_EVENTS_PER_REPORT):
            _ask(request, p.req_macro_events(p.MACRO_BUFFER + i, events[i:i + p.MACRO_EVENTS_PER_REPORT]))
        _ask(request, p.req_set_macro_mode(k, mid, len(events), steps["mode"], steps["repeat"], steps["interval_ms"]))


def restore(request, snapshot: dict, settings: dict, progress=lambda text: None) -> dict:
    """Write what differs between `snapshot` and the active config; returns the plan it carried out."""
    pl = plan(snapshot, settings, request)
    if pl["global"]:
        progress("Global travel…")
        g = snapshot["global"]
        write_global(request, g["actuation_mm"], g["press_dead_mm"], g["release_dead_mm"])
    fields = list(pl["fields"])
    if fields:
        progress(f"Writing {len(fields)} key setting(s)…")
        for i in range(0, len(fields), p.KEY_FIELDS_PER_REPORT):
            _ask(request, p.req_set_key_fields(fields[i:i + p.KEY_FIELDS_PER_REPORT]))
    if pl["advanced"]:
        progress(f"Writing {len(pl['advanced'])} advanced key(s)…")
        in_use = {read_advanced(request, k)["id"] for k in settings["keys"].values()
                  if k["mode_raw"] & 15 == p.ADV_MACRO and str(k["id"]) not in snapshot["keys"]}
        for key, kind, data in pl["advanced"]:
            _write_advanced(request, key, kind, data, in_use)
    if pl["modes"]:
        progress("Trigger modes…")
        modes = [(kid, p.LAYOUT_MODE, raw) for kid, raw in pl["modes"]]
        for i in range(0, len(modes), p.KEY_FIELDS_PER_REPORT):
            _ask(request, p.req_set_key_fields(modes[i:i + p.KEY_FIELDS_PER_REPORT]))
        fields += modes
    if pl["lighting"]:
        progress("Lighting…")
        write_lighting(request, {**settings["lighting"], **snapshot["lighting"]})
    if pl["colors"]:
        progress(f"Colours of {len(pl['colors'])} key(s)…")
        write_key_colors(request, pl["colors"])
    if fields:
        progress("Checking…")
        _verify(request, fields)
    return pl


def _verify(request, fields: list[tuple[int, int, int]]):
    for i in range(0, len(fields), p.KEY_FIELDS_PER_REPORT):
        chunk = fields[i:i + p.KEY_FIELDS_PER_REPORT]
        got = {(k, layout): v for k, layout, v in
               p.parse_key_fields(_ask(request, p.req_key_fields([(k, layout) for k, layout, _ in chunk])))}
        for k, layout, value in chunk:
            if got.get((k, layout)) != value:
                raise ReadError(f"key 0x{k:02X} setting {layout} reads back as {got.get((k, layout))}, wrote {value}")
