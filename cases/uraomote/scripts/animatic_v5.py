"""v5 animatic: script_v5.md section 5 in the world of v5_world.py (the sky, the sea to the horizon, the one wall
with its window and 表 裏 cut through it, the glass of water on the sill), cut on the song's downbeats and
rendered small to judge the pacing, the cameras and the dimension events before the real render.

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
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

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
PUNCH = [(35, 47), (51, 55), (87, 116)]                   # bars with the impact push on every beat
DUTCH = (87, 99)                                          # bars with the Dutch angle, ±12° turning each bar
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


def lifted_sea():
    """P9 end / P10: the sea far behind her lifted like a sheet into a black wall of water, hinged on a line across
    it; a copy of the sea's material on a 300 x 60 m sheet that swings up about its near edge."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=24, size=1.0)
    ob = bpy.context.active_object
    ob.name = "lifted"
    ob.data.transform(Matrix.Translation((0.5, 0.0, 0.0)))                # hinge at x 0, the sheet towards +X
    ob.data.transform(Matrix.Diagonal((60.0, 300.0, 1.0, 1.0)))
    ob.data.materials.append(S.sea.data.materials[0])
    ob.location = (8.0, 0.0, 0.005)
    ob.hide_render = True
    return ob


def setup():
    W.build()
    sc = scene_settings()
    S.glass_light_lamp = S.glass_light                       # the panel behind the glass (an emitter, hidden)
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
    AN.stamp()
    S.hidden = [S.ink["ob"], S.burst["ob"], S.glass_ink["ob"], S.rain_ob, S.dust, S.conf, S.deep, S.sea_under,
                S.shutter, S.lifted, S.glass_light, S.letters_back] + [s["ob"] for s in S.shards] + [ob for ob, _ in S.halves] + \
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
    sky = bpy.data.objects["sky"]
    if sky.rotation_euler.z != 0.0:
        sky.rotation_euler.z = 0.0
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
    S.lifted.rotation_euler.y = 0.0


def look(eye, target, lens=35.0, fstop=8.0, roll=0.0, focus=None, up=(0, 0, 1), ortho=None):
    """The camera at `eye` looking at `target`, with the beat push and the Dutch angle where the script has them."""
    eye, target = Vector(eye), Vector(target)
    if any(a <= _T.b < z for a, z in PUNCH):
        eye = eye + (target - eye) * punch(_T.t, 0.03)
    if DUTCH[0] <= _T.b < DUTCH[1]:
        roll += 12.0 if math.floor(_T.b) % 2 else -12.0
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
    W.set_sky("s3", 1.6)
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
    fx.ink(blob, loc, scale, density, glow, _T.t)


def flash():
    """D4: the frame as its own negative on paper for a frame or two after a downbeat."""
    if _T.t - CLK.last_beat(_T.t) < 1.6 / FPS and abs(_T.b - round(_T.b)) < 0.05:
        put(S.lineart, 1.0)


def beat_in_bar():
    return int((_T.b % 1.0) * 4)


def hide_wall(h=True):
    for ob in S.wall_parts:
        ob.hide_render = h


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
    lens = 18.0 / tw * zoom                                   # the frame (36 mm wide) as wide as the plate's view
    look(eye, target, lens=lens, fstop=16.0, roll=roll, focus=D_SHEET, up=tuple(u))
    S.cam.data.dof.use_dof = False
    if not wall:
        hide_wall(True)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = exposure


def into_free(key, eye, target, lens, d=0.6, glow=1.0, exposure=0.0):
    """A v4 close-up (no plate): the picture on the image plane `d` before a camera at `eye`, filling the frame,
    the world behind its planes."""
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
    look(eye, target, lens=lens, fstop=16.0, focus=d)
    S.cam.data.dof.use_dof = False
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = exposure


def seep(key, v, blob=None):
    """Rose ink soaking into picture `key` from her hair (the stain, by v 0..1); with `blob`, a wisp of ink in the
    air just before the picture, running down."""
    ob, pic = S.into[key], INTO[key][0]
    hair = H.anchor(ob, pic, 0)
    H.stain(ob.name, *H.sheet_uv(ob, pic, *hair["uv"]), 0.02 + 0.07 * v)
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
    look(P0_EYE, P0_TARGET, lens=32, fstop=8.0)
    bpy.context.scene.view_settings.exposure = -0.4
    S.shutter.hide_render = False


