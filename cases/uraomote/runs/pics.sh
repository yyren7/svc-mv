#!/bin/bash
# After a picture round on ComfyUI: the pictures into art/v5, Qwen's green specks painted out, her cut out of each
# (anime-seg, looked for where the plate's mannequin is), the depth and parts maps (maps.py), the flat map from each
# picture's plate (plate_maps.py), and a contact sheet of the round.
#   bash cases/uraomote/runs/pics.sh <sheet name> <picture name>...      (on the server, ComfyUI stopped)
# A picture's plate is the part of its name between v5_ and the seed: v5_kv_211r -> kv, v5_a1_213sp -> a1.
set -e
cd "$(dirname "$(realpath "$0")")/../../.."
C=cases/uraomote
ART=$C/art/v5
P=/root/autodl-tmp/ComfyUI/venv/bin/python
M=/root/miniconda3/bin/python
sheet=$1
shift
mkdir -p $ART/figures $ART/maps
for n in "$@"; do cp -pn /root/autodl-tmp/ComfyUI/output/${n}_00001_.png $ART/ || true; done
PYTHONPATH=/root/autodl-tmp/pv/pylib $P scripts/despeckle.py $ART "$@"
PLATES=$C/renders/v5_plates PYTHONPATH=/root/autodl-tmp/pv/pylib $P scripts/figures.py $ART "$@"
DEPTH_MODEL=tmp/hf/Depth-Anything-V2-Small-hf SEG_MODEL=tmp/hf/clipseg-rd64-refined $P -I scripts/maps.py $ART "$@"
pairs=()
for n in "$@"; do p=${n#v5_}; p=${p%%_*}; [ "$p" = a5o ] && p=a5; pairs+=("$p=$n"); done   # A5 open-eyed: A5's plate
$M scripts/plate_maps.py $C/renders/v5_plates $ART "${pairs[@]}"
files=()
for n in "$@"; do files+=("$ART/${n}_00001_.png"); done
$M scripts/art_sheet.py $ART/_sheet_$sheet.png 4 "${files[@]}"
checks=()
for n in "$@"; do checks+=("$ART/figures/${n}_check.jpg"); done
$M scripts/art_sheet.py $ART/_sheet_${sheet}_figures.png 4 "${checks[@]}"
echo "done: $ART/_sheet_$sheet.png"
