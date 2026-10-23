"""v4 round 3: KV' (script_v4.md 3.4), the 裏 version of each round-2 KV in its own composition, so that printed
mirrored on the back of the sheet it shows through exactly behind the 表 face. Qwen redraws the KV (img2img, with
the design sheet as reference) at night, at two strengths.
    python cases/uraomote/jobs/v4_t3.py                       -> cases/uraomote/jobs/v4_t3.json
    python cases/uraomote/jobs/v4_t3.py <art dir> <input dir>  also copies the KVs to ComfyUI's input (needs PIL)"""
import json
import os
import shutil
import sys

from v4_prompts import KEEP, LOOK, LOOSE, REF, URA, qwen

HERE = os.path.dirname(os.path.abspath(__file__))
KVS = ["v4_kv_211", "v4_kv_213"]
URA_KV = ("The same picture turned to its hidden side: keep the composition, her pose, the framing and the window "
          "exactly as in the input picture, but it is night. The window behind her is dark with cold blue night, and "
          "a strong rose-red light from behind her sets her hair and outline glowing. She still looks over her "
          "shoulder at the viewer, but her eyes are wide and feverish, glistening, lips parted, a flush on her cheeks.")

jobs = [qwen(f"v4_kvu_{kv[6:]}_{d}", 221, (928, 1664), KEEP, URA_KV, LOOSE, LOOK, URA, ref=REF,
             init=f"{kv}_00001_.png", denoise=d / 100)
        for kv in KVS for d in (62, 75)]
with open(os.path.join(HERE, "v4_t3.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(f"v4_t3.json: {len(jobs)} jobs")

if len(sys.argv) == 3:
    for kv in KVS:
        shutil.copy(os.path.join(sys.argv[1], f"{kv}_00001_.png"), os.path.join(sys.argv[2], f"{kv}_00001_.png"))
        print(kv)
