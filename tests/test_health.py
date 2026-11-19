"""Offline checks of the key health findings and the trigger simulation."""

import unittest

from app import health as H

RT = {"mode": {"touch": "rt"}, "actuation": 0.6, "rt_press": 0.15, "rt_release": 0.15}
GLOBAL = {"mode": {"touch": "global"}}


class Rest(unittest.TestCase):
    def test_quiet_keys_pass(self):
        self.assertEqual(H.check_rest({1: [0.0, 0.01, 0.0]}, {1: GLOBAL}, 2.0), [])

    def test_offset_key_with_deep_actuation_is_a_warning(self):
        (f,) = H.check_rest({77: [0.92, 0.93, 0.94]}, {77: GLOBAL}, 2.0)
        self.assertEqual((f["level"], f["rest_mm"]), ("warn", 0.93))

    def test_offset_key_with_rapid_trigger_is_dangerous(self):
        (f,) = H.check_rest({77: [0.9] * 5}, {77: RT}, 2.0)
        self.assertEqual(f["level"], "danger")
        self.assertIn("rapid trigger", f["text"])


class Bottom(unittest.TestCase):
    def test_short_press(self):
        (f,) = H.check_bottom({1: 3.2, 2: 2.1}, {1, 2})
        self.assertEqual(f["slot"], 2)


class Simulate(unittest.TestCase):
    TRACE = [(i / 10, x) for i, x in enumerate([0, 0.3, 0.7, 1.5, 2.0, 1.8, 1.6, 1.7, 1.9, 1.0, 0.5, 0.2, 0.8])]

    def test_rapid_trigger_refires(self):
        self.assertEqual(H.simulate(self.TRACE, RT, 2.0),
                         [(0.2, True), (0.5, False), (0.8, True), (0.9, False), (1.2, True)])

    def test_global_actuation(self):
        self.assertEqual(H.simulate(self.TRACE, GLOBAL, 1.2), [(0.3, True), (0.9, False)])


if __name__ == "__main__":
    unittest.main()
