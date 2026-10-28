"""Characters as a mask image, to cut them out of a surface in a shader (a transparent BSDF where the mask is
white): a wall with 表 裏 cut through it, a sheet with its title cut out. Metres map to pixels, so the mask lays
over the surface by its object coordinates.

    python scripts/text_mask.py <out.png> <font> <width_m> <height_m> <px_per_m> <char> <x_m> <y_m> <size_m> [...]

(x, y) is the character's centre from the surface's bottom-left corner, `size` its height, both in metres;
several characters follow each other. Booleans with a CJK glyph's overlapping contours failed silently (one of
two letters vanished, the other lost strokes); the mask does not.
"""
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    out, font_path = sys.argv[1], sys.argv[2]
    w_m, h_m, ppm = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    W, H = int(round(w_m * ppm)), int(round(h_m * ppm))
    img = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(img)
    items = sys.argv[6:]
    for k in range(0, len(items), 4):
        ch, x, y, size = items[k], float(items[k + 1]), float(items[k + 2]), float(items[k + 3])
        font = ImageFont.truetype(font_path, int(size * ppm))
        # the glyph's own box, so `size` is the drawn height and (x, y) its centre
        x0, y0, x1, y1 = draw.textbbox((0, 0), ch, font=font)
        gh = y1 - y0
        scale = size * ppm / max(gh, 1)
        font = ImageFont.truetype(font_path, max(1, int(size * ppm * scale)))
        x0, y0, x1, y1 = draw.textbbox((0, 0), ch, font=font)
        cx, cy = x * ppm, (h_m - y) * ppm
        draw.text((cx - (x0 + x1) / 2, cy - (y0 + y1) / 2), ch, fill=255, font=font)
        print(ch, "at", round(cx), round(cy), "height px", y1 - y0)
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    main()
