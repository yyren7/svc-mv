"""B 站封面：PV 的一张全景静帧，左边天空里竖排大号歌名（song.json 的 title，每列最多 6 个字，从右往左排，
后面的列往下错开两格），下面一行小字是 artist，带一点柔光。在 AutoDL 上（ComfyUI venv 有 PIL）：

    python templates/kue_stars/cover.py cases/<歌> <静帧.png>      -> <case>/renders/cover/cover_16x9.jpg、cover_4x3.jpg

cover_4x3.jpg（1440×1080）是手机端的裁切，人物和标题都留住。
"""
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "fonts")


def vertical(draw, text, x, y, font, gap, fill):
    for i, ch in enumerate(text):
        w = draw.textlength(ch, font=font)
        draw.text((x - w / 2, y + i * gap), ch, font=font, fill=fill)


def main():
    case, src = sys.argv[1], sys.argv[2]
    song = json.load(open(os.path.join(case, "song.json"), encoding="utf-8"))
    title = [ch for ch in song["title"] if not ch.isspace()]
    img = Image.open(src).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    W, H = img.size
    per = 6
    ncol = (len(title) + per - 1) // per
    size = 80 if len(title) <= 12 else int(80 * 12 / len(title))
    gap = int(size * 1.125)
    big = ImageFont.truetype(os.path.join(FONTS, song.get("title_font", "yumindb.ttf")), size)
    small = ImageFont.truetype(os.path.join(FONTS, song.get("artist_font", "DINNextLTPro-Light.ttf")), 30)
    cols = [("".join(title[k * per:(k + 1) * per]), 650 - 145 * k, 236 + 2 * gap * k) for k in range(ncol)]
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    for text, x, y in cols:
        vertical(ImageDraw.Draw(glow), text, x, y, big, gap, (150, 190, 255))
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    for text, x, y in cols:
        vertical(d, text, x, y, big, gap, (246, 249, 255))
    if song.get("artist"):
        text, x, y = cols[-1]
        w = d.textlength(song["artist"], font=small)
        d.text((x - w / 2, y + len(text) * gap + 26), song["artist"], font=small, fill=(222, 232, 252))
    out = os.path.join(case, "renders", "cover")
    os.makedirs(out, exist_ok=True)
    img.save(os.path.join(out, "cover_16x9.jpg"), quality=95)
    left = 300
    img.crop((left, 0, left + 1440, 1080)).save(os.path.join(out, "cover_4x3.jpg"), quality=95)
    print(out)


if __name__ == "__main__":
    main()
