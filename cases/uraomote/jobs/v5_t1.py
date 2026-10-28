"""v5 round 1: four pictures painted into the world's own plates (renders/v5_plates, v5_plates.py), to see whether
Qwen paints her into a rendered place in its light: the KV at the window at dawn, W1 in the rain, R0 running at
the camera at night, and A1 at the window (a picture the camera enters, so a second pass paints the whole).
Two seeds each; two ways each: `r` with her design sheet alone as the reference (the place is the init picture),
`s` with the plate as a second reference as well (the model sees the grey mannequin it replaces).

    python cases/uraomote/jobs/v5_t1.py <plates dir> <ComfyUI input dir>   -> v5_t1.json beside this file
                                                                            + the plates and masks in input/
On the server: /root/miniconda3/bin/python (PIL, numpy); the plates dir is cases/uraomote/renders/v5_plates.
The mask (`_her.png`, the mannequin widened in Blender) is widened again by 1.5% of the height here, and the plate
is copied as the init picture. Then: nohup bash scripts/comfy_batch.sh cases/uraomote/jobs/v5_t1.json ...
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

from v5_prompts import ENTERED, INTO, INTO_SEEN, KEEP, LOOK, PAINT, PLACE, POSES, REF, TALL, WIDE, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = ["kv", "w1", "r0", "a1"]
SEEDS = (211, 213)
SIZES = {"kv": TALL, "w1": TALL, "r0": TALL, "a1": WIDE}


def prepare(plates, inp, name):
    """The plate as the init picture and her widened mask, in ComfyUI/input."""
    Image.open(os.path.join(plates, f"{name}_plate.png")).convert("RGB").save(os.path.join(inp, f"v5_{name}_plate.png"))
    her = np.asarray(Image.open(os.path.join(plates, f"{name}_her.png")).convert("L")) > 128
    k = int(0.015 * her.shape[0]) * 2 + 1
    mask = Image.fromarray((her * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))
    mask.save(os.path.join(inp, f"v5_{name}_her.png"))
    print(name, "mask", k, "px wider,", int(her.mean() * 100), "% of the picture")


def jobs(name):
    pose, light, hair = POSES[name]
    out = []
    for seed in SEEDS:
        for tag, into, refs in (("r", INTO, REF), ("s", INTO_SEEN, REF + [f"v5_{name}_plate.png"])):
            first = f"v5_{name}_{seed}{tag}"
            out.append(qwen(first, seed, SIZES[name], KEEP, PLACE, into, pose, hair, light, LOOK, ref=refs,
                            init=f"v5_{name}_plate.png", mask=f"v5_{name}_her.png", denoise=1.0))
            if name in ENTERED:
                out.append(qwen(first + "p", seed, SIZES[name], KEEP, PAINT, pose, light, ref=REF, init="@" + first,
                                denoise=0.55))
    return out


def main():
    plates, inp = sys.argv[1], sys.argv[2]
    all_jobs = []
    for name in ROUND:
        prepare(plates, inp, name)
        all_jobs += jobs(name)
    with open(os.path.join(HERE, "v5_t1.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=1)
    print(f"v5_t1.json: {len(all_jobs)} jobs")


if __name__ == "__main__":
    main()