def p0_letters(u, t, b):
    """P0.2: the sun rises behind a wall we cannot see yet: two letters of light in the dark, their long
    reflections running to the lens."""
    aim_sun(P0_EYE)
    energy(S.sun, 5.0 * ease(clamp((b - 2) / 0.5)))
    S.sun_disc.hide_render = False
    W.set_sky("s1", 0.14)
    haze(0.004)
    S.shutter.hide_render = False
    look(P0_EYE + Vector((1.0 * u, -0.2 * u, 0.0)), P0_TARGET, lens=32, fstop=8.0)
    bpy.context.scene.view_settings.exposure = -0.4


def p0_layers(u, t, b):
    """P0.3: a layer of light a downbeat: the wall's outline against the brightening sky (4), the window opens on
    the dawn (5), and on the 6th downbeat she is there before it, a drawn girl standing on the water."""
    dawn(1.0, sky=1.8 * (0.25 + 0.75 * ease(clamp(b - 4.0))), toward=P0_EYE)
    S.shutter.hide_render = b >= 5.0
    if b < 6.0:
        look(P0_EYE + Vector((1.0 + 1.0 * u, -0.2 - 0.2 * u, 0.0)), P0_TARGET, lens=32, fstop=8.0)
        return
    v = clamp(b - 6.0)
    eye = Vector((-7.4, -3.7, 0.9)) + Vector((0.6, 0.3, 0.0)) * v
    show("kv", eye=eye)
    look(eye, (-1.4, -1.0, 1.6), lens=35, fstop=4.0, focus=(-1.6, -1.2, 1.2))


def p0_through(u, t, b):
    """P0.4: the camera rushes at the window glass and through it, four frames, into A1."""
    dawn(1.0)
    show("kv", eye=(-4.0, -1.8, 1.4))
    k = ease(u) ** 2
    eye = Vector((-4.0, -1.8, 1.5)).lerp(Vector((-0.02, -0.9, 2.6)), k)
    look(eye, (1.0, -0.9, 2.7), lens=28, fstop=5.6)
    if u > 0.9:
        into("a1", zoom=1.0 + 0.4 * (1 - (u - 0.9) / 0.1))


def p1_light(u, t, b):
    """P1.1: inside A1. Her window is the real sky: the camera pans two degrees and the clouds slide behind the
    frame; dust in the beam is 3D; on every downbeat a cloud's shadow passes over her."""
    dawn(1.0)
    shade = 1.0 - 0.25 * math.exp(-((b % 1.0) - 0.3) ** 2 / 0.02)
    into("a1", zoom=1.08, pan=-1.0 + 2.0 * u, glow=shade)
    pic, plate = INTO["a1"]
    eye, f, r, uu, lens, tw, th = plate_frame(plate)
    dust(eye + f * 1.6 + Vector((0.0, 0.0, -2.2)))


def p1_eyes(u, t, b):
    """P1.2: A5 closed-eyed, on the downbeat of 13 A5 open-eyed: the same picture, her eyes open."""
    dawn(1.0)
    key = "a5o" if b >= 13.0 and "a5o" in S.into else "a5"
    into(key, zoom=1.04 + 0.04 * u)


