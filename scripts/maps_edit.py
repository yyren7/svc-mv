"""Hand-correct a picture's flat-plane map (scripts/maps.py's <name>_flat.png: R sky or window, G water, B mirror)
when CLIPSeg got a plane wrong, and remake the check picture:

    python scripts/maps_edit.py <art dir> <name> clear G                 # the picture has no water: drop the channel
    python scripts/maps_edit.py <art dir> <name> erase R x0 y0 x1 y1     # pixels of the picture (top-left origin)
    python scripts/maps_edit.py <art dir> <name> fill  R x0 y0 x1 y1

Several operations may follow each other on one line (`clear G erase R 0 0 260 460`). The maps are untracked
resources: run the same command locally and in the server checkout, and compare md5.
"""
import os
import sys

import numpy as np
from PIL import Image

SUFFIX = os.environ.get("PIC_SUFFIX", "_00001_.png")
CHAN = {"R": 0, "G": 1, "B": 2}


def check(img, flat):
    """The picture dimmed, with the flat map over it in its channel colours (as maps.py makes it)."""
    a = np.asarray(img.convert("RGB")).astype(np.float32) * 0.45
    mk = np.asarray(flat).astype(np.float32)
    return Image.fromarray(np.clip(a + mk * 0.55, 0, 255).astype(np.uint8))


def main():
    art, name, ops = sys.argv[1], sys.argv[2], sys.argv[3:]
    maps = os.path.join(art, "maps")
    path = os.path.join(maps, f"{name}_flat.png")
    a = np.array(Image.open(path).convert("RGB"))
    while ops:
        op, c = ops[0], CHAN[ops[1]]
        if op == "clear":
            a[..., c] = 0
            ops = ops[2:]
        elif op in ("erase", "fill"):
            x0, y0, x1, y1 = (int(v) for v in ops[2:6])
            a[y0:y1, x0:x1, c] = 0 if op == "erase" else 255
            ops = ops[6:]
        else:
            sys.exit(f"maps_edit.py: unknown operation {op!r}")
        print(name, op, "RGB"[c], f"-> sky {a[..., 0].mean() / 255:.0%}  water {a[..., 1].mean() / 255:.0%}  "
              f"mirror {a[..., 2].mean() / 255:.0%}")
    flat = Image.fromarray(a)
    flat.save(path)
    check(Image.open(os.path.join(art, name + SUFFIX)), flat).save(os.path.join(maps, f"{name}_check.jpg"), quality=88)


if __name__ == "__main__":
    main()
