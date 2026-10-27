"""A contact sheet of rendered frames, to judge a run at a glance: every n-th frame, in rows.

    python cases/uraomote/scripts/sheet.py <frames_dir> <out.jpg> [every=24] [columns=6] [width=480]
"""
import os
import sys

from PIL import Image


def main():
    frames, out = sys.argv[1], sys.argv[2]
    every = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    w = int(sys.argv[5]) if len(sys.argv) > 5 else 480
    names = sorted(f for f in os.listdir(frames) if f.endswith(".png"))[::every]
    h = w * 9 // 16
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for i, f in enumerate(names):
        sheet.paste(Image.open(os.path.join(frames, f)).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(out, quality=86)
    print(out, len(names), "frames", sheet.size)


if __name__ == "__main__":
    main()
