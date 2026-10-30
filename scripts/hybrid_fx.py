"""3D things that live inside a 2D picture's dimensional parts, and the effects of the room round the prints, for
the hybrid PV: ink as a volume, cracks of light, rain, torn paper, dust, shards of glass with pieces of her
pictures in them, strands of her hair off the paper, a print torn in two halves, letters cut out of a print, the
pulse ring on the room's water and the painted sky on its backdrop.

Each builder returns what it makes (objects, sockets, the per-frame items) and the case keeps them where its shots
can reach them; the setters (ink, scraps, dust, sway) take those back with the frame's time. Nothing here depends
on one room's layout: positions, sizes and colours are arguments with the values that held in the first case
(cases/uraomote). What each of them learnt the hard way is in docs/hybrid.md.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import assets as A
import cyc
import hybrid as H
import kit
import mvlib as m
import paper as P

ROSE, GLOW = "#F0285A", "#FF5C8A"           # the ink, and the ink where it glows
PAPER = "#F2F0EB"                            # paper white, for the scraps' faint glow


# ---------------------------------------------------------------- small helpers

def emission_mat(name, hexstr, strength):
    mat, nt, out = P.nodes(name)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb(hexstr)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat, em


def only_camera(ob):
    """Seen by the camera alone: it lights nothing, shades nothing, mirrors nowhere."""
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter",
                 "visible_shadow"):
        setattr(ob, attr, False)


def mesh(name, verts, faces, uvs=None, mats=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs is not None:
        layer = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uvs[me.loops[li].vertex_index]
    return A._obj(name, me, mats)


# ---------------------------------------------------------------- the room's planes

def sky_backdrop(em, scale=(5.0, 4.0, 1.0), offset=(0.0, -1.33, 0.0)):
    """The painted sky on the backdrop behind the windows (D2): an image, mirrored and tiled by `scale` over the
    backdrop's generated coordinates, on its emission `em`; the image is swapped per shot. Returns (texture node,
    emission node)."""
    nt = em.id_data
    g = kit.G(nt)
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(tc.outputs["Generated"], sep.inputs[0])
    comb = g.node("ShaderNodeCombineXYZ")
    g.link(sep.outputs["X"], comb.inputs["X"])
    g.link(sep.outputs["Z"], comb.inputs["Y"])
    mp = g.node("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Location"].default_value = offset
    g.link(comb.outputs[0], mp.inputs["Vector"])
    tex = g.node("ShaderNodeTexImage")
    tex.extension = "MIRROR"
    g.link(mp.outputs[0], tex.inputs["Vector"])
    g.link(tex.outputs["Color"], em.inputs["Color"])
    return tex, em


def water_ring(mat, glow=ROSE):
    """The pulse on the room's water (a beat is a ring on the water): one ring at a time, its centre, radius and
    height set per frame through the returned `rip` values (x, y, r, a), on top of the water's own ripples.
    Returns dict(rip, glow=the water's emission strength socket, bump=its own ripples' strength socket, bump0=that
    strength as built)."""
    nt = mat.node_tree
    g = kit.G(nt)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    old = next(n for n in nt.nodes if n.type == "BUMP")
    geo = g.node("ShaderNodeNewGeometry")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(geo.outputs["Position"], sep.inputs[0])
    rip = {k: kit.value(nt) for k in ("x", "y", "r", "a")}
    dx = g.math("SUBTRACT", sep.outputs["X"], rip["x"])
    dy = g.math("SUBTRACT", sep.outputs["Y"], rip["y"])
    e = g.math("SUBTRACT", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy))),
               rip["r"])
    wave = g.math("SINE", g.math("MULTIPLY", e, 2 * math.pi / 0.3))
    env = g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", e, e), -1 / 0.2 ** 2))
    bp = g.node("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 1.0
    bp.inputs["Distance"].default_value = 0.04
    g.link(g.math("MULTIPLY", g.math("MULTIPLY", wave, env), rip["a"]), bp.inputs["Height"])
    g.link(old.outputs["Normal"], bp.inputs["Normal"])
    g.link(bp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Emission Color"].default_value = m.srgb(glow)
    return dict(rip=rip, glow=bsdf.inputs["Emission Strength"], bump=old.inputs["Strength"],
                bump0=old.inputs["Strength"].default_value)


# ---------------------------------------------------------------- ink

def ink_volume(name, seed, color="#8C2446", absorb="#5A1030", glow=GLOW):
    """Rose ink in water: noise inside a sphere, thinning to its edge and glowing a little (it scatters dark: ink is
    not a lamp). Its density, glow and swirl (the noise's W) are set per frame by ink()."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
    ob = bpy.context.active_object
    ob.name = name
    mat, nt, out = P.nodes(name)
    g = kit.G(nt)
    tc = g.node("ShaderNodeTexCoord")
    nz = g.node("ShaderNodeTexNoise", {"Scale": 2.4, "Detail": 6.0, "Distortion": 0.8}, noise_dimensions="4D")
    g.link(tc.outputs["Object"], nz.inputs["Vector"])
    w = kit.value(nt, seed)
    g.link(w, nz.inputs["W"])
    fall = g.math("SUBTRACT", 1.0, g.vmath("LENGTH", tc.outputs["Object"]), clamp=True)
    dens = g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", nz.outputs["Fac"], 0.42, clamp=True), 12.0), fall)
    k, gl = kit.value(nt), kit.value(nt)
    vol = g.node("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = m.srgb(color)
    vol.inputs["Absorption Color"].default_value = m.srgb(absorb)
    vol.inputs["Emission Color"].default_value = m.srgb(glow)
    g.link(g.math("MULTIPLY", dens, k), vol.inputs["Density"])
    g.link(g.math("MULTIPLY", dens, gl), vol.inputs["Emission Strength"])
    g.link(vol.outputs[0], out.inputs["Volume"])
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return dict(ob=ob, w=w, seed=seed, density=k, glow=gl)


def ink(blob, loc, scale, density=1.0, glow=0.3, t=0.0):
    """The ink `blob` shown at `loc`, stretched by `scale` (metres), its density and glow per metre, swirling with
    the time `t`."""
    ob = blob["ob"]
    ob.hide_render = False
    ob.location, ob.scale = loc, scale
    blob["density"].default_value = density * 8.0 / max(scale)
    blob["glow"].default_value = glow * 8.0 / max(scale)
    blob["w"].default_value = blob["seed"] + 0.3 * t


# ---------------------------------------------------------------- a glass of water

def outward(ob):
    """Turn a lathe's normals outwards if they point in (its strip of faces meets itself only at the axis, so
    bmesh's recalc is free to orient the whole cup inwards, and Cycles would then refract every entry as an exit).
    The topmost faces, a rim or a water surface, must face up."""
    me = ob.data
    top = max(p.center.z for p in me.polygons)
    if sum(p.normal.z for p in me.polygons if p.center.z > top - 1e-4) < 0:
        me.flip_normals()


def glass_of_water(name, loc):
    """A drinking glass of clear water standing at `loc`: the glass and the water as two lathes, neither casting
    a shadow (no caustics: the light goes through as a photographer expects). A shot through it needs 14 glossy
    bounces, not Cycles's 4: a refraction counts as a glossy bounce."""
    glass = A.lathe(name, [(0.0, 0.004), (0.026, 0.004), (0.029, 0.095), (0.031, 0.095), (0.0285, 0.0), (0.0, 0.0)],
                    mats=[A.clear_glass()])
    glass.location = loc
    wm = A._principled(f"{name}_water", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                           "IOR": 1.33})[0]
    water = A.lathe(f"{name}_water", [(0.0, 0.0045), (0.0257, 0.0045), (0.0272, 0.065), (0.0, 0.065)], mats=[wm])
    water.location = loc
    outward(glass)
    outward(water)
    glass.visible_shadow = water.visible_shadow = False
    return glass, water


# ---------------------------------------------------------------- cracks of light

class Crack:
    """A crack as the shots see it: `crack["reveal"] = v` (0..1) sets how much of it shows, through the Value node
    in its own material. (It was an object property read by an Attribute node, and under persistent render data a
    property changed between frames is never re-read: in seven passes no crack ever showed.)"""

    def __init__(self, ob, reveal):
        self.ob, self.reveal = ob, reveal

    def __getitem__(self, key):
        return self.reveal.default_value

    def __setitem__(self, key, v):
        cyc.put(self.reveal, v)


def crack_material(name, glow=GLOW):
    """A crack's own material: across its width (UV y) a hair of near-white light at the core and a faint rose halo
    fading to the ribbon's edge, shown where UV x is below its reveal value, transparent beyond it. (The whole
    ribbon in one rose at 2.5, with hard edges, was a neon tube from 8 m: light through a crack is a thin bright
    line that blooms, not a stroke.)"""
    mat, nt, out = P.nodes(f"crack_{name}")
    g = kit.G(nt)
    uv = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(uv.outputs["UV"], sep.inputs[0])
    reveal = kit.value(nt, 0.0)
    show = g.math("LESS_THAN", sep.outputs["X"], reveal)
    edge = g.math("ABSOLUTE", g.math("SUBTRACT", g.math("MULTIPLY", sep.outputs["Y"], 2.0), 1.0))   # 0 core, 1 edge
    across = g.math("SUBTRACT", 1.0, edge)
    core = g.math("POWER", across, 6.0)
    halo = g.math("POWER", across, 1.5)
    em = g.node("ShaderNodeEmission")
    g.link(kit._mix_rgba(nt, core, m.srgb(glow), (1.0, 0.94, 0.96, 1.0)), em.inputs["Color"])
    g.link(g.math("ADD", g.math("MULTIPLY", halo, 0.4), g.math("MULTIPLY", core, 3.0)), em.inputs["Strength"])
    alpha = g.math("ADD", g.math("MULTIPLY", halo, 0.7), core, clamp=True)
    mix = g.node("ShaderNodeMixShader")
    g.link(g.math("MULTIPLY", show, alpha), mix.inputs["Fac"])
    g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    g.link(em.outputs[0], mix.inputs[2])
    g.link(mix.outputs[0], out.inputs["Surface"])
    return mat, reveal


def crack(name, seed, origin, ax, ay, length, width=0.008, parent=None, glow=GLOW):
    """A crack of light: a jagged ribbon from `origin` in the plane of ax, ay, mostly straight with three sharp
    kinks and two short branches leaving at 15-30 degrees, thinning to its tip. Its UV x runs along it (a branch's
    from where it leaves the main line); `width` is the whole ribbon's, the light a core a tenth of it and a halo
    over the inner third, so choose it so the core is about a pixel from the shot's distance. Returns the Crack.
    (A walk turning up to 45 degrees a step, at one width and an emission of 8, was a neon squiggle.)"""
    r = random.Random(seed)
    n, a = 26, r.uniform(-0.5, 0.5)
    kinks = set(r.sample(range(4, n - 3), 3))
    pts = [Vector((0.0, 0.0))]
    for i in range(n):
        a += r.uniform(-0.22, 0.22) + (r.choice((-1, 1)) * r.uniform(0.5, 0.9) if i in kinks else 0.0)
        pts.append(pts[-1] + Vector((math.cos(a), math.sin(a))) * length / n)
    lines = [(pts, 0.0, 1.0, 1.0)]                   # points, uv x where it starts, uv x it spans, width scale
    for i in sorted(r.sample(range(5, n - 6), 2)):   # the branches, off the main line at a shallow angle (at 35-60
        d = pts[i + 1] - pts[i]                        # degrees, with a flat rose ribbon, the crack was lightning)
        b = math.atan2(d.y, d.x) + r.choice((-1, 1)) * r.uniform(0.25, 0.55)
        q = [pts[i]]
        for _ in range(r.randint(5, 8)):
            b += r.uniform(-0.2, 0.2)
            q.append(q[-1] + Vector((math.cos(b), math.sin(b))) * 0.6 * length / n)
        lines.append((q, i / n, 0.2, 0.55))
    verts, uvs, faces = [], [], []
    o, ax, ay = Vector(origin), Vector(ax), Vector(ay)
    for q, u0, du, ws in lines:
        k0, last = len(verts), len(q) - 1
        for i, p in enumerate(q):
            d = (q[min(i + 1, last)] - q[max(i - 1, 0)]).normalized()
            side = Vector((-d.y, d.x)) * width * ws * (1.0 - 0.7 * i / last) * r.uniform(0.6, 1.4) / 2
            for s in (-1, 1):
                pq = p + side * s
                verts.append(o + ax * pq.x + ay * pq.y)
                uvs.append((u0 + du * i / last, (s + 1) / 2))
        faces += [(k0 + 2 * i, k0 + 2 * i + 1, k0 + 2 * i + 3, k0 + 2 * i + 2) for i in range(last)]
    mat, reveal = crack_material(name, glow)
    ob = mesh(name, verts, faces, uvs, [mat])
    if parent is not None:
        ob.parent = parent
    return Crack(ob, reveal)


# ---------------------------------------------------------------- rain

def rain(color="#D4E0F2", mix=0.14, seed=5, n=3200, clear=0.8):
    """D5: rain, a block of fine streaks (crossed, so they read from any side) leaning with the wind along +X, most
    of them hair-thin and a few heavier, 14 x 14 x 16 m round its axis, that falls through itself when a shot moves
    it down. None within `clear` metres of the axis, where the camera rides. Returns (the block, its emission node).
    (At 2.5 mm and a brighter emission they were white matchsticks over her face; at a mix of 0.22 the near ones
    were still white sticks in the night shots; the streaks within arm's reach were white rods the height of the
    frame.)"""
    r = random.Random(seed)
    verts, faces = [], []
    for i in range(n):
        x, y, z = r.uniform(-7, 7), r.uniform(-7, 7), r.uniform(0, 16)
        if x * x + y * y < clear ** 2:
            continue
        ln, w = r.uniform(0.3, 0.7), r.uniform(0.0006, 0.0016)
        lx, ly = 0.07 * ln + r.uniform(-0.01, 0.01), 0.03 * ln + r.uniform(-0.01, 0.01)   # the wind, along +X
        for dx, dy in ((w, 0), (0, w)):
            k = len(verts)
            verts += [(x - dx, y - dy, z), (x + dx, y + dy, z), (x + dx + lx, y + dy + ly, z + ln),
                      (x - dx + lx, y - dy + ly, z + ln)]
            faces.append((k, k + 1, k + 2, k + 3))
    mat, nt, out = P.nodes("rain")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb(color)
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = mix
    nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    ob = mesh("rain", verts, faces, mats=[mat])
    only_camera(ob)
    return ob, em


# ---------------------------------------------------------------- torn paper, dust

def confetti(printed, paper=PAPER, n=360, seed=11):
    """D5: torn paper, `n` scraps in one mesh whose corners are set per frame by scraps(): small torn quads, few of
    them big, two thirds bare paper and a third carrying a piece of the picture `printed` (a file). Returns (the
    mesh, the scraps' own numbers). (Even grey cards of one size read as cards, not as a picture torn up.)"""
    r = random.Random(seed)
    items = []
    for _ in range(n):
        w = 0.02 + 0.06 * r.random() ** 2
        items.append(dict(a=r.uniform(0, 2 * math.pi), rad=r.uniform(0.1, 1.0), h=r.uniform(-0.5, 0.5), w=w,
                          corners=[(sx * w * r.uniform(0.55, 1.0), sy * w * r.uniform(0.4, 0.85))
                                   for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))],
                          spin=Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))),
                          rate=r.uniform(2.0, 6.0), fall=r.uniform(0.6, 1.4), ph=r.uniform(0, 6.3)))
    bare = A._principled("scrap", **{"Base Color": m.srgb("#D8D1C4"), "Roughness": 0.8,
                                     "Emission Color": m.srgb(paper), "Emission Strength": 0.06})[0]
    inked, nt, out = P.nodes("scrap_printed")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(printed, check_existing=True)
    nt.links.new(nt.nodes.new("ShaderNodeTexCoord").outputs["UV"], tex.inputs["Vector"])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.8
    bsdf.inputs["Emission Strength"].default_value = 0.08
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    uvs = []
    for _ in range(n):                                                          # each printed scrap a piece of the picture
        u0, v0, su = r.uniform(0.05, 0.85), r.uniform(0.05, 0.85), r.uniform(0.04, 0.1)
        uvs += [(u0, v0), (u0 + su, v0), (u0 + su, v0 + 0.7 * su), (u0, v0 + 0.7 * su)]
    ob = mesh("confetti", [(0, 0, 0)] * (4 * n), [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)],
              uvs, mats=[bare, inked])
    for i, poly in enumerate(ob.data.polygons):
        poly.material_index = 1 if i % 3 == 0 else 0
    ob.visible_shadow = False
    return ob, items


