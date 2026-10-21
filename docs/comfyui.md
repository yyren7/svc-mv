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
| `model` | `anima` or `qwen` |
| `name` | output prefix: the picture lands in `ComfyUI/output/<name>_00001_.png`. Put the seed in it (`kv_41`) |
| `prompt`, `negative` | |
| `w`, `h`, `seed` | about 1 MP: 896×1152, 1152×896, 832×1216, 1024×1024 |
| `steps`, `cfg`, `sampler`, `unet` | optional overrides (`sampler` and `unet` are Anima only) |
| `ref` | Qwen only: a file name, or a list of them, in `ComfyUI/input/`; the encoder looks at these pictures |
| `init` | img2img: a file in `ComfyUI/input/`, or `"@<name>"` for the picture an earlier job in the same file makes (the script waits for it and copies it to `input/`). With `init`, `w` and `h` are ignored |
| `denoise` | with `init`: how much of the picture is redrawn (default 0.55) |

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
(it needs only the standard library). ComfyUI's own log is `/root/autodl-tmp/comfy.log`.

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