def p1_drop(u, t, b):
    """P1.3: macro, the glass of water on the sill, the dawn behind it; on the downbeat of 15 a rose drop falls
    into it and blooms down through the water, the film's first colour."""
    dawn(1.0)
    S.glass_light.hide_render = False
    S.glass_light.location.z = 1.5                             # behind the glass (it sees the low panes, inverted)
    g = S.glass_at
    look(g + Vector((-0.55, 0.12, 0.08)), g + Vector((0.0, 0.0, 0.05)), lens=85, fstop=2.8)
    bpy.context.scene.cycles.glossy_bounces = 14
    bpy.context.scene.cycles.max_bounces = bpy.context.scene.cycles.transmission_bounces = 14
    v = clamp((t - at(15.0)) / 1.4)
    if t >= at(15.0) - 0.15:
        if t < at(15.0):                                       # the drop, falling
            k = (at(15.0) - t) / 0.15
            ink(S.burst, g + Vector((0.0, 0.0, 0.09 + 0.25 * k)), (0.004, 0.004, 0.008), 6.0, 0.2)
        else:
            ink(S.glass_ink, g + Vector((0.0, 0.0, 0.075 - 0.025 * v)), (0.006 + 0.012 * v, 0.006 + 0.012 * v,
                                                                         0.008 + 0.03 * v), 3.0, 0.15)


def p1_seep(u, t, b):
    """P1.4: the same red in 2D: inside Q1 (A5 open-eyed) it soaks into her hair from the roots, and a wisp of
    ink runs down the air before her face (3D)."""
    dawn(1.0)
    key = "a5o" if "a5o" in S.into else "a5"
    into(key, zoom=1.1 + 0.06 * u)
    seep(key, ease(u), S.ink)


def p1_glass_top(u, t, b):
    """P1.5: straight down on the glass, the ink turning in it; the camera rises and the glass's mouth becomes a
    red ring on the sea, thirty metres down: the same swirl, the wall's reflection beside it, her small at the
    window."""
    dawn(1.0)
    g = S.glass_at
    h = 0.12 * math.exp(math.log(30.0 / 0.12) * ease(u))
    look(g + Vector((0.0, 0.0, 0.1 + h)), g, lens=50, fstop=8.0, up=(1, 0, 0))
    ink(S.glass_ink, g + Vector((0.0, 0.0, 0.06)), (0.022, 0.022, 0.03), 3.0, 0.15)
    if u > 0.35:                                               # the red on the sea under the window: ink at the surface
        k = ease((u - 0.35) / 0.4)                             # (the sea's own glow was a flat red floor in v4)
        ink(S.ink, Vector((-1.2, -0.9, -0.03)), (0.3 + 1.6 * k, 0.3 + 1.6 * k, 0.05), 3.0, 0.5)
        clear_sea(0.3)
        show("kv")
    if b >= 23.0:                                              # P1.6: the first crack runs from the red
        reveal("sea", ease((b - 23.0) / 0.9))


def whip_world(u, t, b):
    """P2: the world between the whips: skimming the water along the wall."""
    eye = Vector((-9.0 + 2.0 * u, -6.0 + 3.0 * u, 0.45))
    look(eye, (0.0, 1.0, 2.2), lens=32, fstop=8.0)


WHIP = {24: "a2", 25: "a3", 26: "a4", 27: "a1w"}


def p2_whip(u, t, b):
    """P2.1-2.2: a whip a bar, from the world into a picture's front and back out; a crack of light on every
    downbeat, in 3D (the water, the wall, the glass) and in 2D (across the picture)."""
    dawn(1.0)
    bar = int(math.floor(b))
    v = b - bar
    key = WHIP.get(bar, "a2")
    if 0.3 <= v < 0.85 and key in S.into:
        into(key, zoom=1.06, pan=6.0 * (1 - ease(clamp((v - 0.3) / 0.12))))
    else:
        whip_world(v, t, b)
        if v < 0.3:
            S.cam.rotation_euler.rotate_axis("Y", math.radians(-25.0 * ease(clamp((v - 0.22) / 0.08))))
    bpy.context.scene.render.use_motion_blur = 0.22 <= v < 0.34 or 0.8 <= v < 0.9
    name = ("sea", "wall", "glass", "sea")[bar % 4]
    reveal(name, ease(clamp(v / 0.2)))
    flash()


def p2_wind(u, t, b):
    """P2.3: the wind: the clouds run, the water roughens, the glass's water shivers."""
    dawn(1.0)
    put(S.sea_bump, 0.35)
    bpy.data.objects["sky"].rotation_euler.z = math.radians(4.0 * u)       # the clouds run
    look(Vector((-12.0, 4.0, 1.2)) + Vector((0.0, -3.0 * u, 0.0)), (0.0, -0.5, 2.6), lens=28, fstop=8.0)
    show("kv", eye=S.eye)


