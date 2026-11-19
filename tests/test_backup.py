"""Offline checks of backup planning (no keyboard needed)."""

import copy
import unittest

from app import backup as B
from app import protocol as p


def settings():
    keys = {}
    for slot, kid in ((44, 0x1A), (64, 0x04), (66, 0x07)):
        keys[slot] = {"id": kid, "mode_raw": 0x20, "mode": p.parse_mode(0x20), "actuation": 0.6, "rt_press": 0.15,
                      "rt_release": 0.15, "dead_press": 0.0, "dead_release": 0.0, "fn0": kid, "fn1": 1,
                      "fn2": 1, "fn3": 1, "axis": 0, "color": (255, 0, 0)}
    return {"name": "RK M75 HE", "firmware": "App V0.0.10", "protocol": "1.0.7",
            "global": {"actuation_mm": 2.0, "press_dead_mm": 0.0, "release_dead_mm": 0.0},
            "lighting": {"on": True, "mode": 21, "brightness": 4, "colors": ["#ff0000"] * 7},
            "system": {"config": 0}, "keys": keys}


def snapshot(s):
    return {"global": dict(s["global"]), "lighting": dict(s["lighting"]),
            "keys": {str(k["id"]): {"mode_raw": k["mode_raw"], "axis": k["axis"], "color": list(k["color"]),
                                    **{n: k[n] for n in ("actuation", "rt_press", "rt_release", "dead_press",
                                                         "dead_release", "fn0", "fn1", "fn2", "fn3")}}
                     for k in s["keys"].values()}}


class Planning(unittest.TestCase):
    def test_same_means_nothing(self):
        s = settings()
        self.assertTrue(B.summary(B.plan(snapshot(s), s)).startswith("nothing"))

    def test_only_changes_are_written(self):
        s = settings()
        snap = snapshot(s)
        snap["keys"]["26"]["actuation"] = 1.0
        snap["keys"]["26"]["mode_raw"] = 0x10
        snap["keys"]["4"]["color"] = [0, 0, 255]
        snap["global"]["actuation_mm"] = 1.5
        pl = B.plan(snap, s)
        self.assertTrue(pl["global"])
        self.assertEqual(pl["fields"], [(0x1A, p.LAYOUT_DB0, 1000)])
        self.assertEqual(pl["modes"], [(0x1A, 0x10)])
        self.assertEqual(pl["colors"], {0x04: (0, 0, 255)})

    def test_macro_without_steps_is_left_alone(self):
        s = settings()
        snap = snapshot(s)
        snap["keys"]["7"]["mode_raw"] = 0x20 | p.ADV_MACRO
        snap["keys"]["7"]["advanced"] = {"id": 0, "length": 2, "mode": 0, "repeat": 1, "interval_ms": 10}
        pl = B.plan(snap, s)
        self.assertEqual(pl["no_macro_steps"], [0x07])
        self.assertEqual(pl["modes"], [])

    def test_keys_missing_on_this_board(self):
        s = settings()
        snap = snapshot(s)
        snap["keys"]["99"] = copy.deepcopy(snap["keys"]["26"])
        self.assertEqual(B.plan(snap, s)["missing"], [99])

    def test_file_check(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.json"
            f.write_text(json.dumps({"app": "something else"}))
            with self.assertRaises(ValueError):
                B.load(f)
            B.save(f, B.header(settings(), {"1": snapshot(settings())}))
            self.assertIn("1", B.load(f)["configs"])


if __name__ == "__main__":
    unittest.main()
