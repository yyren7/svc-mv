# Illustrations on ComfyUI

Character illustrations (key visuals, poses, close-ups) are drawn on ComfyUI on a rented GPU. `scripts/riso.py`'s
`separate()` then prints them in the riso inks, so they match the rest of the 2D material.

## The server

- AutoDL, an RTX 4090D (24 GB). ComfyUI lives at `/root/autodl-tmp/ComfyUI` with its own `venv/`.
- `scripts/comfy_batch.sh` starts ComfyUI, draws the job files and stops it, so ComfyUI holds the GPU only while it
  draws. Check `nvidia-smi` before a batch. Blender renders run on the same card.

## The two models

| | Anima | Qwen-Image-2.1 |
|---|---|---|
| Good at | Anime flat colour with crisp lines | Keeping an existing character's outfit and accessories right, from reference pictures |
| Prompt | Danbooru tags, then a sentence or two | Plain sentences |
| Files | `anima-aesthetic-v1.1.safetensors`, `qwen_3_06b_base.safetensors`, `qwen_image_vae.safetensors` | `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_w4a8.safetensors`, `qwen_image_2.1_vae_bf16.safetensors` |
| Defaults in `comfy_gen.py` | 30 steps, cfg 4, `er_sde`, `simple` | 25 steps, cfg 1, `euler`, `simple` |

Why these two (checked 2026-10-21): Qwen-Image-2.1 is first on the Artificial Analysis open-weights text-to-image
board (T2I v2.1, Elo 1042, 2026-09), which has no anime category. Anima (CircleStone Labs and Comfy Org, 2B
parameters, released 2026-05-15) is the newest anime-specific model. Both licences are non-commercial, so private
use is fine. Replace the illustrations before any commercial release.

## A jobs file

A JSON list, one picture per job:

| Field | |
|---|---|
| `model` | `anima`, `qwen`, or `upscale` (only enlarges `init` with `upscale`; nothing is redrawn) |
| `name` | output prefix: the picture lands in `ComfyUI/output/<name>_00001_.png`. Put the seed in it (`kv_41`) |
| `prompt`, `negative` | |
| `w`, `h`, `seed` | about 1 MP: 896×1152, 1152×896, 832×1216, 1024×1024 |
| `steps`, `cfg`, `sampler`, `unet` | optional overrides (`sampler` and `unet` are Anima only) |
| `ref` | Qwen only: a file name, or a list of them, in `ComfyUI/input/`; the encoder looks at these pictures |
| `init` | img2img: a file in `ComfyUI/input/`, or `"@<name>"` for the picture an earlier job in the same file makes (the script waits for it and copies it to `input/`). With `init`, `w` and `h` are ignored unless `upscale` is set |
| `denoise` | with `init`: how much of the picture is redrawn (default 0.55) |
| `upscale` | with `init`: an upscale model in `ComfyUI/models/upscale_models/` (`4x-AnimeSharp.pth`); the picture is enlarged to `w`×`h` before it is redrawn |
| `crop` | with `upscale`: `"center"` keeps the picture's aspect when `w`×`h` has another one; the default `"disabled"` stretches it |
| `mask` | with `init`: a picture in `ComfyUI/input/`, white where to draw. Only that part is redrawn; at `denoise` 1.0 it is drawn from scratch |

A Qwen picture from reference sheets, then Anima redrawing it:

```json
[
 {"model": "qwen", "name": "x_q_tilt", "ref": ["ref_up.png", "ref_full.png"], "w": 1152, "h": 896, "seed": 91,
  "negative": "text, letters, name tag, label, watermark, signature, logo",
  "prompt": "Draw the character from the reference pictures in a close-up of her face and shoulders ... delicate anime illustration. Keep her face, hairstyle, hair colours, accessories and outfit exactly as in the reference pictures."},
 {"model": "anima", "name": "x_tilt_50", "init": "@x_q_tilt", "denoise": 0.5, "seed": 81, "w": 1024, "h": 1024,
  "negative": "worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration, watermark, text, signature",
  "prompt": "masterpiece, best quality, safe, newest, 1girl, solo, <her tags>, portrait, close-up, ..., soft shading, delicate lineart. <her design in a sentence or two>"}
]
```

For a batch of more than a few jobs, write a small Python script that builds the file from tables of shots.

A jobs file lives with what it draws: `characters/<name>/jobs/` for a character, `cases/<name>/jobs/` for a
case's own illustrations, one file per round (`t1.json`, `t2.json`, ...). The pictures pulled back go in the
`art/` folder beside it, and the reference pictures go in the character's `ref/`. Both stay off git.

## Running a batch

