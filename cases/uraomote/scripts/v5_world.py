"""v5 天与水之间 (script_v5.md, section 1): the world is a sky, a mirror of water to the horizon, one old plaster
wall standing in the water with a tall window and the two letters 表 裏 cut through it, a glass of water on the
window's sill, and her: a cut-out 2D figure standing on the water (scripts/figures.py, hybrid.make_figure). No
room, no hung prints. Stills to confirm the world before the shots:

    blender -b --factory-startup -P cases/uraomote/scripts/v5_world.py -- [out_dir] [shot ...]
    shots: dawn (the wall and the letters' light at sunrise, her at the window)
           rain (a rainy night: W1 standing far out on the water, the window glowing)
           waterline (her face over the water line, her 裏 in the water below it)
    RES=50 SAMPLES=48 for a quick look

The wall is built in paper.sheet's frame (origin the middle of its top edge, facing -X, y along it, z down), so
hybrid_fx.cut_letters works on it unchanged; the viewer's side is -X, the sun rises behind the wall at +X.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import assets as A  # noqa: E402
import cyc  # noqa: E402
import hybrid as H  # noqa: E402
import hybrid_fx as fx  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import paper as P  # noqa: E402
import texlib as T  # noqa: E402

ART = P.ART = os.path.join(C.CASE, "art", "v4")
H.HERO = {"v4_kv_211"}
FONT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
ROSE, GLOW = "#F0285A", "#FF5C8A"
SAMPLES = int(os.environ.get("SAMPLES", 0))             # 0: each shot's own count
SEA, DOME = 2000.0, 3000.0                               # the water's radius, the sky's
WALL_W, WALL_H, WALL_T = 8.0, 6.0, 0.4                  # the wall: along y, up, thick (x 0..T, the viewer at -X)
WIN_Y, WIN_W, WIN_Z0, WIN_Z1 = -1.2, 2.4, 0.9, 4.5        # the window: centre y (the viewer's right is -Y), width, sill, head
LETTERS = [("表", 2.6, -(WALL_H - 3.9)), ("裏", 2.6, -(WALL_H - 2.9))]   # the viewer's left, 3.9 and 2.9 m up
SKIES = {"s1": "v4_s1_211", "s2": "v4_s2_211", "s3": "v4_s3_211"}


class S:
    """What the shots move, filled by build()."""


# ---------------------------------------------------------------- the world

def water():
    """The sea: a 3 cm sheet of near-black water over a black bed, out to SEA, a mirror with the slowest ripple;
    the beat ring (fx.water_ring) and the rain's rings (a Value, 0 dry .. 1 pouring) are in its material."""
    bed = A._principled("seabed", **{"Base Color": (0.004, 0.004, 0.006, 1.0), "Roughness": 0.9})[0]
    bpy.ops.mesh.primitive_circle_add(vertices=256, radius=SEA, fill_type="NGON", location=(0, 0, -0.03))
    bpy.context.active_object.name = "seabed"
    bpy.context.active_object.data.materials.append(bed)
    mat, b = A._principled("sea", **{"Base Color": (0.03, 0.03, 0.035, 1.0), "Roughness": 0.015, "IOR": 1.33,
                                     "Transmission Weight": 1.0})
    A._bump(mat, b, 0.35, 0.015, detail=2.0, distance=0.03)       # still water: a mirror, not a mosaic
    bpy.ops.mesh.primitive_circle_add(vertices=256, radius=SEA, fill_type="NGON", location=(0, 0, 0.0))
    sea = bpy.context.active_object
    sea.name = "sea"
    sea.data.materials.append(mat)
    S.sea = sea
    ring = fx.water_ring(mat, ROSE)
    S.rip, S.sea_glow, S.sea_bump, S.SEA_BUMP = ring["rip"], ring["glow"], ring["bump"], ring["bump0"]
    # the rain's rings: Voronoi cells over the surface, each a ring expanding from its centre with its own phase,
    # fading with distance; `rain` scales their height
    nt = mat.node_tree
    g = kit.G(nt)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    last = bsdf.inputs["Normal"].links[0].from_node
    tc = g.node("ShaderNodeTexCoord")
    vor = g.node("ShaderNodeTexVoronoi", {"Scale": 3.0, "Randomness": 1.0})
    g.link(tc.outputs["Object"], vor.inputs["Vector"])
    S.rain_t = kit.value(nt, 0.0)
    sepc = g.node("ShaderNodeSeparateColor")
    g.link(vor.outputs["Color"], sepc.inputs[0])
    d = vor.outputs["Distance"]
    r = g.math("FRACT", g.math("ADD", sepc.outputs["Red"], g.math("MULTIPLY", S.rain_t, 1.7)))    # each cell's ring, 0..1
    e = g.math("SUBTRACT", g.math("MULTIPLY", d, 3.0), g.math("MULTIPLY", r, 0.9))              # distance from the ring
    wave = g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", e, 2 * math.pi / 0.12)),
                  g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", e, e), -1 / 0.08 ** 2)))
    fade = g.math("SUBTRACT", 1.0, r)                                                            # young rings high
    S.rain = kit.value(nt, 0.0)
    rb = g.node("ShaderNodeBump", {"Strength": 1.0, "Distance": 0.012})
    g.link(g.math("MULTIPLY", g.math("MULTIPLY", wave, fade), S.rain), rb.inputs["Height"])
    g.link(last.outputs["Normal"], rb.inputs["Normal"])
    g.link(rb.outputs["Normal"], bsdf.inputs["Normal"])
    return sea


