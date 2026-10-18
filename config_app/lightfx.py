"""On-screen preview of the keyboard's lighting.

The keyboard never reports what its LEDs show, so this simulates the selected
effect from the same settings the keyboard uses (palette, brightness, speed,
direction) and the live key presses. The firmware effects are only numbered,
so each number is matched to one of the styles below; the user picks the
match once and it is remembered in effects.json.
"""

import colorsys
import math
import random

from PySide6.QtGui import QColor

STYLES = {
    "static": "Solid colour",
    "breathing": "Breathing",
    "spectrum": "Colour cycle (whole board)",
    "wave_right": "Rainbow wave, sideways",
    "wave_down": "Rainbow wave, top to bottom",
    "wave_radial": "Rainbow ripple from the centre",
    "snake": "Snake / runner",
    "starlight": "Twinkling stars",
    "rain": "Raindrops falling",
    "reactive_key": "Pressed key lights up",
    "reactive_row": "Press lights the whole row",
    "reactive_column": "Press lights the whole column",
    "reactive_cross": "Press lights row and column",
    "ripple": "Press sends out a ring",
    "explode": "Press lights keys around it",
    "aurora": "Aurora (soft moving colour)",
}
REACTIVE = {"reactive_key", "reactive_row", "reactive_column", "reactive_cross", "ripple", "explode"}


def _hue(h: float, v: float = 1.0) -> QColor:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1.0, max(0.0, min(1.0, v)))
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def _scale(c: QColor, v: float) -> QColor:
    v = max(0.0, min(1.0, v))
    return QColor(int(c.red() * v), int(c.green() * v), int(c.blue() * v))


class LightSim:
    def __init__(self, keys: dict[int, tuple[float, float, int]]):
        """keys: slot -> (x, y centre in px, row index)."""
        self.keys = keys
        xs = [x for x, _, _ in keys.values()]
        ys = [y for _, y, _ in keys.values()]
        self.x0, self.x1 = min(xs), max(xs)
        self.y0, self.y1 = min(ys), max(ys)
        self.cx, self.cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        self.unit = 48.0
        self.presses: list[tuple[int, float]] = []   # (slot, time)
        self.drops: dict[int, float] = {}
        self.order = sorted(keys, key=lambda s: (keys[s][2], keys[s][0] if keys[s][2] % 2 == 0 else -keys[s][0]))

    def press(self, slot: int, t: float):
        if slot in self.keys:
            self.presses.append((slot, t))
            self.presses = self.presses[-40:]

    def frame(self, t: float, style: str | None, light: dict, custom: dict[int, QColor]) -> dict[int, QColor]:
        if not light.get("on", True):
            return {}
        level = 0.25 + 0.75 * min(5, light.get("brightness", 3)) / 5 if light.get("brightness", 3) else 0.08
        speed = 0.35 + 0.45 * light.get("speed", 2)
        sign = -1 if light.get("reverse") else 1
        palette = [QColor(c) for c in light.get("colors", ["#ffffff"] * 7)]
        idx = light.get("static_color", 0)
        base = palette[idx] if 0 <= idx < len(palette) else None   # None = rainbow choice
        mode = light.get("mode", 0)

        def colour_at(slot, phase=0.0):
            if base is not None:
                return base
            x, _, _ = self.keys[slot]
            return _hue((x - self.x0) / max(1, self.x1 - self.x0) + phase)

        if mode == 0 or style == "static":
            return {s: _scale(colour_at(s), level) for s in self.keys}
        if mode == 21:
            return {s: _scale(c, level) for s, c in custom.items()}
        out = {}
        width = max(1.0, self.x1 - self.x0)
        height = max(1.0, self.y1 - self.y0)
        if style == "breathing":
            v = (math.sin(t * speed * 2) + 1) / 2
            c = base if base is not None else _hue(t * speed * 0.05)
            return {s: _scale(c, level * v) for s in self.keys}
        if style == "spectrum":
            c = _hue(t * speed * 0.08)
            return {s: _scale(c, level) for s in self.keys}
        if style in ("wave_right", "wave_down", "wave_radial", "aurora"):
            for s, (x, y, _) in self.keys.items():
                if style == "wave_right":
                    pos = (x - self.x0) / width
                elif style == "wave_down":
                    pos = (y - self.y0) / height
                elif style == "wave_radial":
                    pos = math.hypot(x - self.cx, y - self.cy) / width
                else:
                    pos = 0.5 * math.sin(x / width * 3 + t * speed * 0.4) + 0.3 * math.sin(y / height * 2 - t * 0.3)
                out[s] = _scale(_hue(pos - sign * t * speed * 0.12), level)
            return out
        if style == "snake":
            n = len(self.order)
            head = int(t * speed * 12) % n
            for i, s in enumerate(self.order):
                d = (head - i) % n
                if d < 8:
                    out[s] = _scale(colour_at(s, t * 0.05), level * (1 - d / 8))
            return out
        if style in ("starlight", "rain"):
            rate = speed * (0.9 if style == "rain" else 0.5)
            if random.random() < rate:
                s = random.choice(list(self.keys))
                if style == "rain":
                    top = [k for k, v in self.keys.items() if v[2] == 0]
                    s = random.choice(top)
                self.drops[s] = t
            for s, t0 in list(self.drops.items()):
                age = t - t0
                if style == "rain":
                    x, _, row = self.keys[s]
                    cur = int(age * speed * 4)
                    if cur > 6:
                        del self.drops[s]
                        continue
                    for k, (kx, _, kr) in self.keys.items():
                        if abs(kx - x) < self.unit * 0.6 and 0 <= cur - kr < 2:
                            out[k] = _scale(colour_at(k), level * (1 - (cur - kr) * 0.5))
                else:
                    v = 1 - age / 1.5
                    if v <= 0:
                        del self.drops[s]
                        continue
                    out[s] = _scale(colour_at(s, t0 * 0.1), level * v)
            return out
        if style in REACTIVE:
            fade = 1.2 / speed
            self.presses = [(s, t0) for s, t0 in self.presses if t - t0 < fade * 3]
            for s0, t0 in self.presses:
                age = t - t0
                x0, y0, row0 = self.keys[s0]
                for s, (x, y, row) in self.keys.items():
                    if style == "reactive_key":
                        hit = s == s0
                        v = 1 - age / fade
                    elif style == "reactive_row":
                        hit = row == row0
                        v = 1 - age / fade
                    elif style == "reactive_column":
                        hit = abs(x - x0) < self.unit * 0.55
                        v = 1 - age / fade
                    elif style == "reactive_cross":
                        hit = row == row0 or abs(x - x0) < self.unit * 0.55
                        v = 1 - age / fade
                    elif style == "explode":
                        dist = math.hypot(x - x0, y - y0) / self.unit
                        hit = dist < 1.6
                        v = (1 - age / fade) * (1 - dist / 2)
                    else:  # ripple
                        dist = math.hypot(x - x0, y - y0) / self.unit
                        ring = age * speed * 6
                        hit = abs(dist - ring) < 0.8
                        v = 1 - ring / 14
                    if hit and v > 0:
                        c = _scale(colour_at(s, t0 * 0.1), level * v)
                        old = out.get(s)
                        if old is None or c.value() > old.value():
                            out[s] = c
            return out
        # effect number not matched yet: gentle generic cycle
        for s, (x, _, _) in self.keys.items():
            out[s] = _scale(_hue((x - self.x0) / width - t * 0.05), level * 0.6)
        return out
