"""Two style frames for the PV, to pick a direction before animating.

    blender -b -P cases/uraomote/scripts/styleframes.py -- A cases/uraomote/renders/frame_A.png
    blender -b -P cases/uraomote/scripts/styleframes.py -- B cases/uraomote/renders/frame_B.png

A: paper / ink / signal red, print layout.  B: black / neon pink, HUD and glitch.
The heart stands in for the Tripo models.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case  # noqa: E402,F401  (puts the pipeline's scripts/ on sys.path)
import mvlib as m  # noqa: E402

PAPER, INK, RED = "#EEEAE0", "#141414", "#E1251B"
NIGHT, PINK, CYAN, WHITE = "#0B0B10", "#FF2E88", "#00E5FF", "#F4F4F4"


def frame_a():
    m.reset()
    m.sun((35, -30))
    m.background(PAPER)
    m.rect(2.2, -5, 8.5, 5, RED, z=-8)

    # back / front: 裏 in ink on the paper side, 表 in paper on the red side
    m.text("裏", "mincho", 7.4, -3.2, 0.1, INK, z=0, align="CENTER", valign="CENTER")
    m.text("表", "mincho", 7.4, 5.25, -0.2, PAPER, z=0, align="CENTER", valign="CENTER")
    m.halftone(-8, -4.5, -0.5, -1.0, INK, 0.16, "X", -3.75, 3.75, z=-5, rmax=0.48)

    m.text("ラバーズ", "gothic", 0.95, 2.2, -4.05, INK, z=2, align="CENTER", spacing=1.35)

    m.text("URAOMOTE LOVERS", "din", 0.36, -7.45, 3.82, INK, spacing=1.25)
    m.text("COVER  /  PHEEBIE      VOICE  /  DDSP-SVC", "din_light", 0.19, -7.45, 3.45, INK, spacing=1.2)
    m.rect(-7.45, 3.25, 1.6, 3.27, INK, z=1)
    m.rect(-7.45, -3.38, 1.6, -3.36, INK, z=1)
    m.rect(-7.62, -4.27, -4.1, -3.55, PAPER, z=-4)
    m.text("00:01:24:12", "din", 0.48, -7.45, -4.05, INK, spacing=1.05)
    m.text("TRACK 02  —  2026", "din_medium", 0.17, -7.62, -0.4, INK, rot_deg=90, spacing=1.4)

    m.vtext("詞・曲 wowaka", "gothic", 0.24, 7.55, 3.9, PAPER, z=2)
    m.crop_mark(7.3, -3.85, 0.28, 0.025, PAPER)
    m.barcode(4.6, -4.15, 6.6, -3.55, PAPER)
    m.corner_marks(0.22, 0.45, 0.025, INK, corners=("tl", "bl"))
    m.corner_marks(0.22, 0.45, 0.025, PAPER, corners=("tr",))

    m.heart(1.7, 1.3, 1.75, -16, lit="#F7F4EC", dark=INK, outline=INK, outline_px=7)


def frame_b():
    m.reset()
    m.sun((30, 35))
    m.background(NIGHT)
    m.halftone(-8, -4.5, 8, -1.2, PINK, 0.14, "Y", -1.65, 1.65, z=-5, rmax=0.42)

    title = "裏表ラバーズ"
    m.text(title, "gothic", 3.0, -7.6 - 0.08, 0.75 + 0.06, CYAN, z=0.0)
    m.text(title, "gothic", 3.0, -7.6 + 0.08, 0.75 - 0.06, PINK, z=0.1)
    m.text(title, "gothic", 3.0, -7.6, 0.75, WHITE, z=0.2)

    m.rect(-12, -2.35, 12, -1.45, PINK, z=1, rot_deg=7)
    band = "URAOMOTE LOVERS  ◆  裏表ラバーズ  ◆  " * 4
    m.text(band, "gothic", 0.48, 0, -1.9, NIGHT, z=1.1, rot_deg=7, align="CENTER", valign="CENTER")

    m.heart(4.9, -0.3, 2.2, 14, lit="#FF4FA0", dark="#7A0F45", outline=WHITE, outline_px=6, tilt=(10, 25))
    m.ring(4.9, -0.3, 2.95, 2.92, WHITE, z=12)
    for dx, dy, w, h in ((3.2, 0, 0.45, 0.03), (-3.2, 0, 0.45, 0.03), (0, 3.2, 0.03, 0.45), (0, -3.2, 0.03, 0.45)):
        m.rect(4.9 + dx - w / 2, -0.3 + dy - h / 2, 4.9 + dx + w / 2, -0.3 + dy + h / 2, WHITE, z=12)

    m.corner_marks(0.35, 0.7, 0.035, WHITE)
    m.text("SVC://PHEEBIE.MODEL   F0=RMVPE   SR=44100", "mono", 0.2, -7.4, 3.8, CYAN)
    m.text("●REC", "gothic", 0.22, 4.9, 3.8, PINK)
    m.text("00:01:24:12", "mono", 0.22, 7.4, 3.8, WHITE, align="RIGHT")
    m.rect(-7.6, -4.25, -3.2, -3.2, NIGHT, z=0.5)
    m.text("TRACK 02\nWORDS & MUSIC / wowaka\nCOVER / PHEEBIE", "mono", 0.17, -7.4, -3.55, WHITE, line=1.1)
    m.rect(-7.4, -4.08, -3.4, -4.04, "#3A3A44", z=1)
    m.rect(-7.4, -4.08, -5.0, -4.04, PINK, z=1.1)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    which, out = argv[0], argv[1]
    {"A": frame_a, "B": frame_b}[which]()
    m.render(out)
