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
| `scripts/animatic_v4.py` | v4: the animatic in 3D. Section 5 of script v4 shot by shot in `v4_hall.py`'s hall, cut on the downbeats and rendered in Cycles at 640 px and 16 samples. Every print is a hybrid print (`v4_hybrid.make_print`), and the 2D shots go *into* a print (`into()`): the camera in front of the print that carries the picture, the frame as wide as the picture, centred on her face from the parts map, the picture's planes alive and 3D things at its depth (ink soaking in from her hair and a wisp of it in the air, rain inside the picture, a ripple on her water on the beat). The nine pictures that hang nowhere else are staged as prints before row 0 (`STAGE`, wide ones on sheets turned on their side), out of the way of the cameras. The 3D shots carry the script's effects in the scene (lamps on the downbeats, KV' showing through, 表 and 裏 cut out of the KV, prints turning, lifting, wet and torn, ripples, rose ink as a volume, rain, cracks, shards, the walls falling to the sky, flying paper, the line-art flash, the roll, the dolly zoom, the Dutch angle, the reflection that is her 裏). Every frame is labelled with its section, shot, bar and time |
| `scripts/animatic_cut.py` | Joins the animatic's frames with the song into an MP4, and puts the film's finish on (halation, vignette, grain; `LOOK=0` for none) |
| `scripts/v4_hall.py` | v4: the hall's look, stills at dawn and in rose light (`renders/v4_hall/`, dawn and rose in separate runs). Plaster over a steel frame (columns, cross beams, purlins), the high windows in steel frames with old glass, a damp band above the water; the prints are paper, with a bare border, fibre and a slow cockle. Dawn is one sun through the windows and the sky's light through them, nothing else: the beams in the haze carry the picture. In rose light a cold front light keeps the 表 readable over the 裏 glowing through, and a cold moon is the night's only other light |
| `scripts/maps.py` | For the hybrid prints: each illustration's depth map (Depth Anything V2) and a map of its flat planes, sky or window, water, mirror (CLIPSeg; a picture whose whole background is one plane takes everything far as that plane). Runs on the server; `art/v4/maps/`, with a `_check.jpg` per picture to judge the masks |
| `scripts/v4_hybrid.py` | The 2D picture and the 3D hall set into each other: a print's sky, water and mirrors become the hall's own surfaces (a sky plane behind the paper that shifts with the camera and keeps the picture's window frame, the hall's black water mirroring its lamps and beams, mirror glass), and the figure rises off the paper as a relief from the depth map, so light rakes it and the camera finds parallax. Stills of the KV at dawn and U1 in rose light, `renders/v4_hybrid/` |

## The hybrid print

The pictures do not hang in the hall as cards; each side is set into the other. The flat planes of a picture, its
sky, its water, its mirrors, are the hall's surfaces, and the hall's things sit in the picture's depth. Judge every
shot by that: does the 3D enter the picture and the picture enter the 3D, or is it a card again?

What the good Blender MVs taught (Vaundy『ZERO』, ヨルシカ『晴る』, あんスタ『Dear World』, King Gnu『SPECIALZ』 in
CGWORLD): lock the camera before the art; one subject a shot, three layers of depth; cut by subtraction, let a
pause carry the feeling; light the hero and keep the darks, with off-screen panels for the rim; colour at the
boundary of light and shadow, the one warm colour (the rose) small; near things at high detail, far things low;
grade the whole but do not flatten the sections. The finish (halation, vignette, grain) goes on in the cut.

What the first full cut taught, read off its contact sheets: ink is dark; a volume that glows is a lamp, not ink,
and a stain the size of the sheet is a disc, not a soak (the stain is the size of her hair, ragged, darker at its
rim; the wisps absorb). The rose never fills the air: the haze stays cool, and the red is only where a rose lamp
lands on paper or that paper's reflection in the water. Every 2D shot sets its own exposure; the hall's would wash
it or sink it, and a dawn sun behind translucent paper washes it from behind. A still frame longer than a bar
needs a move in it, even an orthographic one widening a step on each downbeat. A line drawing from render passes
does not work at animatic samples: edges of the normal pass are the water's and walls' bump at every pixel, the
depth pass is not anti-aliased, and even the averaged mist pass is noise under a Laplacian; the beat flash is the
frame's negative on paper instead. The far wall is at x 40: a camera 4 m behind a print's back must still be inside
the hall. The water is a mirror and never a lamp: any emission on it reads as a flat red floor.

