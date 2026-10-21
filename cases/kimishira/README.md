# 君の知らない物語 · 一图流 PV

一张插画、一首歌的"一图流"鉴赏 PV，给 B 站。画面全在 Blender 里做：插画按深度拆成几层摆成 2.5D 场景，
镜头始终看整张画，只缓慢平移，前后景有真实的视差；人物的头发、尾巴、耳朵、裙摆跟着风摆，嘴跟着歌声张合；
花瓣、光点、流星、星星闪烁跟着歌走；月亮外圈的频谱就是"旋律盘"，低音来时像心跳一样鼓起来。

| | |
|---|---|
| 歌 | supercell「君の知らない物語」，旬夏的 AI 翻唱（DDSP-SVC），`audio/kimishira_sakura_shunka_mix.wav` |
| 画 | kue 的星空花田插画，4K 精修版 `characters/kue/art/kue_pv_stars_103_4k_00001_.png`；分层（远景 / 中景 / 近景 / 人物，被挡住的部分 Qwen 补画）在 `characters/kue/art/layers/stars_103/` |
| 预览 | `renders/kimishira_preview_540p.mp4`：960×540、30 fps、8 采样，整首几分钟出完 |
| 成片 | `renders/kimishira_pv.mp4`：3840×2160、60 fps、H.264 High + AAC 320k，5 分 37 秒 |
| 封面 | `renders/cover_16x9.jpg`（1920×1080）、`renders/cover_4x3.jpg`（手机端裁切） |

通用的做法和踩过的坑在 [docs/onepic.md](../../docs/onepic.md)，这里只记这首歌的部分。

## 段落

约 110 BPM，一小节 2.18 秒；段落按小节的响度和主唱音高分（副歌唱得高）。表在 `scripts/pv.py` 的 `SECTIONS`，
每段给花瓣、光点、月亮频谱环、光束的开度和"能量"（管风速、摆动幅度、发光）。

| 时间 | 段落 | 镜头（一条不断开的路径，`camera_keys()`） |
|---|---|---|
| 0:00 | 开头清唱 | 整张画，月亮旁边竖排的标题「君の知らない物語」一个字一个字浮现；歌名出来时焦点拉到镜头前的标题上，人物和背景一起虚下去 |
| 0:09 | 乐队进来 | 标题淡出，焦点拉回她脸上，整张画清楚起来 |
| 0:15 | 前奏、主歌 1 | 左右慢慢挪 |
| 1:06 | 副歌 1 | 机位升起一点 |
| 1:43 | 主歌 2 | 左右慢慢挪 |
| 2:16 | 副歌 2 | 升起一点 |
| 3:23 | 间奏 | 往左上的星空和月亮那边偏一点，流星雨 |
| 3:47 | C 段 | 回到正中 |
| 4:11 | 最后的副歌 | 升起、左右挪，花瓣最多 |
| 5:22 | 尾奏 | 往月亮那边漂一点，淡出；右下角制作信息 |

镜头不硬切、不推近人物：始终是整张画，放大只在 1.04–1.10 倍之间，画面中心只在正中附近漂。
动感来自机位的平移（最多约 1.2 厘米）带出的前后景视差，关键帧之间用单调三次插值（速度连续、不冲过头）。

开头的虚化是真的焦外：标题放在镜头前 0.5 米（`TITLE_Y`，字按距离缩小，画面上一样大），0.8–2.6 秒焦点从她脸上
拉到标题上，景深开到画面宽的 1.4%；8.75–12 秒拉回来。对焦写成只有 `F()` 的关键帧，单独插值，镜头不会因此停顿。

## 人物的摆动

`rig.json` 写各部位的大致位置（头中心、嘴、两只耳朵的框、尾巴的根 / 拱心 / 尖、裙摆的范围），
`onepic_prep.py rig` 按颜色和位置算成权重图，Blender 里 `onepic.deform()` 用 Geometry Nodes 让人物网格局部变形：

- 头发、丝带：离头越远动得越多，从发根往下传的波；副歌风大摆得大（4K 下发梢约 15–27 像素）
- 尾巴：绕根部转，越往尖转得越多
- 耳朵：隔 5–13 秒抖一下
- 裙摆：横向的慢波
- 嘴：跟主唱的快包络上下伸缩（−28%…+18%），嘴角横向跟一点；不唱时合一点
- 呼吸：整个人极轻地起伏

脸、手、话筒、话筒线、颈带在头发、裙摆、嘴三种权重里都是 0，不会变形（话筒线垂在裙子上，跟着裙摆摆会弯；
话筒头挨着下巴，跟着嘴伸缩会歪）。话筒和线另外在 `rig.json` 的 `rigid` 里画成折线（带半宽）：线到下面变细变浅，
按颜色抓不全。两只袖子是半透明的，后面透出头发，按颜色分不开：
`rig.json` 的 `sleeves` 各画一个多边形，里面头发的权重是 0，出了袖子约 2.5% 画面高才慢慢放开，
头发摆的时候不会带着上臂的袖子一起动。

