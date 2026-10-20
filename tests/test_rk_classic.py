"""Offline tests for the non-HE RK backend (rk_classic).

Board-data tests run only when RK_SOFTWARE_DIR points to RK Keyboard Software's folder
(installed, or unpacked from the setup with innoextract); the folder holds Cfg.ini and Dev/.
"""

import os
import unittest
from pathlib import Path

from rk_classic import protocol as p
from rk_classic.rkdata import RKSoftware, find_install, vk_code


class Protocol(unittest.TestCase):
    def test_lighting_report(self):
        r = p.lighting(mode=17, brightness=5, speed=3, colour=(10, 20, 30), random_colour=True, sleep=2)
        self.assertEqual(len(r), 65)
        self.assertEqual(list(r[:14]), [0x0A, 1, 1, 0x02, 0x29, 17, 0, 3, 5, 10, 20, 30, 1, 2])
        self.assertFalse(any(r[14:]))

    def test_lighting_channel_order(self):
        r = p.lighting(1, 5, 3, (10, 20, 30), False, 5, order=(1, 0, 2))
        self.assertEqual(list(r[9:12]), [20, 10, 30])

    def test_lighting_ranges(self):
        with self.assertRaises(ValueError):
            p.lighting(1, 6, 3, (0, 0, 0), False, 5)
        with self.assertRaises(ValueError):
            p.lighting(1, 5, 0, (0, 0, 0), False, 5)

    def test_key_colours(self):
        rs = p.key_colours({0: (1, 2, 3), 21: (4, 5, 6)})
        self.assertEqual(len(rs), 7)
        self.assertTrue(all(len(r) == 65 and r[0] == 0x0A and r[1] == 7 for r in rs))
        self.assertEqual([r[2] for r in rs], list(range(1, 8)))
        self.assertEqual(list(rs[0][3:9]), [0x03, 0x7E, 0x01, 1, 2, 3])
        # index 21 starts at data byte 63: first report carries 59 data bytes, the next 62
        self.assertEqual(list(rs[1][3 + 4:3 + 7]), [4, 5, 6])

    def test_key_map(self):
        rs = p.key_map({0: p.key(0x29), 1: p.consumer(0xE9), 15: p.key(0x04, 0x01)})
        self.assertEqual(len(rs), 9)
        self.assertEqual(list(rs[0][3:13]), [0x01, 0xF8, 0, 0, 0x29, 0, 0x01, 0, 0, 0xE9])
        # index 15 starts at data byte 60: first report carries 60 data bytes
        self.assertEqual(list(rs[1][3:7]), [0, 0x01, 0x04, 0])

    def test_codes(self):
        self.assertEqual(p.key(0x1A), 0x1A00)
        self.assertEqual(p.key(0, 0x01), 0x010000)
        self.assertEqual(p.consumer(0xCD), 0x010000CD)
        self.assertEqual(p.split(p.FN), ("fn", 0, 0))
        self.assertEqual(p.split(p.key(0x06, 0x01)), ("key", 0x06, 0x01))

    def test_vk_codes(self):
        self.assertEqual(vk_code(0x1B), p.key(0x29))     # Esc
        self.assertEqual(vk_code(0x41), p.key(0x04))     # A
        self.assertEqual(vk_code(0x30), p.key(0x27))     # 0
        self.assertEqual(vk_code(0xA2), p.key(0, 0x01))  # left Ctrl
        self.assertEqual(vk_code(0xFA), p.FN)
        self.assertEqual(vk_code(0x8D), p.consumer(0xE9))
        self.assertIsNone(vk_code(0x07))


RK_DIR = os.environ.get("RK_SOFTWARE_DIR")


@unittest.skipUnless(RK_DIR, "set RK_SOFTWARE_DIR to RK Keyboard Software's folder")
class BoardData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rk = find_install([Path(RK_DIR)])

    def test_found(self):
        self.assertIsInstance(self.rk, RKSoftware)
        self.assertEqual(self.rk.vid, 0x258A)
        self.assertGreater(len(self.rk.boards()), 100)

    def test_every_board_parses(self):
        for pid in self.rk.boards():
            b = self.rk.board(pid)
            self.assertTrue(b.keys, f"{pid:04X} has no keys")
            idx = [k.index for k in b.keys]
            self.assertLess(max(idx), p.COLOUR_SLOTS, f"{pid:04X}")

    def test_known_board(self):
        b = self.rk.board(0x0102)
        esc = next(k for k in b.keys if k.name == "Esc")
        self.assertEqual((esc.index, esc.rect, esc.default), (0, (37, 49, 69, 85), p.key(0x29)))
        self.assertEqual(b.rgb_order, (1, 0, 2))
        self.assertTrue(b.can_remap)

    def test_mode_names(self):
        rgb = self.rk.mode_names(rgb=True)
        self.assertEqual(rgb[17], "Steady")
        self.assertIn("custom", rgb[14].lower())
        self.assertEqual(self.rk.mode_names(rgb=False)[1], "Steady")


if __name__ == "__main__":
    unittest.main()
