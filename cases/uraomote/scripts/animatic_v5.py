"""v5 animatic: script_v5.md section 5 in the world of v5_world.py (the sky, the sea to the horizon, the one wall
with its window and 表 裏 cut through it, the glass of water on the sill), cut on the song's downbeats and
rendered small to judge the pacing, the cameras and the dimension events before the real render. Nothing on screen is at rest: alive() runs last on every frame and
moves the camera, her and the light by the music (see there); a shot only says how much (_T.gain, _T.wind, _T.blur).

She is in the world two ways (script_v5 section 2), both from the pictures painted into the world's own plates
(cases/uraomote/scripts/v5_plates.py, jobs/v5_t*.py):
- figure(): the picture's cut-out standing (sitting, lying, leaping) in the world where its plate had her, paper:
  the side is a line, the back is bare.
- into(): the camera inside a picture. The picture stands on its plate camera's image plane, half a metre before
  the lens and exactly as wide as the plate's view, its sky and water cut through to the world's (the plate's own
  plane mask). The camera stays at the plate's eye and may turn, tilt and zoom: whatever it looks at, the real sky
  and sea show where the picture has them, with clouds, sun, rain and rings. The wall is put away behind it.

    blender -b --factory-startup -P cases/uraomote/scripts/animatic_v5.py -- <frames_dir> [first_bar last_bar]
    env: FPS=12 SAMPLES=16 WIDTH=640, LIMIT, AT=0.5, ONLY=P4,P5, DEVICE=CPU, DRY=1 (as animatic.py)
    python scripts/cut.py <frames_dir> cases/uraomote/audio/urao_mix.m4a <out.mp4> 12

Every frame starts from the world at rest (reset(): every light off, every figure and picture put away, the sea
still) and the shot sets what it needs, so any frame renders alone and bar ranges run side by side.
"""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

os.environ.setdefault("ART", "v5")                       # the pictures painted into the world (before v5_world)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case as C  # noqa: E402
import animatic as AN  # noqa: E402
import assets as A  # noqa: E402
import cyc  # noqa: E402
import hybrid as H  # noqa: E402
import hybrid_fx as fx  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import paper as P  # noqa: E402
import v5_world as W  # noqa: E402
import v5_plates as PL  # noqa: E402

FRAMES, FIRST, LAST = AN.args(os.path.join(C.RENDERS, "animatic_v5", "frames"))
FPS, SAMPLES = AN.FPS, AN.SAMPLES
CLK = AN.Clock(os.path.join(C.AUDIO, "urao_timing.json"))
at, bar_at, punch = CLK.at, CLK.bar_at, CLK.punch
ease, clamp, put, energy = AN.ease, AN.clamp, AN.put, AN.energy
ROSE, GLOW, COLD = W.ROSE, W.GLOW, "#7C94FF"
S = W.S                                                   # the world's registry; the animatic adds to it
PUNCH = [(24, 28), (35, 47), (51, 55), (83, 116)]         # bars with the impact push on every beat
# how much the film moves from this bar on: handheld, kicks, her hair, the light's jump on the beat
ENERGY = [(-2, 0.1), (8, 0.25), (24, 0.7), (31, 0.5), (35, 1.0), (56, 0.0), (57, 0.3), (68, 0.25), (83, 1.0), (87, 1.2),
          (97, 0.8), (99, 1.2), (107, 1.5), (116, 0.03)]
_TIMING = json.load(open(os.path.join(C.AUDIO, "urao_timing.json"), encoding="utf-8"))
ONSET, LOUD = _TIMING["onset"], _TIMING["loud_mix"]
ONSET_TOP = sorted(ONSET)[int(len(ONSET) * 0.98)] or 1.0
LOUD_TOP = max(LOUD) or 1.0
DUTCH = (87, 99)                                          # bars with the Dutch angle, ±12° turning each bar
SKY_IN_PICTURE = 0.75                                     # the sky's strength behind a picture the camera is inside
SKY_TURN = 35.0                                           # degrees
D_SHEET = 0.5                                             # a picture the camera is inside: this far before the lens

# the picks (art/v5): she stands in the world as these cut-outs, at their plates' places
FIG = {"kv": ("v5_kv_213s", "kv"), "kvn": ("v5_kvn_211n90", "kv"), "q1s": ("v5_q1s_211s", "q1s"),
       "q1u": (os.environ.get("Q1U", "v5_q1u_211n90"), "q1s"), "w1": ("v5_w1_217s", "w1"),
       "r0": ("v5_r0_213s", "r0"), "u2": ("v5_u2_211s", "u2"), "f1": ("v5_f1_215s", "f1")}
# the pictures the camera enters: (picture, plate); the v4 close-ups have no plate (the shot places the camera)
INTO = {"a1": ("v5_a1_217s_c_pq70", "a1"), "a1w": ("v5_a1w_211s_pq70", "a1w"),
        "a2": (os.environ.get("A2", "v5_a2_215s"), "a2"), "a3": ("v5_a3_213s_pq70", "a3"),
        "a4": ("v5_a4_211s_c_pq70", "a4"), "a5": ("v5_a5_213s_c_pq70", "a5"),
        "a5o": (os.environ.get("A5O", "v5_a5o_213"), "a5"), "u1": ("v5_u1_211s_c_pq70", "u1"),
        "u2": ("v5_u2_211s_c_pq70", "u2"), "r0": ("v5_r0_213s", "r0"), "f1": ("v5_f1_215s", "f1"),
        "kvn": ("v5_kvn_211n90", "kvn"),
        "c1": ("v4_c1_211", None), "c2": ("v4_c2_211", None), "c3": ("v4_c3_211", None), "c4": ("v4_c4_211", None),
        "w2": ("v4_w2_211", None), "u4": ("v4_u4_211", None), "f2": ("v4_f2_211", None)}
CHORUS = ["c1", "c2", "c3", "c4"]
FIG_H = {"u2": 0.85, "f1": 1.85, "r0": 1.55}              # the figure's box in metres (sitting, leaping, running)
LETTERS_AT = Vector((0.0, 2.5, 3.65))                     # between 表 and 裏
STILL_EYE = Vector((-16.0, 3.5, 0.8))                     # the dawn still's camera: the sun shines at it through them


class _T:
    t = b = 0.0
    gain = 1.0                                            # her hair and head, this shot (reset to 1 each frame)
    wind = (0.0, 0.0)                                     # the wind on her hair, in her heights
    blur = None                                           # this frame's speed blur: dict(scale=, amount=, direction=)
    flutter = 1.0                                         # how much a paper figure turns in the air


# ---------------------------------------------------------------- building

def scene_settings():
    """animatic.scene() without its reset (v5_world.build() made the scene): small, few samples, no caustics."""
    sc = bpy.context.scene
    sc.cycles.samples = SAMPLES
    sc.cycles.caustics_refractive = sc.cycles.caustics_reflective = False
    if os.environ.get("DEVICE") == "CPU":
        sc.cycles.device = "CPU"
        sc.cycles.denoising_use_gpu = False
    sc.render.resolution_x, sc.render.resolution_y = AN.WIDTH, AN.WIDTH * 9 // 16
    sc.render.resolution_percentage = 100
    sc.render.use_persistent_data = True
    return sc