def sky():
    """The painted sky on a dome (D2: 3D occupied by 2D): the picture laid round the dome by azimuth (twice,
    mirrored) and up by elevation, its bottom row drawn out below the horizon. The image is swapped per shot."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=DOME, location=(0, 0, 0))
    dome = bpy.context.active_object
    dome.name = "sky"
    mat, nt, out = P.nodes("sky")
    g = kit.G(nt)
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(g.node("ShaderNodeTexCoord").outputs["Object"], sep.inputs[0])
    az = g.math("DIVIDE", g.math("ARCTAN2", sep.outputs["Y"], sep.outputs["X"]), math.pi)        # -1..1 round
    el = g.math("POWER", g.math("DIVIDE", sep.outputs["Z"], DOME, clamp=True), 0.6)              # 0 horizon .. 1 zenith
    uv = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", az, 1.0), uv.inputs["X"])
    g.link(g.math("ADD", g.math("MULTIPLY", el, 0.88), 0.1), uv.inputs["Y"])
    tex = g.node("ShaderNodeTexImage", extension="MIRROR")
    tex.image = P.image(SKIES["s1"])
    g.link(uv.outputs[0], tex.inputs["Vector"])
    em = g.node("ShaderNodeEmission", {"Strength": 1.0})
    g.link(tex.outputs["Color"], em.inputs["Color"])
    g.link(em.outputs[0], out.inputs["Surface"])
    dome.data.materials.append(mat)
    dome.visible_shadow = False
    dome.visible_glossy = True
    S.sky_tex, S.sky_em = tex, em
    return dome


def set_sky(key, strength):
    S.sky_tex.image = P.image(SKIES[key])
    cyc.put(S.sky_em.inputs["Strength"], strength)


def wall():
    """One old plaster wall standing in the water, in the sheet frame (origin the middle of its top edge at
    (0, 0, WALL_H), facing -X): a tall window with a thin steel frame, old glass and a sill, and 表 裏 cut through
    the wall to the left of it. Returns the wall."""
    body = "painted_plaster_wall" if T._find("painted_plaster_wall", "diffuse") else "worn_plaster_wall"
    calm = {} if body == "painted_plaster_wall" else {"flat": ("#9C9B95", 0.55)}
    plaster = T.pbr(body, scale=1.5, bump=0.5, tint="#C4C2BA", name="plaster", **calm)
    steel = A._principled("frame", **{"Base Color": m.srgb("#23272B"), "Roughness": 0.55})[0]
    ob = A.rounded_box("wall", (WALL_T, WALL_W, WALL_H), 0.0, [plaster])
    ob.data.transform(Matrix.Translation((WALL_T / 2, 0.0, -WALL_H / 2)))     # x 0..T, z 0..-H about the top edge
    ob.location = (0.0, 0.0, WALL_H)
    S.plaster = plaster
    # the window: a hole, cut with a box a little deeper than the wall
    hh = WIN_Z1 - WIN_Z0
    cut = A.rounded_box("window_cut", (WALL_T + 0.2, WIN_W, hh), 0.0, [steel])
    cut.location = (WALL_T / 2, WIN_Y, (WIN_Z0 + WIN_Z1) / 2)
    cut.hide_render = True
    cut.display_type = "WIRE"
    mod = ob.modifiers.new("window", "BOOLEAN")
    mod.operation, mod.object = "DIFFERENCE", cut
    try:
        mod.solver = "EXACT"
        mod.use_hole_tolerant = True
    except (TypeError, AttributeError):
        pass
    zc = (WIN_Z0 + WIN_Z1) / 2
    for dy in (-WIN_W / 2, WIN_W / 2):
        A.rounded_box(f"jamb{dy:+.1f}", (0.1, 0.08, hh + 0.08), 0.003, [steel]).location = (WALL_T / 2, WIN_Y + dy, zc)
    for dy in (-WIN_W / 6, WIN_W / 6):
        A.rounded_box(f"mullion{dy:+.1f}", (0.08, 0.05, hh), 0.003, [steel]).location = (WALL_T / 2, WIN_Y + dy, zc)
    for k in range(6):
        A.rounded_box(f"transom{k}", (0.08, WIN_W, 0.05), 0.003, [steel]).location = (WALL_T / 2, WIN_Y, WIN_Z0 + k * hh / 5)
    pane = A.rounded_box("pane", (0.006, WIN_W, hh), 0.0, [A.clear_glass()])
    pane.location = (WALL_T / 2, WIN_Y, zc)
    pane.visible_shadow = False
    sill = A.rounded_box("sill", (WALL_T + 0.3, WIN_W + 0.3, 0.08), 0.004, [plaster])
    sill.location = (WALL_T / 2 - 0.15, WIN_Y, WIN_Z0 - 0.04)
    S.sill_top = WIN_Z0
    glow = fx.emission_mat("letter_lamp", "#FF8DA6", 1.1)[0]
    S.letter_lamps = fx.cut_letters(ob, FONT, LETTERS, 0.7, glow, radius=0.42, offsets=(-0.22, 0.0, 0.22),
                                    x=WALL_T + 0.3, at=WALL_T / 2, extrude=WALL_T / 2 + 0.05)
    for lamp in S.letter_lamps:
        lamp.hide_render = True
    S.wall = ob
    return ob


def glass():
    """A glass of clear water on the sill, before the window, and the soft panel inside the pane that its water
    refracts (seen by transmission rays alone)."""
    S.glass_at = Vector((-0.2, WIN_Y + 0.3, S.sill_top))
    fx.glass_of_water("glass", S.glass_at)
    S.glass_ink = fx.ink_volume("glass_ink", 3.0)
    S.glass_ink["ob"].hide_render = True
    bpy.ops.mesh.primitive_plane_add(size=1.6, location=(WALL_T / 2 - 0.05, WIN_Y, (WIN_Z0 + WIN_Z1) / 2),
                                     rotation=(0.0, math.pi / 2, 0.0))
    S.glass_light = bpy.context.active_object
    S.glass_light.name = "glass_light"
    S.glass_light.scale = (1.0, 1.6, 1.0)
    S.glass_light.data.materials.append(fx.emission_mat("glass_light", "#EAF2FF", 2.0)[0])
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_volume_scatter", "visible_shadow"):
        setattr(S.glass_light, attr, False)
    S.glass_light.hide_render = True


def haze(density):
    """A little haze over the sea round the wall, for the light through the letters and the window; its box
    reaches under the water (a box face on the surface kills the water's reflections)."""
    return cyc.haze("haze", (80.0, 80.0, 24.0), (0.0, 0.0, 11.5), density, color="#E4ECF4", anisotropy=0.3)


def sun(direction, energy, kelvin, angle=0.6, name="sun"):
    lt = bpy.data.lights.new(name, "SUN")
    lt.energy, lt.angle, lt.color = energy, math.radians(angle), A.kelvin(kelvin)
    ob = bpy.data.objects.new(name, lt)
    m._link(ob)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector(direction).normalized().to_track_quat("-Z", "Y")     # direction: the way the light travels
    return ob


def figure(name, picture, x, y, yaw=0.0, height=1.62, seed=0, emission=None):
    """Her, cut out of `picture`, standing on the water at (x, y), turned by `yaw` degrees (0: her picture facing
    -X, the viewer's side)."""
    ob = H.make_figure(name, picture, x, y, height=height, bottom=0.012, seed=seed, emission=emission)
    ob.rotation_euler.z += math.radians(yaw)
    return ob


def build():
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0, 0.0, 0.0))
    water()
    sky()
    wall()
    glass()
    S.haze = haze(0.004)
    S.haze_vol = next(n for n in S.haze.data.materials[0].node_tree.nodes if n.type == "PRINCIPLED_VOLUME")


