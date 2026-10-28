"""v5 round 3: the picks of rounds 1 and 2 finished.
- The 裏 twins: the 表 pick cut out (scripts/figures.py) and laid over the night plate from the same camera, then
  repainted where she is, so the pose and the silhouette stay and only her light, face and hair turn (the
  reflection in P3/P7 that is her 裏; the KV' of P9 that stops and looks back).
- The painted pass of the pictures the camera enters (PAINT_WITH: how round 2's test came out).
- Pictures to draw again with the inpaint mask that stops at her feet (round 1 painted reflections under W1).

    python cases/uraomote/jobs/v5_t3.py <plates dir> <art dir> <ComfyUI input dir>   -> v5_t3.json
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

from v5_prompts import (ANIMA_TAGS, KEEP, LOOK, PAINT, PLACE, POSES, REF, RELIGHT, TALL, TWINS, WIDE, anima, qwen)
from v5_t1 import prepare
from v5_t2 import base

HERE = os.path.dirname(os.path.abspath(__file__))
SUFFIX = "_00001_.png"
# the picks (picture names without the suffix); filled in from the contact sheets
TWIN_PICKS = {"kvn": "v5_kv_213s", "q1u": None}
ENTERED_PICKS = {}                     # plate -> pick, painted whole
AGAIN = {"w1": (215, 217, 219), "f1": (215, 217, 219), "a2": (215, 217)}   # plate -> seeds, drawn again (F1 on its corrected
#   plate: it looked into the sky's mirror seam; A2 with the wall in the frame)
PAINT_WITH = os.environ.get("PAINT_WITH", "qwen:0.7")      # round 2's test: Qwen at 0.7 paints the wall, the frame
#   and the sea in her hand and keeps them where they were (the horizon within a few pixels); Anima at 0.55/0.65
#   turned the rose hair orange and the sea into floor tiles and planks
TWIN_DENOISE = (0.6, 0.75)
TWIN_HAIR = "Her hair keeps its shape, but the rose-red underlayer glows through it now."
SIZES = {"kvn": TALL, "q1u": TALL}


def twin_prep(plates, art, inp, twin, pick):
    """The 表 pick over the night plate, and the mask of her (widened, stopping at her feet)."""
    pic = np.asarray(Image.open(os.path.join(art, pick + SUFFIX)).convert("RGB")).astype(np.float32)
    plate = Image.open(os.path.join(plates, f"{twin}_plate.png")).convert("RGB")
    if plate.size != (pic.shape[1], pic.shape[0]):
        plate = plate.resize((pic.shape[1], pic.shape[0]), Image.LANCZOS)
    fig = Image.open(os.path.join(art, "figures", pick + "_figure.png")).convert("L")
    a = np.asarray(fig.filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)[..., None] / 255
    comp = np.asarray(plate).astype(np.float32) * (1 - a) + pic * a
    Image.fromarray(comp.clip(0, 255).astype(np.uint8)).save(os.path.join(inp, f"v5_{twin}_init.png"))
    her = np.asarray(fig) > 128
    k = int(0.015 * her.shape[0]) * 2 + 1
    mask = np.asarray(Image.fromarray((her * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))).copy()
    feet = np.nonzero(her.any(axis=1))[0].max()
    mask[feet + int(0.004 * her.shape[0]) + 1:] = 0
    Image.fromarray(mask).save(os.path.join(inp, f"v5_{twin}_her.png"))
    print(twin, "from", pick)


def twin_jobs(twin):
    _src, pose, light, _hair = TWINS[twin]
    out = []
    for seed in (211, 213):
        for d in TWIN_DENOISE:
            out.append(qwen(f"v5_{twin}_{seed}t{int(d * 100)}", seed, SIZES[twin], KEEP, PLACE, RELIGHT, pose,
                            TWIN_HAIR, light, LOOK, ref=REF + [f"v5_{twin}_init.png"], init=f"v5_{twin}_init.png",
                            mask=f"v5_{twin}_her.png", denoise=d))
    return out


def paint_job(plate, pick, art, inp):
    shutil.copy(os.path.join(art, pick + SUFFIX), os.path.join(inp, pick + ".png"))
    how, d = PAINT_WITH.split(":")
    d = float(d)
    size = TALL if plate in ("kv", "q1s", "w1", "r0") else WIDE
    if how == "qwen":
        pose, light, _hair = POSES[plate]
        return qwen(f"{pick}_pq{int(d * 100)}", 211, size, KEEP, PAINT, pose, light, ref=REF, init=pick + ".png",
                    denoise=d)
    j = anima(f"{pick}_pa{int(d * 100)}", 211, pick + ".png", d, ANIMA_TAGS[plate])
    j["w"], j["h"] = size
    return j


def main():
    plates, art, inp = sys.argv[1], sys.argv[2], sys.argv[3]
    jobs = []
    for twin, pick in TWIN_PICKS.items():
        if pick:
            twin_prep(plates, art, inp, twin, pick)
            jobs += twin_jobs(twin)
    for plate, pick in ENTERED_PICKS.items():
        jobs.append(paint_job(plate, pick, art, inp))
    for plate, seeds in AGAIN.items():
        prepare(plates, inp, plate)
        jobs += [base(plate, s) for s in seeds]
    with open(os.path.join(HERE, "v5_t3.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    print(f"v5_t3.json: {len(jobs)} jobs")


if __name__ == "__main__":
    main()