def scraps(ob, items, center, t, radius=4.0, height=3.0, swirl=0.0, fall=0.0, n=None):
    """Place the scraps round `center`, turning by `swirl` and dropping to the water by `fall` (0..1); `n` of them,
    the rest put away under the floor."""
    ob.hide_render = False
    co = []
    for i, s in enumerate(items):
        if n is not None and i >= n:
            co.extend([center[0], center[1], -5.0] * 4)
            continue
        a = s["a"] + swirl * t * (1.3 - s["rad"])
        p = Vector((center[0] + math.cos(a) * s["rad"] * radius, center[1] + math.sin(a) * s["rad"] * radius,
                    center[2] + s["h"] * height))
        f = min(1.0, max(0.0, fall * s["fall"]))
        p.z = p.z + (0.012 - p.z) * f
        rot = Matrix.Rotation(s["rate"] * t * (1 - f) + s["ph"], 3, s["spin"].normalized()) if f < 1 else \
            Matrix.Rotation(s["ph"], 3, "Z")
        if f > 0.98:
            rot = Matrix.Rotation(s["ph"], 3, "Z")       # lying flat on the water
        for cx, cy in s["corners"]:
            co.extend(p + rot @ Vector((cx, cy, 0.0)))
    ob.data.vertices.foreach_set("co", co)
    ob.data.update()


