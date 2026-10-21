"""Props for the bedroom (S1, and its inverted twin S6): the set box, the iron bed and its bedding, the
twin-bell alarm clock, the window with a printed sky card and a sheer curtain, the desk, the phone, the milk
glass, prints, polaroids and masking tape.

Everything is modeled procedurally at 1:12 in metres, Z up. The open side of the set faces -Y (the camera).
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import assets as A
import mvlib as m


# ---------------------------------------------------------------- materials

def paper(hexstr="#EEE8DA", rough=0.9, name="paper", alpha=1.0, emit=0.0):
    mat, b = A._principled(name, **{"Base Color": m.srgb(hexstr), "Roughness": rough})
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
    if emit:
        b.inputs["Emission Color"].default_value = m.srgb(hexstr)
        b.inputs["Emission Strength"].default_value = emit
    A._bump(mat, b, 900.0, 0.25, detail=5.0, distance=0.0001)   # paper fibre
    return mat


def fabric(hexstr, rough=0.85, sheen=0.5, name="fabric", sheen_tint=None):
    """Cotton or silk: sheen for the fibre glow at grazing angles, fine bump for the weave."""
    mat, b = A._principled(name, **{"Base Color": m.srgb(hexstr), "Roughness": rough})
    b.inputs["Sheen Weight"].default_value = sheen
    if sheen_tint:
        b.inputs["Sheen Tint"].default_value = m.srgb(sheen_tint)
    A._bump(mat, b, 2500.0, 0.35, detail=6.0, distance=0.00005)
    return mat


def painted(hexstr="#F1EEE6", rough=0.35, name="paint"):
    """Brush-painted wood: thick paint edges and crazing as a coarse bump."""
    mat, b = A._principled(name, **{"Base Color": m.srgb(hexstr), "Roughness": rough})
    A._bump(mat, b, 300.0, 0.5, detail=7.0, distance=0.0003)
    return mat


def enamel(hexstr, chip="#B08D57", chip_thr=0.74, rough=0.22, name="enamel"):
    """Baked enamel with chips down to the brass: noise above chip_thr shows bare metal."""
    mat, b = A._principled(name, **{"Roughness": rough})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.75
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    cut = nt.nodes.new("ShaderNodeMath")
    cut.operation = "GREATER_THAN"
    cut.inputs[1].default_value = chip_thr
    nt.links.new(nz.outputs["Fac"], cut.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = m.srgb(hexstr)
    mix.inputs["B"].default_value = m.srgb(chip)
    nt.links.new(cut.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(cut.outputs[0], b.inputs["Metallic"])
    return mat


def halftone_card(ink="#6F86B8", paper_hex="#EEE8DA", cell=0.0012, angle_deg=15.0, normal="X",
                  grad=(-0.08, 0.08, 0.04, 0.52), strength=0.7, emit=0.0, name="halftone_card"):
    """A printed gradient of dots. cell = screen pitch in metres; the dot radius (in cells) ramps from
    grad[2] to grad[3] along the card's up axis between grad[0] and grad[1] (object space).
    normal = the card's facing axis: 'X' for a card in the YZ plane, 'Y' for one in the XZ plane."""
    mat, b = A._principled(name, **{"Roughness": 0.9})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    rot = nt.nodes.new("ShaderNodeVectorRotate")
    rot.rotation_type = "AXIS_ANGLE"
    rot.inputs["Axis"].default_value = (1, 0, 0) if normal == "X" else (0, 1, 0)
    rot.inputs["Angle"].default_value = math.radians(angle_deg)
    nt.links.new(tc.outputs["Object"], rot.inputs["Vector"])
    scale = nt.nodes.new("ShaderNodeVectorMath")
    scale.operation = "SCALE"
    scale.inputs["Scale"].default_value = 1.0 / cell
    nt.links.new(rot.outputs[0], scale.inputs[0])
    frac = nt.nodes.new("ShaderNodeVectorMath")
    frac.operation = "FRACTION"
    nt.links.new(scale.outputs[0], frac.inputs[0])
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(frac.outputs[0], sub.inputs[0])
    flat = nt.nodes.new("ShaderNodeVectorMath")
    flat.operation = "MULTIPLY"
    flat.inputs[1].default_value = (0, 1, 1) if normal == "X" else (1, 0, 1)
    nt.links.new(sub.outputs[0], flat.inputs[0])
    length = nt.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    nt.links.new(flat.outputs[0], length.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = grad[0], grad[1]
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = grad[2], grad[3]
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    less = nt.nodes.new("ShaderNodeMath")
    less.operation = "LESS_THAN"
    nt.links.new(length.outputs["Value"], less.inputs[0])
    nt.links.new(mr.outputs["Result"], less.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    pc, ic = m.srgb(paper_hex), m.srgb(ink)
    mix.inputs["A"].default_value = pc
    mix.inputs["B"].default_value = tuple(pc[i] * (1 - strength) + ic[i] * strength for i in range(3)) + (1.0,)
    nt.links.new(less.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    if emit:
        nt.links.new(mix.outputs["Result"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    A._bump(mat, b, 900.0, 0.2, detail=5.0, distance=0.0001)
    return mat


def milk():
    mat, b = A._principled("milk", **{"Base Color": m.srgb("#F6F3EA"), "Roughness": 0.25})
    b.inputs["Subsurface Weight"].default_value = 0.8
    b.inputs["Subsurface Radius"].default_value = (0.004, 0.0025, 0.0015)
    b.inputs["Subsurface Scale"].default_value = 1.0
    return mat


# ---------------------------------------------------------------- mesh helpers

def grid_mesh(name, nx, ny, fn, mats=(), parent=None, smooth=True):
    """(nx+1) x (ny+1) vertices placed by fn(i, j) -> (x, y, z), quads between them."""
    verts = [fn(i, j) for j in range(ny + 1) for i in range(nx + 1)]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    for p in mesh.polygons:
        p.use_smooth = smooth
    return A._obj(name, mesh, mats, parent)


def superellipse(a, b, n=4.0, count=96):
    pts = []
    for i in range(count):
        t = 2 * math.pi * i / count
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def sphere(name, radius, mats=(), parent=None, segments=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=radius)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    return A._obj(name, mesh, mats, parent)


def flat_shape(name, outline, mats=(), parent=None):
    """A flat n-gon from a 2D outline in the XY plane (hearts on screens and shoes)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return A._obj(name, mesh, mats, parent)


def map_uv(obj, axes=("x", "z"), size=(1.0, 1.0)):
    """Planar UVs so a printed() image spans the object's extent along two axes."""
    uv = obj.data.uv_layers.new()
    for loop in obj.data.loops:
        co = obj.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (getattr(co, axes[0]) / size[0] + 0.5, getattr(co, axes[1]) / size[1] + 0.5)


# ---------------------------------------------------------------- the set

def set_box(w=0.30, d=0.25, h=0.22, t=0.01, wall=None, floor=None, window=None, batten=None, tape=None, lid=True,
            ceiling=False):
    """Floor and three walls, interior x in [-w/2, w/2], y in [-d/2, d/2], z in [0, h], open towards -Y.
    window = (y0, z0, wy, wz) cuts an opening in the left wall. Battens and masking tape on the outside
    show that this is a model. Returns the parts by name."""
    wall = wall or paper("#EEE8DA", name="wallpaper")
    floor = floor or A.stained_wood("#B48A5C", (), ())
    batten = batten or A.stained_wood("#4A2E1B", (), ())
    tape = tape or paper("#D9C9A3", name="masking_tape", alpha=0.85)
    parts = {}
    fl = A.rounded_box("floor", (w + 2 * t, d + t, t), 0.0005, [floor])
    fl.location = (0, t / 2, -t / 2)
    parts["floor"] = fl
    back = A.rounded_box("wall_back", (w + 2 * t, t, h), 0.0005, [wall])
    back.location = (0, d / 2 + t / 2, h / 2)
    parts["back"] = back
    right = A.rounded_box("wall_right", (t, d, h), 0.0005, [wall])
    right.location = (w / 2 + t / 2, 0, h / 2)
    parts["right"] = right
    xl = -w / 2 - t / 2
    if window:
        y0, z0, wy, wz = window
        y1, z1 = y0 + wy, z0 + wz
        pieces = [("wall_left_low", (-d / 2, d / 2, 0, z0)), ("wall_left_high", (-d / 2, d / 2, z1, h)),
                  ("wall_left_front", (-d / 2, y0, z0, z1)), ("wall_left_back", (y1, d / 2, z0, z1))]
        for name, (ya, yb, za, zb) in pieces:
            ob = A.rounded_box(name, (t, yb - ya, zb - za), 0.0003, [wall])
            ob.location = (xl, (ya + yb) / 2, (za + zb) / 2)
            parts[name] = ob
    else:
        left = A.rounded_box("wall_left", (t, d, h), 0.0005, [wall])
        left.location = (xl, 0, h / 2)
        parts["left"] = left
    # the model's skeleton: battens on the outer vertical edges and along the top, tape over the joints
    bt = 0.011
    for i, (x, y) in enumerate([(-w / 2 - t - bt / 2, -d / 2 + bt / 2), (w / 2 + t + bt / 2, -d / 2 + bt / 2),
                                (-w / 2 - t - bt / 2, d / 2 + t + bt / 2), (w / 2 + t + bt / 2, d / 2 + t + bt / 2)]):
        b = A.rounded_box(f"batten{i}", (bt, bt, h + 0.02), 0.0008, [batten])
        b.location = (x, y, (h + 0.02) / 2 - 0.01)
    for i, (size, loc) in enumerate([((bt, d + t + bt, bt), (-w / 2 - t - bt / 2, t / 2, h + 0.005)),
                                     ((bt, d + t + bt, bt), (w / 2 + t + bt / 2, t / 2, h + 0.005)),
                                     ((w + 2 * t + 2 * bt, bt, bt), (0, d / 2 + t + bt / 2, h + 0.005))]):
        b = A.rounded_box(f"batten_top{i}", size, 0.0008, [batten])
        b.location = loc
    if ceiling:
        # a real ceiling (the inverted room of S6 needs a floor to fall onto)
        ce = A.rounded_box("ceiling", (w + 2 * t, d + t, t), 0.0005, [wall])
        ce.location = (0, t / 2, h + t / 2)
        parts["ceiling"] = ce
    if lid and not ceiling:
        # a black flag over the open top: the camera does not see it, but it stops the window light
        # from pouring in over the walls (the set has no ceiling, the lamp sits above the wall tops)
        flag = A.rounded_box("lid_flag", (w + 2 * t + 0.03, d + t + 0.05, 0.004), 0.0, [A.plaster("#000000")])
        flag.location = (0, t / 2 - 0.01, h + 0.012)
        flag.visible_camera = False
        flag.visible_glossy = False
        flag.visible_transmission = False
        parts["lid"] = flag
    rnd = random.Random(11)
    for i, (x, y, z, rz) in enumerate([(-w / 2 - t - bt, -d / 2 + 0.004, 0.06, 0), (w / 2 + t + bt, -d / 2 + 0.004, 0.15, 0),
                                       (-w / 2 - t - bt / 2, -d / 2 - 0.0005, h + 0.004, 90)]):
        s = A.rounded_box(f"tape{i}", (0.0003, 0.012, 0.03), 0.0, [tape])
        s.location = (x, y, z)
        s.rotation_euler = (math.radians(rnd.uniform(-4, 4)), math.radians(rnd.uniform(-6, 6)), math.radians(rz))
    return parts


# ---------------------------------------------------------------- bed

def iron_bed(loc, length=0.167, width=0.083, head=+1, pipe=None, sheet=None, duvet=None, pillow_mat=None,
             mattress_z=0.030, seed=5):
    """Single iron bed along X at loc (its centre on the floor); head is the +X end when head = +1.
    Returns dict(root, pillow_top (world point), front_y)."""
    pipe = pipe or painted("#F1EEE6", rough=0.3, name="bed_paint")
    sheet = sheet or fabric("#E6E2D8", name="sheet")
    duvet = duvet or fabric("#DED6C6", rough=0.9, name="duvet")
    pillow_mat = pillow_mat or fabric("#EFEBE2", name="pillow")
    rnd = random.Random(seed)
    root = bpy.data.objects.new("bed", None)
    m._link(root)
    root.location = loc
    L, W, r = length / 2, width / 2, 0.0015
    heights = {+1: 0.085, -1: 0.060}
    for sx in (+1, -1):
        hh = heights[sx * head]
        for sy in (+1, -1):
            A.tube_along("bed_post", [(sx * L, sy * W, 0), (sx * L, sy * W, hh)], r, [pipe], root, resolution=4)
            A.tube_along("bed_rail", [(sx * L, sy * W, mattress_z - 0.004), (-sx * L, sy * W, mattress_z - 0.004)],
                         r * 0.8, [pipe], root, resolution=4)
        A.tube_along("bed_top", [(sx * L, -W, hh), (sx * L, W, hh)], r, [pipe], root, resolution=4)
        A.tube_along("bed_low", [(sx * L, -W, mattress_z + 0.008), (sx * L, W, mattress_z + 0.008)], r * 0.8,
                     [pipe], root, resolution=4)
        for k in range(1, 6):
            y = -W + k * (2 * W / 6)
            A.tube_along("bed_bar", [(sx * L, y, mattress_z + 0.008), (sx * L, y, hh)], r * 0.55, [pipe], root,
                         resolution=3)
        sphere("bed_knob", 0.0032, [pipe], root).location = (sx * L, -W, hh)
        sphere("bed_knob", 0.0032, [pipe], root).location = (sx * L, W, hh)
    # mattress and the slept-in sheet: a grid with noise wrinkles, deeper where the body lay
    mat_h = 0.014
    mattress = A.rounded_box("mattress", (length - 0.004, width - 0.004, mat_h), 0.004, [sheet], root)
    mattress.location = (0, 0, mattress_z + mat_h / 2)
    top = mattress_z + mat_h
    nx, ny = 70, 36
    body_x = -head * 0.02

    def sheet_pt(i, j):
        x = -L + 0.002 + (length - 0.004) * i / nx
        y = -W + 0.002 + (width - 0.004) * j / ny
        n = noise.noise(Vector((x * 140 + 3.1, y * 140, 0.0)))
        n2 = noise.noise(Vector((x * 520, y * 520, 1.7)))
        dent = 0.0025 * math.exp(-((x - body_x) ** 2 / 0.0030 + (y + 0.008) ** 2 / 0.0006))
        return (x, y, top + 0.0007 + 0.0011 * n + 0.0003 * n2 - dent)

    grid_mesh("sheet", nx, ny, sheet_pt, [sheet], root)
    # pillow: puffy superellipse with a head-shaped dent
    pm = m.pillow_mesh("pillow", superellipse(0.021, 0.015, 3.2, 120), centre=(0.0, 0.0), depth=0.0045, rings=18)
    px, py = head * (L - 0.028), 0.0
    for v in pm.vertices:
        if v.co.z > 0:
            v.co.z -= 0.0028 * math.exp(-((v.co.x - 0.004) ** 2 + (v.co.y + 0.002) ** 2) / 0.00009)
    pillow = A._obj("pillow", pm, [pillow_mat], root)
    pillow.location = (px, py, top + 0.0045)
    pillow.rotation_euler.z = math.radians(rnd.uniform(-6, 6))
    pillow.modifiers.new("sub", "SUBSURF").render_levels = 2
    # duvet: a strip that lies on the far half of the bed, folds over the front edge and hangs to the floor
    R, thick = 0.007, 0.0055
    y_edge = -W + 0.001
    flat_len = 0.055
    ymax = y_edge + flat_len
    drop = top - thick - 0.002
    total = flat_len + R * math.pi / 2 + drop + 0.03

    def duvet_pt(i, j):
        x = head * (-L + 0.06) + (0.095) * (i / 36 - 0.5)
        s = total * j / 60
        wob = 0.0012 * noise.noise(Vector((x * 90, s * 90, 2.2)))
        if s < flat_len:
            return (x, ymax - s, top + thick / 2 + wob + 0.001 * math.sin(x * 400))
        s -= flat_len
        if s < R * math.pi / 2:
            a = s / R
            return (x, y_edge - R * math.sin(a), top + thick / 2 - R * (1 - math.cos(a)) + wob)
        s -= R * math.pi / 2
        if s < drop:
            return (x, y_edge - R + wob, top + thick / 2 - R - s)
        s -= drop
        return (x, y_edge - R - s, thick / 2 + 0.0008 + wob)

    dv = grid_mesh("duvet", 36, 60, duvet_pt, [duvet], root)
    so = dv.modifiers.new("solid", "SOLIDIFY")
    so.thickness = thick
    so.offset = 0.0
    dv.modifiers.new("sub", "SUBSURF").render_levels = 1
    pillow_top = Vector(loc) + Vector((px, py, top + 0.0045 + 0.003))
    return {"root": root, "pillow_top": pillow_top, "front_y": loc[1] - W, "top": loc[2] + top}


# ---------------------------------------------------------------- alarm clock

def alarm_clock(loc, size=0.016, time=(6, 59, 20), red="#E0301E", yaw_deg=0.0, parent=None):
    """Twin-bell tin clock, dial facing -Y (then yawed). size = body diameter. Returns (root, dial point)."""
    s = size / 2
    root = bpy.data.objects.new("clock", None)
    m._link(root)
    if parent is not None:
        root.parent = parent
    shell = enamel(red, name="clock_enamel")
    brass = A.brass()
    steel = A.metal("#5E6B7A", 0.3, "blued_steel")
    ink = A.plastic("#1B1A19", 0.8, "dial_ink")
    body = A.lathe("clock_body", [(0, -0.30 * s), (0.92 * s, -0.30 * s), (1.0 * s, -0.18 * s), (1.0 * s, 0.20 * s),
                                  (0.90 * s, 0.30 * s), (0.84 * s, 0.31 * s), (0.82 * s, 0.24 * s), (0, 0.24 * s)],
                   64, [shell], root)
    A.lathe("clock_dial", [(0, 0.245 * s), (0.82 * s, 0.245 * s)], 48, [paper("#F2EDE0", name="dial_paper")], root)
    dome = [(0.83 * s * math.cos(a), 0.30 * s + 0.09 * s * math.sin(a)) for a in [math.pi / 2 * k / 10 for k in range(11)]]
    A.lathe("clock_glass", [(0.83 * s, 0.29 * s)] + [(max(r, 0.0001), z) for r, z in dome] +
            [(max(r, 0.0001), z + 0.012 * s) for r, z in dome[::-1]] + [(0.83 * s, 0.29 * s)], 48, [A.clear_glass()], root)
    h, mi, sec = time
    hands = [("hour", 0.06 * s, 0.50 * s, steel, (h % 12 + mi / 60) * 30), ("minute", 0.045 * s, 0.72 * s, steel, mi * 6 + sec / 10),
             ("second", 0.018 * s, 0.78 * s, A.plastic(red, 0.4, "second_hand"), sec * 6)]
    for i, (name, w, ln, mat, ang) in enumerate(hands):
        hb = A.rounded_box(f"hand_{name}", (w, ln, 0.012 * s), 0.0, [mat], root)
        hb.location = (0, 0, 0.255 * s + i * 0.014 * s)
        hb.rotation_euler.z = math.radians(-ang)
        # the box is centred; shift it so it pivots at the dial centre
        hb.location = Matrix.Rotation(math.radians(-ang), 4, "Z") @ Vector((0, ln / 2 - 0.06 * s, 0)) + Vector(
            (0, 0, 0.255 * s + i * 0.014 * s))
    sphere("hand_cap", 0.03 * s, [brass], root).location = (0, 0, 0.27 * s)
    for k in range(12):
        ang = math.radians(90 - k * 30)
        n = 12 if k == 0 else k
        t = m.text(str(n), "din", 0.24 * s, 0.0, 0.0, "#1B1A19", z=0.25 * s, align="CENTER", valign="CENTER")
        t.data.materials.clear()
        t.data.materials.append(ink)
        t.parent = root
        t.location = (0.60 * s * math.cos(ang), 0.60 * s * math.sin(ang), 0.252 * s)
    for k in range(60):
        ang = math.radians(k * 6)
        tick = A.rounded_box("tick", (0.012 * s, (0.06 if k % 5 else 0.1) * s, 0.004 * s), 0.0, [ink], root)
        tick.location = (0.76 * s * math.sin(ang), 0.76 * s * math.cos(ang), 0.25 * s)
        tick.rotation_euler.z = -ang
    # bells, hammer, feet (local +Y is up until the root is stood up)
    for sx in (-1, 1):
        sphere("bell", 0.36 * s, [shell], root).location = (sx * 0.52 * s, 1.22 * s, 0)
        A.tube_along("bell_stem", [(sx * 0.3 * s, 0.9 * s, 0), (sx * 0.52 * s, 1.1 * s, 0)], 0.035 * s, [brass], root)
        sphere("bell_cap", 0.07 * s, [brass], root).location = (sx * 0.52 * s, 1.58 * s, 0)
    A.tube_along("hammer", [(0, 0.95 * s, 0), (0, 1.5 * s, 0)], 0.03 * s, [brass], root)
    sphere("hammer_head", 0.09 * s, [brass], root).location = (0, 1.52 * s, 0)
    for sx in (-1, 1):
        A.tube_along("foot", [(sx * 0.55 * s, -0.75 * s, 0.1 * s), (sx * 0.85 * s, -1.22 * s, 0.1 * s)], 0.04 * s,
                     [brass], root)
        sphere("foot_ball", 0.08 * s, [brass], root).location = (sx * 0.88 * s, -1.25 * s, 0.1 * s)
    root.rotation_euler = (math.radians(90), 0, math.radians(yaw_deg))   # stand up: local +Z -> -Y, +Y -> up
    root.location = (loc[0], loc[1], loc[2] + 1.3 * s)
    dial = Vector(loc) + Vector((0, 0, 1.3 * s)) + Matrix.Rotation(math.radians(yaw_deg), 3, "Z") @ Vector((0, -0.3 * s, 0))
    return root, dial


# ---------------------------------------------------------------- window, sky card, curtain

def window(x_wall, y0, z0, wy, wz, t=0.01, paint=None, fw=0.007, parent=None):
    """Painted wooden frame set into the opening of the left wall (inner face at x_wall), 2 x 2 panes."""
    paint = paint or painted()
    glass = A.clear_glass(0.02)
    cx = x_wall - t / 2
    yc, zc = y0 + wy / 2, z0 + wz / 2
    for name, size, loc in [("frame_b", (t + 0.004, wy + 2 * fw, fw), (cx, yc, z0 - fw / 2 + 0.001)),
                            ("frame_t", (t + 0.004, wy + 2 * fw, fw), (cx, yc, z0 + wz + fw / 2 - 0.001)),
                            ("frame_l", (t + 0.004, fw, wz + 2 * fw), (cx, y0 - fw / 2 + 0.001, zc)),
                            ("frame_r", (t + 0.004, fw, wz + 2 * fw), (cx, y0 + wy + fw / 2 - 0.001, zc)),
                            ("muntin_v", (0.005, 0.004, wz), (cx, yc, zc)),
                            ("muntin_h", (0.005, wy, 0.004), (cx, yc, zc)),
                            ("sill", (0.016, wy + 2 * fw + 0.01, 0.004), (x_wall + 0.004, yc, z0 - 0.004))]:
        ob = A.rounded_box(name, size, 0.0006, [paint], parent)
        ob.location = loc
    pane = A.rounded_box("window_glass", (0.0006, wy, wz), 0.0, [glass], parent)
    pane.location = (cx, yc, zc)
    pane.visible_shadow = False   # refractive glass is opaque to shadow rays; let the sun through unbent
    return pane


def sky_card(x, yc, zc, w, h, ink="#3E5BA6", paper_hex="#E9E7DF", emit=0.6, parent=None):
    """The printed sky pinned 3 cm outside the window: a halftone gradient on paper, lit from behind
    (visible_shadow off so the window light passes through it)."""
    mat = halftone_card(ink, paper_hex, cell=0.0011, angle_deg=15, normal="X", grad=(-h / 2, h / 2, 0.22, 0.74),
                        strength=1.0, emit=emit)
    card = A.rounded_box("sky_card", (0.0005, w, h), 0.0, [mat], parent)
    card.location = (x, yc, zc)
    card.rotation_euler.x = math.radians(1.5)
    card.visible_shadow = False
    brass = A.brass()
    for sy in (-1, 1):
        pin = sphere("pin", 0.0012, [brass], parent)
        pin.location = (x + 0.001, yc + sy * (w / 2 - 0.006), zc + h / 2 - 0.006)
    return card


def curtain(x, y0, y1, z_top, z_bot, folds=6, amp=0.004, mat=None, parent=None):
    """Sheer curtain hanging in the YZ plane, gathered into folds. Half transparent."""
    if mat is None:
        mat, b = A._principled("sheer", **{"Base Color": m.srgb("#E9E3D8"), "Roughness": 0.9})
        b.inputs["Alpha"].default_value = 0.3
        b.inputs["Sheen Weight"].default_value = 0.6
    w = y1 - y0

    def pt(i, j):
        u, v = i / 40, j / 30
        y = y0 + w * u
        sway = 0.003 * v * v * math.sin(u * 3.0)
        return (x + amp * math.sin(2 * math.pi * folds * u) * (0.6 + 0.4 * v) + sway, y, z_top - (z_top - z_bot) * v)

    cu = grid_mesh("curtain", 40, 30, pt, [mat], parent)
    rod = A.tube_along("curtain_rod", [(x, y0 - 0.01, z_top + 0.004), (x, y1 + 0.02, z_top + 0.004)], 0.0012,
                       [A.brass()], parent)
    return cu, rod


# ---------------------------------------------------------------- desk and what is on it

def desk(loc, size=(0.075, 0.045, 0.060), wood=None, parent=None):
    wood = wood or A.stained_wood("#9A7046", (), ())
    w, d, h = size
    top = A.rounded_box("desk_top", (w, d, 0.006), 0.0008, [wood], parent)
    top.location = (loc[0], loc[1], loc[2] + h - 0.003)
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = A.rounded_box("desk_leg", (0.006, 0.006, h - 0.006), 0.0006, [wood], parent)
            leg.location = (loc[0] + sx * (w / 2 - 0.006), loc[1] + sy * (d / 2 - 0.006), loc[2] + (h - 0.006) / 2)
    return loc[2] + h


def phone(loc, yaw_deg=0.0, parent=None):
    """Lit phone on its back: dark glass body, a notification banner with one pink heart. Returns the screen."""
    root = bpy.data.objects.new("phone", None)
    m._link(root)
    root.location = loc
    root.rotation_euler.z = math.radians(yaw_deg)
    if parent is not None:
        root.parent = parent
    body = A.rounded_box("phone_body", (0.0062, 0.0125, 0.0007), 0.0004, [A.metal("#1A1B20", 0.25, "phone_metal")], root)
    body.location = (0, 0, 0.00035)
    screen = A.rounded_box("phone_screen", (0.0056, 0.0118, 0.0001), 0.0, [A.emissive("#0E1016", 0.6)], root)
    screen.location = (0, 0, 0.00075)
    banner = A.rounded_box("phone_banner", (0.0050, 0.0014, 0.00005), 0.0002, [A.emissive("#F4F4F2", 3.0)], root)
    banner.location = (0, 0.0046, 0.00083)
    heart = flat_shape("phone_heart", [(x * 0.00003, y * 0.00003) for x, y in m.heart_outline(48)],
                       [A.emissive("#FF3D8B", 6.0)], root)
    heart.location = (-0.0018, 0.0046, 0.00087)
    return screen


def milk_glass(loc, fill=0.5, parent=None):
    """Tumbler with milk, a small heart bulb floating on it."""
    r0, r1, hgt, wall = 0.0028, 0.0033, 0.0088, 0.0004
    outer = [(0, 0), (r0 - 0.0003, 0), (r0, 0.0003), (r1, hgt)]
    inner = [(r1 - wall, hgt), (r0 - wall, 0.0012), (0, 0.0012)]
    glass = A.lathe("glass", outer + inner, 64, [A.clear_glass(0.01)], parent)
    glass.location = loc
    lvl = 0.0012 + (hgt - 0.0012) * fill
    rl = r0 - wall + (r1 - r0) * (lvl / hgt)
    mk = A.lathe("milk", [(0, 0.00125), (r0 - wall - 0.00002, 0.00125), (rl - 0.00002, lvl), (0, lvl)], 64, [milk()], parent)
    mk.location = loc
    bulb = A.heart_bulb("clean", 0.0028, seed=2)
    bulb.location = (loc[0] + 0.0006, loc[1] - 0.0004, loc[2] + lvl - 0.0002)
    bulb.rotation_euler = (math.radians(70), 0, math.radians(-30))
    if parent is not None:
        bulb.parent = parent
    return glass


def print_stack(loc, image, count=5, size=(0.030, 0.017), seed=3, parent=None):
    rnd = random.Random(seed)
    mat = A.printed(image)
    for k in range(count):
        sh = A.rounded_box("print", (size[0], size[1], 0.00025), 0.0, [mat], parent)
        map_uv(sh, ("x", "y"), size)
        sh.location = (loc[0] + rnd.uniform(-0.002, 0.002), loc[1] + rnd.uniform(-0.002, 0.002), loc[2] + 0.0003 * k)
        sh.rotation_euler.z = math.radians(rnd.uniform(-7, 7))


def polaroid(loc, image, tilt_deg=0.0, photo=0.019, parent=None, tape=None):
    """White-bordered print taped to the back wall (wall inner face at loc[1]); faces -Y."""
    card = A.rounded_box("polaroid", (photo + 0.004, 0.0005, photo + 0.009), 0.0, [paper("#F7F4EC", name="polaroid")], parent)
    card.location = (loc[0], loc[1] - 0.0003, loc[2])
    card.rotation_euler.y = math.radians(tilt_deg)
    ph = A.rounded_box("photo", (photo, 0.0002, photo), 0.0, [A.printed(image, rough=0.5)], card)
    map_uv(ph, ("x", "z"), (photo, photo))
    ph.location = (0, -0.0004, 0.0025)
    tp = A.rounded_box("tape", (0.011, 0.0002, 0.005), 0.0, [tape or paper("#D9C9A3", name="tape", alpha=0.85)], card)
    tp.location = (0, -0.0007, (photo + 0.009) / 2 - 0.001)
    tp.rotation_euler.y = math.radians(8)
    return card


def wallpaper_peel(loc, reveal="#121116", wall_hex="#EEE8DA", size=(0.028, 0.040), parent=None):
    """A corner of wallpaper curling off the back wall; behind it the other side's paper."""
    patch = A.rounded_box("peel_reveal", (size[0], 0.0004, size[1]), 0.0, [paper(reveal, name="reveal")], parent)
    patch.location = (loc[0], loc[1] - 0.0002, loc[2])
    R = 0.011

    def pt(i, j):
        u, v = i / 24, j / 16
        a = u * 2.6
        return (loc[0] - size[0] / 2 + R * math.sin(a) * (0.5 + 0.5 * v) + size[0] * u * (0.5 - 0.5 * v),
                loc[1] - 0.0006 - R * (1 - math.cos(a)) * (0.2 + 0.8 * v),
                loc[2] - size[1] / 2 + size[1] * (1 - v))

    flap = grid_mesh("peel_flap", 24, 16, pt, [paper(wall_hex, name="flap")], parent)
    flap.modifiers.new("solid", "SOLIDIFY").thickness = 0.0003
    return flap


def dust(region, count=300, seed=9, name="dust"):
    """Specks floating in the window beam; only visible where the light hits them."""
    rnd = random.Random(seed)
    (x0, x1), (y0, y1), (z0, z1) = region
    bm = bmesh.new()
    for _ in range(count):
        r = rnd.uniform(0.000025, 0.0001)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r, matrix=Matrix.Translation(
            (rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(z0, z1))))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return A._obj(name, mesh, [paper("#FFFFFF", name="dust")])


# ---------------------------------------------------------------- shared with the other sets

def map_uv_grid(obj, nx, ny):
    """UVs from the grid indices of a grid_mesh object, so a print runs along the strip."""
    uv = obj.data.uv_layers.new()
    for loop in obj.data.loops:
        idx = loop.vertex_index
        uv.data[loop.index].uv = ((idx % (nx + 1)) / nx, (idx // (nx + 1)) / ny)


def tiles(tile=0.02, grout=0.0009, tile_hex="#F2F0EA", grout_hex="#2B2A2C", rough=0.12, name="tiles"):
    """Glazed square tiles with dark grout, by a brick texture in object space (the top face is XY)."""
    mat, b = A._principled(name, **{"Roughness": rough})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = tile
    br.inputs["Row Height"].default_value = tile
    br.inputs["Mortar Size"].default_value = grout
    br.inputs["Mortar Smooth"].default_value = 0.15
    br.inputs["Color1"].default_value = m.srgb(tile_hex)
    br.inputs["Color2"].default_value = m.srgb("#E9E6DE")
    br.inputs["Mortar"].default_value = m.srgb(grout_hex)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    rg = nt.nodes.new("ShaderNodeMath")       # grout is rough, glaze is not
    rg.operation = "MULTIPLY_ADD"
    rg.inputs[1].default_value = 0.7
    rg.inputs[2].default_value = rough
    nt.links.new(br.outputs["Fac"], rg.inputs[0])
    nt.links.new(rg.outputs[0], b.inputs["Roughness"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.0006
    bp.invert = True
    nt.links.new(br.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return mat


def handwriting(loc, lines=4, length=0.03, ink="#C9261B", seed=4, radius=0.00022, parent=None):
    """Scrawled lines of 'writing': wobbly red tubes on a card at loc (its top face), running along +X."""
    rnd = random.Random(seed)
    glaze = A.glaze(ink)
    for k in range(lines):
        y = loc[1] + 0.004 * (lines / 2 - k) - 0.002
        pts, x = [], loc[0] - length / 2
        while x < loc[0] + length / 2 * rnd.uniform(0.6, 1.0):
            pts.append((x, y + rnd.uniform(-0.0012, 0.0012), loc[2] + 0.0001))
            x += rnd.uniform(0.0012, 0.0025)
        if len(pts) > 3:
            A.tube_along(f"writing{k}", pts, radius, [glaze], parent, resolution=2)


# ---------------------------------------------------------------- instancing many small props

def joined_copy(objs, name, parent=None):
    """One mesh object made from the evaluated meshes of objs (curves and modifiers included), with their
    materials as slots, in the coordinate frame of the first object's parent. Used to turn a multi-part prop
    like a heart bulb into a single instanceable mesh."""
    deps = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats = []
    base = objs[0].parent.matrix_world.inverted() if objs[0].parent else Matrix.Identity(4)
    for ob in objs:
        if ob.type not in ("MESH", "CURVE", "FONT"):
            continue
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        if me is None or len(me.polygons) == 0:
            ev.to_mesh_clear()
            continue
        me = me.copy()
        me.transform(base @ ob.matrix_world)
        slot_map = []
        for ms in ob.material_slots:
            if ms.material not in mats:
                mats.append(ms.material)
            slot_map.append(mats.index(ms.material))
        for p in me.polygons:
            p.material_index = slot_map[p.material_index] if slot_map else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        ev.to_mesh_clear()
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for p in out.polygons:
        p.use_smooth = True
    return A._obj(name, out, mats, parent)


def library_collection(name, objs):
    """Put objs into their own collection, unlinked from the scene, so they render only as instances."""
    coll = bpy.data.collections.new(name)
    for ob in objs:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    return coll


def instance_on_points(name, points, coll, seed=1, scale=(0.8, 1.25), rotate=True):
    """A mesh of loose vertices at `points` with a Geometry Nodes modifier that puts a random object from
    coll at each one, randomly turned and scaled. Returns the point object."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in points], [], [])
    ob = A._obj(name, me, [])
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    ci = ng.nodes.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    ci.transform_space = "RELATIVE"
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    ng.links.new(gi.outputs[0], iop.inputs["Points"])
    ng.links.new(ci.outputs[0], iop.inputs["Instance"])
    # Blender 5.x: the Random Value node only shows the sockets of its data type, so address them by name
    idx = ng.nodes.new("FunctionNodeRandomValue")
    idx.data_type = "INT"
    idx.inputs["Min"].default_value, idx.inputs["Max"].default_value = 0, max(0, len(coll.objects) - 1)
    idx.inputs["Seed"].default_value = seed
    ng.links.new(idx.outputs[0], iop.inputs["Instance Index"])
    if rotate:
        rot = ng.nodes.new("FunctionNodeRandomValue")
        rot.data_type = "FLOAT_VECTOR"
        rot.inputs["Min"].default_value = (0, 0, 0)
        rot.inputs["Max"].default_value = (6.2832, 6.2832, 6.2832)
        rot.inputs["Seed"].default_value = seed + 1
        ng.links.new(rot.outputs[0], iop.inputs["Rotation"])
    sc = ng.nodes.new("FunctionNodeRandomValue")
    sc.data_type = "FLOAT"
    sc.inputs["Min"].default_value, sc.inputs["Max"].default_value = scale
    sc.inputs["Seed"].default_value = seed + 2
    sv = ng.nodes.new("ShaderNodeCombineXYZ")
    for k in ("X", "Y", "Z"):
        ng.links.new(sc.outputs[0], sv.inputs[k])
    ng.links.new(sv.outputs[0], iop.inputs["Scale"])
    ng.links.new(iop.outputs[0], go.inputs[0])
    mod = ob.modifiers.new("gn", "NODES")
    mod.node_group = ng
    return ob


def bulb_library(size=0.0045, states=("infected", "infected", "clean")):
    """Three joined heart bulbs in an unlinked collection, for instance_on_points."""
    objs = []
    for i, st in enumerate(states):
        root = A.heart_bulb(st, size, seed=20 + i)
        parts = [c for c in root.children_recursive]
        joined = joined_copy(parts, f"bulb_lib{i}")
        for c in parts:
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(root)
        objs.append(joined)
    return library_collection("bulb_lib", objs)
