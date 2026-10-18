"""Offline checks for app/protocol.py. Run: python -m unittest discover tests"""

import unittest

from app import protocol as p
from app.device import _packet


class PacketTests(unittest.TestCase):
    def test_diag_request_matches_known_adc_request(self):
        for page in (1, 2):
            self.assertEqual(p.req_diag(p.DIAG_ADC, page), bytes(_packet(6, page)))

    def test_checksum_uses_last_payload_byte(self):
        pkt = p.packet(p.CMD_KEY, [0, 44, p.LAYOUT_DB0, 0, 0])
        self.assertEqual(pkt[:4], bytes([0x5C, 5, 0x23, (53 + 0x5C + 5 + 0x23 + 0) & 0xFF]))
        self.assertEqual(len(pkt), 64)

    def test_payload_limit(self):
        with self.assertRaises(ValueError):
            p.packet(p.CMD_KRGB, [0] * 61)

    def test_reply_payload_checks_command(self):
        reply = bytes([0x5C, 5, 0x23 | 0x80, 0, 0, 44, 4, 0x2C, 0x01]).ljust(64, b"\0")
        self.assertEqual(p.reply_payload(reply, p.CMD_KEY)[:5], bytes([0, 44, 4, 0x2C, 0x01]))
        self.assertIsNone(p.reply_payload(reply, p.CMD_DB))


class WriteTests(unittest.TestCase):
    def test_set_key_fields(self):
        pkt = p.req_set_key_fields([(26, p.LAYOUT_DB0, 1050)])
        self.assertEqual(pkt[4:9], bytes([1, 26, 4, 0x1A, 0x04]))

    def test_lighting_round_trip_keeps_unknown_flags(self):
        pl = bytearray(64)
        pl[37], pl[38], pl[40], pl[41] = 0xC1, 3, 2, 5
        light = p.parse_lighting(bytes(pl))
        out = p.req_set_lighting(light)[4:]
        self.assertEqual(out[0], 1)
        self.assertEqual(p.parse_lighting(bytes([0]) + out[1:])["flags"], 0xC1)

    def test_key_colors_padding(self):
        pkt = p.req_set_key_colors([(26, 255, 0, 0)])
        self.assertEqual(pkt[4:9], bytes([1, 26, 255, 0, 0]))
        self.assertEqual(set(pkt[9:]), {0xFF})

    def test_socd(self):
        pkt = p.req_set_socd(4, 7, 0, delay=9)
        self.assertEqual(p.parse_socd(pkt[4:])["delay"], 9)
        self.assertEqual(p.parse_socd(pkt[4:])["key2"], 7)

    def test_keycode_names(self):
        self.assertEqual(p.keycode_name(0x1A), "W")
        self.assertEqual(p.keycode_name(p.CONSUMER | 0xE2), "Mute")
        self.assertEqual(p.keycode_name(p.KEY_NONE), "")
        self.assertEqual(p.keycode_name(p.FN_KEY), "Fn")
        self.assertEqual(p.combo_code(2, 0x1A), 0x621A)
        self.assertEqual(p.keycode_name(0x621A), "Shift+W")


class ParserTests(unittest.TestCase):
    def test_key_field(self):
        self.assertEqual(p.parse_key_field(bytes([0, 44, 4, 0x2C, 0x01])), (44, 4, 300))

    def test_sync_reply_from_keyboard(self):
        # real reply payload captured from the RK M75 HE
        pl = bytes.fromhex(
            "000a160226c00100103132333435363738393031323334353610417070205630"
            "2e302e313000"
        )
        info = p.parse_sync(pl)
        self.assertEqual(info.serial, "1234567890123456")
        self.assertEqual(info.app_version, "App V0.0.10")

    def test_mode(self):
        self.assertEqual(p.parse_mode(0x21), {"touch": "rt", "advanced": "DKS"})

    def test_global_travel(self):
        pl = bytes([0, 0, 0, 0xF4, 0x01, 0x32, 0, 0x64, 0])
        self.assertEqual(p.parse_global_travel(pl),
                         {"actuation_mm": 0.5, "press_dead_mm": 0.05, "release_dead_mm": 0.1})

    def test_key_map(self):
        pl = bytearray(64)
        pl[1], pl[2], pl[3] = 0, 41, 0
        pl[23], pl[24] = 1, 53
        self.assertEqual(p.parse_key_map(bytes(pl)), [(0, 0, 41), (1, 0, 53)])

    def test_diag_page(self):
        pl = bytes([0, 6]) + b"".join(v.to_bytes(2, "little") for v in range(63))
        self.assertEqual(p.parse_diag(pl), list(range(63)))

    def test_lighting_colours_are_bgr(self):
        pl = bytearray(64)
        pl[5:8] = bytes([0x30, 0x20, 0x10])
        pl[37], pl[38], pl[39] = 1, 4, 0
        light = p.parse_lighting(bytes(pl))
        self.assertEqual(light["colors"][0], "#102030")
        self.assertTrue(light["on"])
        self.assertEqual(light["type"], "static")


if __name__ == "__main__":
    unittest.main()
