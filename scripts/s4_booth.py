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
PHONE = BOOTH + Vector((0.009, BW / 2 - BT - 0.0125, 0.075))   # the payphone's base centre, back to the rear panel
HOOK = PHONE + Vector((-0.0205, -0.0025, 0.041))             # where the model's cradle hook is after the cut
HANDSET = HOOK + Vector((-0.004, -0.008, -0.034))             # the hanging handset's centre
UMBRELLA = Vector((-0.105, -0.06, 0.0))


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
        asphalt=T.pbr("asphalt_02", rough=0.10, coat=0.9, scale=1 / 12, name="wet_asphalt"),
        brick=T.pbr("brick_wall_001", rough=0.22, coat=0.6, scale=1 / 12, rotation_deg=90, name="wet_brick"),
        kerb=T.pbr("brushed_concrete", tint="#8E8B84", rough=0.3, coat=0.5, scale=1 / 12),
        planks=T.pbr("dark_wooden_planks", rough=0.45, coat=0.3, scale=1 / 10, rotation_deg=90, name="wet_planks"),
        backwall=T.pbr("peeling_painted_wall", tint="#B9B2A4", rough=0.6, scale=1 / 10),
        awning=T.pbr("corrugated_iron_02", scale=1 / 10, rough=0.35, coat=0.4, name="awning_iron"),
        vm=T.pbr("rusty_painted_metal", flat=("#C8CBD0", 0.75), rough=0.4, scale=1 / 8, name="vm_body"),
    )


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
    # the vending machine far down the alley: a cold white panel and a row of coloured cans
    vm = A.rounded_box("vending", (0.075, 0.06, 0.15), 0.003, [M["vm"]])
    vm.location = (0.205, 0.78, 0.075)
    panel = A.rounded_box("vm_panel", (0.06, 0.0008, 0.09), 0.0, [A.emissive("#EAF2FF", 2.5)])
    panel.location = (0.205, 0.749, 0.085)
    for k, col in enumerate(("#E0301E", "#34E3E8", "#F2C23E", "#F2468A", "#3C6FD8")):
        can = A.lathe("can", [(0.0001, 0), (0.0045, 0), (0.0045, 0.012), (0.0001, 0.012)], 16, [A.plastic(col, 0.3, "can" + col)])
        can.location = (0.183 + 0.011 * k, 0.75, 0.105)
    slot = A.rounded_box("vm_slot", (0.05, 0.0008, 0.018), 0.0, [A.plastic("#101114", 0.6, "vm_dark")])
    slot.location = (0.205, 0.749, 0.03)


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
    # the payphone on the back wall, handset and cord cut off the model; a shelf with a coin and a folded note
    phone = T.model("korean_public_payphone_01", name="payphone")
    T.place(phone, tuple(PHONE))
    # the model's own handset and cord come off the side hook and hang lower, swinging a little
    handset = None
    plo, phi = T.model_bounds(phone)
    # the handset and its cord are the pieces that reach the leftmost 5 mm (the body starts ~7 mm in)
    for ob in phone.children_recursive:
        if ob.type == "MESH":
            handset = T.split_islands(ob, lambda lo, hi: lo.x < plo.x + 0.005 and hi.y < phi.y - 0.0075, "handset")
    if handset is not None:
        bpy.context.view_layer.update()
        hlo, hhi = T.model_bounds(phone)   # body only now
        pivot = Vector((hlo.x - 0.002, (hlo.y + hhi.y) / 2 - 0.004, hlo.z + 0.045))
        mw = handset.matrix_world.copy()
        drop = Matrix.Translation(pivot + Vector((-0.002, -0.004, -0.022))) @ Matrix.Rotation(math.radians(14), 4, "Y")             @ Matrix.Rotation(math.radians(-10), 4, "X") @ Matrix.Translation(-pivot)
        handset.parent = None
        handset.matrix_world = drop @ mw
    green = A.plastic("#2E6F4F", 0.35, "phone_green")
    shelf = A.rounded_box("shelf", (0.040, 0.022, 0.0025), 0.0005, [booth_paint()], root)
    shelf.location = (PHONE.x - BOOTH.x, w / 2 - t - 0.016, 0.072)
    coin = A.lathe("coin", [(0.0001, 0), (0.0022, 0), (0.0022, 0.0004), (0.0001, 0.0004)], 24, [A.brass()], root)
    coin.location = (PHONE.x - BOOTH.x + 0.012, w / 2 - t - 0.014, 0.0733)
    note = A.rounded_box("note", (0.012, 0.009, 0.0008), 0.0002, [A.printed(os.path.join(cyc.ROOT, "renders", "frame_A.png"))], root)
    P.map_uv(note, ("x", "y"), (0.012, 0.009))
    note.location = (PHONE.x - BOOTH.x - 0.006, w / 2 - t - 0.013, 0.0735)
    note.rotation_euler.z = math.radians(18)
    return root


