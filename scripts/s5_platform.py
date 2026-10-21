"""S5「这边与那边的站台」: a single-sided country platform at 1:12, 1.2 m long (14 m), under a sunset from
the far end of the rails, and the same platform at night. Weathered concrete, gravel ballast, rust-streaked
steel canopy, a chain-link fence and utility poles behind, a two-car cream-and-vermilion local train with heart
bulbs in its windows, a painted wooden bench with her bag, and her white sneakers side by side on the tactile
tiles where she jumped. Surfaces and the big props are CC0 Poly Haven assets (scripts/fetch_assets.py); the
sneakers are the Khronos glTF sample shoe (Shopify, CC BY 4.0) recoloured white.

    blender -b -P scripts/s5_platform.py -- [renders/s5] [wide_omote edge_omote shoes_omote edge_ura ...]

Metres, Z up; the platform runs along X, the tracks are on its -Y side. The camera looks down the platform
towards -X, where the sun sets.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402
import texlib as T  # noqa: E402

OUT, SHOTS = cyc.args("s5", ["wide_omote", "edge_omote", "shoes_omote", "edge_ura"])
PL, PW, PH = 1.20, 0.25, 0.09            # platform length, width, height above the rail bed
EDGE = -PW / 2                            # the platform edge (tracks beyond it, at smaller y)
BACK = PW / 2 + 0.20                      # the back apron ends here; the fence stands on it
RAIL_Y = (-0.19, -0.25)
SHOES = Vector((0.03, EDGE + 0.030, PH))  # where the shoes stand on the tactile strip
SHOE_GLB = os.path.join(cyc.ROOT, "assets", "thirdparty", "khronos_shoe", "MaterialsVariantsShoe.glb")
SUN_DIR = Vector((-0.92, 0.34, 0.11)).normalized()   # towards the setting sun: down the rails, over the fence side
TRAIN_X0 = -0.52


# ---------------------------------------------------------------- materials

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
    sm = nt.nodes.new("ShaderNodeMapRange")
    sm.inputs["From Min"].default_value, sm.inputs["From Max"].default_value = radius - 0.06, radius + 0.06
    sm.inputs["To Min"].default_value, sm.inputs["To Max"].default_value = 1.0, 0.0
    nt.links.new(ln.outputs["Value"], sm.inputs["Value"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = distance
    nt.links.new(sm.outputs["Result"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])


def tactile(hexstr="#C9A62A"):
    """Yellow tactile tiles, dirt in the grooves from the concrete's grime map."""
    mat, b = A._principled("tactile", **{"Base Color": m.srgb(hexstr), "Roughness": 0.7})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 90.0
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.35, 0.7
    ramp.color_ramp.elements[0].color = m.srgb("#8A7320")
    ramp.color_ramp.elements[1].color = m.srgb(hexstr)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    dot_bump(mat, b, 0.0046, 0.28)
    return mat


def materials():
    return dict(
        concrete=T.pbr("concrete_floor_01", tint="#D3CFC6", rough=0.72),
        apron=T.pbr("concrete_floor_01", tint="#A9A59B", rough=0.8, rotation_deg=90),
        lip=T.pbr("brushed_concrete", tint="#A5A097"),
        gravel=T.pbr("gravel_floor", displace=0.0025),
        ground=T.pbr("gravel_floor", tint="#5E554C", rough=0.95, scale=1 / 8),
        tie=T.pbr("brown_planks_03", tint="#4E4238", rough=0.9),
        web=T.pbr("rusty_metal_02", tint="#7A6B62"),
        steel=T.pbr("rusty_painted_metal", tint="#93A89D"),
        iron=T.pbr("rusty_corrugated_iron"),
        rustpost=T.pbr("rusty_metal_02", tint="#A08C7C"),
        planks=T.pbr("brown_planks_05", tint="#8A6E52"),
        ceiling=T.pbr("rusty_painted_metal", flat=("#C9CCC3", 0.7), rough=0.8, scale=1 / 6),
        carpaint=T.pbr("rusty_painted_metal", flat=("#EADFC6", 0.82), rough=0.42, scale=1 / 6, bump=0.25, ao=0.2, name="carpaint"),
    )


