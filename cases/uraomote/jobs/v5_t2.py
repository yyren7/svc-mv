"""v5 round 2: the rest of the plates, painted the way round 1 showed works: the plate is the init picture AND the
second reference beside her design sheet (`s`). With the design sheet alone (`r`) Qwen redrew the place inside the
mask as another place (a second window frame, a wall through her, a bluish box round her); with the plate beside
it, it painted her into the place it saw. A1 again on a closer plate (round 1's had her at 4% of the picture).

First in the file, a test of the painted pass on two round-1 pictures (the pictures the camera enters must be
painted whole, the wall and the sea in her hand too): Qwen's own pass at 0.55 kept the render's look, so Qwen at
0.7 against Anima at 0.55 and 0.65. The painted passes of this round's picks follow in the next file.

    python cases/uraomote/jobs/v5_t2.py <plates dir> <ComfyUI input dir>   -> v5_t2.json beside this file
"""
import json
import os
import shutil
import sys

from v5_prompts import ANIMA_TAGS, INTO_SEEN, KEEP, LOOK, PAINT, PLACE, POSES, REF, TALL, WIDE, anima, qwen
from v5_t1 import prepare

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = {"q1s": (211, 213), "u2": (211, 213), "f1": (211, 213), "a1": (215, 217), "a2": (211, 213),
         "a3": (211, 213), "a4": (211, 213), "a5": (211, 213), "u1": (211, 213)}
SIZES = {"q1s": TALL, "u2": WIDE, "f1": WIDE, "a1": WIDE, "a2": WIDE, "a3": WIDE, "a4": WIDE, "a5": WIDE, "u1": WIDE,
         "kv": TALL, "w1": TALL, "r0": TALL}
PAINT_TESTS = {"v5_kv_213s": ("kv", TALL, "standing, from behind, looking back, looking at viewer, window, window "
                                          "frame, sky, dawn, backlighting, plaster wall, ocean, water, reflection"),
               "v5_a1_211s": ("a1", WIDE, ANIMA_TAGS["a1"])}


def base(name, seed):
    pose, light, hair = POSES[name]
    return qwen(f"v5_{name}_{seed}s", seed, SIZES[name], KEEP, PLACE, INTO_SEEN, pose, hair, light, LOOK,
                ref=REF + [f"v5_{name}_plate.png"], init=f"v5_{name}_plate.png", mask=f"v5_{name}_her.png", denoise=1.0)


def paint_tests(inp):
    out = []
    for pic, (plate, size, tags) in PAINT_TESTS.items():
        src = os.path.join(os.path.dirname(inp), "output", pic + "_00001_.png")
        if not os.path.exists(src):
            print("no", src)
            continue
        shutil.copy(src, os.path.join(inp, pic + ".png"))
        pose, light, _hair = POSES[plate]
        q = qwen(pic + "_pq70", 211, size, KEEP, PAINT, pose, light, ref=REF, init=pic + ".png", denoise=0.7)
        out.append(q)
        for d in (0.55, 0.65):
            a = anima(f"{pic}_pa{int(d * 100)}", 211, pic + ".png", d, tags)
            a["w"], a["h"] = size
            out.append(a)
    return out


def main():
    plates, inp = sys.argv[1], sys.argv[2]
    all_jobs = paint_tests(inp)
    for name, seeds in ROUND.items():
        prepare(plates, inp, name)
        all_jobs += [base(name, s) for s in seeds]
    with open(os.path.join(HERE, "v5_t2.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=1)
    print(f"v5_t2.json: {len(all_jobs)} jobs")


if __name__ == "__main__":
    main()
