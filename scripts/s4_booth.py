"""S4「雨夜的电话亭」: the one realistic passage. A 1:12 alley corner in heavy rain, a Japanese public phone
booth lit from inside, the handset hanging off the hook, a clear umbrella upside down on the wet asphalt
with rain pooled in it, posters peeling off the wooden wall, a vending machine far down the alley, and
infected heart bulbs glowing pink in the puddles. Cycles stills.

    blender -b -P scripts/s4_booth.py -- [renders/s4] [long handset]

Metres, Z up. The alley runs along +Y; the camera sits at its mouth (negative y) 3 cm above the ground.
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

OUT, SHOTS = cyc.args("s4", ["long", "handset"])
BOOTH = Vector((0.0, 0.18, 0.0))     # centre of the booth's footprint
BW, BH = 0.085, 0.19                   # booth width and height
HANDSET = BOOTH + Vector((-0.026, -0.012, 0.085))


# ---------------------------------------------------------------- materials

def wet_asphalt():
    mat, b = A._principled("wet_asphalt", **{"Base Color": m.srgb("#15161A"), "Roughness": 0.10, "Coat Weight": 0.6,
                                             "Coat Roughness": 0.05})
    nz = A._bump(mat, b, 70.0, 0.35, detail=7.0, distance=0.0015)
    nz.inputs["Roughness"].default_value = 0.8
    return mat


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
    """Pale green enamel gone chalky with age, rust creeping at the seams."""
    return P.enamel("#9DBAA6", chip="#6B4A32", chip_thr=0.80, rough=0.55, name="booth_paint")


def brick():
    mat, b = A._principled("brick", **{"Roughness": 0.9})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 0.018
    br.inputs["Row Height"].default_value = 0.008
    br.inputs["Mortar Size"].default_value = 0.0008
    br.inputs["Color1"].default_value = m.srgb("#8E4B3A")
    br.inputs["Color2"].default_value = m.srgb("#7A4032")
    br.inputs["Mortar"].default_value = m.srgb("#3A3836")
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.0008
    bp.invert = True
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    # wet: low roughness and a clear coat
    b.inputs["Roughness"].default_value = 0.25
    b.inputs["Coat Weight"].default_value = 0.5
    return mat


def rain_streak_mat():
    mat, b = A._principled("rain_streak", **{"Base Color": (1.0, 1.0, 1.0, 1.0), "Transmission Weight": 1.0,
                                             "Roughness": 0.15, "IOR": 1.33})
    return mat


# ---------------------------------------------------------------- the alley

def alley():
    ground = A.rounded_box("ground", (1.2, 1.4, 0.01), 0.0, [wet_asphalt()])
    ground.location = (0, 0.3, -0.005)
    pave = A.rounded_box("pavement", (0.13, 1.4, 0.004), 0.0005, [brick()])
    pave.location = (0.185, 0.3, 0.002)
    kerb = A.rounded_box("kerb", (0.006, 1.4, 0.006), 0.001, [P.paper("#B9B4AA", name="kerb")])
    kerb.location = (0.118, 0.3, 0.003)
    planks = A.stained_wood("#3A2A1E", (), (), light="#4C3828", rough=0.6)
    for sx, name in ((-1, "wall_left"), (1, "wall_right")):
        w = A.rounded_box(name, (0.02, 1.4, 0.32), 0.001, [planks])
        w.location = (sx * 0.26, 0.3, 0.16)
        # vertical plank seams
        y = -0.4
        while y < 1.0:
            seam = A.rounded_box("seam", (0.004, 0.0015, 0.32), 0.0, [A.plastic("#1A1410", 0.9, "seam")])
            seam.location = (sx * 0.249, y, 0.16)
            y += 0.035
    back = A.rounded_box("wall_back", (0.6, 0.02, 0.32), 0.001, [planks])
    back.location = (0, 1.0, 0.16)
    # corrugated iron awning on the left wall, with drops hanging off its edge
    def corr(i, j):
        u, v = i / 60, j / 6
        return (-0.25 + 0.075 * v, -0.05 + 0.45 * u, 0.175 - 0.012 * v + 0.0012 * math.sin(u * 0.45 * 2 * math.pi / 0.006))
    aw = P.grid_mesh("awning", 60, 6, corr, [A.metal("#6F7276", 0.55, "iron")])
    aw.modifiers.new("solid", "SOLIDIFY").thickness = 0.0006
    rnd = random.Random(2)
    drops = []
    for k in range(40):
        y = -0.05 + 0.45 * rnd.random()
        drops.append((-0.25 + 0.075, y, 0.175 - 0.012 - 0.0012 - rnd.uniform(0.0002, 0.0012)))
    bm_drops = P.dust(((-0.176, -0.174), (-0.05, 0.4), (0.160, 0.162)), 0, name="drops_unused")
    bpy.data.objects.remove(bm_drops)
    for k, (x, y, z) in enumerate(drops):
        d = P.sphere("drop", rnd.uniform(0.0006, 0.0011), [water()], segments=12)
        d.location = (x, y, z)
        d.scale = (1, 1, 1.5)
    # posters on the left wall, rain-soaked, corners lifting
    for k, (y, z, img, tilt) in enumerate([(0.02, 0.10, "frame_A.png", 2), (0.09, 0.095, "frame_B.png", -3),
                                           (0.30, 0.11, "frame_A.png", 4)]):
        po = A.rounded_box("poster", (0.0006, 0.055, 0.034), 0.0, [A.printed(os.path.join(cyc.ROOT, "renders", img), rough=0.35)])
        P.map_uv(po, ("y", "z"), (0.055, 0.034))
        po.location = (-0.2495, y, z)
        po.rotation_euler = (math.radians(tilt), 0, 0)
    # the vending machine far down the alley: a cold white panel and a row of coloured cans
    vm = A.rounded_box("vending", (0.075, 0.06, 0.15), 0.003, [A.plastic("#C8CBD0", 0.4, "vm_body")])
    vm.location = (0.205, 0.72, 0.075)
    panel = A.rounded_box("vm_panel", (0.06, 0.0008, 0.09), 0.0, [A.emissive("#EAF2FF", 2.5)])
    panel.location = (0.205, 0.689, 0.085)
    for k, col in enumerate(("#E0301E", "#34E3E8", "#F2C23E", "#F2468A", "#3C6FD8")):
        can = A.lathe("can", [(0.0001, 0), (0.0045, 0), (0.0045, 0.012), (0.0001, 0.012)], 16, [A.plastic(col, 0.3, "can" + col)])
        can.location = (0.183 + 0.011 * k, 0.69, 0.105)
    slot = A.rounded_box("vm_slot", (0.05, 0.0008, 0.018), 0.0, [A.plastic("#101114", 0.6, "vm_dark")])
    slot.location = (0.205, 0.689, 0.03)


# ---------------------------------------------------------------- the booth

def booth():
    paint = booth_paint()
    glass = rain_glass()
    root = bpy.data.objects.new("booth", None)
    m._link(root)
    root.location = BOOTH
    h, w, t = BH, BW, 0.006
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
    # lower panels are painted steel, upper ones glass; the front has a folding door with a centre stile
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
    # the light box over the door: 公衆電話 on a warm white panel
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
    # the fluorescent tube under the roof
    tube = A.lathe("booth_tube", [(0.0001, -0.03), (0.0025, -0.03), (0.0025, 0.03), (0.0001, 0.03)], 16,
                   [A.emissive("#DCEAF0", 1.4)], root)
    tube.rotation_euler = (0, math.radians(90), 0)
    tube.location = (0, 0.01, h - 0.012)
    # the payphone on the back wall, its handset off the hook and hanging by the cord
    green = A.plastic("#2E6F4F", 0.35, "phone_green")
    body = A.rounded_box("payphone", (0.03, 0.016, 0.036), 0.002, [green], root)
    body.location = (0.006, w / 2 - t - 0.012, 0.108)
    for r in range(3):
        for c in range(3):
            key = A.rounded_box("key", (0.0035, 0.0012, 0.0035), 0.0004, [A.plastic("#E8E6DE", 0.5, "key")], root)
            key.location = (0.006 + (c - 1) * 0.0045, w / 2 - t - 0.012 - 0.0085, 0.112 - (r - 1) * 0.0045)
    hook = A.rounded_box("hook", (0.004, 0.006, 0.012), 0.0005, [A.chrome()], root)
    hook.location = (-0.011, w / 2 - t - 0.012 - 0.006, 0.118)
    shelf = A.rounded_box("shelf", (0.034, 0.02, 0.0025), 0.0005, [green], root)
    shelf.location = (0.006, w / 2 - t - 0.014, 0.088)
    coin = A.lathe("coin", [(0.0001, 0), (0.0022, 0), (0.0022, 0.0004), (0.0001, 0.0004)], 24, [A.brass()], root)
    coin.location = (0.014, w / 2 - t - 0.012, 0.0893)
    note = A.rounded_box("note", (0.012, 0.009, 0.0008), 0.0002, [A.printed(os.path.join(cyc.ROOT, "renders", "frame_A.png"))], root)
    P.map_uv(note, ("x", "y"), (0.012, 0.009))
    note.location = (-0.002, w / 2 - t - 0.012, 0.0895)
    note.rotation_euler.z = math.radians(18)
    # handset: two earpieces on a bar, a heart sticker, hanging from a coiled cord that has gone slack
    hs = HANDSET - BOOTH
    bar = A.tube_along("handset_bar", [(hs.x, hs.y, hs.z + 0.012), (hs.x + 0.002, hs.y - 0.001, hs.z), (hs.x, hs.y, hs.z - 0.012)],
                       0.0025, [green], root)
    for dz in (0.014, -0.014):
        cup = P.sphere("handset_cup", 0.0045, [green], root)
        cup.location = (hs.x, hs.y, hs.z + dz)
        cup.scale = (1, 1, 0.6)
    sticker = P.flat_shape("sticker", [(x * 0.0019, y * 0.0019) for x, y in m.heart_outline(40)],
                           [P.paper("#FF3D8B", name="sticker")], root)
    sticker.rotation_euler = (math.radians(90), 0, math.radians(-10))
    sticker.location = (hs.x - 0.0027, hs.y, hs.z + 0.004)
    cord = []
    top = Vector((-0.011, w / 2 - t - 0.012 - 0.004, 0.102))
    bottom = Vector((hs.x, hs.y + 0.002, hs.z + 0.013))
    for k in range(120):
        u = k / 119
        c = top.lerp(bottom, u) + Vector((0, 0, -0.012 * math.sin(math.pi * u)))
        a = u * 2 * math.pi * 14
        cord.append((c.x + 0.0022 * math.cos(a), c.y + 0.0022 * math.sin(a), c.z))
    A.tube_along("cord", cord, 0.0005, [A.plastic("#1E2D2A", 0.5, "cord")], root, resolution=3)
    return root


def umbrella(loc, yaw_deg=25):
    root = bpy.data.objects.new("umbrella", None)
    m._link(root)
    root.location = loc
    root.rotation_euler.z = math.radians(yaw_deg)
    film = A.clear_glass(0.03)
    R, depth = 0.046, 0.013
    prof = [(R * math.sin(a), depth * (1 - math.cos(a))) for a in [math.pi / 2 * (1 - k / 14) for k in range(15)]]
    canopy = A.lathe("umbrella_canopy", [(max(r, 0.0001), z) for r, z in prof], 64, [film], root)
    canopy.modifiers.new("solid", "SOLIDIFY").thickness = 0.0003
    canopy.location = (0, 0, 0.003)
    for k in range(8):
        a = 2 * math.pi * k / 8
        pts = [(R * math.sin(b) * math.cos(a), R * math.sin(b) * math.sin(a), 0.003 + depth * (1 - math.cos(b)))
               for b in [math.pi / 2 * (1 - j / 6) for j in range(7)]]
        A.tube_along("rib", pts, 0.0004, [A.metal("#8A8C90", 0.4, "rib")], root)
    pool = A.lathe("umbrella_water", [(0.0001, 0.0105), (0.030, 0.0105), (0.0001, 0.0106)], 48, [water()], root)
    _ = pool
    shaft = A.tube_along("shaft", [(0, 0, 0.0), (0, 0, 0.058)], 0.0012, [A.metal("#8A8C90", 0.4, "rib")], root)
    shaft.rotation_euler = (math.radians(-80), 0, 0)
    handle = A.tube_along("handle", [(0, 0.058 * math.sin(math.radians(80)) * 0 + 0.057, 0.010), (0, 0.068, 0.012),
                                     (0, 0.076, 0.009), (0, 0.078, 0.003)], 0.0022, [A.plastic("#E0301E", 0.3, "handle")], root)
    _ = handle
    for k in range(3):
        d = P.sphere("rim_drop", 0.0008, [water()], root, segments=10)
        a = math.radians(40 + 50 * k)
        d.location = (R * 0.98 * math.cos(a), R * 0.98 * math.sin(a), 0.016)
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
    alley()
    booth()
    umbrella((-0.105, -0.06, 0.0))
    puddles_and_bulbs()
    rain()
    # light: the booth's tube and its light box, the vending machine down the alley, the bulbs' pink;
    # a thin blue haze so the rain and the beams read
    cyc.area_light("booth_light", tuple(BOOTH + Vector((0, 0.01, BH - 0.02))), tuple(BOOTH + Vector((0, 0, 0.02))), 0.05,
                   5000, 2.2, size_y=0.03, color="#D9EBF2")
    cyc.area_light("lightbox_glow", tuple(BOOTH + Vector((0, -BW / 2 - 0.02, BH - 0.01))), tuple(BOOTH + Vector((0, -0.2, 0.0))),
                   0.06, 3200, 0.12, size_y=0.015)
    cyc.area_light("vending_glow", (0.205, 0.68, 0.085), (0.0, 0.1, 0.02), 0.07, 6500, 1.6, size_y=0.09)
    cyc.haze("haze", (0.7, 1.4, 0.36), (0, 0.3, 0.18), 0.006, color="#A9C4E0", anisotropy=0.55)
    cyc.glass_lets_light_through(("clear_glass", "rain_glass", "water"))


def main():
    build()
    cams = {
        "long": cyc.camera("cam_long", (-0.075, -0.23, 0.03), tuple(HANDSET + Vector((0, 0, -0.02))), 35, 5.6),
        "handset": cyc.camera("cam_handset", tuple(HANDSET + Vector((0.006, -0.175, 0.04))), tuple(HANDSET), 100, 8.0),
    }
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("rain", "booth_glass", "door_glass", "umbrella_canopy", "umbrella_water")
    cyc.render_shots(cams, SHOTS, OUT, "s4", focus={"long": HANDSET, "handset": HANDSET})


if __name__ == "__main__":
    main()
