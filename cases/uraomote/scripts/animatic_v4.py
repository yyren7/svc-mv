"""v4 animatic in 3D: section 5 of script_v4.md shot by shot in the drying hall of v4_hall.py, cut on the song's
downbeats, rendered in Cycles at low resolution and sample count to judge the pacing, the cameras and the dimension
events before the real render. The 3D shots carry the script's effects in the scene itself: the ceiling lamps
lighting the KV on the downbeats, KV' showing through it, 表 and 裏 cut out of it, prints turning, lifting, wet and
torn, pulse ripples on the water, rose ink as a volume, rain, cracks, shards of glass, the walls falling away to the
painted sky, flying paper, the line-art flash (D4), the roll, the dolly zoom and the Dutch angle. The 2D shots are
her illustrations on a card filling the frame (section 3.1).

    blender -b --factory-startup -P cases/uraomote/scripts/animatic_v4.py -- <frames_dir> [first_bar last_bar]
    env: FPS=12 SAMPLES=16 WIDTH=640, LIMIT=1 (the first frame of every shot), AT=0.5 (that point of every shot),
         ONLY=P4,P5 (those sections), DEVICE=CPU (render on the CPU), DRY=1 (run the shots, render nothing)
    python cases/uraomote/scripts/animatic_cut.py <frames_dir> cases/uraomote/audio/urao_mix.m4a <out.mp4> 12

Frames are numbered on the song's clock and frames already there are skipped, so bar ranges can run side by side
into one folder. Every frame starts from the hall at rest with every light off (reset()), and the shot sets what it
needs, so any frame can be rendered alone. Pictures not drawn yet: Q2 is U2 on the back of Q1's print, U3 is staged
with the reflection trick of P7.3, R1-R6 are missing (the run has only its ripples and the prints it tears).
"""
import bisect
import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case as C  # noqa: E402
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FRAMES = os.path.abspath(ARGV[0]) if ARGV else os.path.join(C.RENDERS, "animatic_v4", "frames")
FIRST, LAST = (float(ARGV[1]), float(ARGV[2])) if len(ARGV) > 2 else (None, None)
import assets as A  # noqa: E402
import cyc  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import v4_hall as V  # noqa: E402
import v4_hybrid as H  # noqa: E402

FPS = int(os.environ.get("FPS", 12))
SAMPLES = int(os.environ.get("SAMPLES", 16))
WIDTH = int(os.environ.get("WIDTH", 640))
LIMIT = int(os.environ.get("LIMIT", 0))
AT = [float(a) for a in os.environ.get("AT", "").split(",") if a]
ONLY = [s for s in os.environ.get("ONLY", "").split(",") if s]
DRY = os.environ.get("DRY") == "1"                  # run every shot without rendering, and save the .blend
TIMING = json.load(open(os.path.join(C.AUDIO, "urao_timing.json"), encoding="utf-8"))
DOWN, BEATS, DURATION = TIMING["downbeats"], TIMING["beats"], TIMING["duration"]
LAST_BEAT = DURATION - (BEATS[-1] - BEATS[-2])     # the beats found stop at bar 116; the song rings on
FONT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
ROSE, GLOW, PAPER, MORNING = "#F0285A", "#FF5C8A", "#F2F0EB", "#BCD3E6"
PICK = {"kv": "v4_kv_211", "kvu": "v4_kvu_211_n75"}  # every other picture: seed 211 until picked
CARDS = ["kv", "kvu", "a5", "q1", "c1", "c2", "c3", "c4", "w2", "u1", "u2", "u4", "r0", "f1", "f2", "s1", "s2", "s3"]
PUNCH = [(35, 47), (51, 55), (87, 116)]              # bars with the impact push on every beat (2.1)
DUTCH = (87, 99)                                     # bars with the Dutch angle, ±12° turning each bar
HOLE = Vector((2.0, 0.78, 3.95))                     # 表 cut out of the KV
FLOAT_C = Vector((31.9, -4.0, 0.0))                  # the print lying on the water (P1.5)
# the props of single shots stand beyond the last row, clear of the two top-down shots (x 29.8-34.1)
QC = Vector((33.5, 0.0, 2.9))                        # Q1 / Q2's print (P3); the far wall is at x 40, and the
#                                                      camera inside its back picture stands 4 m behind it
W1C = Vector((35.5, 5.0, 2.1))                       # her cardboard in the rain (P6)
C1C = Vector((29.0, -1.6, 2.6))                      # C1's print, its ink running off into the water (P5.1)
REFL = Vector((38.0, -5.0, 0.0))                     # a 表 print whose reflection is her 裏 (P7.3, U3)
PATH = ["print_1_+1.6", "print_2_+0.0", "print_3_+1.6", "print_4_+0.0", "print_5_+1.6", "print_6_+0.0"]
# the pictures of the 2D shots hang as hybrid prints (wide ones on their side) behind the cameras' usual places,
# before row 0: a shot goes into one (into()) instead of putting a card before the lens. The water picture in the
# hall proper, to mirror it
STAGE = {"u1": (-7.0, -4.4), "f1": (-7.0, 0.0), "w2": (-7.0, 4.4),
         "u4": (-10.0, -4.4), "c2": (-10.0, 0.0), "c3": (-10.0, 4.4),
         "c4": (-13.0, -4.4), "r0": (-13.0, 0.0), "f2": (-13.0, 4.4)}
STAGE_BACKS = {"u1": "a1", "f1": "f2", "f2": "f1", "w2": "w1", "u4": "u2", "c2": "c3", "c3": "c2", "c4": "c1",
               "r0": "kvu"}


class S:
    """What the shots move, filled in by setup(); t and b are the frame's time and bar."""
    t = b = 0.0


# ---------------------------------------------------------------- the song's clock (as in animatic.py)

def at(bar):
    """Seconds at a bar (a downbeat index; fractions fall between downbeats, bars below 0 in the pickup)."""
    i = max(0, min(math.floor(bar), len(DOWN) - 2))
    return max(0.0, DOWN[i] + (bar - i) * (DOWN[i + 1] - DOWN[i]))


def bar_at(t):
    i = max(0, min(bisect.bisect_right(DOWN, t) - 1, len(DOWN) - 2))
    return i + (t - DOWN[i]) / (DOWN[i + 1] - DOWN[i])


def punch(t, amount, decay=0.12):
    i = bisect.bisect_right(BEATS, t) - 1
    return amount * math.exp(-(t - BEATS[i]) / decay) if i >= 0 else 0.0


def last_beat(t):
    return BEATS[max(0, bisect.bisect_right(BEATS, t) - 1)]


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def clamp(u):
    return min(1.0, max(0.0, u))


# ---------------------------------------------------------------- building

def _pic(key):
    return PICK.get(key, f"v4_{key}_211")


def _path(key):
    return os.path.join(V.ART, _pic(key) + "_00001_.png")


def _value(nt, v=0.0):
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


def _emission_mat(name, hexstr, strength):
    mat, nt, out = V._nodes(name)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb(hexstr)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat, em


def _only_camera(ob):
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter",
                 "visible_shadow"):
        setattr(ob, attr, False)


