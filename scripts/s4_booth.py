"""S4「雨夜的电话亭」: the one realistic passage. A 1:12 alley corner in heavy rain: wet asphalt with rain rings
in its puddles and a strip of brick pavement, plank walls with soaked posters, a corrugated awning dripping, a
Japanese public phone booth lit from inside with the green payphone (its handset off the hook, hanging on a
slack coiled cord), a clear vinyl umbrella upside down with rain pooled in it, crates and a rubbish bag by the
wall, two lit signs and a red lantern, a vending machine at the far end, infected heart bulbs glowing pink in
the puddles. Surfaces and most props are CC0 Poly Haven assets, the payphone, vending machine and lantern are
CC BY (docs/CREDITS.md; scripts/fetch_assets.py fetches them). Cycles stills.

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
        planks=T.pbr("dark_wooden_planks", rough=0.4, scale=1 / 10, rotation_deg=90, name="wet_planks"),
        backwall=T.pbr("peeling_painted_wall", tint="#B9B2A4", rough=0.6, scale=1 / 10),
        awning=T.pbr("corrugated_iron_02", scale=1 / 10, rough=0.35, coat=0.4, name="awning_iron"),
        vm=T.pbr("rusty_painted_metal", flat=("#C8CBD0", 0.75), rough=0.4, scale=1 / 8, name="vm_body"),
    )


def wet_ground(M):
    T.wet(M["asphalt"], cover=0.5, scale=6.0, seed=1.3, dark=0.32, puddle_dark=0.18, film_rough=0.04, ripple=1.0)
    T.wet(M["brick"], cover=0.3, scale=9.0, seed=4.1, dark=0.5, puddle_dark=0.3, film_rough=0.05, ripple=0.8)
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
    vending(0.86)
    lantern_and_door()
    signboard("sign_snack", [("スナック", 0.009), ("こころ", 0.022)], -0.25, +1, 0.66, 0.152, w=0.04, h=0.13, glow=1.0,
              ink_glow=0.2)
    signboard("sign_tabaco", [("たばこ", 0.015)], 0.25, -1, 0.50, 0.17, face="#C9281D", ink="#FBF7EE", h=0.07,
              glow=2.0, ink_glow=3.0)


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


def vinyl_film(wave_scale=250.0):
    """Clear umbrella vinyl: a thin see-through film with a Fresnel reflection, a little milky, never quite flat
    (slow waves a few centimetres across from the folding, `wave_scale` per metre of the canopy's own space).
    The rain on it is real geometry; at 1:12 a bead is a few pixels, so it is not faked in the shader."""
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
    wave = nt.nodes.new("ShaderNodeTexNoise")
    wave.inputs["Scale"].default_value = wave_scale
    wave.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.8
    bp.inputs["Distance"].default_value = 0.0004
    nt.links.new(wave.outputs["Fac"], bp.inputs["Height"])
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
    fr = nt.nodes.new("ShaderNodeFresnel")              # two faces of film: a little more than one surface's 4 %
    fr.inputs["IOR"].default_value = 1.55
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


def pool_water():
    """Rain water standing in the umbrella, rings running across it."""
    mat, b = A._principled("water_pool", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                            "IOR": 1.33})
    nt = mat.node_tree
    nt.links.new(T.ripple_normal(nt, T.ripple_height(nt, 420.0)), b.inputs["Normal"])
    return mat


def _drop_template(seg=10, rings=4):
    """A water drop sitting on a surface: a dome of unit radius on a flat base at z = 0. Returns (verts, faces)."""
    verts = [(0.0, 0.0, 0.0)]
    for i in range(rings):
        e = 0.5 * math.pi * i / rings
        verts += [(math.cos(e) * math.cos(2 * math.pi * k / seg), math.cos(e) * math.sin(2 * math.pi * k / seg),
                   math.sin(e)) for k in range(seg)]
    verts.append((0.0, 0.0, 1.0))
    top = len(verts) - 1

    def ring(i, k):
        return 1 + i * seg + k % seg
    faces = [(0, ring(0, k + 1), ring(0, k)) for k in range(seg)]
    for i in range(rings - 1):
        faces += [(ring(i, k), ring(i, k + 1), ring(i + 1, k + 1), ring(i + 1, k)) for k in range(seg)]
    faces += [(ring(rings - 1, k), ring(rings - 1, k + 1), top) for k in range(seg)]
    return verts, faces


def vinyl_umbrella(loc, yaw_deg=205.0, tilt_deg=27.0, seed=3, drops=1800):
    """A convenience-store clear umbrella (ビニール傘) built to its real measure: eight 60 cm steel ribs under a
    taut clear vinyl dome, white plastic rib tips, runner and top cap, a steel shaft and a vermilion J-handle.
    Built upright (apex at the origin, the shaft down -Z), then turned over and laid on the wet ground on the low
    side of its canopy, the handle in the air; rain beaded on the film and pooled in the bowl."""
    from bisect import bisect_left
    from mathutils.geometry import convex_hull_2d
    s = 1.0 / 12
    RS, RIB, N = 0.70 * s, 0.60 * s, 8
    alpha = RIB / RS                      # the rib tips' polar angle on the canopy's sphere, 49 degrees
    psi0, scallop = 0.012, 0.035          # the opening under the top cap; how far the hem rises between tips
    C = Vector((0.0, 0.0, -RS))

    def sph(psi, th):
        return Vector((RS * math.sin(psi) * math.cos(th), RS * math.sin(psi) * math.sin(th), -RS * (1 - math.cos(psi))))

    root = bpy.data.objects.new("umbrella", None)
    m._link(root)
    # the canopy: each gore is ruled between its two ribs, chord by chord, and gives a little towards the hem
    bm = bmesh.new()
    NU, NP = 14, 26
    hem = []
    for k in range(N):
        t0, t1 = 2 * math.pi * k / N, 2 * math.pi * (k + 1) / N
        grid = []
        for j in range(NP + 1):
            row = []
            for i in range(NU + 1):
                u = i / NU
                psi = psi0 + (alpha - scallop * math.sin(math.pi * u) - psi0) * j / NP
                p = sph(psi, t0).lerp(sph(psi, t1), u)
                p -= (p - C).normalized() * (0.004 * RS * math.sin(math.pi * u) * j / NP)
                row.append(bm.verts.new(p))
            grid.append(row)
        hem += [v.co.copy() for v in grid[NP][:-1]]
        for j in range(NP):
            for i in range(NU):
                bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-8)
    step = 2 * math.pi / N

    def on_rib(v):
        a = math.atan2(v.co.y, v.co.x) % step
        return min(a, step - a) < 1e-6
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if on_rib(e.verts[0]) and on_rib(e.verts[1]):
            e.smooth = False                  # the film folds over each rib
    me = bpy.data.meshes.new("umbrella_canopy")
    bm.to_mesh(me)
    bm.free()
    canopy = A._obj("umbrella_canopy", me, [vinyl_film()], root)

    # the frame: ribs just under the film, stretchers from the runner, white plastic tips, cap, notch and runner
    steel = A.metal("#34373A", 0.35, "rib_steel")
    white = A.plastic("#F1EFE9", 0.35, "umbrella_white")
    r_rib = 0.0013 * s
    psi_a = 0.27 * s / RS                 # the stretchers meet the ribs 27 cm out
    a0 = sph(psi_a, 0.0) - (sph(psi_a, 0.0) - C).normalized() * 2 * r_rib
    r_run = 0.0095 * s
    z_run = a0.z - math.sqrt(max((0.29 * s) ** 2 - (a0.xy.length - r_run) ** 2, 1e-12))
    for k in range(N):
        th = 2 * math.pi * k / N
        pts = []
        for j in range(25):
            p = sph(psi0 * 0.5 + (alpha - psi0 * 0.5) * j / 24, th)
            pts.append(tuple(p - (p - C).normalized() * 1.4 * r_rib))
        A.tube_along("umbrella_rib", pts, r_rib, [steel], root, resolution=2)
        a = Matrix.Rotation(th, 3, "Z") @ a0
        r = Vector((r_run * math.cos(th), r_run * math.sin(th), z_run))
        A.tube_along("umbrella_stretcher", [tuple(r), tuple(r.lerp(a, 0.5)), tuple(a)], 0.0009 * s, [steel], root,
                     resolution=2)
        tip = sph(alpha, th)
        d = Vector((math.cos(alpha) * math.cos(th), math.cos(alpha) * math.sin(th), -math.sin(alpha)))
        cap = A.lathe("umbrella_tip", [(0.0001 * s, -0.012 * s), (0.0034 * s, -0.012 * s), (0.0036 * s, 0.004 * s),
                                       (0.0022 * s, 0.009 * s), (0.0001 * s, 0.010 * s)], 12, [white], root)
        cap.matrix_basis = Matrix.Translation(tip - (tip - C).normalized() * r_rib) \
            @ Vector((0.0, 0.0, 1.0)).rotation_difference(d).to_matrix().to_4x4()
    A.lathe("umbrella_cap", [(0.0001 * s, -0.004 * s), (0.010 * s, -0.004 * s), (0.010 * s, 0.010 * s),
                             (0.006 * s, 0.028 * s), (0.0001 * s, 0.032 * s)], 20, [white], root)
    A.lathe("umbrella_notch", [(0.0001 * s, -0.03 * s), (0.012 * s, -0.03 * s), (0.013 * s, -0.004 * s),
                               (0.0001 * s, -0.004 * s)], 20, [white], root)
    A.lathe("umbrella_runner", [(0.0001 * s, z_run - 0.02 * s), (r_run, z_run - 0.02 * s), (r_run * 1.1, z_run + 0.015 * s),
                                (0.0001 * s, z_run + 0.02 * s)], 20, [white], root)
    z_h = -0.66 * s
    A.lathe("umbrella_shaft", [(0.0001 * s, z_h), (0.0045 * s, z_h), (0.0045 * s, 0.0), (0.0001 * s, 0.0)], 16,
            [A.metal("#C3C6CA", 0.18, "shaft_steel")], root)
    # the J-handle: a 10 cm grip, then the hook
    hook = 0.032 * s
    e = Vector((0.0, 0.0, z_h - 0.10 * s))
    pts = [(0.0, 0.0, z_h + 0.01 * s), (0.0, 0.0, z_h - 0.05 * s), tuple(e)]
    for q in range(1, 13):
        ph = math.pi * q / 12
        pts.append((hook - hook * math.cos(ph), 0.0, e.z - hook * math.sin(ph)))
    pts.append((2 * hook, 0.0, e.z + 0.012 * s))
    lacquer = A.plastic("#D0341F", 0.22, "umbrella_handle")
    next(n for n in lacquer.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Coat Weight"].default_value = 0.8
    A.tube_along("umbrella_handle", pts, 0.0105 * s, [lacquer], root, resolution=4)

    # rain beaded on the film: real drops, most on the inside (it faces the sky now), a few under the hem
    rnd = random.Random(seed)
    me.calc_loop_triangles()
    tris, acc, total = list(me.loop_triangles), [], 0.0
    for lt in tris:
        total += lt.area
        acc.append(total)
    dv, df = _drop_template()
    verts, faces = [], []
    for _ in range(drops):
        lt = tris[min(bisect_left(acc, rnd.random() * total), len(tris) - 1)]
        a, b, c = (me.vertices[i].co for i in lt.vertices)
        r1, r2 = rnd.random(), rnd.random()
        if r1 + r2 > 1.0:
            r1, r2 = 1.0 - r1, 1.0 - r2
        p = a + (b - a) * r1 + (c - a) * r2
        n = Vector(lt.normal)
        if rnd.random() < 0.72:
            n = -n                        # the face normals point out of the dome; the inside is up now
        r = math.exp(rnd.uniform(math.log(0.0010 * s), math.log(0.0035 * s)))   # beads 2-7 mm across
        rot = Vector((0.0, 0.0, 1.0)).rotation_difference(n).to_matrix() @ Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 3, "Z")
        sx = rnd.uniform(0.85, 1.2)
        base = len(verts)
        for x, y, z in dv:
            verts.append(tuple(p + n * 0.00001 + rot @ Vector((x * r * sx, y * r, z * r * 0.75))))
        faces += [tuple(base + i for i in f) for f in df]
    dm = bpy.data.meshes.new("umbrella_drops")
    dm.from_pydata(verts, [], faces)
    for poly in dm.polygons:
        poly.use_smooth = True
    A._obj("umbrella_drops", dm, [water()], root)

    # turn it over: the shaft up, leaning tilt_deg towards yaw_deg; then down onto the ground
    az, tl = math.radians(yaw_deg), math.radians(tilt_deg)
    up = Vector((math.sin(tl) * math.cos(az), math.sin(tl) * math.sin(az), math.cos(tl)))
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Vector((0.0, 0.0, -1.0)).rotation_difference(up)
    root.location = loc
    bpy.context.view_layer.update()
    low = min((ob.matrix_world @ v.co).z for ob in root.children if ob.type == "MESH" for v in ob.data.vertices)
    root.location.z += loc[2] - low + 0.00003
    bpy.context.view_layer.update()
    # the pool: rain in the bottom of the bowl, as deep as the hem lets it be before it spills
    cw = [canopy.matrix_world @ v.co for v in me.vertices]
    z_low = min(p.z for p in cw)
    z_spill = min((root.matrix_world @ h).z for h in hem)
    z_w = z_low + min(0.0022, 0.8 * (z_spill - z_low))
    below = [p for p in cw if p.z <= z_w]
    print(f"umbrella: pool {1000 * (z_w - z_low):.2f} mm deep, hem spills at {1000 * (z_spill - z_low):.2f} mm, "
          f"{len(below)} canopy points under water")
    if len(below) >= 3 and z_w > z_low + 0.0003:
        hull = [below[i] for i in convex_hull_2d([p.xy for p in below])]
        cen = sum((p.xy for p in hull), Vector((0.0, 0.0))) / len(hull)
        bm = bmesh.new()
        bm.faces.new([bm.verts.new((*(cen + (p.xy - cen) * 0.985), z_w)) for p in hull])
        pm = bpy.data.meshes.new("umbrella_water")
        bm.to_mesh(pm)
        bm.free()
        pool = A._obj("umbrella_water", pm, [pool_water()])
        pool.modifiers.new("solid", "SOLIDIFY").thickness = 0.0012
    return root


def vending(y, wall_x=-0.25, facing_deg=-25.0, base_z=0.004):
    """Watanuki_San's red vending machine (CC BY) far down the alley, back to the left wall, its lit front turned
    across the alley and a little towards the mouth: the cold white light the script puts at the end."""
    vm, meshes = T.glb("red_vending", name="vending", scale=1.0 / 12)
    for ob in list(meshes):
        if any(ms.material and ms.material.name.startswith("Concrete_Floor") for ms in ob.material_slots):
            meshes.remove(ob)
            bpy.data.objects.remove(ob)
    bpy.context.view_layer.update()
    lo, hi = T.model_bounds(vm)
    panel = next(o for o in meshes if any(ms.material and ms.material.name.startswith("Vending_1_light") for ms in o.material_slots))
    pc = sum((panel.matrix_world @ Vector(c) for c in panel.bound_box), Vector()) / 8
    native = 0.0 if pc.x > (lo.x + hi.x) / 2 else 180.0     # the lit front faces +x or -x as modelled
    depth = hi.x - lo.x
    vm.rotation_euler.z = math.radians(facing_deg - native)
    bpy.context.view_layer.update()
    lo, hi = T.model_bounds(vm)
    side = 1 if wall_x < 0 else -1
    spot = Vector((wall_x + side * ((hi.x - lo.x) / 2 + 0.002), y, base_z))
    vm.location += spot - Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
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
    a = math.radians(facing_deg)
    f = Vector((math.cos(a), math.sin(a), 0.0))
    front = Vector((spot.x, y, base_z + 0.09)) + f * (depth / 2 + 0.005)
    cyc.area_light("vending_glow", tuple(front), tuple(front + f * 0.2 - Vector((0, 0, 0.09))), 0.06, 6500, 1.4,
                   size_y=0.08, color="#EAF2FF")
    return vm


def signboard(name, lines, wall_x, side, y, z_mid, face="#F3F0E8", ink="#C4301E", w=0.036, h=0.12, t=0.011,
              glow=4.0, ink_glow=2.2):
    """A projecting light box (袖看板) on two arms: a steel case, acrylic faces lit from inside, the name set top
    to bottom in the ink colour. side = +1 on the left wall (it sticks out towards +x), -1 on the right;
    lines = [(text, character size), ...] from the top. It faces the alley's mouth, as they are hung to."""
    root = bpy.data.objects.new(name, None)
    m._link(root)
    cx = wall_x + side * (0.007 + w / 2)
    root.location = (cx, y, z_mid)
    A.rounded_box(name + "_case", (w, t, h), 0.0012, [A.metal("#2A2B2D", 0.45, "sign_case")], root)
    acrylic, _ = A._principled(name + "_acrylic", **{"Base Color": m.srgb(face), "Emission Color": m.srgb(face),
                                                     "Emission Strength": glow, "Roughness": 0.12, "Coat Weight": 0.6})
    ink_mat, _ = A._principled(name + "_ink", **{"Base Color": m.srgb(ink), "Emission Color": m.srgb(ink),
                                                 "Emission Strength": ink_glow, "Roughness": 0.15, "Coat Weight": 0.6})
    for sy in (-1, 1):
        pane = A.rounded_box(name + "_face", (w - 0.003, 0.0008, h - 0.003), 0.0, [acrylic], root)
        pane.location = (0, sy * (t / 2 + 0.0002), 0)
    total = sum(len(body) * size * 1.04 for body, size in lines) + sum(0.25 * size for _, size in lines[:-1])
    z = total / 2
    for body, size in lines:
        for ch in body:
            tx = m.text(ch, "gothic", size, 0, 0, ink, z=0.0, align="CENTER", valign="TOP")
            tx.data.materials.clear()
            tx.data.materials.append(ink_mat)
            tx.data.extrude = 0.00003
            tx.parent = root
            tx.rotation_euler = (math.radians(90), 0, 0)
            tx.location = (0, -(t / 2 + 0.0007), z)
            z -= size * 1.04
        z -= size * 0.25
    iron = A.metal("#1E1F21", 0.5, "sign_arm")
    edge = cx - side * w / 2
    for dz in (h / 2 - 0.01, -h / 2 + 0.01):
        A.tube_along(name + "_arm", [(wall_x, y, z_mid + dz), ((wall_x + edge) / 2, y, z_mid + dz), (edge, y, z_mid + dz)],
                     0.0006, [iron])
    return root


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
    vinyl_umbrella(tuple(UMBRELLA))
    puddles_and_bulbs()
    rain()
    cyc.area_light("booth_light", tuple(BOOTH + Vector((0, 0.01, BH - 0.02))), tuple(BOOTH + Vector((0, 0, 0.02))), 0.05,
                   5000, 2.2, size_y=0.03, color="#D9EBF2")
    cyc.area_light("lightbox_glow", tuple(BOOTH + Vector((0, -BW / 2 - 0.02, BH - 0.01))), tuple(BOOTH + Vector((0, -0.2, 0.0))),
                   0.06, 3200, 0.12, size_y=0.015)
    cyc.haze("haze", (0.7, 1.5, 0.36), (0, 0.3, 0.18), 0.0045, color="#A9C4E0", anisotropy=0.55)
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
        # the booth on the right third, the umbrella in the foreground on the left, the vending machine between
        "long": cyc.camera("cam_long", (-0.075, -0.23, 0.03), (-0.07, 0.20, HANDSET.z - 0.02), 35, 5.6),
        "handset": cyc.camera("cam_handset", tuple(HANDSET + Vector((-0.03, -0.19, 0.012))), tuple(HANDSET + Vector((0.0, 0, 0.004))), 100, 8.0),
        # the umbrella from the alley's mouth: its handle rising on the left, the booth lit behind it on the right
        "umbrella": cyc.camera("cam_umbrella", tuple(umb + Vector((0.02, -0.21, 0.05))), tuple(umb + Vector((-0.005, 0.0, 0.012))),
                               40, 8.0),
    }
    cams = {k: v for k, v in cams.items() if k in SHOTS}
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("rain", "booth_glass", "door_glass", "umbrella_canopy", "umbrella_water", "umbrella_drops")
    cyc.render_shots(cams, SHOTS, OUT, "s4", focus={"long": HANDSET, "handset": HANDSET, "umbrella": umb})


if __name__ == "__main__":
    main()
