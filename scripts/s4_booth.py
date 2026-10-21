"""S4「雨夜的电话亭」: the one realistic passage. A 1:12 alley corner in heavy rain: wet asphalt and a strip
of brick pavement, plank walls with soaked posters, a corrugated awning dripping, a Japanese public phone
booth lit from inside with a payphone (Poly Haven's Korean payphone, its handset taken off the hook and hung
on a slack coiled cord), a clear vinyl umbrella upside down with rain pooled in it, crates and a rubbish bag
by the wall, a vending machine far down the alley, infected heart bulbs glowing pink in the puddles.
Surfaces and props are CC0 Poly Haven assets (scripts/fetch_assets.py). Cycles stills.

    blender -b -P scripts/s4_booth.py -- [renders/s4] [long handset umbrella]

Metres, Z up. The alley runs along +Y; the camera sits at its mouth (negative y) 3 cm above the ground.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402
import texlib as T  # noqa: E402

OUT, SHOTS = cyc.args("s4", ["long", "handset", "umbrella"])
BOOTH = Vector((0.0, 0.18, 0.0))     # centre of the booth's footprint
BW, BH, BT = 0.085, 0.19, 0.006      # booth width, height, frame thickness
PHONE = BOOTH + Vector((0.006, BW / 2 - BT - 0.0115, 0.0733))  # the payphone's base centre, back to the rear panel
HOOK = PHONE + Vector((-0.0205, -0.0025, 0.041))             # where the model's cradle hook is after the cut
HANDSET = HOOK + Vector((-0.004, -0.008, -0.034))             # the hanging handset's centre
UMBRELLA = Vector((-0.15, -0.02, 0.0))


# ---------------------------------------------------------------- materials

def water():
    mat, b = A._principled("water", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                       "IOR": 1.33})
    return mat


def vinyl():
    """Clear umbrella film: slightly milky, crumpled."""
    mat, b = A._principled("vinyl", **{"Base Color": (0.92, 0.94, 0.96, 1.0), "Transmission Weight": 1.0,
                                       "Roughness": 0.10, "IOR": 1.45, "Coat Weight": 0.3})
    A._bump(mat, b, 40.0, 0.5, detail=3.0, distance=0.0015)
    return mat


def rain_glass():
    """Tempered glass with rain running down it: a noise stretched along Z drives a fine bump."""
    mat, b = A._principled("rain_glass", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.02,
                                            "IOR": 1.5})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (400.0, 400.0, 25.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 5.0
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.25
    bp.inputs["Distance"].default_value = 0.0006
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mat


def booth_paint():
    """Pale green enamel gone chalky, rust at the seams: the rusty painted metal map under a green coat."""
    return T.pbr("rusty_painted_metal", flat=("#9DBAA6", 0.78), rough=0.5, scale=1 / 8, bump=0.6, name="booth_paint")


def rain_streak_mat():
    mat, b = A._principled("rain_streak", **{"Base Color": (1.0, 1.0, 1.0, 1.0), "Transmission Weight": 1.0,
                                             "Roughness": 0.15, "IOR": 1.33})
    return mat


def materials():
    return dict(
        asphalt=T.pbr("asphalt_02", rough=0.45, scale=1 / 12, name="wet_asphalt"),
        brick=T.pbr("brick_wall_001", rough=0.5, scale=1 / 12, rotation_deg=90, name="wet_brick"),
        kerb=T.pbr("brushed_concrete", tint="#8E8B84", rough=0.3, coat=0.5, scale=1 / 12),
        planks=T.pbr("dark_wooden_planks", rough=0.45, coat=0.3, scale=1 / 10, rotation_deg=90, name="wet_planks"),
        backwall=T.pbr("peeling_painted_wall", tint="#B9B2A4", rough=0.6, scale=1 / 10),
        awning=T.pbr("corrugated_iron_02", scale=1 / 10, rough=0.35, coat=0.4, name="awning_iron"),
        vm=T.pbr("rusty_painted_metal", flat=("#C8CBD0", 0.75), rough=0.4, scale=1 / 8, name="vm_body"),
    )


def wet_ground(M):
    T.wet(M["asphalt"], cover=0.5, scale=6.0, seed=1.3, dark=0.32, puddle_dark=0.18, film_rough=0.05)
    T.wet(M["brick"], cover=0.3, scale=9.0, seed=4.1, dark=0.5, puddle_dark=0.3, film_rough=0.06)
    T.wet(M["kerb"], cover=0.1, scale=9.0, seed=2.2)


# ---------------------------------------------------------------- the alley

def alley(M):
    ground = A.rounded_box("ground", (1.2, 1.5, 0.01), 0.0, [M["asphalt"]])
    ground.location = (0, 0.3, -0.005)
    pave = A.rounded_box("pavement", (0.13, 1.5, 0.004), 0.0005, [M["brick"]])
    pave.location = (0.185, 0.3, 0.002)
    kerb = A.rounded_box("kerb", (0.006, 1.5, 0.006), 0.001, [M["kerb"]])
    kerb.location = (0.118, 0.3, 0.003)
    for sx, name in ((-1, "wall_left"), (1, "wall_right")):
        w = A.rounded_box(name, (0.02, 1.5, 0.32), 0.001, [M["planks"]])
        w.location = (sx * 0.26, 0.3, 0.16)
    back = A.rounded_box("wall_back", (0.6, 0.02, 0.32), 0.001, [M["backwall"]])
    back.location = (0, 1.05, 0.16)
    # corrugated awning on the left wall, drops hanging off its edge
    def corr(i, j):
        u, v = i / 60, j / 6
        return (-0.25 + 0.075 * v, -0.05 + 0.45 * u, 0.175 - 0.012 * v)
    aw = P.grid_mesh("awning", 60, 6, corr, [M["awning"]])
    aw.modifiers.new("solid", "SOLIDIFY").thickness = 0.0008
    for k in range(3):
        bracket = A.rounded_box("awning_bracket", (0.004, 0.004, 0.08), 0.0005, [A.metal("#4A4A48", 0.6, "bracket")])
        bracket.location = (-0.21, 0.02 + 0.18 * k, 0.135)
        bracket.rotation_euler.y = math.radians(-38)
    rnd = random.Random(2)
    for k in range(40):
        y = -0.05 + 0.45 * rnd.random()
        d = P.sphere("drop", rnd.uniform(0.0006, 0.0011), [water()], segments=12)
        d.location = (-0.175, y, 0.163 - rnd.uniform(0.0002, 0.0012))
        d.scale = (1, 1, 1.5)
    # posters on the left wall, rain-soaked, corners lifting
    for k, (y, z, img, tilt) in enumerate([(0.02, 0.10, "frame_A.png", 2), (0.09, 0.095, "frame_B.png", -3),
                                           (0.30, 0.11, "frame_A.png", 4)]):
        po = A.rounded_box("poster", (0.0006, 0.055, 0.034), 0.0, [A.printed(os.path.join(cyc.ROOT, "renders", img), rough=0.35)])
        P.map_uv(po, ("y", "z"), (0.055, 0.034))
        po.location = (-0.2495, y, z)
        po.rotation_euler = (math.radians(tilt), 0, 0)
    # the right wall: a power box, crates and a rubbish bag under the rain
    box = T.model("power_box_01", name="power_box")
    T.place(box, (0.244, 0.42, 0.11), align="centre", yaw_deg=90)
    crate = T.model("wooden_crate_01", name="crate")
    T.place(crate, (0.215, 0.56, 0.004), yaw_deg=12)
    carton = T.model("cardboard_box_01", name="carton")
    T.place(carton, (0.218, 0.62, 0.004 + 0.029), yaw_deg=-20)
    bag = T.model("trashbag", name="trashbag")
    T.place(bag, (0.21, 0.30, 0.004), yaw_deg=40)
    pc = T.model("plastic_crate_01", name="plastic_crate")
    T.place(pc, (-0.215, 0.62, 0.0), yaw_deg=-8)
    lamp = T.model("street_lamp_02", name="street_lamp")
    T.place(lamp, (0.20, 0.95, 0.004))
    street_lamp_on(lamp)
    vending((0.0, 0.78))
    lantern_and_door()


# ---------------------------------------------------------------- the booth

def booth():
    paint = booth_paint()
    glass = rain_glass()
    root = bpy.data.objects.new("booth", None)
    m._link(root)
    root.location = BOOTH
    h, w, t = BH, BW, BT
    for sx in (-1, 1):
        for sy in (-1, 1):
            post = A.rounded_box("booth_post", (t, t, h), 0.0008, [paint], root)
            post.location = (sx * (w / 2 - t / 2), sy * (w / 2 - t / 2), h / 2)
    for z in (0.004, 0.06, h - 0.004):
        for sx in (-1, 1):
            rail = A.rounded_box("booth_rail", (t, w - 2 * t, t), 0.0008, [paint], root)
            rail.location = (sx * (w / 2 - t / 2), 0, z)
        for sy in (-1, 1):
            if sy < 0 and 0.01 < z < h - 0.01:
                continue   # the front is the full-height folding door: no crossbar through the doorway
            rail = A.rounded_box("booth_rail", (w - 2 * t, t, t), 0.0008, [paint], root)
            rail.location = (0, sy * (w / 2 - t / 2), z)
    for sx in (-1, 1):
        low = A.rounded_box("booth_panel", (0.0025, w - 2 * t, 0.052), 0.0005, [paint], root)
        low.location = (sx * (w / 2 - t / 2), 0, 0.033)
        pane = A.rounded_box("booth_glass", (0.001, w - 2 * t, h - 0.075), 0.0, [glass], root)
        pane.location = (sx * (w / 2 - t / 2), 0, 0.063 + (h - 0.075) / 2)
    low = A.rounded_box("booth_panel", (w - 2 * t, 0.0025, 0.052), 0.0005, [paint], root)
    low.location = (0, w / 2 - t / 2, 0.033)
    pane = A.rounded_box("booth_glass", (w - 2 * t, 0.001, h - 0.075), 0.0, [glass], root)
    pane.location = (0, w / 2 - t / 2, 0.063 + (h - 0.075) / 2)
    lw = (w - 2 * t) / 2 - 0.002
    # the left leaf (the handset's side) stands open, folded into the booth; both shots look in through it
    for sx, open_deg in ((-1, 85.0), (1, 0.0)):
        hinge = Vector((sx * (w / 2 - t), -(w / 2 - t / 2), 0.0))
        rot = Matrix.Rotation(math.radians(-sx * open_deg), 4, "Z")
        leaf = A.rounded_box("door_glass", (lw, 0.001, h - 0.012), 0.0, [glass], root)
        leaf.matrix_basis = Matrix.Translation(hinge) @ rot @ Matrix.Translation((-sx * lw / 2, 0, h / 2))
        stile = A.rounded_box("door_stile", (0.004, 0.004, h - 0.012), 0.0005, [paint], root)
        stile.matrix_basis = Matrix.Translation(hinge) @ rot @ Matrix.Translation((-sx * lw, 0, h / 2))
    roof = A.rounded_box("booth_roof", (w + 0.01, w + 0.01, 0.012), 0.002, [paint], root)
    roof.location = (0, 0, h + 0.006)
    lb = A.rounded_box("lightbox", (w - 0.006, 0.012, 0.018), 0.0015, [paint], root)
    lb.location = (0, -(w / 2 + 0.006), h - 0.012)
    face = A.rounded_box("lightbox_face", (w - 0.014, 0.0008, 0.013), 0.0, [A.emissive("#FFE9C0", 2.6)], root)
    face.location = (0, -(w / 2 + 0.0125), h - 0.012)
    txt = m.text("公衆電話", "gothic", 0.0085, 0, 0, "#1B1A19", z=0.0, align="CENTER", valign="CENTER")
    txt.data.materials.clear()
    txt.data.materials.append(A.plastic("#1B1A19", 0.7, "lb_ink"))
    txt.data.extrude = 0.0001
    txt.parent = root
    txt.rotation_euler = (math.radians(90), 0, 0)
    txt.location = (0, -(w / 2 + 0.0132), h - 0.012)
    tube = A.lathe("booth_tube", [(0.0001, -0.03), (0.0025, -0.03), (0.0025, 0.03), (0.0001, 0.03)], 16,
                   [A.emissive("#DCEAF0", 1.4)], root)
    tube.rotation_euler = (0, math.radians(90), 0)
    tube.location = (0, 0.01, h - 0.012)
    # the green NTT payphone (CC BY, Yevhen Avramenko) on the shelf, keypad to the door. Its handset comes off
    # the side hook and hangs below the shelf on a new coiled cord; the model's own cord is taken out.
    phone, pmeshes = T.glb("old_green_payphone", name="payphone", scale=1.0 / 12)
    phone.location = PHONE
    phone.rotation_euler.z = math.pi
    bpy.context.view_layer.update()
    body = pmeshes[0]
    # in the model's own centimetres (x right of the keypad, z up): handset x 9-13, the hooks are the thin
    # pieces at z 31-34, the cord runs from z 28 down to its exit at the bottom
    lo0, hi0 = T.model_bounds(phone)
    to_model = phone.matrix_world.inverted()

    def model_box(lo, hi):
        a, b = to_model @ lo, to_model @ hi
        return (Vector(map(min, a, b)) * 100, Vector(map(max, a, b)) * 100)   # the pivot's space is the model's metres; cm

    def is_handset(lo, hi):
        a, b = model_box(lo, hi)
        return a.x > 8.85 and b.x < 13.05 and b.z > 19.0 and not (b.x - a.x < 1.2 and a.z > 30.0)

    def is_cord(lo, hi):
        a, b = model_box(lo, hi)
        return 7.0 < a.x < 8.0 and a.z < 6.0 and b.z > 27.0

    anchor = None
    bm_cord = T.split_islands(body, is_cord, "phone_cord_old")
    if bm_cord is not None:
        cw = [bm_cord.matrix_world @ v.co for v in bm_cord.data.vertices]
        anchor = min(cw, key=lambda c: c.z)     # where the cord leaves the phone body
        bpy.data.objects.remove(bm_cord)
    handset = T.split_islands(body, is_handset, "handset")
    if handset is not None:
        bpy.context.view_layer.update()
        hw = [handset.matrix_world @ Vector(c) for c in handset.bound_box]
        hc = sum(hw, Vector()) / 8
        top = max(c.z for c in hw)
        shelf_front = BOOTH.y + w / 2 - t - 0.030
        target = Vector((hc.x + 0.004, shelf_front - 0.006, 0.072 - 0.004 - (top - hc.z) - 0.006 + BOOTH.z))
        swing = Matrix.Translation(target) @ Matrix.Rotation(math.radians(9), 4, "X") \
            @ Matrix.Rotation(math.radians(-6), 4, "Y") @ Matrix.Translation(-hc)
        mw = handset.matrix_world.copy()
        handset.parent = None
        handset.matrix_world = swing @ mw
        bpy.context.view_layer.update()
        hw = [handset.matrix_world @ Vector(c) for c in handset.bound_box]
        bottom = Vector((sum(c.x for c in hw) / 8, sum(c.y for c in hw) / 8, min(c.z for c in hw) + 0.0012))
        if anchor is None:
            anchor = Vector((PHONE.x + 0.009, PHONE.y - 0.008, PHONE.z + 0.005))
        # a coiled cord gone slack between the phone and the hanging handset
        cord = []
        for k in range(160):
            u = k / 159
            c = anchor.lerp(bottom, u) + Vector((0.0, -0.004 * math.sin(math.pi * u), -0.010 * math.sin(math.pi * u)))
            a = u * 2 * math.pi * 22
            cord.append((c.x + 0.0011 * math.cos(a), c.y + 0.0011 * math.sin(a), c.z + 0.0004 * math.sin(a)))
        A.tube_along("phone_cord", cord, 0.00028, [A.plastic("#2C2C2E", 0.45, "cord_black")], resolution=3)
    green = A.plastic("#2E6F4F", 0.35, "phone_green")
    shelf = A.rounded_box("shelf", (0.044, 0.030, 0.0025), 0.0005, [booth_paint()], root)
    shelf.location = (PHONE.x - BOOTH.x, w / 2 - t - 0.015, 0.072)
    coin = A.lathe("coin", [(0.0001, 0), (0.0022, 0), (0.0022, 0.0004), (0.0001, 0.0004)], 24, [A.brass()], root)
    coin.location = (PHONE.x - BOOTH.x + 0.016, w / 2 - t - 0.026, 0.0733)
    note = A.rounded_box("note", (0.012, 0.009, 0.0008), 0.0002, [A.printed(os.path.join(cyc.ROOT, "renders", "frame_A.png"))], root)
    P.map_uv(note, ("x", "y"), (0.012, 0.009))
    note.location = (PHONE.x - BOOTH.x - 0.013, w / 2 - t - 0.025, 0.0735)
    note.rotation_euler.z = math.radians(18)
    return root


def vinyl_beads():
    """Clear umbrella vinyl after rain: a thin see-through film with a Fresnel reflection, a little milky,
    covered in water beads (Voronoi cells, in the canopy's own metres) that catch the lights."""
    mat = bpy.data.materials.new("vinyl")
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = 260.0          # a bead every ~4 mm of real vinyl
    vo.inputs["Randomness"].default_value = 0.9
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")      # a random value per cell: bead size, some cells dry
    nt.links.new(vo.outputs["Color"], sep.inputs["Color"])
    rad = nt.nodes.new("ShaderNodeMapRange")
    rad.inputs["To Min"].default_value, rad.inputs["To Max"].default_value = 0.08, 0.24
    nt.links.new(sep.outputs["Red"], rad.inputs["Value"])
    ratio = nt.nodes.new("ShaderNodeMath")
    ratio.operation = "DIVIDE"
    nt.links.new(vo.outputs["Distance"], ratio.inputs[0])
    nt.links.new(rad.outputs["Result"], ratio.inputs[1])
    dome = nt.nodes.new("ShaderNodeMapRange")          # 1 at the bead centre, 0 at its edge, a rounded cap
    dome.interpolation_type = "SMOOTHSTEP"
    dome.inputs["From Min"].default_value, dome.inputs["From Max"].default_value = 1.0, 0.0
    nt.links.new(ratio.outputs[0], dome.inputs["Value"])
    keep = nt.nodes.new("ShaderNodeMath")
    keep.operation = "GREATER_THAN"
    keep.inputs[1].default_value = 0.55
    nt.links.new(sep.outputs["Green"], keep.inputs[0])
    bead = nt.nodes.new("ShaderNodeMath")
    bead.operation = "MULTIPLY"
    nt.links.new(dome.outputs["Result"], bead.inputs[0])
    nt.links.new(keep.outputs[0], bead.inputs[1])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.0004
    nt.links.new(bead.outputs[0], bp.inputs["Height"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.93, 0.95, 0.96, 1.0)
    gl = None
    for idname in ("ShaderNodeBsdfGlossy", "ShaderNodeBsdfAnisotropic"):
        try:
            gl = nt.nodes.new(idname)
            break
        except RuntimeError:
            continue
    gl.inputs["Roughness"].default_value = 0.02
    nt.links.new(bp.outputs["Normal"], gl.inputs["Normal"])
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.45
    nt.links.new(bp.outputs["Normal"], fr.inputs["Normal"])
    film = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], film.inputs[0])
    nt.links.new(tr.outputs[0], film.inputs[1])
    nt.links.new(gl.outputs[0], film.inputs[2])
    milk = nt.nodes.new("ShaderNodeBsdfDiffuse")
    milk.inputs["Color"].default_value = (0.85, 0.87, 0.88, 1.0)
    hazy = nt.nodes.new("ShaderNodeMixShader")
    hazy.inputs[0].default_value = 0.025
    nt.links.new(film.outputs[0], hazy.inputs[1])
    nt.links.new(milk.outputs[0], hazy.inputs[2])
    nt.links.new(hazy.outputs[0], out.inputs["Surface"])
    return mat