def _mesh(name, verts, faces, uvs=None, mats=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs is not None:
        layer = me.uv_layers.new(name="UV")
        for poly in me.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uvs[me.loops[li].vertex_index]
    return A._obj(name, me, mats)


def sky_images(h):
    """D2: the painted skies (S1-S3) on the backdrop behind the high windows, swapped per shot."""
    em = h["sky_emission"]
    nt = em.id_data
    g = kit.G(nt)
    tc = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(tc.outputs["Generated"], sep.inputs[0])
    comb = g.node("ShaderNodeCombineXYZ")
    g.link(sep.outputs["X"], comb.inputs["X"])
    g.link(sep.outputs["Z"], comb.inputs["Y"])
    mp = g.node("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 4.0, 1.0)          # a picture every 16 m, 7.5 m high round the windows
    mp.inputs["Location"].default_value = (0.0, -1.33, 0.0)
    g.link(comb.outputs[0], mp.inputs["Vector"])
    tex = g.node("ShaderNodeTexImage")
    tex.extension = "MIRROR"
    g.link(mp.outputs[0], tex.inputs["Vector"])
    g.link(tex.outputs["Color"], em.inputs["Color"])
    S.sky_tex, S.sky_em = tex, em


def water_ripple():
    """The pulse on the water (script 0.3: ドクン is a ring on the water): one ring at a time, its centre, radius and
    height set per frame, on top of the water's own ripples."""
    nt = S.water.node_tree
    g = kit.G(nt)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    old = next(n for n in nt.nodes if n.type == "BUMP")
    geo = g.node("ShaderNodeNewGeometry")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(geo.outputs["Position"], sep.inputs[0])
    S.rip = {k: _value(nt) for k in ("x", "y", "r", "a")}
    dx = g.math("SUBTRACT", sep.outputs["X"], S.rip["x"])
    dy = g.math("SUBTRACT", sep.outputs["Y"], S.rip["y"])
    e = g.math("SUBTRACT", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy))),
               S.rip["r"])
    wave = g.math("SINE", g.math("MULTIPLY", e, 2 * math.pi / 0.3))
    env = g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", e, e), -1 / 0.2 ** 2))
    bp = g.node("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 1.0
    bp.inputs["Distance"].default_value = 0.04
    g.link(g.math("MULTIPLY", g.math("MULTIPLY", wave, env), S.rip["a"]), bp.inputs["Height"])
    g.link(old.outputs["Normal"], bp.inputs["Normal"])
    g.link(bp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Emission Color"].default_value = m.srgb(ROSE)
    S.water_glow = bsdf.inputs["Emission Strength"]


def ink_volume(name, seed):
    """Rose ink in water: noise inside a sphere, thinning to its edge and glowing a little. Its density, glow and
    swirl (the noise's W) are set per frame."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
    ob = bpy.context.active_object
    ob.name = name
    mat, nt, out = V._nodes(name)
    g = kit.G(nt)
    tc = g.node("ShaderNodeTexCoord")
    nz = g.node("ShaderNodeTexNoise", {"Scale": 2.4, "Detail": 6.0, "Distortion": 0.8}, noise_dimensions="4D")
    g.link(tc.outputs["Object"], nz.inputs["Vector"])
    w = _value(nt, seed)
    g.link(w, nz.inputs["W"])
    fall = g.math("SUBTRACT", 1.0, g.vmath("LENGTH", tc.outputs["Object"]), clamp=True)
    dens = g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", nz.outputs["Fac"], 0.42, clamp=True), 12.0), fall)
    k, glow = _value(nt), _value(nt)
    vol = g.node("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = m.srgb("#8C2446")                 # ink scatters dark, it is not a lamp
    vol.inputs["Absorption Color"].default_value = m.srgb("#5A1030")
    vol.inputs["Emission Color"].default_value = m.srgb(GLOW)
    g.link(g.math("MULTIPLY", dens, k), vol.inputs["Density"])
    g.link(g.math("MULTIPLY", dens, glow), vol.inputs["Emission Strength"])
    g.link(vol.outputs[0], out.inputs["Volume"])
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return dict(ob=ob, w=w, seed=seed, density=k, glow=glow)


def sill_glass():
    """M1 (script 6): a glass of clear water on the sill of a high window, for the first drop of ink."""
    x, y = 7.0, V.WD / 2                            # on the sill the hall gives every window
    glass = A.lathe("glass", [(0.0, 0.004), (0.026, 0.004), (0.029, 0.095), (0.031, 0.095), (0.0285, 0.0), (0.0, 0.0)],
                    mats=[A.clear_glass()])
    glass.location = (x - 0.4, y - 0.2, 6.0)
    wm = A._principled("glass_water", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                         "IOR": 1.33})[0]
    water = A.lathe("glass_water", [(0.0, 0.0045), (0.0257, 0.0045), (0.0272, 0.065), (0.0, 0.065)], mats=[wm])
    water.location = (x - 0.4, y - 0.2, 6.0)
    glass.visible_shadow = water.visible_shadow = False   # no caustics here: the light goes through as a photographer expects
    S.glass_at = Vector((x - 0.4, y - 0.2, 6.0))
    S.glass_ink = ink_volume("glass_ink", 3.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0035, segments=16, ring_count=8)
    S.drop = bpy.context.active_object
    S.drop.data.materials.append(_emission_mat("drop", ROSE, 3.0)[0])


def crack(name, seed, origin, ax, ay, length, width=0.008, parent=None):
    """A rose crack: a jagged ribbon from `origin` in the plane of ax, ay. Its UV x runs along it, and the object's
    'reveal' (0..1) is how much of it shows."""
    r = random.Random(seed)
    n, a = 26, r.uniform(-0.5, 0.5)
    pts = [Vector((0.0, 0.0))]
    for _ in range(n):
        a += r.uniform(-0.75, 0.75)
        pts.append(pts[-1] + Vector((math.cos(a), math.sin(a))) * length / n)
    verts, uvs = [], []
    o, ax, ay = Vector(origin), Vector(ax), Vector(ay)
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        side = Vector((-d.y, d.x)) * width * r.uniform(0.5, 1.5) / 2
        for s in (-1, 1):
            q = p + side * s
            verts.append(o + ax * q.x + ay * q.y)
            uvs.append((i / n, (s + 1) / 2))
    ob = _mesh(name, verts, [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(n)], uvs, [S.crack_mat])
    if parent is not None:
        ob.parent = parent
    ob["reveal"] = 0.0
    S.cracks[name] = ob
    return ob


def crack_material():
    mat, nt, out = V._nodes("crack")
    g = kit.G(nt)
    uv = g.node("ShaderNodeTexCoord")
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(uv.outputs["UV"], sep.inputs[0])
    attr = g.node("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="reveal")
    show = g.math("LESS_THAN", sep.outputs["X"], attr.outputs["Fac"])
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb(GLOW)
    em.inputs["Strength"].default_value = 8.0
    mix = g.node("ShaderNodeMixShader")
    g.link(show, mix.inputs["Fac"])
    g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    g.link(em.outputs[0], mix.inputs[2])
    g.link(mix.outputs[0], out.inputs["Surface"])
    S.crack_mat = mat


def rain():
    """D5: rain, a block of thin streaks (crossed, so they read from any side) that falls through itself."""
    r = random.Random(5)
    verts, faces = [], []
    for i in range(2200):
        x, y, z = r.uniform(-7, 7), r.uniform(-7, 7), r.uniform(0, 16)
        ln, w = r.uniform(0.25, 0.45), 0.0025
        for dx, dy in ((w, 0), (0, w)):
            k = len(verts)
            verts += [(x - dx, y - dy, z), (x + dx, y + dy, z), (x + dx, y + dy, z + ln), (x - dx, y - dy, z + ln)]
            faces.append((k, k + 1, k + 2, k + 3))
    mat, nt, out = V._nodes("rain")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb("#DCE6F5")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.35
    nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    S.rain = _mesh("rain", verts, faces, mats=[mat])
    _only_camera(S.rain)
    S.rain_em = em


def confetti():
    """D5: torn paper, 360 scraps in one mesh whose corners are set per frame by scraps()."""
    n = 360
    r = random.Random(11)
    S.scrap = [dict(a=r.uniform(0, 2 * math.pi), rad=r.uniform(0.1, 1.0), h=r.uniform(-0.5, 0.5),
                    w=r.uniform(0.04, 0.09), spin=Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))),
                    rate=r.uniform(2.0, 6.0), fall=r.uniform(0.6, 1.4), ph=r.uniform(0, 6.3)) for _ in range(n)]
    mat, b = A._principled("scrap", **{"Base Color": m.srgb("#D8D1C4"), "Roughness": 0.8,
                                       "Emission Color": m.srgb(PAPER), "Emission Strength": 0.06})
    S.conf = _mesh("confetti", [(0, 0, 0)] * (4 * n), [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)],
                   mats=[mat])
    S.conf.visible_shadow = False


def motes():
    """Dust in the light before the KV (P0): 320 specks in one mesh, drifting and sinking, placed by dust()."""
    n = 320
    r = random.Random(17)
    S.mote = [dict(p=Vector((r.uniform(-0.9, -0.1), r.uniform(-1.3, 0.4), r.uniform(1.4, 4.4))), ph=r.uniform(0, 6.3),
                   v=r.uniform(0.03, 0.08), s=r.uniform(0.0015, 0.004)) for _ in range(n)]
    mat = _emission_mat("mote", "#FFF4E8", 1.2)[0]
    S.dust = _mesh("motes", [(0, 0, 0)] * (4 * n), [(4 * i, 4 * i + 1, 4 * i + 2, 4 * i + 3) for i in range(n)],
                   mats=[mat])
    _only_camera(S.dust)


def dust(t, center=(2.0, 0.0, 0.0)):
    S.dust.hide_render = False
    co = []
    for mt in S.mote:
        p = Vector(center) + mt["p"] + Vector((0.03 * math.sin(0.7 * t + mt["ph"]), 0.05 * math.sin(0.5 * t + 1.3 * mt["ph"]),
                                               3.0 - (mt["v"] * t + mt["ph"]) % 3.0))
        s = mt["s"]
        for dy, dz in ((-s, -s), (s, -s), (s, s), (-s, s)):
            co.extend(p + Vector((0.0, dy, dz)))
    S.dust.data.vertices.foreach_set("co", co)
    S.dust.data.update()


def scraps(center, t, radius=4.0, height=3.0, swirl=0.0, fall=0.0, n=None):
    """Place the scraps round `center`, turning by `swirl` and dropping to the water by `fall` (0..1); `n` of them,
    the rest put away under the floor."""
    S.conf.hide_render = False
    co = []
    for i, s in enumerate(S.scrap):
        if n is not None and i >= n:
            co.extend([center[0], center[1], -5.0] * 4)
            continue
        a = s["a"] + swirl * t * (1.3 - s["rad"])
        p = Vector((center[0] + math.cos(a) * s["rad"] * radius, center[1] + math.sin(a) * s["rad"] * radius,
                    center[2] + s["h"] * height))
        f = clamp(fall * s["fall"])
        p.z = p.z + (0.012 - p.z) * f
        rot = Matrix.Rotation(s["rate"] * t * (1 - f) + s["ph"], 3, s["spin"].normalized()) if f < 1 else \
            Matrix.Rotation(s["ph"], 3, "Z")
        if f > 0.98:
            rot = Matrix.Rotation(s["ph"], 3, "Z")       # lying flat on the water
        w = s["w"]
        for cx, cy in ((-w, -0.7 * w), (w, -0.7 * w), (w, 0.7 * w), (-w, 0.7 * w)):
            co.extend(p + rot @ Vector((cx, cy, 0.0)))
    S.conf.data.vertices.foreach_set("co", co)
    S.conf.data.update()


def shards():
    """P8: the high windows burst into shards hanging in the air, each with a piece of one of her pictures; the
    8 x 12 cut from KV' line up into it on the last beat, the others fly off."""
    r = random.Random(13)
    mats = {}
    for key in ("kvu", "a1", "q1", "c1", "w2", "u1", "u2", "c3"):
        mat, nt, out = V._nodes(f"shard_{key}")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(_path(key), check_existing=True)
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 0.9
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.04
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = 0.7
        nt.links.new(gl.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        mats[key] = mat
    S.shards = []
    cols, rows = 8, 12
    cw, ch = V.SHEET_W / cols, V.SHEET_H / rows
    for k in range(160):
        mine = k < cols * rows
        key = "kvu" if mine else r.choice(list(mats)[1:])
        i, j = (k % cols, k // cols) if mine else (r.randrange(8), r.randrange(12))
        u0, u1, v0, v1 = i / cols, (i + 1) / cols, 1 - (j + 1) / rows, 1 - j / rows
        jit = [Vector((0, r.uniform(-0.15, 0.15) * cw, r.uniform(-0.15, 0.15) * ch)) for _ in range(4)]
        corners = [Vector((0, cw / 2, -ch / 2)), Vector((0, -cw / 2, -ch / 2)), Vector((0, -cw / 2, ch / 2)),
                   Vector((0, cw / 2, ch / 2))]
        verts = [c * 0.94 + (Vector() if mine else jit[q]) for q, c in enumerate(corners)]
        uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        ob = _mesh(f"shard{k}", verts, [(0, 1, 2, 3)], uvs, [mats[key]])
        ob.rotation_mode = "QUATERNION"
        home = Vector((r.uniform(9, 27), r.uniform(1.0, 6.5), r.uniform(5.0, 10.5)))
        spin = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))).normalized()
        grid = Vector((24.0, V.SHEET_W / 2 - (i + 0.5) * cw, 0.9 + V.SHEET_H - (j + 0.5) * ch)) if mine else None
        S.shards.append(dict(ob=ob, home=home, spin=spin, ph=r.uniform(0, 6.3), grid=grid,
                             away=home + Vector((r.uniform(-6, 6), r.uniform(-4, 4), r.uniform(2, 6)))))


def halves(p):
    """A print in two halves (left and right of the image), each hinged at its outer clip, for tearing (D6)."""
    out = []
    W = H.size_of(p)[0]
    for side in (1, -1):                       # +1: the image's left half, on +Y
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


def wall_panels(h):
    """The dark wall as 4 m panels of plaster, each hinged at its foot, so in P10 they can fall away outwards and
    show the painted sky (S3) behind."""
    dark = h["walls"][0]
    bpy.data.objects.remove(dark)
    S.panels = []
    for k in range(int((V.X1 - V.X0) / 4.0)):
        ob = A.rounded_box(f"panel{k}", (4.0, 0.4, V.H), 0.0, [S.plaster])
        ob.data.transform(Matrix.Translation((0, -0.2, V.H / 2)))
        ob.location = (V.X0 + 2.0 + 4.0 * k, -V.WD / 2, 0.0)
        S.panels.append(ob)
    mat, nt, out = V._nodes("sky3")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(_path("s3"), check_existing=True)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.0
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    S.sky3 = _mesh("sky3", [(-30, -18, -8), (70, -18, -8), (70, -18, 40), (-30, -18, 40)], [(0, 1, 2, 3)],
                   [(0, 0), (1, 0), (1, 1), (0, 1)], [mat])


def letters(kv):
    """D1: 表 and 裏 cut out of the KV down its left side, so the light behind it shows through; and the lamps
    under them for the back cover (P11)."""
    try:
        font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError as e:
        print("no font for the letters:", e)
        return
    # the glyph's right along -Y and its up along +Z, as seen from the front of the print (from -X)
    turn = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    S.letter_lamps = []
    glow = _emission_mat("letter_lamp", ROSE, 6.0)[0]
    for k, (ch, z) in enumerate((("表", -1.05), ("裏", -1.95))):
        cu = bpy.data.curves.new(f"letter{k}", "FONT")
        cu.body, cu.font, cu.size, cu.extrude = ch, font, 1.0, 0.25
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        tmp = bpy.data.objects.new(cu.name, cu)
        m._link(tmp)
        tmp.matrix_world = kv.matrix_world @ Matrix.Translation((0.0, 0.78, z)) @ turn
        for _ in range(2):                           # the glyph's height depends on the font: measure, then size it
            bpy.context.view_layer.update()
            me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            ys = [v.co.y for v in me.vertices]
            if abs(max(ys) - min(ys) - 0.72) < 0.02:
                break
            cu.size *= 0.72 / (max(ys) - min(ys))
            bpy.data.meshes.remove(me)
        cutter = bpy.data.objects.new(f"cut{k}", me)
        m._link(cutter)
        cutter.matrix_world = tmp.matrix_world
        bpy.data.objects.remove(tmp)
        cutter.parent = kv
        cutter.matrix_parent_inverse = kv.matrix_world.inverted()
        cutter.hide_render = True
        cutter.display_type = "WIRE"
        mod = kv.modifiers.new(f"cut{k}", "BOOLEAN")
        mod.operation, mod.object = "DIFFERENCE", cutter
        try:
            mod.solver = "EXACT"
            mod.use_hole_tolerant = True
        except (TypeError, AttributeError):
            pass
        for dz in (-0.22, 0.0, 0.22):
            bpy.ops.mesh.primitive_circle_add(radius=0.16, fill_type="NGON", vertices=24)
            lamp = bpy.context.active_object
            lamp.data.materials.append(glow)
            lamp.parent = kv
            lamp.location = (-0.04, 0.78, z + dz)
            lamp.rotation_euler = (0.0, math.pi / 2, 0.0)
            S.letter_lamps.append(lamp)


def board():
    """Her cardboard in the rain (P6): W1 on the front, plain paper with a pencilled number on the back."""
    mat, nt, out = V._nodes("board_w1")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    col = kit._mix_rgba(nt, geo.outputs["Backfacing"], V._picture(nt, "v4_w1_211"), m.srgb(PAPER))
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    nt.links.new(col, dif.inputs["Color"])
    nt.links.new(dif.outputs[0], out.inputs["Surface"])
    S.board = V.sheet("w1_board", W1C.x, W1C.y, mat, seed=93, top=V.SHEET_H + 0.02)
    cu = bpy.data.curves.new("pencil", "FONT")
    cu.body, cu.size = "No. 17", 0.13
    try:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError:
        pass
    num = bpy.data.objects.new("pencil", cu)
    m._link(num)
    cu.materials.append(A._principled("pencil", **{"Base Color": m.srgb("#5E5E66"), "Roughness": 0.9})[0])
    num.parent = S.board
    # seen from behind (+X): its right along +Y
    num.matrix_basis = Matrix.Translation((0.03, -0.9, -3.95)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0),
                                                                         (0, 0, 0, 1)))


