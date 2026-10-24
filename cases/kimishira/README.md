# 君の知らない物語 · 一图流 PV

一张插画、一首歌的"一图流"鉴赏 PV，给 B 站。画面全在 Blender 里做：插画按深度拆成几层摆成 2.5D 场景，
镜头始终看整张画，只缓慢平移，前后景有真实的视差；人物的头发、尾巴、耳朵、裙摆跟着风摆，嘴跟着歌声张合；
花瓣、光点、流星、星星闪烁跟着歌走；月亮外圈的星环就是"旋律盘"：光点沿看不见的轨道绕月亮转，跟着歌出现、明灭。

| | |
|---|---|
| 歌 | supercell「君の知らない物語」，旬夏的 AI 翻唱（DDSP-SVC），`audio/kimishira_sakura_shunka_mix.wav` |
| 画 | kue 的星空花田插画，4K 精修版 `characters/kue/art/kue_pv_stars_103_4k_00001_.png`；分层（远景 / 中景 / 近景 / 人物，被挡住的部分 Qwen 补画）在 `characters/kue/art/layers/stars_103/` |
| 预览 | `renders/kimishira_preview_540p_40s.mp4`：960×540、30 fps、8 采样，默认只出前 40 秒（约 1 分半）；`LEN=0` 出整首 `renders/kimishira_preview_540p.mp4`（约 8 分钟） |
| 成片 | `renders/kimishira_pv.mp4`：3840×2160、60 fps、H.264 High + AAC 320k，5 分 37 秒 |
| 封面 | `renders/cover_16x9.jpg`（1920×1080）、`renders/cover_4x3.jpg`（手机端裁切） |

通用的做法和踩过的坑在 [docs/onepic.md](../../docs/onepic.md)，这里只记这首歌的部分。

## 段落

约 110 BPM，一小节 2.18 秒；段落按小节的响度和主唱音高分（副歌唱得高）。表在 `scripts/pv.py` 的 `SECTIONS`，
每段给花瓣、光点、月亮频谱环（`RING=bars` 时）、光束的开度和"能量"（管风速、摆动幅度、发光）。

| 时间 | 段落 | 镜头（一条不断开的路径，`camera_keys()`） |
|---|---|---|
| 0:00 | 开头清唱 | 整张画，第一帧起焦点就在镜头前的标题上，人物和背景都在焦外；月亮旁边竖排的标题「君の知らない物語」在虚的星空里一个字一个字浮现 |
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

开头的虚化是真的焦外：标题放在镜头前 0.5 米（`TITLE_Y`，字按距离缩小，画面上一样大），从第一帧起焦点就在标题上，
景深开到画面宽的 1.4%；8.75–12 秒拉回她脸上。对焦写成只有 `F()` 的关键帧，单独插值，镜头不会因此停顿。
做过先清楚、歌名出来再虚下去（0.8–2.6 秒拉焦），看着像对焦失误。

## 人物的摆动

`rig.json` 写各部位的大致位置（头中心、嘴、两只耳朵的框、尾巴的根 / 拱心 / 尖、裙摆的范围、呼吸的几条线），
`onepic_prep.py rig` 按颜色和位置算成权重图，Blender 里 `onepic.deform()` 用 Geometry Nodes 让人物网格局部变形：

- 头发、丝带：离头越远动得越多，从发根往下传的波；副歌风大摆得大（4K 下发梢约 15–27 像素）
- 尾巴：绕根部转，越往尖转得越多
- 耳朵：一直很慢地摆一点（周期 4–7 秒）；隔 5–13 秒抽一下：3 Hz 的衰减振荡，0.08 秒起手、0.28 秒衰减，
  一半两只耳朵一起（`ear_moves()`）。原来 7 Hz、0.16 秒、没有起手，太快太突然；中间试过慢慢转过去、停一下再转回来，
  后来又改回抽动，只是慢一半。
  头顶的蝴蝶结两边伸进耳朵的框里，`rig.json` 的 `ears_still` 框里白的、浅蓝的像素不跟耳朵动
- 裙摆：横向的慢波
- 嘴：跟主唱的快包络上下伸缩（−28%…+18%），嘴角横向跟一点；不唱时合一点
- 呼吸：胸口和肩膀起伏，头几乎不动（`rig.json` 的 `breath`：`v` 是下巴、肩线、胸口、腰四条线，`u` 是左右范围）。
  每句歌词开唱前半秒吸一口，唱的时候慢慢呼出去，句子之间平静地起伏（`breathing()`，句子的起止取 `audio/lyrics.lrc`）。
  整个人以下边为轴伸缩的呼吸试过，头跟着一点一点的，像假的

