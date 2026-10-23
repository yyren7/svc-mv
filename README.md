# svc-mv

A pipeline for making a music video for a song sung by a [DDSP-SVC](https://github.com/yyren7/DDSP-SVC) voice model,
with Blender and Python. The song's beats, downbeats and sung lines set the cut. The 3D side is procedural sets
rendered in Cycles, built at real size like 1:12 miniatures. The 2D side is print material (risograph inks,
halftones) plus character illustrations drawn on ComfyUI.

The scripts in `scripts/` and the notes in `docs/` are shared. Each song is a **case** in `cases/`, a folder
holding that song's script, set scripts, renders and credits. Each character drawn in the illustrations has a
folder in [characters/](characters/), apart from any case: her design, the prompt and recipe that draw her, the
jobs files.

## Cases

| Case | What it is |
|---|---|
| [cases/uraomote](cases/uraomote/) | The first experiment: six sets as stills, an animatic cut on the downbeats, a script for 2D and 3D invading each other |
| [cases/kimishira](cases/kimishira/) | 一图流鉴赏 PV：一张插画拆层摆成 2.5D 场景，人物随风摆、跟着唱，粒子、月亮外圈的频谱跟着歌走，4K60 成片 |

## Shared scripts

Audio and lyrics:

| File | What it does |
|---|---|
| `scripts/analyze.py` | Beats, downbeats, loudness per frame and sung lines, from the mix and the vocal |
| `scripts/transcribe.py` | Lyrics with word timestamps (faster-whisper) |
| `scripts/audio_bands.py` | 逐帧音频特征：节拍、重拍、响度、低频、高频、人声、对数频谱 |
| `scripts/lrc2ass.py` | LRC 歌词（可带译文）和制作信息 -> ASS 字幕 |

3D sets in Blender (local):

| File | What it does |
|---|---|
| `scripts/kit.py` | Blender-native motion kit: F-curve helpers, Geometry Nodes (kinetic text, timecode, bursts, speedlines, shatter), Line Art, rigid bodies, cloth, compositor |
| `scripts/cyc.py` | Shared Cycles setup: GPU, kelvin lamps, physical DOF with autofocus, haze, per-shot exposure, the still loop |
| `scripts/assets.py` | Cycles material library and procedural hero props (hearts, heart bulbs) |
| `scripts/props.py` | Procedural set dressing at 1:12: set box, iron bed, twin-bell clock, window with a printed sky card, desk things, polaroids, tiles, instancing |
| `scripts/texlib.py` | Poly Haven PBR surfaces box-mapped onto procedural meshes, HDRI worlds, models scaled to 1:12 |
| `scripts/fetch_assets.py` | Downloads the Poly Haven (CC0) and CC BY assets the sets use into `assets/` |
| `scripts/encode.py` | Frames + audio slice to MP4, with film grain |
| `scripts/test_kit.py` | Smoke test for `kit.py` |

2D print material:

| File | What it does |
|---|---|
| `scripts/mvlib.py` | 2D layout kit in Blender: flat / toon / halftone materials, text in Mincho / Gothic / DIN, rules, marks, barcodes |
| `scripts/riso.py` | 2D material as a risograph print (PIL): paper, halftone screens, inks that overprint out of register; `separate()` turns an illustration into the inks |

Illustrations on ComfyUI (AutoDL):

| File | What it does |
|---|---|
| `scripts/comfy_gen.py` | Queues a jobs file on ComfyUI: Anima or Qwen-Image-2.1, reference pictures, img2img from an earlier job |
| `scripts/comfy_batch.sh` | Starts ComfyUI on the GPU server, draws the job files, stops it again |
| `scripts/art_sheet.py` | Tiles pictures into a labelled contact sheet |
| `scripts/retouch.py` | 用 Qwen 的局部 img2img 重画一张图里的一个框（手、道具），其余像素不动 |
| `scripts/retouch_apply.py` | 把修好的图放进一图流的 prep：`color.png` 和人物层的实心处 |
| `scripts/layers.py` | 一张成品图拆成人物层和近 / 中 / 远三层背景（AutoDL）：anime-seg 抠人物、Depth Anything 分深度、Qwen 补画每层被挡住的部分 |

One-picture PV, 一图流 (AutoDL):

| File | What it does |
|---|---|
| `scripts/onepic_setup.sh` | AutoDL 上一图流的环境：依赖装进单独的 pylib，下载模型 |
| `scripts/onepic_prep.py` | 一图流的素材准备（AutoDL）：深度、人物遮罩、补全背景、天空、星点、月亮；接入另外做好的分层并放大 |
| `scripts/onepic.py` | 一图流的 Blender 场景：按深度起伏的插画层、音频数据贴图、漂流粒子、频谱环、流星、立体标题、镜头、合成 |
| `scripts/onepic_player.py` | 一图流左下角的歌名、进度条和时间，可选带唱片和一圈频谱的旋律盘，逐帧透明 PNG |
| `scripts/onepic_finish.py` | 分段视频拼接，一次编码成片：颗粒、暗角、淡入淡出、字幕、音轨 |
| `scripts/ring_lab.py` | 君の知らない物語（kimishira）月亮外圈旋律盘的样式实验：在渲染帧上画几种 2D 的光并排比较；目前只给这个 case 用 |

Notes that apply to every case:

- [docs/comfyui.md](docs/comfyui.md): drawing illustrations on ComfyUI: the server, the two models, the jobs file, and the recipes that worked.
- [docs/models.md](docs/models.md): Qwen-Image-2.1, Anima and Krea 2 compared on quality, and what every model in the pipeline allows commercially.
- [docs/onepic.md](docs/onepic.md)：一图流 PV 的做法和踩过的坑。

## Local and the GPU server

Local (Windows) is for writing scripts, the 3D sets in Blender, and looking at results. ComfyUI and the whole
one-picture PV run on AutoDL (`ssh autodl`, an RTX 4090D, 24 GB):

| On AutoDL | |
|---|---|
| `/root/autodl-tmp/svc-mv` | a git checkout of this repo |
| `/root/autodl-tmp/ComfyUI` | ComfyUI with its own `venv/`; its `input/` and `output/` |
| `/root/autodl-tmp/pv/` | the one-picture PV's `pylib/` and `models/` (`scripts/onepic_setup.sh`) |
| `/root/autodl-tmp/tools/blender-5.2.2-linux-x64/` | Blender |
| `/root/autodl-tmp/conda_envs/` | `evalq` (librosa), `ddsp` (DDSP-SVC's, for RMVPE) |

- **Code goes one way**: commit locally, push to GitHub, then `git pull` in the checkout on the server. Don't commit
  on the server (its token can't push to this repo), and don't scp scripts over: a file added on both sides
  conflicts on the next pull.
- When the server can't reach GitHub, carry the commits in a bundle: locally `git bundle create x.bundle
  <server HEAD>..main`, scp it over, then on the server `/usr/bin/git pull --ff-only x.bundle main`.
- **What git leaves out sits at the same path on both sides** (`art/`, `ref/`, a case's `audio/`): copy pictures
  from `ComfyUI/output/` into the checkout's folder as well as pulling them locally, send contact sheets made
  locally back, and compare md5 on both sides. Don't overwrite a file that is newer on the other side. Renders and
  a PV's `art/prep/` are made on the server and stay there; pull what you want to watch.
- Background jobs over ssh need `nohup ... < /dev/null &`, or the ssh session hangs.

## A case's folder

```
cases/<name>/
  README.md      what the case is, its stills, how to run it
  script_*.md    the script
  CREDITS.md     third-party assets the case uses; the video's description carries the CC BY lines
  scripts/       the case's set scripts; case.py puts the shared scripts/ on sys.path and names the folders below
  renders/       stills (style frames and set stills are in git; everything else is rebuilt)
  audio/         mix, vocal, lines, timing.json (not in git)
  jobs/          ComfyUI jobs files for the case's own illustrations, one per round
  art/           the pictures they drew (not in git)
```

A one-picture PV ([cases/kimishira](cases/kimishira/)) has `pv.py` and its render scripts in `scripts/` instead of
set scripts, plus `rig.json` (where the character's moving parts are) and `credits.txt` (the end credits).

A set script starts like this:

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import cyc  # noqa: E402
OUT, SHOTS = cyc.args(os.path.join(C.RENDERS, "s1"), ["clock", "wide", "pov"])
```

## Setup (Windows)

**Blender 5.2.2 LTS**, portable zip from <https://download.blender.org/release/Blender5.2/>
(or a mirror such as `mirrors.aliyun.com/blender`), unpacked to `D:\tools\blender-5.2.2-windows-x64`.
The scripts use the Blender 5.x API (compositor node groups, action slots, `grease_pencils`) and do not run on 4.x.

**Python tools** (audio analysis, Whisper, ffmpeg via `imageio-ffmpeg`):

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

**Whisper large-v3** (~2.9 GB, not in the repo), from ModelScope:

```sh
.venv/Scripts/python -m pip install modelscope
.venv/Scripts/python -c "from modelscope import snapshot_download; snapshot_download('pengzhendong/faster-whisper-large-v3', local_dir='models/faster-whisper-large-v3')"
```

**Assets**: `scripts/fetch_assets.py` downloads the sets' Poly Haven and CC BY assets into `assets/` (not in the repo).

**Audio** is not in the repo (the songs are copyrighted and the converted voices are not published).
Put a case's files in `cases/<name>/audio/`: the mix, the separated vocal, and a lines file
(`eval_lines.py`'s `lines.jsonl` from DDSP-SVC, or the output of `transcribe.py`).

## Running

```sh
B=D:/tools/blender-5.2.2-windows-x64/blender.exe
.venv/Scripts/python scripts/analyze.py <mix> <vocal> <lines.jsonl> <timing.json> --fps 30
SAMPLES=256 $B -b --factory-startup -P cases/<name>/scripts/<set>.py              # Cycles, OptiX if available
RES=40 SAMPLES=24 $B -b --factory-startup -P cases/<name>/scripts/<set>.py -- tmp/look <shot>   # quick look at 40 %
$B -b --factory-startup -P scripts/test_kit.py
```

Every set script takes `-- [out_dir] [shot ...]`; with no `out_dir` it writes to the case's `renders/`.
`RES` (percent) and `SAMPLES` come from the environment. Blender's temp files go to `tmp/`.
Each case's README has its own commands.