# ---------------------------------------------------------------- the platform and the tracks

def platform(M):
    slab = A.rounded_box("platform", (PL, PW, PH), 0.002, [M["concrete"]])
    slab.location = (0, 0, PH / 2)
    apron = A.rounded_box("apron", (PL + 0.5, BACK - PW / 2 + 0.01, PH - 0.004), 0.002, [M["apron"]])
    apron.location = (0, (PW / 2 + BACK) / 2, (PH - 0.004) / 2)
    line = A.rounded_box("safety_line", (PL, 0.006, 0.0003), 0.0, [P.paper("#E6E2D6", name="white_line")])
    line.location = (0, EDGE + 0.012, PH + 0.00015)
    tac = A.rounded_box("tactile", (PL, 0.025, 0.0012), 0.0002, [tactile()])
    tac.location = (0, EDGE + 0.032, PH + 0.0006)
    lip = A.rounded_box("platform_lip", (PL, 0.004, PH), 0.001, [M["lip"]])
    lip.location = (0, EDGE - 0.001, PH / 2)
    # a drain groove and a crack of grime along the back of the slab
    groove = A.rounded_box("groove", (PL, 0.004, 0.0015), 0.0, [A.plaster("#4A463F")])
    groove.location = (0, PW / 2 - 0.01, PH - 0.0005)
    # ballast: a dense sheet so the gravel map can displace real stones; it slopes off on both sides
    L = PL + 1.8

    def bed_pt(i, j):
        u, v = i / 600, j / 44
        y = -0.33 + 0.24 * v
        edge = min(v, 1 - v) / 0.2
        return (-L / 2 + L * u, y, 0.004 + 0.010 * min(1.0, edge))

    bed = P.grid_mesh("ballast", 600, 44, bed_pt, [M["gravel"]])
    sub = bed.modifiers.new("sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels, sub.render_levels = 0, 1
    ground = A.rounded_box("ground", (L + 1.0, 2.4, 0.004), 0.0, [M["ground"]])
    ground.location = (0, -0.2, -0.002)
    ground_back = A.rounded_box("ground_back", (L + 1.0, 1.0, 0.004), 0.0, [M["ground"]])
    ground_back.location = (0, BACK + 0.5, PH - 0.030)
    steel = A.metal("#C4C4BE", 0.22, "rail_head")
    x = -L / 2
    while x < L / 2:
        t = A.rounded_box("tie", (0.02, 0.11, 0.012), 0.001, [M["tie"]])
        t.location = (x, -0.22, 0.016)
        x += 0.05
    for ry in RAIL_Y:
        head = A.rounded_box("rail", (L, 0.005, 0.004), 0.0008, [steel])
        head.location = (0, ry, 0.028)
        web = A.rounded_box("rail_web", (L, 0.002, 0.008), 0.0, [M["web"]])
        web.location = (0, ry, 0.024)
        foot = A.rounded_box("rail_foot", (L, 0.009, 0.0015), 0.0, [M["web"]])
        foot.location = (0, ry, 0.021)
    # a dark hedge behind the fence hides the seam between the ground and the sky
    hedge = A.rounded_box("hedge", (L + 1.0, 0.18, 0.16), 0.03, [A.plaster("#1E2A1A")])
    hedge.location = (0, BACK + 0.45, PH - 0.03 + 0.08)
    return slab


def ink_text(body, face, size, loc, rot=(90, 0, 0), color="#1B1A19", align="CENTER", parent=None):
    t = m.text(body, face, size, 0.0, 0.0, color, z=0.0, align=align, valign="CENTER")
    t.data.materials.clear()
    t.data.materials.append(A.plastic(color, 0.7, "ink_" + color))
    t.data.extrude = 0.00015
    t.rotation_euler = tuple(math.radians(a) for a in rot)
    t.location = loc
    if parent is not None:
        t.parent = parent
    return t


# ---------------------------------------------------------------- signs, bench, canopy, fence, poles

def station_sign(M, x, y):
    for sx in (-1, 1):
        p = A.rounded_box("sign_post", (0.006, 0.006, 0.17), 0.0008, [M["rustpost"]])
        p.location = (x + sx * 0.055, y, PH + 0.085)
    frame = A.rounded_box("sign_frame", (0.13, 0.006, 0.046), 0.0012, [M["rustpost"]])
    frame.location = (x, y, PH + 0.145)
    board = A.rounded_box("sign_board", (0.122, 0.003, 0.038), 0.0005, [P.paper("#EFEDE6", name="sign_white")])
    board.location = (x, y - 0.0025, PH + 0.145)
    zf = PH + 0.145
    ink_text("うら", "gothic", 0.016, (x, y - 0.0045, zf + 0.004))
    ink_text("う  ら", "din", 0.0045, (x, y - 0.0045, zf - 0.009), color="#3A3A3A")
    ink_text("おもて", "gothic", 0.0055, (x - 0.042, y - 0.0045, zf - 0.013))
    ink_text("あっち", "gothic", 0.0055, (x + 0.042, y - 0.0045, zf - 0.013))
    bar = A.rounded_box("sign_bar", (0.10, 0.0006, 0.0025), 0.0, [A.plastic("#1B1A19", 0.7, "ink_bar")])
    bar.location = (x, y - 0.0046, zf - 0.0075)
    for sx in (-1, 1):
        arrow = P.flat_shape("sign_arrow", [(0, 0.004), (-0.005, 0), (0, -0.004), (0, -0.0015), (0.012, -0.0015),
                                            (0.012, 0.0015), (0, 0.0015)], [A.plastic("#1B1A19", 0.7, "ink_arrow")])
        arrow.rotation_euler = (math.radians(90), 0, math.radians(0 if sx < 0 else 180))
        arrow.location = (x + sx * 0.052, y - 0.0046, zf - 0.0075)


def direction_box(M, x, y, z):
    box = A.rounded_box("dir_box", (0.11, 0.025, 0.028), 0.0015, [M["steel"]])
    box.location = (x, y, z)
    face = A.rounded_box("dir_face", (0.104, 0.0006, 0.022), 0.0, [A.emissive("#F6F3EA", 2.2)])
    face.location = (x, y - 0.0128, z)
    arrows = []
    for i, sx in enumerate((-1, 1)):
        ar = P.flat_shape(f"dir_arrow{i}", [(0, 0.007), (-0.008, 0), (0, -0.007), (0, -0.0028), (0.018, -0.0028),
                                            (0.018, 0.0028), (0, 0.0028)], [A.plastic("#15151A", 0.6, "arrow_ink")])
        ar.rotation_euler = (math.radians(90), 0, math.radians(0 if sx < 0 else 180))
        ar.location = (x + sx * 0.03, y - 0.0135, z)
        arrows.append(ar)
    ink_text("うら", "gothic", 0.007, (x, y - 0.0135, z + 0.0005), color="#15151A")
    for sx in (-1, 1):
        rod = A.rounded_box("dir_rod", (0.004, 0.004, 0.05), 0.0005, [M["steel"]])
        rod.location = (x + sx * 0.04, y, z + 0.039)
    return arrows


def seat_height(x, y, z_from):
    """Top surface under a point: ray cast straight down."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    hit, loc, nrm, _i, ob, _mx = bpy.context.scene.ray_cast(deps, Vector((x, y, z_from)), Vector((0, 0, -1)))
    return (loc.z if hit else PH), (ob.name if hit else None)


def bench(x, y, image):
    root = T.model("painted_wooden_bench", location=(x, y, PH))
    T.place(root, (x, y, PH))
    top = PH + 0.0543   # the seat slats of painted_wooden_bench, probed at 1:12
    # the faded ad on the backrest
    ad = A.rounded_box("bench_ad", (0.06, 0.0004, 0.022), 0.0, [A.printed(image, rough=0.95)])
    P.map_uv(ad, ("x", "z"), (0.06, 0.022))
    ad.location = (x + 0.012, y + 0.0185, PH + 0.055)
    # her bag: navy canvas, the zip half open, a proof sticking out, a pink acrylic heart on the strap
    bag = A.rounded_box("bag", (0.030, 0.015, 0.034), 0.003, [P.fabric("#232A48", rough=0.9, name="bag_canvas")])
    bag.location = (x - 0.028, y - 0.003, top + 0.017)
    bag.rotation_euler = (math.radians(-6), 0, math.radians(14))
    A.tube_along("bag_zip", [(x - 0.042, y + 0.003, top + 0.031), (x - 0.028, y - 0.008, top + 0.034)], 0.0006, [A.chrome()])
    proof = A.rounded_box("bag_proof", (0.018, 0.0005, 0.024), 0.0, [A.printed(image)])
    P.map_uv(proof, ("x", "z"), (0.018, 0.024))
    proof.location = (x - 0.033, y - 0.0085, top + 0.030)
    proof.rotation_euler = (math.radians(-6), math.radians(-12), math.radians(14))
    ring = P.flat_shape("keyring", [(px * 0.0035, py * 0.0035) for px, py in m.heart_outline(48)],
                        [A.smoked_glass("#FF3D8B", density=350.0)])
    ring.rotation_euler = (math.radians(90), 0, math.radians(20))
    ring.location = (x - 0.012, y - 0.012, top + 0.012)
    ring.modifiers.new("solid", "SOLIDIFY").thickness = 0.0012
    aid = P.flat_shape("band_aid", [(px * 0.0045, py * 0.0045) for px, py in m.heart_outline(48)],
                       [P.paper("#E9C9B4", name="band_aid")])
    aid.location = (x + 0.030, y - 0.004, top + 0.0003)
    aid.rotation_euler.z = math.radians(-25)
    return root


def canopy(M):
    z_roof = PH + 0.20
    for x in (-0.40, -0.22, -0.04, 0.14, 0.32):
        post = A.rounded_box("canopy_post", (0.009, 0.009, 0.20), 0.001, [M["steel"]])
        post.location = (x, 0.09, PH + 0.10)
        brace = A.rounded_box("canopy_brace", (0.005, 0.11, 0.005), 0.0006, [M["steel"]])
        brace.location = (x, 0.035, z_roof - 0.055)
        brace.rotation_euler.x = math.radians(40)
    roof = A.rounded_box("canopy_roof", (PL - 0.2, 0.21, 0.004), 0.001, [M["ceiling"]])
    roof.location = (-0.04, 0.03, z_roof)
    sheet = A.rounded_box("canopy_sheet", (PL - 0.2, 0.21, 0.002), 0.0005, [M["iron"]])
    sheet.location = (-0.04, 0.03, z_roof + 0.003)
    beam = A.rounded_box("canopy_beam", (PL - 0.2, 0.012, 0.012), 0.001, [M["steel"]])
    beam.location = (-0.04, 0.0, z_roof - 0.009)
    beam2 = A.rounded_box("canopy_beam", (PL - 0.2, 0.012, 0.012), 0.001, [M["steel"]])
    beam2.location = (-0.04, 0.09, z_roof - 0.009)
    gutter = A.rounded_box("gutter", (PL - 0.2, 0.012, 0.010), 0.002, [M["steel"]])
    gutter.location = (-0.04, -0.075, z_roof - 0.004)
    tubes = []
    for x in (-0.46, -0.34, -0.22, -0.10, 0.02, 0.14, 0.26, 0.38):
        fixture = A.rounded_box("tube_fixture", (0.1, 0.02, 0.006), 0.001, [A.plastic("#CFCDC4", 0.5, "fixture")])
        fixture.location = (x, -0.02, z_roof - 0.018)
        tube = A.lathe("fluoro", [(0.0001, -0.048), (0.003, -0.048), (0.003, 0.048), (0.0001, 0.048)], 20,
                       [A.emissive("#F2EFE4", 1.0)])
        tube.rotation_euler = (0, math.radians(90), 0)
        tube.location = (x, -0.02, z_roof - 0.024)
        tubes.append(tube)
    return tubes


def fence_and_poles():
    """Chain-link fence along the back of the apron, two utility poles with wires behind it."""
    z0 = PH - 0.030
    panel_len = 0.1595
    x = -1.3
    k = 0
    while x < 1.3:
        root = T.model("modular_chainlink_fence", pick="fence_double", name=f"fence_panel{k}")
        T.place(root, (x + panel_len / 2, BACK, z0 - 0.005))
        post = T.model("modular_chainlink_fence", pick="fence_end_01", name=f"fence_post{k}")
        T.place(post, (x, BACK, z0))
        x += panel_len
        k += 1
    tops = []
    for i, (px, preset) in enumerate(((-0.62, "preset_02_"), (0.40, "preset_01_"))):
        pole = T.model("modular_electricity_poles", pick=preset, name=f"pole{i}", scale=1 / 18)
        T.place(pole, (px, BACK + 0.30, z0), yaw_deg=90)
        lo, hi = T.model_bounds(pole)
        tops.append(Vector((px, BACK + 0.30, hi.z)))
    wire = A.plastic("#1A1A1C", 0.6, "wire")
    for dy, dz in ((-0.018, -0.03), (0.0, -0.03), (0.018, -0.03), (0.0, -0.085)):
        a, b = tops[0] + Vector((0, dy, dz)), tops[1] + Vector((0, dy, dz))
        far_a, far_b = a + Vector((-1.2, 0, 0.01)), b + Vector((1.2, 0, 0.01))
        for p0, p1 in ((far_a, a), (a, b), (b, far_b)):
            mid = (p0 + p1) / 2 + Vector((0, 0, -0.012 * (p1 - p0).length / 1.0))
            A.tube_along("wire", [tuple(p0), tuple(mid), tuple(p1)], 0.0004, [wire], resolution=3)
    box = T.model("utility_box_01", name="utility_box")
    T.place(box, (-0.10, 0.108, PH), yaw_deg=-8)


# ---------------------------------------------------------------- the train

def train(x0, M, bulbs=True):
    cream = M["carpaint"]
    red = T.pbr("rusty_painted_metal", flat=("#C4301E", 0.8), rough=0.4, scale=1 / 6, bump=0.25, ao=0.2, name="train_red")
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
        y_face = yc + Wd / 2
        for sx in (-0.19, -0.13, -0.07, 0.07, 0.13, 0.19):
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
        door = A.rounded_box("door", (0.052, 0.004, 0.088), 0.001, [stainless])
        door.location = (xc, y_face + 0.0014, z0 + 0.046)
        seam = A.rounded_box("door_seam", (0.0012, 0.0006, 0.086), 0.0, [A.plastic("#1A1A1C", 0.6, "seam")])
        seam.location = (xc, y_face + 0.0036, z0 + 0.046)
        for sx in (-1, 1):
            dw = A.rounded_box("door_window", (0.018, 0.0006, 0.03), 0.0, [warm])
            dw.location = (xc + sx * 0.013, y_face + 0.0036, z0 + 0.066)
        if car == 0:
            for sy in (-1, 1):
                hl = A.lathe("headlight", [(0.0001, 0), (0.006, 0), (0.006, 0.003), (0.0001, 0.003)], 24,
                             [A.emissive("#FFF2D0", 8.0)])
                hl.rotation_euler = (0, math.radians(-90), 0)
                hl.location = (xc - L / 2 - 0.001, yc + sy * 0.025, z0 + 0.03)


# ---------------------------------------------------------------- her sneakers

def _bounds(objs):
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def sneaker(loc, yaw_deg=0.0, mirror=False, length=0.024):
    """The Khronos sample shoe, scaled to a 29 cm shoe at 1:12, toe towards -Y, standing on loc."""
    before = {o.name for o in bpy.context.scene.objects}
    bpy.ops.import_scene.gltf(filepath=SHOE_GLB)
    new = [o for o in bpy.context.scene.objects if o.name not in before]
    root = next(o for o in new if o.parent is None)
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    lo, hi = _bounds(meshes)
    s = length / max(hi - lo)
    root.scale = tuple(v * s for v in root.scale)   # the importer already scales the root
    bpy.context.view_layer.update()
    lo, hi = _bounds(meshes)
    root.location = Vector(root.location) - Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    pivot = bpy.data.objects.new("sneaker", None)
    m._link(pivot)
    bpy.context.view_layer.update()
    root.parent = pivot
    pivot.location = loc
    pivot.rotation_euler.z = math.radians(-90 + yaw_deg)   # the file's +X (toe) turns to -Y
    if mirror:
        pivot.scale.x = -1.0
    # white canvas: desaturate the shoe's base colour, keep its weave and the grey laces and sole
    for ob in meshes:
        for ms in ob.material_slots:
            mat = ms.material
            if mat is None or mat.get("whitened"):
                continue
            nt = mat.node_tree
            bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            links = bsdf.inputs["Base Color"].links
            if links:
                hs = nt.nodes.new("ShaderNodeHueSaturation")
                hs.inputs["Saturation"].default_value = 0.0
                hs.inputs["Value"].default_value = 2.6
                nt.links.new(links[0].from_socket, hs.inputs["Color"])
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type = "RGBA"
                mix.inputs["Factor"].default_value = 0.45
                mix.inputs["B"].default_value = (0.95, 0.94, 0.9, 1.0)
                nt.links.new(hs.outputs["Color"], mix.inputs["A"])
                nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = max(0.6, bsdf.inputs["Roughness"].default_value)
            mat["whitened"] = True
    return pivot, meshes


def pen_heart(point_above, meshes, full=True, size=0.00011):
    """A ballpoint heart drawn on the shoe's toe. Each stroke point is dropped onto the shoe along the
    surface normal at the heart's centre, so the drawing hugs the curve of the toe."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    names = {o.name for o in meshes}
    hit, loc, nrm, _i, ob, _mx = bpy.context.scene.ray_cast(deps, Vector(point_above), Vector((0, 0, -1)))
    if not hit or ob.name not in names:
        print("pen_heart: no shoe under", point_above, hit, ob.name if hit else None)
        return
    ink = A.plastic("#243585", 0.75, "ballpoint")
    quat = nrm.to_track_quat("Z", "Y")
    frame = quat.to_matrix()

    def drop(x, y):
        start = loc + frame @ Vector((x, y, 0.004))
        h, p, n, _i2, o2, _m2 = bpy.context.scene.ray_cast(deps, start, -nrm, distance=0.012)
        if h and o2.name in names:
            return p + n * 0.00012
        return loc + frame @ Vector((x, y, 0.00012))

    def stroke(name, pts2d, radius, cyclic=False):
        pts = [tuple(drop(x, y)) for x, y in pts2d]
        return A.tube_along(name, pts, radius, [ink], cyclic=cyclic, resolution=3)

    S = size * 16
    stroke("pen_heart", [(x * S, y * S) for x, y in m.heart_outline(64)], 0.00011, cyclic=True)
    if full:
        # ballpoint hatching inside the outline, at a slant, like a quick colour-in
        for k in range(9):
            y0 = -0.95 * S + 0.24 * S * k
            half = 1.0 * S * math.sqrt(max(0.0, 1 - ((y0 + 0.1 * S) / (1.15 * S)) ** 2))
            if half < 0.1 * S:
                continue
            steps = 6
            pts = [(-half + 2 * half * t / steps, y0 + 0.08 * S * t / steps) for t in range(steps + 1)]
            stroke("pen_fill", pts, 0.00008)
    else:
        for sx in (-1, 1):
            for sy in (-1, 1):
                stroke("crop", [(sx * 1.3 * S, sy * 1.3 * S), (sx * 1.9 * S, sy * 1.3 * S)], 0.00008)
                stroke("crop", [(sx * 1.3 * S, sy * 1.3 * S), (sx * 1.3 * S, sy * 1.9 * S)], 0.00008)
    return loc


def shoes():
    left, lm = sneaker(tuple(SHOES), yaw_deg=-3)
    right, rm = sneaker(tuple(SHOES + Vector((0.013, 0.0, 0.0))), yaw_deg=2, mirror=True)
    toe_l = pen_heart((SHOES.x, SHOES.y - 0.0065, PH + 0.05), lm, full=True)
    toe_r = pen_heart((SHOES.x + 0.013, SHOES.y - 0.0065, PH + 0.05), rm, full=False)
    return toe_l or SHOES + Vector((0, -0.0065, 0.008)), toe_r


# ---------------------------------------------------------------- scene

def build(palette="omote"):
    m.reset()
    cyc.cycles()
    M = materials()
    platform(M)
    station_sign(M, -0.30, 0.03)
    arrows = direction_box(M, -0.20, 0.0, PH + 0.155)
    img = os.path.join(cyc.ROOT, "renders", "frame_A.png")
    bench(-0.12, 0.078, img)
    tubes = canopy(M)
    fence_and_poles()
    train(TRAIN_X0, M)
    toe_l, toe_r = shoes()
    rnd = random.Random(3)
    for k in range(6):
        b = A.heart_bulb("infected", 0.0045, seed=10 + k)
        b.location = (rnd.uniform(-0.45, 0.35), rnd.uniform(EDGE + 0.04, 0.1), PH + 0.0022)
        b.rotation_euler = (math.radians(rnd.uniform(70, 110)), 0, math.radians(rnd.uniform(0, 360)))
    if palette == "omote":
        # the sunset sky lights everything; a sun lamp aligned with its brightest spot gives the long shadows
        d0 = T.hdri_sun("industrial_sunset", 0.0)
        yaw = math.degrees(math.atan2(SUN_DIR.y, SUN_DIR.x) - math.atan2(d0.y, d0.x))
        T.hdri_world("industrial_sunset", strength=1.0, rotation_deg=yaw)
        sun = Vector((SUN_DIR.x, SUN_DIR.y, 0)).normalized() * math.cos(math.asin(SUN_DIR.z)) + Vector((0, 0, SUN_DIR.z))
        T.sun_lamp(sun, strength=4.0, kelvin_k=2600, angle_deg=0.8)
        for t in tubes:
            t.data.materials[0] = A.plastic("#CFCDC4", 0.5, "tube_off")
        cyc.haze("haze", (PL + 2.8, 2.5, 0.6), (0, 0.1, 0.3), 0.0015, color="#F2B07A")
    else:
        cyc.world((0.00015, 0.00025, 0.0006))
        for i, t in enumerate(tubes):
            t.data.materials[0] = A.emissive("#EEF0E8", 0.9 if i != 3 else 0.12)   # the fourth tube is dying
        cyc.area_light("tube_glow", (-0.1, -0.02, PH + 0.17), (-0.1, -0.02, PH), 0.9, 4000, 0.6, size_y=0.08)
        cyc.area_light("train_glow", (-0.3, -0.17, 0.09), (-0.3, -0.08, PH + 0.02), 0.7, 2900, 0.6, size_y=0.04)
        cyc.haze("haze", (PL + 2.8, 2.5, 0.6), (0, 0.1, 0.3), 0.0015)
    cyc.glass_lets_light_through()
    return dict(arrows=arrows, toe=toe_l)


def main():
    want = set(SHOTS)
    for pal in ("omote", "ura"):
        shots = [s for s in SHOTS if s.endswith(pal)]
        if not shots:
            continue
        info = build(pal)
        toe = Vector(info["toe"])
        cams = {
            f"wide_{pal}": cyc.camera("cam_wide", (0.72, -0.09, PH + 0.075), (-0.15, 0.03, PH + 0.075), 35, 8.0),
            f"edge_{pal}": cyc.camera("cam_edge", (0.115, EDGE + 0.048, PH + 0.016), tuple(SHOES + Vector((0.008, 0, 0.005))), 24, 8.0),
            f"shoes_{pal}": cyc.camera("cam_shoes", tuple(toe + Vector((0.085, -0.06, 0.03))), tuple(toe + Vector((0.006, 0.004, 0.0))), 100, 11.0),
        }
        cams = {k: v for k, v in cams.items() if k in want}
        focus = {f"wide_{pal}": (-0.12, 0.06, PH + 0.04), f"edge_{pal}": SHOES + Vector((0, 0, 0.004)), f"shoes_{pal}": toe}
        cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("window_glass", "haze")
        cyc.render_shots(cams, shots, OUT, "s5", focus=focus, blend=f"s5_{pal}.blend")


if __name__ == "__main__":
    main()
