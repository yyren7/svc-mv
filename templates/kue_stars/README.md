# 模板：kue 星空花田 · 一图流 PV

kimishira（君の知らない物語）那支 PV 的做法存成的模板：画面还是 kue 的星空花田插画，换一首歌、换歌词和文字，
就能出一支新的。场景、人物的摆动、粒子、镜头的路子都和 kimishira 一样。星环默认是后来定的**花哨样式**：
- 11 道拉开的轨道；
- 七种光点：普通、双子星、火花尾、脉冲星、彗星、珠串、棱彩尾；
- 缓慢变化的六芒星芒、横向光条；
- 月亮当星系核的大星系。

比样式的过程在 kimishira 的 `scripts/ring_poc.py`（E 那一版）。

通用的做法和踩过的坑在 [docs/onepic.md](../../docs/onepic.md)。

## 一首歌要准备什么

都放在 `cases/<歌>/`：

| 文件 | 内容 | 进仓库 |
|---|---|---|
| `song.json` | 歌名、歌手、左下角的副标题、各个文件在哪（见下） | 是 |
| `credits.txt` | 结尾右下角的制作信息，一行一条 | 是 |
| `audio/mix.wav` | 混音（成片的音轨，也用来量拍子、响度、频谱） | 否 |
| `audio/vocal.flac` | 人声分轨（可以没有：`"vocal": null`） | 否 |
| `audio/lyrics.lrc` | 歌词（LRC，空行标间奏开始）；呼吸、段落、左下角歌名淡出的时机都看它 | 否 |
| `audio/lyrics_cn.lrc` | 译文（可以没有） | 否 |
| `plan.json` | 自动排的段落、镜头、流星、标题时机，草稿，可以手改 | 是 |

`song.json`：

```json
{
  "title": "君の知らない物語",
  "artist": "supercell",
  "sub": "supercell · cover 小铃久绘（DDSP-SVC）",
  "mix": "audio/mix.wav",
  "vocal": "audio/vocal.flac",
  "lyrics": "audio/lyrics.lrc",
  "lyrics_cn": "audio/lyrics_cn.lrc",
  "lyrics_offset": 0.15,
  "credits": "credits.txt"
}
```

- `title` 用在三处：
  - 开头月亮旁边竖排的大标题：8 个字是 kimishira 的大小，更短的按字数放大（最多 1.5 倍），再长就缩小；
  - 左下角进度条上的歌名；
  - 封面。
- `artist`：大标题下面的一行小字，也印在封面上。有中日文字时用标题的字体（DIN 没有这些字形）。
- `sub`：左下角歌名下面那行。
- `lyrics_offset`：歌词整体推后几秒。这首网易云的 LRC 比开唱早约 0.4 秒，所以给了 0.15。
- 可选字段：
  - `title_font` / `artist_font`：`fonts/` 里的文件名，默认 `yumindb.ttf` / `DINNextLTPro-Light.ttf`；
  - `title_end`、`show`（`[淡入, 淡完]`）、`credits_at`（`[开始, 结束]`）：直接定三处歌名的时机，不让 `plan.py` 排；
  - `lyrics_style`：`stagger`（默认）：
    - 歌词放在左边中部的天空里，上下两个位置交替，下面那个往右错开一点；
    - 下一句提前半透明挂着，开唱时从左往右一个字一个字亮起来、往上浮一点，字下面划出一道细光；
    - `line` 是 kimishira 成片那种，左下角一次一句。
    - 歌词里没有假名时，字体用 Noto Serif CJK SC。
  - `ring`：`fancy`（默认）、`classic`（kimishira 成片那种）；
  - `fx`：见 kimishira 的 README，默认 `bokeh`。

## 怎么做

