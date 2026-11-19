"""One-click setups for the active config, built from the same writes the pages use.

Each preset says how to set groups of keys (trigger mode and distances), which SOCD pairs to make
and whether W gets the sprint DKS. Before applying, the app saves an automatic backup, so a preset
can always be undone from the Backup page.
"""

from . import protocol as p
from .kbconfig import read_settings, write_advanced, write_global, write_keys, write_socd

# HID key ids
W, A, S, D, Q, E, SHIFT = 0x1A, 0x04, 0x16, 0x07, 0x14, 0x08, 0xE1
MOVE = (W, A, S, D)
ACTION = (0x1E, 0x1F, 0x20, 0x21, 0x22,              # 1-5
          Q, E, 0x15, 0x09, 0x0A, 0x0B,               # Q E R F G H
          0x1D, 0x1B, 0x06, 0x19, 0x05, 0x11, 0x10,   # Z X C V B N M
          0x2B, SHIFT, 0xE0, 0xE2, 0x2C)              # Tab LShift LCtrl LAlt Space
GAMING = MOVE + (Q, E)       # keys whose SOCD / DKS a preset takes over

PRESETS = {
    "battle_royale": {
        "name": "Battle royale (PUBG, Apex, Fortnite)",
        "about": "Rapid trigger on WASD (0.6 mm, 0.15 mm) and action keys (1.0 mm, 0.3 mm), SOCD on A/D and "
                 "Q/E, and W sprints (adds Shift) when pressed to the bottom.",
        "global_mm": 2.0,
        "groups": [(MOVE, {"touch": "rt", "actuation": 0.6, "rt_press": 0.15, "rt_release": 0.15}),
                   (ACTION, {"touch": "rt", "actuation": 1.0, "rt_press": 0.3, "rt_release": 0.3})],
        "socd": [(A, D), (Q, E)],
        "sprint": True,
    },
    "fps": {
        "name": "Competitive FPS (Valorant, CS2)",
        "about": "Fast rapid trigger on WASD (0.4 mm, 0.1 mm) for counter-strafing, SOCD on A/D, action keys on "
                 "their own 1.2 mm actuation.",
        "global_mm": 2.0,
        "groups": [(MOVE, {"touch": "rt", "actuation": 0.4, "rt_press": 0.1, "rt_release": 0.1}),
                   (ACTION, {"touch": "single", "actuation": 1.2})],
        "socd": [(A, D)],
        "sprint": False,
    },
    "racing": {
        "name": "Racing (with Analog Drive)",
        "about": "Plain keys with a deep 1.5 mm actuation on WASD so light presses only steer the virtual pad, "
                 "no SOCD so both directions can be held.",
        "global_mm": 2.0,
        "groups": [(MOVE, {"touch": "single", "actuation": 1.5}),
                   (ACTION, {"touch": "global"})],
        "socd": [],
        "sprint": False,
    },
    "typing": {
        "name": "Typing",
        "about": "Every gaming key back to the global 1.8 mm actuation, rapid trigger, SOCD and DKS off.",
        "global_mm": 1.8,
        "groups": [(MOVE + ACTION, {"touch": "global"})],
        "socd": [],
        "sprint": False,
    },
}


def apply(request, preset_id: str, progress=lambda text: None) -> None:
    preset = PRESETS[preset_id]
    s = read_settings(request)
    by_id = {k["id"]: k for k in s["keys"].values()}
    g = s["global"]
    if abs(g["actuation_mm"] - preset["global_mm"]) > 0.0005:
        progress("Global travel…")
        write_global(request, preset["global_mm"], g["press_dead_mm"], g["release_dead_mm"])

    # clear SOCD / DKS the preset takes over, so old pairs do not linger
    stale = [by_id[k] for k in GAMING if k in by_id and by_id[k]["mode_raw"] & 15 in (p.ADV_SOCD, p.ADV_DKS)]
    if stale:
        progress("Clearing old SOCD and DKS…")
        for k in write_keys(request, stale, {"clear_advanced": True}):
            by_id[k["id"]] = k

    for ids, changes in preset["groups"]:
        keys = [by_id[k] for k in ids if k in by_id]
        if keys:
            progress(f"Setting {len(keys)} key(s)…")
            for k in write_keys(request, keys, changes):
                by_id[k["id"]] = k

    for a, b in preset["socd"]:
        if a in by_id and b in by_id:
            progress("SOCD pairs…")
            write_socd(request, a, b, 0)
            request(p.req_set_key_fields([(k["id"], p.LAYOUT_MODE, p.mode_value(k["mode"]["touch"], p.ADV_SOCD))
                                          for k in (by_id[a], by_id[b])]))

    if preset["sprint"] and W in by_id:
        progress("W sprint…")
        bits = lambda cells: sum(bit for bit, on in zip(p.DKS_CELLS, cells) if on)
        write_advanced(request, by_id[W], p.ADV_DKS, {
            "codes": [W, SHIFT, 0, 0],
            "trps": [bits((1, 1, 1, 1, 1, 1, 1)), bits((0, 0, 1, 1, 1, 0, 0)), 0, 0],
            "first_mm": by_id[W].get("actuation") or 0.6, "second_mm": 3.2})
