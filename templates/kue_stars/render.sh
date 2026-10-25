#!/bin/bash
# 模板的成片，在 AutoDL 上：音频特征（没有就算）-> 编排（没有 plan.json 就排）-> 搭场景 -> 每 CHUNK 帧一段、N 个 Blender
# 同时渲（共用 4090 D）-> 左下角的歌名进度条、歌词、制作信息 -> 成片 <case>/renders/<歌>_pv_<高>p.mp4。
#   bash templates/kue_stars/render.sh cases/<歌> [N=4] [起始帧 结束帧]   # 给了帧范围就只渲那一段（试渲用）
#   RESUME=1 ...        不重建场景，跳过已完成的段（中途断了）
#   SKIP_RENDER=1 ...   只重做字幕和成片（改了歌词、制作信息、歌名时）
#   HEIGHT=2160 ...     4K60（默认 1080p60）
# 4 个进程时 18 核的 CPU 配额就满了；4K 时一个进程约 3.4 GB 显存、9.5 GB 内存，N=6 会被 OOM 杀掉。
set -euo pipefail
export B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
LIBROSA_PY=/root/autodl-tmp/conda_envs/evalq/bin/python
T=templates/kue_stars
cd /root/autodl-tmp/svc-mv
export CASE=${1:?"用法：render.sh cases/<歌> [N] [起始帧 结束帧]"}
export PYTHONPATH=/root/autodl-tmp/pv/pylib
export R=$CASE/renders
N=${2:-4}
HEIGHT=${HEIGHT:-1080}
export RES=$((HEIGHT * 100 / 2160))
mkdir -p $R/chunks $R/logs

eval "$($PY $T/plan.py env $CASE)"
if [ ! -f $CASE/audio/bands.npz ]; then
    $LIBROSA_PY scripts/audio_bands.py "$MIX" "$VOCAL" $CASE/audio/bands.npz --fps 60 --bands 48
fi
[ -f $CASE/plan.json ] || $PY $T/plan.py make $CASE
eval "$($PY $T/plan.py env $CASE)"
P=$R/player_$HEIGHT

if [ -n "${RESUME:-}" ] && [ -f $P/region.json ]; then
    PLAYER=
else
    nice -n 19 $PY scripts/onepic_player.py $CASE/audio/bands.npz $P --title "$TITLE" --sub "$SUB" \
        --fps 60 --height $HEIGHT --show $SHOW > $R/logs/player.log 2>&1 &
    PLAYER=$!
fi

if [ -z "${SKIP_RENDER:-}" ]; then
    if [ -z "${RESUME:-}" ]; then
        $B -b --factory-startup -P $T/pv.py -- build > $R/logs/build.log 2>&1
        rm -f $R/chunks/*
    fi
    export F1=${4:-$(($($PY -c "import numpy as np; print(len(np.load('$CASE/audio/bands.npz')['loud']))") - 1))}
    export SIZE=${CHUNK:-600}
    seq ${3:-0} $SIZE $F1 | xargs -P $N -I{} bash -c '
        a={}; b=$((a + SIZE - 1)); [ $b -gt $F1 ] && b=$F1
        name=$(printf "c_%05d-%05d" $a $b)
        [ -f $R/chunks/$name.done ] && exit 0
        rm -f $R/chunks/$name.mp4
        if $B -b $R/scene.blend -s $a -e $b -a > $R/logs/$name.log 2>&1; then
            touch $R/chunks/$name.done
        else
            echo "failed: $name"
        fi' || true
    todo=$(for a in $(seq ${3:-0} $SIZE $F1); do b=$((a + SIZE - 1)); [ $b -gt $F1 ] && b=$F1
           [ -f $R/chunks/$(printf "c_%05d-%05d" $a $b).done ] || echo $a; done)
    if [ -n "$todo" ]; then
        echo "unfinished chunks start at: $todo -- run again with RESUME=1"
        exit 1
    fi
fi

[ -n "$PLAYER" ] && wait $PLAYER
ARGS=()
[ -n "$LRC" ] && [ -f "$LRC" ] && ARGS+=(--lrc "$LRC")
[ -n "$TLRC" ] && [ -f "$TLRC" ] && ARGS+=(--tlrc "$TLRC")
[ -n "$CREDITS" ] && [ -f "$CREDITS" ] && ARGS+=(--credits "$CREDITS")
$PY scripts/lrc2ass.py $R/subs.ass "${ARGS[@]}" --offset "$LYRICS_OFFSET" --credits-at $CREDITS_AT --lift 150 \
    --res $((HEIGHT * 16 / 9)) $HEIGHT
$PY scripts/onepic_finish.py $R/chunks "$MIX" $R/${NAME}_pv_${HEIGHT}p.mp4 --ass $R/subs.ass --overlay $P
touch $R/render_done
