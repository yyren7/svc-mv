"""Her figure cut out of each illustration, for a 2D figure standing in a 3D world: an 8-bit alpha the size of
the picture, 255 where she is, from anime-segmentation's ISNet (a first pass finds her, a second on her box draws
the edge, a guided filter pulls the edge onto the picture's own hair strands), plus a check picture.

    PYTHONPATH=/root/autodl-tmp/pv/pylib python scripts/figures.py <art dir> <name> [name ...]
    -> <art dir>/figures/<name>_figure.png     L, 255 = her
       <art dir>/figures/<name>_check.jpg      the picture over mid grey where she is not
    env: MODELS=/root/autodl-tmp/pv/models (anime-seg/isnetis.onnx, from scripts/onepic_setup.sh)
         PIC_SUFFIX=_00001_.png
         PLATES=<dir>   a picture painted on a plate (v5_<plate>_...) is looked for inside the plate's mannequin

Runs on the server (onnxruntime, OpenCV in pv/pylib). scripts/hybrid.py reads the figure for a cut-out print.
"""
import os
import sys

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

MODELS = os.environ.get("MODELS", "/root/autodl-tmp/pv/models")
SUFFIX = os.environ.get("PIC_SUFFIX", "_00001_.png")


def seg(img, s=1024):
    """ISNet on a picture letterboxed into s x s: the character's alpha, 0..1, at the picture's size."""
    sess = seg.sess = getattr(seg, "sess", None) or ort.InferenceSession(f"{MODELS}/anime-seg/isnetis.onnx")
    h0, w0 = img.shape[:2]
    h, w = (s, int(s * w0 / h0)) if h0 > w0 else (int(s * h0 / w0), s)
    ph, pw = (s - h) // 2, (s - w) // 2
    x = np.zeros((s, s, 3), np.float32)
    x[ph:ph + h, pw:pw + w] = cv2.resize(img.astype(np.float32) / 255, (w, h), interpolation=cv2.INTER_AREA)
    m = sess.run(None, {"img": x.transpose(2, 0, 1)[None]})[0][0, 0]
    return cv2.resize(m[ph:ph + h, pw:pw + w], (w0, h0), interpolation=cv2.INTER_CUBIC).clip(0, 1)


def guided(guide, src, r, eps):
    """He's guided filter: src's edges pulled onto guide's (alpha onto the picture's hair strands)."""
    box = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))  # noqa: E731
    mi, ms = box(guide), box(src)
    a = (box(guide * src) - mi * ms) / (box(guide * guide) - mi * mi + eps)
    b = ms - a * mi
    return (box(a) * guide + box(b)).clip(0, 1)


def figure(img, hint=None):
    """The character's alpha 0..1: whole picture, then her box, then the guided edge; only alpha within 12 px of
    where she is solid is kept (ISNet leaves a haze over glowing background beside her). `hint`: a box (x0, y0,
    x1, y1) where she is known to be (the mannequin of the picture's plate), used instead of the first pass, which
    misses a figure 4% of a wide picture."""
    H, W = img.shape[:2]
    pad = int(0.04 * W)
    if hint is not None:
        x0, y0, x1, y1 = hint
        hw, hh = (x1 - x0) * 0.25, (y1 - y0) * 0.12
        y0, y1, x0, x1 = (max(int(y0 - hh), 0), min(int(y1 + hh), H), max(int(x0 - hw), 0), min(int(x1 + hw), W))
    else:
        m = seg(img)
        ys, xs = np.nonzero(m > 0.5)
        if len(xs) == 0:
            return m
        y0, y1, x0, x1 = max(ys.min() - pad, 0), min(ys.max() + pad, H), max(xs.min() - pad, 0), min(xs.max() + pad, W)
    m = np.zeros((H, W), np.float32)
    m[y0:y1, x0:x1] = seg(img[y0:y1, x0:x1])
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    m = guided(gray, m.astype(np.float32), 4, 1e-4)
    core = cv2.dilate((m > 0.75).astype(np.uint8), np.ones((25, 25), np.uint8)).astype(np.float32)
    core = cv2.GaussianBlur(core, (0, 0), 6)
    return (m * core).clip(0, 1)


def plate_hint(name, size):
    """With PLATES=<dir> (cases/uraomote/scripts/v5_plates.py's renders) and a picture named v5_<plate>_..., the box
    of the plate's mannequin, scaled to the picture."""
    plates = os.environ.get("PLATES")
    if not plates or not name.startswith("v5_"):
        return None
    path = os.path.join(plates, name[3:].split("_")[0] + "_her.png")
    if not os.path.exists(path):
        return None
    her = np.asarray(Image.open(path).convert("L").resize(size, Image.NEAREST)) > 128
    ys, xs = np.nonzero(her)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else None


def main():
    art, names = sys.argv[1], sys.argv[2:]
    out = os.path.join(art, "figures")
    os.makedirs(out, exist_ok=True)
    for name in names:
        img = np.asarray(Image.open(os.path.join(art, name + SUFFIX)).convert("RGB"))
        a = figure(img, plate_hint(name, (img.shape[1], img.shape[0])))
        Image.fromarray((a * 255).astype(np.uint8), "L").save(os.path.join(out, f"{name}_figure.png"))
        grey = np.full_like(img, 110)
        chk = (img.astype(np.float32) * a[..., None] + grey * (1 - a[..., None])).astype(np.uint8)
        Image.fromarray(chk).save(os.path.join(out, f"{name}_check.jpg"), quality=86)
        ys, xs = np.nonzero(a > 0.5)
        box = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None
        print(f"{name}: {a.mean():.1%} of the picture, box {box}", flush=True)


if __name__ == "__main__":
    main()