def umbrella(loc, yaw_deg=205.0, tilt_deg=26.0):
    """al_syd's umbrella (CC BY) made a clear vinyl one and left upside down on the wet ground: canopy a bowl,
    the vermilion J-handle up in the air, rain pooled in it."""
    from mathutils.geometry import convex_hull_2d
    pivot, meshes = T.glb("umbrella_alsyd", name="umbrella", scale=1.0 / 12)
    bpy.context.view_layer.update()
    frame = next(o for o in meshes if o.name.startswith("Helix"))
    canopy = next(o for o in meshes if o.name.startswith("Line"))
    canopy.name = "umbrella_canopy"
    inv = pivot.matrix_world.inverted()

    def native(o):
        mw = inv @ o.matrix_world
        return [mw @ v.co for v in o.data.vertices]

    cpts, fpts = native(canopy), native(frame)
    cc = sum(cpts, Vector()) / len(cpts)
    handle_end = max(fpts, key=lambda p: (p - cc).length)
    d = (handle_end - cc).normalized()
    # the handle is the last 20 cm of the frame along the shaft; in the frame's own coordinates for the shader
    to_frame = (inv @ frame.matrix_world).inverted()
    he_l, cc_l = to_frame @ handle_end, to_frame @ cc
    d_l = (he_l - cc_l).normalized()
    per_m = (he_l - cc_l).length / (handle_end - cc).length
    t_h = (he_l - cc_l).length - 0.20 * per_m
    fm = bpy.data.materials.new("umbrella_frame")
    try:
        fm.use_nodes = True
    except AttributeError:
        pass
    nt = fm.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = tuple(cc_l)
    nt.links.new(tc.outputs["Object"], sub.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = tuple(d_l)
    nt.links.new(sub.outputs[0], dot.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = t_h
    nt.links.new(dot.outputs["Value"], gt.inputs[0])
    for name, metal, red in (("Base Color", (0.55, 0.56, 0.58, 1.0), m.srgb("#C4301E")), ("Metallic", 1.0, 0.0),
                             ("Roughness", 0.28, 0.32)):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA" if name == "Base Color" else "FLOAT"
        nt.links.new(gt.outputs[0], mx.inputs["Factor"])
        if name == "Base Color":
            mx.inputs["A"].default_value, mx.inputs["B"].default_value = metal, red
            nt.links.new(mx.outputs["Result"], b.inputs[name])
        else:
            mx.inputs[2].default_value, mx.inputs[3].default_value = metal, red
            nt.links.new(mx.outputs[0], b.inputs[name])
    b.inputs["Coat Weight"].default_value = 0.5
    frame.data.materials.clear()
    frame.data.materials.append(fm)
    canopy.data.materials.clear()
    canopy.data.materials.append(vinyl_beads())
    # turn it over: the canopy-to-handle direction points up, leaning towards yaw_deg
    az, tl = math.radians(yaw_deg), math.radians(tilt_deg)
    up = Vector((math.sin(tl) * math.cos(az), math.sin(tl) * math.sin(az), math.cos(tl)))
    pivot.rotation_mode = "QUATERNION"
    pivot.rotation_quaternion = d.rotation_difference(up)
    pivot.location = loc
    bpy.context.view_layer.update()
    cw = [canopy.matrix_world @ v.co for v in canopy.data.vertices]
    fw = [frame.matrix_world @ v.co for v in frame.data.vertices]
    zmin = min(p.z for p in cw + fw)
    pivot.location.z += loc[2] - zmin + 0.0002
    bpy.context.view_layer.update()
    cw = [canopy.matrix_world @ v.co for v in canopy.data.vertices]
    # the pool: water level a third of the way up the bowl, its rim where the canopy crosses that level
    axis = pivot.matrix_world.to_3x3() @ d
    axis.normalize()
    base = min(cw, key=lambda p: p.z)
    radial = sorted(cw, key=lambda p: ((p - base) - axis * (p - base).dot(axis)).length)
    rim = radial[int(len(radial) * 0.9):]
    z_rim = min(p.z for p in rim)
    z_w = base.z + 0.38 * (z_rim - base.z)
    below = [p for p in cw if p.z <= z_w]
    if len(below) >= 3:
        hull = [below[i] for i in convex_hull_2d([p.xy for p in below])]
        cen = sum((p.xy for p in hull), Vector((0.0, 0.0))) / len(hull)
        poly = [cen + (p.xy - cen) * 0.95 for p in hull]
        bm = bmesh.new()
        bm.faces.new([bm.verts.new((p.x, p.y, z_w)) for p in poly])
        me = bpy.data.meshes.new("umbrella_water")
        bm.to_mesh(me)
        bm.free()
        pool = A._obj("umbrella_water", me, [water()])
        pool.modifiers.new("solid", "SOLIDIFY").thickness = 0.0012
    return pivot


def vending(loc_xy, wall_x=0.25, base_z=0.004):
    """Watanuki_San's red vending machine (CC BY), back to the right wall, lit for the night."""
    vm, meshes = T.glb("red_vending", name="vending", scale=1.0 / 12)
    for ob in list(meshes):
        if any(ms.material and ms.material.name.startswith("Concrete_Floor") for ms in ob.material_slots):
            meshes.remove(ob)
            bpy.data.objects.remove(ob)
    bpy.context.view_layer.update()
    lo, hi = T.model_bounds(vm)
    panel = next(o for o in meshes if any(ms.material and ms.material.name.startswith("Vending_1_light") for ms in o.material_slots))
    pc = sum((panel.matrix_world @ Vector(c) for c in panel.bound_box), Vector()) / 8
    front_plus_x = pc.x > (lo.x + hi.x) / 2
    vm.rotation_euler.z = math.pi if front_plus_x else 0.0    # the lit front faces -x, into the alley
    depth = hi.x - lo.x
    vm.location = (wall_x - depth / 2 - 0.002, loc_xy[1], base_z)
    for mat in {ms.material for o in meshes for ms in o.material_slots if ms.material}:
        b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b is None:
            continue
        if mat.name.startswith(("Vending_1_light", "Lamp_Light_bulb")):
            b.inputs["Emission Color"].default_value = (0.90, 0.95, 1.0, 1.0)
            b.inputs["Emission Strength"].default_value = 9.0
        elif mat.name.startswith(("Vending_1_sign", "Vending_price")) and b.inputs["Base Color"].links:
            mat.node_tree.links.new(b.inputs["Base Color"].links[0].from_socket, b.inputs["Emission Color"])
            b.inputs["Emission Strength"].default_value = 2.5
    front_x = wall_x - depth - 0.004
    cyc.area_light("vending_glow", (front_x - 0.004, loc_xy[1], base_z + 0.09), (front_x - 0.2, loc_xy[1], 0.0), 0.06,
                   6500, 1.4, size_y=0.08, color="#EAF2FF")
    return vm


def lantern_and_door(y=0.47, wall_x=-0.25):
    """A red paper lantern (DeepDown, CC BY) over a frosted sliding door on the left wall: warm light and a red
    one for the wet ground to throw back."""
    lan, meshes = T.glb("chochin", name="chochin", scale=1.0 / 12)
    lo, hi = T.model_bounds(lan)
    h = hi.z - lo.z
    top = 0.186
    lan.location = (wall_x + 0.024, y, top - h)
    for mat in {ms.material for o in meshes for ms in o.material_slots if ms.material}:
        b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if b is not None and b.inputs["Base Color"].links:
            mat.node_tree.links.new(b.inputs["Base Color"].links[0].from_socket, b.inputs["Emission Color"])
            b.inputs["Emission Strength"].default_value = 3.5
    iron = A.metal("#2B2B2C", 0.5, "bracket_iron")
    A.tube_along("lantern_bracket", [(wall_x, y, top + 0.004), (wall_x + 0.024, y, top + 0.004)], 0.0008, [iron])
    cyc.point_light("lantern_glow", (wall_x + 0.024, y, top - h * 0.45), 2200, 0.45, radius=0.012, color="#FF5A2E")
    # the door: warm frosted panes in a kumiko lattice
    dm, b = A._principled("frosted_door", **{"Base Color": (0.9, 0.85, 0.75, 1.0), "Roughness": 0.6})
    nt = dm.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 0.012
    br.inputs["Row Height"].default_value = 0.016
    br.inputs["Mortar Size"].default_value = 0.0012
    br.inputs["Color1"].default_value = m.srgb("#FFD9A0")
    br.inputs["Color2"].default_value = m.srgb("#FFCF8E")
    br.inputs["Mortar"].default_value = m.srgb("#2A1D14")
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Emission Color"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Emission Strength"].default_value = 1.6
    door = A.rounded_box("izakaya_door", (0.002, 0.07, 0.15), 0.0, [dm])
    door.location = (wall_x + 0.001, y, 0.004 + 0.075)
    frame = A.rounded_box("izakaya_frame", (0.004, 0.078, 0.158), 0.0005, [A.stained_wood("#3A2617", (), (), light="#4A3020")])
    frame.location = (wall_x - 0.0005, y, 0.004 + 0.079)
    cyc.area_light("door_spill", (wall_x + 0.006, y, 0.06), (wall_x + 0.2, y, 0.0), 0.07, 3000, 0.5, size_y=0.12, color="#FFC98A")


def street_lamp_on(root):
    """Light the bulb of street_lamp_02 and put a lamp where it is."""
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    for ob in meshes:
        for ms in ob.material_slots:
            mat = ms.material
            if mat is None:
                continue
            b = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if b is None:
                continue
            if mat.name.endswith("_bulb"):
                b.inputs["Emission Color"].default_value = A.kelvin(2700) + (1.0,)
                b.inputs["Emission Strength"].default_value = 40.0
            elif mat.name.endswith("_glass"):
                b.inputs["Emission Color"].default_value = A.kelvin(2700) + (1.0,)
                b.inputs["Emission Strength"].default_value = 3.0
    lo, hi = T.model_bounds(root)
    cyc.point_light("street_lamp_light", ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z - 0.012), 2700, 0.8, radius=0.004)


