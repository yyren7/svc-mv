"""S5「这边与那边的站台」: a single-sided country platform at 1:12, 60 cm long. Tactile tiles along the edge,
a rusty station sign that says うら, a light-box direction sign with two loose arrows, a slatted bench with her
bag, a two-car cream-and-vermilion local train whose windows are hung with heart bulbs, a steel canopy with a
row of fluorescent tubes. Her canvas shoes stand side by side on the tactile tiles where she jumped.

    blender -b -P scripts/s5_platform.py -- [renders/s5] [edge_omote edge_ura shoes_omote]

omote = sunset from the end of the rails, 3200K; ura = night, only the tubes, the train windows and the bulbs.
Metres, Z up; the platform runs along X, the tracks are on its -Y side.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402

OUT, SHOTS = cyc.args("s5", ["edge_omote", "edge_ura", "shoes_omote"])
PL, PW, PH = 0.60, 0.25, 0.09          # platform length, width, height above the rail bed
EDGE = -PW / 2                           # the platform edge (tracks beyond it, at smaller y)
RAIL_Y = (-0.19, -0.25)
SHOES = Vector((0.03, EDGE + 0.03, PH))  # where the shoes stand on the tactile strip


def dot_bump(mat, bsdf, pitch, radius, distance=0.0008, strength=0.6, axes=(1, 1, 0)):
    """Raised dots on a surface (tactile paving), as a bump from a grid of discs in object space."""
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    sc.inputs["Scale"].default_value = 1.0 / pitch
    nt.links.new(tc.outputs["Object"], sc.inputs[0])
    fr = nt.nodes.new("ShaderNodeVectorMath")
    fr.operation = "FRACTION"
    nt.links.new(sc.outputs[0], fr.inputs[0])
    sb = nt.nodes.new("ShaderNodeVectorMath")
    sb.operation = "SUBTRACT"
    sb.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(fr.outputs[0], sb.inputs[0])
    mu = nt.nodes.new("ShaderNodeVectorMath")
    mu.operation = "MULTIPLY"
    mu.inputs[1].default_value = axes
    nt.links.new(sb.outputs[0], mu.inputs[0])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(mu.outputs[0], ln.inputs[0])
    sm = nt.nodes.new("ShaderNodeMapRange")       # soft-edged disc: 1 inside, 0 outside
    sm.inputs["From Min"].default_value, sm.inputs["From Max"].default_value = radius - 0.06, radius + 0.06
    sm.inputs["To Min"].default_value, sm.inputs["To Max"].default_value = 1.0, 0.0
    nt.links.new(ln.outputs["Value"], sm.inputs["Value"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = distance
    nt.links.new(sm.outputs["Result"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])


def tactile(hexstr="#E0B81F"):
    mat, b = A._principled("tactile", **{"Base Color": m.srgb(hexstr), "Roughness": 0.65})
    dot_bump(mat, b, 0.0046, 0.28)
    return mat


def concrete(hexstr="#B5B1A8", name="concrete"):
    mat, b = A._principled(name, **{"Base Color": m.srgb(hexstr), "Roughness": 0.92})
    A._bump(mat, b, 160.0, 0.6, detail=8.0, distance=0.0008)
    return mat


def ballast():
    mat, b = A._principled("ballast", **{"Base Color": m.srgb("#5E5B57"), "Roughness": 0.95})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = 900.0
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.9
    bp.inputs["Distance"].default_value = 0.0012
    nt.links.new(vo.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mat


def rusty(hexstr="#8A5A3A"):
    mat, b = A._principled("rust", **{"Base Color": m.srgb(hexstr), "Roughness": 0.9})
    A._bump(mat, b, 700.0, 0.5, detail=7.0, distance=0.0003)
    return mat


def ink_text(body, face, size, loc, rot=(90, 0, 0), color="#1B1A19", align="CENTER", parent=None):
    """A flat text object standing upright (facing -Y by default) with a matte ink material."""
    t = m.text(body, face, size, 0.0, 0.0, color, z=0.0, align=align, valign="CENTER")
    t.data.materials.clear()
    t.data.materials.append(A.plastic(color, 0.7, "ink_" + color))
    t.data.extrude = 0.00015
    t.rotation_euler = tuple(math.radians(a) for a in rot)
    t.location = loc
    if parent is not None:
        t.parent = parent
    return t


# ---------------------------------------------------------------- the platform and the tracks

def platform():
    slab = A.rounded_box("platform", (PL, PW, PH), 0.002, [concrete()])
    slab.location = (0, 0, PH / 2)
    line = A.rounded_box("safety_line", (PL, 0.006, 0.0003), 0.0, [P.paper("#F2EFE6", name="white_line")])
    line.location = (0, EDGE + 0.012, PH + 0.00015)
    tac = A.rounded_box("tactile", (PL, 0.025, 0.0012), 0.0002, [tactile()])
    tac.location = (0, EDGE + 0.032, PH + 0.0006)
    # the edge face is darker and chipped
    lip = A.rounded_box("platform_lip", (PL, 0.004, PH), 0.001, [concrete("#8E8A82", "lip")])
    lip.location = (0, EDGE - 0.001, PH / 2)
    bed = A.rounded_box("ballast", (PL + 1.6, 0.16, 0.012), 0.002, [ballast()])
    bed.location = (0, -0.22, 0.006)
    ground = A.rounded_box("ground", (PL + 1.6, 1.2, 0.004), 0.0, [concrete("#6E6B66", "ground")])
    ground.location = (0, 0.1, -0.002)
    tie = A.stained_wood("#3C3129", (), (), light="#51423A", rough=0.9)
    steel = A.metal("#9A9A96", 0.35, "rail_steel")
    x = -PL / 2 - 0.8
    while x < PL / 2 + 0.8:
        t = A.rounded_box("tie", (0.02, 0.11, 0.012), 0.001, [tie])
        t.location = (x, -0.22, 0.014)
        x += 0.05
    for ry in RAIL_Y:
        head = A.rounded_box("rail", (PL + 1.6, 0.005, 0.004), 0.0008, [steel])
        head.location = (0, ry, 0.026)
        web = A.rounded_box("rail_web", (PL + 1.6, 0.002, 0.008), 0.0, [steel])
        web.location = (0, ry, 0.022)
    return slab


# ---------------------------------------------------------------- signs, bench, canopy

def station_sign(x, y):
    """White board on two rusty posts: うら, with おもて and あっち as the next stations."""
    post_mat = rusty("#6E4A33")
    for sx in (-1, 1):
        p = A.rounded_box("sign_post", (0.006, 0.006, 0.17), 0.0008, [post_mat])
        p.location = (x + sx * 0.055, y, PH + 0.085)
    frame = A.rounded_box("sign_frame", (0.13, 0.006, 0.046), 0.0012, [rusty("#7A4E34")])
    frame.location = (x, y, PH + 0.145)
    board = A.rounded_box("sign_board", (0.122, 0.003, 0.038), 0.0005, [P.paper("#F3F1EA", name="sign_white")])
    board.location = (x, y - 0.0025, PH + 0.145)
    zf = PH + 0.145
    ink_text("うら", "gothic", 0.016, (x, y - 0.0045, zf + 0.004))
    ink_text("う  ら", "din", 0.0045, (x, y - 0.0045, zf - 0.009), color="#3A3A3A")
    ink_text("おもて", "gothic", 0.0055, (x - 0.042, y - 0.0045, zf - 0.013))
    ink_text("あっち", "gothic", 0.0055, (x + 0.042, y - 0.0045, zf - 0.013))
    bar = A.rounded_box("sign_bar", (0.10, 0.0006, 0.0025), 0.0, [A.plastic("#1B1A19", 0.7, "ink_bar")])
    bar.location = (x, y - 0.0046, zf - 0.0075)
    for sx in (-1, 1):
        arrow = P.flat_shape("sign_arrow", [(0, 0.004), (-0.005, 0), (0, -0.004), (0, -0.0015), (0.012, -0.0015), (0.012, 0.0015),
                                            (0, 0.0015)], [A.plastic("#1B1A19", 0.7, "ink_arrow")])
        arrow.rotation_euler = (math.radians(90), 0, math.radians(0 if sx < 0 else 180))
        arrow.location = (x + sx * 0.052, y - 0.0046, zf - 0.0075)


def direction_box(x, y, z):
    """Light-box sign under the canopy; the two arrows are separate objects so they can spin."""
    box = A.rounded_box("dir_box", (0.11, 0.025, 0.028), 0.0015, [A.plastic("#2A2B2E", 0.4, "dir_metal")])
    box.location = (x, y, z)
    face = A.rounded_box("dir_face", (0.104, 0.0006, 0.022), 0.0, [A.emissive("#F6F3EA", 2.2)])
    face.location = (x, y - 0.0128, z)
    arrows = []
    for i, sx in enumerate((-1, 1)):
        ar = P.flat_shape(f"dir_arrow{i}", [(0, 0.007), (-0.008, 0), (0, -0.007), (0, -0.0028), (0.018, -0.0028), (0.018, 0.0028),
                                            (0, 0.0028)], [A.plastic("#15151A", 0.6, "arrow_ink")])
        ar.rotation_euler = (math.radians(90), 0, math.radians(0 if sx < 0 else 180))
        ar.location = (x + sx * 0.03, y - 0.0135, z)
        arrows.append(ar)
    ink_text("うら", "gothic", 0.007, (x, y - 0.0135, z + 0.0005), color="#15151A")
    for sx in (-1, 1):
        rod = A.rounded_box("dir_rod", (0.004, 0.004, 0.05), 0.0005, [A.plastic("#2A2B2E", 0.4, "dir_metal")])
        rod.location = (x + sx * 0.04, y, z + 0.039)
    return arrows


def bench(x, y, image):
    wood = A.stained_wood("#6E5236", (), (), light="#8C6B48", rough=0.6)
    iron = A.metal("#2E2F33", 0.5, "bench_iron")
    for sx in (-1, 1):
        for dy in (-0.018, 0.012):
            leg = A.rounded_box("bench_leg", (0.006, 0.006, 0.045), 0.0006, [iron])
            leg.location = (x + sx * 0.05, y + dy, PH + 0.0225)
    for k, dy in enumerate((-0.02, -0.008, 0.004, 0.016)):
        slat = A.rounded_box("bench_slat", (0.12, 0.011, 0.004), 0.0008, [wood])
        slat.location = (x, y + dy, PH + 0.047)
    for k, dz in enumerate((0.07, 0.085)):
        back = A.rounded_box("bench_back", (0.12, 0.004, 0.012), 0.0008, [wood])
        back.location = (x, y + 0.024, PH + dz)
        back.rotation_euler.x = math.radians(-8)
    ad = A.rounded_box("bench_ad", (0.07, 0.0004, 0.026), 0.0, [A.printed(image, rough=0.95)])
    P.map_uv(ad, ("x", "z"), (0.07, 0.026))
    ad.location = (x + 0.01, y + 0.0215, PH + 0.078)
    ad.rotation_euler.x = math.radians(-8)
    # her bag: navy canvas, the zip half open, a heart keyring; the band-aid stuck to the seat
    bag = A.rounded_box("bag", (0.034, 0.016, 0.038), 0.003, [P.fabric("#232A48", rough=0.9, name="bag_canvas")])
    bag.location = (x - 0.03, y - 0.002, PH + 0.049 + 0.019)
    bag.rotation_euler = (math.radians(-6), 0, math.radians(14))
    zip_ = A.tube_along("bag_zip", [(x - 0.046, y + 0.004, PH + 0.084), (x - 0.03, y - 0.007, PH + 0.088)], 0.0006,
                        [A.chrome()])
    _ = zip_
    proof = A.rounded_box("bag_proof", (0.02, 0.0005, 0.026), 0.0, [A.printed(image)])
    P.map_uv(proof, ("x", "z"), (0.02, 0.026))
    proof.location = (x - 0.036, y - 0.0075, PH + 0.082)
    proof.rotation_euler = (math.radians(-6), math.radians(-12), math.radians(14))
    ring = P.flat_shape("keyring", [(px * 0.00022, py * 0.00022) for px, py in m.heart_outline(48)],
                        [A.smoked_glass("#FF3D8B", density=350.0)])
    ring.rotation_euler = (math.radians(90), 0, math.radians(20))
    ring.location = (x - 0.012, y - 0.012, PH + 0.064)
    ring.modifiers.new("solid", "SOLIDIFY").thickness = 0.0012
    aid = P.flat_shape("band_aid", [(px * 0.00028, py * 0.00028) for px, py in m.heart_outline(48)],
                       [P.paper("#E9C9B4", name="band_aid")])
    aid.location = (x + 0.035, y - 0.004, PH + 0.0495)
    aid.rotation_euler.z = math.radians(-25)


def canopy(night_flicker=2):
    steel = A.metal("#5B5F66", 0.45, "canopy_steel")
    z_roof = PH + 0.20
    for k, x in enumerate((-0.22, -0.07, 0.08, 0.23)):
        post = A.rounded_box("canopy_post", (0.009, 0.009, 0.20), 0.001, [steel])
        post.location = (x, 0.09, PH + 0.10)
    roof = A.rounded_box("canopy_roof", (PL, 0.21, 0.006), 0.001, [A.plastic("#8E8F8A", 0.6, "roof_paint")])
    roof.location = (0, 0.03, z_roof)
    beam = A.rounded_box("canopy_beam", (PL, 0.012, 0.012), 0.001, [steel])
    beam.location = (0, 0.0, z_roof - 0.009)
    tubes = []
    for k, x in enumerate((-0.24, -0.12, 0.0, 0.12, 0.24)):
        fixture = A.rounded_box("tube_fixture", (0.1, 0.02, 0.006), 0.001, [A.plastic("#D8D6CE", 0.5, "fixture")])
        fixture.location = (x, -0.02, z_roof - 0.018)
        tube = A.lathe("fluoro", [(0.0001, -0.048), (0.003, -0.048), (0.003, 0.048), (0.0001, 0.048)], 20,
                       [A.emissive("#F2EFE4", 1.0)])
        tube.rotation_euler = (0, math.radians(90), 0)
        tube.location = (x, -0.02, z_roof - 0.024)
        tubes.append(tube)
    return tubes


# ---------------------------------------------------------------- the train

def train(x0, bulbs=True):
    cream = A.plastic("#EDE4CF", 0.35, "train_cream")
    red = A.plastic("#C7321F", 0.3, "train_red")
    stainless = A.metal("#B9BBC0", 0.32, "stainless")
    glass = A.clear_glass(0.0)
    warm = A.emissive("#FFD8A6", 1.6)
    L, Wd, Hb = 0.45, 0.08, 0.10
    yc, z0 = -0.22, 0.032
    for car in range(2):
        xc = x0 + car * (L + 0.012)
        body = A.rounded_box("car_body", (L, Wd, Hb), 0.006, [cream])
        body.location = (xc, yc, z0 + Hb / 2)
        band = A.rounded_box("car_band", (L + 0.0005, Wd + 0.001, 0.026), 0.002, [red])
        band.location = (xc, yc, z0 + 0.022)
        skirt = A.rounded_box("car_skirt", (L - 0.02, Wd - 0.01, 0.03), 0.002, [A.plastic("#2A2A2C", 0.6, "skirt")])
        skirt.location = (xc, yc, z0 - 0.01)
        roof = A.rounded_box("car_roof", (L - 0.01, Wd - 0.012, 0.012), 0.005, [A.plastic("#C9C2B2", 0.5, "car_roof")])
        roof.location = (xc, yc, z0 + Hb + 0.004)
        ac = A.rounded_box("car_ac", (0.06, 0.04, 0.012), 0.003, [A.plastic("#B9B3A4", 0.5, "car_ac")])
        ac.location = (xc, yc, z0 + Hb + 0.014)
        for wx in (-0.14, 0.14):
            for sy in (-1, 1):
                wheel = A.lathe("wheel", [(0.0001, -0.004), (0.012, -0.004), (0.012, 0.004), (0.0001, 0.004)], 24,
                                [A.metal("#3A3A3C", 0.5, "wheel")])
                wheel.rotation_euler = (math.radians(90), 0, 0)
                wheel.location = (xc + wx, RAIL_Y[0] if sy < 0 else RAIL_Y[1], 0.026)
        # the platform side: windows, two sliding doors; the far side gets windows only
        y_face = yc + Wd / 2
        slots = [-0.19, -0.13, -0.07, 0.07, 0.13, 0.19]
        for sx in slots:
            for side in (1, -1):
                yf = yc + side * Wd / 2
                rim = A.rounded_box("window_rim", (0.05, 0.004, 0.039), 0.0008, [A.plastic("#4A4A4C", 0.5, "window_rim")])
                rim.location = (xc + sx, yf + side * 0.0012, z0 + 0.064)
                panel = A.rounded_box("window_light", (0.046, 0.0006, 0.035), 0.0, [warm])
                panel.location = (xc + sx, yf + side * 0.0016, z0 + 0.064)
                pane = A.rounded_box("window_glass", (0.046, 0.0004, 0.035), 0.0, [glass])
                pane.location = (xc + sx, yf + side * 0.0036, z0 + 0.064)
                if bulbs and side == 1:
                    rnd = random.Random(int(sx * 1000) + car)
                    for k in range(3):
                        b = A.heart_bulb("infected" if rnd.random() < 0.7 else "clean", 0.0045, seed=k + car)
                        b.location = (xc + sx - 0.014 + 0.014 * k, yf + 0.0026, z0 + 0.074 - 0.004 * (k % 2))
                        b.rotation_euler = (math.radians(rnd.uniform(70, 110)), 0, math.radians(rnd.uniform(0, 360)))
                        A.tube_along("bulb_string", [(xc + sx - 0.014 + 0.014 * k, yf + 0.0026, z0 + 0.082),
                                                     (xc + sx - 0.014 + 0.014 * k, yf + 0.0026, z0 + 0.077)], 0.0002,
                                     [A.plastic("#E0301E", 0.7, "cord")])
        for dx in (-0.0, ):
            door = A.rounded_box("door", (0.052, 0.004, 0.088), 0.001, [stainless])
            door.location = (xc + dx, y_face + 0.0014, z0 + 0.046)
            seam = A.rounded_box("door_seam", (0.0012, 0.0006, 0.086), 0.0, [A.plastic("#1A1A1C", 0.6, "seam")])
            seam.location = (xc + dx, y_face + 0.0036, z0 + 0.046)
            for sx in (-1, 1):
                dw = A.rounded_box("door_window", (0.018, 0.0006, 0.03), 0.0, [warm])
                dw.location = (xc + dx + sx * 0.013, y_face + 0.0036, z0 + 0.066)
        # headlights on the front car
        if car == 0:
            for sy in (-1, 1):
                hl = A.lathe("headlight", [(0.0001, 0), (0.006, 0), (0.006, 0.003), (0.0001, 0.003)], 24, [A.emissive("#FFF2D0", 8.0)])
                hl.rotation_euler = (0, math.radians(-90), 0)
                hl.location = (xc - L / 2 - 0.001, yc + sy * 0.025, z0 + 0.03)
    return None


# ---------------------------------------------------------------- her shoes

def canvas_shoe(loc, yaw_deg, mirror=False, heart="outline"):
    """A simplified white canvas sneaker: puffy upper, rubber sole and toe cap, loose laces.
    heart: 'full' draws the ballpoint heart on the toe, 'outline' only its outline and crop marks."""
    root = bpy.data.objects.new("shoe", None)
    m._link(root)
    root.location = loc
    root.rotation_euler.z = math.radians(yaw_deg)
    canvas = P.fabric("#EFECE3", rough=0.9, sheen=0.3, name="canvas")
    rubber = A.plastic("#E4DCC6", 0.55, "sole_rubber")
    sgn = -1 if mirror else 1
    outline = [(x, sgn * y * (1.0 + 0.15 * (x > 0))) for x, y in P.superellipse(0.0115, 0.0042, 2.6, 96)]
    sole = A._obj("sole", m.pillow_mesh("sole", [(x, y) for x, y in outline], centre=(0.0, 0.0), depth=0.0012, rings=10),
                  [rubber], root)
    sole.location = (0, 0, 0.0012)
    upper = A._obj("upper", m.pillow_mesh("upper", [(x * 0.96, y * 0.9) for x, y in outline], centre=(-0.002, 0.0),
                                          depth=0.0045, rings=16), [canvas], root)
    upper.location = (0, 0, 0.0025)
    upper.modifiers.new("sub", "SUBSURF").render_levels = 2
    cap = A._obj("toe_cap", m.pillow_mesh("cap", [(x, y) for x, y in P.superellipse(0.0045, 0.0038, 2.4, 48)], centre=(0, 0),
                                          depth=0.003, rings=8), [rubber], root)
    cap.location = (0.0075, 0, 0.0035)
    cap.modifiers.new("sub", "SUBSURF").render_levels = 2
    # ankle collar: a padded ring around the opening at the heel end; the tongue rises in front of it
    collar = [(-0.0048 + 0.0036 * math.cos(a), sgn * 0.0030 * math.sin(a), 0.0064 + 0.0010 * (1 - math.cos(a)) / 2)
              for a in [2 * math.pi * k / 24 for k in range(24)]]
    A.tube_along("collar", collar, 0.00035, [canvas], root, cyclic=True)
    tongue = A.rounded_box("tongue", (0.0055, 0.0032, 0.0008), 0.0003, [canvas], root)
    tongue.location = (0.0005, 0, 0.0072)
    tongue.rotation_euler.y = math.radians(-18)
    eyelet = A.metal("#9A9A96", 0.4, "eyelet")
    # laces: three crossings of thin white cord, the ends trailing
    lace = A.plastic("#F4F2EC", 0.8, "lace")
    for k in range(3):
        x = -0.001 - 0.0025 * k
        A.tube_along("lace", [(x, -0.0025, 0.0074), (x + 0.0025, 0.0025, 0.0076)], 0.00028, [lace], root)
        A.tube_along("lace", [(x, 0.0025, 0.0074), (x + 0.0025, -0.0025, 0.0076)], 0.00028, [lace], root)
        for sy in (-1, 1):
            e = A.lathe("eyelet", [(0.0001, 0), (0.0005, 0), (0.0005, 0.0003), (0.0001, 0.0003)], 12, [eyelet], root)
            e.location = (x, sy * 0.0027, 0.0071)
    A.tube_along("lace_end", [(-0.007, -0.003, 0.0058), (-0.010, -0.006, 0.002), (-0.012, -0.009, 0.0004)], 0.00025, [lace], root)
    # the ballpoint heart on the toe: blue ink lines sunk a little into the weave
    ink = A.plastic("#243585", 0.75, "ballpoint")   # matte: a glossy ink only mirrored the sky
    pts = [(0.0075 + 0.00007 * x, 0.00007 * y, 0.0066) for x, y in m.heart_outline(40)]
    pts.append(pts[0])
    A.tube_along("pen_heart", pts, 0.00022, [ink], root, cyclic=True)
    if heart == "full":
        for k in range(7):
            y = -0.0009 + 0.0003 * k
            half = 0.0011 * math.sqrt(max(0.0, 1 - (y / 0.0011) ** 2))
            A.tube_along("pen_fill", [(0.0075 - half, y, 0.0066), (0.0075 + half, y + 0.00012, 0.0066)], 0.00013, [ink], root)
    else:
        for sx in (-1, 1):
            for sy in (-1, 1):
                A.tube_along("crop", [(0.0075 + sx * 0.0016, sy * 0.0016, 0.0066), (0.0075 + sx * 0.0022, sy * 0.0016, 0.0066)],
                             0.0001, [ink], root)
    return root


# ---------------------------------------------------------------- scene

def build(palette="omote"):
    m.reset()
    cyc.cycles()
    cyc.world((0.006, 0.007, 0.010) if palette == "omote" else (0.0, 0.0, 0.0))
    platform()
    station_sign(0.10, 0.02)
    arrows = direction_box(-0.05, 0.0, PH + 0.155)
    img = os.path.join(cyc.ROOT, "renders", "frame_A.png")
    bench(0.0, 0.06, img)
    tubes = canopy()
    train(-0.42)
    canvas_shoe(tuple(SHOES + Vector((0, 0.0, 0))), yaw_deg=-92, heart="full")
    canvas_shoe(tuple(SHOES + Vector((0.013, 0.0, 0))), yaw_deg=-88, mirror=True, heart="outline")
    rnd = random.Random(3)
    for k in range(6):   # stray infected bulbs along the platform and in the ballast
        b = A.heart_bulb("infected", 0.0045, seed=10 + k)
        b.location = (rnd.uniform(-0.28, 0.28), rnd.uniform(EDGE + 0.04, 0.1), PH + 0.0022)
        b.rotation_euler = (math.radians(rnd.uniform(70, 110)), 0, math.radians(rnd.uniform(0, 360)))
    if palette == "omote":
        # sunset from the far end of the rails: low, orange, long shadows toward the camera
        cyc.area_light("sunset", (-1.4, -0.34, 0.30), (0.1, -0.10, PH), 0.25, 3000, 16.0, spread_deg=30)
        cyc.area_light("sky", (0.0, 0.0, 0.9), (0.0, 0.0, 0.0), 1.2, 9000, 1.5, size_y=1.0)
        for t in tubes:
            t.data.materials[0] = A.emissive("#B9B6AC", 0.0)   # tubes off in daylight
        cyc.haze("haze", (PL + 1.6, 1.0, 0.5), (0, 0.0, 0.25), 0.0025, color="#F2B07A")
    else:
        for i, t in enumerate(tubes):
            t.data.materials[0] = A.emissive("#EEF0E8", 0.8 if i != 2 else 0.15)   # the third tube is dying
        cyc.area_light("tube_glow", (0.0, -0.02, PH + 0.17), (0.0, -0.02, PH), 0.5, 4000, 1.6, size_y=0.08)
        cyc.area_light("train_glow", (-0.2, -0.17, 0.09), (-0.2, -0.08, PH + 0.02), 0.4, 2900, 0.5, size_y=0.04)
        cyc.haze("haze", (PL + 1.6, 1.0, 0.5), (0, 0.0, 0.25), 0.005)
    cyc.glass_lets_light_through()
    return dict(arrows=arrows, shoes=SHOES)


def main():
    want = {s for s in SHOTS}
    for pal in ("omote", "ura"):
        shots = [s for s in SHOTS if s.endswith(pal)]
        if not shots:
            continue
        build(pal)
        toe = SHOES + Vector((0.0115, 0.0, 0.0066))
        cams = {
            f"edge_{pal}": cyc.camera("cam_edge", (0.125, EDGE + 0.050, PH + 0.018), tuple(SHOES + Vector((0.01, 0, 0.004))), 24, 8.0),
            f"shoes_{pal}": cyc.camera("cam_shoes", tuple(toe + Vector((0.09, -0.07, 0.045))), tuple(toe), 100, 8.0),
        }
        cams = {k: v for k, v in cams.items() if k in want}
        focus = {f"edge_{pal}": SHOES + Vector((0, 0, 0.004)), f"shoes_{pal}": toe}
        cyc.render_shots(cams, shots, OUT, "s5", focus=focus, blend=f"s5_{pal}.blend")


if __name__ == "__main__":
    main()
