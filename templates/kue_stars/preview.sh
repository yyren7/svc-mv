#!/bin/bash
# 模板的快速预览，在 AutoDL 上：960×540（HEIGHT=1080 出 1080p）、30 fps（隔一帧渲一帧）、8 采样，4 段同时渲；带左下角歌名、歌词和制作信息。
# 默认只出前 40 秒（约 1 分半），LEN=0 出整首；音频特征、plan.json 没有时先做（同 render.sh）。
#   bash templates/kue_stars/preview.sh cases/<歌>           -> <case>/renders/<歌>_preview_540p_40s.mp4
#   LEN=0 bash templates/kue_stars/preview.sh cases/<歌>     -> <case>/renders/<歌>_preview_540p.mp4
#   START=60 LEN=30 ...   从第 60 秒起的 30 秒（看副歌）
set -euo pipefail
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
LIBROSA_PY=/root/autodl-tmp/conda_envs/evalq/bin/python
T=templates/kue_stars
cd /root/autodl-tmp/svc-mv
export CASE=${1:?"用法：preview.sh cases/<歌>"}
export PYTHONPATH=/root/autodl-tmp/pv/pylib
R=$CASE/renders
P=$R/preview
START=${START:-0}
LEN=${LEN:-40}
mkdir -p $P $R/logs
rm -f $P/*

eval "$($PY $T/plan.py env $CASE)"
[ -f $CASE/audio/bands.npz ] || $LIBROSA_PY scripts/audio_bands.py "$MIX" "$VOCAL" $CASE/audio/bands.npz --fps 60 --bands 48
[ -f $CASE/plan.json ] || $PY $T/plan.py make $CASE
eval "$($PY $T/plan.py env $CASE)"
HEIGHT=${HEIGHT:-540}
export RES=$((HEIGHT * 100 / 2160))
OUT=$R/${NAME}_preview_${HEIGHT}p${TAG:+_$TAG}.mp4
[ "$LEN" -gt 0 ] && OUT=$R/${NAME}_preview_${HEIGHT}p_${START}s+${LEN}s${TAG:+_$TAG}.mp4

nice -n 19 $PY scripts/onepic_player.py $CASE/audio/bands.npz $R/player_p$HEIGHT --title "$TITLE" --sub "$SUB" \
    --fps 30 --height $HEIGHT --show $SHOW > $R/logs/player.log 2>&1 &
$B -b --factory-startup -P $T/pv.py -- build > $R/logs/build.log 2>&1
grep -E "camera out|star ring|galaxy" $R/logs/build.log || true
N=$($PY -c "import numpy as np; print(len(np.load('$CASE/audio/bands.npz')['loud']))")
F0=$((START * 60)); F1=$((N - 1))
[ "$LEN" -gt 0 ] && [ $((F0 + LEN * 60 - 1)) -lt $F1 ] && F1=$((F0 + LEN * 60 - 1))
step=$(( ((F1 - F0) / 4 + 2) / 2 * 2 ))       # 每段的起点取偶数，-j 2 才都落在偶数帧上
for k in 0 1 2 3; do
    a=$((F0 + k * step)); b=$((a + step - 1)); [ $k -eq 3 ] && b=$F1
    $B -b $R/scene.blend -P $T/pv.py -s $a -e $b -j 2 -a -- preview > $P/log_$k.txt 2>&1 &
done
wait

ARGS=()
[ -n "$LRC" ] && [ -f "$LRC" ] && ARGS+=(--lrc "$LRC")
[ -n "$TLRC" ] && [ -f "$TLRC" ] && ARGS+=(--tlrc "$TLRC")
[ -n "$CREDITS" ] && [ -f "$CREDITS" ] && ARGS+=(--credits "$CREDITS")
$PY scripts/lrc2ass.py $R/subs.ass "${ARGS[@]}" --offset "$LYRICS_OFFSET" --credits-at $CREDITS_AT --lift 150 \
    --res $((HEIGHT * 16 / 9)) $HEIGHT
$PY scripts/onepic_finish.py $P "$MIX" $OUT --ass $R/subs.ass --overlay $R/player_p$HEIGHT --crf 20 --preset fast \
    --fade-out $([ "$LEN" -gt 0 ] && echo 1 || echo 4) ${START:+--start $START}
echo "-> $OUT"
