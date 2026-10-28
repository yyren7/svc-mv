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
hung loose in the sky through the parallax of a long strand lifted towards the lens; strands that simply hung were
right on the portraits and wrong on everyone running, leaping or lying down. A strand follows the hair's own flow:
the hair mask's long axis, pointed at the tips (the end farther from her face; against the face's centroid it went
up on a portrait whose hair frames the face), a little out from the head and a little off the paper; each the
picture's colour where it roots (black ones were scratches on a dark print), rooted only on the hair's bulk where
the picture is dark (the mask's strays and painted flyaways in the sky), and none on C1, whose every strand was a
scratch under the spill's light. Rain 2.5 mm wide and bright is matchsticks over her face; hair-thin, dim, leaning with the wind,
it is rain. Even grey cards of one size are cards; torn paper is small, uneven, and some of it carries the picture.
An ink volume seen from above is a black disc; the chorus's ink is the rose flowering on her paper. A camera that
flies at a print spends half a bar on blurred brushstrokes unless it crosses fast on a wide lens with the paper
wet. A print's bare border is paper without ink: behind a rose lamp it glows like a strip light unless it lets
through less. Under a raking lamp a close print's relief mottles the paper and the pink coming through it: the two
prints seen closest carry a flatter relief. A reflection shot framed from the water's edge at 3 m showed her collar
and its mirror image: to read as 表 and 裏 it needs her face and her reflected face both in frame, and a 16:9
frame holding a whole portrait print over its whole reflection leaves the print a sixth of the width, so P7 tilts
from her face down over the water line into her reflected face instead. Under that tilt the water had to be stilled
and the beat ring made almost nothing: a long lens close to a mirror sees a far virtual image, and a normal tilted
a few degrees moves that image by most of a metre (liquid chrome in three check rounds). A 2D shot's key must point
at the print that actually hangs the picture: `v4_hall.hang` deals FRONTS from k 4 in row 2 (q1, a5, a1), and the
A5 shot aimed at the first of them showed q1 under A5's relief, anchors and strands, with strands loose in the sky.
In P0 the white was not the lamp but the picture's sky portal, lit at the hall's default: a shot before dawn sets
the sky dark itself. The beat the reflection turns 表 again shows a self-lit copy of the 表 picture, not the paper
print: in the mirror at that angle the print was dim and speckled with its own fibre. The chorus hall at exposure
1.8 in its haze went milky where a print came near the lens; 1.5 and a thinner haze keep the blacks. A whip onto a
dawn-lit print needs the shot's own exposure and a drier paper, or the print is white. Glass shards that are lit
cards of picture are cards: the picture faint and a quarter see-through, the glass in the Fresnel reflection.

The second 1280 px cut, read the same way, found what the sheets had hidden for seven passes. A sheet laid on the
water with `rotation_euler = (0, pi/2, 0)` turns its bow and curl downwards, so all but its edges were under the
water: the shot from above showed a sliver of her face beside a grey mirror of the lit ceiling and a window as a
white band. A print that lies down keeps its relief in millimetres (`scale.x`) and sits just over the surface, and
the hall round it goes dark but for its lamp, so the water is black; the ink over her is a small dense pancake, as
the same ink spread 4 m wide was invisible. A glass of water is a black tube unless the camera is level with the
water and the window is behind the glass; then the drop meets the surface and the bloom descends through a lit
column. A crack is not a random walk: it runs straight with a few sharp kinks and short branches, thins to its
tip, and at an emission of 8 under the bloom it was a neon tube (3 is a crack of light). Rain that is right by day
is white rods at night: 0.14 of the emission, and 2.5 for the speed lines. A kraft board without its corrugation as
relief is a flat slab for a bar. A bare margin beside a dark picture, under the same lamp, is a white bar down the
frame: the 2D shot starts off it. The same chorus insert framed the same way four times is four repeats; the second
round is close on her face. 表 and 裏 lit from behind at 6 were a neon sign, and three small lamps behind a cut
letter show as three bands: the lamps overlap, at 1.5, with the shot's glare down.

Two of those were not art but renderer: a bare test scene (the glass alone before a lit slab) is worth its minute.
In Cycles a refraction counts as a glossy bounce as well as a transmission bounce, so at the default 4 glossy
bounces a path through a glass of water (four faces of glass, two of water) died in the far wall whatever the
transmission limit was: the glass was a black tube in three passes, in front of a mullion or not. And a value the
shots set per frame must live in a node socket, a transform or a hide flag: an object custom property read by an
Attribute node is not re-read under persistent render data, so the cracks' `reveal` never changed and no crack
showed in seven passes.

The third 1280 px cut (pass 8) had every one of those in it, and its full frames asked for the finer version of
three. A crack drawn as one flat rose ribbon, however thin and however low its emission, is a stroke: from 8 m the
window crack was pink lightning, its branches at 35-60 degrees. Light through a crack is a hair, so the material
shapes it across the ribbon (a near-white core a tenth of the width, a rose halo over the inner third, transparent
beyond), the branches leave at 15-30 degrees, and the ribbons are wide enough that the core is about a pixel. A
print on black water is a card on a void unless the water shows something: every lamp of the hall is hidden from
glossy rays (a lamp in the water is a bright slab), so for the shot from above the one lamp on the print is made
visible to them, and its reflection beside the print, broken by the water's own ripples and the ring, is what
says water. Ink dropped into a glass starts at the surface and is taller than wide; corrugation at 40 bands and a
bump of 0.4 is corrugated plastic (22 and 0.22 is kraft).

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
