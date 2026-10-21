# 裏表ラバーズ: the first experiment

An MV for 《裏表ラバーズ》 (wowaka). Pheebie's cover stands in for the song until the SVC version exists
(181.0 s, about 161 BPM; the cut is on the downbeats, so the SVC version drops into the same grid).
The case tries the whole pipeline end to end: six procedural sets in Cycles, 2D print material, illustrations, and an
animatic cut on the downbeats.

- [script_v3.md](script_v3.md): the current script (in Chinese). 2D and 3D invade each other: her face only in
  print, the sets as the 3D side.
- [script_v2.md](script_v2.md): v2.3, the six 3D sets S1–S6. Its sets, props, materials and light still hold in v3.
- [CREDITS.md](CREDITS.md): the CC BY assets in the sets. The video's description must carry these lines.

## The six sets, as stills

| | |
|---|---|
| S1 bedroom, 6:59 ![](renders/s1/s1_clock.png) | S1 the set box ![](renders/s1/s1_wide.png) |
| S1 from the pillow ![](renders/s1/s1_pov.png) | S2 the bell jar ![](renders/s2/s2_orbit.png) |
| S2 the first heart on the agar ![](renders/s2/s2_macro.png) | S3 the workshop, day and night ![](renders/s3/s3_wide.png) |
| S3 the resin seam ![](renders/s3/s3_macro.png) | S4 the phone booth ![](renders/s4/s4_long.png) |
| S4 the handset ![](renders/s4/s4_handset.png) | S5 the platform at sunset ![](renders/s5/s5_edge_omote.png) |
| S5 the same platform at night ![](renders/s5/s5_edge_ura.png) | S5 her shoes ![](renders/s5/s5_shoes_omote.png) |
| S6 the bedroom, inverted ![](renders/s6/s6_fall.png) | S6 the clock falling up ![](renders/s6/s6_macro.png) |

Style frames (the 2D side): ![](renders/frame_A_post.png) ![](renders/frame_B_post.png)

## Scripts

| File | What it does |
|---|---|
| `scripts/case.py` | This case's folders; puts the pipeline's `scripts/` on `sys.path` |
| `scripts/s1_bedroom.py` | S1 the bedroom at 6:59 (also builds S6's inverted room in the 裏 palette) |
| `scripts/s2_belljar.py` | S2 the bell jar on the lab bench |
| `scripts/s3_workshop.py` | S3 the risograph workshop split into day and night |
| `scripts/s4_booth.py` | S4 the phone booth in the rain |
| `scripts/s5_platform.py` | S5 the platform, sunset and night |
| `scripts/s6_inverted.py` | S6 the bedroom upside down, the furniture falling up |
| `scripts/styleframes.py` | The two static style frames |
| `scripts/sample.py` | 15-second kinetic sample of the chorus |
| `scripts/animatic.py` | The whole PV at low resolution: every set's shots moving to the song, cut on the downbeats |
| `scripts/animatic_cut.py` | Joins the animatic's frames with the song into an MP4 |

The sets show each other's pictures as prints: S1's polaroids are the S3 stills, and the style frames hang in
S1, S2, S3, S4 and S5. Render the style frames and S3 before the others.

## Running

From the repository root. `audio/` holds `urao_mix.m4a`, `urao_vocal.wav`, `urao_lines.jsonl` (not in git).

```sh
B=D:/tools/blender-5.2.2-windows-x64/blender.exe
C=cases/uraomote
.venv/Scripts/python scripts/analyze.py $C/audio/urao_mix.m4a $C/audio/urao_vocal.wav $C/audio/urao_lines.jsonl $C/audio/urao_timing.json --fps 30
$B -b --factory-startup -P $C/scripts/styleframes.py -- A $C/renders/frame_A.png
$B -b --factory-startup -P $C/scripts/styleframes.py -- B $C/renders/frame_B.png
SAMPLES=256 $B -b --factory-startup -P $C/scripts/s3_workshop.py     # writes $C/renders/s3/
RES=40 SAMPLES=24 $B -b --factory-startup -P $C/scripts/s1_bedroom.py -- tmp/s1 wide   # quick look at 40 %
FPS=12 SAMPLES=24 WIDTH=640 $B -b --factory-startup -P $C/scripts/animatic.py -- s3 $C/renders/animatic/full
.venv/Scripts/python $C/scripts/animatic_cut.py $C/renders/animatic/full $C/audio/urao_mix.m4a $C/renders/animatic/animatic.mp4 12
```

The animatic's parts are `title s1 s2 s3 s4 s5_omote s5_ura s6`. They can run side by side into the same folder.

## Illustrations

Her illustrations (script v3, section 2.3) are drawn on ComfyUI as in [docs/comfyui.md](../../docs/comfyui.md).
`jobs/t1.json` compares Anima and Qwen on one prompt. `jobs/t2.json` and `t3.json` draw the key visual, its 裏
version, her back, the running legs, the hand and the eye, in several seeds each. The pictures are in `art/`,
on the local disk only.
