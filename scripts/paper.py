"""Thin paper printed on both sides, hung as a sheet: the 2D picture's body in a 3D Cycles scene.

A print is one sheet with two pictures on the same UVs: the front one faces -X, the back one is printed mirrored,
so from the front it shows through exactly behind the front picture, and from behind it reads left-right reversed.
The picture sits inside a border of bare paper (MARGIN, deeper at the foot, as prints are); the paper is warm cotton
rag with a faint fibre and a slow cockle, so under raking light a sheet reads as paper and not as a screen. Light
through the paper passes both inks, so the translucent colour is front x back, and the bare border lets through a
third of what the picture does (behind a rose lamp a print's foot margin otherwise glows like a strip light).
`WET` (0..1) is how much light the paper lets through: dry paper about 0.15, wet paper 0.7; the animatic wets a
print per frame through the mix node named "wet".

A case sets where its pictures are before building anything (`paper.ART = ...`, the ComfyUI output names
`<picture>_00001_.png`), and may change the sheet's size, margin, colour and hanging height the same way.
hybrid.py builds on this: the same sheet with the picture's flat planes swapped for the scene's own surfaces and
her figure as a relief. Lessons that shaped it are in docs/hybrid.md.
"""
import math
import os
import random

import bpy

import assets as A
import kit
import mvlib as m

ART = None                                  # the folder of the pictures (a case sets it)
SUFFIX = "_00001_.png"                      # ComfyUI's output names: <picture>_00001_.png
SHEET_W, SHEET_H = 2.4, 4.2                 # a print, metres
MARGIN = 0.08                               # bare paper round the picture; the foot's border is 1.4x this
PAPER = "#F1ECE2"                           # warm cotton rag
TOP = 5.0                                   # the prints' top edge above the floor (the water)
WET = float(os.environ.get("WET", 0.18))


def path(name):
    """The picture file of `name`."""
    return os.path.join(ART, name + SUFFIX)


def image(name):
    """The picture `name` as a Blender image, loaded once."""
    return bpy.data.images.load(path(name), check_existing=True)


def nodes(name):
    """A fresh node material: (material, node tree, its output node)."""
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return mat, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def layout(w, h, size=None, margin=None):
    """How picture() lays a w x h picture on a sheet of `size`: the border (mu, mv), the picture rectangle's size
    (rw, rh) in sheet UVs and the crop (s) of the picture inside it (the middle of the picture where its aspect
    differs from the rectangle's)."""
    W, Hh = size or (SHEET_W, SHEET_H)
    margin = MARGIN if margin is None else margin
    mu, mv = margin / W, 1.4 * margin / Hh
    rw, rh = 1 - 2 * mu, 1 - mv - margin / Hh
    a, target = w / h, (W * rw) / (Hh * rh)
    s = (target / a, 1.0) if a > target else (1.0, a / target)
    return mu, mv, rw, rh, s


def size_of(ob):
    """A sheet's (width, height), as sheet() remembered them."""
    return ob.get("sheet_w", SHEET_W), ob.get("sheet_h", SHEET_H)


def picture(nt, name, margin=0.0, file=None, size=None):
    """An image texture on the sheet's UVs, the middle of the picture where its aspect differs from the sheet's.
    With `margin` (metres) the picture sits inside a border of bare paper and (colour, alpha) come back, alpha 0 on
    the border; without, it fills the sheet and only the colour does. `file` is another image laid out exactly as
    the picture `name` is (a map of it); `size` the sheet's (width, height) when it is not the usual one."""
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(file or path(name), check_existing=True)
    tex.extension = "CLIP" if margin else "EXTEND"
    w, h = tex.image.size
    mu, mv, rw, rh, s = layout(w, h, size, margin)
    mp = nt.nodes.new("ShaderNodeMapping")                           # uv -> the rectangle as 0..1 -> the picture's middle
    mp.inputs["Scale"].default_value = (s[0] / rw, s[1] / rh, 1.0)
    mp.inputs["Location"].default_value = ((1 - s[0]) / 2 - mu * s[0] / rw, (1 - s[1]) / 2 - mv * s[1] / rh, 0.0)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    return (tex.outputs["Color"], tex.outputs["Alpha"]) if margin else tex.outputs["Color"]


