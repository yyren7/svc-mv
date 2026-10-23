"""v4 晾画大厅 (script_v4.md 1.1, 1.2): the look of the hall before anything moves. A long empty hall with a floor
of still black water, rows of two-sided prints of her hung on wires, a row of high windows with the sky behind.
Two lights: dawn (表: a cold sun through the high windows and haze, the prints lit from the front) and rose (裏:
a rose lamp behind every print, so the back of each sheet shows through the front). Cycles stills.

    blender -b --factory-startup -P cases/uraomote/scripts/v4_hall.py -- [out_dir] [shot ...]
    shots: aisle_dawn aisle_rose front_rose

A print is one sheet with two pictures on the same UVs: the front one faces -X, the back one is printed mirrored,
so from the front it shows through exactly behind the front picture, and from behind it reads left-right reversed.
Light through the paper passes both inks, so the translucent colour is front x back. `WET` (0..1) is how much light
the paper lets through: dry paper about 0.15, wet paper 0.7.
KV' does not exist yet, so for now every back is a 裏 picture of another composition.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import assets as A  # noqa: E402
import cyc  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402

OUT, SHOTS = cyc.args(os.path.join(C.RENDERS, "v4_hall"), ["aisle_dawn", "aisle_rose", "front_rose"])
ART = os.path.join(C.CASE, "art", "v4")
L, WD, H = 40.0, 14.0, 12.0                 # the hall: length along +X, width along Y, height
SHEET_W, SHEET_H = 2.4, 4.2                 # a print, metres
TOP = 5.0                                   # the prints' top edge above the water
ROWS = [2.0 + 4.0 * i for i in range(7)]    # x of each wire
WET = float(os.environ.get("WET", 0.18))
ROSE = "#F0285A"

# fronts are 表 pictures, backs 裏 ones; the first print (row 0, in the middle) is the KV
KV = ("v4_kv_205", "v4_chorus_203")
FRONTS = ["v4_kv_201", "v4_window_201", "v4_kv_203", "v4_window_203", "v4_kv_207", "v4_kv_205"]
BACKS = ["v4_chorus_201", "v4_rain_201", "v4_chorus_205", "v4_water_201", "v4_chorus_207", "v4_rain_203",
         "v4_water_203"]


def _nodes(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return mat, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def _picture(nt, name):
    """An image texture on the sheet's UVs, the middle of the picture when its aspect differs from the sheet's."""
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(ART, f"{name}_00001_.png"), check_existing=True)
    tex.extension = "EXTEND"
    w, h = tex.image.size
    a, target = w / h, SHEET_W / SHEET_H
    mp = nt.nodes.new("ShaderNodeMapping")
    s = (target / a, 1.0) if a > target else (1.0, a / target)
    mp.inputs["Scale"].default_value = (s[0], s[1], 1.0)
    mp.inputs["Location"].default_value = ((1 - s[0]) / 2, (1 - s[1]) / 2, 0.0)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    return tex.outputs["Color"]


def _multiply(nt, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MULTIPLY"
    kit.sock(n.inputs, "Factor", "VALUE").default_value = 1.0
    nt.links.new(a, kit.sock(n.inputs, "A", "RGBA"))
    nt.links.new(b, kit.sock(n.inputs, "B", "RGBA"))
    return kit.sock(n.outputs, "Result", "RGBA")


def print_mat(front, back, wet=WET):
    """Thin paper printed on both sides: diffuse with the facing picture, translucent with both inks."""
    mat, nt, out = _nodes(f"print_{front}_{back}")
    f, b = _picture(nt, front), _picture(nt, back)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    facing = kit._mix_rgba(nt, geo.outputs["Backfacing"], f, b)
    through = _multiply(nt, f, b)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    fibre = nt.nodes.new("ShaderNodeTexNoise")
    fibre.inputs["Scale"].default_value = 260.0
    fibre.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], fibre.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.0004
    nt.links.new(fibre.outputs["Fac"], bump.inputs["Height"])
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    nt.links.new(facing, dif.inputs["Color"])
    nt.links.new(bump.outputs["Normal"], dif.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(through, tr.inputs["Color"])
    nt.links.new(bump.outputs["Normal"], tr.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = wet
    nt.links.new(dif.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def sheet(name, x, y, mat, seed):
    """A hanging print: a grid in the YZ plane facing -X, bowed a little and curling at the foot."""
    rnd = random.Random(seed)
    nu, nv = 10, 18
    bow, curl, lean = rnd.uniform(0.02, 0.06), rnd.uniform(0.03, 0.09), rnd.uniform(-0.04, 0.04)
    verts, uvs = [], []
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            u = i / nu
            dx = bow * math.sin(math.pi * u) * (0.4 + 0.6 * v) + curl * (1 - v) ** 3 + lean * (1 - v)
            verts.append((x + dx, y + SHEET_W / 2 - u * SHEET_W, TOP - SHEET_H + v * SHEET_H))
            uvs.append((u, v))
    faces = [(j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i)
             for j in range(nv) for i in range(nu)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    uv = mesh.uv_layers.new(name="UV")
    for poly in mesh.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            uv.data[li].uv = uvs[mesh.loops[li].vertex_index]
    ob = A._obj(name, mesh, [mat])
    metal = A._principled("clip", **{"Base Color": m.srgb("#2A2A2E"), "Metallic": 1.0, "Roughness": 0.35})[0]
    for side in (-1, 1):
        clip = A.rounded_box(f"{name}_clip{side}", (0.03, 0.05, 0.07), 0.004, [metal])
        clip.location = (x, y + side * (SHEET_W / 2 - 0.12), TOP + 0.01)
    return ob


def hall(dawn):
    plaster, b = A._principled("plaster", **{"Base Color": m.srgb("#8E8D89" if dawn else "#5A5856"), "Roughness": 0.92})
    A._bump(plaster, b, 3.0, 0.25, detail=8.0, distance=0.02)
    water, b = A._principled("water", **{"Base Color": (0.002, 0.002, 0.003, 1.0), "Roughness": 0.015, "IOR": 1.33})
    A._bump(water, b, 0.35, 0.05, detail=2.0, distance=0.03)
    floor = A.rounded_box("water", (L + 20, WD, 0.04), 0.0, [water])
    floor.location = (L / 2, 0, -0.02)
    t = 0.4
    walls = [((L / 2, -WD / 2 - t / 2, H / 2), (L + 20, t, H)),          # the dark wall
             ((L / 2, 0, H + t / 2), (L + 20, WD + 2 * t, t)),          # ceiling
             ((L + t / 2, 0, H / 2), (t, WD, H)),                       # far end
             ((L / 2, WD / 2 + t / 2, 3.0), (L + 20, t, 6.0)),          # window wall below the windows
             ((L / 2, WD / 2 + t / 2, 11.25), (L + 20, t, 1.5))]        # and above them
    xs = [3.0 + 4.0 * i for i in range(10)]                             # window centres, each 2.6 m wide
    edges = [-10.0] + [e for x in xs for e in (x - 1.3, x + 1.3)] + [L + 10]
    walls += [(((a + b2) / 2, WD / 2 + t / 2, 8.25), (b2 - a, t, 4.5)) for a, b2 in zip(edges[::2], edges[1::2])]
    for k, (loc, size) in enumerate(walls):
        A.rounded_box(f"wall{k}", size, 0.0, [plaster]).location = loc
    # the sky behind the windows: painted later (S1, S2), a glowing backdrop for now
    sky, nt, out = _nodes("sky")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb("#D6E4F2" if dawn else "#0E1630")
    em.inputs["Strength"].default_value = 2.5 if dawn else 0.4
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    A.rounded_box("sky", (L + 40, 0.1, 30), 0.0, [sky]).location = (L / 2, WD / 2 + 4.0, 10)


def hang():
    mats, k = {}, 0
    steel = A._principled("steel", **{"Base Color": m.srgb("#3A3A40"), "Metallic": 1.0, "Roughness": 0.3})[0]
    prints = []
    for r, x in enumerate(ROWS):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.004, depth=WD, location=(x, 0, TOP + 0.04),
                                            rotation=(math.pi / 2, 0, 0))
        bpy.context.active_object.data.materials.append(steel)
        ys = [0.0] if r == 0 else ([-4.8, -1.6, 1.6, 4.8] if r % 2 else [-3.2, 0.0, 3.2])
        for y in ys:
            front, back = KV if r == 0 else (FRONTS[k % len(FRONTS)], BACKS[k % len(BACKS)])
            if r:
                k += 1
            key = (front, back)
            if key not in mats:
                mats[key] = print_mat(front, back)
            prints.append(sheet(f"print_{r}_{y:+.1f}", x, y, mats[key], seed=r * 10 + int(y * 3)))
    return prints


def light(dawn, prints):
    if dawn:
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy = 6.0
        sun.angle = math.radians(0.6)
        sun.color = A.kelvin(7600)
        ob = bpy.data.objects.new("sun", sun)
        m._link(ob)
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = Vector((0.35, -0.55, -0.75)).normalized().to_track_quat("-Z", "Y")
        cyc.area_light("bounce", (L / 2, 0, 0.6), (L / 2, 0, 5), 20, 7000, 400, size_y=8)   # light off the water
        cyc.haze("haze", (L + 10, WD, H), (L / 2, 0, H / 2), 0.0045, color="#E4ECF4", anisotropy=0.55)
        return
    for p in prints:
        x = p.data.vertices[0].co.x
        y = sum(v.co.y for v in p.data.vertices) / len(p.data.vertices)
        lamp = cyc.area_light(f"behind_{p.name}", (x + 0.9, y, TOP - SHEET_H / 2), (x, y, TOP - SHEET_H / 2),
                              2.0, 2000, 260, size_y=3.6, color=ROSE)
        lamp.visible_glossy = False
    cyc.area_light("fill", (L / 2, 0, H - 0.5), (L / 2, 0, 0), 30, 9000, 120, size_y=10, color="#5A78FF")
    cyc.haze("haze", (L + 10, WD, H), (L / 2, 0, H / 2), 0.0035, color="#F2D8E0", anisotropy=0.4)


def main():
    dawn = all(s.endswith("dawn") for s in SHOTS)
    if not dawn and any(s.endswith("dawn") for s in SHOTS):
        sys.exit("dawn and rose shots need separate runs (the lights differ)")
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0004, 0.0004, 0.0008))
    hall(dawn)
    prints = hang()
    light(dawn, prints)
    cyc.post(bloom=0.35 if dawn else 0.6, threshold=1.0 if dawn else 0.75)
    kv = (ROWS[0], 0.0, TOP - SHEET_H / 2)
    cams = {"aisle_dawn": cyc.camera("aisle_dawn", (-1.0, -3.8, 0.75), (20.0, 0.8, 3.0), 24, 4.0),
            "aisle_rose": cyc.camera("aisle_rose", (-1.0, -3.8, 0.75), (20.0, 0.8, 3.0), 24, 4.0),
            "front_rose": cyc.camera("front_rose", (-4.6, 0.0, 2.95), (ROWS[0], 0.0, 2.95), 28, 5.6)}
    cams = {k: v for k, v in cams.items() if k in SHOTS}
    cyc.render_shots(cams, SHOTS, OUT, "hall", focus={k: kv for k in cams},
                     samples={k: (128 if k.endswith("dawn") else 160) for k in cams}, blend="hall_dawn.blend" if dawn else "hall_rose.blend")


main()