def motes(n=320, seed=17, color="#FFF4E8"):
    """Dust in a beam of light: `n` specks in one mesh, drifting and sinking, placed by dust(). Returns (the mesh,
    the specks' own numbers)."""
    r = random.Random(seed)
    items = [dict(p=Vector((r.uniform(-0.9, -0.1), r.uniform(-1.3, 0.4), r.uniform(1.4, 4.4))), ph=r.uniform(0, 6.3),
                  v=r.uniform(0.03, 0.08), s=r.uniform(0.0015, 0.004)) for _ in range(n)]
    mat = emission_mat("mote", color, 1.2)[0]
    ob = mesh("motes", [(0, 0, 0)] * (4 * n), [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)],
              mats=[mat])
    only_camera(ob)
    return ob, items


def dust(ob, items, t, center=(2.0, 0.0, 0.0)):
    ob.hide_render = False
    co = []
    for mt in items:
        p = Vector(center) + mt["p"] + Vector((0.03 * math.sin(0.7 * t + mt["ph"]), 0.05 * math.sin(0.5 * t + 1.3 * mt["ph"]),
                                               3.0 - (mt["v"] * t + mt["ph"]) % 3.0))
        s = mt["s"]
        for dy, dz in ((-s, -s), (s, -s), (s, s), (-s, s)):
            co.extend(p + Vector((0.0, dy, dz)))
    ob.data.vertices.foreach_set("co", co)
    ob.data.update()


