"""B 站封面：PV 的一张全景静帧，左边天空里竖排大号标题，带一点柔光。在 AutoDL 上（ComfyUI venv 有 PIL）：

    python cases/kimishira/scripts/cover.py <静帧.png> <输出目录>

输出 cover_16x9.jpg（1920×1080）和 cover_4x3.jpg（1440×1080，手机端的裁切，人物和标题都留住）。
"""
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "fonts")
TITLE = "君の知らない物語"


def vertical(draw, text, x, y, font, gap, fill):
    for i, ch in enumerate(text):
        w = draw.textlength(ch, font=font)
        draw.text((x - w / 2, y + i * gap), ch, font=font, fill=fill)


def main():
    src, out = sys.argv[1], sys.argv[2]
    img = Image.open(src).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    W, H = img.size
    big = ImageFont.truetype(os.path.join(FONTS, "yumindb.ttf"), 80)
    small = ImageFont.truetype(os.path.join(FONTS, "DINNextLTPro-Light.ttf"), 30)
    # 竖排两列，从右往左：「君の知らない」，「物語」往下错开两格；都留在左边深色的天空里
    gap = 90
    cols = [("君の知らない", 650, 236), ("物語", 505, 236 + 2 * gap)]
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    for text, x, y in cols:
        vertical(ImageDraw.Draw(glow), text, x, y, big, gap, (150, 190, 255))
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    for text, x, y in cols:
        vertical(d, text, x, y, big, gap, (246, 249, 255))
    w = d.textlength("supercell", font=small)
    d.text((505 - w / 2, 236 + 4 * gap + 26), "supercell", font=small, fill=(222, 232, 252))
    os.makedirs(out, exist_ok=True)
    img.save(os.path.join(out, "cover_16x9.jpg"), quality=95)
    left = 300
    img.crop((left, 0, left + 1440, 1080)).save(os.path.join(out, "cover_4x3.jpg"), quality=95)
    print(out)


if __name__ == "__main__":
    main()
