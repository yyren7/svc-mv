"""Split a finished picture into layers for Blender: the character, and the background in three depth bands (near,
mid, far), every layer the full size of the picture and aligned with the others, each with what it hides drawn in.
    CLIENT="env PYTHONPATH=/root/autodl-tmp/pv/pylib /root/autodl-tmp/ComfyUI/venv/bin/python $PWD/scripts/layers.py" \
        bash scripts/comfy_batch.sh <spec.json>...
Runs on AutoDL in the repo's checkout, next to comfy_gen.py, with ComfyUI up (comfy_batch.sh starts it). A spec:
    {"picture": <file in ComfyUI/output>, "dir": <out dir>, "scene": <the whole background, a sentence or two>,
     "far_scene": <only the distant background>, "near": <depth>, "far": <depth>}
Without "near" and "far" it stops after the plate (the picture with the character taken out and filled in) and the
depth map, and prints depth quantiles to pick them from: depth is 0 at the back and 1 at the front, and a pixel is
far below "far", near above "near", mid in between.
Out: char.png, near.png, mid.png (RGBA, straight alpha), far.png (opaque); depth.png (16-bit, front white) and
depth.npy of the picture; far_depth.png, mid_depth.png, near_depth.png in the same scale with what each layer hides
filled; plate.png; layers.json (back to front, z and bbox of each layer); _check.png.
anime-seg finds the character, Depth Anything V2 the depth, Qwen-Image-2.1 (masked img2img) draws what is hidden,
4x-AnimeSharp brings the fill to full size. How to run it: docs/comfyui.md."""
import json
import os
import shutil
import sys

import cv2
import numpy as np
import onnxruntime as ort
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfy_gen import COMFY, img2img, post, qwen, upscale, wait  # noqa: E402

MODELS = "/root/autodl-tmp/pv/models"
WORK = (1792, 1008)        # Qwen's size for the fills: 16:9, multiples of 16
UPSCALER = "4x-AnimeSharp.pth"
NEG = "people, girl, person, character, animal, text, letters, logo, watermark, signature, blurry, low quality"


def load(path):
    return np.asarray(Image.open(path).convert("RGB"))


def save(path, a):
    Image.fromarray(a).save(path)


def seg(img, s=1024):
    """anime-seg (ISNet) on a picture letterboxed into s x s: the character's alpha, 0..1, at the picture's size."""
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


def char_alpha(img):
    """The character: a first pass on the whole picture finds her, a second on her bounding box draws the edge."""
    m = seg(img)
    ys, xs = np.nonzero(m > 0.5)
    H, W = m.shape
    pad = int(0.04 * W)
    y0, y1, x0, x1 = max(ys.min() - pad, 0), min(ys.max() + pad, H), max(xs.min() - pad, 0), min(xs.max() + pad, W)
    m = np.zeros_like(m)
    m[y0:y1, x0:x1] = seg(img[y0:y1, x0:x1])
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    m = guided(gray, m.astype(np.float32), 4, 1e-4)
    # anime-seg leaves a faint haze over glowing background next to her (the flowers by the tail); keep only alpha
    # within 12 px of where she is solid, which still keeps nine in ten of the loose hair strands
    core = cv2.GaussianBlur(grow(m > 0.75, 12).astype(np.float32), (0, 0), 6)
    return m * core


def depth(img):
    """Depth Anything V2 Large, raw: a disparity, bigger at the front, in its own scale for every picture."""
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    path = f"{MODELS}/depth-anything-v2-large"
    if not hasattr(depth, "model"):
        depth.proc = AutoImageProcessor.from_pretrained(path)
        depth.model = AutoModelForDepthEstimation.from_pretrained(path).cuda().eval()
    x = depth.proc(images=Image.fromarray(img), return_tensors="pt", size={"height": 756, "width": 1344}).to("cuda")
    with torch.no_grad():
        d = depth.model(**x).predicted_depth[None]
    return torch.nn.functional.interpolate(d, size=img.shape[:2], mode="bicubic")[0, 0].float().cpu().numpy()