def p2_out(u, t, b):
    """P2.4: the dawn goes out a beat at a time: the world dark but for the crack's red and the letters."""
    k = 1.0 - 0.25 * beat_in_bar() - 0.25 * ease((b % 0.25) * 4)
    dawn(max(0.0, k))
    energy(S.letters_glow, 400.0 * (1 - max(0.0, k)))
    put(S.letters_em.inputs["Strength"], 3.0 * (1 - max(0.0, k)))
    S.letters_back.hide_render = k >= 1.0
    reveal("sea", 1.0)
    look((-18.0, 0.0, 0.6), (0.0, 0.6, 2.4), lens=40, fstop=8.0)


def p3_turn(u, t, b):
    """P3: her 表 (Q1) on the water at nightfall; in the water her 裏 (the twin) where her reflection should be.
    The camera at water level turns round her and, a beat at a time (a half beat in bar 34), tilts from her face
    to the face in the water and back. On the last beat the water bursts in a ring from her feet and the camera
    dives in."""
    dusk(1.0)
    q = show("q1s")
    S.figs["q1u"].hide_render = False
    x, y = q.location.x, q.location.y
    ang = math.radians(-20.0 + 40.0 * u)
    eye = Vector((x - 5.2 * math.cos(ang), y - 5.2 * math.sin(ang), 0.55))
    facing(q, eye)
    facing(S.figs["q1u"], eye)
    step = 2.0 if b >= 34.0 else 1.0
    phase = ((b % 1.0) * 4 * step) % 2.0
    down = ease(clamp(phase - 0.5)) if phase < 1.0 else 1.0 - ease(clamp(phase - 1.5))
    target = Vector((x, y, 1.45 - 2.9 * down))
    look(eye, target, lens=40, fstop=4.0)
    if b >= 34.75:
        k = clamp((b - 34.75) / 0.25)
        ring(at(34.75), x, y, amp=2.0, speed=6.0)
        look(eye.lerp(Vector((x, y, -0.8)), ease(k)), Vector((x, y, -2.0)), lens=40, fstop=4.0)


CHORUS_CAMS = ["skim", "top", "half", "window", "up"]


def chorus_cam(kind, u):
    if kind == "skim":                                     # ① skimming the water towards the wall
        look((-16.0 + 9.0 * u, -1.5, 0.3), (0.0, 0.0, 1.6), lens=24, fstop=8.0)
    elif kind == "top":                                    # ② straight down, the ink opening by the wall's reflection
        look((-3.0, -0.6, 9.0), (-3.0, -0.6, 0.0), lens=28, fstop=8.0, up=(1, 0, 0))
    elif kind == "half":                                   # ③ half in the water: the world above, the deep below
        look((-9.0 + 2.0 * u, 0.4, 0.0005), (0.0, 0.2, 0.0005), lens=20, fstop=8.0)
    elif kind == "window":                                 # ④ through the window towards the horizon
        e = Vector((-3.0, -1.2, 2.6)).lerp(Vector((3.0, -1.2, 2.6)), ease(u))
        look(e, e + Vector((10.0, 0.0, -0.4)), lens=24, fstop=8.0)
    else:                                                  # ⑤ from under the water, looking up
        look((-6.0, -1.0, -2.2), (-2.0, -0.6, 1.0), lens=20, fstop=8.0)