脸、手、话筒、话筒线、颈带在头发、裙摆、嘴三种权重里都是 0，不会变形（话筒线垂在裙子上，跟着裙摆摆会弯；
话筒头挨着下巴，跟着嘴伸缩会歪）。话筒和线另外在 `rig.json` 的 `rigid` 里画成折线（带半宽）：线到下面变细变浅，
按颜色抓不全；折线按修图后竖直的话筒画（见下面「修图」）。两只袖子是半透明的，后面透出头发，按颜色分不开：
`rig.json` 的 `sleeves` 各画一个多边形，里面头发的权重是 0，出了袖子约 2.5% 画面高才慢慢放开，
头发摆的时候不会带着上臂的袖子一起动。

分层抠出来的人物，尾巴和右边几缕头发是半透明的（尾巴约 0.9，右边那截 0.6–0.85），渲染时后面的花透出来，
看着像尾巴糊了。`rig` 最后把人物内部的 alpha 补满（写 `art/prep/layer_char_solid.png`），离边缘几个像素的抗锯齿边和细发丝不动；
`rig.json` 的 `translucent` 是本来就该透的地方（右下透出花的裙边），也不动。

## 修图

原画里话筒歪了约 9°，下面那只手的手指糊成一团。`scripts/retouch.py` 用 Qwen 的局部 img2img 只重画框里那块
（按原画像素裁一块给模型，不放大，羽化后贴回去），任务在 `jobs/retouch_*.json`：

| 任务 | 做法 | 结果 |
|---|---|---|
| `retouch_hands` | 重绘强度 0.65 / 0.8 | 几乎没变：0.9 以下模型保留原来的结构，话筒照样歪 |
| `retouch_hands_a` | 1.0，整框照提示词重画 | 用了 s2，话筒竖直 |
| `retouch_hands_b` | 框里先转 9° 摆正，再 0.75 / 0.9 | 没用 |
| `retouch_cable` | 在 hands_a s2 上只重画新旧话筒线的接头 | 用了 s3：hands_a 的新线到 v 0.83 就淡没了，旧线从 v 0.86 起偏左 80 像素，重画后接成一条弧 |

`scripts/retouch_apply.py` 把修好的图放进 `art/prep`：`color.png` 换成新图，人物层（`layer_char.png`、
`layer_char_solid.png`，放大过的按比例放大）只在实心处换上变了的像素；修之前的原图留在 `color_before_retouch.png`。
之后要重跑 `onepic_prep.py rig`，并按新的话筒改 `rig.json` 的 `rigid`。

## 旋律盘

旋律盘就是画里的月亮：月亮是唱片中间的标签，外面 15 道看不见的正圆轨道（1.40–10.40 R，R 是月亮半径，大体往外
越来越疏，盘超过半个画面），158 颗光点沿着轨道顺时针转，拖着细尾巴（`RING=stars`，默认；`scripts/star_ring.py`）：

- 每道轨道一段频率（里低外高），亮着的颗数跟这段的响度走；哪颗、什么时候出现（落在拍子上）、什么时候熄灭是随机的
- 每道轨道 2 到 14 小节一圈，同一道上的光点快慢差到 0.6–1.6 倍，快的追过慢的；响的时候一起转快一点
- 每颗按自己的周期明灭（4–12 拍，相位随机），经过朝她和对面那两段（唱片的反光）亮一点
- 颜色从里圈暖白到外圈冰蓝，个别几颗是金、红、粉

拍子用这首歌自己量的恒速网格：`audio/bands.npz` 的 `grid_beat`、`grid_phase`（`audio_bands.py`，165.00 BPM，
第 0 拍 0.021 s；librosa 的 beat_track 测成 109）。光点摆在 213 米处，在天空前面，她、花瓣、近处的花田会挡住它，
最外两道从她身后过；那里在景深外，细线虚掉一些，亮度乘 2.5（`onepic.star_ring()` 的 `gain`）。

这个样式是在渲染帧上叠 2D 的光一轮轮比出来的：频谱柱、光环、涟漪、跟着人声音高的旋律线、环绕的星群、
月轮唱片，最后唱片的纹变透明，只留光点。定下来以后做进了场景，比较用的脚本删了。

原来的频谱柱还在（`RING=bars`）：外圈 96 根跟着频谱跳的柱子（低频在下、高频在上，左右对称），低音来时整圈像心跳
一样鼓起来（`heart` 列，半径最多大 5%）。朝右下（人物那边）的柱子拉长到 1.3 倍，像月光斜着照向她；左上压到
0.85 倍；朝上的柱子软压在画面 v = 0.035 以下，整首不出画框（`spectrum_ring()` 的 `tilt`、`squeeze`、`top`）。

插画里月亮贴着上边，旋律盘顶上没地方：天空整层往下挪画面高的 3.5%（`MOON_DOWN`）。远景层只有天空和月亮，
整层放平在 275 米；Depth Anything 把月亮左上的天空估到 60–100 米，比 213 米处的旋律盘还近，挡掉了左上一段。

