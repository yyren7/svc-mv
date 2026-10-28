#!/bin/bash
# The v5 stills with the pictures painted into the world (art/v5), beside the first ones (the v4 pictures, kept as
# world_<still>_v4art.png), a side-by-side of the two, and a sheet of the picked pictures.
#   W1_PIC=v5_w1_... Q1U_PIC=v5_q1u_... bash cases/uraomote/runs/stills_v5art.sh [samples]
set -e
cd "$(dirname "$(realpath "$0")")/../../.."
C=cases/uraomote
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
M=/root/miniconda3/bin/python
O=$C/renders/v5_world
S=${1:-128}
for f in dawn rain waterline; do [ -f $O/world_${f}_v4art.png ] || cp -p $O/world_$f.png $O/world_${f}_v4art.png; done
export ART=v5 KV_PIC=v5_kv_213s Q1S_PIC=v5_q1s_211s SAMPLES=$S
for still in dawn dawn_near rain waterline; do
    $B -b --factory-startup -P $C/scripts/v5_world.py -- $O $still > tmp/still_$still.log 2>&1
    echo "$still $(date +%T)"
done
$M - << 'EOF'
from PIL import Image, ImageDraw
O = "cases/uraomote/renders/v5_world"
rows = []
for f in ("dawn", "rain", "waterline"):
    a = Image.open(f"{O}/world_{f}_v4art.png").convert("RGB").resize((960, 540), Image.LANCZOS)
    b = Image.open(f"{O}/world_{f}.png").convert("RGB").resize((960, 540), Image.LANCZOS)
    r = Image.new("RGB", (1930, 550), (16, 16, 18))
    r.paste(a, (0, 5)); r.paste(b, (970, 5))
    rows.append(r)
s = Image.new("RGB", (1930, 550 * len(rows) + 40), (16, 16, 18))
d = ImageDraw.Draw(s)
d.text((10, 10), "left: the v4 pictures cut out  |  right: pictures painted into the world's plates", fill=(230, 230, 230))
for k, r in enumerate(rows):
    s.paste(r, (0, 40 + 550 * k))
s.save(f"{O}/compare_v4art_v5art.jpg", quality=90)
print("compare", s.size)
EOF
