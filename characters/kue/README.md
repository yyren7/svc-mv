# 小铃久绘 (Kosuzu Hisae)

小铃久绘Official on bilibili (UID 1875094289, live room 22754458), a cat girl who works in a dessert shop. Debut
2021-03-20. Her debut look: very long wine-red hair that turns pink towards the ends, blunt bangs and an ahoge, small
braided buns on both sides, pink cat ears with white fluff inside, a big light-blue ribbon bow on top of her head, a
small white flower hairclip, big blue eyes, a long wine-red cat tail. A white lace collar with a light-blue buckled
ribbon, a light-blue and white dress. Later outfits (魔法猫猫 2023, bunny 2024, elf 2024, 偶像服2.0 2025-10) are in
the album; none of them is drawn here.

No three-view sheet turned up: not in her 2729 image posts (2021-02 to 2026), and her fan-art call articles have
none. The debut bust-up from 2021-02-23 is the reference.

## Recipe

Qwen-Image-2.1 from two pictures (`ref`, in `ComfyUI/input/`):

1. `ref_kue_face.png`: her bust-up (`ref/album/20210223_115934413_1.png`), for her face, hair, ears and ornaments.
2. `ref_shunka_sing.png`: Shunka's `s3_sing_71` (`characters/shunka/art/`), for the singing pose and the feel of
   the outfit (the sheer white off-shoulder jacket with frilled sleeves, the black lace choker, the light-blue
   ribbon bow with white flowers), which the user asked for.

The prompt names everything to keep from picture 1, the pose and outfit from picture 2, then the scene.
`jobs/kv.py` holds it. At 1664×928 she comes out right in most seeds. Round 1 gave half of them open eyes and a
microphone stand, so round 2 asks for a cordless microphone and puts `microphone stand, pole, open eyes` in the
negative. Some seeds take a light-blue streak into her hair from Shunka's (`sweets_107`), and `sweets_107` keeps her
own buckled collar over the black choker.

For a 4K picture: the pick is drawn again at 2496×1392 with the same prompt (`upscale` + `denoise` 0.3), then
enlarged to 3840×2160 (`model: "upscale"`, `crop: "center"`). Anima did worse at both steps (`_cmp_refine.png`).

## Picks

The three key visuals, 3840×2160 (`art/kue_pv_*_4k_00001_.png`, with 1920×1080 copies `kue_pv_*_1080p.png`):

| | |
|---|---|
| `stars_103` | a hill of white flowers under a starry sky and a big moon. The one-picture PV of 君の知らない物語 uses it |
| `stage_103` | a concert stage with light-blue spotlights and a sea of light sticks |
| `sweets_107` | a dessert-shop wonderland at dusk, her own setting |

## Layers

`art/layers/<pick>/` splits each pick for Blender (`scripts/layers.py`, specs `jobs/layers_*.json`): `far.png`
(opaque), `mid.png`, `near.png`, `char.png` (RGBA), each 3840×2160 and filled in where a nearer layer hid it, with
`depth.png`, `*_depth.png` and `layers.json` (order, z, bbox). Thresholds: stars far 0.15 near 0.35 (sky and moon;
the field; the big corner flowers), sweets 0.15 / 0.25 (the far street; the cake towers; the corner cakes and
lanterns), stage 0.10 / 0.13 (haze and bokeh split less cleanly: the truss and crowd; the ribbons).

## Rounds

| Jobs | Pictures | |
|---|---|---|
| `jobs/t1.json` | `kue_q_*_101`, `_103` | Qwen: stage, sweets, stars, two seeds each |
| `jobs/t2.json` | `kue_q_*_107`, `_109`, `kue_a_*`, `kue_h_stage_103_*` | Qwen with the microphone pinned down; Anima redraws and the 2496×1392 redraws of `stage_103` compared |
| `jobs/t3.json` | `kue_h_stars_103_q30`, `kue_h_sweets_107_q30`, `kue_pv_*_4k` | the picks at 2496×1392, then 4K |

`jobs/kv.py` writes all three. `_sheet_q1.png` and `_sheet_q2.png` are the contact sheets of t1 and t2.
`ref/album/` is her downloaded image posts from 2021-02 to 2021-03 and a few outfit posts.