def props():
    """The prints and lights of single shots, beyond the last row of the hall (x 29-40)."""
    S.q_print = H.make_print("q_print", QC.x, QC.y, "v4_q1_211", "v4_u2_211", seed=91, fit=True)
    S.c1_print = H.make_print("c1_print", C1C.x, C1C.y, "v4_c1_211", "v4_u1_211", seed=92, fit=True)
    S.float_print = V.sheet("float_print", 34.0, -4.0, V.print_mat("v4_q1_211", "v4_u4_211"), seed=94, top=0.012)
    S.float_print.rotation_euler = (0.0, math.pi / 2, 0.0)        # lying on the water, face up, its top at +X
    S.refl_omote = V.sheet("refl_omote", REFL.x, REFL.y, V.print_mat("v4_q1_211", "v4_u4_211"), seed=95, top=2.25)
    glow, nt, out = V._nodes("refl_ura")             # lit by itself: the water reflects only a few percent
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 20.0
    nt.links.new(V._picture(nt, "v4_u4_211"), em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    S.refl_ura = V.sheet("refl_ura", REFL.x - 0.002, REFL.y, glow, seed=95, top=2.25)
    for ob in (S.refl_omote, S.refl_ura):
        ob.scale = (0.5, 0.5, 0.5)                    # small and low, so the print and all of its reflection fit
    S.refl_omote.visible_glossy = False
    for attr in ("visible_camera", "visible_transmission", "visible_diffuse", "visible_shadow"):
        setattr(S.refl_ura, attr, False)             # only the water's mirror sees her 裏 (P7.3); in front, unshaded
    board()
    al = cyc.area_light
    S.lights = {
        "sweep": (al("sweep", (1.0, 1.5, 5.0), (2.0, 1.0, 4.7), 1.5, 9000, 5, size_y=0.06, spread_deg=12), 5.0),
        "q_cold": (al("q_cold", QC + Vector((-3.0, -1.5, 0.7)), QC, 2.0, 9000, 300, color="#7C94FF"), 300.0),
        "q_rose": (al("q_rose", QC + Vector((3.0, 1.5, 0.1)), QC, 2.0, 2000, 400, color=ROSE), 400.0),
        "c1_rose": (al("c1_rose", C1C + Vector((0.9, 0, 0.3)), C1C + Vector((0, 0, 0.3)), 2.0, 2000, 260, size_y=3.6,
                       color=ROSE), 260.0),
        "c1_cold": (al("c1_cold", C1C + Vector((-2.4, -1.5, 0.4)), C1C, 2.0, 9000, 120, color="#7C94FF"), 120.0),
        "w1_cold": (al("w1_cold", W1C + Vector((-3.5, -1.0, -0.6)), W1C, 2.0, 9000, 250, color="#7C94FF"), 250.0),
        "w1_rose": (al("w1_rose", W1C + Vector((2.5, 0.5, 1.4)), W1C, 1.5, 2000, 60, color=ROSE), 60.0),
        "w1_back": (al("w1_back", W1C + Vector((3.2, -1.8, 1.2)), W1C + Vector((0, 0, -0.6)), 2.0, 9000, 140,
                       color="#7C94FF"), 140.0),
        "refl_cold": (al("refl_cold", REFL + Vector((-4.0, 0, 2.0)), REFL + Vector((0, 0, 1.4)), 2.0, 9000, 120,
                         color="#7C94FF"), 120.0),
        "refl_rose": (al("refl_rose", REFL + Vector((1.6, 0, 2.0)), REFL + Vector((0, 0, 1.4)), 2.0, 2000, 200,
                         color=ROSE), 200.0),
        "under": (al("under", (V.L / 2, 0, 0.12), (V.L / 2, 0, 3), 40, 2000, 2500, size_y=14, color=ROSE), 2500.0),
        "float_sun": (al("float_sun", (31.9, -0.5, 6.0), FLOAT_C, 3.0, 8000, 900), 900.0),
        "cover": (al("cover", (32.1, 0.0, 6.5), (32.1, 0.0, 0.0), 4.0, 9000, 500, color="#9FB2FF"), 500.0),
        # cold light on the KV's back, for the one shot inside KV' (she looks back): rose on her, the paper cold
        "kv_back": (al("kv_back", (4.6, -1.8, 4.2), (2.0, 0.0, 3.0), 2.0, 9000, 400, color="#7C94FF"), 400.0),
    }
    for ob, _ in S.lights.values():                  # no lamp as a bright slab in the water or a picture's glass
        ob.visible_glossy = False
    for i, (target, z) in enumerate((((2, 0.78, 3.95), 0), ((2, 0.78, 3.05), 0), ((2, -0.3, 3.9), 0),
                                     ((2, -0.3, 2.2), 0))):
        S.lights[f"kv{i}"] = (al(f"kv{i}", Vector(target) + Vector((-2.6, 0, 2.0)), target, 0.5, 5200, 40,
                                 spread_deg=38), 40.0)


def cards():
    """A 2D shot: her picture on a card filling the frame in front of the camera, in two halves so it can tear down
    the middle (P9.2). Zoom, pan, the rose soaking in (P1.4) and a tint are set per frame."""
    mat, nt, out = V._nodes("card")
    g = kit.G(nt)
    uv = g.node("ShaderNodeTexCoord")
    mp = g.node("ShaderNodeMapping")
    g.link(uv.outputs["UV"], mp.inputs["Vector"])
    tex = g.node("ShaderNodeTexImage")
    tex.extension = "CLIP"                           # a tall picture is letterboxed in black
    g.link(mp.outputs[0], tex.inputs["Vector"])
    col = kit._mix_rgba(nt, tex.outputs["Alpha"], (0, 0, 0, 1), tex.outputs["Color"])
    seep = _value(nt)
    d = g.vmath("DISTANCE", uv.outputs["UV"], (0.46, 0.55, 0.0))
    mr = g.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    g.link(d, mr.inputs["Value"])
    g.link(g.math("SUBTRACT", seep, 0.12), mr.inputs["From Min"])
    g.link(g.math("ADD", seep, 0.12), mr.inputs["From Max"])
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.8, 0.0
    stained = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    kit.sock(stained.inputs, "Factor", "VALUE").default_value = 1.0
    g.link(col, kit.sock(stained.inputs, "A", "RGBA"))
    kit.sock(stained.inputs, "B", "RGBA").default_value = m.srgb(ROSE)
    col = kit._mix_rgba(nt, g.math("MULTIPLY", mr.outputs["Result"], g.math("GREATER_THAN", seep, 0.001)), col,
                        kit.sock(stained.outputs, "Result", "RGBA"))
    tint = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    tint_a = kit.sock(tint.inputs, "Factor", "VALUE")
    g.link(col, kit.sock(tint.inputs, "A", "RGBA"))
    tint_rgb = kit.sock(tint.inputs, "B", "RGBA")
    em = g.node("ShaderNodeEmission")
    g.link(kit.sock(tint.outputs, "Result", "RGBA"), em.inputs["Color"])
    g.link(em.outputs[0], out.inputs["Surface"])
    h = 0.5 * 9 / 16
    S.card_halves = []
    for side, (x0, x1, u0, u1) in ((-1, (-0.5, 0.0, 0.0, 0.5)), (1, (0.0, 0.5, 0.5, 1.0))):
        ob = _mesh(f"card{side:+d}", [(x0, -h, 0), (x1, -h, 0), (x1, h, 0), (x0, h, 0)], [(0, 1, 2, 3)],
                   [(u0, 0), (u1, 0), (u1, 1), (u0, 1)], [mat])
        ob.parent = S.cam
        _only_camera(ob)
        S.card_halves.append((ob, side))
    S.card = dict(tex=tex, map=mp, seep=seep, tint_a=tint_a, tint_rgb=tint_rgb, strength=em.inputs["Strength"])
    S.images = {k: bpy.data.images.load(_path(k), check_existing=True) for k in CARDS}
    cu = bpy.data.curves.new("page0", "FONT")
    cu.body, cu.align_x, cu.align_y = "0", "CENTER", "CENTER"
    S.zero = bpy.data.objects.new("page0", cu)
    m._link(S.zero)
    cu.materials.append(_emission_mat("page0", ROSE, 6.0)[0])
    S.zero.parent = S.cam
    _only_camera(S.zero)


def compositor():
    """Bloom and a touch of dispersion (as cyc.post), and D4: the frame as its own line drawing on paper, from the
    edges in the normal and depth passes, mixed in by S.lineart."""
    scene = bpy.context.scene
    vl = bpy.context.view_layer
    vl.use_pass_mist = True                           # mist is averaged over the samples; the depth pass is not,
    mist = scene.world.mist_settings                 # and its sub-pixel jitter made every slanted plane a field of noise
    mist.start, mist.depth, mist.falloff = 0.0, 40.0, "LINEAR"
    tree = bpy.data.node_groups.new("anim_post", "CompositorNodeTree")
    scene.compositing_node_group = tree
    kit._iface(tree, "Image", "OUTPUT", "NodeSocketColor")
    g = kit.G(tree)
    rl = g.node("CompositorNodeRLayers")
    glare = g.node("CompositorNodeGlare")
    for name, val in (("Type", "Bloom"), ("Threshold", 0.8), ("Strength", 0.4), ("Size", 0.6)):
        try:
            kit.sock(glare.inputs, name).default_value = val
        except (KeyError, TypeError, ValueError) as e:
            print("glare", name, e)
    g.link(rl.outputs["Image"], kit.sock(glare.inputs, "Image"))
    lens = g.node("CompositorNodeLensdist")
    g.link(glare.outputs[0], kit.sock(lens.inputs, "Image"))
    kit.sock(lens.inputs, "Dispersion").default_value = 0.004

    def edges(sock, kind="Sobel"):
        f = g.node("CompositorNodeFilter")
        kit.sock(f.inputs, "Type").default_value = kind
        g.link(sock, kit.sock(f.inputs, "Image"))
        bw = g.node("CompositorNodeRGBToBW")
        g.link(f.outputs[0], bw.inputs[0])
        return bw.outputs[0]
    # the Laplacian of the disparity (1 / depth): a plane is linear in disparity across the frame, so only a step
    # in depth or a crease draws, at any slant. The normal pass carried the water's and the walls' bump at every
    # pixel (white noise), and the depth's gradient saturated on every slanted plane (ink)
    disp = g.math("DIVIDE", 1.0, g.math("MAXIMUM", g.math("MULTIPLY", rl.outputs["Mist"], 40.0), 0.3))
    e = g.math("MULTIPLY", g.math("ABSOLUTE", edges(disp, "Laplace")), 30.0)
    lines = g.node("ShaderNodeMapRange")
    g.link(e, lines.inputs["Value"])
    lines.inputs["From Min"].default_value, lines.inputs["From Max"].default_value = 0.25, 0.7
    art = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(lines.outputs["Result"], kit.sock(art.inputs, "Factor", "VALUE"))
    kit.sock(art.inputs, "A", "RGBA").default_value = m.srgb(PAPER)
    kit.sock(art.inputs, "B", "RGBA").default_value = m.srgb("#1A1820")
    mix = g.node("ShaderNodeMix", data_type="RGBA")
    S.lineart = kit.sock(mix.inputs, "Factor", "VALUE")
    g.link(lens.outputs[0], kit.sock(mix.inputs, "A", "RGBA"))
    g.link(kit.sock(art.outputs, "Result", "RGBA"), kit.sock(mix.inputs, "B", "RGBA"))
    g.link(kit.sock(mix.outputs, "Result", "RGBA"), g.node("NodeGroupOutput").inputs[0])
    scene.render.use_compositing = True
    S.glare = kit.sock(glare.inputs, "Strength")


def stamp():
    r = bpy.context.scene.render
    r.use_stamp = True
    for attr in dir(r):
        if attr.startswith("use_stamp_") and attr not in ("use_stamp_note", "use_stamp_labels"):
            try:
                setattr(r, attr, False)
            except (AttributeError, TypeError):
                pass
    r.use_stamp_note = True
    r.stamp_font_size = 11


def setup():
    m.reset()
    scene = cyc.cycles(samples=SAMPLES, bounces=6)
    scene.cycles.caustics_refractive = scene.cycles.caustics_reflective = False    # fireflies at these samples
    if os.environ.get("DEVICE") == "CPU":           # when the GPU is taken: the server has 256 cores
        scene.cycles.device = "CPU"
        scene.cycles.denoising_use_gpu = False
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, WIDTH * 9 // 16
    scene.render.resolution_percentage = 100
    scene.render.use_persistent_data = True
    cyc.world((0.0004, 0.0004, 0.0008))
    h = V.hall(True)
    S.water, S.plaster = h["water"], h["plaster"]
    S.bulbs, S.lamp_glow = V.lamps()
    V.pipes()
    prints = V.hang(make=H.make_print)
    for key, (x, y) in STAGE.items():                   # the 2D shots' pictures, as prints too, each its own way up
        prints.append(H.make_print(f"stage_{key}", x, y, _pic(key), _pic(STAGE_BACKS[key]), seed=70 + len(prints),
                                   fit=True))
    S.prints_by = {p.name: p for p in prints}
    S.prints_by["stage_u1"].rotation_euler.z += math.pi   # her water faces the hall, so it has the hall to mirror
    S.prints = {p.name: p for p in prints}
    S.kv = S.prints["print_0_+0.0"]
    S.dawn = V.dawn_light()
    S.behind, S.cold = V.rose_light(prints)
    # the cold light from the near end stops at the first row: at night every print has its own, in front
    S.fronts, S.front_of = [], {}
    for p in prints:
        x, y = p.location.x, p.location.y
        lamp = cyc.area_light(f"front_{p.name}", (x - 1.5, y, V.TOP - 1.2), (x, y, V.TOP - 2.1), 1.6, 9000, 60,
                              color="#7C94FF")
        lamp.visible_glossy = False
        S.fronts.append((lamp, 60.0))
        S.front_of[p.name] = lamp
    S.haze = V.haze(True)
    S.haze_vol = next(n for n in S.haze.data.materials[0].node_tree.nodes if n.type == "PRINCIPLED_VOLUME")
    sky_images(h)
    water_ripple()
    wall_panels(h)
    props()
    S.cam = cyc.camera("anim_cam", (0.0, -1.0, 2.0), (0.0, 0.0, 2.0), 35, 8.0)
    scene.camera = S.cam
    cards()
    S.ink, S.burst = ink_volume("ink", 1.0), ink_volume("burst", 7.0)
    sill_glass()
    crack_material()
    S.cracks = {}
    for k, x in enumerate((7.0, 15.0)):                               # P2: on the high windows' glass
        crack(f"win{k}", 40 + k, (x - 0.3, V.WD / 2 - 0.02, 8.4), (1, 0, 0), (0, 0, 1), 1.8, width=0.025)
    for k, name in enumerate(("print_2_+3.2", "print_4_-3.2")):      # P2: across the prints
        crack(f"print{k}", 50 + k, (-0.02, 0.9, -1.4), (0, -1, 0), (0, 0, -0.35), 1.9, parent=S.prints[name])
    crack("face", 60, (-0.02, 0.62, -1.55), (0, -1, 0), (0, 0, -0.25), 1.3, width=0.006, parent=S.float_print)
    for k in range(4):                                                 # P7.4: one window giving way
        crack(f"win7_{k}", 70 + k, (11.0, V.WD / 2 - 0.02, 8.3), (math.cos(k * 1.6), 0, math.sin(k * 1.6)),
              (-math.sin(k * 1.6), 0, math.cos(k * 1.6)), 1.6, width=0.025)
    S.halves = {name: halves(S.prints[name]) for name in PATH + ["stage_r0"]}
    rain()
    confetti()
    motes()
    shards()
    letters(S.kv)
    compositor()
    stamp()
    S.mix = {p.name: p.data.materials[0].node_tree.nodes["wet"]
             for p in list(S.prints.values()) + [S.q_print, S.c1_print, S.float_print]}
    # where a 2D shot's picture is: the print, the picture's name, and whether it is on the print's back
    S.where = {key: (S.prints[f"stage_{key}"], _pic(key), False) for key in STAGE}
    S.where.update({"kv": (S.kv, _pic("kv"), False), "kvu": (S.kv, _pic("kvu"), True),
                    "a5": (S.prints["print_2_-3.2"], _pic("a5"), False), "q1": (S.q_print, _pic("q1"), False),
                    "u2": (S.q_print, _pic("u2"), True), "c1": (S.c1_print, _pic("c1"), False)})
    S.home = {ob.name: (ob.location.copy(), ob.rotation_euler.copy())
              for ob in list(S.prints.values()) + S.panels + [S.kv]}
    S.everything_lit = S.dawn + S.cold + S.fronts + S.bulbs + list(S.behind.values()) + list(S.lights.values())
    S.hidden = [S.rain, S.conf, S.dust, S.drop, S.zero, S.ink["ob"], S.burst["ob"], S.glass_ink["ob"]] + \
        [s["ob"] for s in S.shards] + [ob for hv in S.halves.values() for ob, _ in hv] + \
        [ob for ob, _ in S.card_halves] + getattr(S, "letter_lamps", [])
    return scene


# ---------------------------------------------------------------- what a shot sets

def put(sock, v):
    """Set a socket's value only when it changes: setting it again, even to the same value, makes Cycles rebuild
    the material or light, and forty hybrid prints make that most of a frame's time."""
    cur = sock.default_value
    if isinstance(v, (int, float)):
        if cur != v:
            sock.default_value = v
    elif tuple(cur) != tuple(v):
        sock.default_value = v


def reset(scene):
    """The hall at rest, every light off, nothing in the air: each shot then sets what it needs."""
    for ob, _ in S.everything_lit:
        if ob.data.energy != 0.0:
            ob.data.energy = 0.0
    for s in S.lamp_glow:
        put(s, 0.0)
    put(S.sky_em.inputs["Strength"], 0.0)
    haze(0.0)
    put(S.rip["a"], 0.0)
    put(S.water_glow, 0.0)
    for ob in S.hidden:
        if not ob.hide_render:
            ob.hide_render = True
    for p in S.prints.values():
        if p.hide_render:
            p.hide_render = False
    for name, (loc, rot) in S.home.items():
        ob = bpy.data.objects[name]
        if ob.location != loc:
            ob.location = loc
        if ob.rotation_euler != rot:
            ob.rotation_euler = rot
    for mix in S.mix.values():
        put(mix.inputs["Fac"], V.WET)
    for name in H.RINGS:
        H.ring(name, 0.0, 0.0, 0.0, 0.0)
    for name in H.STAINS:
        H.stain(name, 0.0, 0.0, -1.0)
    for ob in S.cracks.values():
        if ob["reveal"] != 0.0:
            ob["reveal"] = 0.0
    if S.refl_omote.visible_glossy or not S.refl_ura.visible_glossy:
        S.refl_omote.visible_glossy, S.refl_ura.visible_glossy = False, True
    put(S.lineart, 0.0)
    put(S.glare, 0.4)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    scene.cycles.samples = SAMPLES
    scene.cycles.max_bounces = scene.cycles.transmission_bounces = 6
    scene.cycles.use_denoising = True
    S.cam.data.type = "PERSP"
    S.cam.data.dof.use_dof = True


def haze(density, color="#E4ECF4", anisotropy=0.3):
    if S.haze.hide_render != (density <= 0):
        S.haze.hide_render = density <= 0
    put(S.haze_vol.inputs["Density"], density)
    put(S.haze_vol.inputs["Color"], m.srgb(color))
    put(S.haze_vol.inputs["Anisotropy"], anisotropy)


def sky(key, strength):
    """The painted sky behind the high windows, and behind every picture's window."""
    if S.sky_tex.image is not S.images[key]:
        S.sky_tex.image = S.images[key]
        for tex in H.SKY_TEX:
            tex.image = S.images[key]
    put(S.sky_em.inputs["Strength"], strength)
    for em in H.SKY_EM:                                  # a picture's sky no brighter than the hall's
        put(em.inputs["Strength"], 0.6 * strength)


def energy(ob, e):
    if ob.data.energy != e:
        ob.data.energy = e


def dawn(a=1.0, sky_key="s1"):
    """表: the cold sun through the high windows, by `a`."""
    for ob, e in S.dawn:
        energy(ob, e * a)
    sky(sky_key, 2.5 * max(a, 0.15))
    haze(0.01 * max(a, 0.2), "#E4ECF4", 0.25)
    bpy.context.scene.view_settings.exposure = 1.2


def night(cold=1.0, rose=0.0, sky_key="s2", density=0.0035, red=0.0):
    """裏: cold light on the fronts by `cold`, the rose lamp behind each print by `rose` (a number, or a function of
    the print's name); `red` turns the haze from pink to rose."""
    for ob, e in S.cold + S.fronts:
        energy(ob, e * cold)
    for name, (ob, e) in S.behind.items():
        energy(ob, e * (rose(name) if callable(rose) else rose))
    sky(sky_key, 0.5)
    haze(density, "#C4BCD0" if red > 0.5 else "#E6D4DC", 0.4)    # the air never rose: the rose stays on the paper and the water
    bpy.context.scene.view_settings.exposure = 1.1


def light(name, a=1.0):
    ob, e = S.lights[name]
    energy(ob, e * a)


def behind(p, a):
    ob, e = S.behind[p.name]
    energy(ob, e * a)


def wet(p, w):
    put(S.mix[p.name].inputs["Fac"], w)


def ripple(t0, x, y, amp=1.0):
    age = S.t - t0
    if 0 <= age < 1.2:
        S.rip["x"].default_value, S.rip["y"].default_value = x, y
        S.rip["r"].default_value = 0.1 + 2.4 * age
        S.rip["a"].default_value = amp * (1 - age / 1.2)


def ink(blob, loc, scale, density=1.0, glow=0.3):
    ob = blob["ob"]
    ob.hide_render = False
    ob.location, ob.scale = loc, scale
    blob["density"].default_value = density * 8.0 / max(scale)
    blob["glow"].default_value = glow * 8.0 / max(scale)
    blob["w"].default_value = blob["seed"] + 0.3 * S.t


def look(eye, target, lens=35.0, fstop=8.0, roll=0.0, focus=None, up=(0, 0, 1), ortho=None):
    """Put the camera at `eye` looking at `target`, with the chorus's beat push and the Dutch angle where the script
    has them. `focus` is a distance or a point (default: the target)."""
    eye, target = Vector(eye), Vector(target)
    if any(a <= S.b < z for a, z in PUNCH):
        eye = eye + (target - eye) * punch(S.t, 0.03)
    if DUTCH[0] <= S.b < DUTCH[1]:
        roll += 12.0 if math.floor(S.b) % 2 else -12.0
    f = (target - eye).normalized()
    upv = Vector(up)
    if abs(f.dot(upv)) > 0.999:
        upv = Vector((1.0, 0.0, 0.0))
    r = f.cross(upv).normalized()
    rot = Matrix((r, r.cross(f), -f)).transposed()
    if roll:
        rot = rot @ Matrix.Rotation(math.radians(roll), 3, "Z")
    S.cam.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()
    cam = S.cam.data
    cam.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.ortho_scale = ortho
    cam.lens = lens
    cam.dof.aperture_fstop = fstop
    cam.dof.focus_object = None
    cam.dof.focus_distance = focus if isinstance(focus, (int, float)) else \
        ((Vector(focus) if focus is not None else target) - eye).length
    S.eye, S.fwd = eye, f


def card(key, zoom=1.0, cx=0.5, cy=0.5, seep=0.0, gap=0.0, tint=None, tint_a=0.0, dist=1.0, alone=True):
    """Her picture `key` filling the frame (a tall one fitted to the height), `gap` the halves torn apart by;
    `alone` False when something 3D is in front of it."""
    scene = bpy.context.scene
    img = S.images[key]
    S.card["tex"].image = img
    sx = (16 / 9) / (img.size[0] / img.size[1]) / zoom
    S.card["map"].inputs["Scale"].default_value = (sx, 1 / zoom, 1.0)
    S.card["map"].inputs["Location"].default_value = (cx - 0.5 * sx, cy - 0.5 / zoom, 0.0)
    S.card["seep"].default_value = seep
    S.card["tint_a"].default_value = tint_a if tint else 0.0
    S.card["tint_rgb"].default_value = m.srgb(tint or "#FFFFFF")
    S.card["strength"].default_value = 1.0
    w = dist * S.cam.data.sensor_width / S.cam.data.lens * 1.004
    for ob, side in S.card_halves:
        ob.hide_render = False
        ob.scale = (w, w, 1.0)
        ob.location = (side * gap * w * 0.5, 0.0, -dist)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0.0
    S.glare.default_value = 0.1
    S.cam.data.dof.use_dof = False                   # the card sits a metre from the lens
    if gap <= 0 and alone:                           # nothing of the 3D scene shows: one sample is enough,
        S.cam.matrix_world = Matrix.Translation((16.0, 0.0, 40.0))   # and nothing (glass, haze) before the card
        S.haze.hide_render = True
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False


def into(key, zoom=1.0, cx=None, cy=None, lens=35.0, fstop=2.8, cold=1.0, rose=0.0, yaw=0.0, pitch=0.0,
         sky_key=None, exposure=0.6):
    """A 2D shot: the camera in front of the print that carries picture `key`, the frame covering the picture's
    width over `zoom`, centred on (cx, cy) of the picture (0..1 from its bottom left; by default her face, from
    the parts map). The picture's planes are the hall's and its figure a relief, so the shot is inside the picture,
    not before a card. `yaw`, `pitch` (degrees) look at it a little from the side or above, for the parallax.
    Lit by its own cold lamp in front (`cold`) and the rose lamp behind it (`rose`); the other 2D pictures' prints
    are out of the way."""
    p, name, on_back = S.where[key]
    W, Hh = H.size_of(p)
    img = bpy.data.images.load(_path(key), check_existing=True)
    mu, mv, rw, rh, s = H._layout(*img.size, (W, Hh))
    half = (W * rw / zoom) * 9 / 16 / (Hh * rh) / 2                             # the frame's half height, of the picture
    if cy is None:                                                              # one subject: her face, in frame
        hv = H.anchor(p, name, 0)["uv"][1]
        cy = min(1 - half, max(half, hv - 0.04)) if half < 0.5 else 0.5
    cx = 0.5 if cx is None else cx
    target = H.picture_point(p, name, cx, cy, lift=-0.05 if on_back else 0.0)
    face = p.matrix_world.to_3x3() @ Vector((1.0 if on_back else -1.0, 0.0, 0.0))
    d = W * rw / zoom * lens / S.cam.data.sensor_width                          # the frame as wide as the print's picture
    away = Matrix.Rotation(math.radians(yaw), 3, "Z") @ face
    away = Matrix.Rotation(math.radians(pitch), 3, away.cross(Vector((0, 0, 1)))) @ away
    look(target + away * d, target, lens=lens, fstop=fstop, focus=target)
    for other in STAGE:
        if other != key:
            S.prints[f"stage_{other}"].hide_render = True
    if p is S.q_print:
        light("q_cold", cold)
        light("q_rose", rose)
    elif p is S.c1_print:
        light("c1_cold", cold)
        light("c1_rose", rose)
    else:
        if p.name in S.behind:
            behind(p, rose)
        if p.name in S.front_of:
            energy(S.front_of[p.name], 200.0 * cold)
        if on_back and p is S.kv:
            light("kv_back", cold)
    if sky_key:
        sky(sky_key, 2.0 if sky_key == "s1" else 0.5)
    haze(0.002, "#E4ECF4", 0.3)
    bpy.context.scene.view_settings.exposure = exposure     # the picture's own exposure, whatever the hall's is


def seep(key, v, blob=None):
    """P1.4 and the chorus: rose ink soaking into picture `key` from her hair (the stain on the paper, by v 0..1),
    and, with `blob`, a wisp of ink in the air just off the paper, running down."""
    p, name, _ = S.where[key]
    hair = H.anchor(p, name, 0)
    H.stain(p.name, *H.sheet_uv(p, name, *hair["uv"]), 0.02 + 0.11 * v)   # hair-sized: the stain, not a disc
    if blob is not None:
        ink(blob, hair["point"] + Vector((-0.03, 0.0, -0.2 * v)), (0.04 + 0.02 * v, 0.1 + 0.14 * v, 0.2 + 0.4 * v),
            1.6, 0.0)


def rain_in(p, t):
    """The rain inside a picture: the block of streaks as a slab just in front of the print `p`, over its face."""
    W, Hh = H.size_of(p)
    S.rain.hide_render = False
    S.rain.scale = (0.5, W / 14.0, 0.5)                   # spread through the depth between the camera and the paper,
    S.rain.location = (p.location.x - 3.6, p.location.y,  # so it is rain, not a curtain of lines
                       p.location.z - Hh - 0.5 * ((t * 6.5) % 8.0))
    put(S.rain_em.inputs["Strength"], 0.6)


def ripple_in(key, t0, amp=1.0, part=0):
    """A ring on the water inside picture `key`, from her hair (or `part`), spreading for a second after t0."""
    age = S.t - t0
    if not 0 <= age < 1.0:
        return
    p, name, _ = S.where[key]
    c = p.matrix_world.inverted() @ H.anchor(p, name, part)["point"]
    H.ring(p.name, c.y, c.z - 0.3, 0.05 + 1.3 * age, amp * (1 - age))


def row(r):
    return [p for name, p in S.prints.items() if name.startswith(f"print_{r}_")]


def tear(name, w):
    """D6: print `name` torn down the middle, its halves swung open like doors by w (0..1) and dropping."""
    if w <= 0:
        return
    S.prints[name].hide_render = True
    for ob, side in S.halves[name]:
        ob.hide_render = False
        ob.rotation_euler = (side * 0.3 * w, 0.0, side * math.radians(115) * w)
        ob.location.z = V.TOP - 1.4 * w * w


def lift(p, a):
    """A print lifting in the wind, swung about its top edge so its foot rises towards the camera side."""
    p.rotation_euler.y = -math.radians(a)


# ---------------------------------------------------------------- the shots, script_v4.md section 5

def p0_paper(u, t, b):
    S.kv.rotation_euler.z = 0.012 * math.sin(2 * math.pi * t / 2.6)          # the sheet breathing
    lt, e = S.lights["sweep"]                                                   # a band of cold light down the paper
    lt.data.energy = e
    z = 5.4 - 1.6 * u
    cyc._aim(lt, (1.0, 1.5, z), (2.0, 1.0, z))
    bpy.context.scene.view_settings.exposure = -1.2                             # the band shows the fibre, not white
    look((0.9, 0.7, 4.5), (2.03, 1.15, 4.3), lens=60, fstop=2.8)


P0_ORTHO = [4.2, 5.6, 7.1, 8.6]                                                 # the frame a step wider on each downbeat


def p0_frame(b):
    k = min(3, math.floor(b))
    o = P0_ORTHO[k] + (P0_ORTHO[min(3, k + 1)] - P0_ORTHO[k]) * ease((b - k) / 0.5)
    return o, 0.5 - 0.22 * b                                                    # and drifting slowly across


def p0_lights(u, t, b):
    for i in range(4):
        light(f"kv{i}", clamp((b - i) * 6))                                     # a lamp on every downbeat
    behind(S.kv, 0.25)                                                          # the letters glow a little
    haze(0.004, "#E4ECF4", 0.3)
    dust(t)                                                                     # the lamps find the dust in the air
    o, y = p0_frame(b)
    look((-6, y, 2.9 + 0.35 * (8.6 - o) / 4.4), (2, y, 2.9 + 0.35 * (8.6 - o) / 4.4), ortho=o)
    bpy.context.scene.view_settings.exposure = -0.4                             # paper, not a light box


def p0_through(u, t, b):
    for i in range(4):
        light(f"kv{i}")
    behind(S.kv, 0.25 + 0.7 * ease(u))
    wet(S.kv, V.WET + 0.3 * ease(u))
    haze(0.004, "#F2D8E0", 0.3)
    dust(t)
    o, y = p0_frame(b)
    look((-6, y, 2.9), (2, y, 2.9), ortho=o - 0.4 * ease(u))
    bpy.context.scene.view_settings.exposure = -0.4


def kv_lit():
    for i in range(4):
        light(f"kv{i}")
    night(cold=0.1, rose=0.12)
    behind(S.kv, 0.7)
    wet(S.kv, V.WET + 0.3)
    bpy.context.scene.view_settings.exposure = 0.4                              # the lit print is paper, not white


def p0_space(u, t, b):
    kv_lit()
    dust(t)
    look((-5.5, 2.5 - 5.0 * ease(u), 2.9), (2, 0, 2.9), lens=35, fstop=5.6)


def p0_dive(u, t, b):
    kv_lit()
    dust(t)
    e0 = Vector((-5.5, -2.5, 2.9))
    d = (HOLE - e0).normalized()
    s = 1.25 * u ** 2.2                                                         # accelerating; 1 is the cut-out
    eye = e0.lerp(HOLE, s) if s <= 1 else HOLE + d * (s - 1) * 8.0
    look(eye, eye + d * 5.0, lens=35 - 11 * u, fstop=4)


def p1_hall(u, t, b):
    dawn()
    r1 = sorted(row(1), key=lambda p: -p.location.y)
    r1[math.floor(b) % 4].rotation_euler.z = 0.1 * math.sin(math.pi * min(1.0, b % 1 * 2))   # one turns in the wind
    # three layers: a print's edge close and dark, the row lit by the sun across it, the windows and their beams
    # above and beyond; the camera low among the prints, drifting down the hall towards the light
    x = 1.0 + 6.0 * u
    look((x, -5.6, 1.1), (x + 6.0, 6.0, 5.2), lens=24, fstop=4, focus=(x + 3.0, 0.0, 3.0))


def p1_eyes(u, t, b):
    dawn(0.25)                                                                  # the sun low: it would wash the paper from behind
    if b < 13:                                                                  # A6 not drawn: Q1
        into("a5", 1.05 + 0.05 * u, yaw=-3 + 6 * u, cold=0.45, exposure=0.3)
    else:
        into("q1", 1.1, yaw=4 - 8 * (b - 13), cold=0.6, exposure=0.4)
    sky("s1", 1.2)


def p1_drop(u, t, b):
    dawn()
    scene = bpy.context.scene
    scene.cycles.samples = 4 * SAMPLES                                          # glass in glass in water
    scene.cycles.max_bounces = scene.cycles.transmission_bounces = 14           # glass, water, glass, the window's glass
    sky("s1", 6.0)                                                              # the glass against the bright window
    scene.view_settings.exposure = -0.5
    g, t15 = S.glass_at, at(15)
    if t15 - 0.35 <= t < t15:
        S.drop.hide_render = False
        S.drop.location = g + Vector((0, 0, 0.065 + 0.6 * (t15 - t)))
    if t >= t15:
        v = ease((t - t15) / (at(16) - t15))
        s = 0.006 + 0.02 * v
        ink(S.glass_ink, g + Vector((0, 0, 0.05 - 0.015 * v)), (s, s, s * 1.3), 1.0, 0.05)
    look(g + Vector((-0.30, -0.22, 0.05)), g + Vector((0, 0, 0.035)), lens=85, fstop=2.8)


def p1_seep(u, t, b):
    if b < 19:                                                                  # P1.4: the ink soaks in from her hair
        night(cold=0.0, rose=0.0)
        v = ease((b - 16) / 3)
        into("q1", 1.05 + 0.04 * u, yaw=-3 + 6 * u, cold=0.7, rose=0.4 * v, sky_key="s1")
        seep("q1", v, S.ink)
        return
    dawn()
    g = S.glass_at
    ink(S.glass_ink, g + Vector((0, 0, 0.035)), (0.026, 0.026, 0.03), 1.2, 0.05)
    eye = Vector((5.35, 3.45, 4.85))
    look(eye, g + Vector((0, 0, 0.04)), lens=50, fstop=1.4, focus=0.9 + ((g - eye).length - 0.9) * ease(b - 19))


def p1_top(u, t, b):
    dawn(0.4)                                                                   # the water black, not the lit ceiling
    light("float_sun", 3.5)
    v = ease((b - 20) / 4)
    ink(S.ink, FLOAT_C + Vector((0, 0, -0.015)), (2.2 + 1.8 * v, 2.2 + 1.8 * v, 0.014), 0.6 + 0.8 * v, 0.0)
    ripple(last_beat(t), FLOAT_C.x, FLOAT_C.y, 0.7)
    if b >= 23.75:
        S.cracks["face"]["reveal"] = ease((b - 23.75) * 4)                     # the first crack, across her face
    a = 0.3 * ease(u)                                                           # sinking towards her, turning a little
    look(FLOAT_C + Vector((0, 0, 7.2 - 2.4 * ease(u))), FLOAT_C, lens=35, fstop=8, up=(math.cos(a), math.sin(a), 0))


WHIP = [("print_1_-1.6", 1), ("print_2_+3.2", -1), ("print_3_+1.6", 1), ("print_4_-3.2", -1)]
CRACKS_P2 = ["win0", "print0", "win1", "print1"]                               # 3D and 2D in turn


def p2_whip(u, t, b):
    dawn()
    k, v = min(3, math.floor(b) - 24), b % 1
    p, side = S.prints[WHIP[k][0]], WHIP[k][1]
    eye = Vector((p.location.x - 2.3, p.location.y, 2.9))
    # whip in from looking along the row (up at the windows), hold on the print, whip out the other way
    yaw = side * 90 * (1 - ease(v / 0.3)) if v < 0.6 else -side * 90 * ease((v - 0.6) / 0.4)
    d = Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.5 * abs(yaw) / 90))
    look(eye, eye + d * 4.0, lens=24, fstop=5.6, focus=2.3)
    for j, name in enumerate(CRACKS_P2):
        if b >= 24 + j:
            S.cracks[name]["reveal"] = ease((b - 24 - j) / 0.15)


