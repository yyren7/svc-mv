"""v5 round 4: round 3's twins and composed painted passes again, over the clean plates (without the mannequin).
Round 3 laid the 表 pick over the night plate with the grey mannequin still standing in it: a blue and rose
column showed round her, and at 0.6 / 0.75 the repaint changed her mouth and little of her light. Now the clean
night plate, and the repaint at 0.82 / 0.9, with the 裏 light named first.

    python cases/uraomote/jobs/v5_t4.py <plates dir> <art dir> <ComfyUI input dir>   -> v5_t4.json
"""
import json
import os
import sys

import v5_t3 as T3
from v5_prompts import KEEP, LOOK, NIGHT, PLACE, REF, RELIGHT, TWINS, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
TWIN_PICKS = {"kvn": "v5_kv_213s", "q1u": "v5_q1s_211s"}
COMPOSED = {"a1": "v5_a1_217s", "a4": "v5_a4_211s", "a5": "v5_a5_213s", "u2": "v5_u2_211s", "u1": "v5_u1_211s"}
TWIN_DENOISE = (0.82, 0.9)


def twin_jobs(twin):
    _src, pose, light, _hair = TWINS[twin]
    out = []
    for seed in (211, 213):
        for d in TWIN_DENOISE:
            out.append(qwen(f"v5_{twin}_{seed}u{int(d * 100)}", seed, T3.SIZES[twin], NIGHT, RELIGHT, KEEP, PLACE,
                            pose, T3.TWIN_HAIR, LOOK, ref=REF + [f"v5_{twin}_init.png"], init=f"v5_{twin}_init.png",
                            mask=f"v5_{twin}_her.png", denoise=d))
    return out


def main():
    plates, art, inp = sys.argv[1], sys.argv[2], sys.argv[3]
    jobs = []
    for plate, pick in COMPOSED.items():
        jobs.append(T3.paint_job(plate, pick, art, inp, plates, "compose"))
    for twin, pick in TWIN_PICKS.items():
        T3.twin_prep(plates, art, inp, twin, pick)
        jobs += twin_jobs(twin)
    with open(os.path.join(HERE, "v5_t4.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    print(f"v5_t4.json: {len(jobs)} jobs")


if __name__ == "__main__":
    main()
