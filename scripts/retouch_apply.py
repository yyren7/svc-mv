"""Put a retouched picture (scripts/retouch.py's output) into a one-picture PV's prep folder: color.png becomes the
retouched picture, and the character layer takes the changed pixels where it is solid (its alpha stays).
    python retouch_apply.py <prep dir> <retouched picture>
The first run keeps the previous picture as color_before_retouch.png. Run `onepic_prep.py rig` again afterwards (the
rig's weights read the layer's colours), and update rig.json's rigid lines if a prop moved."""
import os
import sys

import cv2
import numpy as np


def main():
    prep, src = sys.argv[1], sys.argv[2]
    new = cv2.imread(src)
    cur = os.path.join(prep, "color.png")
    keep = os.path.join(prep, "color_before_retouch.png")
    if not os.path.exists(keep):
        os.rename(cur, keep)
    old = cv2.imread(keep)                     # every retouch so far, against the picture before any of them
    assert new.shape == old.shape, (new.shape, old.shape)
    cv2.imwrite(cur, new)
    changed = (np.abs(new.astype(np.int16) - old.astype(np.int16)).max(2) > 8).astype(np.uint8)
    changed = cv2.dilate(changed, np.ones((9, 9), np.uint8))
    m = cv2.GaussianBlur(changed.astype(np.float32), (0, 0), 2)
    ys, xs = np.nonzero(changed)
    H, W = changed.shape
    print(f"changed: u {xs.min() / W:.3f}-{xs.max() / W:.3f}, v {ys.min() / H:.3f}-{ys.max() / H:.3f}", flush=True)
    for name in ("layer_char.png", "layer_char_solid.png"):
        path = os.path.join(prep, name)
        if not os.path.exists(path):
            continue
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        a = img[..., 3].astype(np.float32) / 255
        src_, m_ = new, m
        if img.shape[:2] != new.shape[:2]:         # the layer was upscaled (2x-AnimeSharp): bring the change to its size
            size = (img.shape[1], img.shape[0])
            src_ = cv2.resize(new, size, interpolation=cv2.INTER_LANCZOS4)
            m_ = cv2.resize(m, size, interpolation=cv2.INTER_LINEAR)
        k = (m_ * (a > 0.98))[..., None]           # loose hair over the sky keeps its old colour and alpha
        img[..., :3] = (img[..., :3] * (1 - k) + src_ * k).round().astype(np.uint8)
        cv2.imwrite(path, img)
        print(f"{name}: {(k > 0.5).mean() * 100:.2f}% of the layer replaced", flush=True)


if __name__ == "__main__":
    main()
