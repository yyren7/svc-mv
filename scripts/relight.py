"""Relight a cut-out picture in 2D for another light: darker and cooler all over, and a rim of a coloured light along
the side of her silhouette that faces the lamp. For a twin that must keep the exact silhouette of its source but
stand in the night (the 裏 that the water mirrors), when a repaint keeps the source's daylight. Writes a new
picture with the source's figure and maps beside it, so it drops in wherever the source did.

    python scripts/relight.py <art dir> <source> <new name> [dark] [rim hex] [rim strength] [dx,dy]
        dark 0.5: the picture's light kept;  rim #F0285A;  strength 1.6;  dx,dy 1,0.25: the lamp's side in the
        picture (x right, y down)
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

SUFFIX = os.environ.get("PIC_SUFFIX", "_00001_.png")
COOL = np.array([0.78, 0.84, 1.0], np.float32)


def lin(a):
    return np.power(a, 2.2)


def srgb(a):
    return np.power(np.clip(a, 0.0, 1.0), 1 / 2.2)


def main():
    art, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    dark = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
    hexs = sys.argv[5] if len(sys.argv) > 5 else "#F0285A"
    k = float(sys.argv[6]) if len(sys.argv) > 6 else 1.6
    dx, dy = (float(v) for v in (sys.argv[7] if len(sys.argv) > 7 else "1,0.25").split(","))
    img = np.asarray(Image.open(os.path.join(art, src + SUFFIX)).convert("RGB")).astype(np.float32) / 255
    fig = Image.open(os.path.join(art, "figures", src + "_figure.png")).convert("L")
    a = np.asarray(fig).astype(np.float32) / 255
    h, w = a.shape
    # the rim: where she is and the pixel a few px towards the lamp is not her
    n = max(2, int(0.006 * h))
    sx, sy = int(round(dx * n)), int(round(dy * n))
    shifted = np.roll(np.roll(a, -sy, axis=0), -sx, axis=1)
    rim = np.clip(a - shifted, 0, 1)
    rim = np.asarray(Image.fromarray((rim * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(n * 0.8))) / 255.0
    rim = (rim * a)[..., None]
    col = np.array([int(hexs[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    out = lin(img) * dark * COOL + lin(col) * rim * k
    res = srgb(out)
    res = res * a[..., None] + img * (1 - a[..., None])           # outside her: the picture as it was
    Image.fromarray((res * 255).astype(np.uint8)).save(os.path.join(art, dst + SUFFIX))
    shutil.copy(os.path.join(art, "figures", src + "_figure.png"), os.path.join(art, "figures", dst + "_figure.png"))
    for kind in ("depth", "flat", "parts"):
        p = os.path.join(art, "maps", f"{src}_{kind}.png")
        if os.path.exists(p):
            shutil.copy(p, os.path.join(art, "maps", f"{dst}_{kind}.png"))
    print(dst, "from", src, "dark", dark, "rim", hexs, k, (dx, dy))


if __name__ == "__main__":
    main()
