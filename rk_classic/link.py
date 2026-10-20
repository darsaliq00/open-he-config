"""HID link to RK's non-HE keyboards (VID 0x258A). Settings go out as feature reports."""

import sys
import threading

import hid

from . import protocol as p
from .rkdata import VID

# The config interface is the collection with usage page 0x01, usage 0x80 (System Control).
# On Windows each collection has its own path ending in "&colNN": collection 5 on most boards,
# 6 on PID 0x0057.
COLLECTION = {0x0057: 6}
DEFAULT_COLLECTION = 5


def _is_config(d: dict) -> bool:
    if sys.platform == "win32":
        path = d["path"].decode(errors="ignore").lower()
        col = COLLECTION.get(d["product_id"], DEFAULT_COLLECTION)
        return f"&col{col:02d}" in path
    return d["usage_page"] == 0x0001 and d["usage"] == 0x0080


def connected() -> list[tuple[bytes, int]]:
    """(path, PID) of every connected RK non-HE keyboard's config interface."""
    seen, out = set(), []
    for d in hid.enumerate(VID, 0):
        if _is_config(d) and d["product_id"] not in seen:
            seen.add(d["product_id"])
            out.append((d["path"], d["product_id"]))
    return out


class SendError(Exception):
    pass


class ClassicLink:
    def __init__(self):
        self.lock = threading.Lock()

    def send(self, path: bytes, reports: list[bytes]):
        """Send the reports in order over a fresh handle. Raises SendError."""
        with self.lock:
            dev = hid.device()
            try:
                dev.open_path(path)
            except OSError as e:
                raise SendError(f"cannot open the keyboard ({e}); close RK's software and try again") from e
            try:
                for r in reports:
                    if len(r) != p.REPORT_LEN:
                        raise SendError("bad report length")
                    if dev.send_feature_report(list(r)) != p.REPORT_LEN:
                        raise SendError("the keyboard did not take a report")
            except OSError as e:
                raise SendError(str(e)) from e
            finally:
                dev.close()
