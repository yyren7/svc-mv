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


def lift_xf(objs, t, rise, tumble_deg, seed=0, pivot=None):
    """The move of a group at time t (0..1): up by rise * t, tumbled about its centre by up to tumble_deg * t."""
    rnd = random.Random(seed)
    if pivot is None:
        pivot = sum((o.matrix_world.translation for o in objs), Vector()) / len(objs)
    rot = Euler((math.radians(rnd.uniform(-1, 1) * tumble_deg * t), math.radians(rnd.uniform(-1, 1) * tumble_deg * t),
                 math.radians(rnd.uniform(-1, 1) * tumble_deg * t))).to_matrix().to_4x4()
    return Matrix.Translation(pivot + Vector((0, 0, rise * t))) @ rot @ Matrix.Translation(-pivot)


def lift_group(objs, t, rise, tumble_deg, pivot=None, seed=0):
    """Move a group of objects up by rise * t and tumble it about its centre."""
    if not objs:
        return
    xf = lift_xf(objs, t, rise, tumble_deg, seed, pivot)
    for o in objs:
        if o.parent is None:
            o.matrix_world = xf @ o.matrix_world


# what leaves its place: (name prefixes, rise, tumble in degrees, seed); two polaroids drop instead
LIFTS = [(("desk_",), 0.10, 40, 1), (("clock",), 0.13, 160, 2), (("glass", "milk", "heart_bulb"), 0.09, 90, 3),
         (("phone",), 0.07, 120, 4), (("print",), 0.05, 60, 5), (("notebook",), 0.12, 70, 6), (("stool",), 0.06, 25, 7)]


def lift_groups():
    """The groups that move, as (objects, rise, tumble_deg, seed). Call before the bulb cloud exists."""
    objs = bpy.context.scene.objects
    by = lambda *prefixes: [o for o in objs if o.name.startswith(prefixes) and o.parent is None]   # noqa: E731
    groups = [(by(*names), rise, tumble, seed) for names, rise, tumble, seed in LIFTS]
    groups += [([p], -0.08 - 0.03 * k, 140, 10 + k) for k, p in enumerate(by("polaroid")[:2])]
    return [g for g in groups if g[0]]


def face_out(dial):
    """The tumble is random: if it has turned the clock's face to a wall, the turn about the vertical through its
    dial that makes the face look out of the open side, where the macro camera can stand. (angle, axis point)."""
    bpy.context.view_layer.update()
    c = dial.matrix_world.translation.copy()
    n = (dial.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    if n.x > 0.35 or n.y > 0.3:
        return math.atan2(-0.94, -0.34) - math.atan2(n.y, n.x), c
    return 0.0, c


def build(t=0.55, lift=True):
    """The room at time t of its collapse. lift=False leaves everything in place (the animatic moves it per frame)
    but still fills the room with t's share of bulbs."""
    info = S1.build("ura", ceiling=True)
    groups = lift_groups()
    if lift:
        for objs, rise, tumble, seed in groups:
            lift_group(objs, t, rise, tumble, seed=seed)
        angle, c = face_out(info["dial_ob"])
        if angle:
            spin = Matrix.Translation(c) @ Matrix.Rotation(angle, 4, "Z") @ Matrix.Translation(-c)
            for o in next(g[0] for g in groups if g[3] == 2):
                o.matrix_world = spin @ o.matrix_world
            bpy.context.view_layer.update()
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
    return dict(info=info, cloud=cloud, dial=info["dial_ob"], groups=groups)


def main():
    info = build(0.55)
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    dial = info["dial"].matrix_world.translation.copy()
    face = (info["dial"].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    # "fall": the room reads upright and the furniture falls up; "hang": the camera rolls over and the room is
    # seen for what it is, hanging upside down; "macro": the tumbling clock's face among the rising bulbs
    eye = dial + face * 0.09 + Vector((0.0, 0.0, 0.01))
    cams = {
        "fall": cyc.camera("cam_fall", (0.03, -0.40, 0.11), (0.0, 0.03, 0.10), 50, 8.0),
        "hang": cyc.camera("cam_hang", (0.03, -0.40, 0.11), (0.0, 0.03, 0.10), 50, 8.0, roll_deg=180),
        "macro": cyc.camera("cam_macro", tuple(eye), tuple(dial), 100, 8.0),
    }
    cams["macro"].data.dof.focus_distance = (eye - dial).length
    haze = [scene.objects["haze"]]
    cyc.render_shots(cams, SHOTS, OUT, "s6", focus={"fall": (0.0, 0.03, 0.10), "hang": (0.0, 0.03, 0.10)},
                     hide={"macro": haze})


if __name__ == "__main__":
    main()
