"""v5 round 5: the 裏 twins a third way, and A5 with her eyes open.
Round 4's twins kept the pose and the silhouette but also the dawn on her (a bright white shirt in the night): the
second reference was the composite, her 表 self in it, and Qwen kept her as the reference showed her. Now the
second reference is the clean night plate, the repaint 0.9 / 0.95, the night light said plainly. (scripts/relight.py
is the fallback: the silhouette exactly, the light in 2D.)
A5 open-eyed: her face alone repainted (the parts map's face, in the top of her figure), so the picture is the
same but for the eyes: the cut from A5 to Q1 in P1.2 is the same composition.

    python cases/uraomote/jobs/v5_t5.py <plates dir> <art dir> <ComfyUI input dir>   -> v5_t5.json
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

import v5_t3 as T3
from v5_prompts import DAWN, KEEP, LOOK, PLACE, REF, RELIGHT, TWINS, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
SUFFIX = "_00001_.png"
TWIN_PICKS = {"kvn": "v5_kv_213s", "q1u": "v5_q1s_211s"}
NIGHT_ON_HER = ("Night. Her white shirt is not white now: it is dark blue-grey in the night, and her skin is in cool "
                "shadow; a vivid rose-red rim light from low behind her runs along her hair, her shoulder and the side "
                "of her body; her face is lit only faintly from the front. Deep velvety blacks, glossy highlights.")
A5 = "v5_a5_213s_c_pq70"
OPEN = ("Close-up of her face and shoulders before the window at dawn: her eyes are open now, looking straight at the "
        "viewer, calm and clear, the pale dawn sky reflected in her dark grey eyes. Everything else stays exactly as it is.")


def twin_jobs(plates, inp, twin):
    shutil.copy(T3.clean(plates, twin), os.path.join(inp, f"v5_{twin}_clean.png"))
    _src, pose, _light, _hair = TWINS[twin]
    out = []
    for seed in (211, 213):
        for d in (0.9, 0.95):
            out.append(qwen(f"v5_{twin}_{seed}n{int(d * 100)}", seed, T3.SIZES[twin], NIGHT_ON_HER, RELIGHT, KEEP,
                            PLACE, pose, T3.TWIN_HAIR, LOOK, ref=REF + [f"v5_{twin}_clean.png"],
                            init=f"v5_{twin}_init.png", mask=f"v5_{twin}_her.png", denoise=d))
    return out


def face_mask(art, inp, pick):
    """Her face: the parts map's face and skin (G) in the top 40% of her figure, widened."""
    parts = np.asarray(Image.open(os.path.join(art, "maps", pick + "_parts.png")).convert("RGB"))[..., 1] > 100
    fig = np.asarray(Image.open(os.path.join(art, "figures", pick + "_figure.png")).convert("L")) > 128
    if parts.shape != fig.shape:
        parts = np.asarray(Image.fromarray(parts.astype(np.uint8) * 255).resize(fig.shape[::-1])) > 128
    ys = np.nonzero(fig.any(axis=1))[0]
    top, bottom = ys.min(), ys.min() + int(0.4 * (ys.max() - ys.min()))
    m = parts & fig
    m[:top] = False
    m[bottom:] = False
    k = int(0.02 * fig.shape[0]) * 2 + 1
    Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(k)).save(os.path.join(inp, pick + "_face.png"))
    print(pick, "face", int(m.mean() * 1000) / 10, "% of the picture")


def main():
    plates, art, inp = sys.argv[1], sys.argv[2], sys.argv[3]
    jobs = []
    for twin, pick in TWIN_PICKS.items():
        T3.twin_prep(plates, art, inp, twin, pick)
        jobs += twin_jobs(plates, inp, twin)
    shutil.copy(os.path.join(art, A5 + SUFFIX), os.path.join(inp, A5 + ".png"))
    face_mask(art, inp, A5)
    for seed in (211, 213):
        jobs.append(qwen(f"v5_a5o_{seed}", seed, (1664, 928), KEEP, OPEN, DAWN, LOOK, ref=REF + [A5 + ".png"],
                         init=A5 + ".png", mask=A5 + "_face.png", denoise=0.7))
    with open(os.path.join(HERE, "v5_t5.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    print(f"v5_t5.json: {len(jobs)} jobs")


if __name__ == "__main__":
    main()
