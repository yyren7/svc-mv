#!/bin/bash
# scripts/exp.sh NAME SPEC|- "ENV=.. ENV=.." [FIRST_BAR] [LAST_BAR]
# One side-by-side experiment on the GPU server: a git worktree of HEAD at $EXP/NAME with the untracked resources
# (the case's art, audio, renders and the repo's top-level data folders) linked in from the main checkout, the
# substitutions of SPEC (json: [[file, old, new], ...], see patch.py; "-" for none: a dry run of HEAD) applied to
# it, the frames the environment asks for (WIDTH, SAMPLES, AT, ONLY, DEVICE...) rendered to NAME/tmp/out/frames,
# a contact sheet and full-frame jpgs beside them, then a done flag. Several run beside each other and beside a
# film pass on the one GPU (each Blender takes ~5.3 GB of the 24); queue.sh launches a list of them as memory
# allows. Settings, with their defaults for the uraomote case on AutoDL:
#   MAIN=/root/autodl-tmp/svc-mv            the checkout        EXP=/root/autodl-tmp/exp   where worktrees go
#   CASE=cases/uraomote                     the case            SCRIPT=$CASE/scripts/animatic_v4.py  its shots
#   BLENDER=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender   PY=/root/autodl-tmp/ComfyUI/venv/bin/python
set -u
NAME=$1; SPEC=$2; ENVS=$3; FIRST=${4:-0}; LAST=${5:-200}
MAIN=${MAIN:-/root/autodl-tmp/svc-mv}
EXP=${EXP:-/root/autodl-tmp/exp}
CASE=${CASE:-cases/uraomote}
SCRIPT=${SCRIPT:-$CASE/scripts/animatic_v4.py}
B=${BLENDER:-/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender}
P=${PY:-/root/autodl-tmp/ComfyUI/venv/bin/python}
W=$EXP/$NAME
cd $MAIN
git worktree remove --force $W 2>/dev/null; rm -rf $W; git worktree prune
git worktree add -q --detach $W HEAD
mkdir -p $W/tmp/out
for d in $(ls $MAIN); do [ -e "$W/$d" ] || ln -s "$MAIN/$d" "$W/$d"; done
for d in art audio renders; do [ -e "$W/$CASE/$d" ] || ln -s "$MAIN/$CASE/$d" "$W/$CASE/$d"; done
if [ "$SPEC" != "-" ]; then
  $P $MAIN/scripts/patch.py $W $SPEC > $W/tmp/out/patch.log 2>&1 || { echo "patch failed"; cat $W/tmp/out/patch.log; touch $W/tmp/out/done; exit 1; }
fi
cd $W
env $ENVS $B -b --factory-startup -P $SCRIPT -- $W/tmp/out/frames $FIRST $LAST > $W/tmp/out/a.log 2>&1
$P scripts/sheet.py $W/tmp/out/frames $W/tmp/out/sheet.jpg 1 6 640 > $W/tmp/out/s.log 2>&1
$P scripts/grab.py $W/tmp/out/frames $W/tmp/out/full $(ls $W/tmp/out/frames | sed "s/f_0*\([0-9]*\).png/\1/" | tr "\n" " ") > /dev/null 2>&1
touch $W/tmp/out/done