def p2_wind(u, t, b):
    dawn()
    a = math.sin(math.pi * clamp((b - 28.4) / 1.3))
    for k, p in enumerate(row(2) + row(3)):
        lift(p, 55 * a * (0.85 + 0.15 * math.sin(k * 1.7)))
        behind(p, 0.6 * a)                                                      # lit from behind for an instant
    for name in CRACKS_P2:
        S.cracks[name]["reveal"] = 1.0
    look((3.2, -5.5, 1.0), (14, 1.5, 3.4), lens=24, fstop=5.6)


def p2_out(u, t, b):
    dawn(1 - (math.floor(b % 1 * 4) + 1) / 4)                                  # the light goes beat by beat
    for name in CRACKS_P2:
        S.cracks[name]["reveal"] = 1.0
    look((3.2, -5.5, 1.0), (14, 1.5, 3.4), lens=24, fstop=5.6)


def p3_turn(u, t, b):
    night(cold=0.0, rose=0.06)
    light("q_cold")
    light("q_rose")
    n = (b - 31) * 4 if b < 34 else 12 + (b - 34) * 8                          # a side a beat, on bar 34 a half beat
    ang = math.pi * (math.floor(n) + ease(min(1.0, n % 1 / 0.45)))
    look(QC + Vector((-math.cos(ang) * 3.4, math.sin(ang) * 3.4, 0.0)), QC, lens=35, fstop=4)