# ---------------------------------------------------------------- the stills

def still_dawn():
    """Sunrise behind the wall: the letters as light with their long reflections, the window full of the dawn
    sky, and her (the KV) standing on the water before the wall, lit from behind, her reflection under her."""
    set_sky("s1", 1.4)
    sun((-1.0, 0.25, -0.17), 7.0, 6200)                 # low, from behind the wall, a little from the viewer's left
    cyc.put(S.haze_vol.inputs["Density"], 0.006)
    S.her = figure("her", "v4_kv_211", -2.6, -0.3, yaw=0.0, height=1.15)   # the KV shows her to the knees: she
    #                                                                       stands in the water to there
    fill = cyc.area_light("fill", (-7.0, -4.0, 3.0), (-2.6, -0.3, 1.2), 4.0, 9000, 90, color="#9FB2D8")
    fill.visible_glossy = False
    eye, target = (-10.5, 2.4, 0.55), (-1.4, -0.6, 1.5)
    return cyc.camera("dawn", eye, target, 35, 5.6), target, 0.3


def still_rain():
    """A rainy night: W1 far out on the water with her back to us, rain and its rings on the whole sea, the
    window the only light."""
    set_sky("s2", 0.5)
    cyc.put(S.haze_vol.inputs["Density"], 0.008)
    cyc.put(S.haze_vol.inputs["Color"], m.srgb("#C8D0E0"))
    cyc.put(S.rain, 1.0)
    cyc.put(S.rain_t, 0.37)
    cyc.put(S.sea_bump, 0.12)
    S.her = figure("her", "v4_w1_211", -6.0, 0.6, yaw=0.0)
    glow = cyc.area_light("window_glow", (WALL_T + 0.4, WIN_Y, (WIN_Z0 + WIN_Z1) / 2), (-6.0, WIN_Y, 1.5), 2.0,
                          2000, 900, size_y=3.4, color=ROSE)
    glow.visible_glossy = False
    key = cyc.area_light("key", (-9.5, -2.5, 2.4), (-6.0, 0.6, 1.1), 1.5, 9000, 110, color="#7C94FF")
    key.visible_glossy = False
    S.rain_ob, S.rain_em = fx.rain()
    S.rain_ob.location = (-7.0, 0.0, 0.0)
    S.rain_ob.scale = (1.4, 1.4, 1.0)
    cyc.put(S.rain_em.inputs["Strength"], 0.5)
    eye, target = (-14.5, 1.0, 1.25), (-6.0, 0.6, 1.1)
    return cyc.camera("rain", eye, target, 40, 4.0), target, 0.6


