# 裏表ラバーズ: the first experiment

An MV for 《裏表ラバーズ》 (wowaka). Pheebie's cover stands in for the song until the SVC version exists
(181.0 s, about 161 BPM; the cut is on the downbeats, so the SVC version drops into the same grid).
The case tries the whole pipeline end to end: a 3D set in Cycles, illustrations, and an animatic cut on the
downbeats.

- [script_v4.md](script_v4.md): the script (in Chinese). She is a two-sided print: her 表 on the front of a thin
  sheet, her 裏 printed mirrored on the back, showing through when the sheet is lit from behind, wet, or seen from
  behind. The 3D side is one hall hung with these prints over a floor of black water; love is a drop of rose ink.
  Its section map is measured from the song. Scripts v2 and v3, their six sets S1–S6, the style frames, the old
  animatic and the v3 illustrations are deleted; they are only in git history.
- [CREDITS.md](CREDITS.md): the assets the hall uses.

## Scripts

| File | What it does |
|---|---|
| `scripts/case.py` | This case's folders; puts the pipeline's `scripts/` on `sys.path` |
| `scripts/animatic_cut.py` | Joins the animatic's frames with the song into an MP4 |
| `scripts/animatic_v4.py` | v4: the animatic in 3D. Section 5 of script v4 shot by shot in `v4_hall.py`'s hall, cut on the downbeats and rendered in Cycles at 640 px and 16 samples. The 3D shots carry the script's effects in the scene (lamps on the downbeats, KV' showing through, 表 and 裏 cut out of the KV, prints turning, lifting, wet and torn, ripples, rose ink as a volume, rain, cracks, shards, the walls falling to the sky, flying paper, the line-art flash, the roll, the dolly zoom, the Dutch angle, the reflection that is her 裏); the 2D shots are round 2's illustrations on a card filling the frame. Every frame is labelled with its section, shot, bar and time |
| `scripts/v4_hall.py` | v4: the hall's look, stills at dawn and in rose light (`renders/v4_hall/`, dawn and rose in separate runs). Poly Haven plaster, concrete, lamps and pipes; the prints carry KV 211 with KV' behind it and round 2's pictures. In rose light a cold light on the fronts keeps the 表 readable over the 裏; without it only the 表's window frames show, and read as stripes |

## Running

From the repository root. `audio/` holds `urao_mix.m4a`, `urao_vocal.wav`, `urao_lines.jsonl` (not in git), and
`urao_lyrics.json`, the speech recognition of the cover's lyrics, mistakes and all (no real lyric text yet).

The song's timing (`audio/urao_timing.json`, which the scripts read):

```sh
C=cases/uraomote
.venv/Scripts/python scripts/analyze.py $C/audio/urao_mix.m4a $C/audio/urao_vocal.wav $C/audio/urao_lines.jsonl $C/audio/urao_timing.json --fps 30
```

The v4 animatic renders on the server's GPU. Frames already in the folder are skipped, so bar ranges run side by side
into one folder; delete the folder's frames before a full rerun. `AT=0.5` renders one frame from the middle of every
shot (37 frames, about a minute), `ONLY=P0,P7` only those sections, `DRY=1` builds and poses every frame without
rendering and saves the .blend.

```sh
C=cases/uraomote
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
P=/root/autodl-tmp/ComfyUI/venv/bin/python
$B -b --factory-startup -P $C/scripts/animatic_v4.py -- $C/renders/animatic_v4/frames -3 58 &
$B -b --factory-startup -P $C/scripts/animatic_v4.py -- $C/renders/animatic_v4/frames 58 120
$P $C/scripts/animatic_cut.py $C/renders/animatic_v4/frames $C/audio/urao_mix.m4a $C/renders/animatic_v4/animatic_v4.mp4 12
```

## Illustrations

Her illustrations are drawn on ComfyUI as in [docs/comfyui.md](../../docs/comfyui.md). The pictures stay off git,
in `art/` on the local disk and in the server's checkout, with contact sheets `art/**/_sheet_*.png`.

### v4

Script v4, section 3.4, on Qwen-Image-2.1 (小铃久绘's recipe). `jobs/v4_prompts.py` holds what every round shares:
her design, the look, the 表 and 裏 lights. Pictures in `art/v4/`.

| Jobs | Pictures | |
|---|---|---|
| `jobs/v4_t1.json` (from `v4_t1.py`) | `v4_{sheet,kv,window,chorus,water,rain,print}_*` | Her new design and the look, no reference. `sheet_201` is the design; the 表 pictures (kv, window) work, the 裏 ones came out flat: one pink light, blank faces, pink smoke for ink, ink tears that read as blood, and the bird's-eye view ignored |
| `jobs/v4_t2.json` (from `v4_t2.py`) | `v4_{kv,a1–a5,q1,c1–c4,w1,w2,u1,u2,u4,r0,f1,f2}_211/213`, `v4_s1–s3_211` | Every illustration of 3.4 from `sheet_201`, two seeds each, and the three skies. The 裏 light gained a cold fill and every face its expression. Sheet: `_sheet_v4_t2.png`. Not picked yet; KV' and Q2 come from the picks |
| `jobs/v4_t3.json` (from `v4_t3.py`) | `v4_kvu_{211,213}_{62,75,n62,n75}` | KV' in each round-2 KV's own composition. Redrawn from the KV as it is, it stayed in daylight (62, 75: only her face changed). Turned to night first (`v4_kv_*_night.png`), it keeps the composition exactly and comes out at night with the rose light from the window, n75 the better; but hazy, and the rose glow sits in front of her face instead of rimming her hair. Sheet: `_sheet_v4_t3.png` |
