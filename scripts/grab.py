"""Save chosen full-size frames of a frames folder as jpgs, to look at what a contact sheet's tiles hide (strands,
rain, relief grain):

    python scripts/grab.py <frames_dir> <out_dir> n [n ...]
"""
import os
import sys

from PIL import Image

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for n in sys.argv[3:]:
    im = Image.open(os.path.join(src, f"f_{int(n):05d}.png")).convert("RGB")
    im.save(os.path.join(out, f"f_{int(n):05d}.jpg"), quality=92)
    print(n, im.size)
