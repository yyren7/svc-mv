# Pheebie

A petite Siamese-cat girl from a café tea room. A short ash-blonde bob with a black streak through her bangs,
Siamese cat ears that are cream with dark brown tips, round thin-rimmed glasses over blue eyes, ear piercings.
A white cropped bolero with short puffy sleeves and black cuffs over a black shirt laced crosswise at the chest,
a black bowtie and choker, a black underbust corset. Pinned on the bolero: a blue shield badge with a golden key,
and a pocket watch. Soft, pastel official art.

## Recipe

Qwen keeps her outfit true to the official design, and Anima gives it its line. Two steps:

1. **Qwen-Image-2.1** draws the shot from her reference sheets (`ref`: `ref_pheebie_up_clean.png`,
   `ref_pheebie_full.png` in `ComfyUI/input/`), 1152×896, seed 91. The prompt is "Draw the character from the
   reference pictures in <the shot>, delicate anime illustration. Keep her face, hairstyle, hair colours,
   accessories and outfit exactly as in the reference pictures." Negative:
   `text, letters, name tag, label, watermark, signature, logo`.
2. **Anima** redraws it (`init: "@<qwen job>"`) at `denoise` 0.5 and 0.65, seed 81, with her tags, the shot's tags,
   and her design as a sentence. Use `soft shading, pastel colors, delicate lineart` for day shots and
   `soft shading, delicate lineart` for night shots.

**Leave her name out of the Anima prompt.** With it, Anima letters PHEEBIE onto the badge.
`jobs/t8.py` still puts `pheebie` in `TAGS` and "Pheebie," in `WHO`, so take both out before the next batch.

Close-ups and half-body shots come out well. Full-body long shots are weak.

`jobs/t8.py` writes a round like this from two tables: new shots (a Qwen picture, then two redraws each) and old
Qwen pictures to redraw.

## Picks

`p7_i2i_face_50` and `p7_i2i_face_65` (round t7): the hand to aim for.

## Rounds

| Jobs | Pictures | |
|---|---|---|
| `jobs/t3.json` | `pheebie_*` | First Anima round (its pictures are not in `art/`) |
| `jobs/t4.json` | `p2_*` | Anima; `p2_qref_*` tried Qwen with the reference pictures |
| `jobs/t5.json`, `t5q.json` | `p3_*`, `p3_qref_*` | Anima: cup, singing, paws, heart, glasses; Qwen from the references |
| `jobs/t6.json` | `p6_*` | Qwen scenes: bedroom, phone booth, platform, chibi, face, stage, 裏 |
| `jobs/t7.json` | `p7_*` | Anima again, Qwen bases (`p7_q_*`), and the first redraws (`p7_i2i_*`). The picks are here |
| `jobs/t8.json` (from `t8.py`) | `art/t8/p8_*` | 8 new Qwen close-ups (tilt, watch, cup, sing, shh, table, rain, neon 裏), each redrawn at 0.5 and 0.65, and 8 earlier Qwen pictures redrawn the same way |
| — | `art/riso/` | `riso.separate()` on two of the t5 pictures |

`ref/`: `pheebie_1`–`6.jpg`, `pheebie_sheet.png`, `ref_pheebie*.png` (the pictures given to Qwen: t5q and t7 used
`ref_pheebie_up.png`, t8 its cleaned copy `ref_pheebie_up_clean.png`), `p_debut0930.png`, `p_debut1020.png`, `p_fullbody.png`,
`p_idphoto.png`, `p_poster.png`. `ref/album/` is her downloaded image posts.
