"""HID link to the keyboard's config interface, for the standalone config app.

Each process gets its own copy of every input report on Windows, so this can
run next to Analog Drive: replies are matched by command byte, and closing it
does not send the diagnostic stop that Analog Drive's own reader sends.
"""

import threading
import time

import hid

from app import protocol as p
from app.device import find_path


class Link:
    def __init__(self):
        self.dev = None
        self.lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self.dev is not None

    def open(self) -> bool:
        with self.lock:
            if self.dev:
                return True
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
            return True

    def close(self):
        with self.lock:
            if self.dev:
                try:
                    self.dev.close()
                except OSError:
                    pass
                self.dev = None

    def _drain(self):
        while self.dev.read(64):
            pass

    def _exchange(self, report: bytes, size: int, timeout: float) -> bytes | None:
        """Send a report, collect `size` bytes of the reply that starts with cmd | 0x80."""
        cmd = report[2] | 0x80
        self._drain()
        self.dev.write([0, *report])
        buf = bytearray()
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            chunk = self.dev.read(64)
            if not chunk:
                time.sleep(0.0005)
                continue
            if not buf and not (chunk[0] == p.HEADER and chunk[2] == cmd):
                continue
            buf.extend(chunk)
            if len(buf) >= size:
                return bytes(buf)
        return None

    def request(self, report: bytes, timeout: float = 0.2) -> bytes | None:
        """Send one config report and return the reply payload (byte 4 on), or None."""
        with self.lock:
            if not self.dev:
                return None
            try:
                reply = self._exchange(report, 64, timeout)
            except OSError:
                self.dev = None
                return None
        return reply[4:] if reply else None

    def diag(self, data_type: int, page: int, timeout: float = 0.05) -> list[int] | None:
        """One page (63 values) of a CMD_RM6X21 data type."""
        with self.lock:
            if not self.dev:
                return None
            try:
                reply = self._exchange(p.req_diag(data_type, page), 192, timeout)
            except OSError:
                self.dev = None
                return None
        if not reply or reply[5] != data_type:
            return None
        return p.parse_diag(reply[4:])
