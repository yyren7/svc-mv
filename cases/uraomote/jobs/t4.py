"""Batch t4: KV' from the KV candidates. Script v3 wants KV' in the same composition as KV, and none of the ura
drafts matches a kv draft, so each candidate (kv_43, kv_47, kv_53) gets its cream ground flooded to the black paper
and Anima redraws it as the 裏 version at 0.6 and 0.75.
    python cases/uraomote/jobs/t4.py                          -> cases/uraomote/jobs/t4.json
    python cases/uraomote/jobs/t4.py <art dir> <input dir>    also writes the black-ground inits (needs PIL)
On the server: <art dir> is ComfyUI/output, <input dir> is ComfyUI/input."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KVS = [43, 47, 53]
BLACK = (0x12, 0x11, 0x16)   # the black paper of script v3, 0.2

TAGS = ("masterpiece, best quality, safe, newest, 1girl, solo, short hair, bob cut, black hair, two-tone hair, "
        "pink inner hair, red heart hair ornament, hairclip, serafuku, navy sailor collar, white stripes, red bowtie, "
        "oversized cardigan, cream cardigan, sleeves past fingers, elbow patch, pleated skirt, navy skirt, "
        "holding heart, large heart, hugging heart, glowing heart, floating hair, hair blowing, wide-eyed, blush, "
        "sweat, looking at viewer, upper body, flat color, limited palette, bold lineart, black background, "
        "simple background")
WHO = ("A girl with a black bob haircut whose inner layer is dyed fluorescent pink, wearing a navy sailor school "
       "uniform under an oversized cream cardigan with a crooked red patch on the left elbow. Her hair lifts and the "
       "fluorescent pink inner layer shows; wide-eyed and flushed as if with a fever, she hugs a big flat glowing pink "
       "heart to her chest. Neon pink and cyan lines and flat colors on black paper, like a fluorescent risograph print.")
NEG = "worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration, watermark, text, signature"


def init_name(kv):
    return f"urao_kv{kv}_black.png"


def black_ground(src, dst):
    """Flood the cream ground from the top, left and right edges (the figure stands on the bottom edge)."""
    from PIL import Image, ImageDraw
    im = Image.open(src).convert("RGB")
    w, h = im.size
    seeds = [(x, 0) for x in range(0, w, 32)] + [(x, y) for y in range(0, h, 32) for x in (0, w - 1)]
    for p in seeds:
        if sum(im.getpixel(p)) > 600:   # still cream: not filled yet, not a line
            ImageDraw.floodfill(im, p, BLACK, thresh=60)
    im.save(dst)


jobs = [{"model": "anima", "name": f"kvu_{kv}_{d}", "init": init_name(kv), "denoise": d / 100, "seed": 81,
         "w": 896, "h": 1152, "prompt": f"{TAGS}. {WHO}", "negative": NEG}
        for kv in KVS for d in (60, 75)]
with open(os.path.join(HERE, "t4.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(jobs, f, ensure_ascii=False, indent=1)
print(f"t4.json: {len(jobs)} jobs")

if len(sys.argv) == 3:
    for kv in KVS:
        black_ground(os.path.join(sys.argv[1], f"kv_{kv}_00001_.png"), os.path.join(sys.argv[2], init_name(kv)))
        print(init_name(kv))