def p4_chorus(u, t, b):
    k, v = math.floor(b) - 35, b % 1
    beat, p = int(v * 4), v * 4 % 1
    if beat == 3 and p < 0.5:                                                   # half a beat inside a chorus picture
        key = f"c{k % 4 + 1}"
        night(cold=0.0, rose=0.0)
        into(key, 1.05 + 0.05 * p, yaw=6 - 12 * p, cold=0.7, rose=0.8)
        seep(key, 0.3 + 0.7 * p, S.burst)
        return
    names = list(S.prints)
    red = ease((b - 41) / 5)
    night(cold=1.0 - 0.4 * red, rose=lambda n: clamp((b - 41 - 0.22 * names.index(n)) / 0.5),
          density=0.004 + 0.003 * red, red=red)
    bpy.context.scene.view_settings.exposure = 1.6 - 0.3 * red
    cam = k % 5
    if cam == 0:                                                                # low along a row, between the prints
        y = 5.5 - 11 * v
        look((8.1, y, 0.35), (14, y - 1.5, 2.2), lens=24, fstop=5.6)
    elif cam == 1:                                                              # ink flowering on the water, lit from above
        c = FLOAT_C + Vector((0.0, 1.6, 0.0))                                   # beside the print lying there
        s = 0.4 + 2.6 * ease(v)
        ink(S.ink, c + Vector((0, 0, -0.015)), (s, s, 0.014), 1.2, 0.15)
        light("float_sun", 2.0)
        look(c + Vector((-2.6, -0.8, 4.2)), c, lens=35, fstop=5.6)
    elif cam == 2:                                                              # round a print to its back
        c = S.prints["print_3_-1.6"].location + Vector((0, 0, -2.1))
        ang = math.radians(-25 + 230 * ease(v))
        look(c + Vector((-math.cos(ang) * 3.2, math.sin(ang) * 3.2, -0.4)), c, lens=28, fstop=4)
    elif cam == 3:                                                              # through a print
        x = 6.8 + 5.5 * v ** 1.5
        look((x, 0.15, 2.9), (x + 5, 0.15, 2.9), lens=24, fstop=5.6)
    else:                                                                       # from under the water
        look((4.0 + 1.5 * v, -0.8, -0.012), (12, 0.5, 4.5), lens=20, fstop=8)
    tb = at(math.floor(b) + beat / 4)
    if beat == 0 and t - tb < 2 / FPS:
        S.lineart.default_value = 1.0                                           # D4: two frames of line art
        S.cam.data.dof.use_dof = False                                          # a drawing has no blur; blur is noise
    if beat == 1:
        c = S.eye + S.fwd * 4.0
        ripple(tb, c.x, c.y, 1.0)
        for q in S.prints.values():                                             # every print swayed by the pulse
            q.rotation_euler.z = 0.06 * math.exp(-(t - tb) / 0.2) * math.sin(12 * (t - tb))
    if beat == 2:                                                               # ink blooms on the water ahead
        c = S.eye + S.fwd * 5.0
        s = 0.3 + 2.2 * ease(p)
        ink(S.burst, (c.x, c.y, -0.015), (s, s, 0.014), 1.4 * (1 - 0.5 * p), 0.0)