What the first 1280 px cut taught, off its sheets and a dozen full frames: the 3D in a picture's dimensional part
has to behave like the thing it stands for. Hair strands pointing out from the head were whiskers, and two of them
hung loose in the sky through the parallax of a long strand lifted towards the lens; hair hangs down and a little
out, short flyaways on the crown only, each strand the picture's colour where it roots (black ones were scratches
on a dark print). Rain 2.5 mm wide and bright is matchsticks over her face; hair-thin, dim, leaning with the wind,
it is rain. Even grey cards of one size are cards; torn paper is small, uneven, and some of it carries the picture.
An ink volume seen from above is a black disc; the chorus's ink is the rose flowering on her paper. A camera that
flies at a print spends half a bar on blurred brushstrokes unless it crosses fast on a wide lens with the paper
wet. A print's bare border is paper without ink: behind a rose lamp it glows like a strip light unless it lets
through less. Under a raking lamp a close print's relief mottles the paper and the pink coming through it: the two
prints seen closest carry a flatter relief. A reflection shot framed from the water's edge at 3 m showed her collar
and its mirror image: to read as 表 and 裏 it needs her face and her reflected face both in frame.

Judge a run by its contact sheets, not by single frames: `AT=0.25,0.5,0.75` (three frames of every shot, six
minutes) into `tmp/`, `sheet.py` on it, read the sheet; a full run only after the sheet holds. The full run's
sheets, a frame a second, sit beside its mp4. At 1280 px pull a dozen full frames of the shots in question too:
strands, rain and relief grain are invisible in a 640 px tile.

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
$P $C/scripts/sheet.py $C/renders/animatic_v4/frames $C/renders/animatic_v4/sheet_0.jpg 12 6 400 0 431   # a frame a second, 36 s a sheet
```

Two Blender processes on the one GPU are slower than one after the other (they contend, and most of a frame is
the CPU re-syncing materials): run the halves in sequence. Setting a socket or a light to the value it already
has still makes Cycles rebuild it, so the per-frame setters (`put`, `energy`) write only on change.

The hall's and the hybrid's stills, and the maps they need (the hub is not reachable from the server: the two models'
files are fetched with curl from hf-mirror.com into `tmp/hf/` and named by `DEPTH_MODEL` and `SEG_MODEL`):

```sh
DEPTH_MODEL=tmp/hf/Depth-Anything-V2-Small-hf SEG_MODEL=tmp/hf/clipseg-rd64-refined $P -I $C/scripts/maps.py $C/art/v4 v4_kv_211 v4_u1_211
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
her design, the look, the 表 and 裏 lights. Pictures in `art/v4/`.

| Jobs | Pictures | |
|---|---|---|
| `jobs/v4_t1.json` (from `v4_t1.py`) | `v4_{sheet,kv,window,chorus,water,rain,print}_*` | Her new design and the look, no reference. `sheet_201` is the design; the 表 pictures (kv, window) work, the 裏 ones came out flat: one pink light, blank faces, pink smoke for ink, ink tears that read as blood, and the bird's-eye view ignored |
| `jobs/v4_t2.json` (from `v4_t2.py`) | `v4_{kv,a1–a5,q1,c1–c4,w1,w2,u1,u2,u4,r0,f1,f2}_211/213`, `v4_s1–s3_211` | Every illustration of 3.4 from `sheet_201`, two seeds each, and the three skies. The 裏 light gained a cold fill and every face its expression. Sheet: `_sheet_v4_t2.png`. Not picked yet; KV' and Q2 come from the picks |
| `jobs/v4_t3.json` (from `v4_t3.py`) | `v4_kvu_{211,213}_{62,75,n62,n75}` | KV' in each round-2 KV's own composition. Redrawn from the KV as it is, it stayed in daylight (62, 75: only her face changed). Turned to night first (`v4_kv_*_night.png`), it keeps the composition exactly and comes out at night with the rose light from the window, n75 the better; but hazy, and the rose glow sits in front of her face instead of rimming her hair. Sheet: `_sheet_v4_t3.png` |