# ---------------------------------------------------------------- shards of glass

SHARD_KEYS = []                             # the picture each shard of the last shards() call carries


def shards(pictures, hero, sheet, grid=(8, 12), n=160, seed=13, home=((9.0, 27.0), (1.0, 6.5), (5.0, 10.5)),
           line=(24.0, 0.9)):
    """Windows burst into `n` shards hanging in the air, each with a piece of one of her pictures in its glass:
    `pictures` is {key: file} with the `hero` picture first; the grid's `cols x rows` pieces cut from the hero
    line up into it (a sheet of size `sheet`, standing at x `line[0]`, its foot at z `line[1]`) when a shot drives
    them there, the others fly off. Each shard: dict(ob, home, spin, ph, grid, away); `home` is the box they hang
    in. (Lit cards of picture were cards: the picture is faint and a quarter see-through, the glass is in the
    Fresnel reflection.)"""
    r = random.Random(seed)
    mats = {}
    for key, file in pictures.items():
        mat, nt, out = P.nodes(f"shard_{key}")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(file, check_existing=True)
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 0.7
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        inner = nt.nodes.new("ShaderNodeMixShader")
        inner.inputs["Fac"].default_value = 0.25
        nt.links.new(em.outputs[0], inner.inputs[1])
        nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], inner.inputs[2])
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.02
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lw.outputs["Fresnel"], mix.inputs["Fac"])
        nt.links.new(inner.outputs[0], mix.inputs[1])
        nt.links.new(gl.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        mats[key] = mat
    others = [k for k in mats if k != hero]
    out = []
    SHARD_KEYS.clear()
    cols, rows = grid
    W, Hh = sheet
    cw, ch = W / cols, Hh / rows
    (x0, x1), (y0, y1), (z0, z1) = home
    for k in range(n):
        mine = k < cols * rows
        key = hero if mine else r.choice(others)
        SHARD_KEYS.append(key)
        i, j = (k % cols, k // cols) if mine else (r.randrange(cols), r.randrange(rows))
        u0, u1, v0, v1 = i / cols, (i + 1) / cols, 1 - (j + 1) / rows, 1 - j / rows
        jit = [Vector((0, r.uniform(-0.15, 0.15) * cw, r.uniform(-0.15, 0.15) * ch)) for _ in range(4)]
        corners = [Vector((0, cw / 2, -ch / 2)), Vector((0, -cw / 2, -ch / 2)), Vector((0, -cw / 2, ch / 2)),
                   Vector((0, cw / 2, ch / 2))]
        verts = [c * 0.94 + (Vector() if mine else jit[q]) for q, c in enumerate(corners)]
        uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        ob = mesh(f"shard{k}", verts, [(0, 1, 2, 3)], uvs, [mats[key]])
        ob.rotation_mode = "QUATERNION"
        at = Vector((r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(z0, z1)))
        spin = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))).normalized()
        place = Vector((line[0], W / 2 - (i + 0.5) * cw, line[1] + Hh - (j + 0.5) * ch)) if mine else None
        out.append(dict(ob=ob, home=at, spin=spin, ph=r.uniform(0, 6.3), grid=place,
                        away=at + Vector((r.uniform(-6, 6), r.uniform(-4, 4), r.uniform(2, 6)))))
    return out


