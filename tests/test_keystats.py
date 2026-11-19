"""Offline checks of the key press counter (no hook needed)."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

from app.keystats import KeyCounter


class Counting(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "key_stats.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_auto_repeat_counts_once(self):
        c = KeyCounter(self.path)
        for _ in range(5):
            c.count(0x11, True)          # W held: Windows repeats key-down
        c.count(0x11, False)
        c.count(0x11, True)
        self.assertEqual(c.counts[0x11], 2)

    def test_saved_and_loaded(self):
        c = KeyCounter(self.path)
        c.count(0x1E, True)
        c.save()
        self.assertEqual(KeyCounter(self.path).counts, {0x1E: 1})

    def test_reset(self):
        c = KeyCounter(self.path)
        c.count(0x1E, True)
        c.reset()
        self.assertEqual(KeyCounter(self.path).counts, {})

    @unittest.skipUnless(sys.platform == "win32", "Windows hook")
    def test_hook_starts_and_stops(self):
        c = KeyCounter(self.path)
        c.start()
        time.sleep(0.2)
        self.assertTrue(c.running)
        c.stop()
        self.assertFalse(c.running)


if __name__ == "__main__":
    unittest.main()
