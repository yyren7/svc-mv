#!/bin/bash
# scripts/queue.sh LIST: launch each line of LIST (the arguments of exp.sh: NAME SPEC "ENVS" FIRST LAST) when the
# GPU has room, under 13 GB in use so two more ~5.3 GB Blenders fit beside what runs, 100 s apart so their scene
# setups do not all land on the CPU at once. Lines appended to LIST while it runs are picked up. The same
# settings as exp.sh (MAIN, CASE, SCRIPT, ...) pass through the environment.
set -u
MAIN=${MAIN:-/root/autodl-tmp/svc-mv}
cd $MAIN
while read -r line; do
  [ -z "$line" ] && continue
  until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)" -lt 13000 ]; do sleep 15; done
  eval "(nohup bash scripts/exp.sh $line > /dev/null 2>&1 < /dev/null &)"
  echo "$(date +%H:%M:%S) launched $line"
  sleep 100
done < "$1"