def deep_water():
    """The sea's depth: the bed let down to 12 m and a body of dark water over it (absorbing, a little scattering,
    for the light that falls through the surface in shafts), the ink's and the camera's room under the surface.
    From above it looks as the 3 cm of near-black water did. The surface the camera sees from below is a copy of
    the sea that casts no shadow, so the sun reaches the deep (the sea itself blocks it, being refractive)."""
    bed = bpy.data.objects["seabed"]
    bed.location.z = -12.0
    mat = bpy.data.materials.new("deep")
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = m.srgb("#3E6E84")
    vol.inputs["Absorption Color"].default_value = m.srgb("#0A1A26")
    vol.inputs["Density"].default_value = 0.06
    vol.inputs["Anisotropy"].default_value = 0.55
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    S.deep_vol = vol
    S.deep = A.rounded_box("deep", (140.0, 140.0, 11.98), 0.0, [mat])
    S.deep.location = (-30.0, 0.0, -6.0 - 0.01)
    S.deep.visible_shadow = False
    S.sea_under = S.sea.copy()
    S.sea_under.data = S.sea.data
    S.sea_under.name = "sea_under"
    bpy.context.scene.collection.objects.link(S.sea_under)
    S.sea_under.visible_shadow = False
    bsdf = next(n for n in S.sea.data.materials[0].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    S.sea_base = bsdf.inputs["Base Color"]
    S.SEA_BASE = tuple(S.sea_base.default_value)
    S.sea_metal = bsdf.inputs["Metallic"]
    # the red that fills the deep from bar 41: a wide soft lamp low in the water, under the wall
    S.red_deep = cyc.area_light("red_deep", (-6.0, 0.0, -7.0), (-6.0, 0.0, 0.0), 30.0, 2000, 0.0, color=ROSE)


def wall_parts():
    names = ("wall", "pane", "sill", "glass", "glass_water")
    return [ob for ob in bpy.context.scene.objects
            if ob.name in names or ob.name.startswith(("jamb", "mullion", "transom"))]


def lights():
    """Every lamp of the film, off; the shots turn on theirs."""
    eye = Vector((-16.0, 3.5, 0.8))
    S.sun_dir = (eye - Vector((0.0, 2.5, 3.6))).normalized()
    S.sun = W.sun(S.sun_dir, 0.0, 6200, disc=40.0)
    S.sun.rotation_mode = "QUATERNION"
    S.sun_disc = bpy.data.objects["sun_disc"]
    S.fill = cyc.area_light("fill", (-6.0, -4.8, 3.0), (-1.6, -1.2, 1.2), 4.0, 9000, 0.0, color="#9FB2D8")
    S.fill.visible_glossy = False
    S.window_glow = cyc.area_light("window_glow", (W.WALL_T + 0.9, W.WIN_Y, (W.WIN_Z0 + W.WIN_Z1) / 2),
                                   (-6.0, W.WIN_Y, 1.5), 2.0, 2000, 0.0, size_y=3.4, color=ROSE)
    S.window_glow.visible_glossy = False
    S.letters_glow = cyc.area_light("letters_glow", (W.WALL_T + 1.0, 2.5, 3.6), (-12.0, 2.5, 1.0), 1.2, 2000, 0.0,
                                    size_y=2.6, color=ROSE)
    S.letters_glow.visible_glossy = False
    S.key = cyc.area_light("key", (-9.5, -2.5, 2.4), (-6.0, 0.6, 1.1), 1.5, 9000, 0.0, color=COLD)
    S.key.visible_glossy = False
    S.cold = cyc.area_light("cold", (-6.5, -2.0, 2.6), (-3.0, 0.0, 1.0), 2.0, 9000, 0.0, color=COLD)
    S.cold.visible_glossy = False
    S.rose = cyc.area_light("rose", (-1.4, 1.5, 2.2), (-3.0, 0.0, 0.9), 2.0, 2000, 0.0, color=ROSE)
    S.rose.visible_glossy = False
    S.sun_cold = W.sun(Vector((1.0, 0.2, -0.45)), 0.0, 9000, name="sun_cold", disc=30.0)
    S.sun_cold.data.color = m.srgb(COLD)[:3]
    S.sun_rose = W.sun(Vector((-1.0, 0.2, -0.35)), 0.0, 2000, name="sun_rose", disc=30.0)
    S.sun_rose.data.color = m.srgb(ROSE)[:3]
    S.discs = [bpy.data.objects[n] for n in ("sun_cold_disc", "sun_rose_disc")]
    S.lamps = [S.sun, S.fill, S.window_glow, S.letters_glow, S.key, S.cold, S.rose, S.sun_cold, S.sun_rose, S.red_deep]


def letters_back():
    """A rose panel close behind 表 裏, seen through the letters and mirrored by the water (the lamp behind them
    lights nothing the camera sees: at night the letters were holes onto a dark sky, and the back cover was black)."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(W.WALL_T + 0.35, 2.5, 3.65), rotation=(0.0, math.pi / 2, 0.0))
    ob = bpy.context.active_object
    ob.name = "letters_back"
    ob.scale = (3.2, 1.8, 1.0)
    mat, em = fx.emission_mat("letters_back", GLOW, 0.0)
    ob.data.materials.append(mat)
    ob.visible_shadow = ob.visible_diffuse = False
    S.letters_back, S.letters_em = ob, em


def shutter():
    """A black board in the window opening: the window stays dark while the letters light first (P0.2)."""
    mat = A._principled("shutter", **{"Base Color": (0.0, 0.0, 0.0, 1.0), "Roughness": 1.0})[0]
    S.shutter = A.rounded_box("shutter", (0.05, W.WIN_W, W.WIN_Z1 - W.WIN_Z0), 0.0, [mat])
    S.shutter.location = (W.WALL_T / 2 + 0.06, W.WIN_Y, (W.WIN_Z0 + W.WIN_Z1) / 2)


def figures():
    """The cut-outs, each where its plate had her, put away until a shot shows one."""
    S.figs, S.fig_home = {}, {}
    for key, (pic, plate) in FIG.items():
        x, y, how = PL.PLATES[plate]["her"]
        if key == "q1u":                                       # her 裏: lit by itself, the mirror alone sees it
            ob = mirror_only(W.figure("fig_q1u", pic, x - 0.002, y, emission=6.0))
        else:
            ob = W.figure(f"fig_{key}", pic, x, y, height=FIG_H.get(key, 1.62), bottom=1.7 if how == "leap" else 0.012)
        ob.hide_render = True
        S.figs[key] = ob
        S.fig_home[key] = (ob.location.copy(), ob.rotation_euler.copy())
    # her 表 at the water line is never mirrored as herself: the water shows the 裏 twin, or (the flash back, P7.3)
    # this glossy-only copy of the 表 one (ray visibility switched per frame does not take under persistent data)
    S.figs["q1s"].visible_glossy = False
    x, y, _ = PL.PLATES["q1s"]["her"]
    S.figs["q1m"] = mirror_only(W.figure("fig_q1m", FIG["q1s"][0], x - 0.002, y, emission=2.5))
    S.figs["q1m"].hide_render = True
    S.fig_home["q1m"] = (S.figs["q1m"].location.copy(), S.figs["q1m"].rotation_euler.copy())


def mirror_only(ob):
    for attr in ("visible_camera", "visible_diffuse", "visible_transmission", "visible_shadow"):
        setattr(ob, attr, False)
    return ob


def facing(ob, eye):
    """Turn figure `ob` about its top edge to face a camera at `eye`."""
    loc = ob.location
    ob.rotation_euler.z = math.atan2(eye[1] - loc.y, eye[0] - loc.x) - math.pi


def show(key, x=None, y=None, eye=None, yaw=None, lift=0.0):
    """Figure `key` in the world (moved to x, y; turned to face `eye`, or by `yaw` degrees)."""
    ob = S.figs[key]
    ob.hide_render = False
    loc, rot = S.fig_home[key]
    ob.location = (loc.x if x is None else x, loc.y if y is None else y, loc.z + lift)
    ob.rotation_euler = rot.copy()
    if eye is not None:
        facing(ob, eye)
    elif yaw is not None:
        ob.rotation_euler.z = math.radians(yaw)
    return ob


def plate_frame(plate):
    """A plate camera's frame: (eye, forward, right, up, lens, half-width tan, half-height tan) with the plate's
    sensor fit (36 mm on its longer side)."""
    p = PL.PLATES[plate]
    eye, target = Vector(p["eye"]), Vector(p["target"])
    q = (target - eye).to_track_quat("-Z", "Y")            # as cyc.camera aims it (a plate straight down: U1)
    f, r, u = q @ Vector((0.0, 0.0, -1.0)), q @ Vector((1.0, 0.0, 0.0)), q @ Vector((0.0, 1.0, 0.0))
    w, h = p["size"]
    tw = 18.0 / p["lens"] * (1.0 if w >= h else w / h)
    th = 18.0 / p["lens"] * (h / w if w >= h else 1.0)
    return eye, f, r, u, p["lens"], tw, th


def into_sheets():
    """Each picture the camera enters, as a sheet on its plate camera's image plane D_SHEET before the eye, 2% over
    the plate's view, giving off its picture, its sky and water cut through (the plate's own plane mask)."""
    S.into, S.into_mats = {}, {}
    for key, (pic, plate) in INTO.items():
        if not os.path.exists(P.path(pic)):
            print("into: no picture", pic, "for", key)
            continue
        img = P.image(pic)
        w, h = img.size
        size = (1.0, h / w)
        mat = H.world_mat(f"into_{key}", pic, size, emission=1.0)
        ob = P.sheet(f"into_{key}", 0.0, 0.0, mat, 7, top=0.0, grid=(48, 28) if w >= h else (28, 48), size=size,
                     clips=False, flat=0.0)
        if plate:
            place_on_plate(ob, plate, h / w)
        ob.hide_render = True
        ob.visible_shadow = False
        S.into[key] = ob
        S.into_mats[key] = next(n for n in mat.node_tree.nodes if n.name == "lit")


def place_on_plate(ob, plate, aspect, d=D_SHEET, over=1.02):
    eye, f, r, u, lens, tw, th = plate_frame(plate)
    s = 2 * d * tw * over                                      # the sheet is 1 m wide: scale to the view's width
    centre = eye + f * d
    rot = Matrix((f, -r, u)).transposed()                      # sheet X (its normal) along the view, Y to the left
    #                                                            (f, r, u from the plate's own aim)
    ob.matrix_world = Matrix.Translation(centre + u * (aspect * s / 2)) @ rot.to_4x4() @ Matrix.Scale(s, 4)


def effects():
    S.ink, S.burst = fx.ink_volume("ink", 1.0), fx.ink_volume("burst", 7.0)
    S.rain_ob, S.rain_em = fx.rain()
    S.dust, S.mote = fx.motes()
    S.conf, S.scrap = fx.confetti(P.path(FIG["kv"][0]))
    S.cracks = {
        # P1.6 / P2: a crack of light along the water from the red, and across the wall and the window
        "sea": fx.crack("crack_sea", 41, (-2.0, -0.6, 0.004), (-1.0, 0.25, 0.0), (0.25, 1.0, 0.0), 9.0, width=0.05),
        "wall": fx.crack("crack_wall", 42, (-0.004, 1.2, 4.9), (0.0, 0.3, -1.0), (0.0, 1.0, 0.3), 3.2, width=0.03),
        "glass": fx.crack("crack_glass", 43, (W.WALL_T / 2 - 0.02, W.WIN_Y + 0.6, 3.6), (0.0, -0.6, -1.0),
                          (0.0, 1.0, -0.6), 2.2, width=0.02),
        "feet": fx.crack("crack_feet", 44, (-3.0, 0.0, 0.004), (-1.0, -0.4, 0.0), (0.4, -1.0, 0.0), 7.0, width=0.04),
    }
    pics = {k: P.path(INTO[k][0]) for k in ("a1", "a3", "a4", "a5", "u1", "u2") if k in S.into}
    pics = {"hero": P.path(FIG["q1s"][0]), **pics}
    S.shards = fx.shards(pics, "hero", (1.4, 2.5), grid=(8, 12), n=160, seed=13,
                         home=((-12.0, -2.0), (-4.5, 4.5), (0.2, 4.2)), line=(-5.0, 0.15))
    S.halves = fx.halves(S.into["r0"]) if "r0" in S.into else []
    S.lifted = lifted_sea()
    make_wall_pieces()
    big = random.Random(31)
    faces = {k: H.LIVE[S.into[k].material_slots[0].material.name]["meta"] for k in ("a1", "a3", "a4", "a5", "u1", "u2")
             if k in S.into and S.into[k].material_slots[0].material.name in H.LIVE}
    for s, key in zip(S.shards, fx.SHARD_KEYS):            # the loose shards large, each a moment of her: her face and hair
        if s.get("grid") is None:
            s["big"] = big.uniform(1.6, 3.6)
            if key in faces:
                shard_on_face(s["ob"], faces[key], big)


def lifted_sea():
    """P9 end / P10: the sea far behind her lifted like a sheet into a black wall of water, hinged on a line across
    it: two halves, 60 x 150 m, swinging up about their near edge, meeting on a torn edge that lift() pulls apart.
    Near-black, so it reads against the bright sky behind it. Returns the two."""
    mat = A._principled("lifted", **{"Base Color": (0.006, 0.007, 0.01, 1.0), "Roughness": 0.25})[0]
    out = []
    for side in (-1.0, 1.0):
        r = random.Random(7)                                   # the same seed: the two edges fit
        nx, ny = 60, 24
        verts, faces = [], []
        tear = [r.uniform(-5.0, 5.0) * (0.3 + 0.7 * i / nx) for i in range(nx + 1)]
        for i in range(nx + 1):
            for j in range(ny + 1):
                y = 150.0 * j / ny + side * tear[i] * (1.0 - j / ny) ** 3
                verts.append((60.0 * i / nx, side * y, 0.0))
        for i in range(nx):
            for j in range(ny):
                a, c = i * (ny + 1) + j, (i + 1) * (ny + 1) + j
                faces.append((a, c, c + 1, a + 1) if side > 0 else (a, a + 1, c + 1, c))
        ob = fx.mesh(f"lifted_{int(side)}", verts, faces, mats=[mat])
        ob.location = (8.0, 0.0, 0.005)
        ob.hide_render = True
        out.append(ob)
    return out


def lift(angle, gap):
    """The lifted sea up by `angle` degrees, its two halves `gap` metres apart (each moved by half)."""
    for ob, side in zip(S.lifted, (-1.0, 1.0)):
        ob.hide_render = False
        ob.rotation_euler.y = -math.radians(angle)
        ob.location.y = side * gap / 2


def make_wall_pieces():
    """P10: the wall as blocks of its own plaster, to take its place on the downbeat it bursts."""
    r = random.Random(23)
    plaster = bpy.data.objects["wall"].data.materials[0]
    S.pieces = []
    ny, nz = 8, 6
    for i in range(ny):
        for j in range(nz):
            size = (W.WALL_T, W.WALL_W / ny * 0.98, W.WALL_H / nz * 0.98)
            ob = A.rounded_box(f"piece_{i}_{j}", size, 0.0, [plaster])
            ob.rotation_mode = "QUATERNION"
            ob.hide_render = True
            home = Vector((W.WALL_T / 2, W.WALL_W * ((i + 0.5) / ny - 0.5), W.WALL_H * (j + 0.5) / nz))
            out = (home - Vector((0.0, 0.0, 1.0))).normalized()
            S.pieces.append(dict(ob=ob, home=home, v=Vector((r.uniform(-16.0, -3.0), out.y * r.uniform(6.0, 22.0),
                                                             r.uniform(1.0, 14.0))),
                                 spin=Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))).normalized(),
                                 rate=r.uniform(1.0, 5.0), ph=r.uniform(0.0, 6.3)))


def wall_pieces(k, t):
    """The pieces `k` of the way out (0 where the wall stood), tumbling."""
    for p in S.pieces:
        p["ob"].hide_render = False
        p["ob"].location = p["home"] + p["v"] * k
        p["ob"].rotation_quaternion = Quaternion(p["spin"], p["rate"] * (0.15 * t + k * 2.0) + p["ph"] * k)


def shard_on_face(ob, meta, r):
    """The shard's piece of the picture moved to round her face, wide enough to read as her."""
    fu, fv = meta["face"]
    su, sv = 0.55 * meta["her"] / meta["w"], 0.55 * meta["her"] / meta["h"]
    cu, cv = fu + r.uniform(-0.3, 0.3) * su, fv + r.uniform(-0.3, 0.3) * sv
    data = ob.data.uv_layers.active.data
    uvs = [d.uv.copy() for d in data]
    mu, mv = sum(c.x for c in uvs) / len(uvs), sum(c.y for c in uvs) / len(uvs)
    du = max(max(abs(c.x - mu) for c in uvs), 1e-4)
    dv = max(max(abs(c.y - mv) for c in uvs), 1e-4)
    for d, c in zip(data, uvs):
        d.uv = (min(1.0, max(0.0, cu + (c.x - mu) / du * su / 2)), min(1.0, max(0.0, cv + (c.y - mv) / dv * sv / 2)))