def p5_spill(u, t, b):
    night(cold=0.25, rose=0.6)
    light("c1_rose")
    light("c1_cold", 2.0)
    v = ease(u)
    # from her face filling the frame back and aside, behind the last row: it was a print hanging in the hall
    face = H.anchor(S.c1_print, "v4_c1_211", 1)["point"]
    eye = (face + Vector((-1.35, 0, 0.1))).lerp(Vector((27.2, -4.5, 3.8)), v)
    look(eye, face.lerp(C1C, v), lens=35 - 7 * v, fstop=4)
    # the ink round her runs off the foot of the paper and pours into the water, then spreads
    ink(S.burst, (C1C.x, C1C.y - 0.1, 0.45), (0.12, 0.3, 0.5 * clamp(u * 3)), 1.6, 0.0)
    s = 0.2 + 3.5 * ease((u - 0.2) / 0.8)
    ink(S.ink, (C1C.x - 0.4, C1C.y, -0.015), (s, s, 0.014), 1.4, 0.0)


def p5_full(u, t, b):
    night(cold=0.35, rose=0.4, density=0.003, red=1.0)
    put(S.water_glow, 0.0)                                                      # the water is a mirror, never a lamp
    light("under", 0.05 * ease(u * 2))
    look((-1.5, -5.0, 0.8), (20, 1, 3.2), lens=24, fstop=5.6)


