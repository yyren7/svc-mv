"""A rough cut of the whole PV (an animatic): the script's 3D shots moving to the song, at low resolution and
frame rate, to judge the pacing and the camera before the pages and the paper cutouts exist.

    blender -b --factory-startup -P scripts/animatic.py -- <part> <frames_dir>
    part: title | s1 | s2 | s3 | s4 | s5_omote | s5_ura | s6          env: FPS=12 SAMPLES=24 WIDTH=640 LIMIT=0

Frames are numbered on the song's clock (f_00000.png is t = 0), so every part drops its shots into the same
folder and the parts can run side by side; frames already there are skipped. scripts/animatic_cut.py joins
the folder with the song. The cut follows section 5 of docs/script_uraomote_v2.md on the downbeats of
assets/audio/urao_timing.json. The pages (P0-P8) and her paper cutouts do not exist yet: the two style frames
stand in for the covers, and every other shot is a set full frame.
"""
import bisect
import json
import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
argv = sys.argv[sys.argv.index("--") + 1:]
PART, FRAMES = argv[0], os.path.abspath(argv[1])
sys.argv = [sys.argv[0], "--", os.path.join(FRAMES, "_unused")]   # the set scripts read their own arguments
import cyc  # noqa: E402
import mvlib as m  # noqa: E402

FPS = int(os.environ.get("FPS", 12))
SAMPLES = int(os.environ.get("SAMPLES", 24))
WIDTH = int(os.environ.get("WIDTH", 640))
LIMIT = int(os.environ.get("LIMIT", 0))          # LIMIT=1: only the first frame of every shot, to check the cameras
TIMING = json.load(open(os.path.join(ROOT, "assets", "audio", "urao_timing.json"), encoding="utf-8"))
DOWN, BEATS, DURATION = TIMING["downbeats"], TIMING["beats"], TIMING["duration"]
RAIN_SPEED = 0.75       # m/s: 9 m/s of real rain at 1:12
BULB_RISE = 0.004       # m/s: the bulbs drift up through the inverted room

# (from bar, to bar, part, shot, options). Bars are downbeat indices (fractions cut between downbeats); "beat"
# punches the camera in on every beat by that much of the distance, "hand" adds the chorus's hand-held shake.
CHORUS = {"beat": 0.03, "hand": True}
EDL = [
    # intro (P0): the cover, then the heart on its altar
    ("start", 4, "title", "cover", {}),
    (4, 8, "s3", "rise", {}),
    # verse 1 (P1): the bedroom wakes; the bell jar
    (8, 11, "s1", "clock", {"beat": 0.02}),
    (11, 15, "s1", "wide", {}),
    (15, 18, "s1", "pov", {}),
    (18, 22, "s2", "macro", {}),
    # pre-chorus (P2): lateral moves, each faster than the last
    (22, 26, "s2", "orbit", {"sweep": 60}),
    (26, 30, "s4", "truck", {}),
    (30, 33, "s5_omote", "wide", {"push": 0.25}),
    # chorus 1 (P3): the heart from a new angle every bar, punched on the beats; the umbrella and the receiver
    (33, 34, "s3", "macro", CHORUS), (34, 35, "s3", "wide", CHORUS), (35, 37, "s3", "arc", {"a": (-70, 70), **CHORUS}),
    (37, 38, "s3", "three", CHORUS), (38, 39, "s3", "macro", CHORUS), (39, 40, "s4", "umbrella", CHORUS),
    (40, 41, "s3", "wide", CHORUS), (41, 43, "s3", "arc", {"a": (70, -70), **CHORUS}), (43, 44, "s3", "three", CHORUS),
    (44, 45, "s3", "macro", CHORUS), (45, 47, "s4", "handset", CHORUS), (47, 48, "s3", "wide", CHORUS),
    (48, 49, "s3", "three", CHORUS), (49, 50, "s3", "macro", CHORUS), (50, 51, "s3", "rise", CHORUS),
    # interlude (P4): the one long take down the alley, then the receiver
    (51, 65, "s4", "long", {}),
    (65, 68, "s4", "handset", {}),
    # verse 2 (P5): the bedroom in its 裏 materials, things beginning to lift
    (68, 72, "s6", "fall", {"t": (0.0, 0.04)}),
    (72, 76, "s6", "desk", {"t": (0.04, 0.08)}),
    (76, 79, "s6", "macro", {"t": (0.08, 0.10)}),
    (79, 82, "s6", "fall", {"t": (0.10, 0.14)}),
    # pre-chorus 2 (P6): every set, half a bar each
    (82, 82.5, "s1", "wide", {}), (82.5, 83, "s2", "orbit", {"sweep": 8}), (83, 83.5, "s3", "macro", {}),
    (83.5, 84, "s4", "long", {}), (84, 84.5, "s5_omote", "wide", {}), (84.5, 85, "s6", "fall", {"t": (0.18, 0.2)}),
    (85, 85.5, "s1", "clock", {}), (85.5, 86, "s3", "three", {}),
    # chorus 2 (P7): the platform, 表 and 裏 bar by bar, and the heart
    (86, 87, "s5_omote", "track", CHORUS), (87, 88, "s5_ura", "track", CHORUS), (88, 89, "s3", "macro", CHORUS),
    (89, 90, "s5_omote", "shoes", CHORUS), (90, 91, "s5_ura", "shoes", CHORUS), (91, 92, "s5_omote", "wide", CHORUS),
    (92, 93, "s5_ura", "wide", CHORUS), (93, 94, "s3", "three", CHORUS), (94, 95, "s5_omote", "track", CHORUS),
    (95, 96, "s5_ura", "track", CHORUS), (96, 97, "s3", "wide", CHORUS), (97, 98, "s5_ura", "wide", CHORUS),
    # outro (P8): the room collapses upward, the camera rolls over to show it hanging; the back cover
    (98, 104, "s6", "fall", {"t": (0.15, 0.45)}),
    (104, 109, "s6", "fall", {"t": (0.45, 0.62), "roll": (0, 180)}),
    (109, 111, "s6", "macro", {"t": (0.62, 0.68)}),
    (111, 115, "s6", "fall", {"t": (0.68, 0.85), "roll": (180, 180)}),
    (115, "end", "title", "back", {}),
]


