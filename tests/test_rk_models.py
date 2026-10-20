"""Offline checks for multi-model RK support: write detection and key map layouts."""

import unittest

from app import keycodes, layout
from app import protocol as p
from config_app.link import is_write


class WriteDetectionTests(unittest.TestCase):
    def test_reads_are_not_writes(self):
        for report in (p.req_sync(), p.req_order(p.ORDER_TOP_DEAD_SWITCH), p.req_order(p.ORDER_POLLING),
                       p.req_order(p.ORDER_CONFIG), p.req_global_travel(), p.req_lighting(),
                       p.req_key_fields([(0x1A, p.LAYOUT_DB0)]), p.req_key_color(0x1A), p.req_diag(2, 1),
                       p.req_key_map(0, 1), p.req_socd(4), p.req_mpt(4), p.req_macro_mode(4)):
            self.assertFalse(is_write(report), report[:8].hex())

    def test_writes_are_writes(self):
        for report in (p.req_set_key_fields([(0x1A, p.LAYOUT_DB0, 1000)]), p.req_set_order(p.ORDER_POLLING, 3),
                       p.req_set_order(p.ORDER_CONFIG, 1), p.req_set_order(p.ORDER_TOP_DEAD_SWITCH, 0),
                       p.req_order(p.ORDER_FACTORY_RESET), p.req_order(p.ORDER_START_CALIBRATION),
                       p.req_set_global_travel(2, 0, 0), p.req_set_key_colors([(4, 1, 2, 3)]),
                       p.req_save_key_colors(), p.req_set_socd(4, 7, 0), p.req_set_mt(4, 5, 6, 200)):
            self.assertTrue(is_write(report), report[:8].hex())


class KeyMapLayoutTests(unittest.TestCase):
    def test_keycodes(self):
        self.assertEqual(keycodes.describe(0x1A), ("W", 0x11, 1))
        self.assertEqual(keycodes.describe(0x2C)[2], 6.25)
        self.assertEqual(keycodes.describe(0x01)[0], "Fn")

    def test_m75_layout_matches_its_key_map(self):
        # the M75 HE's top-right key is Del at slot 13 (as the keyboard reports), there is no slot 14
        self.assertEqual(layout.M75_KEYS[13]["label"], "Del")
        self.assertNotIn(14, layout.M75_KEYS)


if __name__ == "__main__":
    unittest.main()