def setup():
    W.build()
    sc = scene_settings()
    S.glass_light_lamp = S.glass_light                       # the panel behind the glass (an emitter, hidden)
    # the glass and its water weak lenses: at full strength the lathe gathers the wall and the jambs from far to the
    # side, grey-brown, and hid the ink inside it (with the glass hidden the water was clear and the ink red)
    clear = bpy.data.objects["glass"].material_slots[0].material.copy()
    bpy.data.objects["glass"].material_slots[0].material = clear
    for mat in (clear, bpy.data.materials["glass_water"]):
        next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["IOR"].default_value = 1.08
    deep_water()
    lights()
    letters_back()
    shutter()
    figures()
    into_sheets()
    effects()
    S.wall_parts = wall_parts()
    S.cam = cyc.camera("anim_cam", (-20.0, 0.0, 1.0), (0.0, 0.0, 2.0), 35, 8.0)
    S.cam.data.clip_end = 10000.0
    sc.camera = S.cam
    S.lineart, S.glare = AN.compositor()
    S.speed = AN.speed_blur()
    S.live_obs = [ob for ob in list(S.figs.values()) + list(S.into.values())
                  if ob.material_slots[0].material.name in H.LIVE]
    AN.stamp()
    S.hidden = [S.ink["ob"], S.burst["ob"], S.glass_ink["ob"], S.rain_ob, S.dust, S.conf, S.deep, S.sea_under,
                S.shutter, S.glass_light, S.letters_back] + S.lifted + [p["ob"] for p in S.pieces] + \
        [s["ob"] for s in S.shards] + [ob for ob, _ in S.halves] + \
        [c.ob for c in S.cracks.values()] + list(S.figs.values()) + \
        list(S.into.values()) + S.discs + [S.sun_disc]
    return sc


# ---------------------------------------------------------------- at rest, and what a shot sets

def reveal(name, v):
    c = S.cracks[name]
    c.ob.hide_render = v <= 0
    c["reveal"] = v


def reset(scene, t, b):
    _T.t, _T.b = t, b
    _T.gain, _T.wind, _T.blur, _T.flutter = 1.0, (0.0, 0.0), None, 1.0
    for lt in S.lamps:
        if lt.data.energy != 0.0:
            lt.data.energy = 0.0
    for ob in S.hidden:
        if not ob.hide_render:
            ob.hide_render = True
    for ob in S.wall_parts + [S.sea, bpy.data.objects["sky"]]:
        if ob.hide_render:
            ob.hide_render = False
    W.set_sky("s1", 0.0)
    put(S.haze_vol.inputs["Density"], 0.0)
    if not S.haze.hide_render:
        S.haze.hide_render = True
    put(S.haze_vol.inputs["Color"], m.srgb("#E4ECF4"))
    put(S.rain, 0.0)
    put(S.sea_bump, S.SEA_BUMP)
    put(S.sea_glow, 0.0)
    put(S.rip["a"], 0.0)
    put(S.sea_base, S.SEA_BASE)
    put(S.sea_metal, 0.0)
    for key, ob in S.figs.items():
        loc, rot = S.fig_home[key]
        if ob.location != loc:
            ob.location = loc
        if ob.rotation_euler != rot:
            ob.rotation_euler = rot
    for name in list(H.STAINS):
        H.stain(name, 0.0, 0.0, -1.0)
    for c in S.cracks.values():
        c["reveal"] = 0.0
    # the clouds are always going, and the seam of the sky's mirrored picture is kept out of the view along +X
    bpy.data.objects["sky"].rotation_euler.z = math.radians(SKY_TURN + 0.1 * t)
    put(S.lineart, 0.0)
    put(S.glare, 0.4)
    put(S.letters_em.inputs["Strength"], 0.0)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    scene.cycles.samples = SAMPLES
    scene.cycles.max_bounces = scene.cycles.transmission_bounces = 6
    scene.cycles.glossy_bounces = 4
    scene.render.use_motion_blur = False
    S.cam.data.type = "PERSP"
    S.cam.data.dof.use_dof = True
    for ob in S.lifted:
        ob.rotation_euler.y = 0.0
        ob.location.y = 0.0


def look(eye, target, lens=35.0, fstop=8.0, roll=0.0, focus=None, up=(0, 0, 1), ortho=None):
    """The camera at `eye` looking at `target`, with the beat push and the Dutch angle where the script has them."""
    eye, target = Vector(eye), Vector(target)
    if any(a <= _T.b < z for a, z in PUNCH):
        eye = eye + (target - eye) * punch(_T.t, 0.03)
    if DUTCH[0] <= _T.b < DUTCH[1]:                        # turning over within a beat, not jumping
        side = 1.0 if math.floor(_T.b) % 2 else -1.0
        roll += 12.0 * side * (2.0 * ease(clamp((_T.b % 1.0) * 4.0)) - 1.0)
    S.eye, S.fwd = AN.aim(S.cam, eye, target, lens, fstop, roll, focus, up, ortho)


def haze(density, color="#E4ECF4"):
    S.haze.hide_render = density <= 0
    put(S.haze_vol.inputs["Density"], density)
    put(S.haze_vol.inputs["Color"], m.srgb(color))


def aim_sun(toward):
    """The dawn sun low behind the wall where a camera at `toward` sees it through the letters (a cheat a shot,
    as a film's sun is)."""
    d = (Vector(toward) - LETTERS_AT).normalized()
    q = d.to_track_quat("-Z", "Y")
    if S.sun.rotation_quaternion != q:
        S.sun.rotation_quaternion = q
        S.sun_disc.location = -d * 500.0
        S.sun_disc.rotation_euler = d.to_track_quat("Z", "Y").to_euler()


def dawn(a=1.0, sky=1.8, disc=True, toward=None):
    """表: the low sun behind the wall through the letters and the window, by `a`."""
    aim_sun(toward if toward is not None else STILL_EYE)
    energy(S.sun, 5.0 * a)
    S.sun_disc.hide_render = not (disc and a > 0.05)
    bpy.data.objects["pane"].hide_render = True                # (what it mirrored was a second sun beside the disc)
    W.set_sky("s1", sky * max(a, 0.08))
    haze(0.003 * max(a, 0.3))
    energy(S.fill, 70.0 * a)
    bpy.context.scene.view_settings.exposure = -0.2


def dusk(a=1.0):
    """Nightfall over the water line (the q1s plate's light): a cold lamp before her, a rose one behind."""
    W.set_sky("s2", 0.35)
    haze(0.002, "#C4BCD0")
    put(S.sea_bump, 0.0)
    energy(S.cold, 160.0 * a)
    energy(S.rose, 120.0 * a)
    bpy.context.scene.view_settings.exposure = 0.4


def night(letters=1.0, sky=0.35):
    """裏: the letters glowing rose from behind the wall, the sky the rain night's."""
    W.set_sky("s2", sky)
    haze(0.003, "#C4BCD0")
    energy(S.letters_glow, 400.0 * letters)
    put(S.letters_em.inputs["Strength"], 3.0 * letters)
    S.letters_back.hide_render = letters <= 0
    bpy.context.scene.view_settings.exposure = 0.5


def rain_night(rain=1.0):
    W.set_sky("s2", 0.5)
    haze(0.008, "#C8D0E0")
    put(S.rain, rain)
    put(S.rain_t, (_T.t * 0.9) % 1.0)
    put(S.sea_bump, 0.12)
    energy(S.window_glow, 520.0)
    energy(S.key, 110.0)
    bpy.context.scene.view_settings.exposure = 0.6


def rain3d(center, t, strength=0.5):
    """The 3D streaks, a block round `center` falling through itself."""
    S.rain_ob.hide_render = False
    S.rain_ob.location = (center[0], center[1], center[2] - (t * 6.5) % 8.0)
    S.rain_ob.scale = (1.0, 1.0, 1.0)
    put(S.rain_em.inputs["Strength"], strength)


def twin_suns(view_from, view_to, a=1.0):
    """P10: two suns low at the two ends of the sky, the cold one on the camera's left, the rose one on its right."""
    W.set_sky("s3", 1.0)
    haze(0.002)
    f = (Vector(view_to) - Vector(view_from)).normalized()
    r = f.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = Vector((0.0, 0.0, 1.0))
    for lt, disc, d in ((S.sun_cold, S.discs[0], r - 0.45 * up - 0.25 * f), (S.sun_rose, S.discs[1], -r - 0.35 * up - 0.25 * f)):
        d = d.normalized()
        lt.rotation_quaternion = d.to_track_quat("-Z", "Y")
        energy(lt, 3.0 * a)
        disc.hide_render = False
        disc.location = -d * 500.0
        disc.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    bpy.context.scene.view_settings.exposure = 0.0


def underwater(red=0.0, shafts=1.0):
    """The camera in the deep: the water's body, the surface from below (no shadow, so the sun falls in shafts),
    the sea's own surface put away; `red` lights the deep rose from below."""
    S.deep.hide_render = False
    S.sea.hide_render = True
    S.sea_under.hide_render = False
    put(S.sea_base, (0.55, 0.62, 0.66, 1.0))
    energy(S.sun, 5.0 * shafts)
    energy(S.red_deep, 9000.0 * red)
    haze(0.0)


