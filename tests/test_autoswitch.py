"""Offline checks of the auto-switch rules."""

import unittest

from app import autoswitch as A


class Chooser(unittest.TestCase):
    def setUp(self):
        self.c = A.Chooser([{"exe": "TslGame.exe", "config": 2}, {"exe": "VALORANT.exe", "config": 3}], 1)

    def feed(self, exe, n=A.STABLE_TICKS, own=False):
        out = None
        for _ in range(n):
            out = self.c.tick(exe, own) or out
        return out

    def test_switches_after_game_stays_in_front(self):
        self.assertIsNone(self.c.tick("TslGame.exe"))            # just came to the front
        self.assertEqual(self.feed("TslGame.exe", 1), 2)

    def test_case_and_default(self):
        self.assertEqual(self.feed("tslgame.EXE"), 2)
        self.assertEqual(self.feed("chrome.exe"), 1)             # no rule: the default config

    def test_no_repeat_switch(self):
        self.assertEqual(self.feed("TslGame.exe"), 2)
        self.assertIsNone(self.feed("TslGame.exe", 5))

    def test_alt_tab_flicker_is_ignored(self):
        self.assertEqual(self.feed("TslGame.exe"), 2)
        self.assertIsNone(self.c.tick("Discord.exe"))           # one glance at another window
        self.assertIsNone(self.c.tick("TslGame.exe"))
        self.assertIsNone(self.feed("TslGame.exe"))

    def test_own_window_keeps_config(self):
        self.assertEqual(self.feed("TslGame.exe"), 2)
        self.assertIsNone(self.feed("OpenHEConfig.exe", own=True))

    def test_leave_as_is(self):
        c = A.Chooser([{"exe": "x.exe", "config": 4}], 0)
        self.assertIsNone(c.target("chrome.exe"))


if __name__ == "__main__":
    unittest.main()