def umbrella(loc, yaw_deg=25, R=0.046, depth=0.014):
    """A clear vinyl umbrella upside down on the ground, rain pooled in it, the red handle in the air."""
    root = bpy.data.objects.new("umbrella", None)
    m._link(root)
    root.location = loc
    root.rotation_euler = (math.radians(6), 0, math.radians(yaw_deg))
    film, rib_mat, white = vinyl(), A.metal("#8A8C90", 0.35, "rib"), A.plastic("#F2F0EA", 0.5, "tip")

    def pt(i, j):
        a = 2 * math.pi * i / 64
        r = R * (j / 10) ** 0.85
        gore = abs(((i % 8) / 8) - 0.5) * 2
        return (r * math.cos(a), r * math.sin(a), 0.004 + depth * (r / R) ** 2 - 0.0025 * (1 - gore) * (j / 10) ** 2)

    can = P.grid_mesh("umbrella_canopy", 64, 10, pt, [film], root)
    bm = bmesh.new()
    bm.from_mesh(can.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(can.data)
    bm.free()
    can.modifiers.new("solid", "SOLIDIFY").thickness = 0.00025
    can.modifiers.new("sub", "SUBSURF").render_levels = 2
    for k in range(8):
        a = 2 * math.pi * k / 8
        pts = [((R * t) * math.cos(a), (R * t) * math.sin(a), 0.004 + depth * t * t + 0.0004) for t in (0.05, 0.3, 0.55, 0.8, 1.0)]
        A.tube_along("rib", pts, 0.00035, [rib_mat], root)
        tip = P.sphere("tip", 0.0009, [white], root)
        tip.location = (R * 1.01 * math.cos(a), R * 1.01 * math.sin(a), 0.004 + depth + 0.0004)
        A.tube_along("stretcher", [(0, 0, 0.024), (R * 0.5 * math.cos(a), R * 0.5 * math.sin(a), 0.004 + depth * 0.25 + 0.0006)],
                     0.0003, [rib_mat], root)
    pool = A.lathe("umbrella_water", [(0.0001, 0.004 + depth * 0.18), (R * 0.42, 0.004 + depth * 0.18),
                                      (0.0001, 0.004 + depth * 0.18 + 0.00005)], 64, [water()], root)
    _ = pool
    A.tube_along("shaft", [(0, 0, 0.004), (0, 0, 0.054)], 0.0012, [rib_mat], root)
    A.tube_along("handle", [(0, 0, 0.054), (0, 0.004, 0.066), (0, 0.012, 0.072), (0, 0.020, 0.068), (0, 0.022, 0.060)],
                 0.0022, [A.plastic("#E0301E", 0.3, "handle")], root)
    return root


def puddles_and_bulbs(seed=5):
    rnd = random.Random(seed)
    for k, (x, y, rx, ry) in enumerate([(-0.12, 0.12, 0.05, 0.03), (0.06, -0.04, 0.035, 0.025), (0.0, 0.42, 0.06, 0.04),
                                        (-0.18, 0.38, 0.04, 0.03)]):
        pd = A.lathe(f"puddle{k}", [(0.0001, 0.0002), (1.0, 0.0002), (1.0, 0.0004), (0.0001, 0.0004)], 48, [water()])
        pd.scale = (rx, ry, 1)
        pd.location = (x, y, 0.0)
        pd.rotation_euler.z = math.radians(rnd.uniform(0, 180))
        for _ in range(2):
            b = A.heart_bulb("infected", 0.0045, seed=k * 3)
            b.location = (x + rnd.uniform(-rx * 0.6, rx * 0.6), y + rnd.uniform(-ry * 0.6, ry * 0.6), 0.0018)
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
    alley(M)
    booth()
    umbrella(tuple(UMBRELLA))
    puddles_and_bulbs()
    rain()
    cyc.area_light("booth_light", tuple(BOOTH + Vector((0, 0.01, BH - 0.02))), tuple(BOOTH + Vector((0, 0, 0.02))), 0.05,
                   5000, 2.2, size_y=0.03, color="#D9EBF2")
    cyc.area_light("lightbox_glow", tuple(BOOTH + Vector((0, -BW / 2 - 0.02, BH - 0.01))), tuple(BOOTH + Vector((0, -0.2, 0.0))),
                   0.06, 3200, 0.12, size_y=0.015)
    cyc.area_light("vending_glow", (0.205, 0.74, 0.085), (0.0, 0.1, 0.02), 0.07, 6500, 1.6, size_y=0.09)
    cyc.haze("haze", (0.7, 1.5, 0.36), (0, 0.3, 0.18), 0.006, color="#A9C4E0", anisotropy=0.55)
    cyc.glass_lets_light_through(("clear_glass", "rain_glass", "water", "vinyl"))


def main():
    build()
    global HANDSET
    hs = bpy.data.objects.get("handset")
    if hs is not None:
        bpy.context.view_layer.update()
        pts = [hs.matrix_world @ Vector(c) for c in hs.bound_box]
        HANDSET = sum(pts, Vector()) / 8
        print("handset at mm", tuple(round(v * 1000, 1) for v in HANDSET))
    cams = {
        "long": cyc.camera("cam_long", (-0.075, -0.23, 0.03), tuple(HANDSET + Vector((0, 0, -0.02))), 35, 5.6),
        "handset": cyc.camera("cam_handset", tuple(HANDSET + Vector((-0.006, -0.20, 0.022))), tuple(HANDSET + Vector((0.002, 0, 0.008))), 100, 8.0),
        "umbrella": cyc.camera("cam_umbrella", tuple(UMBRELLA + Vector((0.05, -0.19, 0.035))), tuple(UMBRELLA + Vector((0, 0, 0.012))), 50, 8.0),
    }
    cams = {k: v for k, v in cams.items() if k in SHOTS}
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("rain", "booth_glass", "door_glass", "umbrella_canopy", "umbrella_water")
    cyc.render_shots(cams, SHOTS, OUT, "s4", focus={"long": HANDSET, "handset": HANDSET, "umbrella": UMBRELLA + Vector((0, 0, 0.012))})


if __name__ == "__main__":
    main()