def p4_chorus(u, t, b):
    """P4: a dimension event a beat: (1) push and the negative on paper, (2) a pulse ring over the whole water,
    (3) ink bursting in the deep, (4) half a beat inside a chorus picture (C1-C4), back to 3D. A camera a bar,
    five in turn; from bar 41 the deep glows red under the cold mirror."""
    dawn(1.0)
    bar = int(math.floor(b))
    beat = beat_in_bar()
    v = (b % 1.0) * 4 - beat
    red = 0.0 if b < 41 else ease(clamp((b - 41) / 5.0))
    kind = CHORUS_CAMS[(bar - 35) % 5]
    if beat == 3 and v < 0.5:
        key = CHORUS[(bar - 35) % 4]
        into_free(key, (-8.0, -1.0, -4.0), (-2.0, -0.6, -4.4), 35.0)
        underwater(red=0.4 + red, shafts=0.8)
        return
    if kind in ("half", "up"):
        underwater(red=red)
        put(S.sea_base, (0.55, 0.62, 0.66, 1.0))
        if kind == "half":
            S.sea.hide_render = False
    else:
        clear_sea(0.35 + 0.4 * red)
        energy(S.red_deep, 9000.0 * red)
    chorus_cam(kind, b % 1.0)
    flash()
    ring(CLK.last_beat(t) if beat == 1 else -10.0, -2.0, -0.6, amp=1.2, speed=7.0, life=0.6)
    if beat >= 2:
        k = clamp(((b % 1.0) * 4 - 2) / 2.0)
        ink(S.burst, Vector((-2.5, -0.6, -1.4 + 0.6 * k)), (0.5 + 2.0 * k, 0.5 + 2.0 * k, 0.4 + 1.2 * k), 1.4, 0.5)


def p5_spill(u, t, b):
    """P5.1: inside C1 the ink round her rises along her hair; her water is the sea: the camera follows the ink
    out of the picture and up through the surface, and from above the red spreads on the sea."""
    if u < 0.55:
        into_free("c1", (-8.0, -1.0, -4.0 + 1.2 * u), (-2.0, -0.6, -4.4 + 1.6 * u), 35.0)
        underwater(red=0.6, shafts=0.8)
        ink(S.ink, Vector((-7.45, -0.97, -3.95 + 1.3 * u)), (0.004, 0.004, 0.03 + 0.05 * u), 2.5, 0.4)
    else:
        dawn(1.0)
        k = (u - 0.55) / 0.45
        clear_sea(0.55)
        energy(S.red_deep, 9000.0 * 0.6)
        look((-6.0, -1.0, 0.5 + 6.0 * ease(k)), (-3.0, -0.6, 0.0), lens=28, fstop=8.0)
        ink(S.ink, Vector((-4.0, -0.8, -0.05)), (2.0 + 2.0 * k, 2.0 + 2.0 * k, 0.12), 1.0, 0.6)


def p5_full(u, t, b):
    """P5.2: the whole sea lit red from below, the cold sky still in its mirror; skimming, a push a beat; the
    wall's reflection red."""
    dawn(1.0)
    clear_sea(0.6)
    energy(S.red_deep, 9000.0)
    look((-14.0 + 6.0 * u, 2.0, 0.25), (0.0, 0.0, 2.0), lens=24, fstop=8.0)
    show("kv", eye=S.eye)


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
    look(eye, her + Vector((0.0, 0.0, 0.3)), lens=lens, fstop=5.6)


def p5_cut(u, t, b):
    """P5.4: black for a beat. Then the rain's sound."""
    W.set_sky("s1", 0.0)
    look((-20.0, 0.0, 1.0), (0.0, 0.0, 1.0), lens=35)
    bpy.context.scene.view_settings.exposure = -10.0


def p6_rain(u, t, b):
    """P6.1: the first night (S2): rain over the whole sea, its rings; the wall dark but for the window; W1 far out
    on the water, small, in the rain; the camera comes in slowly from behind her."""
    rain_night()
    w = show("w1")
    eye = Vector((-30.0 + 12.0 * ease(u), 1.2, 1.4))
    facing(w, eye)
    look(eye, (-6.0, 0.6, 1.4), lens=35, fstop=5.6)
    rain3d((eye.x + 6.0, eye.y, 6.0), t, 0.45)


def p6_w1(u, t, b):
    """P6.2: W1's back grows, the window's light edges her rose, the rain falls before her, her reflection under
    her; then W2 fills the frame, the rain falling before her face (3D)."""
    rain_night()
    if b < 62.5:
        w = show("w1")
        eye = Vector((-12.5 + 2.0 * u, 0.9, 1.25))
        facing(w, eye)
        look(eye, (-6.0, 0.6, 1.15), lens=45, fstop=4.0)
        rain3d((eye.x + 3.0, eye.y, 6.0), t, 0.45)
    else:
        into_free("w2", (-9.0, 0.6, 1.4), (-6.0, 0.6, 1.4), 50.0, exposure=0.0)
        rain3d((-8.4, 0.6, 6.0), t, 0.5)


