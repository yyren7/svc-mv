#!/bin/bash
# cases/uraomote/jobs/exp.sh NAME SPEC|- "ENV=.. ENV=.." FIRST LAST
# One side-by-side experiment on the server: a git worktree of HEAD at /root/autodl-tmp/exp/NAME with the
# untracked resources (art, audio, renders, the repo's top-level data folders) linked in from the main checkout,
# the substitutions of SPEC (json: [[file, old, new], ...], see patch.py) applied to it, the frames the
# environment asks for rendered to NAME/tmp/out/frames, a contact sheet and full-frame jpgs beside them, then a
# done flag. Several run beside each other and beside a film pass on the one GPU (each Blender takes ~5.3 GB of
# the 24); queue.sh launches a list of them as memory allows.
set -u
NAME=$1; SPEC=$2; ENVS=$3; FIRST=${4:-0}; LAST=${5:-200}
MAIN=/root/autodl-tmp/svc-mv
W=/root/autodl-tmp/exp/$NAME
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
P=/root/autodl-tmp/ComfyUI/venv/bin/python
J=$MAIN/cases/uraomote/jobs
cd $MAIN
git worktree remove --force $W 2>/dev/null; rm -rf $W; git worktree prune
git worktree add -q --detach $W HEAD
mkdir -p $W/tmp/out
for d in $(ls $MAIN); do [ -e "$W/$d" ] || ln -s "$MAIN/$d" "$W/$d"; done
for d in art audio renders; do [ -e "$W/cases/uraomote/$d" ] || ln -s "$MAIN/cases/uraomote/$d" "$W/cases/uraomote/$d"; done
if [ "$SPEC" != "-" ]; then
  $P $J/patch.py $W $SPEC > $W/tmp/out/patch.log 2>&1 || { echo "patch failed"; cat $W/tmp/out/patch.log; touch $W/tmp/out/done; exit 1; }
fi
cd $W
env $ENVS $B -b --factory-startup -P cases/uraomote/scripts/animatic_v4.py -- $W/tmp/out/frames $FIRST $LAST > $W/tmp/out/a.log 2>&1
$P cases/uraomote/scripts/sheet.py $W/tmp/out/frames $W/tmp/out/sheet.jpg 1 6 640 > $W/tmp/out/s.log 2>&1
$P $J/grab.py $W/tmp/out/frames $W/tmp/out/full $(ls $W/tmp/out/frames | sed "s/f_0*\([0-9]*\).png/\1/" | tr "\n" " ") > /dev/null 2>&1
touch $W/tmp/out/done
