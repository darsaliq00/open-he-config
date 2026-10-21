"""Offline tests for the macro library and key recording (no keyboard needed)."""

import unittest
from unittest import mock

from config_app import macros


class ScanCodes(unittest.TestCase):
    def test_plain_and_extended(self):
        self.assertEqual(macros.usage_from_scan(0x11), 0x1A)      # W
        self.assertEqual(macros.usage_from_scan(0x1D), 0xE0)      # left Ctrl
        self.assertEqual(macros.usage_from_scan(0x11D), 0xE4)     # right Ctrl (extended)
        self.assertEqual(macros.usage_from_scan(0x148), 0x52)     # Up arrow (extended)
        self.assertIsNone(macros.usage_from_scan(0x7F))


class Recording(unittest.TestCase):
    def test_delays_are_time_until_next_step(self):
        page = macros.MacroPage.__new__(macros.MacroPage)
        page._rec_events, page._rec_last = [], 0.0
        page.status = mock.Mock()
        times = iter([1.000, 1.050, 1.300])
        with mock.patch.object(macros.time, "perf_counter", lambda: next(times)):
            page.record_key(0x11, True)
            page.record_key(0x11, False)
            page.record_key(0x1F, True)
        self.assertEqual(page._rec_events, [[0x1A, True, 50], [0x1A, False, 250], [0x16, True, 10]])


if __name__ == "__main__":
    unittest.main()
