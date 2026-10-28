#!/bin/bash
# cases/uraomote/runs/patch.sh PASS SECTION FIRST_BAR LAST_BAR F0 F1 [SHEET=k] [WIDTH=1280] [SAMPLES=32]
# After a full pass, when one shot was fixed: delete its frames F0..F1 (frame numbers) from the pass's frames
# folder, render bars FIRST..LAST of SECTION again from HEAD, cut the film again and remake contact sheet k.
# Logs and a done flag in tmp/patchPASS/. Give the bar window a little slack on both sides: a frame the window
# misses stays deleted and the cut fills it with the frame before (and says so).
#   bash cases/uraomote/runs/patch.sh 9 P8 84.2 85.9 1560 1582 3
set -u
N=$1; SEC=$2; FIRST=$3; LAST=$4; F0=$5; F1=$6; K=${7:-0}; W=${8:-1280}; SM=${9:-32}
cd ${MAIN:-/root/autodl-tmp/svc-mv}
C=cases/uraomote
R=$C/renders/animatic_v4
B=${BLENDER:-/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender}
P=${PY:-/root/autodl-tmp/ComfyUI/venv/bin/python}
if [ "$W" = 1280 ]; then F=$R/frames; MP4=$R/animatic_v4.mp4; SH=$R/sheet_; else F=$R/frames_$W; MP4=$R/animatic_v4_$W.mp4; SH=$R/sheet${W}_; fi
mkdir -p tmp/patch$N
for f in $(seq $F0 $F1); do rm -f $F/$(printf "f_%05d.png" $f); done
WIDTH=$W SAMPLES=$SM ONLY=$SEC $B -b --factory-startup -P $C/scripts/animatic_v4.py -- $F $FIRST $LAST > tmp/patch$N/render.log 2>&1
echo "frames now $(ls $F | wc -l)" >> tmp/patch$N/render.log
$P scripts/cut.py $F $C/audio/urao_mix.m4a $MP4 12 > tmp/patch$N/cut.log 2>&1
$P scripts/sheet.py $F ${SH}$K.jpg 12 6 640 $((K * 432)) $((K * 432 + 431)) >> tmp/patch$N/cut.log 2>&1
touch tmp/patch$N/done
