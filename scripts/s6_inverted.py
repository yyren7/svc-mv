"""S6「颠倒的卧室」: S1's set in its 裏 materials, upside down. Gravity points up: the desk, the clock, the
milk, the phone and the polaroids have left their places and are falling towards the ceiling, and some two
thousand infected heart bulbs rise through the room like snow, the only light there is. Cycles stills.

    blender -b -P scripts/s6_inverted.py -- [renders/s6] [fall macro]

The room itself is built upright (S1's builder with palette "ura" and a ceiling); the camera is rolled 180
degrees, so the picture shows an upright room whose furniture falls up, exactly as the script describes.
`t` (0..1) is how far the collapse has gone; the stills use 0.55.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402
import s1_bedroom as S1  # noqa: E402

OUT, SHOTS = cyc.args("s6", ["fall", "hang", "macro"])
W, D, H = S1.W, S1.D, S1.H


def lift_group(objs, t, rise, tumble_deg, pivot=None, seed=0):
    """Move a group of objects up by rise * t and tumble it about its centre."""
    rnd = random.Random(seed)
    if not objs:
        return
    if pivot is None:
        pivot = sum((o.matrix_world.translation for o in objs), Vector()) / len(objs)
    rot = Euler((math.radians(rnd.uniform(-1, 1) * tumble_deg * t), math.radians(rnd.uniform(-1, 1) * tumble_deg * t),
                 math.radians(rnd.uniform(-1, 1) * tumble_deg * t))).to_matrix().to_4x4()
    xf = Matrix.Translation(pivot + Vector((0, 0, rise * t))) @ rot @ Matrix.Translation(-pivot)
    for o in objs:
        if o.parent is None:
            o.matrix_world = xf @ o.matrix_world
    return pivot + Vector((0, 0, rise * t))


def build(t=0.55):
    info = S1.build("ura", ceiling=True)
    objs = bpy.context.scene.objects
    by = lambda *prefixes: [o for o in objs if o.name.startswith(prefixes) and o.parent is None]   # noqa: E731
    lift_group(by("desk_"), t, 0.10, 40, seed=1)
    clock_at = lift_group(by("clock"), t, 0.13, 160, seed=2)
    lift_group(by("glass", "milk", "heart_bulb"), t, 0.09, 90, seed=3)
    lift_group(by("phone"), t, 0.07, 120, seed=4)
    lift_group(by("print"), t, 0.05, 60, seed=5)
    lift_group(by("notebook"), t, 0.12, 70, seed=6)
    lift_group(by("stool"), t, 0.06, 25, seed=7)
    pols = by("polaroid")
    for k, p in enumerate(pols[:2]):
        lift_group([p], t, -0.08 - 0.03 * k, 140, seed=10 + k)
    # the bulbs: a cloud rising from the floor, denser near the top; one in the milk stays
    rnd = random.Random(8)
    pts = []
    for _ in range(int(1800 * min(1.0, 0.3 + t))):
        z = rnd.random() ** 0.6 * H
        pts.append((rnd.uniform(-W / 2 + 0.01, W / 2 - 0.01), rnd.uniform(-D / 2 + 0.01, D / 2 - 0.01), z))
    coll = P.bulb_library(0.0042)
    cloud = P.instance_on_points("bulb_cloud", pts, coll, seed=3, scale=(0.7, 1.2))
    # light: the bulbs are the light. A few pink and cyan lamps stand in for their glow, plus the moon.
    cyc.point_light("bulb_glow_a", (-0.05, 0.0, 0.17), 6500, 2.5, radius=0.05, color="#FF3D8B")
    cyc.point_light("bulb_glow_b", (0.08, 0.04, 0.08), 6500, 1.2, radius=0.05, color="#FF3D8B")
    cyc.point_light("bulb_glow_c", (-0.09, 0.06, 0.05), 6500, 0.5, radius=0.04, color="#34E3E8")
    cyc.glass_lets_light_through()
    return dict(info=info, cloud=cloud, clock=clock_at)


def main():
    info = build(0.55)
    scene = bpy.context.scene
    clock = info["clock"]
    # "fall": the room reads upright and the furniture falls up; "hang": the camera rolls over and the room is
    # seen for what it is, hanging upside down; "macro": the tumbling clock among the rising bulbs
    cams = {
        "fall": cyc.camera("cam_fall", (0.03, -0.40, 0.11), (0.0, 0.03, 0.10), 50, 8.0),
        "hang": cyc.camera("cam_hang", (0.03, -0.40, 0.11), (0.0, 0.03, 0.10), 50, 8.0, roll_deg=180),
        "macro": cyc.camera("cam_macro", tuple(clock + Vector((-0.03, -0.15, 0.04))), tuple(clock), 100, 8.0),
    }
    cams["macro"].data.dof.focus_distance = (Vector(cams["macro"].location) - clock).length
    haze = [scene.objects["haze"]]
    cyc.render_shots(cams, SHOTS, OUT, "s6", focus={"fall": (0.0, 0.03, 0.10), "hang": (0.0, 0.03, 0.10)},
                     hide={"macro": haze})


if __name__ == "__main__":
    main()