def fit(src, ref, same):
    """src brought into ref's scale: the a * src + b that matches ref best where both show the same thing."""
    a, b = np.linalg.lstsq(np.stack([src[same], np.ones(same.sum())], 1), ref[same], rcond=None)[0]
    return (a * src + b).astype(np.float32)


def save16(path, d):
    save(path, (d.clip(0, 1) * 65535).round().astype(np.uint16))


def grow(mask, px):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(mask.astype(np.uint8), k)


def fill(tag, base, hole, prompt, seed):
    """Qwen draws the white part of `hole` (full size, 0/1) into `base` (full size RGB) at WORK size; the fill is
    enlarged with the upscale model and pasted back only inside the hole, so everything else stays exact."""
    H, W = hole.shape
    work = cv2.resize(base, WORK, interpolation=cv2.INTER_AREA)
    scale = WORK[0] / W
    hole_w = grow(cv2.resize(hole, WORK, interpolation=cv2.INTER_NEAREST), max(int(48 * scale), 8))
    save(f"{COMFY}/input/{tag}_work.png", work)
    save(f"{COMFY}/input/{tag}_hole.png", hole_w * 255)
    j = dict(model="qwen", name=f"{tag}_fill", init=f"{tag}_work.png", mask=f"{tag}_hole.png", denoise=1.0, seed=seed,
             w=WORK[0], h=WORK[1], ref=[f"{tag}_work.png"], negative=NEG, prompt=prompt)
    status, outs = wait(post("/prompt", {"prompt": img2img(qwen(j), j, ["4", 0])})["prompt_id"])
    print(j["name"], status, outs, flush=True)
    shutil.copy(f"{COMFY}/output/{outs[0]}", f"{COMFY}/input/{outs[0]}")
    u = dict(name=f"{tag}_fill_big", init=outs[0], upscale=UPSCALER, w=W, h=H)
    status, big = wait(post("/prompt", {"prompt": upscale(u)})["prompt_id"])
    print(u["name"], status, big, flush=True)
    f = load(f"{COMFY}/output/{big[0]}")
    m = cv2.GaussianBlur(grow(hole, 24).astype(np.float32), (0, 0), 8)[..., None]
    return (base * (1 - m) + f * m).round().astype(np.uint8), f


def bands(d, near, far):
    """Soft masks of the near and mid bands: a small ramp at each threshold, specks smaller than 0.05% dropped."""
    ramp = lambda x, t: np.clip((x - t) / 0.03 + 0.5, 0, 1)  # noqa: E731
    n, m = ramp(d, near), ramp(d, far) * (1 - ramp(d, near))
    for a in (n, m):
        k, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8))
        small = np.isin(lab, np.nonzero(st[:, cv2.CC_STAT_AREA] < 0.0005 * a.size)[0])
        a[small & (lab > 0)] = 0
    return n.astype(np.float32), m.astype(np.float32)


def rgba(rgb, a):
    return np.dstack([rgb, (a * 255).round().astype(np.uint8)])


