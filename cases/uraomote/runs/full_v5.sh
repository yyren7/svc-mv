#!/bin/bash
# The v5 animatic, the whole film: frames, the cut with the song, contact sheets.
#   bash cases/uraomote/runs/full_v5.sh [WIDTH] [SAMPLES] [FPS]      (on the server; frames already there are kept)
# Blender runs one section at a time and starts again from the frames it has when it crashes (a pass died in the NVIDIA
# driver 29 minutes in, and the cut filled the missing 54 s with a held frame): no cut unless every frame is there.
cd "$(dirname "$(realpath "$0")")/../../.."
W=${1:-1280}
SMP=${2:-32}
RATE=${3:-12}
O=cases/uraomote/renders/animatic_v5
F=$O/frames_$W
[ "$RATE" = 12 ] || F=${F}_$RATE
P=/root/autodl-tmp/ComfyUI/venv/bin/python
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
L=tmp/full_v5_$W.log
mkdir -p $O $F
: > $L
want=$($P -c "import json; print(round(json.load(open('cases/uraomote/audio/urao_timing.json'))['duration'] * $RATE))")
for part in "-2 24" "24 35" "35 57" "57 83" "83 99" "99 120"; do
    for try in 1 2 3 4 5; do
        FPS=$RATE WIDTH=$W SAMPLES=$SMP $B -b --factory-startup -P cases/uraomote/scripts/animatic_v5.py -- $F $part >> $L 2>&1 \
            && break
        echo "bars $part: blender failed (try $try)" | tee -a $L
    done
done
n=$(ls $F | wc -l)
if [ "$n" -lt "$want" ]; then
    echo "full_v5 $W FAILED: $n of $want frames, no cut (see $L)" | tee -a $L
    exit 1
fi
OUT=$O/animatic_v5_$W.mp4
[ "$RATE" = 12 ] || OUT=$O/animatic_v5_${W}_$RATE.mp4
# the transitions go on the rendered frames, so they can be changed without rendering again
J=${F}_joined
$P scripts/joins.py $F $J cases/uraomote/scripts/joins_v5.py $RATE 2>&1 | tee -a $L
$P scripts/cut.py $J cases/uraomote/audio/urao_mix.m4a $OUT $RATE >> $L 2>&1
# one frame a second, 36 s a sheet
for k in $(seq 0 $(( (n - 1) / (36 * RATE) ))); do
    $P scripts/sheet.py $J $O/sheet${W}_$k.jpg $RATE 6 320 $((k * 36 * RATE)) $(((k + 1) * 36 * RATE - 1)) >> $L 2>&1
done
echo "full_v5 $W done $(date), $n frames" | tee -a $L