```sh
# 本地：开一首新歌（只写文本文件），改好 song.json、credits.txt，提交、推送
bash templates/kue_stars/new_song.sh <歌> "歌名" "原唱" "翻唱"

# AutoDL：git pull，把音频和歌词放进 cases/<歌>/audio/（不进仓库）
cd /root/autodl-tmp/svc-mv
PY=/root/autodl-tmp/ComfyUI/venv/bin/python; export PYTHONPATH=/root/autodl-tmp/pv/pylib
# 第一次跑 preview.sh / render.sh 时会先算音频特征（audio/bands.npz），没有 plan.json 就排一份
bash templates/kue_stars/preview.sh cases/<歌>                      # 前 40 秒 540p，约 2 分钟
HEIGHT=1080 START=60 LEN=20 bash templates/kue_stars/preview.sh cases/<歌>   # 第 60 秒起 20 秒 1080p，看副歌
$PY templates/kue_stars/plan.py make cases/<歌> --force             # 重排 plan.json（会覆盖手改的）
bash templates/kue_stars/render.sh cases/<歌>                       # 1080p60 成片，4 个进程约 1 小时 20 分
HEIGHT=2160 bash templates/kue_stars/render.sh cases/<歌>           # 4K60，约 4 小时
# 封面：副歌里的一张 4K 静帧，左边加竖排大标题
eval "$($PY templates/kue_stars/plan.py env cases/<歌>)"
CASE=cases/<歌> RES=100 $B -b cases/<歌>/renders/scene.blend -P templates/kue_stars/pv.py -- stills $COVER_AT
$PY templates/kue_stars/cover.py cases/<歌> cases/<歌>/renders/stills/t_$(printf %06.2f $COVER_AT).png
```

成片在 `cases/<歌>/renders/<歌>_pv_1080p.mp4`（或 `_2160p`），预览是 `<歌>_preview_540p_0s+40s.mp4`。

- **只改了歌词、制作信息、歌名**：`SKIP_RENDER=1 bash templates/kue_stars/render.sh cases/<歌>`，只重做字幕和成片，几分钟。
- **中途断了**：`RESUME=1` 续渲。

插画处理好的东西（分层、深度、人物摆动的权重图）在服务器的 `characters/kue/art/stars_103_prep/`，不进仓库。
它是从 `cases/kimishira/art/prep/` 复制的，`meta.json` 里的分层改成了相对路径。
换了插画就是另一个模板了：插画相关的常数在 `pv.py` 开头（`FACE`、`MOON_DOWN`、`GLINTS`、`LAYER_GAIN`），
人物的摆动要重做权重图（kimishira 的 `rig_paint.py`、`rig_review.sh`）。

## plan.json 是怎么排的

`plan.py make` 打印一张段落表。看一下，不对的地方直接改 `plan.json`：
- `sections` 一行一段：`[名字, 开始秒, 能量, 花瓣, 光点, 旋律盘, 光束]`；
- `camera` 一行一个关键帧；
- `meteors` 是流星的秒数；
- `title_end`、`show`、`credits_at` 是三处歌名的时机。

排的规则（照 kimishira 手排的那份总结出来的，细节见 `plan.py` 开头）：

- **小节**：取音频特征里的重拍。kimishira 手排的边界都落在它上面。
- **切段**：前后两、四小节的响度、高频、低频、高音区和"有没有人在唱"差得多的地方切开；超过约 24 秒的段落在里面最明显的地方再切。
- **能量**：这段在整首里的响度位置和排名各占一半，0.2–1.0。花瓣、光点、旋律盘、光束都按能量推。
- **名字**：开头、间奏（没人唱）、结尾按歌词定；有人唱的段落里最响的三成多叫 chorus。
  名字管镜头：chorus 升起一点，inst 往月亮那边偏，其余左右慢慢挪。
- **三处歌名接力**：
  - 开头的大标题在第一句开唱时淡完：第一句不在 6–25 秒里，或者没有歌词，就在乐队进来后约 3 秒淡完；
  - 左下角的歌名紧接着淡入，最后一句唱完 1.5 秒淡出；
  - 制作信息接在后面，到片尾前 3.5 秒；
  - 进度条和时间一直都在。

拿 kimishira 的音频和歌词试排，和手排的那份对照：
- 前三段（0、8.75、15.3 秒）和手排的一样；大标题 11.6 秒淡完、左下角歌名 15.3 秒进来，也和成片一样（这是改成"第一句开唱时淡完"之前的规则）。
- 后面的边界大多差 1–2 秒。
- 少数段落的能量偏低：最后一段副歌排成了 bridge 0.55，手排是 1.0。混音压得紧的歌段落之间的响度差很小，这种要手改。
