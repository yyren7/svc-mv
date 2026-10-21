"""Tile pictures into a labelled contact sheet, each fitted into the same cell.
    python scripts/art_sheet.py <out.png> <cols> <picture>..."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
cw, ch, bar = 360, 400, 26
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cw, rows * (ch + bar)), (18, 18, 20))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothicB.ttc", 17)
except OSError:
    font = ImageFont.load_default()
for k, f in enumerate(files):
    im = Image.open(f).convert("RGB")
    s = min(cw / im.width, ch / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (k % cols) * cw, (k // cols) * (ch + bar)
    sheet.paste(im, (x + (cw - im.width) // 2, y + bar + (ch - im.height) // 2))
    d.text((x + 6, y + 4), os.path.basename(f).replace("_00001_.png", "").replace(".png", ""), fill=(240, 240, 240), font=font)
sheet.save(out)
print(out, sheet.size)
