"""Draws the app icon: a magnetic (Hall effect) switch seen from the side through a clear housing:
cross stem, spring, magnet at the foot of the stem and the Hall sensor on the PCB below, with
"RK" lettered on the housing. Plain text in Segoe UI, not RK's logo artwork.
Run once; writes assets/icon.png and assets/icon.ico."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BIG = 1024           # drawn large, then scaled down for smooth edges
S = BIG / 256        # scale from a 256 px design grid
FONT = Path("C:/Windows/Fonts/segoeuib.ttf")


def box(*xy):
    return tuple(round(v * S) for v in xy)


def r(v):
    return round(v * S)


def draw() -> Image.Image:
    jade, jade_dark = (64, 214, 200, 255), (34, 160, 150, 255)
    base = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    # PCB with the Hall sensor under the switch
    d.rounded_rectangle(box(6, 222, 250, 246), radius=r(5), fill=(22, 101, 52, 255))
    d.rectangle(box(106, 208, 150, 224), fill=(24, 24, 28, 255))
    for x in (110, 124, 138):
        d.rectangle(box(x, 222, x + 8, 226), fill=(200, 200, 205, 255))
    # stem: cross on top, long body inside the housing
    d.rounded_rectangle(box(118, 6, 138, 60), radius=r(4), fill=jade)
    d.rounded_rectangle(box(98, 18, 158, 36), radius=r(4), fill=jade)
    d.rounded_rectangle(box(104, 56, 152, 76), radius=r(4), fill=jade_dark)
    d.rounded_rectangle(box(114, 72, 142, 172), radius=r(5), fill=jade_dark)
    # spring coiled around the stem
    steel = (205, 212, 222, 255)
    coils = 7
    for i in range(coils):
        y0 = 88 + i * 12
        d.line([box(92, y0)[:2], box(164, y0 + 6)[:2]], fill=steel, width=r(4))
        if i < coils - 1:
            d.line([box(164, y0 + 6)[:2], box(92, y0 + 12)[:2]], fill=(150, 160, 175, 255), width=r(3))
    # magnet at the foot of the stem (red N, blue S)
    d.rectangle(box(110, 170, 146, 182), fill=(229, 72, 77, 255))
    d.rectangle(box(110, 182, 146, 194), fill=(59, 130, 246, 255))
    # field lines from magnet to sensor
    field = (250, 204, 21, 255)
    d.arc(box(86, 176, 128, 220), start=90, end=270, fill=field, width=r(3))
    d.arc(box(128, 176, 170, 220), start=270, end=90, fill=field, width=r(3))

    # transparent housing over the internals
    shell = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shell)
    top = [box(44, 72)[:2], box(212, 72)[:2], box(232, 156)[:2], box(24, 156)[:2]]
    sd.polygon(top, fill=(96, 165, 250, 95), outline=(37, 99, 235, 255), width=r(3))
    sd.rounded_rectangle(box(18, 154, 238, 206), radius=r(8), fill=(96, 165, 250, 110),
                         outline=(37, 99, 235, 255), width=r(3))
    sd.rounded_rectangle(box(6, 166, 24, 192), radius=r(4), fill=(37, 99, 235, 200))
    sd.rounded_rectangle(box(232, 166, 250, 192), radius=r(4), fill=(37, 99, 235, 200))
    sd.line([box(52, 78)[:2], box(36, 144)[:2]], fill=(255, 255, 255, 140), width=r(4))   # glare
    font = ImageFont.truetype(str(FONT), r(40))
    text = "OHE"
    w = sd.textlength(text, font=font)
    sd.text((BIG / 2 - w / 2, r(96)), text, font=font, fill=(255, 255, 255, 235),
            stroke_width=r(3), stroke_fill=(30, 58, 138, 255))
    return Image.alpha_composite(base, shell)


def main():
    out = Path(__file__).resolve().parent.parent / "assets"
    icon = draw().resize((256, 256), Image.LANCZOS)
    icon.save(out / "icon.png")
    icon.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(out / "icon.png")


if __name__ == "__main__":
    main()
