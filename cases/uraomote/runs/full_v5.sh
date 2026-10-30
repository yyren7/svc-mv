#!/bin/bash
# The v5 animatic, the whole film: frames, the cut with the song, contact sheets.
#   bash cases/uraomote/runs/full_v5.sh [WIDTH] [SAMPLES]      (on the server; frames already there are kept)
cd "$(dirname "$(realpath "$0")")/../../.."
W=${1:-1280}
SMP=${2:-32}
O=cases/uraomote/renders/animatic_v5
P=/root/autodl-tmp/ComfyUI/venv/bin/python
mkdir -p $O
WIDTH=$W SAMPLES=$SMP /root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender -b --factory-startup \
    -P cases/uraomote/scripts/animatic_v5.py -- $O/frames_$W > tmp/full_v5_$W.log 2>&1
$P scripts/cut.py $O/frames_$W cases/uraomote/audio/urao_mix.m4a $O/animatic_v5_$W.mp4 12 >> tmp/full_v5_$W.log 2>&1
n=$(ls $O/frames_$W | wc -l)
for k in 0 1 2 3 4 5; do
    $P scripts/sheet.py $O/frames_$W $O/sheet${W}_$k.jpg 12 6 320 $((k * 436)) $((k * 436 + 435)) >> tmp/full_v5_$W.log 2>&1
done
echo "full_v5 $W done $(date), $n frames" | tee -a tmp/full_v5_$W.log