def multiply(nt, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = "MULTIPLY"
    kit.sock(n.inputs, "Factor", "VALUE").default_value = 1.0
    nt.links.new(a, kit.sock(n.inputs, "A", "RGBA"))
    nt.links.new(b, kit.sock(n.inputs, "B", "RGBA"))
    return kit.sock(n.outputs, "Result", "RGBA")


def coords(nt):
    """Object coordinates shifted by the object's random, so sheets sharing a material don't share a pattern."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    shift = nt.nodes.new("ShaderNodeVectorMath")
    shift.operation = "SCALE"
    shift.inputs[0].default_value = (37.0, 53.0, 71.0)
    nt.links.new(info.outputs["Random"], shift.inputs["Scale"])
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(tc.outputs["Object"], add.inputs[0])
    nt.links.new(shift.outputs[0], add.inputs[1])
    return add.outputs[0]


def bare(nt, co):
    """Bare paper: PAPER with a faint mottle, so a border is not one flat colour."""
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 12.0
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(co, nz.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(nz.outputs["Fac"], kit.sock(mix.inputs, "Factor", "VALUE"))
    kit.sock(mix.inputs, "A", "RGBA").default_value = m.srgb(PAPER)
    kit.sock(mix.inputs, "B", "RGBA").default_value = tuple(c * 0.965 for c in m.srgb(PAPER)[:3]) + (1.0,)
    return kit.sock(mix.outputs, "Result", "RGBA")


def cockle(nt, co):
    """Paper's relief as a normal: a slow cockle (hung paper is never flat) with the fibre on top of it."""
    slow = nt.nodes.new("ShaderNodeTexNoise")
    slow.inputs["Scale"].default_value = 1.6
    slow.inputs["Detail"].default_value = 3.0
    slow.inputs["Roughness"].default_value = 0.55
    nt.links.new(co, slow.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.005
    nt.links.new(slow.outputs["Fac"], bump.inputs["Height"])
    fibre = nt.nodes.new("ShaderNodeTexNoise")
    fibre.inputs["Scale"].default_value = 260.0
    fibre.inputs["Detail"].default_value = 6.0
    nt.links.new(co, fibre.inputs["Vector"])
    fine = nt.nodes.new("ShaderNodeBump")
    fine.inputs["Strength"].default_value = 0.12
    fine.inputs["Distance"].default_value = 0.0004
    nt.links.new(fibre.outputs["Fac"], fine.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], fine.inputs["Normal"])
    return fine.outputs["Normal"]


def print_mat(front, back, wet=None, size=None):
    """Thin paper printed on both sides: the facing picture inside its border, translucent with both inks."""
    mat, nt, out = nodes(f"print_{front}_{back}")
    co = coords(nt)
    paper = bare(nt, co)

    def inked(name):
        col, alpha = picture(nt, name, MARGIN, size=size)
        return kit._mix_rgba(nt, alpha, paper, multiply(nt, paper, col)), alpha

    (f, fa), (b, ba) = inked(front), inked(back)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    facing = kit._mix_rgba(nt, geo.outputs["Backfacing"], f, b)
    # the bare border lets through a third of what the picture does: with the rose lamp behind, a print's foot
    # margin glowed like a strip light under it
    through = multiply(nt, multiply(nt, f, b), kit._mix_rgba(nt, fa, (0.35, 0.35, 0.35, 1.0), (1.0, 1.0, 1.0, 1.0)))
    normal = cockle(nt, co)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.72
    bsdf.inputs["Specular IOR Level"].default_value = 0.25           # a matt print: a little sheen at grazing angles
    nt.links.new(facing, bsdf.inputs["Base Color"])
    nt.links.new(normal, bsdf.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(through, tr.inputs["Color"])
    nt.links.new(normal, tr.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = "wet"                                     # the animatic wets a print through this node
    mix.inputs["Fac"].default_value = WET if wet is None else wet
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def sheet(name, x, y, mat, seed, top=None, grid=(16, 28), relief=None, size=None):
    """A hanging print: a grid in the YZ plane facing -X, bowed a little, curling and waving at the foot, hung a
    touch askew, a galvanised clip at each top corner. Its origin is the middle of its top edge, at (x, y, top), so
    it turns, lifts in the wind or lies down about that point. `relief(u, v)` adds its own offset along X (negative:
    towards the front); give it a finer `grid`. `size` is the sheet's (width, height) when it is not the usual one;
    the object remembers it as sheet_w and sheet_h."""
    W, Hh = size or (SHEET_W, SHEET_H)
    top = TOP if top is None else top
    rnd = random.Random(seed)
    nu, nv = grid
    bow, curl, lean = rnd.uniform(0.02, 0.06), rnd.uniform(0.03, 0.09), rnd.uniform(-0.04, 0.04)
    wave, phase = rnd.uniform(0.008, 0.02), rnd.uniform(0.0, 2 * math.pi)
    verts, uvs = [], []
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            u = i / nu
            dx = bow * math.sin(math.pi * u) * (0.4 + 0.6 * v) + curl * (1 - v) ** 3 + lean * (1 - v) \
                + wave * math.sin(3 * math.pi * u + phase) * (1 - v) ** 2
            if relief is not None:
                dx += relief(u, v)
            verts.append((dx, W / 2 - u * W, (v - 1) * Hh))
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
    ob.location = (x, y, top)
    ob.rotation_euler = (0.0, 0.0, rnd.uniform(-0.03, 0.03))
    ob["sheet_w"], ob["sheet_h"] = W, Hh
    metal = A._principled("clip", **{"Base Color": m.srgb("#9A9DA0"), "Metallic": 1.0, "Roughness": 0.35})[0]
    for side in (-1, 1):                                             # a galvanised clip over the wire at each top corner
        A.rounded_box(f"{name}_clip{side}", (0.03, 0.06, 0.1), 0.004, [metal],
                      parent=ob).location = (0, side * (W / 2 - 0.12), 0.0)
    return ob
