# 裏表ラバーズ: the first hybrid PV

An MV for 《裏表ラバーズ》 (wowaka). Pheebie's cover stands in for the song until the SVC version exists
(181.0 s, about 161 BPM; the cut is on the downbeats, so the SVC version drops into the same grid).
The case is where the 3D-into-2D pipeline was built: the 2D pictures and the 3D hall set into each other, an
animatic cut on the downbeats, rendered in Cycles, judged from contact sheets and refined pass by pass. The
reusable method, with everything the passes taught, is in [docs/hybrid.md](../../docs/hybrid.md); this file is
what belongs to this film alone.

- [script_v4.md](script_v4.md): the script (in Chinese). She is a two-sided print: her 表 on the front of a thin
  sheet, her 裏 printed mirrored on the back, showing through when the sheet is lit from behind, wet, or seen from
  behind. The 3D side is one hall hung with these prints over a floor of black water; love is a drop of rose ink.
  Its section map is measured from the song. Scripts v2 and v3, their six sets S1–S6, the style frames, the old
  animatic and the v3 illustrations are deleted; they are only in git history.
- [CREDITS.md](CREDITS.md): the assets the hall uses.

## Files

| File | What it does |
|---|---|
| `scripts/case.py` | This case's folders; puts the pipeline's `scripts/` on `sys.path` |
| `scripts/v4_hall.py` | The hall: plaster over a steel frame (columns, cross beams, purlins), the high windows in steel frames with old glass, 3 cm of black water over concrete, a damp band above it, industrial lamps and pipes (Poly Haven), the wires and the rows of prints (`hang()`), dawn and rose lighting, the haze. Stills at dawn and in rose light (`renders/v4_hall/`, separate runs) |
| `scripts/v4_hybrid.py` | Stills of the hybrid print in the hall: the KV at dawn and U1 in rose light, straight on and from the side (`renders/v4_hybrid/`) |
| `scripts/animatic_v4.py` | The film: section 5 of the script shot by shot on `scripts/animatic.py`'s engine. The hall's props for single shots (the glass of water on a sill, the print lying on the water and the lamp it mirrors, the Q1/Q2 print, C1's print, the cardboard in the rain, the 表 print whose reflection is her 裏), its lights, the prints staged for the 2D shots (`STAGE`), `into()` (a 2D shot inside a print), `reset()` and the shot functions |
| `runs/full.sh`, `runs/patch.sh`, `runs/restart.sh` | A full pass on the server, a re-render of one shot's bars with the cut and sheet remade, a restart |
| `runs/exp/*.json`, `runs/exp/queue*.txt` | The side-by-side experiments of the pass-9 rounds (`scripts/exp.sh` specs against the pass-8 code) and the lists they were queued from; their verdicts are in docs/hybrid.md |
| `runs/tests/glass_tube.py`, `runs/tests/haze_on_water.py` | The two bare-scene renderer tests: why the glass of water was a black tube (a refraction is a glossy bounce), why the water mirrored nothing (the haze box's face on the surface) |
| `jobs/v4_prompts.py`, `jobs/v4_t1–t3.{py,json}` | The ComfyUI jobs that drew her (below) |

Shared with every hybrid PV, in the repository's `scripts/`: `paper.py` (the two-sided print), `hybrid.py` (its
planes as the hall's, the relief, anchors), `hybrid_fx.py` (ink, cracks, rain, scraps, shards, strands, letters),
`animatic.py` (the engine), `maps.py`, `cut.py`, `sheet.py`, `grab.py`, `exp.sh`, `patch.py`, `queue.sh`.

## The hybrid print

The pictures do not hang in the hall as cards; each side is set into the other. The flat planes of a picture, its
sky, its water, its mirrors, are the hall's surfaces, and the hall's things sit in the picture's depth: ink soaking
in from her hair and a wisp of it in the air, rain inside the picture, a ripple on her water on the beat, strands of
her hair off the paper. Judge every shot by that: does the 3D enter the picture and the picture enter the 3D, or is
it a card again? How it is built, and what nine passes taught about it, is in [docs/hybrid.md](../../docs/hybrid.md).

What is particular here: the KV hangs in row 0 with KV' on its back and 表 / 裏 cut out of it; rows 1–6 carry the
round-2 pictures (a 表 one in front, a 裏 one of another composition behind); the nine pictures that hang nowhere
else are staged as prints before row 0 (`STAGE`, wide ones on sheets turned on their side), out of the way of the
cameras; the props of single shots stand beyond the last row (x 29–40). Pictures not drawn yet: Q2 is U2 on the
back of Q1's print, U3 is staged with the reflection trick of P7.3, R1–R6 are missing (the run has only its ripples
and the prints it tears).

## Passes

Every pass is a full render at one size, kept as `renders/animatic_v4/animatic_v4_passN.mp4` with
`passN_sheet_0..5.jpg` beside it (the same files locally and on the server, md5 equal); the current one is
`animatic_v4.mp4` + `sheet_0..5.jpg`. Review is from the sheets plus a dozen full frames, never from the player.

| Pass | Size | What it settled |
|---|---|---|
| 1–3 (2026-10-27) | 640 px / 16 | The cut and the cameras; ink is dark, not a lamp; the rose stays on paper and water; every 2D shot sets its own exposure; a long still needs a move; the beat flash is the frame's negative on paper |
| 4–6 (2026-10-28) | 1280 px / 32 | Hair strands along the hair's flow; hair-thin rain; torn paper that is small and uneven; the chorus ink as the rose flowering on her paper; P7 tilting from her face to her reflected face over stilled water; the 2D shots aimed at the prints that really carry their pictures |
| 7 | 1280 / 32 | The print lying on the water pressed flat and held over the surface; the glass of water seen level with the water, 14 glossy bounces; cracks that run straight with kinks; night rain at 0.14; the kraft board's corrugation; the second chorus round close on her face; `reveal` moved into a node socket (no crack had ever shown) |
| 8 | 1280 / 32 | The crack as a hair of light (white core, rose halo); ink in the glass from the surface down; corrugation at 22 bands |
| 9 | 1280 / 32 | Side-by-side experiments (`runs/exp/`): the lamp mirrored in the water beside the lying print (an emissive disc seen by glossy rays alone, over the haze box fixed to reach under the water); lights-out camera low towards the windows; no rain within arm's reach; pale letters on the back cover; the shards cuts off the hall's axis; the chorus inserts brighter; the 裏 print lit for the mirror at 9 |

| 10 | 1920 / 48 | The final size. Before it (`runs/exp/queue4-6`): C1's and R0's prints full-bleed (no white margin bar in the spill's pull-back and the tear), the glass of water lit through its water by a panel inside the pane, the reflection print facing down the hall so her face has the rows behind it, the third shards cut aimed lower |

Pass 9 (commit 897dce1, 2026-10-28, md5 `0364c4792324c92a11ef750dab78a072`) is the current 1280 px `animatic_v4.mp4`;
pass 10 renders to `frames_1920/`, `animatic_v4_1920.mp4`, `sheet1920_0..5.jpg`, with the chorus's shot from the
water lifted to the surface and the flat maps of F1, A5 and C3 cleared (CLIPSeg had given them planes they do not
have; the other 15 were checked by eye and left). Still weak: strands are the only 3D hair element; the window
glass of A1, A2 and A4 is only partly mapped (hung prints only).

## Running

From the repository root. `audio/` holds `urao_mix.m4a`, `urao_vocal.wav`, `urao_lines.jsonl` (not in git), and
`urao_lyrics.json`, the speech recognition of the cover's lyrics, mistakes and all (no real lyric text yet).

The song's timing (`audio/urao_timing.json`, which the scripts read):

```sh
C=cases/uraomote
.venv/Scripts/python scripts/analyze.py $C/audio/urao_mix.m4a $C/audio/urao_vocal.wav $C/audio/urao_lines.jsonl $C/audio/urao_timing.json --fps 30
```

The animatic renders on the server's GPU. Frames already in the folder are skipped, so bar ranges run side by side
into one folder; delete the folder's frames before a full rerun. `AT=0.5` renders one frame from the middle of every
shot (37 frames, about two minutes at 1280), `ONLY=P0,P7` only those sections, `DRY=1` builds and poses every frame
without rendering and saves the .blend.

```sh
C=cases/uraomote
B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
P=/root/autodl-tmp/ComfyUI/venv/bin/python
WIDTH=1280 SAMPLES=32 AT=0.25,0.5,0.75 $B -b --factory-startup -P $C/scripts/animatic_v4.py -- tmp/check/frames   # a look
$P scripts/sheet.py tmp/check/frames tmp/check/sheet.jpg 1 6 640
bash $C/runs/full.sh 9                                   # a full pass at 1280/32: frames, cut, six sheets, tmp/full9/done
bash $C/runs/full.sh 10 1920 48                          # the 1920 pass, beside the 1280 one
bash $C/runs/patch.sh 9 P8 84.2 85.9 1560 1582 3         # one shot again, then the cut and sheet 3
bash scripts/exp.sh out_windows $C/runs/exp/out_windows.json "WIDTH=1280 SAMPLES=32 ONLY=P2 AT=0.2,0.6,0.95" 30 31
```

Two Blender processes on the one GPU are slower than one after the other for the film itself (they contend, and most
of a frame is the CPU re-syncing materials): run a pass as one process, and put experiments beside it.

The hall's and the hybrid's stills, and the maps they need (the hub is not reachable from the server: the two models'
files are fetched with curl from hf-mirror.com into `tmp/hf/` and named by `DEPTH_MODEL` and `SEG_MODEL`; the
pictures whose whole background is one plane are named in `BACKDROP`):

```sh
DEPTH_MODEL=tmp/hf/Depth-Anything-V2-Small-hf SEG_MODEL=tmp/hf/clipseg-rd64-refined \
BACKDROP=v4_q1_:R,v4_u1_:G,v4_u3_:G,v4_c1_:G,v4_s1_:R,v4_s2_:R,v4_s3_:R \
$P -I scripts/maps.py $C/art/v4 v4_kv_211 v4_kvu_211_n75 v4_u1_211     # and every other *_211 picture
$B -b --factory-startup -P $C/scripts/v4_hall.py -- $C/renders/v4_hall aisle_dawn beams_dawn print_dawn
$B -b --factory-startup -P $C/scripts/v4_hall.py -- $C/renders/v4_hall aisle_rose front_rose beams_rose
$B -b --factory-startup -P $C/scripts/v4_hybrid.py -- $C/renders/v4_hybrid kv_dawn kv_side_dawn
$B -b --factory-startup -P $C/scripts/v4_hybrid.py -- $C/renders/v4_hybrid u1_rose u1_side_rose
```

`RES=50 SAMPLES=48` for a quick look at either.

## Illustrations

Her illustrations are drawn on ComfyUI as in [docs/comfyui.md](../../docs/comfyui.md). The pictures stay off git,
in `art/` on the local disk and in the server's checkout, with contact sheets `art/**/_sheet_*.png`.

### v4

Script v4, section 3.4, on Qwen-Image-2.1 (小铃久绘's recipe). `jobs/v4_prompts.py` holds what every round shares:
her design, the look, the 表 and 裏 lights. Pictures in `art/v4/`, their maps in `art/v4/maps/`.

| Jobs | Pictures | |
|---|---|---|
| `jobs/v4_t1.json` (from `v4_t1.py`) | `v4_{sheet,kv,window,chorus,water,rain,print}_*` | Her new design and the look, no reference. `sheet_201` is the design; the 表 pictures (kv, window) work, the 裏 ones came out flat: one pink light, blank faces, pink smoke for ink, ink tears that read as blood, and the bird's-eye view ignored |
| `jobs/v4_t2.json` (from `v4_t2.py`) | `v4_{kv,a1–a5,q1,c1–c4,w1,w2,u1,u2,u4,r0,f1,f2}_211/213`, `v4_s1–s3_211` | Every illustration of 3.4 from `sheet_201`, two seeds each, and the three skies. The 裏 light gained a cold fill and every face its expression. Sheet: `_sheet_v4_t2.png`. Seed 211 is used throughout until picked; KV' and Q2 come from the picks |
| `jobs/v4_t3.json` (from `v4_t3.py`) | `v4_kvu_{211,213}_{62,75,n62,n75}` | KV' in each round-2 KV's own composition. Redrawn from the KV as it is, it stayed in daylight (62, 75: only her face changed). Turned to night first (`v4_kv_*_night.png`), it keeps the composition exactly and comes out at night with the rose light from the window, n75 the better (and the one in use); but hazy, and the rose glow sits in front of her face instead of rimming her hair. Sheet: `_sheet_v4_t3.png` |
