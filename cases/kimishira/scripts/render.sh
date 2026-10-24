#!/bin/bash
# 君の知らない物語 一图流 PV，在 AutoDL 上：搭场景 -> 切成每段 CHUNK 帧的小段，最多 N 个 Blender 同时渲（共用 4090 D）
# -> 字幕 -> 合成成片。每段渲完留一个 .done，中途断了用 RESUME=1 重跑，只补没完成的段。
#   bash cases/kimishira/scripts/render.sh [N=4] [起始帧 结束帧]     # 给了帧范围就只渲那一段（试渲用）
#   RESUME=1 bash cases/kimishira/scripts/render.sh                  # 不重建场景，跳过已完成的段
#   SKIP_RENDER=1 bash cases/kimishira/scripts/render.sh             # 只重做字幕和成片（改了歌词、制作信息时）
# 一个 Blender 进程约占 3.4 GB 显存、9.5 GB 内存；容器内存上限 64 GB，N=6 时会被 OOM 杀掉。
# 4 个进程 GPU 就满了，再多也不会更快。
# 歌词：把 LRC 放在 audio/lyrics.lrc（译文可以在同一个文件里同时间戳的第二行，或 audio/lyrics_cn.lrc）。
set -euo pipefail
export B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
cd /root/autodl-tmp/svc-mv
C=cases/kimishira
# 三处歌名轮流出：开头竖排的大标题（pv.py 的 title()，0–11.6 秒）-> 左下角的歌名栏（前奏第一个重拍 15.3 秒淡入，
# 最后一句唱完后 320 秒淡出完）-> 右下角的制作信息（尾奏的重拍 321.65 秒起）
SHOW="15.30 320"
CREDITS_AT="321.65 334"
export R=$C/renders
N=${1:-4}
mkdir -p $R/chunks $R/logs

# 左下角的歌名、进度条和时间（旋律盘是画面里月亮外圈的频谱）：透明 PNG 序列，和渲染同时画（吃 CPU，不占 GPU）
$PY scripts/onepic_player.py $C/audio/bands.npz $R/player_2160 \
    --title "君の知らない物語" --sub "supercell · cover 旬夏" --fps 60 --height 2160 --show $SHOW > $R/logs/player.log 2>&1 &
PLAYER=$!

if [ -z "${SKIP_RENDER:-}" ]; then
    if [ -z "${RESUME:-}" ]; then
        $B -b --factory-startup -P $C/scripts/pv.py -- build > $R/logs/build.log 2>&1
        rm -f $R/chunks/*
    fi
    export F1=${3:-$(($($PY -c "import numpy as np; print(len(np.load('$C/audio/bands.npz')['loud']))") - 1))}
    export SIZE=${CHUNK:-600}
    seq ${2:-0} $SIZE $F1 | xargs -P $N -I{} bash -c '
        a={}; b=$((a + SIZE - 1)); [ $b -gt $F1 ] && b=$F1
        name=$(printf "c_%05d-%05d" $a $b)
        [ -f $R/chunks/$name.done ] && exit 0
        rm -f $R/chunks/$name.mp4
        if $B -b $R/scene.blend -s $a -e $b -a > $R/logs/$name.log 2>&1; then
            touch $R/chunks/$name.done
        else
            echo "failed: $name"
        fi' || true
    todo=$(for a in $(seq ${2:-0} $SIZE $F1); do b=$((a + SIZE - 1)); [ $b -gt $F1 ] && b=$F1
           [ -f $R/chunks/$(printf "c_%05d-%05d" $a $b).done ] || echo $a; done)
    if [ -n "$todo" ]; then
        echo "unfinished chunks start at: $todo -- run again with RESUME=1"
        exit 1
    fi
fi

wait $PLAYER
ARGS=()
[ -f $C/audio/lyrics.lrc ] && ARGS+=(--lrc $C/audio/lyrics.lrc)
[ -f $C/audio/lyrics_cn.lrc ] && ARGS+=(--tlrc $C/audio/lyrics_cn.lrc)
$PY scripts/lrc2ass.py $R/subs.ass "${ARGS[@]}" --offset "${LYRICS_OFFSET:-0.15}" --credits $C/credits.txt --credits-at $CREDITS_AT --lift 150
$PY scripts/onepic_finish.py $R/chunks $C/audio/kimishira_sakura_shunka_mix.wav $R/kimishira_pv.mp4 --ass $R/subs.ass --overlay $R/player_2160
touch $R/render_done