def clear_sea(v):
    """The sea let see into by `v` (0: the near-black mirror, 1: clear water): for the red under it and the ink."""
    base = S.SEA_BASE
    put(S.sea_base, tuple(base[k] + (0.5 - base[k]) * v for k in range(3)) + (1.0,))
    S.deep.hide_render = v <= 0


def ring(t0, x, y, amp=1.0, speed=2.4, life=1.2):
    """A pulse ring on the sea from (x, y), spreading for `life` seconds after t0 (the beat's ドクン)."""
    age = _T.t - t0
    if 0 <= age < life:
        put(S.rip["x"], x)
        put(S.rip["y"], y)
        put(S.rip["r"], 0.1 + speed * age)
        put(S.rip["a"], amp * (1 - age / life))


def ink(blob, loc, scale, density=1.0, glow=0.3):
    # at least 3 mm a side: OpenVDB aborts the render on a volume a fraction of a millimetre thin
    fx.ink(blob, loc, tuple(max(0.003, c) for c in scale), density, glow, _T.t)


def flash():
    """D4: the frame as its own negative on paper for a frame or two after a downbeat."""
    if _T.t - CLK.last_beat(_T.t) < 1.6 / FPS and abs(_T.b - round(_T.b)) < 0.05 and round(_T.b) % 4 == 3:
        put(S.lineart, 1.0)


def beat_in_bar():
    return int((_T.b % 1.0) * 4)


def surge(x, a=0.5):
    """A count that moves faster on each whole number of `x` and never stops: a camera that leans on the beat. (One that
    leapt on the beat and then stood still read as a stutter.)"""
    return x + a * math.sin(2 * math.pi * x) / (2 * math.pi)


def overshoot(x):
    """1 down to 0 with a little swing past it, as a whip pan lands."""
    return (1.0 - x) ** 2 * math.cos(x * math.pi * 1.5) if x < 1.0 else 0.0


def since_beat(decay=0.14):
    """1 on the beat, dying away over `decay` seconds."""
    return math.exp(-(_T.t - CLK.last_beat(_T.t)) / decay)


def face(key, du=0.0, dv=0.0):
    """Her face in picture `key` (u, v from its bottom left; scripts/live_maps.py), moved by (du, dv)."""
    meta = H.LIVE.get(S.into[key].material_slots[0].material.name, {}).get("meta")
    fu, fv = meta["face"] if meta else (0.5, 0.6)
    return (fu + du, fv + dv)


def energy_at(b):
    e = ENERGY[0][1]
    for bar, v in ENERGY:
        if b >= bar:
            e = v
    return e


def alive(t):
    """The last thing on every frame: nothing on screen is at rest, and what moves moves with the song.
    The camera: a hand's slow wander, and a kick on each beat as strong as the beat's onset in the mix. The light: the
    exposure jumps on the beats, with a zoom blur, where the film has energy. Her: every picture and figure on screen
    has its hair waving and flung on the beats, her head turning and nodding on the downbeats, her chest breathing,
    her standing off her background (hybrid.live); a paper figure turns a little in the air."""
    b, e = _T.b, energy_at(_T.b)
    beat_t = CLK.last_beat(t)
    dt = t - beat_t
    i = min(int(beat_t * 30), len(ONSET) - 1)
    hit = min(1.0, max(ONSET[max(0, i - 1):i + 3]) / ONSET_TOP) * math.exp(-dt / 0.14)
    kick = hit if e >= 0.2 else 0.0                       # (the opening's slow push: a kick on it reads as a stutter)
    loud = LOUD[min(int(t * 30), len(LOUD) - 1)] / LOUD_TOP
    seed = random.Random(int(beat_t * 1000))
    cam = S.cam
    if e > 0 and cam.data.type == "PERSP":
        k = min(1.4, 35.0 / cam.data.lens) * e
        yaw = k * (0.30 * math.sin(1.7 * t + 0.4) + 0.14 * math.sin(3.7 * t + 2.1) + kick * seed.uniform(-0.7, 0.7))
        pitch = k * (0.22 * math.sin(1.3 * t + 1.2) + 0.12 * math.sin(4.1 * t) + kick * seed.uniform(-0.7, 0.7))
        rock = k * (0.45 * math.sin(0.9 * t + 2.0) + kick * seed.uniform(-1.2, 1.2))
        turn = Euler((math.radians(pitch), math.radians(yaw), math.radians(rock)))
        cam.matrix_world = cam.matrix_world @ turn.to_matrix().to_4x4()
    sc = bpy.context.scene
    blur = dict(_T.blur or {})
    if e >= 0.7 and sc.view_settings.exposure > -5.0:
        sc.view_settings.exposure += 0.3 * e * hit
        blur.setdefault("scale", 1.0 + 0.035 * e * hit)
    scale, amount = blur.get("scale", 1.0), blur.get("amount", 0.0)
    put(S.speed["Scale"], scale)
    put(S.speed["Amount"], amount)
    put(S.speed["Direction"], blur.get("direction", 0.0))
    samples = 16 if amount > 0.002 or scale > 1.004 else 1
    if S.speed["Samples"].default_value != samples:
        S.speed["Samples"].default_value = samples
    down = max(0.0, t - at(math.floor(b)))
    side = 1.0 if int(beat_t * 1000) % 2 else -1.0
    g = _T.gain
    amp = g * (0.004 + 0.007 * e) * (0.7 + 0.6 * loud)
    speed = 0.5 + 0.8 * e
    pose = dict(t1=2 * math.pi * 0.55 * speed * t, t2=2 * math.pi * 0.83 * speed * t + 1.0,
                t3=2 * math.pi * 0.69 * speed * t, amp=amp,
                wx=_T.wind[0] + 0.012 * e * g * side * math.exp(-dt / 0.3),
                wy=_T.wind[1] + 0.004 * e * g * math.exp(-dt / 0.3),
                hx=0.0025 * math.sin(0.8 * t), hy=-(0.003 + 0.006 * e) * min(g, 1.5) * math.exp(-down / 0.24),
                rot=math.radians(0.6 + 0.6 * e) * math.sin(0.7 * t + 1.0),
                breath=0.005 * math.sin(2 * math.pi * t / 3.2), px=(0.6 + e) * 0.006 * math.sin(0.6 * t),
                py=(0.6 + e) * 0.003 * math.sin(0.45 * t + 1.0))
    for ob in S.live_obs:
        if ob.hide_render:
            continue
        socks = H.LIVE[ob.material_slots[0].material.name]
        for key, v in pose.items():
            put(socks[key], v)
    for ob in S.figs.values():
        if not ob.hide_render:
            ob.rotation_euler.z += math.radians(_T.flutter * (1.5 + 2.0 * e) * math.sin(0.9 * t + 0.5))


def hide_wall(h=True):
    for ob in S.wall_parts:
        ob.hide_render = h


def on_picture(pu, pv, zoom, roll, tw, th, margin=0.02):
    """(pu, pv, zoom) as near what was asked as keeps the whole frame, turned by `roll`, on the picture: past its edge the
    sky behind shows and she is a card cut off in the air."""
    sc = bpy.context.scene
    c, s = abs(math.cos(math.radians(roll))), abs(math.sin(math.radians(roll)))
    fw, fh = tw, tw * sc.render.resolution_y / sc.render.resolution_x
    du, dv = (fw * c + fh * s) / (2 * tw), (fw * s + fh * c) / (2 * th)      # half the frame at zoom 1, in u and v
    zoom = max(zoom, du / (0.5 - margin), dv / (0.5 - margin))
    du, dv = du / zoom, dv / zoom
    return min(max(pu, margin + du), 1 - margin - du), min(max(pv, margin + dv), 1 - margin - dv), zoom


