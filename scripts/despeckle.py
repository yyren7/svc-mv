"""Paint out the small vivid-green specks Qwen leaves at the top of an inpainted region (round after round of the
v5 pictures had one or two by her head): pixels far greener than they are red or blue, in blobs no bigger than
`MAX_BLOB` pixels, filled from their surroundings (OpenCV's Telea inpainting). A palette with real greens in it
(foliage) must not be run through this.

    PYTHONPATH=/root/autodl-tmp/pv/pylib python scripts/despeckle.py <art dir> <name> [name ...]
    -> <art dir>/<name>_00001_.png rewritten (the untouched picture stays in ComfyUI/output); prints the blobs.
"""
import os
import sys

import cv2
import numpy as np

SUFFIX = os.environ.get("PIC_SUFFIX", "_00001_.png")
MAX_BLOB = int(os.environ.get("MAX_BLOB", 900))


def specks(img):
    """A mask of the green specks in a BGR picture, and their boxes."""
    b, g, r = (img[..., k].astype(np.int16) for k in range(3))
    green = ((g - np.maximum(r, b) > 25) & (g > 100)) | ((g - b > 80) & (g > r) & (g > 120))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(green.astype(np.uint8), 8)
    mask = np.zeros(green.shape, np.uint8)
    boxes = []
    for k in range(1, n):
        x, y, w, h, area = stats[k]
        if area <= MAX_BLOB:
            mask[lab == k] = 255
            boxes.append((int(x), int(y), int(w), int(h), int(area)))
    return cv2.dilate(mask, np.ones((7, 7), np.uint8)), boxes


def main():
    art = sys.argv[1]
    for name in sys.argv[2:]:
        path = os.path.join(art, name + SUFFIX)
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        mask, boxes = specks(img)
        if boxes:
            cv2.imwrite(path, cv2.inpaint(img, mask, 6, cv2.INPAINT_TELEA))
        print(name, len(boxes), "specks", boxes[:6])


if __name__ == "__main__":
    main()
