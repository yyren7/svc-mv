# 旬夏

Shoulder-length chestnut-brown hair with an ahoge, fading to light blue at the ends. A small braid on her right,
tied with a light-blue ribbon bow and a round brown button ornament with a white flower. A light-blue and white
hairclip in her bangs, blue eyes, a black lace choker with a small white flower and a white ribbon. An off-shoulder
sheer white jacket with wide frilled sleeves over a white dress.

## Recipe

Anima text-to-image, with no reference picture: Anima knows her by the tag `sakura shunka`. Write the tags first,
then the same design as a sentence, then the shot:

```
masterpiece, best quality, safe, newest, 1girl, solo, sakura shunka, medium hair, brown hair, gradient hair,
light blue hair, ahoge, side braid, braid, blue ribbon, hair bow, round hair ornament, hair flower, hairclip,
blue eyes, black choker, lace choker, white ribbon, off-shoulder, see-through, white jacket, wide sleeves,
frilled sleeves, white dress, <shot tags>, detailed, soft lighting, simple background, white background.
Sakura Shunka: <the design above in one sentence>. <the shot in one sentence>. A polished full-color character illustration.
```

Negative: `worst quality, low quality, artist name, blurry, jpeg artifacts, chromatic aberration, watermark, text, signature`.
1024×1024, two seeds per shot.

## Picks

`s3_sing_71`, `s3_lookback_71`, `s3_wave_73` (round t5).

## Rounds

| Jobs | Pictures | |
|---|---|---|
| `jobs/t3.json` | `shunka_*` | First Anima round (its pictures are not in `art/`) |
| `jobs/t4.json` | `s2_*` | Anima; `s2_qref_*` tried Qwen with `ref_shunka.png` |
| `jobs/t5.json` | `s3_*` | Anima: hugging a heart, singing, looking back, waving. The picks are here |
| `jobs/t5q.json` | `s3_qref_*` | Qwen from `ref_shunka.png` and `ref_shunka_face.png` |
| `jobs/t6.json` | `s6_*` | Qwen scenes: bedroom, phone booth, platform, 裏, chibi, face, stage, flat colour |
| — | `art/riso/` | `riso.separate()` on two of the t5 pictures |

`ref/`: `shunka_1`–`6.jpg`, `shunka_sheet.png`, the two pictures given to Qwen (`ref_shunka.png`, `ref_shunka_face.png`),
`s_debut.png`, `s_ref.png`. `ref/album/` is her downloaded image posts.
