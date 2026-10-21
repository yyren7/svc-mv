"""S2「钟罩里的培养皿」: a thick blown-glass bell jar on a walnut plinth on a white-tiled lab bench. Inside,
a petri dish of amber agar with the first, still clean, heart bulb, and strips of risograph paper curled into
brain folds against the glass. Cycles stills.

    blender -b -P cases/uraomote/scripts/s2_belljar.py -- [out_dir] [macro orbit]

infection (0..1) later drives the colony and the pink glow; the stills use 0. Metres, Z up.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402

OUT, SHOTS = cyc.args(os.path.join(C.RENDERS, "s2"), ["macro", "orbit"])
JAR_R, JAR_H, WALL, CYL = 0.055, 0.18, 0.004, 0.115
PLINTH_H = 0.018
JAR = Vector((0.0, 0.02, 0.0))        # centre of the plinth's base on the bench
TOP = JAR + Vector((0.0, 0.0, PLINTH_H))   # where the jar and the dish stand


def dome(r, z0, z1, n=28):
    """(radius, z) along a quarter ellipse from the cylinder top to the axis."""
    return [(max(r * math.cos(math.pi / 2 * k / n), 0.0001), z0 + (z1 - z0) * math.sin(math.pi / 2 * k / n))
            for k in range(n + 1)]


def bell_jar(parent, seed=2):
    rnd = random.Random(seed)
    glass = A.clear_glass(0.0)
    # blown glass: the slightest waves only; the stock bump made the view through the wall muddy
    nz = next(n for n in glass.node_tree.nodes if n.type == "BUMP")
    nz.inputs["Strength"].default_value = 0.01
    outer = [(JAR_R, 0.0), (JAR_R, CYL)] + dome(JAR_R, CYL, JAR_H)
    inner = dome(JAR_R - WALL, CYL, JAR_H - WALL)[::-1] + [(JAR_R - WALL, CYL), (JAR_R - WALL, 0.0), (JAR_R, 0.0)]
    jar = A.lathe("jar", outer + inner, 96, [glass], parent)
    sub = jar.modifiers.new("sub", "SUBSURF")
    sub.levels, sub.render_levels = 1, 2
    A.lathe("jar_neck", [(0.0001, JAR_H - 0.002), (0.0045, JAR_H - 0.002), (0.0045, JAR_H + 0.004), (0.0001, JAR_H + 0.004)],
            32, [glass], parent)
    P.sphere("jar_knob", 0.0095, [glass], parent, segments=32).location = (0, 0, JAR_H + 0.011)
    # air bubbles trapped in the wall: inside-out spheres of the same glass
    bm = bmesh.new()
    for _ in range(90):
        z = rnd.uniform(0.008, JAR_H - 0.01)
        rm = JAR_R - WALL / 2
        if z > CYL:
            rm *= math.cos(math.asin(min(1.0, (z - CYL) / (JAR_H - CYL))))
        th = rnd.uniform(0, 2 * math.pi)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rnd.uniform(0.00015, 0.0006),
                                   matrix=Matrix.Translation((rm * math.cos(th), rm * math.sin(th), z)))
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("jar_bubbles")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    A._obj("jar_bubbles", me, [glass], parent)
    # the cork and its glass tube, set into the dome beside the knob
    a = math.radians(52)
    pos = Vector((JAR_R * math.cos(a), 0, CYL + (JAR_H - CYL) * math.sin(a)))
    tilt = Matrix.Rotation(math.radians(90) - a, 4, "Y")
    cork = A.lathe("cork", [(0.0001, -0.004), (0.0036, -0.004), (0.0042, 0.006), (0.0001, 0.006)], 24,
                   [A.plastic("#C8A878", 0.85, "cork")], parent)
    cork.matrix_basis = Matrix.Translation(pos) @ tilt
    tube = A.lathe("cork_tube", [(0.0009, -0.012), (0.0012, -0.012), (0.0012, 0.03), (0.0009, 0.03), (0.0009, -0.012)],
                   16, [glass], parent)
    tube.matrix_basis = Matrix.Translation(pos) @ tilt
    return jar


def gyri(parent, images, seed=5, count=7):
    """Risograph strips curled into brain folds, stuck to the inside of the glass."""
    rnd = random.Random(seed)
    r_in = JAR_R - WALL - 0.0008
    for k in range(count):
        z0 = rnd.uniform(0.055, 0.125)   # above the dish, which the macro looks at from the front
        th0 = rnd.uniform(math.radians(15), math.radians(165))   # the back half: the macro looks in from -Y
        span = math.radians(rnd.uniform(45, 95))
        w = rnd.uniform(0.010, 0.016)
        folds = rnd.uniform(3.0, 6.0)
        ph = rnd.uniform(0, 6)

        def pt(i, j, z0=z0, th0=th0, span=span, w=w, folds=folds, ph=ph):
            u, v = i / 48, j / 8
            th = th0 + span * u
            depth = 0.0035 * (0.5 + 0.5 * math.sin(folds * span * u + ph)) * (1 - abs(v - 0.5) * 0.6)
            r = r_in - depth
            if z0 > CYL - 0.01:
                r = min(r, (JAR_R - WALL) * math.cos(math.asin(min(1.0, max(0.0, (z0 - CYL) / (JAR_H - CYL))))) - 0.001)
            return (r * math.cos(th), r * math.sin(th), z0 + w * (v - 0.5) + 0.0025 * math.sin(2.3 * span * u + ph))

        strip = P.grid_mesh(f"gyrus{k}", 48, 8, pt, [A.printed(images[k % len(images)], rough=0.9)], parent)
        P.map_uv_grid(strip, 48, 8)
        strip.modifiers.new("solid", "SOLIDIFY").thickness = 0.00025


def petri(parent, infection=0.0):
    glass = A.clear_glass(0.01)
    dish = A.lathe("petri", [(0.0001, 0.0), (0.029, 0.0), (0.030, 0.0008), (0.030, 0.012), (0.0291, 0.012),
                             (0.0291, 0.0009), (0.0001, 0.0009)], 96, [glass], parent)
    # half-set agar: milky amber, scattering over ~1 mm so it reads as a puck and not as the walnut under it
    agar_mat, b = A._principled("agar", **{"Base Color": m.srgb("#D9A64A"), "Roughness": 0.2,
                                           "Subsurface Weight": 1.0, "Subsurface Scale": 0.12,
                                           "Coat Weight": 0.6, "Coat Roughness": 0.04})
    b.inputs["Subsurface Radius"].default_value = (0.010, 0.006, 0.003)
    if infection > 0:
        b.inputs["Emission Color"].default_value = m.srgb("#FF3D8B")
        b.inputs["Emission Strength"].default_value = 3.0 * infection
    agar = A.lathe("agar", [(0.0001, 0.001), (0.0289, 0.001), (0.0289, 0.0068), (0.0001, 0.0072)], 96, [agar_mat], parent)
    _ = dish
    bulb = A.heart_bulb("clean" if infection < 0.3 else "fever", 0.006, seed=1)
    bulb.parent = parent
    bulb.location = (0.004, -0.005, 0.0072 + 0.0028)
    bulb.rotation_euler = (math.radians(88), 0, math.radians(35))
    return agar, bulb


def plinth(parent):
    walnut = A.stained_wood("#1E130C", (), (), light="#3A2416", rough=0.35)
    base = A.lathe("plinth", [(0.0001, 0.0), (0.075, 0.0), (0.078, 0.004), (0.080, 0.012), (0.076, PLINTH_H),
                              (0.0001, PLINTH_H)], 96, [walnut], parent)
    base.modifiers.new("bev", "BEVEL").width = 0.0008
    plaque = A.rounded_box("plaque", (0.034, 0.0012, 0.012), 0.0004, [A.brass()], parent)
    plaque.location = (0, -0.0790, 0.0085)
    ink = A.plastic("#1B1A19", 0.6, "engraving")
    for body, face, z in (("No. 0", "din", 0.0113), ("裏表", "mincho", 0.0058)):
        t = m.text(body, face, 0.0036, 0.0, 0.0, "#1B1A19", z=0.0, align="CENTER", valign="CENTER")
        t.data.materials.clear()
        t.data.materials.append(ink)
        t.parent = parent
        t.rotation_euler = (math.radians(90), 0, 0)
        t.location = (0, -0.0798, z)
    return base


def bench_props(seed=7):
    rnd = random.Random(seed)
    brass = A.brass()
    glass = A.clear_glass(0.01)
    # tweezers: two tapered arms meeting at the joint
    root = bpy.data.objects.new("tweezers", None)
    m._link(root)
    root.location = (0.115, -0.045, 0.0)
    root.rotation_euler.z = math.radians(-40)
    for sy in (-1, 1):
        arm = P.grid_mesh("tweezer_arm", 20, 1, lambda i, j, sy=sy: (
            0.07 * i / 20, sy * (0.0012 + 0.0045 * (i / 20) ** 0.8) + (j - 0.5) * 0.0025 * (0.4 + 0.6 * i / 20),
            0.0004 + 0.0006 * (i / 20)), [brass], root, smooth=False)
        arm.modifiers.new("solid", "SOLIDIFY").thickness = 0.0007
    # pipettes: glass tubes with rubber teats, lying crossed
    for k in range(3):
        tube = A.lathe(f"pipette{k}", [(0.0011, 0), (0.0014, 0), (0.0014, 0.065), (0.0011, 0.065), (0.0011, 0)], 16, [glass])
        teat = A.lathe(f"teat{k}", [(0.0001, 0.062), (0.0028, 0.064), (0.0032, 0.074), (0.0024, 0.078), (0.0001, 0.078)], 24,
                       [A.plastic("#2A2628", 0.8, "rubber")])
        for ob in (tube, teat):
            ob.rotation_euler = (math.radians(90), 0, math.radians(-15 + 25 * k))
            ob.location = (-0.12 + 0.01 * k, -0.03 - 0.012 * k, 0.0016 + 0.001 * k)
    # the note card with scrawled notes
    card = A.rounded_box("note_card", (0.042, 0.030, 0.0005), 0.0002, [P.paper("#F5F1E6", name="note")])
    card.location = (-0.105, -0.095, 0.00025)
    card.rotation_euler.z = math.radians(14)
    P.handwriting((-0.105, -0.095, 0.0005), lines=5, length=0.032, seed=4, parent=None)
    # a stray bulb caught in a grout line
    stray = A.heart_bulb("clean", 0.006, seed=3)
    stray.location = (0.10, -0.08, 0.0028)
    stray.rotation_euler = (math.radians(95), 0, math.radians(rnd.uniform(0, 360)))


def build(infection=0.0):
    m.reset()
    cyc.cycles()
    cyc.world()
    bench = A.rounded_box("bench", (0.5, 0.4, 0.02), 0.001, [P.tiles()])
    bench.location = (0, 0.1, -0.01)
    root = bpy.data.objects.new("jar_root", None)
    m._link(root)
    root.location = JAR
    plinth(root)
    inner = bpy.data.objects.new("jar_inner", None)   # everything on the plinth top
    m._link(inner)
    inner.parent = root
    inner.location = (0, 0, PLINTH_H)
    jar = bell_jar(inner)
    gyri(inner, [os.path.join(C.RENDERS, "frame_A.png"), os.path.join(C.RENDERS, "frame_B.png")])
    agar, bulb = petri(inner, infection)
    bench_props()
    # light: one hard round lab lamp overhead, a big soft panel behind the jar, thin haze for the beams
    cyc.area_light("lab_lamp", (0.0, JAR.y, 0.42), (0.0, JAR.y, 0.0), 0.05, 5500, 3.0, shape="DISK", spread_deg=110)
    cyc.area_light("back_panel", (0.0, JAR.y + 0.36, 0.16), (0.0, JAR.y, 0.09), 0.40, 5000, 2.0, size_y=0.30)
    cyc.area_light("front_fill", (0.10, JAR.y - 0.40, 0.12), (0.0, JAR.y, TOP.z + 0.03), 0.25, 5200, 0.6)
    # a small examination light on the dish itself, from the front-top, so the agar is the brightest thing
    cyc.area_light("exam", (0.06, JAR.y - 0.16, 0.30), (0.0, JAR.y, TOP.z + 0.006), 0.03, 5000, 0.3, spread_deg=40)
    cyc.glass_lets_light_through()
    cyc.post(bloom=0.45, threshold=0.9)
    _ = (jar, agar)
    return dict(bulb=TOP + Vector(bulb.location))


def main():
    info = build(0.0)
    bulb = info["bulb"]
    macro_eye = Vector((TOP.x + 0.006, TOP.y - JAR_R - 0.025, TOP.z + 0.02))
    cams = {
        # the script's macro: the lens close to the jar's wall, the first heart seen through the glass, the
        # bubbles in the wall out of focus in front of it
        "macro": cyc.camera("cam_macro", tuple(macro_eye), tuple(bulb), 100, 32.0),
        "orbit": cyc.camera("cam_orbit", (0.27, -0.23, 0.15), (TOP.x, TOP.y, TOP.z + 0.085), 35, 8.0),
    }
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("jar", "petri")
    eye = Vector(cams["orbit"].location)
    cams["orbit"].data.dof.focus_distance = (Vector((TOP.x, TOP.y, eye.z)) - eye).length - JAR_R
    # the filament glows 4.5 mm behind the straight line to the bulb's origin once the curved wall (4 mm of
    # glass) has moved its image: found by bracketing. At f/32 the depth of field is about two millimetres
    cams["macro"].data.dof.focus_distance = (Vector(bulb) - macro_eye).length + 0.0045
    cyc.render_shots(cams, SHOTS, OUT, "s2", exposure={"macro": -0.9})


if __name__ == "__main__":
    main()
