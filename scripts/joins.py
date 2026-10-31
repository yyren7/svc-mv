"""The joins between shots, on the rendered frames (docs/hybrid.md 切点): a straight cut between two unrelated pictures reads
as a slide show, so each cut gets a transition from the frames either side of it, with no new render:

    soft   a dissolve
    rush   out through the lens: the old shot zooms up into the new one, which lands (radial blur)
    whip   the old shot flies off and the new one flies in the same way (directional blur)
    ink    the new shot soaks through the old one in blots, with a rose edge

    python scripts/joins.py <frames> <out> <table.py> <fps> [first_frame last_frame]

<table.py> defines TIMING (the song's timing json) and joins(at), which takes bars-to-seconds and returns (time, kind,
seconds a side[, direction]) for each cut; a whip's direction is 0 right, 1 up, 2 left, 3 down. <out> is made afresh:
frames no join touches are hard links, so the pass costs nothing where nothing happens.
"""
import importlib.util
import json
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image

ROSE = np.array([0.95, 0.20, 0.32], dtype=np.float32)
PAD = 0.75                                                 # each side, of the frame's size: mirrored room to move in


def padded(rgb):
    h, w = rgb.shape[:2]
    return Image.fromarray(np.pad(rgb, ((int(PAD * h),) * 2, (int(PAD * w),) * 2, (0, 0)), mode="reflect"))


def pose(pad, w, h, scale, dx, dy):
    """The frame `scale` times larger about its centre and moved by (dx, dy), from its mirrored copy."""
    a = 1.0 / scale
    c = int(PAD * w) + w / 2 - (w / 2 + dx) * a
    f = int(PAD * h) + h / 2 - (h / 2 + dy) * a
    return np.asarray(pad.transform((w, h), Image.AFFINE, (a, 0, c, 0, a, f), Image.BILINEAR), dtype=np.float32)


def smear(rgb, p0, p1, n=8):
    """The frame's travel from pose p0 to pose p1 (scale, dx, dy) within the shutter: the average of the poses between."""
    h, w = rgb.shape[:2]
    pad = padded(rgb)
    out = np.zeros_like(rgb, dtype=np.float32)
    for k in range(n):
        a = k / (n - 1)
        out += pose(pad, w, h, *[x + (y - x) * a for x, y in zip(p0, p1)])
    return out / n / 255.0


def blots(shape, seed):
    """A soft cloud of 0..1, flat in its values, so a threshold moving through it uncovers area evenly."""
    h, w = shape[:2]
    rnd = np.random.RandomState(seed)
    field = np.zeros((h, w), dtype=np.float32)
    for size, amp in ((5, 1.0), (11, 0.5), (23, 0.25), (47, 0.12)):
        small = Image.fromarray(rnd.rand(size, int(size * w / h) + 1).astype(np.float32))
        field += amp * np.asarray(small.resize((w, h), Image.BICUBIC))
    order = np.argsort(field, axis=None)
    flat = np.empty(field.size, dtype=np.float32)
    flat[order] = np.linspace(0.0, 1.0, field.size, dtype=np.float32)
    return flat.reshape(h, w)


def near_cut(x):
    """0 at the join's ends, 1 at the cut, gathering speed towards it."""
    return max(0.0, 1.0 - abs(x - 0.5) * 2) ** 2


def join_frame(kind, old, new, a, shutter, direction, field):
    """A frame of the join, `a` running 0..1 over it with the cut at 0.5. `old` and `new` are uint8 RGB: the frames here,
    or the shot's last or first frame held."""
    h, w = old.shape[:2]
    if kind == "soft":
        k = a * a * (3 - 2 * a)
        return (old * (1 - k) + new * k) / 255.0
    if kind == "ink":
        edge = 0.06
        k = np.clip((a * (1 + edge) - field) / edge, 0.0, 1.0)[..., None]
        out = (old * (1 - k) + new * k) / 255.0
        band = 4 * k * (1 - k)
        return out * (1 - 0.7 * band) + ROSE * 0.7 * band
    if kind == "rush":
        if a < 0.5:
            return smear(old, (1.0 + 0.9 * near_cut(a - shutter), 0.0, 0.0), (1.0 + 0.9 * near_cut(a), 0.0, 0.0))
        return smear(new, (1.0 - 0.3 * near_cut(a), 0.0, 0.0), (1.0 - 0.3 * near_cut(a + shutter), 0.0, 0.0))
    if kind == "whip":
        horizontal = direction in (0, 2)
        dist = 0.6 * (w if horizontal else h) * (1.0 if direction in (0, 3) else -1.0)
        if a < 0.5:
            o0, o1, im = dist * near_cut(a - shutter), dist * near_cut(a), old
        else:
            o0, o1, im = -dist * near_cut(a), -dist * near_cut(a + shutter), new
        p = (lambda o: (1.0, o, 0.0)) if horizontal else (lambda o: (1.0, 0.0, o))
        return smear(im, p(o0), p(o1))
    raise ValueError(kind)


def main():
    src, out, table, fps = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    names = sorted(f for f in os.listdir(src) if f.endswith(".png"))
    n = int(names[-1][2:7]) + 1
    lo = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    hi = int(sys.argv[6]) if len(sys.argv) > 6 else n - 1
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    spec = importlib.util.spec_from_file_location("join_table", table)
    tb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tb)
    down = json.load(open(tb.TIMING, encoding="utf-8"))["downbeats"]

    def at(bar):
        i = max(0, min(math.floor(bar), len(down) - 2))
        return max(0.0, down[i] + (bar - i) * (down[i + 1] - down[i]))

    rows = sorted((math.ceil(j[0] * fps - 1e-6), j[1], j[2], j[3] if len(j) > 3 else 0) for j in tb.joins(at))
    load = lambda f: np.asarray(Image.open(os.path.join(src, f"f_{f:05d}.png")).convert("RGB"))   # noqa: E731
    changed = 0
    for k, (c, kind, secs, direction) in enumerate(rows):
        gap0 = c - rows[k - 1][0] if k else n
        gap1 = rows[k + 1][0] - c if k + 1 < len(rows) else n
        side = max(1, min(round(secs * fps), gap0 // 2, gap1 // 2))
        if c - side < lo or c + side > hi + 1:
            continue
        last_old, first_new = load(c - 1), load(c)
        field = blots(last_old.shape, c) if kind == "ink" else None
        for f in range(c - side, c + side):
            a = (f - (c - side) + 0.5) / (2 * side)
            old, new = (load(f), first_new) if f < c else (last_old, load(f))
            im = join_frame(kind, old, new, a, 0.8 / (2 * side), direction, field)
            Image.fromarray(np.uint8(np.clip(im, 0.0, 1.0) * 255 + 0.5)).save(os.path.join(out, f"f_{f:05d}.png"))
            changed += 1
    for name in names:
        if lo <= int(name[2:7]) <= hi and not os.path.exists(os.path.join(out, name)):
            os.link(os.path.join(src, name), os.path.join(out, name))
    print("joins:", len(rows), "cuts,", changed, "frames changed")


if __name__ == "__main__":
    main()