# ---------------------------------------------------------------- her hair off the paper

_PIX = {}


def pixels(path):
    """A picture's pixels as (H, W, 4) floats as stored (sRGB), rows from the bottom: read from a copy of the
    image, so the print's own texture keeps its colour space."""
    if path not in _PIX:
        img = bpy.data.images.load(path)
        w, h = img.size
        _PIX[path] = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
        bpy.data.images.remove(img)
    return _PIX[path]


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hair_mat(rgb, mats):
    """A strand's material: the picture's colour where it roots, a little darker (a thin hair against the light),
    quantised so a few materials (kept in `mats`) serve every strand of every print."""
    key = tuple(round(float(c) * 0.85 * 12) / 12 for c in rgb)
    if key not in mats:
        mats[key] = A._principled(f"hair_{len(mats)}", **{
            "Base Color": tuple(_lin(c) for c in key) + (1.0,), "Roughness": 0.5})[0]
    return mats[key]


def strands(p, name, n=36, seed=0, mats=None):
    """Her hair lifting off the paper: thin 3D strands rooted on the relief along the hair's edge (from the parts
    map), each the picture's colour where it roots, following the hair's own flow (the mask's long axis, pointed
    away from her face), a little out from the head and a little off the paper, swaying in the air (sway(), per
    frame). The 3D inside the picture's dimensional part; a child of the print, so it goes where the print goes.
    Returns dict(ob, parent, items) or None when the picture gives no roots. `mats` is the shared hair_mat cache.
    (Strands pointing out from the head were whiskers; strands that simply hung were right on the portraits and
    wrong on everyone running, leaping or lying down; black strands were scratches on a dark print; roots on the
    mask's strays were strands loose in her sky.)"""
    mats = {} if mats is None else mats
    parts = H.load(H.map_path(name, "parts"))
    mk, face = parts[..., 0] > 0.5, parts[..., 1] > 0.5
    if not mk.any():
        return None
    h, w = mk.shape
    W, Hh = P.size_of(p)
    inner, near_face = mk.copy(), face.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
        inner &= np.roll(mk, (dy, dx), axis=(0, 1))
        near_face |= np.roll(face, (dy, dx), axis=(0, 1))
    ys, xs = np.nonzero(mk & ~inner & ~near_face)                              # the hair's outer edge, not along her face
    if len(xs) < 8:
        return None
    my, mx = np.nonzero(mk)
    cu_, cv_ = (mx.mean() + 0.5) / w, (my.mean() + 0.5) / h
    # the hair's flow: the mask's long axis, pointing away from her face (down on an upright portrait, back on a
    # running figure, along the pillow on a sleeping one)
    pts = np.stack([(mx + 0.5) / w * W, (my + 0.5) / h * Hh], axis=1)
    axis = np.linalg.eigh(np.cov(pts.T))[1][:, -1]
    fy, fx = np.nonzero(face)
    face_c = np.array([(fx.mean() + 0.5) / w * W, (fy.mean() + 0.5) / h * Hh]) if len(fx) else \
        np.array([cu_ * W, cv_ * Hh + 0.3 * Hh])
    proj = pts @ axis                                   # the tips are the end of the axis farther from her face
    if abs(np.percentile(proj, 95) - face_c @ axis) < abs(face_c @ axis - np.percentile(proj, 5)):
        axis = -axis                                    # (the mask's centroid against her face was wrong on a
    #                                                     portrait whose hair frames the face: strands went up)
    flow = Vector((0.0, -float(axis[0]), float(axis[1])))                     # the picture's right is the sheet's -Y
    pix = pixels(P.path(name))
    ph, pw = pix.shape[:2]
    r = random.Random(seed)
    k = W / P.SHEET_H
    inv = p.matrix_world.inverted()
    cu = bpy.data.curves.new(f"{p.name}_hair", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution, cu.fill_mode = "3D", 0.0022 * k, 2, "FULL"
    items, roots = [], []
    order = list(range(len(xs)))
    r.shuffle(order)
    for i in order:
        if len(items) >= n:
            break
        pu, pv = (xs[i] + 0.5) / w, (ys[i] + 0.5) / h
        if any(abs(pu - a) < 0.025 and abs(pv - b) < 0.025 for a, b in roots):  # along the edge, not in tufts
            continue
        dy, dz = -(pu - cu_) * W, (pv - cv_) * Hh
        norm = math.hypot(dy, dz)
        if norm < 1e-3:
            continue
        ny, nz = dy / norm, dz / norm
        if nz > 0.55 and flow.z < -0.5 and r.random() < 0.6:                  # few on the crown of a portrait
            continue
        iy, ix = min(ph - 2, max(1, int(pv * ph))), min(pw - 2, max(1, int(pu * pw)))
        rgb = pix[iy - 1:iy + 2, ix - 1:ix + 2, :3].mean(axis=(0, 1))
        if 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 0.5:               # not hair where the picture is light:
            continue                                                            # the mask's strays in her sky
        y, x, e = ys[i], xs[i], max(4, w // 25)                                 # nor on a painted flyaway out in the
        if mk[max(0, y - e):y + e + 1, max(0, x - e):x + e + 1].mean() < 0.3:    # sky: the edge of the hair's bulk
            continue
        roots.append((pu, pv))
        # with the flow, a little out from the head and a little off the paper, each its own way
        d = (0.65 * flow + 0.35 * Vector((0.0, ny, nz))
             + Vector((-0.1, r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15)))).normalized()
        L, droop = r.uniform(0.08, 0.28) * k, 0.15
        mat = hair_mat(rgb, mats)
        if cu.materials.find(mat.name) < 0:
            cu.materials.append(mat)
        sp = cu.splines.new("NURBS")
        sp.points.add(5)
        sp.order_u, sp.use_endpoint_u = 4, True
        sp.material_index = cu.materials.find(mat.name)
        for j, pt in enumerate(sp.points):
            pt.radius = 1.0 - 0.85 * j / 5                                      # fine at the tip
        items.append(dict(sp=sp, root=inv @ H.picture_point(p, name, pu, pv, lift=0.004), d=d, L=L, droop=droop,
                          ph=r.uniform(0, 6.3), w=r.uniform(0.6, 1.4)))
    if not items:
        return None
    ob = bpy.data.objects.new(cu.name, cu)
    m._link(ob)
    ob.parent = p
    return dict(ob=ob, parent=p, items=items)


def sway(strands_, t):
    """The strands in the air: each bends with its own slow wave and droops towards its tip; hidden with its print."""
    for st in strands_:
        for it in st["items"]:
            root, d, L = it["root"], it["d"], it["L"]
            a = 0.25 * math.sin(it["w"] * t + it["ph"])
            for j, pt in enumerate(it["sp"].points):
                s = j / 5
                q = root + d * (L * s) + Vector((0.0, a * L * s * s, -it["droop"] * L * s * s))
                pt.co = (q.x, q.y, q.z, 1.0)
        hidden = st["parent"].hide_render
        if st["ob"].hide_render != hidden:
            st["ob"].hide_render = hidden


# ---------------------------------------------------------------- a print in two halves, letters cut out of one

def halves(p):
    """A print in two halves (left and right of the image), each hinged at its outer clip, for tearing (D6).
    Returns [(half, side)], side +1 the image's left half, on +Y."""
    out = []
    W = P.size_of(p)[0]
    for side in (1, -1):
        me = p.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        uv = bm.loops.layers.uv.active
        kill = [f for f in bm.faces if (sum(lp[uv].uv.x for lp in f.loops) / len(f.loops) < 0.5) != (side == 1)]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, -side * W / 2, 0))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"{p.name}_half{side:+d}", me)
        m._link(ob)
        ob.location = p.location + Vector((0, side * W / 2, 0))
        out.append((ob, side))
    return out


