"""Maps for the hybrid prints: for each illustration a depth map, a map of its flat planes and a map of her parts,
so in Blender the sheet can be a relief, its sky, water and mirrors can be the hall's own (the 3D world set into
the 2D picture), and 3D things (ink, rain, ripples) can attach to her hair, face and clothes.

    python cases/uraomote/scripts/maps.py <art dir> <name> [name ...]      (`all`: every *_211 picture and KV')
    -> <art dir>/maps/<name>_depth.png   16-bit, bright = near (Depth Anything V2 small)
       <art dir>/maps/<name>_flat.png    R sky or window glass, G water, B mirror (CLIPSeg, smoothed)
       <art dir>/maps/<name>_parts.png   R hair, G face and skin, B clothes
       <art dir>/maps/<name>_check.jpg   the picture with the flat map over it, to judge it by eye

Runs on the server (torch, transformers). The hub is not reachable from there: the two models' files are fetched
with curl from hf-mirror.com into tmp/hf/ and named by DEPTH_MODEL and SEG_MODEL.
"""
import os
import sys

import numpy as np
import torch
from PIL import Image, ImageFilter

DEPTH = os.environ.get("DEPTH_MODEL", "depth-anything/Depth-Anything-V2-Small-hf")
SEG = os.environ.get("SEG_MODEL", "CIDAS/clipseg-rd64-refined")
FLAT = {"R": ["sky", "window", "bright light through a window"],
        "G": ["water surface", "dark water", "lake at night"],
        "B": ["mirror"]}
PARTS = {"R": ["hair"], "G": ["face", "skin"], "B": ["clothes", "shirt", "skirt"]}
LOW, HIGH = 0.4, 0.7          # CLIPSeg probability -> mask: 0 below LOW, 1 above HIGH
# pictures whose whole background is one plane: everything far in the depth map is that plane (CLIPSeg misses a
# black water surface at night and only patches a pale sky)
BACKDROP = {"v4_q1_": "R", "v4_u1_": "G", "v4_u3_": "G", "v4_c1_": "G", "v4_s1_": "R", "v4_s2_": "R", "v4_s3_": "R"}
FAR = 0.5                     # depth (0 far .. 1 near) below which a point belongs to the backdrop


def depth(pipe, img):
    """0 far .. 1 near, the picture's size."""
    out = pipe(img)
    d = out["predicted_depth"]
    d = torch.nn.functional.interpolate(d[None, None].float(), size=img.size[::-1], mode="bicubic",
                                        align_corners=False)[0, 0].cpu().numpy()
    return (d - d.min()) / max(d.max() - d.min(), 1e-6)


def masks(proc, model, img, device, table, backdrop=None, d=None):
    """An RGB image of three CLIPSeg masks, each the best of its prompts, thresholded and smoothed; the `backdrop`
    channel also takes everything far in the depth `d`."""
    chans = []
    for key in ("R", "G", "B"):
        prompts = table[key]
        inputs = proc(text=prompts, images=[img] * len(prompts), padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits                           # (prompts, 352, 352)
        p = torch.sigmoid(logits).max(dim=0).values
        p = torch.nn.functional.interpolate(p[None, None], size=img.size[::-1], mode="bilinear",
                                            align_corners=False)[0, 0].cpu().numpy()
        p = np.clip((p - LOW) / (HIGH - LOW), 0.0, 1.0)
        if key == backdrop:
            p = np.maximum(p, np.clip((FAR - d) / 0.12, 0.0, 1.0))
        chans.append(Image.fromarray((p * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(img.size[0] / 300)))
    return Image.merge("RGB", chans)


def check(img, flat):
    """The picture dimmed, with the flat map over it in its channel colours."""
    a = np.asarray(img.convert("RGB")).astype(np.float32) * 0.45
    mk = np.asarray(flat).astype(np.float32)
    return Image.fromarray(np.clip(a + mk * 0.55, 0, 255).astype(np.uint8))


def main():
    art, names = sys.argv[1], sys.argv[2:]
    if names == ["all"]:
        names = sorted(f[:-len("_00001_.png")] for f in os.listdir(art)
                       if f.endswith("_211_00001_.png") or f.startswith("v4_kvu_211_n75"))
    out = os.path.join(art, "maps")
    os.makedirs(out, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    from transformers import pipeline, CLIPSegProcessor, CLIPSegForImageSegmentation
    pipe = pipeline("depth-estimation", model=DEPTH, device=0 if device == "cuda" else -1)
    proc = CLIPSegProcessor.from_pretrained(SEG)
    seg = CLIPSegForImageSegmentation.from_pretrained(SEG).to(device).eval()
    for name in names:
        img = Image.open(os.path.join(art, f"{name}_00001_.png")).convert("RGB")
        d = depth(pipe, img)
        Image.fromarray((d * 65535).astype(np.uint16)).save(os.path.join(out, f"{name}_depth.png"))
        backdrop = next((v for k, v in BACKDROP.items() if k in name), None)
        flat = masks(proc, seg, img, device, FLAT, backdrop, d)
        flat.save(os.path.join(out, f"{name}_flat.png"))
        masks(proc, seg, img, device, PARTS).save(os.path.join(out, f"{name}_parts.png"))
        check(img, flat).save(os.path.join(out, f"{name}_check.jpg"), quality=88)
        cover = [np.asarray(flat)[..., k].mean() / 255 for k in range(3)]
        print(f"{name}: sky {cover[0]:.0%}  water {cover[1]:.0%}  mirror {cover[2]:.0%}", flush=True)


if __name__ == "__main__":
    main()