分层抠出来的人物，尾巴和右边几缕头发是半透明的（尾巴约 0.9，右边那截 0.6–0.85），渲染时后面的花透出来，
看着像尾巴糊了。`rig` 最后把人物内部的 alpha 补满（写 `art/prep/layer_char_solid.png`），离边缘几个像素的抗锯齿边和细发丝不动；
`rig.json` 的 `translucent` 是本来就该透的地方（右下透出花的裙边），也不动。

## 旋律盘

旋律盘就是画里的月亮：外圈 96 根跟着频谱跳的柱子（低频在下、高频在上，左右对称），低音来时整圈像心跳一样
鼓起来（`heart` 列，半径最多大 8%），月晕跟着亮；月光光束只从月亮和这圈频谱发出，跟心跳一起亮
（`BEAM_GAIN`、`BEAM_MASK`）。镜头始终看整张画，月亮一直在画面里。

左下角只留一条窄的歌名、"supercell · cover 旬夏"、进度条和时间（`scripts/onepic_player.py` 不给 `--art`），
逐帧画成透明 PNG，最后叠上去；歌词在它上面。

一开始左下角也做过一个带唱片的旋律盘（`--art` 给图就有），和月亮外圈的频谱同时跳，两个盘抢眼，就只留了月亮。

## 歌词

网易云音乐的原曲（id 825646）的 LRC 和中文翻译，存在 `audio/lyrics.lrc`、`audio/lyrics_cn.lrc`（不进仓库）。
和主唱的起音逐句对过：整首没有漂移，句子比开唱早约 0.4 秒出，所以整体推后 0.15 秒（`LYRICS_OFFSET`）。
结尾的制作信息在 `credits.txt`。改歌词或制作信息只需重做成片（`SKIP_RENDER=1`），不用重渲染。

## 怎么跑

全部在 AutoDL 上（`ssh autodl`），本地只写脚本、同步、看结果。服务器上的仓库副本在 `/root/autodl-tmp/svc-mv`，用 scp 同步。

```sh
PY=/root/autodl-tmp/ComfyUI/venv/bin/python; export PYTHONPATH=/root/autodl-tmp/pv/pylib
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
C=cases/kimishira

# 一次性：环境（依赖装进单独的 pylib，模型下到 /root/autodl-tmp/pv/models）
bash scripts/onepic_setup.sh
# 逐帧音频特征（evalq 环境里有 librosa）
/root/autodl-tmp/conda_envs/evalq/bin/python scripts/audio_bands.py $C/audio/kimishira_sakura_shunka_mix.wav \
    $C/audio/kimishira_lead.flac $C/audio/bands.npz --fps 60 --bands 48
# 插画 -> 深度、天空、星点、月亮；接入分层（每层 2 倍放大）；人物各部位的权重
$PY scripts/onepic_prep.py $C/art/kue_pv_stars_103_4k_00001_.png $C/art/prep
UPSCALER2=/root/autodl-tmp/ComfyUI/models/upscale_models/2x-AnimeSharpV4_RCAN.safetensors \
    $PY scripts/onepic_prep.py layers /root/autodl-tmp/layers/kue_stars_103 $C/art/prep
$PY scripts/onepic_prep.py rig /root/autodl-tmp/layers/kue_stars_103/char.png $C/rig.json $C/art/prep

# 快速预览（约 10 分钟）-> renders/kimishira_preview_540p.mp4
bash $C/scripts/preview.sh
# 几秒的静帧（RES=50 是 1080p）
$B -b --factory-startup -P $C/scripts/pv.py -- build
RES=50 $B -b $C/renders/scene.blend -P $C/scripts/pv.py -- stills 3 20 35 210
# 4K60 成片（4 个进程两个多小时，再加约 40 分钟编码；断了用 RESUME=1 续）
bash $C/scripts/render.sh 4
# 封面：副歌里一张 4K 静帧（月亮的频谱和光束都亮着），左边加竖排大标题
RES=100 $B -b $C/renders/scene.blend -P $C/scripts/pv.py -- stills 70
$PY $C/scripts/cover.py $C/renders/stills/t_070.00.png $C/renders/cover
```

## 投稿

- 分区：音乐 → 翻唱。类型选"自制"，在简介里写明原曲。
- 作者声明勾选"使用 AI 合成技术"：歌声是 DDSP-SVC 转换的，插画是 AI 画的。
- 插画和放大、深度模型都是非商用许可（见 [docs/comfyui.md](../../docs/comfyui.md) 和 [docs/onepic.md](../../docs/onepic.md)），不开充电、不接商单的普通投稿没问题。
- 上传 `renders/kimishira_pv.mp4` 原文件即可（B 站会按 4K 转码）。

草稿（按需改）：

- 标题：`【旬夏】君の知らない物語【AI翻唱 · 一图流 4K60】`
- 简介：
  ```
  原曲：supercell「君の知らない物語」（《化物语》ED）
  翻唱：旬夏（DDSP-SVC 转换的 AI 歌声）
  画面：一张 AI 插画在 Blender 里拆层做成 2.5D，人物随风摆动、跟着歌声张口，花瓣、流星、旋律盘都跟着歌走
  4K 60 帧，建议调到最高画质观看
  ```
- 标签：`君の知らない物語` `supercell` `化物语` `翻唱` `AI翻唱` `一图流` `4K` `Blender`
