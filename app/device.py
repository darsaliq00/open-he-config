"""RK M75 HE raw Hall sensor reader.

The keyboard exposes a vendor HID interface (usage page 0xFFA0). Sending a
diagnostic request returns a 192-byte report (three 64-byte chunks) holding
16-bit little-endian ADC values for 63 matrix slots. The 126-slot matrix
(6 rows x 21 columns) is split into two pages: page 1 = slots 0..62,
page 2 = slots 63..125. ADC falls as the magnet nears the sensor.
"""

import time

import hid

VID = 0x1CA2
PID = 0x160A
USAGE_PAGE = 0xFFA0
USAGE = 1

SLOTS = 126
PAGE_SLOTS = 63
REPORT_LEN = 192
TYPE_ADC = 6


def _packet(data_type: int, page: int) -> list[int]:
    p = [0] * 64
    p[0], p[1], p[2] = 0x5C, 4, 0x12
    p[4], p[5], p[6], p[7] = data_type, page, 0xFF, 0xFF
    # checksum = 53 + header + length + command + last payload byte
    p[3] = (53 + p[0] + p[1] + p[2] + p[p[1] + 3]) & 0xFF
    return p


def find_path() -> bytes | None:
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE and d["usage"] == USAGE:
            return d["path"]
    return None


class Keyboard:
    def __init__(self):
        self.dev = None
        self.adc = [0] * SLOTS
        self._req = {1: [0] + _packet(TYPE_ADC, 1), 2: [0] + _packet(TYPE_ADC, 2)}
        self._misses = 0

    @property
    def connected(self) -> bool:
        return self.dev is not None

    def open(self) -> bool:
        path = find_path()
        if not path:
            return False
        try:
            dev = hid.device()
            dev.open_path(path)
            dev.set_nonblocking(True)
        except OSError:
            return False
        self.dev = dev
        self._misses = 0
        self._drain()
        return True

    def close(self):
        if not self.dev:
            return
        try:
            # data type 0 ends diagnostic streaming
            self.dev.write([0] + _packet(0, 1))
            self.dev.write([0] + _packet(0, 2))
            self.dev.close()
        except OSError:
            pass
        self.dev = None

    def _drain(self):
        try:
            while self.dev.read(64):
                pass
        except OSError:
            pass

    def _read_page(self, page: int, timeout: float = 0.015) -> bytearray | None:
        # Reports carry no page id, so stale input must be flushed before
        # each request or pages get mixed up.
        self._drain()
        self.dev.write(self._req[page])
        buf = bytearray()
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            chunk = self.dev.read(64)
            if not chunk:
                time.sleep(0.0005)
                continue
            if not buf and not (chunk[0] == 0x5C and chunk[2] == 0x92):
                continue
            buf.extend(chunk)
            if len(buf) >= REPORT_LEN:
                return buf if buf[5] == TYPE_ADC else None
        return None

    def poll(self, pages: tuple[int, ...] = (1, 2)) -> bool:
        """Refresh self.adc for the given pages. Returns False on disconnect."""
        if not self.dev:
            return False
        try:
            for page in pages:
                buf = self._read_page(page)
                if buf is None:
                    self._misses += 1
                    if self._misses > 20:
                        raise OSError("keyboard stopped answering")
                    continue
                self._misses = 0
                base = (page - 1) * PAGE_SLOTS
                for i in range(PAGE_SLOTS):
                    o = 6 + 2 * i
                    self.adc[base + i] = buf[o] | (buf[o + 1] << 8)
            return True
        except OSError:
            self.close()
            return False