def still_waterline():
    """Her face over the water line and, in the water under it, her 裏 (U2) where her reflection should be: the
    water's mirror alone sees a lit U2 figure standing in her place."""
    set_sky("s2", 0.35)
    cyc.put(S.haze_vol.inputs["Density"], 0.004)
    cyc.put(S.haze_vol.inputs["Color"], m.srgb("#C4BCD0"))
    cyc.put(S.sea_bump, 0.0)
    S.her = figure("her", "v4_q1_211", -3.0, 0.0, yaw=0.0, height=0.78)      # Q1 is a bust: head to chest
    S.her.visible_glossy = False
    ura = figure("ura", "v4_u2_211", -3.0 - 0.002, 0.0, yaw=0.0, height=0.78, emission=9.0)
    for attr in ("visible_camera", "visible_diffuse", "visible_transmission", "visible_shadow"):
        setattr(ura, attr, False)                       # only the water's mirror sees her 裏
    cold = cyc.area_light("cold", (-6.5, -2.0, 2.6), (-3.0, 0.0, 1.3), 2.0, 9000, 160, color="#7C94FF")
    cold.visible_glossy = False
    rose = cyc.area_light("rose", (-1.4, 1.5, 2.2), (-3.0, 0.0, 1.2), 2.0, 2000, 120, color=ROSE)
    rose.visible_glossy = False
    eye, target = (-7.6, 0.8, 0.8), (-3.0, 0.0, 0.25)
    return cyc.camera("waterline", eye, target, 28, 5.6), target, 0.5


STILLS = {"dawn": still_dawn, "rain": still_rain, "waterline": still_waterline}


def main():
    out, shots = cyc.args(os.path.join(C.RENDERS, "v5_world"), ["dawn"])
    if len(shots) != 1:
        sys.exit("one still a run (the sky and the lights differ): " + " ".join(STILLS))
    build()
    cam, target, exposure = STILLS[shots[0]]()
    cyc.render_shots({shots[0]: cam}, shots, out, "world", focus={shots[0]: target},
                     samples={shots[0]: SAMPLES or 128}, exposure={shots[0]: exposure},
                     blend=f"world_{shots[0]}.blend")


if __name__ == "__main__":
    main()
