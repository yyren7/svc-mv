#!/bin/bash
# 看人物各部位怎么动，在 AutoDL 上：重算权重图（case 的 rig_paint/ 里有手改的就用它）-> 搭一份 1080p 的场景
# -> 每个部位渲一段只有它动的小样（pv.py 的 review：镜头定住、只渲插画几层）-> 每段拼成三栏：
#    渲出来的画面 | 这个部位的热力图 | 每个像素动了多少（和都不动的那一帧相减，放大 6 倍），配上那一段的歌。
#   bash cases/kimishira/scripts/rig_review.sh [起始秒 70] [秒数 10] [部位 ...]   # 部位默认 hair tail dress breath mouth
#   SKIP_RIG=1 不重算权重图，SKIP_BUILD=1 不重搭场景（只换了时间段、部位时）
# 部位：hair tail ear dress mouth breath，逗号连起来是一起动（hair,tail）。
# 结果在 renders/rig_review/：<部位>.mp4；maps/ 是权重图：<部位>.png 灰度（白 = 动满，黑 = 不动），改好放进
# case 的 rig_paint/ 再跑一遍；<部位>_heat.png 热力图；ref_char.png 同尺寸的人物，画图时垫在下面对位置。
set -euo pipefail
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
PY=/root/autodl-tmp/ComfyUI/venv/bin/python
export PYTHONPATH=/root/autodl-tmp/pv/pylib
cd /root/autodl-tmp/svc-mv
C=cases/kimishira
R=$C/renders
O=$R/rig_review
BL=$R/rig_review.blend
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
T0=${1:-70}
LEN=${2:-10}
PARTS="${*:3}"
PARTS=${PARTS:-hair tail dress breath mouth}
F0=$((T0 * 60))
F1=$((F0 + LEN * 60 - 1))
mkdir -p $O $R/logs

if [ -z "${SKIP_RIG:-}" ]; then
    $PY scripts/onepic_prep.py rig $C/art/prep/layer_char.png $C/rig.json $C/art/prep > $R/logs/rig.log 2>&1
fi
rm -rf $O/maps && cp -r $C/art/prep/rig_maps $O/maps
if [ -z "${SKIP_BUILD:-}" ]; then
    BLEND=$BL RES=50 $B -b --factory-startup -P $C/scripts/pv.py -- build > $R/logs/rig_review_build.log 2>&1
fi

# 都不动的那一帧，和每个部位只有它动的一段，同时渲
rm -rf $R/clips/rr_*
$B -b $BL -P $C/scripts/pv.py -s $F0 -e $F0 -a -- review none $F0 rr_rest > $R/logs/rr_rest.log 2>&1 &
for p in $PARTS; do
    $B -b $BL -P $C/scripts/pv.py -s $F0 -e $F1 -j 2 -a -- review $p $F0 rr_$p > $R/logs/rr_$p.log 2>&1 &
done
wait
REST=$(ls $R/clips/rr_rest/*.png | head -1)

# 三栏：人物那一块（1160×1020）各缩到 0.9
CROP="crop=1160:1020:660:40,scale=1044:918"
label() { echo "drawtext=fontfile=$FONT:text='$1':x=24:y=18:fontsize=34:fontcolor=white:borderw=3"; }
for p in $PARTS; do
    heat=$O/maps/${p%%,*}_heat.png
    ffmpeg -v error -y -framerate 30 -pattern_type glob -i "$R/clips/rr_$p/f_*.png" -loop 1 -i $REST -loop 1 -i $heat \
        -ss $T0 -t $LEN -i $C/audio/kimishira_sakura_shunka_mix.wav -filter_complex "
        [0:v]format=gbrp,split[v0][v1];
        [1:v]format=gbrp[r];
        [v0]$CROP,$(label "只有 ${p//,/+} 在动")[a];
        [v1][r]blend=all_mode=difference:shortest=1,lutrgb=r='min(255,val*6)':g='min(255,val*6)':b='min(255,val*6)',$CROP,$(label '动了多少（×6）')[d];
        [2:v]format=gbrp,$CROP,$(label "${p%%,*} 的热力图")[h];
        [a][h][d]hstack=inputs=3:shortest=1,format=yuv420p[v]" \
        -map "[v]" -map 3:a -shortest -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k $O/${p//,/+}.mp4
    echo "$O/${p//,/+}.mp4"
done