def cut_letters(sheet, font, items, height=0.72, glow=None, radius=0.42, offsets=(-0.22, 0.0, 0.22), x=-0.04,
                at=0.0, extrude=0.25):
    """D1: letters cut out of a print (or a wall), so the light behind it shows through: `items` are (character,
    y, z) in the sheet's own frame (its origin the middle of its top edge; y along the sheet, z down), each glyph
    sized to `height` metres, `extrude` deep each way about x = `at` (half a wall's thickness for a wall) and cut
    with a boolean; and behind each, a stack of small lamp discs of the `glow` material at x (hidden until a shot
    shows them: the back cover). Returns the lamps, [] when the font cannot be loaded. (At an offset of 0.16 the
    discs showed as three bright bands; at 6 the letters were a neon sign.)"""
    try:
        font = bpy.data.fonts.load(font, check_existing=True)
    except RuntimeError as e:
        print("no font for the letters:", e)
        return []
    # the glyph's right along -Y and its up along +Z, as seen from the front of the print (from -X)
    turn = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    lamps = []
    for k, (ch, y, z) in enumerate(items):
        cu = bpy.data.curves.new(f"letter{k}", "FONT")
        cu.body, cu.font, cu.size, cu.extrude = ch, font, 1.0, extrude
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        tmp = bpy.data.objects.new(cu.name, cu)
        m._link(tmp)
        tmp.matrix_world = sheet.matrix_world @ Matrix.Translation((at, y, z)) @ turn
        for _ in range(2):                           # the glyph's height depends on the font: measure, then size it
            bpy.context.view_layer.update()
            me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            ys = [v.co.y for v in me.vertices]
            if abs(max(ys) - min(ys) - height) < 0.02:
                break
            cu.size *= height / (max(ys) - min(ys))
            bpy.data.meshes.remove(me)
        cutter = bpy.data.objects.new(f"cut{k}", me)
        m._link(cutter)
        cutter.matrix_world = tmp.matrix_world
        bpy.data.objects.remove(tmp)
        cutter.parent = sheet
        cutter.matrix_parent_inverse = sheet.matrix_world.inverted()
        cutter.hide_render = True
        cutter.display_type = "WIRE"
        mod = sheet.modifiers.new(f"cut{k}", "BOOLEAN")
        mod.operation, mod.object = "DIFFERENCE", cutter
        try:
            mod.solver = "EXACT"
            mod.use_hole_tolerant = True
        except (TypeError, AttributeError):
            pass
        for dz in offsets:
            bpy.ops.mesh.primitive_circle_add(radius=radius, fill_type="NGON", vertices=24)
            lamp = bpy.context.active_object
            if glow is not None:
                lamp.data.materials.append(glow)
            lamp.parent = sheet
            lamp.location = (x, y, z + dz)
            lamp.rotation_euler = (0.0, math.pi / 2, 0.0)
            lamps.append(lamp)
    return lamps