def into(key, zoom=1.0, at_point=None, pan=0.0, tilt=0.0, roll=0.0, glow=1.0, exposure=0.0, wall=False):
    """Inside picture `key`: the camera at its plate's eye, looking where the plate looked (or at the picture's
    point `at_point` = (u, v) from its bottom left), turned by `pan` and `tilt` degrees, the lens `zoom` times the
    plate's (a portrait plate's lens is widened to the frame's width first). The picture gives off its own light
    (`glow`); the view is the plain sRGB one, so it looks as painted; the wall is put away (the picture's own is
    there) unless `wall`."""
    pic, plate = INTO[key]
    ob = S.into[key]
    ob.hide_render = False
    put(S.into_mats[key].inputs["Strength"], glow)
    zoom = max(zoom, 1.05)                                    # room for the hand's wander inside the picture
    # the view here is the plain sRGB one, where the sky behind the panes burnt white at the 3D shots' strength
    put(S.sky_em.inputs["Strength"], min(S.sky_em.inputs["Strength"].default_value, SKY_IN_PICTURE))
    S.sun_disc.hide_render = True
    eye, f, r, u, lens, tw, th = plate_frame(plate)
    target = eye + f
    if at_point is not None:
        pu, pv = at_point
        target = eye + f + r * (2 * pu - 1) * tw + u * (2 * pv - 1) * th
    if pan or tilt:
        d = (target - eye).normalized()
        d = Matrix.Rotation(math.radians(pan), 3, u) @ d
        d = Matrix.Rotation(math.radians(tilt), 3, r) @ d
        target = eye + d
    d = target - eye
    d = d / d.dot(f)
    pu, pv, zoom = on_picture(0.5 + d.dot(r) / (2 * tw), 0.5 + d.dot(u) / (2 * th), zoom, roll, tw, th)
    target = eye + f + r * (2 * pu - 1) * tw + u * (2 * pv - 1) * th
    lens = 18.0 / tw * zoom                                   # the frame (36 mm wide) as wide as the plate's view
    look(eye, target, lens=lens, fstop=16.0, roll=roll, focus=D_SHEET, up=tuple(u))
    S.cam.data.dof.use_dof = False
    if not wall:
        hide_wall(True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = exposure


def into_free(key, eye, target, lens, d=0.6, glow=1.0, exposure=0.0, zoom=1.08):
    """A v4 close-up (no plate): the picture on the image plane `d` before a camera at `eye`, filling the frame at
    `lens`, `zoom` times closer, the world behind its planes."""
    ob = S.into[key]
    ob.hide_render = False
    put(S.into_mats[key].inputs["Strength"], glow)
    eye, target = Vector(eye), Vector(target)
    f = (target - eye).normalized()
    r = f.cross(Vector((0.0, 0.0, 1.0))).normalized()
    u = r.cross(f)
    img = P.image(INTO[key][0])
    aspect = img.size[1] / img.size[0]
    s = 2 * d * (18.0 / lens) * 1.04
    centre = eye + f * d
    ob.matrix_world = Matrix.Translation(centre + u * (aspect * s / 2)) @ Matrix((f, -r, u)).transposed().to_4x4() @ \
        Matrix.Scale(s, 4)
    look(eye, target, lens=lens * zoom, fstop=16.0, focus=d)
    S.cam.data.dof.use_dof = False
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = exposure


def seep(key, v, blob=None):
    """Rose ink soaking into picture `key` from her hair (the stain, by v 0..1); with `blob`, a wisp of ink in the
    air just before the picture, running down."""
    ob, pic = S.into[key], INTO[key][0]
    hair = H.anchor(ob, pic, 0)
    hu, hv = hair["uv"]                                         # the hair's middle is over her face: the stain
    H.stain(ob.name, *H.sheet_uv(ob, pic, hu + 0.1, hv - 0.2), 0.02 + 0.05 * v)   # soaks in at her red ends
    if blob is not None:                                        # a thread of ink running down the air before her
        s = ob.matrix_world.to_scale()[0]                       # (the sheet is metres wide; at 0.5 m from the lens a
        p = hair["point"] + (S.eye - hair["point"]).normalized() * 0.02 * s   # few mm is a strand of hair)
        ink(blob, p + Vector((0.0, 0.0, -0.03 * v * s)), (0.0015 * s, 0.0015 * s, (0.006 + 0.03 * v) * s), 2.5, 0.0)


def dust(center):
    fx.dust(S.dust, S.mote, _T.t, center)


def scraps(center, radius=4.0, height=3.0, swirl=0.0, fall=0.0, n=None):
    fx.scraps(S.conf, S.scrap, center, _T.t, radius, height, swirl, fall, n)


# ---------------------------------------------------------------- the shots, script_v5.md section 5

P0_EYE, P0_TARGET = Vector((-16.0, 3.5, 0.45)), Vector((-0.5, -0.3, 2.6))


def p0_horizon(u, t, b):
    """P0.1: black; a thin cold line comes out of it, the horizon, the camera on the water facing it."""
    a = ease(clamp((b + 2) / 4.0))
    W.set_sky("s1", 0.12 * a)
    look(P0_EYE + Vector((-1.2 * (1 - u), 0.0, 0.0)), P0_TARGET, lens=32, fstop=8.0)
    bpy.context.scene.view_settings.exposure = -0.4
    S.shutter.hide_render = False


def p0_letters(u, t, b):
    """P0.2: the sun rises behind a wall we cannot see yet: two letters of light in the dark, their long
    reflections running to the lens; the camera pushes in without stopping and the light swells as it goes."""
    aim_sun(P0_EYE)
    energy(S.sun, 5.0 * ease(clamp((b - 2) / 0.5)) * (0.8 + 0.3 * u))
    S.sun_disc.hide_render = False
    W.set_sky("s1", 0.14)
    haze(0.004)
    S.shutter.hide_render = False
    look(P0_EYE + Vector((1.6 * u, -0.3 * u, 0.0)), P0_TARGET, lens=32 + 8 * u, fstop=8.0)
    bpy.context.scene.view_settings.exposure = -0.4


def p0_layers(u, t, b):
    """P0.3: a layer of light a downbeat, a new place for the camera with it: the wall's outline against the
    brightening sky from far along the water (4), low under the window as it opens on the dawn (5), and on the 6th
    downbeat she is there before it, a drawn girl standing on the water."""
    dawn(1.0, sky=1.8 * (0.25 + 0.75 * ease(clamp(b - 4.0))), toward=P0_EYE)
    S.shutter.hide_render = b >= 5.0
    if b < 5.0:                                                 # the same push as P0.2 goes on, at its speed and lens
        v = b - 4.0
        look(P0_EYE + Vector((1.6 + 1.0 * v, -0.3, 0.0)), P0_TARGET, lens=40 + 4 * v, fstop=8.0)
        return
    if b < 6.0:
        v = b - 5.0
        look(Vector((-11.0 + 1.5 * v, 5.0 - 0.8 * v, 0.3)), (-0.4, -0.2, 3.3), lens=30, fstop=8.0)
        return
    v = b - 6.0
    eye = Vector((-7.4, -3.7, 0.9)) + Vector((1.5, 0.6, 0.0)) * v
    show("kv", eye=eye)
    _T.gain = 1.6
    look(eye, (-1.4, -1.0, 1.6), lens=35, fstop=4.0, focus=(-1.6, -1.2, 1.2))


def p0_through(u, t, b):
    """P0.4: the camera rushes at the window glass and through it, four frames, into A1."""
    dawn(1.0)
    show("kv", eye=(-4.0, -1.8, 1.4))
    k = ease(u) ** 2
    eye = Vector((-4.0, -1.8, 1.5)).lerp(Vector((-0.02, -0.9, 2.6)), k)
    look(eye, (1.0, -0.9, 2.7), lens=28, fstop=5.6)
    _T.blur = dict(scale=1.0 + 0.12 * k)
    if u > 0.9:
        into("a1", zoom=1.0 + 0.4 * (1 - (u - 0.9) / 0.1))


def p1_light(u, t, b):
    """P1.1: inside A1. Her window is the real sky: the camera pans and the clouds slide behind the frame; dust in
    the beam is 3D; on every downbeat a cloud's shadow passes over her. Half way the camera is nearer her."""
    dawn(1.0)
    shade = 1.0 - 0.25 * math.exp(-((b % 1.0) - 0.3) ** 2 / 0.02)
    if b < 10.0:
        v = (b - 8.0) / 2.0
        into("a1", zoom=1.16 + 0.24 * v, pan=-3.5 + 7.0 * v, roll=-1.5 + 3.0 * v, glow=shade)
    else:
        v = (b - 10.0) / 2.0
        into("a1", zoom=1.45 + 0.5 * v, at_point=face("a1", 0.06 - 0.12 * v, -0.08 + 0.04 * v), roll=2.0 - 3.0 * v,
             glow=shade)
    _T.gain = 1.6
    pic, plate = INTO["a1"]
    eye, f, r, uu, lens, tw, th = plate_frame(plate)
    dust(eye + f * 1.6 + Vector((0.0, 0.0, -2.2)))


def p1_eyes(u, t, b):
    """P1.2: A5 closed-eyed, on the downbeat of 13 A5 open-eyed: the same picture, her eyes open, the camera going in
    on them as they do."""
    dawn(1.0)
    key = "a5o" if b >= 13.0 and "a5o" in S.into else "a5"
    near = 1.0 - math.exp(-6.0 * max(0.0, b - 13.0))
    into(key, zoom=1.15 + 0.3 * u + 0.5 * near, at_point=face(key, 0.05 * (1.0 - u), -0.02 * near - 0.05 * (1.0 - u)),
         roll=-2.0 + 3.0 * u)
    _T.gain = 1.6


def p1_drop(u, t, b):
    """P1.3: macro, the glass of water on the sill, the dawn behind it; on the downbeat of 15 a rose drop falls
    into it and blooms down through the water, the film's first colour; the camera drifts in, and starts at the drop."""
    dawn(1.0)
    S.glass_light.hide_render = False
    S.glass_light.location.z = 1.5                             # behind the glass (it sees the low panes, inverted)
    g = S.glass_at
    # level with the water, the window behind it: from above it saw the sill through the water, brown
    v = clamp((t - at(15.0)) / 1.4)
    near = 0.28 * u + 0.05 * (1.0 - math.exp(-5.0 * v))
    look(g + Vector((-0.8 + near, 0.22 - 0.3 * u, 0.1 - 0.05 * u)), g + Vector((0.0, 0.0, 0.05)), lens=85, fstop=2.8,
         roll=2.0 - 4.0 * u)
    bpy.context.scene.cycles.glossy_bounces = 14
    bpy.context.scene.cycles.max_bounces = bpy.context.scene.cycles.transmission_bounces = 14
    if t >= at(15.0) - 0.15:
        if t < at(15.0):                                       # the drop, falling
            k = (at(15.0) - t) / 0.15
            ink(S.burst, g + Vector((0.0, 0.0, 0.09 + 0.25 * k)), (0.004, 0.004, 0.008), 6.0, 0.2)
        else:
            ink(S.glass_ink, g + Vector((0.0, 0.0, 0.058 - 0.022 * v)), (0.005 + 0.013 * v, 0.005 + 0.013 * v,
                                                                         0.006 + 0.022 * v), 3.0, 0.15)


def p1_seep(u, t, b):
    """P1.4: the same red in 2D: inside Q1 (A5 open-eyed) it soaks into her hair from the roots, and a wisp of
    ink runs down the air before her face (3D); the camera creeps nearer without stopping."""
    dawn(1.0)
    key = "a5o" if "a5o" in S.into else "a5"
    # down her hair where the red is, and back up to her eyes
    into(key, zoom=1.25 + 0.75 * u, at_point=face(key, 0.14 * (1.0 - ease(u)), -0.2 * (1.0 - ease(u)) - 0.02),
         roll=3.0 - 5.0 * u)
    _T.gain = 1.8
    seep(key, ease(u))                                          # (a wisp of ink before her face read as a nosebleed)


def p1_glass_top(u, t, b):
    """P1.5: straight down on the glass, the ink turning in it; the camera rises, turning, and the glass's mouth
    becomes a red ring on the sea, thirty metres down: the same swirl, the wall's reflection beside it, her small at
    the window."""
    dawn(1.0)
    g = S.glass_at
    h = 0.12 * math.exp(math.log(30.0 / 0.12) * ease(u))
    look(g + Vector((0.0, 0.0, 0.1 + h)), g, lens=50, fstop=8.0, up=(1, 0, 0), roll=55.0 * u)
    ink(S.glass_ink, g + Vector((0.0, 0.0, 0.06)), (0.022, 0.022, 0.03), 3.0, 0.15)
    if u > 0.35:                                               # the red on the sea under the window: ink at the surface
        k = ease((u - 0.35) / 0.4)                             # (the sea's own glow was a flat red floor in v4)
        ink(S.ink, Vector((-1.2, -0.9, -0.03)), (0.3 + 1.6 * k, 0.3 + 1.6 * k, 0.05), 3.0, 0.5)
        clear_sea(0.3)
        show("kv")
    if b >= 23.0:                                              # P1.6: the first crack runs from the red
        reveal("sea", ease((b - 23.0) / 0.9))


# the world between the whips, somewhere new each bar: (eye, its travel, target, lens, she is in it)
WHIP_WORLD = {24: ((-9.0, -6.0, 0.45), (3.0, 3.5, 0.0), (0.0, -1.0, 2.2), 28.0, False),
              25: ((-6.0, 6.5, 6.5), (-1.5, -3.0, -3.0), (-1.0, 0.0, 1.0), 26.0, True),
              26: ((-5.0, -3.2, 0.5), (1.5, -0.6, 0.5), (-1.6, -1.2, 1.5), 32.0, True),
              27: ((-8.0, 8.0, 0.3), (3.0, -6.0, 0.0), (0.0, 0.0, 3.0), 22.0, False)}


def whip_world(u, t, b):
    """P2: the world between the whips."""
    eye, travel, to, lens, her = WHIP_WORLD[int(math.floor(b))]
    eye = Vector(eye) + Vector(travel) * u
    if her:
        show("kv", eye=eye)
        _T.gain = 2.2
    look(eye, to, lens=lens, fstop=8.0)


WHIP = {24: "a2", 25: "a3", 26: "a4", 27: "a1w"}


def p2_whip(u, t, b):
    """P2.1-2.2: a whip a bar, from the world into a picture's front and back out, one way and the other way; the
    whip overshoots and settles on the beat; a crack of light on every downbeat, in 3D (the water, the wall, the glass)
    and in 2D (across the picture)."""
    dawn(1.0)
    bar = int(math.floor(b))
    v = b - bar
    key = WHIP.get(bar, "a2")
    side = 1.0 if bar % 2 else -1.0
    if 0.3 <= v < 0.85 and key in S.into:
        x = clamp((v - 0.3) / 0.14)
        into(key, zoom=1.1 + 0.16 * (v - 0.3), pan=side * 14.0 * overshoot(x), at_point=face(key, 0.0, -0.03))
        _T.gain = 1.8
        if x < 1.0:
            _T.blur = dict(amount=0.10 * (1 - x), direction=0.0 if side > 0 else math.pi)
    else:
        whip_world(v, t, b)
        out = clamp((v - 0.2) / 0.1) if v < 0.3 else 1 - clamp((v - 0.85) / 0.1)
        if out > 0:
            S.cam.matrix_world = S.cam.matrix_world @ Matrix.Rotation(math.radians(side * 32.0 * ease(out)), 4, "Y")
            _T.blur = dict(amount=0.12 * out, direction=math.pi if side > 0 else 0.0)
    name = ("sea", "wall", "glass", "sea")[bar % 4]
    reveal(name, ease(clamp(v / 0.2)))
    flash()


def p2_wind(u, t, b):
    """P2.3: the wind: the clouds run, the water roughens, her hair streams, and the camera goes round her close to;
    then low on the water with the whole wall and the sky running over it."""
    dawn(1.0)
    put(S.sea_bump, 0.35)
    bpy.data.objects["sky"].rotation_euler.z += math.radians(10.0 * u)       # the clouds run
    if b < 29.0:
        v = surge((b - 28.0) * 4) / 4
        ang = math.radians(-155.0 + 45.0 * v)
        her = Vector((-1.6, -1.2, 1.0))
        eye = her + Vector((3.6 * math.cos(ang), 3.6 * math.sin(ang), 0.1))
        show("kv", eye=eye)
        _T.gain, _T.wind = 2.6, (0.02, 0.006)
        look(eye, her + Vector((0.0, 0.0, 0.15)), lens=40, fstop=3.2)
    else:
        look(Vector((-12.0, 4.0, 0.3)) + Vector((1.5, -6.0 * (b - 29.0), 0.0)), (0.0, -0.5, 3.0), lens=22, fstop=8.0)
        show("kv", eye=S.eye)
        _T.gain, _T.wind = 2.2, (0.015, 0.004)


def p2_out(u, t, b):
    """P2.4: the dawn goes out a beat at a time, the camera a step further off with each: the world dark but for the
    crack's red and the letters."""
    k = 1.0 - 0.25 * beat_in_bar() - 0.25 * ease((b % 0.25) * 4)
    dawn(max(0.0, k))
    energy(S.letters_glow, 400.0 * (1 - max(0.0, k)))
    put(S.letters_em.inputs["Strength"], 3.0 * (1 - max(0.0, k)))
    S.letters_back.hide_render = k >= 1.0
    reveal("sea", 1.0)
    look((-13.0 - 7.0 * surge((b - 30.0) * 4) / 4, 0.0, 0.6), (0.0, 0.6, 2.4), lens=40, fstop=8.0)


def p3_turn(u, t, b):
    """P3: her 表 (Q1) on the water at nightfall; in the water her 裏 (the twin) where her reflection should be.
    The camera at water level turns round her and, a bar at a time (two beats in bar 34), tilts from her face to the
    face in the water, brought up to be seen, and back. On the last beat the water bursts in a ring from her feet and
    the camera dives in."""
    dusk(1.0)
    q = show("q1s")
    S.figs["q1u"].hide_render = False
    x, y = q.location.x, q.location.y
    ang = math.radians(-50.0 + 100.0 * surge((b - 31.0) * 2) / 8)
    dist = 5.2 - 1.6 * clamp((b - 31.0) / 3.5)
    eye = Vector((x - dist * math.cos(ang), y - dist * math.sin(ang), 0.55))
    facing(q, eye)
    facing(S.figs["q1u"], eye)
    step = 1.0 if b >= 34.0 else 0.5                       # (every two beats it rested on her ankles half the time)
    phase = ((b % 1.0) * 4 * step) % 2.0
    down = ease(clamp((phase - 0.5) * 2)) if phase < 1.0 else 1.0 - ease(clamp((phase - 1.5) * 2))
    target = Vector((x, y, 1.25 - 2.5 * down))
    _T.gain = 1.3
    look(eye, target, lens=55, fstop=4.0)
    bpy.context.scene.view_settings.exposure += 1.2 * down  # the water's mirror is darker than she is
    if b >= 34.75:
        k = clamp((b - 34.75) / 0.25)
        ring(at(34.75), x, y, amp=2.0, speed=6.0)
        look(eye.lerp(Vector((x, y, -0.8)), ease(k)), Vector((x, y, -2.0)), lens=40, fstop=4.0)
        _T.blur = dict(scale=1.0 + 0.1 * k)


CHORUS_CAMS = ["skim", "round", "half", "under", "top"]


def chorus_cam(kind, u):
    if kind == "skim":                                     # ① skimming the water towards the wall, past her
        look((-16.0 + 12.0 * u, -1.9, 0.3), (0.0, 0.0, 1.6), lens=24, fstop=8.0)
        show("kv", eye=S.eye)
    elif kind == "top":                                    # ② high over her, turning, the wall's reflection beside her
        # (straight down was a dark empty sea: on the odd bars the picture comes before the ink opens)
        look((-7.5 + 2.0 * u, -5.5, 5.0 + 1.5 * u), (-2.0, -1.0, 0.8), lens=28, fstop=8.0, roll=-20.0 + 30.0 * u)
        show("kv", eye=S.eye)
    elif kind == "half":                                   # ③ half in the water: the world above, the deep below
        look((-9.0 + 4.0 * u, 0.4, 0.0005), (0.0, 0.2, 0.0005), lens=20, fstop=8.0)
    else:
        her = Vector((-1.6, -1.2, 1.0))
        if kind == "round":                                # ④ going round her close to, the world wheeling behind her
            ang, dist, up = math.radians(-165.0 + 70.0 * u), 3.6 - 0.8 * u, 0.2
            to = her + Vector((0.0, 0.0, 0.2))
        else:                                              # ⑤ from the water's surface up at her, sliding under her
            ang, dist, up = math.radians(-125.0 - 40.0 * u), 2.7, -0.95
            to = her + Vector((0.0, 0.0, 0.5))
        eye = her + Vector((dist * math.cos(ang), dist * math.sin(ang), up))
        look(eye, to, lens=30, fstop=4.0, roll=(-6.0 + 12.0 * u) if kind == "round" else 10.0 * u)
        show("kv", eye=eye)


def p4_chorus(u, t, b):
    """P4: a dimension event a beat: (1) push, and the negative on paper at each fourth bar, (2) a pulse ring over the
    whole water, (3) ink bursting in the deep, (4) a chorus picture (C1-C4), half a beat on the even bars, the last two
    beats of the odd, her hair flung, then back to 3D. A camera a bar, five in turn, leaning on the beats; from bar 41
    the deep glows red under the cold mirror."""
    dawn(1.0)
    bar = int(math.floor(b))
    beat = beat_in_bar()
    v = (b % 1.0) * 4 - beat
    red = 0.0 if b < 41 else ease(clamp((b - 41) / 5.0))
    kind = CHORUS_CAMS[(bar - 35) % 5]
    if (bar % 2 and beat >= 2) or (beat == 3 and v < 0.5):
        key = CHORUS[(bar - 35) % 4]
        w = (b % 1.0) * 2.0 - 1.0 if bar % 2 else v / 3.0
        into_free(key, (-8.0, -1.0, -4.0), (-2.0, -0.6, -4.4), 35.0, zoom=1.1 + 0.42 * w)
        underwater(red=0.4 + red, shafts=0.8)
        _T.gain = 2.2
        return
    if kind == "half":
        underwater(red=red)
        put(S.sea_base, (0.55, 0.62, 0.66, 1.0))
        S.sea.hide_render = False
    else:
        clear_sea(0.35 + 0.4 * red)
        energy(S.red_deep, 9000.0 * red)
    chorus_cam(kind, surge((b % 1.0) * 4) / 4)
    _T.gain = 2.0
    flash()
    ring(CLK.last_beat(t) if beat == 1 else -10.0, -2.0, -0.6, amp=1.2, speed=7.0, life=0.6)
    if beat >= 2:
        k = clamp(((b % 1.0) * 4 - 2) / 2.0)
        ink(S.burst, Vector((-2.5, -0.6, -1.4 + 0.6 * k)), (0.5 + 2.0 * k, 0.5 + 2.0 * k, 0.4 + 1.2 * k), 1.4, 0.5)


def p5_spill(u, t, b):
    """P5.1: inside C1 the ink round her rises along her hair; her water is the sea: the camera follows the ink
    out of the picture and up through the surface, and from above the red spreads on the sea."""
    if u < 0.55:
        into_free("c1", (-8.0, -1.0, -4.0 + 1.2 * u), (-2.0, -0.6, -4.4 + 1.6 * u), 35.0, zoom=1.08 + 0.5 * u)
        underwater(red=0.6, shafts=0.8)
        _T.gain = 2.4
    else:
        dawn(1.0)
        k = (u - 0.55) / 0.45
        clear_sea(0.55)
        energy(S.red_deep, 9000.0 * 0.6)
        look((-6.0, -1.0, 0.5 + 6.0 * ease(k)), (-3.0, -0.6, 0.0), lens=28, fstop=8.0, roll=-30.0 * k)
        ink(S.ink, Vector((-4.0, -0.8, -0.05)), (2.0 + 2.0 * k, 2.0 + 2.0 * k, 0.12), 1.0, 0.6)


def p5_full(u, t, b):
    """P5.2: the whole sea lit red from below, the cold sky still in its mirror; skimming, a push a beat, the camera
    coming to her and rising (from under her chin her face was gone); the wall's reflection red."""
    dawn(1.0)
    clear_sea(0.6)
    energy(S.red_deep, 9000.0)
    v = surge((b - 51.0) * 4) / 16
    look((-14.0 + 9.0 * v, 2.2 - 3.4 * v, 0.25 + 0.75 * v), Vector((0.0, -0.4, 2.0)).lerp(Vector((-1.6, -1.2, 1.4)), v),
         lens=24 + 6 * v, fstop=8.0)
    show("kv", eye=S.eye)
    _T.gain = 2.0


def p5_vertigo(u, t, b):
    """P5.3: the film's one dolly zoom, on her standing at the window: she stays, the wall and the horizon go."""
    dawn(1.0)
    clear_sea(0.6)
    energy(S.red_deep, 9000.0)
    her = Vector((-1.6, -1.2, 1.0))
    k = ease(u)
    dist = 3.0 + 9.0 * k
    lens = 28.0 * dist / 3.0
    eye = her + Vector((-dist * 0.94, -dist * 0.34, 0.2))
    show("kv", eye=eye)
    _T.gain = 2.0
    look(eye, her + Vector((0.0, 0.0, 0.3)), lens=lens, fstop=5.6)


def p5_cut(u, t, b):
    """P5.4: black for a beat. Then the rain's sound."""
    W.set_sky("s1", 0.0)
    look((-20.0, 0.0, 1.0), (0.0, 0.0, 1.0), lens=35)
    bpy.context.scene.view_settings.exposure = -10.0


def p6_rain(u, t, b):
    """P6.1: the first night (S2): rain over the whole sea, its rings; the wall dark but for the window; W1 far out
    on the water, small, in the rain; the camera comes in slowly from behind her; then down on the water, long, her
    small in the rings."""
    rain_night()
    w = show("w1")
    _T.wind = (0.006, 0.0)
    if b < 59.0:
        eye = Vector((-30.0 + 16.0 * (b - 57.0) / 2.0, 3.0 - 2.0 * (b - 57.0) / 2.0, 1.8 - 0.5 * (b - 57.0) / 2.0))
        facing(w, eye)
        look(eye, (-6.0, 0.6, 1.4), lens=35, fstop=5.6)
        rain3d((eye.x + 6.0, eye.y, 6.0), t, 0.45)
        return
    v = (b - 59.0) / 2.0
    eye = Vector((-20.0 + 3.0 * v, 4.5 - 4.5 * v, 0.1))
    facing(w, eye)
    look(eye, (-6.0, 0.6, 0.55), lens=85, fstop=4.0)
    rain3d((eye.x + 5.0, eye.y, 6.0), t, 0.5)


def p6_w1(u, t, b):
    """P6.2: W1's back grows, the window's light edges her rose, the rain falls before her, her reflection under
    her; then W2 fills the frame, the rain falling before her face (3D)."""
    rain_night()
    _T.wind = (0.008, 0.0)
    if b < 62.5:
        w = show("w1")
        v = (b - 61.0) / 1.5
        eye = Vector((-13.0 + 4.5 * v, 2.0 - 1.4 * v, 1.25))
        facing(w, eye)
        look(eye, (-6.0, 0.6, 1.15), lens=45, fstop=4.0)
        rain3d((eye.x + 3.0, eye.y, 6.0), t, 0.45)
    else:
        v = (b - 62.5) / 1.5
        into_free("w2", (-9.0, 0.6, 1.4), (-6.0, 0.6, 1.4), 50.0, exposure=0.0, zoom=1.08 + 0.45 * v)
        _T.gain = 1.8
        rain3d((-8.4, 0.6, 6.0), t, 0.5)


def p6_side(u, t, b):
    """P6.3: round her figure by 90 degrees: she becomes a line; on round to the back, bare paper. She is paper."""
    rain_night()
    w = show("w1")
    yaw0 = w.rotation_euler.z
    ang = math.pi + yaw0 + math.radians(170.0 * ease(u))
    eye = Vector((w.location.x + 4.0 * math.cos(ang), w.location.y + 4.0 * math.sin(ang), 1.1))
    _T.flutter = 0.0                                           # a clean edge: she has to become a line
    look(eye, (w.location.x, w.location.y, 0.9), lens=40, fstop=4.0)
    rain3d((w.location.x, w.location.y, 6.0), t, 0.4)


def p6_lines(u, t, b):
    """P6.4: on the downbeat the 3D rain turns to speed lines for a bar and back; on the last beat the camera
    tips down to her reflection and starts to roll."""
    rain_night()
    w = show("w1")
    eye = Vector((-11.0, 1.0, 1.0))
    facing(w, eye)
    tilt = ease(clamp((b - 67.5) * 2.0))
    look(eye, Vector((-6.0, 0.6, 1.0 - 2.2 * tilt)), lens=40 + 10 * u, fstop=4.0, roll=40.0 * tilt)
    rain3d((eye.x + 3.0, eye.y, 6.0), t, 0.5)
    if 66.0 <= b < 66.25 and _T.t - CLK.last_beat(_T.t) < 1.6 / FPS:
        put(S.lineart, 1.0)


def p7_roll(u, t, b):
    """P7.1: the camera on the water rolls through 180 degrees: the reflection is the real one now, the night sky
    above, the water below, black and rose. Once in the film."""
    night()
    w = show("w1")
    eye = Vector((-11.0, 1.0, 0.18))
    look(eye, (-6.0, 0.6, 0.2), lens=35, fstop=5.6, roll=40.0 + 140.0 * ease(u))


URA = [(70, "u1"), (72, 72), (73, "u2"), (75, 75), (76, "u4"), (77, 77)]
# the world between her 裏 pictures, somewhere new each time: (eye, its drift, target, lens)
URA_WORLD = {72: ((-9.0, 3.0, 0.7), (1.5, -2.0, 0.8), (0.0, 2.5, 3.65), 60.0),
             75: ((-5.0, -6.5, 0.2), (2.5, 2.0, 0.0), (0.0, 1.0, 2.6), 26.0),
             77: ((-14.0, 5.8, 0.15), (4.0, -2.5, 0.0), (0.0, 0.6, 2.2), 32.0)}


def p7_ura(u, t, b):
    """P7.2: her 裏 pictures alternate with the world: U1 (lying on the black water, straight down: her water is
    the night sea, a ring a beat, the camera close and travelling up her to the face), the world (the letters glowing
    rose, seen from a new place each time), U2, the world, U4."""
    night()
    key = None
    for bar0, k in URA:
        if b >= bar0:
            key = k
    if key == "u1":
        v = (b - 70.0) / 2.0
        fu, fv = face("u1")
        into("u1", zoom=2.4 + 0.5 * v, at_point=(fu + 0.2 * (1 - ease(v)), fv), roll=8.0 * v)
        put(S.sea_bump, 0.0)
        _T.gain = 1.5
        ring(CLK.last_beat(t), -6.0, 1.0, amp=1.0, speed=1.6, life=1.5)
    elif key == "u2":
        v = (b - 73.0) / 2.0
        into("u2", zoom=1.2 + 0.65 * v, at_point=face("u2", 0.1 * (1.0 - v), -0.16 + 0.1 * v), roll=-3.0 + 5.0 * v)
        _T.gain = 1.6
    elif key == "u4":
        into_free("u4", (-9.0, 0.0, 1.4), (-6.0, 0.0, 1.4), 50.0, zoom=1.08 + 0.4 * (b - 76.0))
        _T.gain = 1.3
    else:
        eye, drift, to, lens = URA_WORLD[key]
        v = b - key
        # what it looks at moves too: round a fixed point the letters stood still in the frame
        look(Vector(eye) + Vector(drift) * v, Vector(to) + Vector(drift) * 0.4 * v, lens=lens, fstop=8.0)


def p7_reflect(u, t, b):
    """P7.3: her 表 on the night water, her reflection her 裏; the camera tilts from her face down over the water
    line and closes on the face upside down; once a bar the reflection flashes back to 表."""
    night(letters=0.6)
    dusk(1.0)
    q = show("q1s")
    eye = Vector((-8.2 + 1.6 * u, 0.6 - 1.2 * u, 0.6))
    facing(q, eye)
    back = (b % 1.0) < 0.12
    S.figs["q1u"].hide_render = back
    S.figs["q1m"].hide_render = not back
    facing(S.figs["q1u"], eye)
    facing(S.figs["q1m"], eye)
    look(eye, Vector((-3.0, 0.0, 1.45 - 2.9 * ease(u))), lens=45 + 35 * ease(u), fstop=4.0)
    bpy.context.scene.view_settings.exposure += 0.8 * ease(u)  # the water's mirror is darker than she is


def p7_crack(u, t, b):
    """P7.4: a crack of light runs from her feet across the water."""
    night(letters=0.6)
    dusk(1.0)
    q = show("q1s")
    look((-9.0 + 1.5 * u, -2.5, 1.0), (-3.0, 0.0, 0.3), lens=35, fstop=5.6)
    facing(q, S.eye)
    reveal("feet", ease(u))


def p8_shards(u, t, b):
    """P8: the surface bursts: the shards leap up off the water on the first beat and hang in the air, each a mirror
    with a moment of her in it; the red deep under them; the camera between them, a cut each half bar, close on one
    shard that turns to face it; on the last beat the small ones make her silhouette and
    the big ones fly off."""
    night(letters=0.4)
    clear_sea(0.6)
    energy(S.red_deep, 9000.0)
    k = (b - 83.0) / 4.0
    up = 1.0 - math.exp(-7.0 * clamp((b - 83.0) / 0.7))
    gather = ease(clamp((b - 86.0) / 0.9))
    cut = int(k * 8)
    v = (k * 8) % 1.0
    rnd = random.Random(cut)
    hero = rnd.choice([s for s in S.shards if s.get("grid") is None])
    for s in S.shards:
        ob = s["ob"]
        ob.hide_render = False
        home = s["home"]
        bob = Vector((0.0, 0.0, 0.15 * math.sin(t * 1.3 + s["ph"])))
        at_home = Vector((home.x, home.y, 0.02)).lerp(home, up) + bob
        if s.get("grid") is not None:
            ob.location = at_home.lerp(s["grid"], gather)
        else:
            ob.scale = (s["big"],) * 3
            ob.location = at_home + (at_home - Vector((-5.0, 0.0, 1.6))) * 2.0 * gather
        ob.rotation_quaternion = Quaternion(s["spin"], (0.6 * t + s["ph"] + 9.0 * (1.0 - up)) * (1 - gather))
    pos = hero["ob"].location.copy()
    if cut < 6:
        ang = rnd.uniform(0.0, 2 * math.pi)
        eye = pos + Vector((-2.4 * abs(math.cos(ang)), 2.4 * math.sin(ang), rnd.uniform(-0.3, 0.5)))
        eye.z = max(0.3, eye.z)
        hero["ob"].rotation_quaternion = (eye - pos).to_track_quat("X", "Z")
        hero["ob"].scale = (5.0,) * 3
        look(eye.lerp(pos, 0.12 * v), pos, lens=32, fstop=4.0, roll=rnd.uniform(-20.0, 20.0))
    else:
        look((-11.0 + 1.5 * v, rnd.uniform(-1.5, 1.5), 1.4), (-5.0, 0.0, 1.6), lens=30, fstop=5.6)
    if v < 0.15 and cut in (0, 6):
        put(S.lineart, 1.0)


def p9_run(u, t, b):
    """P9.1: she runs: 24 mm backing away low over the water before her (R0), each beat a step: the paper rises, leans
    and swings, a ring from the foot that lands, her hair streaming; the wall going away behind her, the letters' light
    far off; a shard of the surface past the lens on the downbeats; the Dutch angle turning each bar."""
    night(sky=0.6)
    x = -6.0 - 34.0 * u
    step = (b * 4.0) % 1.0
    foot = 1.0 if int(b * 4.0) % 2 else -1.0
    r = show("r0", x=x, y=0.08 * foot * math.sin(math.pi * step))
    eye = Vector((x - 2.2, 0.35 * math.sin(u * 7.0), 0.42 + 0.06 * abs(math.sin(math.pi * step))))
    facing(r, eye)
    r.location.z += 0.13 * math.sin(math.pi * step)
    r.rotation_euler.z += math.radians(9.0 * foot * math.sin(math.pi * step))
    r.rotation_euler.y += math.radians(2.5 * foot)
    _T.gain, _T.wind = 2.6, (0.01 * foot, 0.012)
    look(eye, (x, 0.0, 0.95), lens=24, fstop=4.0)
    ring(CLK.last_beat(t), x - 0.1, 0.12 * foot, amp=1.8, speed=4.5, life=0.5)
    if (b % 1.0) < 0.14:                                       # a shard past the lens
        s = S.shards[-1]
        w = (b % 1.0) / 0.14
        s["ob"].hide_render = False
        s["ob"].scale = (3.0,) * 3
        s["ob"].location = eye + S.fwd * 0.9 + Vector((0.0, 1.3 - 2.6 * w, 0.2 - 0.3 * w))
        s["ob"].rotation_quaternion = Quaternion((0.3, 0.8, 0.5), t * 3.0)


def p9_r0(u, t, b):
    """P9.2: inside R0, she runs at the lens and grows and grows; on the downbeat of 96 the picture tears down the
    middle, the only time her picture is torn, and behind it is the real night sea and sky."""
    night()
    k = ease(clamp((b - 93.0) / 3.0)) ** 1.6
    zoom = 1.08 + 0.95 * k
    _T.gain, _T.wind = 2.8, (0.0, 0.016)
    if b < 96.0:
        into("r0", zoom=zoom, at_point=face("r0", 0.0, -0.03))
        return
    w = ease(clamp((b - 96.0) / 0.9))
    into("r0", zoom=zoom, at_point=face("r0", 0.0, -0.03))
    _T.blur = dict(scale=1.0 + 0.08 * (1 - w))
    S.into["r0"].hide_render = True
    M = S.into["r0"].matrix_world
    for ob, side in S.halves:                                 # each half on its outer edge, swinging away like a door
        ob.hide_render = False
        ob.matrix_world = M @ Matrix.Translation((0.0, side * 0.5, 0.0)) @ \
            Matrix.Rotation(side * math.radians(95.0) * w, 4, "Z")


def p9_back(u, t, b):
    """P9.3: she stops and looks back (KV', 裏, night, rose); behind her the whole sea lifts like a sheet of paper
    into a black wall of water, against a sky bright enough to show it rise."""
    night(sky=0.35 if b < 98.0 else 1.1)
    if b < 98.0:
        into("kvn", zoom=1.25 + 0.2 * (b - 97.0), at_point=face("kvn", 0.0, -0.05), roll=-3.0 * (b - 97.0))
        _T.gain, _T.wind = 2.2, (0.012, 0.0)
        return
    k = ease(clamp(b - 98.0))
    eye = Vector((-11.0 + 1.5 * k, -3.4, 0.5))
    show("kvn", x=-7.2, y=-1.8, eye=eye)
    _T.gain, _T.wind = 2.4, (0.014, 0.0)
    lift(80.0 * k, 0.0)
    look(eye, (4.0, -0.4, 1.6 + 7.0 * k), lens=20, fstop=5.6)


def p10_tear(u, t, b):
    """P10, first pass: the lifted sea tears open down the middle from the horizon like paper, and outside is the
    sky (S3), bright; on the downbeat of 101 the wall bursts into pieces; she leaps (F1), the scraps whirl round her,
    the camera rising and going round with her."""
    twin_suns((-5.0, 3.5, 1.6), (-5.0, 10.0, 2.5))
    if b < 103.0:
        lift(80.0, 50.0 * ease(clamp((b - 99.0) / 3.5)) ** 1.5)
        burst = clamp((b - 101.0) / 2.0)
        if b >= 101.0:
            hide_wall(True)
            wall_pieces(1.0 - math.exp(-3.0 * burst), t)
            if b < 101.1:
                put(S.lineart, 1.0)
        v = surge((b - 99.0) * 2) / 8
        look((-14.0 + 4.0 * v, -3.4 + 2.0 * v, 0.7), (4.0, 0.0, 5.0 + 2.0 * v), lens=22, fstop=8.0)
        scraps(Vector((-2.0, 0.0, 3.0)), radius=6.0, height=4.0, swirl=0.6)
        return
    hide_wall(True)
    v = (b - 103.0) / 4.0
    up = 1.0 - math.exp(-3.5 * v)
    ang = math.radians(-115.0 + 55.0 * surge(v * 8) / 8)
    her = Vector((-5.0, 10.0, 2.6 + 3.0 * up))
    eye = her + Vector((6.4 * math.cos(ang), 6.4 * math.sin(ang), -1.0 + 0.4 * v))
    show("f1", eye=eye, lift=3.0 * up)
    _T.gain, _T.wind = 2.8, (0.0, 0.012)
    look(eye, her, lens=40, fstop=5.6, roll=-7.0 + 14.0 * v)
    scraps(her, radius=3.0, height=3.0, swirl=1.4)


FAST = ["f1", "w_sky", "c1", "w_high", "r0", "w_low", "u2", "w_kv", "a1", "w_sky", "kvn", "w_low", "w2", "w_high",
        "c3", "w_kv", "u1", "w_sky", "c4", "w_low", "f1", "w_high", "a5", "w_kv", "u4", "w_sky", "c2", "w_low", "q1",
        "w_high", "f2", "w_kv"]


def p10_fast(u, t, b):
    """P10, second pass: the same, faster: the sky above and below, no water, no wall; the two suns at the ends of the
    sky; a cut every half bar between the pictures and the 3D sky, every beat in the last four bars, the cold and rose
    light trading sides each beat; each cut rushes in, the sky's at its own tilt."""
    step = 0.5 if b < 111 else 0.25
    k = int((b - 107.0) / step)
    v = ((b - 107.0) / step) % 1.0
    item = FAST[k % len(FAST)]
    swap = int(b * 4) % 2 == 1 and b >= 111
    rush = 1.0 - math.exp(-4.0 * v)
    hide_wall(True)
    if item.startswith("w_"):
        frm, to = {"w_sky": ((-6.0, 0.0, 1.5), (4.0, 3.0, 9.0)), "w_high": ((-6.0, 0.0, 9.0), (6.0, 0.0, 3.0)),
                   "w_low": ((-6.0, 0.0, 0.3), (6.0, 2.0, 2.0)), "w_kv": ((-8.0, 4.0, 1.4), (6.0, -2.0, 4.0))}[item]
        twin_suns(to if swap else frm, frm if swap else to)
        put(S.sea_metal, 1.0)                                  # no water: the sky below too (hidden, the bed showed grey)
        put(S.sea_base, (1.0, 1.0, 1.0, 1.0))
        put(S.sea_bump, 0.0)
        rnd = random.Random(k)
        eye = Vector(frm).lerp(Vector(to), 0.2 * rush)
        look(eye, to, lens=24, fstop=8.0, roll=rnd.uniform(-35.0, 35.0) + 25.0 * v)
        scraps(Vector((-2.0, 0.0, 3.0)), radius=8.0, height=5.0, swirl=1.2)
        return
    twin_suns((-5.0, 3.5, 1.6), (-5.0, 10.0, 2.5))
    _T.gain = 2.6
    zoom = 1.12 + 0.28 * rush
    if item in ("f1", "r0", "kvn", "a1", "a5", "u1", "u2") and item in S.into and INTO[item][1]:
        if item in ("u1", "a1"):
            zoom += 0.8                                        # she is small in these: go to her
        into(item, zoom=zoom, at_point=face(item, 0.0, -0.03))
    elif item == "q1":
        key = "a5o" if "a5o" in S.into else "a5"
        into(key, zoom=zoom + 0.1, at_point=face(key))
    elif item in S.into:
        into_free(item, (-6.0, 0.0, 1.5), (0.0, 0.0, 1.5), 50.0, zoom=zoom)


def p10_f2(u, t, b):
    """P10 end: F2 on the first beat of the last bar (one eye cold, one rose); on the last beat the whirl stops,
    the scraps fall, the water comes back, still, in the night the back cover is in."""
    if b < 115.25:
        twin_suns((-6.0, 0.0, 1.5), (0.0, 0.0, 1.5))
        hide_wall(True)
        into_free("f2", (-6.0, 0.0, 1.5), (0.0, 0.0, 1.5), 50.0, zoom=1.08 + 0.5 * (b - 115.0))
        _T.gain = 2.0
        return
    night(letters=0.5, sky=0.25)
    put(S.sea_bump, 0.0)
    look((-14.0, 0.0, 1.0), (0.0, 0.0, 2.0), lens=35, fstop=8.0)
    scraps(Vector((-4.0, 0.0, 3.0)), radius=6.0, height=4.0, fall=ease((b - 115.25) / 0.75))


def p11_back(u, t, b):
    """P11: straight down on the still water at the wall's foot: in the wall's reflection the two letters read
    backwards, 裏表; the light behind them goes out; black; one tiny ring on the water."""
    lit = max(0.0, 1.0 - ease(u * 1.4))
    night(letters=lit, sky=0.2)
    put(S.letters_em.inputs["Strength"], 8.0 * lit)
    # low over the water at the reflection: from straight above the near-black water mirrors next to nothing
    look((-11.0 + 0.8 * u, 2.5, 1.6), (0.0, 2.5, -3.6), lens=50, fstop=8.0)
    if u > 0.8:
        ring(at(116.0) + 0.85 * (CLK.duration - at(116.0)), -2.4, 2.5, amp=0.4, speed=0.6, life=1.5)


SHOTS = [
    (-2, "P0", "horizon", p0_horizon), (2, "P0", "two letters", p0_letters), (4, "P0", "wall, window, her", p0_layers),
    (7, "P0", "through the window", p0_through),
    (8, "P1", "A1 in the light", p1_light), (12, "P1", "eyes open", p1_eyes), (14, "P1", "the first drop", p1_drop),
    (16, "P1", "seeping", p1_seep), (20, "P1", "the glass is the sea", p1_glass_top),
    (24, "P2", "whips, cracks", p2_whip), (28, "P2", "wind", p2_wind), (30, "P2", "lights out", p2_out),
    (31, "P3", "表 and 裏 over the water", p3_turn),
    (35, "P4", "chorus", p4_chorus),
    (47, "P5", "spill", p5_spill), (51, "P5", "red sea", p5_full), (55, "P5", "dolly zoom", p5_vertigo),
    (56, "P5", "cut", p5_cut),
    (57, "P6", "rain on the sea", p6_rain), (61, "P6", "W1, W2", p6_w1), (64, "P6", "round to the side", p6_side),
    (66, "P6", "rain to lines", p6_lines),
    (68, "P7", "roll", p7_roll), (70, "P7", "ura", p7_ura), (78, "P7", "the reflection", p7_reflect),
    (82, "P7", "crack", p7_crack),
    (83, "P8", "shards", p8_shards),
    (87, "P9", "run", p9_run), (93, "P9", "R0 tears", p9_r0), (97, "P9", "looks back", p9_back),
    (99, "P10", "the sea tears, F1", p10_tear), (107, "P10", "second pass", p10_fast), (115, "P10", "F2", p10_f2),
    (116, "P11", "back cover", p11_back),
]


def main():
    AN.run(FRAMES, SHOTS, CLK, setup, reset, after=alive, first=FIRST, last=LAST, name="animatic v5")


if __name__ == "__main__":
    main()
