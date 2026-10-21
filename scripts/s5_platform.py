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
KIHA_S = 1.1 / 12                         # the KiHa 32 model is a little under real size; 1.1 fits the platform
CAR_LEN, CAR_W = 13.519 * KIHA_S, 2.549 * KIHA_S
RAIL_TOP = 0.030
PL, PW = 1.20, 0.25                       # platform length and width
PH = RAIL_TOP + 1.0 * KIHA_S - 0.005      # platform top a little under the car floor
EDGE = -PW / 2                            # the platform edge (tracks beyond it, at smaller y)
BACK = PW / 2 + 0.20                      # the back apron ends here; the fence stands on it
TRACK_Y = EDGE - 0.008 - CAR_W / 2        # the car side stands 8 mm (10 cm real) off the platform edge
RAIL_Y = (TRACK_Y + 0.566 * KIHA_S, TRACK_Y - 0.566 * KIHA_S)   # rail centres under the model's wheel treads
SHOES = Vector((0.03, EDGE + 0.030, PH))  # where the shoes stand on the tactile strip
SHOE_GLB = os.path.join(cyc.ROOT, "assets", "thirdparty", "khronos_shoe", "MaterialsVariantsShoe.glb")
SUN_DIR = Vector((-0.92, 0.34, 0.11)).normalized()   # towards the setting sun: down the rails, over the fence side
TRAIN_NEAR_X = 0.33                       # the near end of the nearer car


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
    L = 6.0
    y0, y1 = TRACK_Y - 0.17, EDGE + 0.02

    def bed_pt(i, j):
        u, v = i / 1200, j / 64
        y = y0 + (y1 - y0) * v
        edge = min(v, 1 - v) / 0.2
        return (-L / 2 + L * u, y, 0.004 + 0.010 * min(1.0, edge))

    bed = P.grid_mesh("ballast", 1200, 64, bed_pt, [M["gravel"]])
    sub = bed.modifiers.new("sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels, sub.render_levels = 0, 1
    ground = A.rounded_box("ground", (L + 1.0, 2.4, 0.004), 0.0, [M["ground"]])
    ground.location = (0, -0.2, -0.002)
    ground_back = A.rounded_box("ground_back", (L + 1.0, 1.0, 0.004), 0.0, [M["ground"]])
    ground_back.location = (0, BACK + 0.5, PH - 0.030)
    steel = A.metal("#D2D2CE", 0.07, "rail_head")   # the running surface is polished by the wheels
    x = -L / 2
    while x < L / 2:
        t = A.rounded_box("tie", (0.2 * KIHA_S, 2.1 * KIHA_S, 0.012), 0.001, [M["tie"]])
        t.location = (x, TRACK_Y, 0.016)
        x += 0.6 * KIHA_S
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
    z_roof = PH + 0.23
    for x in (-0.40, -0.22, -0.04, 0.14, 0.32):
        post = A.rounded_box("canopy_post", (0.009, 0.009, 0.23), 0.001, [M["steel"]])
        post.location = (x, 0.09, PH + 0.115)
    x = -0.62
    while x < 0.55:   # rafters across the canopy, purlins along it
        r = A.rounded_box("canopy_rafter", (0.006, 0.21, 0.010), 0.0008, [M["steel"]])
        r.location = (x, 0.03, z_roof - 0.007)
        x += 0.09
    for y in (-0.06, 0.0, 0.06, 0.12):
        pu = A.rounded_box("canopy_purlin", (PL - 0.2, 0.005, 0.005), 0.0006, [M["steel"]])
        pu.location = (-0.04, y, z_roof - 0.0045)
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

def _glossy(nt):
    for idname in ("ShaderNodeBsdfGlossy", "ShaderNodeBsdfAnisotropic"):
        try:
            return nt.nodes.new(idname)
        except RuntimeError:
            continue
    raise RuntimeError("no glossy BSDF node")


def livery(mat, cream="#EADFC6"):
    """KiHa 32 texture to the JNR cream + vermilion livery, and its painted windows to real glass.
    Image_0 is the colour, Image_1 the glTF metal/roughness map: its green (roughness) is 0 on the glass."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    texs = [n for n in nt.nodes if n.type == "TEX_IMAGE"]
    base = next(n for n in texs if n.image.name.startswith("Image_0"))
    mr = next(n for n in texs if n.image.name.startswith("Image_1"))
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(mr.outputs["Color"], sep.inputs["Color"])
    body = sep.outputs["Green"]
    bs = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(base.outputs["Color"], bs.inputs["Color"])
    blue = nt.nodes.new("ShaderNodeMath")          # how blue: (B - R) * 3, clamped
    blue.operation = "SUBTRACT"
    nt.links.new(bs.outputs["Blue"], blue.inputs[0])
    nt.links.new(bs.outputs["Red"], blue.inputs[1])
    gain = nt.nodes.new("ShaderNodeMath")
    gain.operation = "MULTIPLY"
    gain.use_clamp = True
    gain.inputs[1].default_value = 3.0
    nt.links.new(blue.outputs[0], gain.inputs[0])
    only_body = nt.nodes.new("ShaderNodeMath")
    only_body.operation = "MULTIPLY"
    nt.links.new(gain.outputs[0], only_body.inputs[0])
    nt.links.new(body, only_body.inputs[1])
    hs = nt.nodes.new("ShaderNodeHueSaturation")   # JR Shikoku blue (199 deg) round to vermilion (6 deg)
    hs.inputs["Hue"].default_value = 0.964
    hs.inputs["Saturation"].default_value = 1.08
    nt.links.new(base.outputs["Color"], hs.inputs["Color"])
    m1 = nt.nodes.new("ShaderNodeMix")
    m1.data_type = "RGBA"
    nt.links.new(only_body.outputs[0], m1.inputs["Factor"])
    nt.links.new(base.outputs["Color"], m1.inputs["A"])
    nt.links.new(hs.outputs["Color"], m1.inputs["B"])
    m2 = nt.nodes.new("ShaderNodeMix")              # white paint to cream, the glass untouched
    m2.data_type = "RGBA"
    m2.blend_type = "MULTIPLY"
    nt.links.new(body, m2.inputs["Factor"])
    nt.links.new(m1.outputs["Result"], m2.inputs["A"])
    m2.inputs["B"].default_value = m.srgb(cream)
    nt.links.new(m2.outputs["Result"], bsdf.inputs["Base Color"])
    # the map's roughness is 1.0 on the paint, which made the car chalk-matte: real paint is glossy under a
    # clear coat, so the body takes a quarter of it and reflects the sky
    rl = bsdf.inputs["Roughness"].links
    if rl:
        damp = nt.nodes.new("ShaderNodeMath")
        damp.operation = "MULTIPLY"
        damp.inputs[1].default_value = 0.28
        nt.links.new(rl[0].from_socket, damp.inputs[0])
        nt.links.new(damp.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Coat Weight"].default_value = 0.7
    bsdf.inputs["Coat Roughness"].default_value = 0.04
    # glass: see-through with a Fresnel reflection, where the map says glass
    glass_mask = nt.nodes.new("ShaderNodeMath")
    glass_mask.operation = "SUBTRACT"
    glass_mask.inputs[0].default_value = 1.0
    nt.links.new(body, glass_mask.inputs[1])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    gl = _glossy(nt)
    gl.inputs["Roughness"].default_value = 0.03
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.5
    glass = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], glass.inputs[0])
    nt.links.new(tr.outputs[0], glass.inputs[1])
    nt.links.new(gl.outputs[0], glass.inputs[2])
    final = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(glass_mask.outputs[0], final.inputs[0])
    nt.links.new(bsdf.outputs[0], final.inputs[1])
    nt.links.new(glass.outputs[0], final.inputs[2])
    nt.links.new(final.outputs[0], out.inputs["Surface"])
    mat["livery"] = True


def interior(pivot, near, night, seed=0):
    """What is seen through the windows, in the model's own metres (the pivot scales it): floor, ceiling with
    two light strips, the far wall, long seats, hand straps, and the heart bulbs hanging between the straps.
    near = +1 when the platform is on the car's local +y side."""
    rnd = random.Random(seed)
    floor = A.rounded_box("car_floor", (12.4, 2.2, 0.05), 0.0, [A.plastic("#5D665A", 0.6, "car_floor")], pivot)
    floor.location = (0, 0, 1.02)
    ceil = A.rounded_box("car_ceiling", (12.4, 2.2, 0.05), 0.0, [A.plastic("#D8D5CB", 0.7, "car_ceiling")], pivot)
    ceil.location = (0, 0, 2.66)
    for y in (-0.45, 0.45):
        strip = A.rounded_box("car_light", (11.6, 0.1, 0.03), 0.0, [A.emissive("#FFF1DC", 5.0 if night else 1.2)], pivot)
        strip.location = (0, y, 2.62)
    wall = A.rounded_box("car_wall", (12.4, 0.05, 1.62), 0.0, [A.plastic("#CFC8B8", 0.7, "car_wall")], pivot)
    wall.location = (0, -near * 1.06, 1.85)
    moquette = P.fabric("#2C3C73", rough=0.95, name="moquette")
    for sy in (-1, 1):
        seat = A.rounded_box("car_seat", (8.6, 0.48, 0.16), 0.04, [moquette], pivot)
        seat.location = (0, sy * 0.86, 1.47)
        back = A.rounded_box("car_seatback", (8.6, 0.10, 0.42), 0.04, [moquette], pivot)
        back.location = (0, sy * 1.02, 1.72)
    white = A.plastic("#F1EFE8", 0.4, "strap")
    rod = A.metal("#C8C9CC", 0.25, "rail_steel_in")
    for sy in (-0.62, 0.62):
        A.tube_along("strap_rail", [(-5.8, sy, 2.5), (5.8, sy, 2.5)], 0.016, [rod], pivot, resolution=3)
        x = -5.4
        while x <= 5.4:
            A.tube_along("strap", [(x, sy, 2.5), (x, sy, 2.26)], 0.012, [white], pivot, resolution=2)
            ring = [(x + 0.055 * math.cos(a), sy, 2.20 + 0.055 * math.sin(a)) for a in [2 * math.pi * k / 12 for k in range(12)]]
            A.tube_along("strap_ring", ring, 0.009, [white], pivot, cyclic=True, resolution=2)
            x += 0.45
    cord = A.plastic("#E0301E", 0.7, "cord")
    x = -4.4
    while x <= 4.4:
        for _k in range(rnd.choice((1, 2))):
            bx = x + rnd.uniform(-0.12, 0.12)
            bz = rnd.uniform(2.02, 2.32)
            by = near * rnd.uniform(0.75, 0.95)
            b = A.heart_bulb("infected" if rnd.random() < 0.75 else "clean", 0.06, seed=rnd.randrange(1000))
            b.parent = pivot
            b.location = (bx, by, bz)
            b.rotation_euler = (math.radians(rnd.uniform(80, 100)), 0, math.radians(rnd.uniform(0, 360)))
            A.tube_along("bulb_string", [(bx, by, 2.63), (bx, by, bz + 0.035)], 0.004, [cord], pivot, resolution=2)
        x += 0.63


def kiha_car(xc, night, flip=False, seed=0):
    pivot, meshes = T.glb("kiha32", name="kiha32", scale=KIHA_S)
    pivot.location = (xc, TRACK_Y, RAIL_TOP)
    if flip:
        pivot.rotation_euler.z = math.pi
    for ob in meshes:
        for ms in ob.material_slots:
            if ms.material and ms.material.name.startswith("1591184735691") and not ms.material.get("livery"):
                livery(ms.material)
    interior(pivot, near=-1 if flip else 1, night=night, seed=seed)
    return pivot


def train(night):
    """Two KiHa 32 railcars coupled, the nearer one's end at TRAIN_NEAR_X."""
    xa = TRAIN_NEAR_X - CAR_LEN / 2
    kiha_car(xa, night, seed=1)
    kiha_car(xa - CAR_LEN - 0.012, night, flip=True, seed=2)


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
    ink = A.plastic("#243585", 0.45, "ballpoint")
    quat = nrm.to_track_quat("Z", "Y")
    frame = quat.to_matrix()

    def drop(x, y, lift):
        start = loc + frame @ Vector((x, y, 0.004))
        h, p, n, _i2, o2, _m2 = bpy.context.scene.ray_cast(deps, start, -nrm, distance=0.012)
        if h and o2.name in names:
            return p + n * lift
        return loc + frame @ Vector((x, y, lift))

    def stroke(name, pts2d, radius, cyclic=False):
        # ink lies in the fabric: the stroke's core sits under the surface and only a sliver shows, a line
        # 0.7 x its diameter wide
        pts = [tuple(drop(x, y, -0.7 * radius)) for x, y in pts2d]
        return A.tube_along(name, pts, radius, [ink], cyclic=cyclic, resolution=3)

    S = size * 16
    stroke("pen_heart", [(x * S, y * S) for x, y in m.heart_outline(64)], 0.00004, cyclic=True)
    if full:
        # ballpoint hatching inside the outline, at a slant, like a quick colour-in
        for k in range(9):
            y0 = -0.95 * S + 0.24 * S * k
            half = 1.0 * S * math.sqrt(max(0.0, 1 - ((y0 + 0.1 * S) / (1.15 * S)) ** 2))
            if half < 0.1 * S:
                continue
            steps = 6
            pts = [(-half + 2 * half * t / steps, y0 + 0.08 * S * t / steps) for t in range(steps + 1)]
            stroke("pen_fill", pts, 0.000032)
    else:
        for sx in (-1, 1):
            for sy in (-1, 1):
                stroke("crop", [(sx * 1.3 * S, sy * 1.3 * S), (sx * 1.9 * S, sy * 1.3 * S)], 0.000045)
                stroke("crop", [(sx * 1.3 * S, sy * 1.3 * S), (sx * 1.3 * S, sy * 1.9 * S)], 0.000045)
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
    train(palette == "ura")
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
        cyc.area_light("tube_glow", (-0.1, -0.02, PH + 0.20), (-0.1, -0.02, PH), 0.9, 4000, 0.3, size_y=0.08)
        cyc.haze("haze", (PL + 2.8, 2.5, 0.6), (0, 0.1, 0.3), 0.0015)
    cyc.glass_lets_light_through()
    cyc.post(bloom=0.35 if palette == "omote" else 0.55, threshold=1.0 if palette == "omote" else 0.8)
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
            f"shoes_{pal}": cyc.camera("cam_shoes", tuple(toe + Vector((0.09, -0.004, 0.04))), tuple(toe + Vector((0.006, 0.004, 0.0))), 100, 11.0),
        }
        cams = {k: v for k, v in cams.items() if k in want}
        focus = {f"wide_{pal}": (-0.12, 0.06, PH + 0.04), f"edge_{pal}": SHOES + Vector((0, 0, 0.004)), f"shoes_{pal}": toe}
        cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("window_glass", "haze")
        cyc.render_shots(cams, shots, OUT, "s5", focus=focus, blend=f"s5_{pal}.blend")


if __name__ == "__main__":
    main()
