#!/bin/bash
# 快速预览，在 AutoDL 上：960×540、30 fps（隔一帧渲一帧）、8 采样，4 段同时渲；带歌词和制作信息。
# 默认只出前 40 秒（约 1 分半），LEN=0 出整首（约 8 分钟）；TAG 加在文件名后面，FX（见 pv.py）传给 Blender。
#   bash cases/kimishira/scripts/preview.sh                    -> renders/kimishira_preview_540p_40s.mp4
#   FX=bokeh,rim TAG=fx2 bash cases/kimishira/scripts/preview.sh  -> renders/kimishira_preview_540p_40s_fx2.mp4
#   LEN=0 bash cases/kimishira/scripts/preview.sh              -> renders/kimishira_preview_540p.mp4
set -euo pipefail
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
cd /root/autodl-tmp/svc-mv
C=cases/kimishira
# 三处歌名轮流出：开头竖排的大标题（pv.py 的 title()，0–11.6 秒）-> 左下角的歌名（前奏第一个重拍 15.3 秒淡入，
# 最后一句唱完后 320 秒淡出完；下面的进度条和时间一直在）-> 右下角的制作信息（尾奏的重拍 321.65 秒起）
SHOW="15.30 320"
CREDITS_AT="321.65 334"
R=$C/renders
P=$R/preview
LEN=${LEN:-40}
OUT=$R/kimishira_preview_540p${TAG:+_$TAG}.mp4
[ "$LEN" -gt 0 ] && OUT=$R/kimishira_preview_540p_${LEN}s${TAG:+_$TAG}.mp4
mkdir -p $P $R/logs
rm -f $P/*

# 左下角的歌名、进度条和时间（旋律盘是画面里月亮外圈的频谱）：透明 PNG 序列，和渲染同时画（吃 CPU，不占 GPU）
$PY scripts/onepic_player.py $C/audio/bands.npz $R/player_540 \
    --title "君の知らない物語" --sub "supercell · cover 旬夏" --fps 30 --height 540 --seconds $LEN --show $SHOW > $R/logs/player.log 2>&1 &
$B -b --factory-startup -P $C/scripts/pv.py -- build > $R/logs/build.log 2>&1
grep -E "camera out" $R/logs/build.log || true
F1=$(($($PY -c "import numpy as np; print(len(np.load('$C/audio/bands.npz')['loud']))") - 1))
[ "$LEN" -gt 0 ] && [ $((LEN * 60 - 1)) -lt $F1 ] && F1=$((LEN * 60 - 1))      # pv.py 是 60 fps
step=$(( (F1 / 4 + 2) / 2 * 2 ))       # 每段的起点取偶数，-j 2 才都落在偶数帧上
for k in 0 1 2 3; do
    a=$((k * step)); b=$((a + step - 1)); [ $k -eq 3 ] && b=$F1
    $B -b $R/scene.blend -P $C/scripts/pv.py -s $a -e $b -j 2 -a -- preview > $P/log_$k.txt 2>&1 &
done
wait          # Blender 的 4 段和左下角的 PNG 都画完

ARGS=()
[ -f $C/audio/lyrics.lrc ] && ARGS+=(--lrc $C/audio/lyrics.lrc)
[ -f $C/audio/lyrics_cn.lrc ] && ARGS+=(--tlrc $C/audio/lyrics_cn.lrc)
$PY scripts/lrc2ass.py $R/subs.ass "${ARGS[@]}" --offset "${LYRICS_OFFSET:-0.15}" --credits $C/credits.txt --credits-at $CREDITS_AT --lift 150
$PY scripts/onepic_finish.py $P $C/audio/kimishira_sakura_shunka_mix.wav $OUT \
    --ass $R/subs.ass --overlay $R/player_540 --crf 20 --preset fast --fade-out $([ "$LEN" -gt 0 ] && echo 1 || echo 4)
