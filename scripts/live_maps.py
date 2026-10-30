"""What moves in a picture and how much (hybrid.live, docs/hybrid.md 让画活起来): from the parts map (R hair, G skin,
B clothes), the cut-out and the depth map of each picture:

    <art>/maps/<name>_live.png   R hair (0 at the roots, 1 at the tips), G head, B chest
    <art>/maps/<name>_plx.png    how far she stands before the picture's background (0 background, 1 nearest)
    <art>/maps/<name>_live.json  pivot (the neck, picture coordinates from the bottom left), her (her size in pixels),
                                 w, h

Works in any pose: the hair's roots are found by distance from her face, not from the top of the picture, so a lying
or leaping figure is weighted the same way as a standing one. Maps painted by hand are kept unless --force.

    python scripts/live_maps.py <art_dir> <name> [<name> ...] [--force]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter


def load(path, size):
    return np.asarray(Image.open(path).convert("RGB").resize(size, Image.BILINEAR), dtype=np.float32) / 255.0


def blur(a, radius):
    im = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def face_of(hair, skin, her):
    """The face: the skin that lies against the hair. (The arms and legs are skin too, but far from most of it.)"""
    near = blur(hair, 0.05 * max(hair.shape))
    w = skin * near * near * her
    if w.sum() < 1.0:
        w = hair * her
    if w.sum() < 1.0:
        w = her
    ys, xs = np.mgrid[0:hair.shape[0], 0:hair.shape[1]]
    cx, cy = (w * xs).sum() / w.sum(), (w * ys).sum() / w.sum()
    # the centroid again from the pixels round it, so a far arm does not pull it
    d = np.hypot(xs - cx, ys - cy)
    r0 = np.sqrt((w > 0.5 * w.max()).sum() / np.pi)
    w2 = w * (d < 2.5 * max(r0, 1.0))
    if w2.sum() >= 1.0:
        cx, cy = (w2 * xs).sum() / w2.sum(), (w2 * ys).sum() / w2.sum()
    r = max(np.sqrt((w2 > 0.5 * w2.max()).sum() / np.pi), 0.02 * max(hair.shape))
    return cx, cy, r, np.hypot(xs - cx, ys - cy)


def maps(art, name, force=False):
    d = os.path.join(art, "maps")
    out = os.path.join(d, f"{name}_live.png")
    if os.path.exists(out) and not force:
        print(name, "kept")
        return
    pic = Image.open(os.path.join(art, f"{name}_00001_.png"))
    w, h = pic.size
    parts = load(os.path.join(d, f"{name}_parts.png"), (w, h))
    depth = load(os.path.join(d, f"{name}_depth.png"), (w, h))[..., 0]
    fig = os.path.join(art, "figures", f"{name}_figure.png")
    her = load(fig, (w, h))[..., 0] if os.path.exists(fig) else np.clip(parts.sum(axis=2), 0, 1)
    hair, skin, cloth = parts[..., 0] * her, parts[..., 1] * her, parts[..., 2] * her
    cx, cy, r, dist = face_of(hair, skin, her)
    ys, xs = np.nonzero(her > 0.5)
    size = float(max(ys.max() - ys.min(), xs.max() - xs.min())) if len(ys) else float(h)

    # hair: nothing at the roots (over the face's own radius), all at the far tips, the face itself kept still
    far = np.percentile(dist[hair > 0.5], 96) if (hair > 0.5).any() else 2.0 * r
    ramp = np.clip((dist - 1.05 * r) / max(far - 1.05 * r, 1.0), 0.0, 1.0) ** 0.8
    soft = 0.006 * max(w, h)
    hw = blur(hair * ramp, soft) * (1.0 - blur(skin * (dist < 1.3 * r), soft))
    # head: the face and the hair round it, rigid, fading out towards the neck and the far hair
    head = np.clip(blur(np.maximum(skin, hair) * (dist < 1.7 * r), 0.25 * r) * 1.25, 0.0, 1.0)
    # chest: the clothes below the face, a broad soft hump, nothing at the picture's edges
    chest = blur(cloth * np.exp(-((dist - 3.2 * r) / (2.2 * r)) ** 2), 0.5 * r)
    if chest.max() > 0:
        chest = np.clip(chest / chest.max() * 1.3, 0.0, 1.0)
    # she against the background: a soft step at her edge (the background behind it stretches a little), nearer parts
    # by the depth a little more
    inner = depth[her > 0.5] if (her > 0.5).any() else depth
    lo, hi = np.percentile(inner, 5), np.percentile(inner, 95)
    near = np.clip((depth - lo) / max(hi - lo, 1e-3), 0.0, 1.0)
    plx = blur(her * (0.65 + 0.35 * blur(near, 0.012 * max(w, h))), 0.012 * max(w, h))

    Image.fromarray(np.uint8(np.dstack([hw, head, chest]) * 255)).save(out)
    Image.fromarray(np.uint8(plx * 255)).save(os.path.join(d, f"{name}_plx.png"))
    pivot = (float(cx / w), float(1.0 - min(cy + r, h - 1) / h))
    json.dump({"pivot": pivot, "face": (float(cx / w), float(1.0 - cy / h)), "her": size, "w": w, "h": h},
              open(os.path.join(d, f"{name}_live.json"), "w"))
    print(name, "face", round(cx / w, 3), round(1 - cy / h, 3), "r", round(r), "her", round(size), "of", w, h)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    for nm in args[1:]:
        maps(args[0], nm, "--force" in sys.argv)
