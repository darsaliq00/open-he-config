"""Key sensor checks and trigger simulation, from the keyboard's own travel readings.

check_rest: with hands off, every key should read about 0 mm. A key that reads more is either
held down a little (keycap, stem) or has a sensor offset, and fires by itself if its actuation
point is set near that reading.

check_bottom: while the user presses every key fully, each should get near the switch's full
travel; one that stays short has a sticking switch or a sensor that does not see the magnet well.

simulate: replays a recorded press through the key's trigger settings (global, single, rapid
trigger) to show where the keyboard sends press and release.
"""

from __future__ import annotations

from statistics import median

REST_WARN_MM = 0.15      # reading at rest above this is worth a look
MARGIN_MM = 0.4          # keep the actuation point at least this far past a key's rest reading
BOTTOM_SHORT_MM = 2.8    # a full press that never gets this deep is short


def check_rest(samples: dict[int, list[float]], keys: dict[int, dict], global_mm: float) -> list[dict]:
    """samples: slot -> travel readings (mm) taken with hands off. Returns one finding per odd key."""
    out = []
    for slot, values in samples.items():
        if not values or slot not in keys:
            continue
        rest = median(values)
        if rest < REST_WARN_MM:
            continue
        k = keys[slot]
        touch = k.get("mode", {}).get("touch", "global")
        actuation = global_mm if touch == "global" else k.get("actuation", global_mm)
        risky = touch == "rt" or actuation < rest + MARGIN_MM
        out.append({
            "slot": slot, "rest_mm": round(rest, 2), "actuation_mm": actuation, "touch": touch,
            "level": "danger" if risky else "warn",
            "text": (f"Reads {rest:.2f} mm while untouched. "
                     + ("With rapid trigger on, it can press itself; turn rapid trigger off for this key."
                        if touch == "rt" else
                        f"Its actuation ({actuation:.2f} mm) is too close: set it to at least "
                        f"{rest + MARGIN_MM:.2f} mm." if risky else
                        f"Safe with its actuation of {actuation:.2f} mm; keep it above {rest + MARGIN_MM:.2f} mm.")),
        })
    return sorted(out, key=lambda f: (f["level"] != "danger", -f["rest_mm"]))


def check_bottom(maximum: dict[int, float], pressed: set[int], full_mm: float = 3.3) -> list[dict]:
    """maximum: slot -> deepest reading while the user pressed keys; only keys in `pressed` count."""
    out = []
    short = min(BOTTOM_SHORT_MM, full_mm - 0.4)
    for slot in pressed:
        m = maximum.get(slot, 0.0)
        if m < short:
            out.append({"slot": slot, "max_mm": round(m, 2), "level": "warn",
                        "text": f"Deepest press reached only {m:.2f} mm of about {full_mm:.1f} mm. The switch may "
                                "stick or the sensor may not see the magnet well; try reseating the switch."})
    return sorted(out, key=lambda f: f["max_mm"])


def simulate(trace: list[tuple[float, float]], key: dict, global_mm: float) -> list[tuple[float, bool]]:
    """trace: (seconds, travel mm). Returns (seconds, pressed) at each change, like the keyboard decides it.

    Global / single: pressed while past the actuation point. Rapid trigger: pressed once past the
    actuation point; then it releases after rising by the release distance from its deepest point
    and presses again after sinking by the press distance from its highest point; above the
    actuation point it is fully released."""
    touch = key.get("mode", {}).get("touch", "global")
    act = global_mm if touch == "global" else key.get("actuation", global_mm)
    press_d, release_d = key.get("rt_press", 0.3), key.get("rt_release", 0.3)
    events, down, inside, extreme = [], False, False, 0.0
    for t, x in trace:
        if touch != "rt":
            now = x >= act
        elif x < act:
            now, inside = False, False
        elif not inside:
            now, inside, extreme = True, True, x
        elif down:
            extreme = max(extreme, x)
            now = x > extreme - release_d
            if not now:
                extreme = x
        else:
            extreme = min(extreme, x)
            now = x >= extreme + press_d
            if now:
                extreme = x
        if now != down:
            events.append((t, now))
            down = now
    return events