def p6_side(u, t, b):
    """P6.3: round her figure by 90 degrees: she becomes a line; on round to the back, bare paper. She is paper."""
    rain_night()
    w = show("w1")
    yaw0 = w.rotation_euler.z
    ang = math.pi + yaw0 + math.radians(170.0 * ease(u))
    eye = Vector((w.location.x + 4.0 * math.cos(ang), w.location.y + 4.0 * math.sin(ang), 1.1))
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
    look(eye, Vector((-6.0, 0.6, 1.0 - 2.2 * tilt)), lens=40, fstop=4.0, roll=40.0 * tilt)
    rain3d((eye.x + 3.0, eye.y, 6.0), t, 0.5)
    if 66.0 <= b < 67.0 and _T.t - CLK.last_beat(_T.t) < 1.6 / FPS:
        put(S.lineart, 1.0)


def p7_roll(u, t, b):
    """P7.1: the camera on the water rolls through 180 degrees: the reflection is the real one now, the night sky
    above, the water below, black and rose. Once in the film."""
    night()
    w = show("w1")
    eye = Vector((-11.0, 1.0, 0.18))
    look(eye, (-6.0, 0.6, 0.2), lens=35, fstop=5.6, roll=40.0 + 140.0 * ease(u))


URA = [(70, "u1"), (72, None), (73, "u2"), (75, None), (76, "u4"), (77, None)]


def p7_ura(u, t, b):
    """P7.2: her 裏 pictures alternate with the world: U1 (lying on the black water, straight down: her water is
    the night sea, a ring a beat), the world (the letters glowing rose), U2, the world, U4."""
    night()
    key = None
    for bar0, k in URA:
        if b >= bar0:
            key = k
    if key == "u1":
        into("u1", zoom=1.04)
        put(S.sea_bump, 0.0)
        ring(CLK.last_beat(t), -6.0, 1.0, amp=1.0, speed=1.6, life=1.5)
    elif key == "u2":
        into("u2", zoom=1.04 + 0.04 * ((b - 73) / 2.0))
    elif key == "u4":
        into_free("u4", (-9.0, 0.0, 1.4), (-6.0, 0.0, 1.4), 50.0)
    else:
        v = (b % 1.0)
        show("u2")
        look((-16.0 + 2.0 * v, 3.0, 0.4), (0.0, 1.5, 2.6), lens=35, fstop=8.0)


def p7_reflect(u, t, b):
    """P7.3: her 表 on the night water, her reflection her 裏; the camera tilts from her face down over the water
    line to the face upside down; once a bar the reflection flashes back to 表."""
    night(letters=0.6)
    dusk(1.0)
    q = show("q1s")
    eye = Vector((-8.2, 0.6, 0.6))
    facing(q, eye)
    back = (b % 1.0) < 0.12
    S.figs["q1u"].hide_render = back
    S.figs["q1m"].hide_render = not back
    facing(S.figs["q1u"], eye)
    facing(S.figs["q1m"], eye)
    look(eye, Vector((-3.0, 0.0, 1.45 - 2.6 * ease(u))), lens=45, fstop=4.0)


def p7_crack(u, t, b):
    """P7.4: a crack of light runs from her feet across the water."""
    night(letters=0.6)
    dusk(1.0)
    q = show("q1s")
    look((-9.0, -2.5, 1.0), (-3.0, 0.0, 0.3), lens=35, fstop=5.6)
    facing(q, S.eye)
    reveal("feet", ease(u))


