#!/usr/bin/env python3
"""
Turn a picture into ASCII art for the hero card (data/portrait.txt).

Put a photo of yourself at .github/assets/portrait.jpg (or .png), ideally a
head-and-shoulders shot on a plain, light background, then run:

    pip install pillow
    python scripts/make_ascii.py

Without a portrait it falls back to the drone illustration from the old banner.
"""
import os
import sys

from PIL import Image, ImageOps

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, ".github", "assets")
OUT = os.path.join(ROOT, "data", "portrait.txt")

COLS = 110          # characters per row
ASPECT = 0.55       # monospace glyphs are taller than wide
RAMP = " .'`^,:;-~=+*cxoO0#%@"  # light -> dense


def source():
    for name in ("portrait.jpg", "portrait.jpeg", "portrait.png"):
        p = os.path.join(ASSETS, name)
        if os.path.exists(p):
            return Image.open(p), True
    img = Image.open(os.path.join(ASSETS, "hero-pasta-ai.png"))
    w, h = img.size
    return img.crop((int(w * 0.5), int(h * 0.12), int(w * 0.985), int(h * 0.88))), False


def main():
    img, is_photo = source()
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img, cutoff=2)
    if is_photo:
        img = ImageOps.equalize(img)
    w, h = img.size
    rows = max(1, int(h / w * COLS * ASPECT))
    img = img.resize((COLS, rows), Image.LANCZOS)
    px = img.load()
    lines = []
    for y in range(rows):
        row = ""
        for x in range(COLS):
            v = px[x, y] / 255  # 0 dark .. 1 light
            row += RAMP[min(len(RAMP) - 1, int((1 - v) * len(RAMP)))]
        lines.append(row.rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote data/portrait.txt ({len(lines)} rows, from {'photo' if is_photo else 'illustration'})")


if __name__ == "__main__":
    sys.exit(main())