def puddles_and_bulbs(seed=5):
    """Infected heart bulbs lying in the wet, each with its pink glow on the ground."""
    rnd = random.Random(seed)
    for k, (x, y) in enumerate([(-0.12, 0.12), (0.06, -0.04), (0.0, 0.42), (-0.18, 0.38)]):
        for _ in range(2):
            b = A.heart_bulb("infected", 0.0045, seed=k * 3)
            b.location = (x + rnd.uniform(-0.025, 0.025), y + rnd.uniform(-0.015, 0.015), 0.0018)
            b.rotation_euler = (math.radians(rnd.uniform(75, 105)), 0, math.radians(rnd.uniform(0, 360)))
            cyc.point_light("bulb_pink", (b.location.x, b.location.y, 0.006), 6500, 0.015, radius=0.004, color="#FF3D8B")


def rain(count=2600, seed=11):
    rnd = random.Random(seed)
    streak = A.lathe("rain_streak", [(0.00003, -0.007), (0.00009, -0.005), (0.00009, 0.005), (0.00003, 0.007)], 6, [rain_streak_mat()])
    coll = P.library_collection("rain_lib", [streak])
    pts = []
    while len(pts) < count:
        p = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.35, 0.6), rnd.uniform(0.002, 0.3))
        if abs(p[0] - BOOTH.x) < BW / 2 + 0.01 and abs(p[1] - BOOTH.y) < BW / 2 + 0.01 and p[2] < BH + 0.02:
            continue   # dry inside the booth
        pts.append(p)
    ob = P.instance_on_points("rain", pts, coll, seed=seed, scale=(0.6, 1.5), rotate=False)
    ob.rotation_euler = (math.radians(6), math.radians(3), 0)
    return ob


