"""Redraw one part of a finished picture (a hand, a prop) with Qwen-Image-2.1's masked img2img; the rest stays
pixel for pixel. Runs on AutoDL with ComfyUI up, through comfy_batch.sh:
    CLIENT="env PYTHONPATH=/root/autodl-tmp/pv/pylib /root/autodl-tmp/ComfyUI/venv/bin/python /root/autodl-tmp/svc-mv/scripts/retouch.py" \
        nohup bash /root/autodl-tmp/comfy_batch.sh <spec.json> > retouch.log 2>&1 &
A spec:
    {"picture": <png>, "dir": <out dir>, "box": [u0, v0, u1, v1], "prompt": ..., "negative": ...,
     "denoise": [0.65, 0.8], "seeds": [1, 2, 3, 4], "crop": [1008, 1792], "steps": 30, "rotate": [u, v, degrees]}
Qwen gets a crop of the picture at its own pixels (crop: w, h, multiples of 16, centred on the box), so a small part
is drawn at full resolution and nothing is upscaled; only the box, edges feathered, is pasted back. The crop is
also the reference picture, for the style. rotate turns what is inside the box about (u, v) before Qwen sees it
(cv2's angle: positive is counter-clockwise), to straighten a prop the model would otherwise keep as it is;
the seams it makes are inside the mask and get redrawn. Below denoise ~0.9 the model keeps the drawing's
structure (a hand's pose, a prop's angle); 1.0 draws the box afresh from the prompt and the surroundings.
Out: one full picture per denoise × seed, <dir>/<tag>_d<denoise>_s<seed>.png, and <dir>/_sheet.png with the box
of each next to the original."""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfy_gen import COMFY, img2img, post, qwen, wait  # noqa: E402


def load(path):
    return np.asarray(Image.open(path).convert("RGB"))


def save(path, a):
    Image.fromarray(a).save(path)


def grow(mask, px):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(mask.astype(np.uint8), k)


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = spec["dir"]
    os.makedirs(out, exist_ok=True)
    tag = os.path.basename(out.rstrip("/"))
    pic = load(spec["picture"])
    H, W = pic.shape[:2]
    u0, v0, u1, v1 = spec["box"]
    bx0, by0, bx1, by1 = int(u0 * W), int(v0 * H), int(u1 * W), int(v1 * H)
    cw, ch = spec.get("crop", [1008, 1792])
    cx = min(max((bx0 + bx1) // 2 - cw // 2, 0), W - cw)
    cy = min(max((by0 + by1) // 2 - ch // 2, 0), H - ch)
    src = pic
    if spec.get("rotate"):
        ru, rv, deg = spec["rotate"]
        turned = cv2.warpAffine(pic, cv2.getRotationMatrix2D((ru * W, rv * H), deg, 1.0), (W, H),
                                flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        inside = np.zeros((H, W), np.float32)
        inside[by0:by1, bx0:bx1] = 1
        inside = cv2.GaussianBlur(inside, (0, 0), 6)[..., None]
        src = (pic * (1 - inside) + turned * inside).round().astype(np.uint8)
    crop = pic[cy:cy + ch, cx:cx + cw]            # what is pasted around the result stays the original
    hole = np.zeros((ch, cw), np.uint8)
    hole[by0 - cy:by1 - cy, bx0 - cx:bx1 - cx] = 1
    save(f"{COMFY}/input/{tag}_work.png", src[cy:cy + ch, cx:cx + cw])
    save(f"{COMFY}/input/{tag}_hole.png", grow(hole, 16) * 255)       # 2 latent pixels of room around the box
    m = cv2.GaussianBlur(grow(hole, 10).astype(np.float32), (0, 0), 6)[..., None]

    pad = 60
    sx0, sy0, sx1, sy1 = max(bx0 - pad, 0), max(by0 - pad, 0), min(bx1 + pad, W), min(by1 + pad, H)

    def tile(img, label):
        t = np.ascontiguousarray(img[sy0:sy1, sx0:sx1])
        t = cv2.resize(t, (int(t.shape[1] * 700 / t.shape[0]), 700), interpolation=cv2.INTER_AREA)
        cv2.putText(t, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(t, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        return t

    tiles = [tile(pic, "original")]
    for dn in spec.get("denoise", [0.7]):
        for seed in spec.get("seeds", [1]):
            name = f"{tag}_d{int(round(dn * 100))}_s{seed}"
            j = dict(model="qwen", name=name, init=f"{tag}_work.png", mask=f"{tag}_hole.png", denoise=dn, seed=seed,
                     w=cw, h=ch, ref=[f"{tag}_work.png"], negative=spec.get("negative", ""), prompt=spec["prompt"],
                     steps=spec.get("steps", 30))
            status, outs = wait(post("/prompt", {"prompt": img2img(qwen(j), j, ["4", 0])})["prompt_id"])
            print(name, status, outs, flush=True)
            if not outs:
                continue
            res = load(f"{COMFY}/output/{outs[0]}")
            if res.shape[:2] != (ch, cw):
                res = cv2.resize(res, (cw, ch), interpolation=cv2.INTER_LANCZOS4)
            full = pic.copy()
            full[cy:cy + ch, cx:cx + cw] = (crop * (1 - m) + res * m).round().astype(np.uint8)
            save(f"{out}/{name}.png", full)
            tiles.append(tile(full, f"d{dn} s{seed}"))
    per = 5
    rows = [np.hstack(tiles[i:i + per]) for i in range(0, len(tiles), per)]
    wmax = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
    save(f"{out}/_sheet.png", np.vstack(rows))
    print("sheet", f"{out}/_sheet.png", flush=True)


if __name__ == "__main__":
    main()
