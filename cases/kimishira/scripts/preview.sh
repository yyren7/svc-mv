#!/bin/bash
# 快速预览，在 AutoDL 上：960×540、30 fps（隔一帧渲一帧）、8 采样，4 段同时渲，几分钟出整首；带歌词和制作信息。
#   bash cases/kimishira/scripts/preview.sh      -> renders/kimishira_preview_540p.mp4
set -euo pipefail
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
cd /root/autodl-tmp/svc-mv
C=cases/kimishira
R=$C/renders
P=$R/preview
mkdir -p $P $R/logs
rm -f $P/*

# 左下角的歌名、进度条和时间（旋律盘是画面里月亮外圈的频谱）：透明 PNG 序列，和渲染同时画（吃 CPU，不占 GPU）
$PY scripts/onepic_player.py $C/audio/bands.npz $R/player_540 \
    --title "君の知らない物語" --sub "supercell · cover 旬夏" --fps 30 --height 540 > $R/logs/player.log 2>&1 &
$B -b --factory-startup -P $C/scripts/pv.py -- build > $R/logs/build.log 2>&1
grep -E "camera out" $R/logs/build.log || true
F1=$(($($PY -c "import numpy as np; print(len(np.load('$C/audio/bands.npz')['loud']))") - 1))
step=$(( (F1 / 4 + 2) / 2 * 2 ))       # 每段的起点取偶数，-j 2 才都落在偶数帧上
for k in 0 1 2 3; do
    a=$((k * step)); b=$((a + step - 1)); [ $k -eq 3 ] && b=$F1
    $B -b $R/scene.blend -P $C/scripts/pv.py -s $a -e $b -j 2 -a -- preview > $P/log_$k.txt 2>&1 &
done
wait          # Blender 的 4 段和左下角的 PNG 都画完

ARGS=()
[ -f $C/audio/lyrics.lrc ] && ARGS+=(--lrc $C/audio/lyrics.lrc)
[ -f $C/audio/lyrics_cn.lrc ] && ARGS+=(--tlrc $C/audio/lyrics_cn.lrc)
$PY scripts/lrc2ass.py $R/subs.ass "${ARGS[@]}" --offset "${LYRICS_OFFSET:-0.15}" --credits $C/credits.txt --credits-at 322 334 --lift 150
$PY scripts/onepic_finish.py $P $C/audio/kimishira_sakura_shunka_mix.wav $R/kimishira_preview_540p.mp4 \
    --ass $R/subs.ass --overlay $R/player_540 --crf 20 --preset fast