def build():
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0005, 0.0006, 0.0012))
    M = materials()
    wet_ground(M)
    alley(M)
    booth()
    umbrella(tuple(UMBRELLA))
    puddles_and_bulbs()
    rain()
    cyc.area_light("booth_light", tuple(BOOTH + Vector((0, 0.01, BH - 0.02))), tuple(BOOTH + Vector((0, 0, 0.02))), 0.05,
                   5000, 2.2, size_y=0.03, color="#D9EBF2")
    cyc.area_light("lightbox_glow", tuple(BOOTH + Vector((0, -BW / 2 - 0.02, BH - 0.01))), tuple(BOOTH + Vector((0, -0.2, 0.0))),
                   0.06, 3200, 0.12, size_y=0.015)
    cyc.haze("haze", (0.7, 1.5, 0.36), (0, 0.3, 0.18), 0.003, color="#A9C4E0", anisotropy=0.55)
    cyc.glass_lets_light_through(("clear_glass", "rain_glass", "water", "vinyl"))
    cyc.post(bloom=0.55, threshold=0.8, size=0.6, dispersion=0.004)


def main():
    build()
    global HANDSET
    hs = bpy.data.objects.get("handset")
    if hs is not None:
        bpy.context.view_layer.update()
        pts = [hs.matrix_world @ Vector(c) for c in hs.bound_box]
        HANDSET = sum(pts, Vector()) / 8
        print("handset at mm", tuple(round(v * 1000, 1) for v in HANDSET))
    can = bpy.data.objects.get("umbrella_canopy")
    umb = UMBRELLA + Vector((0, 0, 0.012))
    if can is not None:
        pts = [can.matrix_world @ v.co for v in can.data.vertices]
        umb = sum(pts, Vector()) / len(pts)
        print("umbrella canopy centre mm", tuple(round(v * 1000, 1) for v in umb))
    cams = {
        "long": cyc.camera("cam_long", (-0.075, -0.23, 0.03), tuple(HANDSET + Vector((0, 0, -0.02))), 35, 5.6),
        "handset": cyc.camera("cam_handset", tuple(HANDSET + Vector((-0.03, -0.19, 0.012))), tuple(HANDSET + Vector((0.0, 0, 0.004))), 100, 8.0),
        "umbrella": cyc.camera("cam_umbrella", tuple(umb + Vector((0.07, -0.17, 0.055))), tuple(umb), 50, 8.0),
    }
    cams = {k: v for k, v in cams.items() if k in SHOTS}
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("rain", "booth_glass", "door_glass", "umbrella_canopy", "umbrella_water")
    cyc.render_shots(cams, SHOTS, OUT, "s4", focus={"long": HANDSET, "handset": HANDSET, "umbrella": umb})


if __name__ == "__main__":
    main()
