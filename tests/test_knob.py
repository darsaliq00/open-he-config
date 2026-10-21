"""Offline checks of the knob remap table (the hook itself needs a real knob turn)."""

import sys
import unittest

if sys.platform == "win32":
    from app import knob


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class KnobMapping(unittest.TestCase):
    def test_default_is_not_hooked(self):
        r = knob.KnobRemapper()
        r.configure("volume", "mute")
        self.assertFalse(r.active)
        self.assertIsNone(r._thread)

    def test_actions(self):
        r = knob.KnobRemapper()
        r.turn, r.press = "scroll", "play"
        self.assertEqual(r._action_for(knob.VK_VOLUME_UP), ("wheel", 120))
        self.assertEqual(r._action_for(knob.VK_VOLUME_DOWN), ("wheel", -120))
        self.assertEqual(r._action_for(knob.VK_VOLUME_MUTE), ("keys", [0xB3]))
        self.assertIsNone(r._action_for(0x41))

    def test_hook_starts_and_stops(self):
        r = knob.KnobRemapper()
        r.configure("scroll", "mute")
        self.assertTrue(r._thread.is_alive())
        r.configure("volume", "mute")
        self.assertIsNone(r._thread)

    def test_unknown_names_fall_back(self):
        r = knob.KnobRemapper()
        r.configure("bogus", "bogus")
        self.assertEqual((r.turn, r.press), ("volume", "mute"))


if __name__ == "__main__":
    unittest.main()