def p8_shards(u, t, b):
    """P8: the surface bursts into hundreds of shards hanging in the air, each a mirror with a moment of her in it;
    the red deep under them; the camera between them, a cut each half bar, each cut a negative first; on the last
    beat they make her silhouette."""
    night(letters=0.4)
    clear_sea(0.6)
    energy(S.red_deep, 9000.0)
    k = (b - 83.0) / 4.0
    gather = ease(clamp((b - 86.0) / 0.9))
    for s in S.shards:
        ob = s["ob"]
        ob.hide_render = False
        home = s["home"]
        if s.get("grid") is not None and gather > 0:
            ob.location = home.lerp(s["grid"], gather)
        else:
            ob.location = home + Vector((0.0, 0.0, 0.15 * math.sin(t * 1.3 + s["ph"])))
        ob.rotation_quaternion = Quaternion(s["spin"], (0.6 * t + s["ph"]) * (1 - gather))
    cut = int(k * 8)
    rnd = random.Random(cut)
    eye = Vector((rnd.uniform(-13.0, -7.0), rnd.uniform(-3.0, 3.0), rnd.uniform(0.6, 3.2)))
    v = (k * 8) % 1.0
    look(eye + Vector((1.2 * v, 0.0, 0.0)), (-5.0, 0.0, 1.6), lens=28, fstop=5.6)
    if v < 0.15:
        put(S.lineart, 1.0)


def p9_run(u, t, b):
    """P9.1: she runs: 24 mm backing away low over the water before her (R0), each step a ring and a splash, the
    wall going away behind her, the letters' light far off; a shard of the surface past the lens on the
    downbeats; the Dutch angle turning each bar."""
    night()
    x = -6.0 - 9.0 * u
    r = show("r0", x=x, y=0.0)
    eye = Vector((x - 3.2, 0.0, 0.5))
    facing(r, eye)
    r.location.z = S.fig_home["r0"][0].z + 0.05 * abs(math.sin(math.pi * 2 * (b % 0.5)))
    look(eye, (x, 0.0, 1.0), lens=24, fstop=4.0)
    ring(CLK.last_beat(t), x + 0.1, 0.0, amp=1.4, speed=3.0, life=0.6)


def p9_r0(u, t, b):
    """P9.2: inside R0, she runs at the lens; on the downbeat of 96 the picture tears down the middle, the only
    time her picture is torn, and behind it is the real night sea and sky."""
    night()
    if b < 96.0:
        into("r0", zoom=1.0 + 0.25 * ease(clamp((b - 93.0) / 3.0)), at_point=(0.5, 0.7))
        return
    w = ease(clamp((b - 96.0) / 0.9))
    into("r0", zoom=1.25, at_point=(0.5, 0.7))
    S.into["r0"].hide_render = True
    M = S.into["r0"].matrix_world
    for ob, side in S.halves:                                 # each half on its outer edge, swinging away like a door
        ob.hide_render = False
        ob.matrix_world = M @ Matrix.Translation((0.0, side * 0.5, 0.0)) @ \
            Matrix.Rotation(side * math.radians(95.0) * w, 4, "Z")


def p9_back(u, t, b):
    """P9.3: she stops and looks back (KV', 裏, night, rose); behind her the whole sea lifts like a sheet of paper
    into a black wall of water."""
    night()
    if b < 98.0:
        into("kvn", zoom=1.3, at_point=(0.5, 0.78))
        return
    k = ease(clamp(b - 98.0))
    show("kvn", eye=(-9.0, -2.4, 1.0))
    S.lifted.hide_render = False
    S.lifted.rotation_euler.y = -math.radians(80.0 * k)
    look((-9.0, -2.4, 1.0), (4.0, -0.4, 3.0 + 6.0 * k), lens=24, fstop=5.6)


def p10_tear(u, t, b):
    """P10, first pass: the lifted sea tears open from the horizon like paper, and outside is the sky (S3); the
    wall in pieces; she leaps (F1), the scraps whirl round her, the camera rising with her."""
    twin_suns((-5.0, 3.5, 1.6), (-5.0, 10.0, 2.5))
    if b < 103.0:
        S.lifted.hide_render = False
        S.lifted.rotation_euler.y = -math.radians(80.0)
        S.lifted.scale.y = max(0.0, 1.0 - ease(u * 2))
        look((-12.0, -3.0, 1.0), (4.0, 0.0, 6.0), lens=24, fstop=8.0)
        scraps(Vector((-2.0, 0.0, 3.0)), radius=6.0, height=4.0, swirl=t * 0.6)
        return
    f = show("f1")
    v = (b - 103.0) / 4.0
    eye = Vector((-5.0, 3.5, 1.6 + 1.5 * ease(v)))
    facing(f, eye)
    look(eye, (-5.0, 10.0, 2.6 + 1.0 * ease(v)), lens=40, fstop=5.6)
    scraps(Vector((-5.0, 10.0, 2.6)), radius=3.0, height=3.0, swirl=t * 1.4)


