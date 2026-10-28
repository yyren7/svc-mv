#!/bin/bash
# cases/uraomote/runs/full.sh PASS [WIDTH=1280] [SAMPLES=32]: a full pass of the v4 animatic on the GPU server:
# every frame, the cut with the song, six contact sheets (a frame a second, 36 s a sheet), a done flag.
# At 1280 px the outputs are renders/animatic_v4/{frames, animatic_v4.mp4, sheet_K.jpg}; at another width they
# carry it (frames_1920, animatic_v4_1920.mp4, sheet1920_K.jpg), so the 1280 cut stays. Logs and the flag in
# tmp/fullPASS/. Frames already there are skipped (restart.sh clears them). 1280/32 takes about 100 min alone on
# the 4090 D (~3.5 s a frame); 1920/48 about 5.5 h.
#   (nohup bash cases/uraomote/runs/full.sh 10 1920 48 > /dev/null 2>&1 < /dev/null &)
set -u
N=$1; W=${2:-1280}; SM=${3:-32}
cd ${MAIN:-/root/autodl-tmp/svc-mv}
C=cases/uraomote
R=$C/renders/animatic_v4
B=${BLENDER:-/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender}
P=${PY:-/root/autodl-tmp/ComfyUI/venv/bin/python}
if [ "$W" = 1280 ]; then F=$R/frames; MP4=$R/animatic_v4.mp4; SH=$R/sheet_; else F=$R/frames_$W; MP4=$R/animatic_v4_$W.mp4; SH=$R/sheet${W}_; fi
mkdir -p tmp/full$N
WIDTH=$W SAMPLES=$SM $B -b --factory-startup -P $C/scripts/animatic_v4.py -- $F > tmp/full$N/render.log 2>&1
$P scripts/cut.py $F $C/audio/urao_mix.m4a $MP4 12 > tmp/full$N/cut.log 2>&1
for k in 0 1 2 3 4 5; do
  $P scripts/sheet.py $F ${SH}$k.jpg 12 6 640 $((k * 432)) $((k * 432 + 431)) >> tmp/full$N/cut.log 2>&1
done
touch tmp/full$N/done
