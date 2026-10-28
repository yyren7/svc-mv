#!/bin/bash
# cases/uraomote/runs/restart.sh PASS [WIDTH=1280] [SAMPLES=32]: stop whatever Blender and full.sh still run for
# this pass, clear its frames, start it again. Run it as a script on the server (`bash cases/uraomote/runs/restart.sh 9`),
# never as an inline ssh command: a kill pattern that also appears in the ssh command line kills the ssh shell
# itself (it happened three times).
set -u
N=$1; W=${2:-1280}; SM=${3:-32}
cd ${MAIN:-/root/autodl-tmp/svc-mv}
R=cases/uraomote/renders/animatic_v4
if [ "$W" = 1280 ]; then F=$R/frames; else F=$R/frames_$W; fi
for p in $(ps -eo pid,cmd | grep -E "blender -b .*$F( |$)|bash cases/uraomote/runs/full.sh $N( |$)" | grep -v grep | awk '{print $1}'); do
  echo "kill $p"; kill $p
done
sleep 3
echo "left: $(ps -eo pid,cmd | grep -E "blender -b .*$F( |$)" | grep -v grep | wc -l)"
rm -rf $F tmp/full$N
mkdir -p tmp/full$N
(nohup bash cases/uraomote/runs/full.sh $N $W $SM > /dev/null 2>&1 < /dev/null &)
echo "started pass $N at $W px / $SM samples, $(date)"