def p5_vertigo(u, t, b):
    night(cold=0.4, rose=0.4, density=0.003, red=1.0)
    put(S.water_glow, 0.0)
    light("under", 0.05)
    for key in STAGE:                                                           # the camera backs out through their places
        S.prints[f"stage_{key}"].hide_render = True
    d = 3.5 + 10.5 * ease(u)                                                    # back away, zoom in: she stays
    look((2 - d, 0, 2.9), (2, 0, 2.9), lens=24 * d / 3.5, fstop=8)


def p5_cut(u, t, b):
    if b >= 56.25:                                                              # one beat of black, then the rain
        p6_rain(0.0, t, b)
        return
    scene = bpy.context.scene
    scene.view_settings.exposure = -10.0
    scene.cycles.samples, scene.cycles.use_denoising = 1, False
    look((-1.5, -5.0, 0.8), (20, 1, 3.2))


def rain_at(t, lines=False):
    """The rain round the camera; `lines` stretches it into 2D speed lines for a bar (D5)."""
    S.rain.hide_render = False
    S.rain.location = (S.eye.x, S.eye.y, -((t * 6.5) % 8.0))
    S.rain.scale = (1.0, 1.0, 4.0 if lines else 1.0)
    S.rain_em.inputs["Strength"].default_value = 6.0 if lines else 0.8


def p6_rain(u, t, b):
    v = ease(u)
    night(cold=0.45, rose=0.25 + 0.5 * v, density=0.005)
    for p in S.prints.values():
        wet(p, V.WET + 0.55 * v)                                                # wet paper turns clear: the 裏 shows
    look((-1.5, -4.2 + 2.0 * u, 1.6), (6.0, -1.0, 2.8), lens=35, fstop=4)
    rain_at(t)


def p6_w1(u, t, b):
    night(cold=0.2, rose=0.0, density=0.005)
    light("w1_cold")
    light("w1_rose")
    look(W1C + Vector((-4.5, -0.3 + 0.4 * u, -1.65)), W1C + Vector((0, 0, -0.2)), lens=50, fstop=2.8)
    rain_at(t)


def p6_w2(u, t, b):
    night(cold=0.0, rose=0.0, density=0.003)
    into("w2", 1.05 + 0.08 * u, yaw=4 - 8 * u, cold=0.9, rose=0.35)
    rain_in(S.where["w2"][0], t)


def p6_side(u, t, b):
    night(cold=0.2, rose=0.0, density=0.005)
    light("w1_cold")
    light("w1_rose", 0.5 if b < 65 else 0.12)         # behind: plain paper and a pencilled number, in the cold
    light("w1_back", 0.0 if b < 65 else 0.35 * ease((b - 65) * 1.5))
    ang = math.radians(90 * ease(b - 64) if b < 65 else 90 + 90 * ease((b - 65) * 1.5))   # a line, then its back
    look(W1C + Vector((-math.cos(ang) * 4.0, -math.sin(ang) * 4.0, -1.0)), W1C, lens=40, fstop=4)
    rain_at(t)


def p6_lines(u, t, b):
    night(cold=0.45, rose=0.75, density=0.005)
    for p in S.prints.values():
        wet(p, V.WET + 0.55)
    yaw = math.radians(180 * ease((b - 67.75) * 4)) if b >= 67.75 else 0.0     # the last beat turns the page
    eye = Vector((-1.0, -2.0, 1.8))
    look(eye, eye + Vector((math.cos(yaw), math.sin(yaw), 0.15)) * 8, lens=28, fstop=4)
    rain_at(t, lines=b < 67)


def p7_night():
    night(cold=0.3, rose=0.6, density=0.004)


def p7_roll(u, t, b):
    p7_night()
    look((-1.0, -2.4, 0.35), (16, 0.5, 1.2), lens=24, roll=180 * ease(u))


URA_SEQ = [(70, "u1"), (72, None), (73, "u2"), (75, None), (76, "u4"), (77, "U3"), (78, None)]


def p7_ura(u, t, b):
    k = max((i for i, (bar, _) in enumerate(URA_SEQ[:-1]) if b >= bar), default=0)
    (bar0, key), nxt = URA_SEQ[k], URA_SEQ[k + 1][0]
    v = (b - bar0) / (nxt - bar0)
    if key == "U3":                                                             # two of her across the water line
        night(cold=0.1, rose=0.3)
        light("refl_cold")
        light("refl_rose")
        look(REFL + Vector((-3.0, 0.6, 0.12)), REFL, lens=28, fstop=5.6)
    elif key:
        night(cold=0.0, rose=0.0, density=0.003)
        into(key, 1.05 + 0.08 * v, yaw=-6 + 12 * v, cold=0.6, rose=0.7)      # rose on her, the paper still cold
        if key == "u1":                                                         # her water takes the beat
            ripple_in("u1", last_beat(t), 0.8)
    else:                                                                       # the hall, upside down
        p7_night()
        look((-1.0 + 3.0 * v, -2.4, 0.35), (16, 0.5, 1.2), lens=24, roll=180)


def p7_reflect(u, t, b):
    night(cold=0.1, rose=0.3)
    light("refl_cold")
    light("refl_rose")
    flash = t - at(math.floor(b)) < 2 / FPS                                     # once a bar the reflection is 表 again
    S.refl_ura.visible_glossy, S.refl_omote.visible_glossy = not flash, flash
    # the whole print and the whole of its reflection, the water line across the middle; a slow slide past
    look(REFL + Vector((-3.0, 0.6 - 1.2 * u, 0.12)), REFL, lens=28 + 2 * u, fstop=5.6)


def p7_crack(u, t, b):
    p7_night()
    for k in range(4):
        S.cracks[f"win7_{k}"]["reveal"] = ease(1.5 * u - 0.15 * k)
    look((9.0, 3.0, 3.0), (11.0, 7.0, 8.4), lens=35, fstop=5.6)


SHARD_CUTS = [((10, 2, 7), (16, 6.5, 9.5)), ((14, 6, 9), (18, 1, 5)), ((20, 1.5, 6), (22, 7, 10.5)),
              ((24, 4, 8), (16, 2, 6)), ((12, 4, 5.5), (18, 6.5, 10)), ((17, 6.2, 7.5), (17, -2, 6)),
              ((26, 2, 9), (16, 6, 6))]                                      # never straight down the hall: the far wall is a slab


