"""v4 round 3: KV' (script_v4.md 3.4), the 裏 version of each round-2 KV in its own composition, so that printed
mirrored on the back of the sheet it shows through exactly behind the 表 face. Qwen redraws the KV (img2img, with
the design sheet as reference) at night, at two strengths. Redrawn from the KV as it is, the picture stayed in
daylight at both strengths (v4_kvu_*_62/75: only her face changed), so each KV is first turned to night: dark
ink-blue, with a rose glow from the window behind her (v4_kvu_*_n62/n75).
    python cases/uraomote/jobs/v4_t3.py                       -> cases/uraomote/jobs/v4_t3.json
    python cases/uraomote/jobs/v4_t3.py <art dir> <input dir>  also writes the night inits to ComfyUI's input (needs PIL)"""
import json
import os
import sys

from v4_prompts import KEEP, LOOK, LOOSE, REF, URA, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
KVS = ["v4_kv_211", "v4_kv_213"]
URA_KV = ("The same picture turned to its hidden side: keep the composition, her pose, the framing and the window "
          "exactly as in the input picture, but it is night. The window behind her is dark with cold blue night, and "
          "a strong rose-red light from behind her sets her hair and outline glowing. She still looks over her "
          "shoulder at the viewer, but her eyes are wide and feverish, glistening, lips parted, a flush on her cheeks.")


def init_name(kv):
    return f"{kv}_night.png"


def night(src, dst):
    """The KV's luminance in ink-blue, plus a rose glow centred on the window behind her shoulder."""
    from PIL import Image, ImageChops
    im = Image.open(src).convert("RGB")
    w, h = im.size
    lum = im.convert("L")
    dark = Image.merge("RGB", [lum.point(lambda v, k=k: int(v * k)) for k in (0.10, 0.13, 0.26)])
    glow = Image.new("L", (w, h))
    px = glow.load()
    cx, cy, r = 0.82 * w, 0.32 * h, 0.75 * w
    for y in range(h):
        for x in range(w):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r
            px[x, y] = int(255 * max(0.0, 1 - d) ** 1.6)
    rose = Image.merge("RGB", [glow.point(lambda v, k=k: int(v * k)) for k in (0.95, 0.12, 0.32)])
    ImageChops.add(dark, rose).save(dst)


jobs = [qwen(f"v4_kvu_{kv[6:]}_n{d}", 221, (928, 1664), KEEP, URA_KV, LOOSE, LOOK, URA, ref=REF,
             init=init_name(kv), denoise=d / 100)
        for kv in KVS for d in (62, 75)]
with open(os.path.join(HERE, "v4_t3.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(f"v4_t3.json: {len(jobs)} jobs")

if len(sys.argv) == 3:
    for kv in KVS:
        night(os.path.join(sys.argv[1], f"{kv}_00001_.png"), os.path.join(sys.argv[2], init_name(kv)))
        print(init_name(kv))