def check(path, layers, picture):
    """The layers side by side over a checkerboard, and the stack composited back next to the picture."""
    H, W = picture.shape[:2]
    s = 480 / W
    tile = lambda a: cv2.resize(a, (480, int(H * s)), interpolation=cv2.INTER_AREA)  # noqa: E731
    yy, xx = np.mgrid[:int(H * s), :480]
    board = np.where(((yy // 16 + xx // 16) % 2)[..., None] == 0, 200, 140).astype(np.float32)
    cells, out = [], np.zeros((H, W, 3), np.float32)
    for name, a in layers:
        if a.shape[2] == 3:
            a = np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])
        al = a[..., 3:].astype(np.float32) / 255
        out = out * (1 - al) + a[..., :3] * al
        t = tile(a).astype(np.float32)
        cells.append((board * (1 - t[..., 3:] / 255) + t[..., :3] * t[..., 3:] / 255).astype(np.uint8))
    cells += [tile(out.round().astype(np.uint8)), tile(picture)]
    print("stack vs picture: mean abs diff", np.abs(out - picture).mean().round(3), flush=True)
    rows = [np.hstack(cells[i:i + 3] + [np.zeros_like(cells[0])] * (3 - len(cells[i:i + 3]))) for i in range(0, len(cells), 3)]
    save(path, np.vstack(rows))


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = spec["dir"]
    os.makedirs(out, exist_ok=True)
    tag = os.path.basename(out.rstrip("/"))
    picture = load(os.path.join(f"{COMFY}/output", spec["picture"]))
    if os.path.exists(f"{out}/char.png"):       # delete a file to make it again
        alpha = np.asarray(Image.open(f"{out}/char.png"))[..., 3] / 255
    else:
        alpha = char_alpha(picture)
        save(f"{out}/char.png", rgba(picture, alpha))
    if os.path.exists(f"{out}/plate.png"):
        plate = load(f"{out}/plate.png")
        d, dp = np.load(f"{out}/depth.npy"), np.load(f"{out}/_plate_depth.npy")
    else:
        hole = (alpha > 0.03).astype(np.uint8)
        plate, _ = fill(f"{tag}_plate", picture, hole,
                        "Picture 1 with the girl taken out: remove the cat girl, her tail, her microphone and its cable "
                        "completely and show only the empty scene behind her, continuing what is around her. "
                        + spec["scene"], spec.get("seed", 81))
        save(f"{out}/plate.png", plate)
        raw = depth(picture)          # the picture's depth sets the scale: 0..1 over the picture, the front white
        d = ((raw - raw.min()) / (raw.max() - raw.min())).astype(np.float32)
        np.save(f"{out}/depth.npy", d)
        save16(f"{out}/depth.png", d)
        dp = fit(depth(plate), d, grow(hole, 60) == 0)
        np.save(f"{out}/_plate_depth.npy", dp)
    smooth = cv2.GaussianBlur(dp, (0, 0), 3)
    print("plate depth quantiles 10..90%:", [round(float(np.percentile(smooth, q)), 3) for q in range(10, 100, 10)], flush=True)
    if "near" not in spec:
        return
    n, m = bands(smooth, spec["near"], spec["far"])
    hidden = ((n + m) > 0.03).astype(np.uint8)
    if os.path.exists(f"{out}/far.png"):
        far = load(f"{out}/far.png")
    else:
        far, _ = fill(f"{tag}_far", plate, hidden,
                      "Picture 1 with everything in front of the distant background taken out: show only the distant "
                      "background, continuing it where the nearer things were. " + spec["far_scene"], spec.get("seed", 81))
    df = fit(depth(far), dp, grow(hidden, 60) == 0)     # against the plate's: the picture's depth has her in it
    layers = [("far", far), ("mid", rgba(plate, m)), ("near", rgba(plate, n)), ("char", rgba(picture, alpha))]
    for name, a in layers:
        save(f"{out}/{name}.png", a)
    for name, dd in (("far", df), ("mid", dp), ("near", dp)):    # each layer's own depth, with what it hides filled
        save16(f"{out}/{name}_depth.png", dd)

    def info(name, a):
        """z from where the layer shows in the picture; bbox of its pixels (far is opaque, so the whole frame)."""
        on = a > 0.5
        ys, xs = np.nonzero(np.ones_like(on) if name == "far" else on)
        z = df if name == "far" else d if name == "char" else dp
        return dict(name=name, file=f"{name}.png", depth_file=None if name == "char" else f"{name}_depth.png",
                    z=round(float(np.median(z[on])), 3) if on.any() else None,
                    bbox=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None)
    json.dump(dict(picture=spec["picture"], size=list(picture.shape[1::-1]), near=spec["near"], far=spec["far"],
                   order="back to front; z is the median disparity of the layer in depth.png's scale (1 = front)",
                   layers=[info("far", 1 - n - m), info("mid", m), info("near", n), info("char", alpha)]),
              open(f"{out}/layers.json", "w"), indent=1)
    check(f"{out}/_check.png", layers, picture)


if __name__ == "__main__":
    main()