def p8_shards(u, t, b):
    night(cold=0.6, rose=0.4, density=0.003)
    w = ease((b - 86.75) * 4) if b >= 86.75 else 0.0                            # the last beat: they line up into KV'
    for s in S.shards:
        ob = s["ob"]
        ob.hide_render = False
        q = Matrix.Rotation(s["ph"] + 0.6 * t, 3, s["spin"]).to_quaternion()
        drift = s["home"] + Vector((0, 0, 0.15 * math.sin(t + s["ph"])))
        if s["grid"] is not None:
            ob.location = drift.lerp(s["grid"], w)
            ob.rotation_quaternion = q.slerp(Matrix.Identity(3).to_quaternion(), w)
        else:
            ob.location = drift.lerp(s["away"], w)
            ob.rotation_quaternion = q
    if w > 0:
        look((17.5, 0, 3.0), (24, 0, 3.0), lens=35, fstop=8)
        return
    n, q = int((b - 83) * 2), (b - 83) * 2 % 1
    eye, target = (Vector(v) for v in SHARD_CUTS[n % len(SHARD_CUTS)])
    eye = eye + (target - eye).normalized() * 0.8 * q
    look(eye, target, lens=28, fstop=4)
    if q < 0.25:
        S.lineart.default_value = 1.0                                           # each cut lands on line art first
        S.cam.data.dof.use_dof = False


def p9_run(u, t, b):
    night(cold=0.7, rose=0.6, density=0.004, red=1.0)
    x = 5.6 + 4.0 * (b - 87)                                                    # through a print on every downbeat
    for r, name in enumerate(PATH):
        tear(name, ease((b - (87 + r) + 0.12) / 0.5))
    look((x, 0.8, 0.45), (x + 6, 0.8, 1.3), lens=24, fstop=5.6)
    ripple(last_beat(t), x + 1.2, 0.8, 0.9)                                     # her steps on the water


def p9_r0(u, t, b):
    night(cold=0.45, rose=1.0, density=0.004, red=1.0)
    for name in PATH:
        tear(name, 1.0)
    into("r0", 1.0 + 0.3 * ease(u), cold=0.8, rose=1.0)                        # torn, the hall shows behind it
    tear("stage_r0", ease(b - 96) if b >= 96 else 0.0)


def p9_back(u, t, b):
    if b < 98:                                                                  # she stops and looks back: KV'
        night(cold=0.0, rose=0.0, density=0.003)
        into("kvu", 1.0, yaw=6 * (b - 97), cold=0.8, rose=0.15)
        return
    night(cold=0.5, rose=0.45, density=0.004, red=1.0)
    a = ease((b - 98) / 0.6)
    for k, p in enumerate(S.prints.values()):                                   # every print behind her lifts
        lift(p, 65 * a * (0.8 + 0.2 * math.sin(k * 2.3)))
    for name in PATH:
        tear(name, 1.0)
    look((1.0, -5.5, 0.8), (16, 1.0, 4.2), lens=24, fstop=5.6)


def p10_walls(u, t, b):
    dawn(0.5, "s3")
    night(cold=0.3, rose=0.6, sky_key="s3", density=0.004)
    S.sky_em.inputs["Strength"].default_value = 2.0
    for k, panel in enumerate(S.panels):                                        # the walls are paper too
        panel.rotation_euler.x = math.radians(95) * ease((b - 99.3 - 0.18 * abs(k - 9)) / 1.2)
    v = ease(u)
    look(Vector((14, 3.5, 1.0)).lerp(Vector((4, 5.5, 7.5)), v), Vector((18, -7, 4)).lerp(Vector((20, -9, 6)), v),
         lens=24 - 4 * v, fstop=8)
    bpy.context.scene.view_settings.exposure = 0.0
    scraps((16, 0, 4), t, radius=6, height=4, swirl=0.6)


def p10_f1(u, t, b):
    night(cold=0.0, rose=0.0, density=0.003)
    into("f1", 1.15, cy=0.62 - 0.25 * u, cold=0.9, rose=0.5)
    scraps(S.eye + S.fwd * 2.4, t, radius=3.2, height=2.8, swirl=1.2 + u)      # the paper flying round her


FAST = ["f1", "h_wide", "c1", "h_high", "r0", "h_low", "u2", "h_kv", "kv", "h_wide", "kvu", "h_low", "w2", "h_high",
        "f2", "h_kv"]
FAST_VIEWS = {"h_wide": ((-1.5, -5, 0.9), (20, 1, 3.2), (0, 0, 1)), "h_high": ((6, -6, 8.5), (22, 2, 1.5), (0, 0, 1)),
              "h_low": ((3, -2, 0.3), (20, 2, 2), (0, 0, 1)), "h_kv": ((-3, 0, 2.9), (2, 0, 2.9), (0, 0, 1))}


def p10_fast(u, t, b):
    n = int((b - 107) * 2) if b < 111 else 8 + int((b - 111) * 4)             # half bars, then every beat
    key = FAST[n % len(FAST)]
    cold = int(b % 1 * 4) % 2 == 0                                              # cold and rose change places each beat
    if not key.startswith("h_"):
        night(cold=0.0, rose=0.0, density=0.003)
        if S.where[key][2]:                                                     # a back picture: the rose lamp is its key
            into(key, 1.08, cold=0.4, rose=0.5 if cold else 1.0)
        else:
            into(key, 1.08, cold=1.0 if cold else 0.2, rose=0.0 if cold else 1.0)
        return
    if cold:
        dawn(1.0, "s3")
    else:
        night(cold=0.2, rose=1.0, sky_key="s3", density=0.004, red=1.0)
    eye, target, up = FAST_VIEWS[key]
    look(eye, target, lens=24, fstop=5.6, up=up)
    scraps((14, 0, 4), t, radius=6, height=4, swirl=1.6)


def p10_f2(u, t, b):
    if b < 115.75:
        night(cold=0.0, rose=0.0, density=0.003)
        into("f2", 1.05 + 0.05 * u, yaw=-5 + 10 * u, cold=0.6, rose=0.6)
        return
    night(cold=0.3, rose=0.3)
    look((32, 0, 9), (32, 0, 0), lens=35, up=(-1, 0, 0))
    scraps((32, 0, 4), t, radius=5, height=3, swirl=0.4, fall=ease((b - 115.75) * 4))


def p11_back(u, t, b):
    look((32.1, 0, 7.0), (32.1, 0, 0), lens=35, fstop=8, up=(-1, 0, 0))
    if t >= LAST_BEAT:                                                          # black, and a tiny rose page 0
        scene = bpy.context.scene
        scene.view_settings.view_transform = "Standard"
        S.zero.hide_render = False
        S.zero.location = (0.0, -0.21, -1.0)
        S.zero.scale = (0.012, 0.012, 0.012)
        for p in S.prints.values():
            p.hide_render = True
        return
    night(cold=0.25, rose=0.0)
    light("cover", 0.35)
    S.kv.location, S.kv.rotation_euler = (30.0, 0.0, 0.015), (0.0, -math.pi / 2, 0.0)   # back up: KV', 表裏 reversed
    left = 6 - math.floor((t - at(116)) / (LAST_BEAT - at(116)) * 6)           # the lamps under the letters go out
    for k, lamp in enumerate(getattr(S, "letter_lamps", [])):
        lamp.hide_render = k >= left
    scraps((32.1, 0, 0), t, radius=4.5, height=0.0, fall=1.0, n=110)


SHOTS = [
    (-2, "P0", "paper", p0_paper), (0, "P0", "lights", p0_lights), (4, "P0", "show-through", p0_through),
    (6, "P0", "space", p0_space), (7, "P0", "through the cut", p0_dive),
    (8, "P1", "dawn hall", p1_hall), (12, "P1", "eyes 2D", p1_eyes), (14, "P1", "first drop", p1_drop),
    (16, "P1", "seep", p1_seep), (20, "P1", "top-down, crack", p1_top),
    (24, "P2", "whip, cracks", p2_whip), (28, "P2", "wind", p2_wind), (30, "P2", "lights out", p2_out),
    (31, "P3", "round the print", p3_turn),
    (35, "P4", "chorus", p4_chorus),
    (47, "P5", "spill", p5_spill), (51, "P5", "red water", p5_full), (55, "P5", "dolly zoom", p5_vertigo),
    (56, "P5", "cut", p5_cut),
    (57, "P6", "rain on paper", p6_rain), (61, "P6", "W1 in the rain", p6_w1), (62.5, "P6", "W2 2D", p6_w2),
    (64, "P6", "round the board", p6_side), (66, "P6", "rain to lines", p6_lines),
    (68, "P7", "roll", p7_roll), (70, "P7", "ura", p7_ura), (78, "P7", "reflection", p7_reflect),
    (82, "P7", "crack", p7_crack),
    (83, "P8", "shards", p8_shards),
    (87, "P9", "run", p9_run), (93, "P9", "R0 tears", p9_r0), (97, "P9", "looks back", p9_back),
    (99, "P10", "walls are paper", p10_walls), (103, "P10", "F1 leap", p10_f1), (107, "P10", "second pass", p10_fast),
    (115, "P10", "F2", p10_f2),
    (116, "P11", "back cover", p11_back),
]


# ---------------------------------------------------------------- frames

def main():
    os.makedirs(FRAMES, exist_ok=True)
    starts = [at(s[0]) for s in SHOTS] + [DURATION]
    lo = round(at(FIRST) * FPS) if FIRST is not None else 0
    hi = round(at(LAST) * FPS) if LAST is not None else round(DURATION * FPS)
    path = lambda f: os.path.join(FRAMES, f"f_{f:05d}.png")   # noqa: E731
    todo = []
    for k, (bar, sec, title, fn) in enumerate(SHOTS):
        if ONLY and sec not in ONLY:
            continue
        frames = list(range(round(starts[k] * FPS), round(starts[k + 1] * FPS)))
        if AT:
            frames = sorted({frames[round(a * (len(frames) - 1))] for a in AT}) if frames else []
        elif LIMIT:
            frames = frames[:LIMIT]
        todo += [(f, k) for f in frames if lo <= f < hi and not os.path.exists(path(f))]
    if not todo:
        print("animatic v4: nothing to do")
        return
    scene = setup()
    for done, (f, k) in enumerate(todo):
        bar, sec, title, fn = SHOTS[k]
        t = f / FPS
        S.t, S.b = t, max(bar_at(t), bar)          # rounding can put a shot's first frame just before it
        reset(scene)
        fn((t - starts[k]) / (starts[k + 1] - starts[k]), t, S.b)
        scene.render.stamp_note_text = f"{sec} {title}  |  bar {math.floor(S.b)}.{int(S.b % 1 * 4) + 1}  |  " \
                                       f"{int(t // 60)}:{t % 60:04.1f}"
        scene.render.filepath = path(f)
        if not DRY:
            bpy.ops.render.render(write_still=True)
        if done % 24 == 0:
            print(f"animatic v4: {done + 1}/{len(todo)} frames, now {sec} {title} at {t:.2f} s", flush=True)
    if DRY:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(FRAMES), "animatic_v4_dry.blend"))
    print(f"animatic v4: {len(todo)} frames done")


main()