FAST = ["f1", "w_sky", "c1", "w_high", "r0", "w_low", "u2", "w_kv", "a1", "w_sky", "kvn", "w_low", "w2", "w_high",
        "c3", "w_kv", "u1", "w_sky", "c4", "w_low", "f1", "w_high", "a5", "w_kv", "u4", "w_sky", "c2", "w_low", "q1",
        "w_high", "f2", "w_kv"]


def p10_fast(u, t, b):
    """P10, second pass: the same, faster: the sky above and below, no water; the two suns at the ends of the sky;
    a cut every half bar between the pictures and the 3D sky, every beat in the last four bars, the cold and rose
    light trading sides each beat."""
    step = 0.5 if b < 111 else 0.25
    k = int((b - 107.0) / step)
    item = FAST[k % len(FAST)]
    swap = int(b * 4) % 2 == 1 and b >= 111
    if item.startswith("w_"):
        frm, to = {"w_sky": ((-6.0, 0.0, 1.5), (4.0, 3.0, 9.0)), "w_high": ((-6.0, 0.0, 9.0), (6.0, 0.0, 3.0)),
                   "w_low": ((-6.0, 0.0, 0.3), (6.0, 2.0, 2.0)), "w_kv": ((-8.0, 4.0, 1.4), (6.0, -2.0, 4.0))}[item]
        twin_suns(to if swap else frm, frm if swap else to)
        S.sea.hide_render = True
        look(frm, to, lens=24, fstop=8.0)
        scraps(Vector((-2.0, 0.0, 3.0)), radius=8.0, height=5.0, swirl=t * 1.2)
        return
    twin_suns((-5.0, 3.5, 1.6), (-5.0, 10.0, 2.5))
    if item in ("f1", "r0", "kvn", "a1", "a5", "u1", "u2") and item in S.into and INTO[item][1]:
        into(item, zoom=1.05)
    elif item == "q1":
        into("a5o" if "a5o" in S.into else "a5", zoom=1.1)
    elif item in S.into:
        into_free(item, (-6.0, 0.0, 1.5), (0.0, 0.0, 1.5), 50.0)


def p10_f2(u, t, b):
    """P10 end: F2 on the first beat of the last bar (one eye cold, one rose); on the last beat the whirl stops,
    the scraps fall, the water comes back, still."""
    if b < 115.25:
        twin_suns((-6.0, 0.0, 1.5), (0.0, 0.0, 1.5))
        into_free("f2", (-6.0, 0.0, 1.5), (0.0, 0.0, 1.5), 50.0)
        return
    dawn(0.3, sky=0.6)
    look((-14.0, 0.0, 1.0), (0.0, 0.0, 2.0), lens=35, fstop=8.0)
    scraps(Vector((-4.0, 0.0, 3.0)), radius=6.0, height=4.0, fall=ease((b - 115.25) / 0.75))


def p11_back(u, t, b):
    """P11: straight down on the still water at the wall's foot: in the wall's reflection the two letters read
    backwards, 裏表; the light behind them goes out; black; one tiny ring on the water."""
    night(letters=max(0.0, 1.0 - ease(u * 1.4)), sky=0.2)
    look((-7.0, 2.5, 7.5), (-3.4, 2.5, 0.0), lens=35, fstop=8.0)            # high and steep: the wall just out
    if u > 0.8:                                                                 # of the top, its reflection fills it
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
    AN.run(FRAMES, SHOTS, CLK, setup, reset, first=FIRST, last=LAST, name="animatic v5")


if __name__ == "__main__":
    main()