月晕和月光光束跟柔和版的心跳（低音的平方再 0.3 秒滑动平均，`pulse` 列），幅度也小，不闪；月亮本身的圆盘亮度不变。
光束只从月亮（`RING=bars` 时还有那圈频谱）发出（`BEAM_GAIN`、`BEAM_MASK`）。镜头始终看整张画，月亮一直在画面里。

## 可选特效

`FX=` 选，逗号隔开，`pv.py build` 时读（`preview.sh`、`render.sh` 前面加上就行）。不给时只开 `bokeh`，`FX=` 全关。
rim、streak 试过不要：streak 照现在的强度在画面上几乎没有变化，加强到看得见时是横着的一块光，月亮周围还多一圈暗边。
前 40 秒的对比（不开、bokeh、rim、streak 各单开，和四格并排的 `grid4`）在 `renders/fx/`。

| `FX` | 效果 |
|---|---|
| `bokeh` | 镜头前 0.5–1.3 米的虚焦花瓣，二十几片，比飘着的花瓣大一倍多，半透明、边上软，慢慢翻、慢慢明灭，镜头一动视差最大（原来是圆的光斑） |
| `rim` | 人物朝月亮那一侧的轮廓光，跟着心跳 |
| `kick` | 重拍上镜头轻推 0.4% |
| `streak` | 月亮的水平光条 |
| `glint` | 发夹的花、丝带上的花、头顶蝴蝶结偶尔闪一下四芒星 |

左下角只留一条窄的歌名、"supercell · cover 旬夏"、进度条和时间（`scripts/onepic_player.py` 不给 `--art`），
逐帧画成透明 PNG，最后叠上去；歌词在它上面。

一开始左下角也做过一个带唱片的旋律盘（`--art` 给图就有），和月亮外圈的频谱同时跳，两个盘抢眼，就只留了月亮。

## 歌词

网易云音乐的原曲（id 825646）的 LRC 和中文翻译，存在 `audio/lyrics.lrc`、`audio/lyrics_cn.lrc`（不进仓库）。
和主唱的起音逐句对过：整首没有漂移，句子比开唱早约 0.4 秒出，所以整体推后 0.15 秒（`LYRICS_OFFSET`）。
结尾的制作信息在 `credits.txt`。改歌词或制作信息只需重做成片（`SKIP_RENDER=1`），不用重渲染。

## 怎么跑

全部在 AutoDL 上（`ssh autodl`），本地只写脚本、看结果。服务器上的 `/root/autodl-tmp/svc-mv` 是这个仓库的 git 克隆：
本地提交、push 到 GitHub，服务器上 `git pull`；服务器推不了这个仓库，别在那边提交。用 scp 把脚本推过去，两边会各加一遍同样的文件，
下次 pull 就冲突。详见总 README 的 [Local and the GPU server](../../README.md#local-and-the-gpu-server)。

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
# 修图（ComfyUI 由 comfy_batch.sh 起停），挑好的放进 art/prep，再重跑上面的 rig
CLIENT="env PYTHONPATH=/root/autodl-tmp/pv/pylib $PY /root/autodl-tmp/svc-mv/scripts/retouch.py" \
    bash scripts/comfy_batch.sh $C/jobs/retouch_hands_a.json       # 它会 cd 到 ComfyUI，CLIENT 里的脚本给绝对路径
$PY scripts/retouch_apply.py $C/art/prep $C/art/retouch_cable/retouch_cable_d100_s3.png

# 快速预览：前 40 秒约 1 分半 -> renders/kimishira_preview_540p_40s.mp4；LEN=0 整首；FX、TAG 见上
bash $C/scripts/preview.sh
FX=bokeh,rim TAG=fx2 bash $C/scripts/preview.sh      # -> renders/kimishira_preview_540p_40s_fx2.mp4
# 几秒的静帧（RES=50 是 1080p）
$B -b --factory-startup -P $C/scripts/pv.py -- build
RES=50 $B -b $C/renders/scene.blend -P $C/scripts/pv.py -- stills 3 20 35 210
# 4K60 成片（4 个进程两个多小时，再加约 40 分钟编码；断了用 RESUME=1 续）
bash $C/scripts/render.sh 4
# 封面：副歌里一张 4K 静帧（月亮的星环和光束都亮着），左边加竖排大标题
RES=100 $B -b $C/renders/scene.blend -P $C/scripts/pv.py -- stills 70
$PY $C/scripts/cover.py $C/renders/stills/t_070.00.png $C/renders/cover
```

## 投稿

- 分区：音乐 → 翻唱。类型选"自制"，在简介里写明原曲。
- 作者声明勾选"使用 AI 合成技术"：歌声是 DDSP-SVC 转换的，插画是 AI 画的。
- 插画（Qwen-Image-2.1 画的）和放大、深度模型都是非商用许可，不开充电、不接商单。Qwen 的许可严格说只许研究和评估用，
  见 [docs/models.md](../../docs/models.md)。
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