# ---------------------------------------------------------------- time

def at(bar):
    """Seconds at a downbeat index (fractions fall between downbeats); "start" and "end" are the song's ends."""
    if bar == "start":
        return 0.0
    if bar == "end":
        return DURATION
    i = min(int(bar), len(DOWN) - 2)
    return DOWN[i] + (bar - i) * (DOWN[i + 1] - DOWN[i])


def punch(t, amount, decay=0.12):
    """The beat's impact push: a jump of `amount` of the distance to the subject on every beat, dying away."""
    i = bisect.bisect_right(BEATS, t) - 1
    return amount * math.exp(-(t - BEATS[i]) / decay) if i >= 0 else 0.0


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return Vector(a).lerp(Vector(b), u)


def span(pair, u):
    return pair[0] + (pair[1] - pair[0]) * u


# ---------------------------------------------------------------- the covers (style frames on cards)

def setup_title():
    m.reset()
    cyc.cycles()
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.cycles.use_denoising = False
    world = bpy.data.worlds.new("black")
    world.color = (0.0, 0.0, 0.0)
    scene.world = world
    cards = {}
    for k, name in enumerate(("frame_A", "frame_B")):
        me = bpy.data.meshes.new(name)
        me.from_pydata([(-0.5, -0.28125, 0), (0.5, -0.28125, 0), (0.5, 0.28125, 0), (-0.5, 0.28125, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap").data
        for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uv[i].uv = co
        mat = bpy.data.materials.new(name)
        try:
            mat.use_nodes = True
        except AttributeError:
            pass
        nt = mat.node_tree
        for n in list(nt.nodes):
            if n.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(n)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(ROOT, "renders", f"{name}.png"))
        emit = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"])
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        m._link(ob)
        ob.location.x = 2.0 * k
        cards[name] = (ob, emit)
    return dict(cards=cards)


def title_cover(c, u, t, kw):
    return dict(card="frame_A", ortho=1.0 - 0.06 * ease(u), strength=1.0)


def title_back(c, u, t, kw):
    fade = ease((t - (DURATION - 1.4)) / 1.2)
    return dict(card="frame_B", ortho=0.94 + 0.06 * ease(u), strength=1.0 - fade)


# ---------------------------------------------------------------- S1 the bedroom

def setup_s1():
    import s1_bedroom as S1
    info = S1.build("omote")
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("alarm_clock_01_glass", "window_glass", "curtain")
    n = (info["dial_ob"].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return dict(dial=Vector(info["dial"]), n=n, pillow=Vector(info["pillow"]))


def s1_clock(c, u, t, kw):
    side = c["n"].cross(Vector((0.0, 0.0, 1.0))).normalized()     # slides past the clock at 1 cm/s
    eye = c["dial"] + c["n"] * 0.10 + Vector((0.0, 0.0, 0.012)) + side * (0.02 * (2 * u - 1))
    return dict(eye=eye, target=c["dial"], lens=100, fstop=8, focus=c["dial"], hide=("haze",))


def s1_wide(c, u, t, kw):
    eye = lerp((0.02, -0.38, 0.14), (0.02, -0.52, 0.16), ease(u))   # pulls back until the set box shows
    return dict(eye=eye, target=Vector((0.0, 0.02, 0.09)), lens=24, fstop=8, focus=Vector((0.0, 0.0, 0.05)),
                hide=("rim_pink",))


def s1_pov(c, u, t, kw):
    window = Vector((-0.155, 0.01, 0.105))
    far = (window - c["pillow"]).length          # the focus walks from the pillow to the printed sky in 1.5 s
    return dict(eye=c["pillow"], target=window, lens=50, fstop=5.6, focus=0.03 + (far - 0.03) * ease((u - 0.3) / 0.33),
                hide=("haze",), exposure=-1.2)


# ---------------------------------------------------------------- S2 the bell jar

def setup_s2():
    import s2_belljar as S2
    info = S2.build(0.0)
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("jar", "petri")
    return dict(bulb=Vector(info["bulb"]), top=S2.TOP, r=S2.JAR_R)


def s2_macro(c, u, t, kw):
    top = c["top"]
    eye = Vector((top.x + 0.006 + 0.004 * (u - 0.5), top.y - c["r"] - 0.025, top.z + 0.02))
    return dict(eye=eye, target=c["bulb"], lens=100, fstop=32, focus=(c["bulb"] - eye).length + 0.0045, exposure=-0.9)


def s2_orbit(c, u, t, kw):
    top = c["top"]
    centre = Vector((top.x, top.y, top.z + 0.085))
    a0, r = math.atan2(-0.23 - top.y, 0.27 - top.x), math.hypot(0.27 - top.x, -0.23 - top.y)
    a = a0 + math.radians(kw.get("sweep", 60)) * ease(u)
    eye = Vector((top.x + r * math.cos(a), top.y + r * math.sin(a), 0.12 + 0.08 * ease(u)))
    return dict(eye=eye, target=centre, lens=35, fstop=8, focus=(Vector((top.x, top.y, eye.z)) - eye).length - c["r"])


# ---------------------------------------------------------------- S3 the workshop

def setup_s3():
    import s3_workshop as S3
    S3.build()
    bt = S3.BENCH_TOP
    hc = Vector((0.0, 0.0, bt + 0.033))
    return dict(bt=bt, hc=hc, seam=Vector((0.0, -0.011, hc.z + 0.002)))


def s3_rise(c, u, t, kw):
    eye = Vector((0.0, -0.34, c["bt"] + 0.035 + 0.155 * ease(u)))    # table height up to 25 degrees down
    return dict(eye=eye, target=c["hc"] + Vector((0.0, 0.0, 0.01)), lens=50, fstop=5.6, focus=c["seam"])


def s3_macro(c, u, t, kw):
    start = Vector((0.03, -0.17, c["seam"].z + 0.014))
    return dict(eye=start.lerp(c["seam"], 0.08 * u), target=c["seam"], lens=100, fstop=8, focus=c["seam"])


def s3_wide(c, u, t, kw):
    bt = c["bt"]
    return dict(eye=lerp((0.0, -0.36, bt + 0.07), (0.0, -0.33, bt + 0.076), u), target=Vector((0.0, 0.08, bt + 0.05)),
                lens=50, fstop=5.6, focus=c["seam"])


def s3_three(c, u, t, kw):
    bt = c["bt"]
    return dict(eye=lerp((-0.16, -0.2, bt + 0.11), (-0.15, -0.19, bt + 0.105), u), target=Vector((0.0, 0.02, bt + 0.03)),
                lens=85, fstop=2.0, focus=c["seam"], hide=("haze",))


def s3_arc(c, u, t, kw):
    a = math.radians(span(kw["a"], ease(u)))      # round the front of the heart: 表 and 裏 trade sides
    eye = c["hc"] + Vector((0.2 * math.sin(a), -0.2 * math.cos(a), 0.02))
    return dict(eye=eye, target=c["hc"], lens=50, fstop=5.6, focus=c["seam"])


# ---------------------------------------------------------------- S4 the phone booth in the rain

def setup_s4():
    import s4_booth as S4
    S4.build()
    bpy.context.view_layer.update()
    hs = bpy.data.objects["handset"]
    handset = sum((hs.matrix_world @ Vector(co) for co in hs.bound_box), Vector()) / 8
    can = bpy.data.objects["umbrella_canopy"]
    umb = sum((can.matrix_world @ v.co for v in can.data.vertices), Vector()) / len(can.data.vertices)
    rain = bpy.data.objects["rain"]
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("rain", "booth_glass", "door_glass", "umbrella_canopy", "umbrella_water",
                                       "umbrella_drops")
    return dict(handset=handset, umb=umb, rain=rain, rain0=[v.co.copy() for v in rain.data.vertices],
                booth=(S4.BOOTH, S4.BW, S4.BH))


def animate_s4(c, t):
    """The rain falls: every streak drops at rain speed and wraps round its 30 cm column; none inside the booth."""
    booth, bw, bh = c["booth"]
    co = []
    for p in c["rain0"]:
        z = 0.002 + (p.z - 0.002 - RAIN_SPEED * t) % 0.298
        if abs(p.x - booth.x) < bw / 2 + 0.01 and abs(p.y - booth.y) < bw / 2 + 0.01 and z < bh + 0.02:
            z = -1.0
        co += (p.x, p.y, z)
    c["rain"].data.vertices.foreach_set("co", co)
    c["rain"].data.update()


def s4_long(c, u, t, kw):
    h, e = c["handset"], ease(u)
    eye = lerp((-0.075, -0.23, 0.03), (-0.06, 0.0, 0.034), e)          # 23 cm in the 21 s of the interlude
    target = lerp((-0.07, 0.20, h.z - 0.02), (h.x - 0.02, h.y, h.z - 0.01), e)
    near, far = (c["umb"] - eye).length, (h - eye).length               # focus from the umbrella's beads to the booth
    return dict(eye=eye, target=target, lens=35, fstop=5.6, focus=near + (far - near) * ease((u - 0.1) / 0.35))


def s4_handset(c, u, t, kw):
    h = c["handset"]
    eye = lerp(h + Vector((-0.03, -0.19, 0.012)), h + Vector((-0.027, -0.17, 0.012)), ease(u))
    return dict(eye=eye, target=h + Vector((0.0, 0.0, 0.004)), lens=100, fstop=8, focus=h)


def s4_truck(c, u, t, kw):
    e = ease(u)
    return dict(eye=lerp((-0.13, -0.12, 0.045), (0.07, -0.12, 0.045), e), target=lerp((-0.04, 0.18, 0.06), (0.03, 0.18, 0.06), e),
                lens=50, fstop=5.6, focus=c["handset"])


def s4_umbrella(c, u, t, kw):
    umb = c["umb"]
    eye = lerp(umb + Vector((0.02, -0.21, 0.05)), umb + Vector((0.018, -0.19, 0.046)), u)
    return dict(eye=eye, target=umb + Vector((-0.005, 0.0, 0.012)), lens=40, fstop=8, focus=umb)


# ---------------------------------------------------------------- S5 the platform (表 at sunset, 裏 at night)

def setup_s5(pal):
    import s5_platform as S5
    info = S5.build(pal)
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("window_glass", "haze")
    return dict(toe=Vector(info["toe"]), shoes=Vector(S5.SHOES), edge=S5.EDGE, ph=S5.PH)


def s5_track(c, u, t, kw):
    end = Vector((0.115, c["edge"] + 0.048, c["ph"] + 0.016))         # low along the tactile strip, to the shoes
    look = c["shoes"] + Vector((0.008, 0.0, 0.005)) - end
    eye = lerp(end + Vector((0.22, 0.0, 0.0)), end, ease(u))
    return dict(eye=eye, target=eye + look, lens=24, fstop=8, focus=c["shoes"] + Vector((0.0, 0.0, 0.004)))


def s5_shoes(c, u, t, kw):
    toe = c["toe"]
    eye = lerp(toe + Vector((0.09, -0.004, 0.04)), toe + Vector((0.08, -0.0035, 0.036)), u)
    return dict(eye=eye, target=toe + Vector((0.006, 0.004, 0.0)), lens=100, fstop=11, focus=toe)


def s5_wide(c, u, t, kw):
    ph = c["ph"]
    eye = lerp((0.72, -0.09, ph + 0.075), (0.72 - kw.get("push", 0.08), -0.09, ph + 0.072), ease(u))
    return dict(eye=eye, target=Vector((-0.15, 0.03, ph + 0.075)), lens=35, fstop=8, focus=Vector((-0.12, 0.06, ph + 0.04)))


# ---------------------------------------------------------------- S6 the inverted room

def setup_s6():
    import s6_inverted as S6
    info = S6.build(0.7, lift=False)
    groups = []
    for objs, rise, tumble, seed in info["groups"]:
        rnd = random.Random(seed)                 # the same draws as S6.lift_xf
        ang = [rnd.uniform(-1, 1) * tumble for _ in range(3)]
        piv = sum((o.matrix_world.translation for o in objs), Vector()) / len(objs)
        groups.append(dict(objs=[(o, o.matrix_world.copy()) for o in objs], piv=piv, rise=rise, ang=ang, seed=seed))
    c = dict(groups=groups, dial=info["dial"], cloud=info["cloud"], h=S6.H, face=0.0)
    lift(c, 0.55)                                 # the clock's face-out turn as the still finds it at t = 0.55
    c["face"], _ = S6.face_out(info["dial"])
    lift(c, 0.0)
    c["cloud0"] = [v.co.copy() for v in info["cloud"].data.vertices]
    return c


def lift(c, t):
    """Every group at time t of the collapse; the clock eases into its face-out turn as it rises."""
    for g in c["groups"]:
        xf = Matrix.Translation(g["piv"] + Vector((0.0, 0.0, g["rise"] * t))) \
            @ Euler([math.radians(a * t) for a in g["ang"]]).to_matrix().to_4x4() @ Matrix.Translation(-g["piv"])
        if g["seed"] == 2 and c["face"]:
            p = g["piv"] + Vector((0.0, 0.0, g["rise"] * t))
            xf = Matrix.Translation(p) @ Matrix.Rotation(c["face"] * min(1.0, t / 0.55), 4, "Z") @ Matrix.Translation(-p) @ xf
        for o, base in g["objs"]:
            o.matrix_world = xf @ base
    bpy.context.view_layer.update()


def animate_s6(c, t):
    """The bulbs drift up through the room and come round again from the floor."""
    h, co = c["h"], []
    for p in c["cloud0"]:
        co += (p.x, p.y, (p.z + BULB_RISE * t) % h)
    c["cloud"].data.vertices.foreach_set("co", co)
    c["cloud"].data.update()


def s6_fall(c, u, t, kw):
    lift(c, span(kw["t"], u))
    eye = lerp((0.03, -0.40, 0.11), (0.03, -0.37, 0.11), ease(u))
    return dict(eye=eye, target=Vector((0.0, 0.03, 0.10)), lens=50, fstop=8, focus=Vector((0.0, 0.03, 0.10)),
                roll=span(kw.get("roll", (0, 0)), ease(u)))


def s6_desk(c, u, t, kw):
    lift(c, span(kw["t"], u))
    eye = lerp((0.14, -0.22, 0.09), (0.13, -0.20, 0.085), ease(u))
    return dict(eye=eye, target=Vector((0.10, -0.04, 0.06)), lens=50, fstop=5.6, focus=Vector((0.10, -0.04, 0.06)))


def s6_macro(c, u, t, kw):
    lift(c, span(kw["t"], u))
    dial = c["dial"].matrix_world.translation.copy()
    face = (c["dial"].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    eye = dial + face * 0.09 + Vector((0.0, 0.0, 0.01))
    return dict(eye=eye, target=dial, lens=100, fstop=8, focus=(eye - dial).length, hide=("haze",))


# ---------------------------------------------------------------- the run

SETUP = {"title": setup_title, "s1": setup_s1, "s2": setup_s2, "s3": setup_s3, "s4": setup_s4,
         "s5_omote": lambda: setup_s5("omote"), "s5_ura": lambda: setup_s5("ura"), "s6": setup_s6}
ANIMATE = {"s4": animate_s4, "s6": animate_s6}
SHOTS = {"title": {"cover": title_cover, "back": title_back},
         "s1": {"clock": s1_clock, "wide": s1_wide, "pov": s1_pov},
         "s2": {"macro": s2_macro, "orbit": s2_orbit},
         "s3": {"rise": s3_rise, "macro": s3_macro, "wide": s3_wide, "three": s3_three, "arc": s3_arc},
         "s4": {"long": s4_long, "handset": s4_handset, "truck": s4_truck, "umbrella": s4_umbrella},
         "s5": {"track": s5_track, "shoes": s5_shoes, "wide": s5_wide},
         "s6": {"fall": s6_fall, "desk": s6_desk, "macro": s6_macro}}


def aim(cam, st, kw, t):
    """Put the camera where the shot says, with the chorus's beat punch and hand shake, and focus it."""
    eye, target = Vector(st["eye"]), Vector(st["target"])
    if kw.get("beat"):
        eye = eye + (target - eye) * punch(t, kw["beat"])
    if kw.get("hand"):
        d = target - eye
        right = d.cross(Vector((0.0, 0.0, 1.0))).normalized()
        up = right.cross(d).normalized()
        a = 0.006 * d.length * 36.0 / st["lens"]       # 0.6 % of the frame width
        target = target + right * a * (math.sin(t * 10.7) + 0.6 * math.sin(t * 24.3 + 1.3)) \
            + up * a * (math.sin(t * 14.1 + 0.5) + 0.5 * math.sin(t * 29.5 + 2.1))
    cam.location = eye
    q = (target - eye).to_track_quat("-Z", "Y")
    if st.get("roll"):
        q = q @ Quaternion((0.0, 0.0, 1.0), math.radians(st["roll"]))
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = q
    cam.data.lens = st["lens"]
    cam.data.dof.aperture_fstop = st["fstop"]
    bpy.context.view_layer.update()
    f = st.get("focus")
    if isinstance(f, (int, float)):
        cam.data.dof.focus_object = None
        cam.data.dof.focus_distance = f
    elif f is not None:
        cyc.autofocus(cam, f, verbose=False)


def main():
    os.makedirs(FRAMES, exist_ok=True)
    shots = [(at(b0), at(b1), shot, kw) for b0, b1, part, shot, kw in EDL if part == PART]
    path = lambda f: os.path.join(FRAMES, f"f_{f:05d}.png")   # noqa: E731
    todo = [(t0, t1, shot, kw, [f for f in range(round(t0 * FPS), round(t1 * FPS)) if not os.path.exists(path(f))])
            for t0, t1, shot, kw in shots]
    todo = [(t0, t1, shot, kw, frames[:LIMIT] if LIMIT else frames) for t0, t1, shot, kw, frames in todo if frames]
    if not todo:
        print(f"animatic {PART}: nothing to do")
        return
    c = SETUP[PART]()
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, WIDTH * 9 // 16
    scene.render.resolution_percentage = 100
    scene.render.use_persistent_data = True
    scene.cycles.samples = 8 if PART == "title" else SAMPLES
    if PART == "title":
        cam = bpy.data.objects.new("anim_cam", bpy.data.cameras.new("anim_cam"))
        m._link(cam)
        cam.data.type = "ORTHO"
    else:
        cam = cyc.camera("anim_cam", (0.0, -1.0, 0.0), (0.0, 0.0, 0.0), 50, 8.0)
    scene.camera = cam
    family = PART.split("_")[0] if PART.startswith("s5") else PART
    done = 0
    for t0, t1, shot, kw, frames in todo:
        hidden = []
        for f in frames:
            t = f / FPS
            u = (t - t0) / max(1e-6, t1 - t0)
            if PART in ANIMATE:
                ANIMATE[PART](c, t)
            st = SHOTS[family][shot](c, u, t, kw)
            if PART == "title":
                ob, emit = c["cards"][st["card"]]
                cam.location = (ob.location.x, 0.0, 1.0)
                cam.data.ortho_scale = st["ortho"]
                emit.inputs["Strength"].default_value = st["strength"]
            else:
                if not hidden:
                    hidden = [scene.objects[n] for n in st.get("hide", ()) if n in scene.objects]
                    for ob in hidden:
                        ob.hide_render = True
                scene.view_settings.exposure = st.get("exposure", 0.0)
                aim(cam, st, kw, t)
            scene.render.filepath = path(f)
            bpy.ops.render.render(write_still=True)
            done += 1
            if done % 24 == 0:
                print(f"animatic {PART}: {done} frames, now {shot} at {t:.2f} s", flush=True)
        for ob in hidden:
            ob.hide_render = False
    print(f"animatic {PART}: {done} frames done")


main()
