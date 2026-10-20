"""Read-only dump of the keyboard's stored settings: python -m config_app.dump

Sends only read requests; nothing is written to the keyboard.
"""

from app.kbconfig import read_settings
from app.layout import M75_KEYS as KEYS

from .link import Link


def main():
    link = Link()
    if not link.open():
        raise SystemExit("keyboard not found")
    try:
        s = read_settings(link.request)
    finally:
        link.close()
    print(f"{s['name']} · {s['firmware']} · protocol {s['protocol']} · global {s['global']}")
    for slot, k in sorted(s["keys"].items()):
        if slot in KEYS:
            print(f"{KEYS[slot]['label']:6} slot {slot:3}", {n: v for n, v in k.items() if n != "mode_raw"})


if __name__ == "__main__":
    main()
