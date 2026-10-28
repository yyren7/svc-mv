"""The flat map of a picture painted over a plate of the world (cases/uraomote/scripts/v5_plates.py): the plate's
own plane mask (R the sky, G the water, rendered flat from the same camera) with her figure (scripts/figures.py)
taken out, so hybrid.world_mat cuts the picture through to the real sky and water everywhere but her, exactly
where the world has them (CLIPSeg guessed; this is the geometry), plus a check picture.

    python scripts/plate_maps.py <plates dir> <art dir> <plate>=<picture> [...]
    -> <art dir>/maps/<picture>_flat.png, <picture>_check.jpg

The picture is the plate's size (it was painted over it). The depth and parts maps still come from
scripts/maps.py; run that first, since it writes a flat map of its own that this one replaces.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

SUFFIX = os.environ.get("PIC_SUFFIX", "_00001_.png")


def main():
    plates, art = sys.argv[1], sys.argv[2]
    out = os.path.join(art, "maps")
    os.makedirs(out, exist_ok=True)
    for item in sys.argv[3:]:
        plate, pic = item.split("=")
        img = Image.open(os.path.join(art, pic + SUFFIX)).convert("RGB")
        mask = Image.open(os.path.join(plates, f"{plate}_mask.png")).convert("RGB")
        if mask.size != img.size:
            mask = mask.resize(img.size, Image.NEAREST)
        m = np.asarray(mask) > 128
        sky, water = m[..., 0] & ~m[..., 1], m[..., 1] & ~m[..., 0]
        fig_path = os.path.join(art, "figures", f"{pic}_figure.png")
        if os.path.exists(fig_path):
            fig = Image.open(fig_path).convert("L").filter(ImageFilter.MaxFilter(5))     # her edge kept paper
            her = np.asarray(fig.resize(img.size, Image.BILINEAR)) > 100
            sky, water = sky & ~her, water & ~her
        else:
            print(pic, "no figure yet: the planes cover her too")
        flat = np.zeros(m.shape, np.uint8)
        flat[..., 0], flat[..., 1] = sky * 255, water * 255
        Image.fromarray(flat).save(os.path.join(out, f"{pic}_flat.png"))
        a = np.asarray(img).astype(np.float32)
        check = (a * 0.55 + flat.astype(np.float32) * 0.45).clip(0, 255).astype(np.uint8)
        Image.fromarray(check).save(os.path.join(out, f"{pic}_check.jpg"), quality=88)
        print(pic, f"sky {sky.mean() * 100:.0f}%  water {water.mean() * 100:.0f}%")


if __name__ == "__main__":
    main()