```sh
# reference pictures go to ComfyUI/input/ first
scp -P <port> ref_*.png root@<host>:/root/autodl-tmp/ComfyUI/input/
scp -P <port> scripts/comfy_gen.py scripts/comfy_batch.sh jobs.json root@<host>:/root/autodl-tmp/
ssh -p <port> root@<host>
cd /root/autodl-tmp
sed -i 's/\r$//' comfy_gen.py comfy_batch.sh jobs.json      # files from Windows carry CRLF; bash will not run them
nohup bash comfy_batch.sh jobs.json > batch.log 2>&1 &     # several job files run one after another
# when batch.log ends with "== done" and "comfyui stopped":
scp -P <port> 'root@<host>:/root/autodl-tmp/ComfyUI/output/<prefix>*' <local folder>
.venv/Scripts/python scripts/art_sheet.py <folder>/_sheet.png 4 <folder>/*.png    # a contact sheet to choose from
```

`comfy_batch.sh` expects `comfy_gen.py` in `/root/autodl-tmp/` and runs it with `/root/miniconda3/bin/python`
(it needs only the standard library). ComfyUI's own log is `/root/autodl-tmp/comfy.log`. It hands each file to
`$CLIENT` instead when that is set (see [Layers for Blender](#layers-for-blender)).

The upscale models in `ComfyUI/models/upscale_models/` are Kim2091's `4x-AnimeSharp.pth` and
`2x-AnimeSharpV4_RCAN.safetensors`, from `hf-mirror.com` (the server cannot reach huggingface.co).

## Recipes that worked

- **A character Anima already knows by tag**: text-to-image with Anima directly.
- **A character whose outfit has to match an official design**: Qwen-Image-2.1 draws the picture from the
  reference sheets (`ref`), then Anima redraws it (`init: "@<qwen job>"`). At `denoise` 0.5 the design stays
  closer to Qwen's; at 0.65 more of Anima's own hand comes through. Both keep the outfit, and the result has
  Anima's line instead of Qwen's.
- **Keep the character's name out of the Anima prompt**: Anima letters the name onto badges and tags in the picture.
- **Keep text out of Qwen too**: `text, letters, name tag, label, watermark, signature, logo` in the negative.
- **Close-ups and half-body shots come out well; full-body long shots are weak** (small faces, details lost).
  Frame a shot tighter, or build the wide shot in 3D and put the character in as a cut-out.
- Draw two or three seeds of every prompt and pick from the contact sheet.
- **A 4K picture for a video**: Qwen at 1664×928; the pick drawn again at 2496×1392 with the same prompt
  (`init` + `upscale`, `denoise` 0.3), which sharpens the line and keeps the design; then `model: "upscale"` to
  3840×2160 with `crop: "center"`. Anima at the second step changed the hair ornaments, and Anima redrawing at
  1664×928 came out softer. `characters/kue/jobs/kv.py` is the example.

## Layers for Blender

`scripts/layers.py` splits a finished picture into a character, near, mid and far layer, each the full size of the
picture and filled in where a nearer layer hid it, plus their depth maps, for animating the layers one by one. It
runs on the server with ComfyUI up, so it goes through `comfy_batch.sh` with a different client:

```sh
scp scripts/layers.py scripts/comfy_gen.py scripts/comfy_batch.sh <spec.json> root@<host>:/root/autodl-tmp/
CLIENT="env PYTHONPATH=/root/autodl-tmp/pv/pylib /root/autodl-tmp/ComfyUI/venv/bin/python /root/autodl-tmp/layers.py" \
    nohup bash comfy_batch.sh <spec.json> > layers.log 2>&1 &
```

The first run (a spec without `near` and `far`) cuts the character out (anime-seg), fills the plate behind her
(Qwen, `mask`), and writes the depth (Depth Anything V2) with its quantiles. Pick `far` and `near` from the
quantiles and a look at the plate, add them to the spec, and run it again for the layers; the second run keeps the
first run's files. Delete a file in the out dir to make it again (`far.png` after changing the thresholds).
The models are the one-picture PV's, in `/root/autodl-tmp/pv/models/` (`scripts/onepic_setup.sh`).
Depth splits a scene with solid things in it well (a flower field, cake towers); a stage of haze and bokeh splits
less cleanly. The specs for the 小铃久绘 pictures are in `characters/kue/jobs/layers_*.json`.

In Blender (the one-picture PV of stars_103): where `far.png` fills in what mid hides, its depth is almost mid's,
so the two meshes z-fight in a blocky pattern; set far about 20% further back. Depth Anything puts big foreground
flowers behind the character; that PV pulls near 2.2× closer than its depth.
