"""v4 animatic in 3D: section 5 of script_v4.md shot by shot in the drying hall of v4_hall.py, cut on the song's
downbeats, rendered in Cycles at low resolution and sample count to judge the pacing, the cameras and the dimension
events before the real render. The 3D shots carry the script's effects in the scene itself: the ceiling lamps
lighting the KV on the downbeats, KV' showing through it, 表 and 裏 cut out of it, prints turning, lifting, wet and
torn, pulse ripples on the water, rose ink as a volume, rain, cracks, shards of glass, the walls falling away to the
painted sky, flying paper, the line-art flash (D4), the roll, the dolly zoom and the Dutch angle. A 2D shot goes
*into* the hybrid print that carries its picture (into()): the camera before the paper, the frame as wide as the
picture, her planes the hall's and her figure a relief, never a card before the lens.

    blender -b --factory-startup -P cases/uraomote/scripts/animatic_v4.py -- <frames_dir> [first_bar last_bar]
    env: FPS=12 SAMPLES=16 WIDTH=640, LIMIT=1 (the first frame of every shot), AT=0.5 (that point of every shot),
         ONLY=P4,P5 (those sections), DEVICE=CPU (render on the CPU), DRY=1 (run the shots, render nothing)
    python scripts/cut.py <frames_dir> cases/uraomote/audio/urao_mix.m4a <out.mp4> 12

The engine (the song's clock, the frame loop, the camera, the finish) is scripts/animatic.py; the prints are
scripts/paper.py and scripts/hybrid.py; the ink, cracks, rain, scraps, shards, strands and letters are
scripts/hybrid_fx.py. This file is what is particular to this film: the hall's props, its lights, and section 5
of script_v4.md shot by shot.

Frames are numbered on the song's clock and frames already there are skipped, so bar ranges can run side by side
into one folder. Every frame starts from the hall at rest with every light off (reset()), and the shot sets what it
needs, so any frame can be rendered alone. Pictures not drawn yet: Q2 is U2 on the back of Q1's print, U3 is staged
with the reflection trick of P7.3, R1-R6 are missing (the run has only its ripples and the prints it tears).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

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
import v4_hall as V  # noqa: E402

FRAMES, FIRST, LAST = AN.args(os.path.join(C.RENDERS, "animatic_v4", "frames"))
FPS, SAMPLES = AN.FPS, AN.SAMPLES
CLK = AN.Clock(os.path.join(C.AUDIO, "urao_timing.json"))     # the beats found stop at bar 116; the song rings on
at, bar_at, punch, last_beat = CLK.at, CLK.bar_at, CLK.punch, CLK.last_beat
ease, clamp, put, energy = AN.ease, AN.clamp, AN.put, AN.energy
DURATION, LAST_BEAT = CLK.duration, CLK.last_beat_t
H.SKY, H.HERO = "v4_s1_211", {V.KV[0]}               # the sky behind every picture's window; the KV at the full relief
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
REFL = Vector((35.2, -5.6, 0.0))                     # a 表 print whose reflection is her 裏 (P7.3, U3); it faces +X
#                                                      and the camera 4 m beyond it looks back down the hall (at x 38
#                                                      that camera stood outside the far wall); clear of the shot from
#                                                      above (x 29.8-34.0)
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


# ---------------------------------------------------------------- building

def _pic(key):
    return PICK.get(key, f"v4_{key}_211")


def _path(key):
    return P.path(_pic(key))


def sill_glass():
    """M1 (script 6): a glass of clear water on the sill of a high window, for the first drop of ink."""
    x, y = 7.0, V.WD / 2                            # on the sill the hall gives every window, before its middle
    #                                                 pane (0.4 m left of that it stood in front of a mullion, which
    #                                                 the water column magnified into a black tube)
    S.glass_at = Vector((x, y - 0.2, 6.0))
    fx.glass_of_water("glass", S.glass_at)
    S.glass_ink = fx.ink_volume("glass_ink", 3.0)
    # what the glass refracts: a soft white panel just inside the pane behind it, in front of the mullions and the
    # piers, seen by transmission rays alone (the camera sees the window as it is), so the glass reads as a glass
    # of water against the light. A cylinder of water is a lens that shows a wide sweep of what is behind it, and
    # most of that was mullions, piers and the dark hall: the glass was a tube of black chrome against a white
    # window (a panel outside the pane changed little: the mullions stayed between it and the glass)
    bpy.ops.mesh.primitive_plane_add(size=1.6, location=(x, V.WD / 2 - 0.02, 6.5), rotation=(math.pi / 2, 0, 0))
    S.glass_light = bpy.context.active_object
    S.glass_light.name = "glass_light"
    S.glass_light.scale = (1.6, 1.0, 1.0)
    S.glass_light.data.materials.append(fx.emission_mat("glass_light", "#EAF2FF", 2.0)[0])   # (at 4 the ink's
    #                                                                                           plume washed out)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_volume_scatter", "visible_shadow"):
        setattr(S.glass_light, attr, False)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0035, segments=16, ring_count=8)
    S.drop = bpy.context.active_object
    S.drop.data.materials.append(fx.emission_mat("drop", ROSE, 3.0)[0])


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
    mat, nt, out = P.nodes("sky3")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(_path("s3"), check_existing=True)
    uv = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.0
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    S.sky3 = fx.mesh("sky3", [(-30, -18, -8), (70, -18, -8), (70, -18, 40), (-30, -18, 40)], [(0, 1, 2, 3)],
                   [(0, 0), (1, 0), (1, 1), (0, 1)], [mat])


def images():
    """Her pictures as Blender images (the skies, swapped on the backdrop by key), and the tiny rose page number
    for the very end (P11), riding with the camera."""
    S.images = {k: P.image(_pic(k)) for k in CARDS}
    cu = bpy.data.curves.new("page0", "FONT")
    cu.body, cu.align_x, cu.align_y = "0", "CENTER", "CENTER"
    S.zero = bpy.data.objects.new("page0", cu)
    m._link(S.zero)
    cu.materials.append(fx.emission_mat("page0", ROSE, 6.0)[0])
    S.zero.parent = S.cam
    fx.only_camera(S.zero)


def board():
    """Her cardboard in the rain (P6): W1 on the front; on the back the kraft board, its corrugation as faint
    bands, mottled, with a pencilled number. (Plain paper there, with W1's night sky uniform over the half the
    camera crosses, was a flat lilac rectangle for a bar; the picture through it gave nothing to see.)"""
    mat, nt, out = P.nodes("board_w1")
    g = kit.G(nt)
    geo = g.node("ShaderNodeNewGeometry")
    co = P.coords(nt)
    pic = P.picture(nt, "v4_w1_211")
    wave = g.node("ShaderNodeTexWave")
    wave.bands_direction = "Z"
    for name, val in (("Scale", 22.0), ("Distortion", 1.5), ("Detail", 1.0)):     # (at 40 the bands were scanlines)
        wave.inputs[name].default_value = val
    g.link(co, wave.inputs["Vector"])
    nz = g.node("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 3.0, 4.0
    g.link(co, nz.inputs["Vector"])
    kraft = kit._mix_rgba(nt, nz.outputs["Fac"], m.srgb("#7E5D3C"), m.srgb("#9A7652"))
    kraft = kit._mix_rgba(nt, g.math("MULTIPLY", wave.outputs["Fac"], 0.15), kraft, m.srgb("#5E4228"))
    col = kit._mix_rgba(nt, geo.outputs["Backfacing"], pic, kraft)
    normal = P.cockle(nt, co)                                                  # cockle and fibre in the raking light
    corr = g.node("ShaderNodeBump")                                             # and the corrugation as relief: as
    corr.inputs["Strength"].default_value = 0.22                                # colour bands alone the board was a
    corr.inputs["Distance"].default_value = 0.004                               # flat pink-brown slab for a bar (at
    #                                                                             0.4 and 40 bands, corrugated plastic)
    g.link(wave.outputs["Fac"], corr.inputs["Height"])
    g.link(normal, corr.inputs["Normal"])
    normal = corr.outputs["Normal"]
    dif = g.node("ShaderNodeBsdfDiffuse")
    g.link(col, dif.inputs["Color"])
    g.link(normal, dif.inputs["Normal"])
    tr = g.node("ShaderNodeBsdfTranslucent")                                    # a little of the lit front comes through
    g.link(P.multiply(nt, kraft, pic), tr.inputs["Color"])
    g.link(normal, tr.inputs["Normal"])
    mix = g.node("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.12
    g.link(dif.outputs[0], mix.inputs[1])
    g.link(tr.outputs[0], mix.inputs[2])
    g.link(mix.outputs[0], out.inputs["Surface"])
    S.board = P.sheet("w1_board", W1C.x, W1C.y, mat, seed=93, top=V.SHEET_H + 0.02)
    cu = bpy.data.curves.new("pencil", "FONT")
    cu.body, cu.size = "No. 17", 0.13
    try:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError:
        pass
    num = bpy.data.objects.new("pencil", cu)
    m._link(num)
    cu.materials.append(A._principled("pencil", **{"Base Color": m.srgb("#2E2825"), "Roughness": 0.9})[0])
    num.parent = S.board
    # seen from behind (+X): its right along +Y
    num.matrix_basis = Matrix.Translation((0.03, -0.9, -3.95)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0),
                                                                         (0, 0, 0, 1)))


def props():
    """The prints and lights of single shots, beyond the last row of the hall (x 29-40)."""
    # the two prints seen closest, under raking lamps: a flatter relief, or its grain mottles the paper
    S.q_print = H.make_print("q_print", QC.x, QC.y, "v4_q1_211", "v4_u2_211", seed=91, fit=True,
                             amount=0.45 * H.RELIEF)
    # C1 printed full-bleed: its dark water to the paper's edge. With a bare border, the spill shot's pull back
    # showed the margin beside her dark picture as a white bar down the frame under the same lamp
    S.c1_print = H.make_print("c1_print", C1C.x, C1C.y, "v4_c1_211", "v4_u1_211", seed=92, fit=True,
                              amount=0.4 * H.RELIEF, margin=0.0)
    S.float_print = P.sheet("float_print", 34.0, -4.0, P.print_mat("v4_q1_211", "v4_u4_211"), seed=94, top=0.0)
    # lying on the water, face up, its top at +X. Laid down, the sheet's bow and curl point into the water, so
    # they are pressed to a few millimetres and the whole sheet held just over the surface (as hung, all but its
    # edges lay under the water, and the shot from above saw a sliver of her face in a grey mirror of the ceiling)
    S.float_print.rotation_euler = (0.0, math.pi / 2, 0.0)
    S.float_print.scale = (0.12, 1.0, 1.0)
    S.float_print.location = (34.0, -4.0, 0.03)
    # what the water mirrors beside the print in the shot from above: a soft white panel where its lamp hangs,
    # seen by glossy rays alone (every lamp is hidden from them, and a lamp's own glossy flag flipped per frame
    # changed nothing under persistent data), shown in P1.5 only. Without it the water was a void and the print
    # a card lying on it.
    # a disc fading to its rim, not a panel: the water mirrored a square at 1.6 and 2.4 m alike, a crisp beige
    # tile lying on it; its reflection lands 0.2-0.4 m off the print's edge over the shot
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(31.9, -1.6, 6.0))
    S.moon = bpy.context.active_object
    S.moon.name = "float_moon"
    mat, nt, out = P.nodes("float_moon")
    g = kit.G(nt)
    grad = g.node("ShaderNodeTexGradient", gradient_type="SPHERICAL")
    g.link(g.node("ShaderNodeTexCoord").outputs["Object"], grad.inputs["Vector"])
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = m.srgb("#FFF3E8")
    g.link(g.math("MULTIPLY", g.math("POWER", grad.outputs["Fac"], 1.5), 8.0), em.inputs["Strength"])
    g.link(em.outputs[0], out.inputs["Surface"])
    S.moon.data.materials.append(mat)
    for attr in ("visible_camera", "visible_diffuse", "visible_transmission", "visible_volume_scatter",
                 "visible_shadow"):
        setattr(S.moon, attr, False)
    # the 表 print whose reflection is her 裏 faces +X, down the hall: the camera on its far side looks back along
    # the rows of prints glowing in the dark, so her face has the hall's depth behind it (facing -X, the camera
    # had the plaster of the far wall 2 m behind the print, and the shot was a print on a wall)
    S.refl_omote = P.sheet("refl_omote", REFL.x, REFL.y, P.print_mat("v4_q1_211", "v4_u4_211"), seed=95, top=2.25)
    glow, nt, out = P.nodes("refl_ura")             # lit by itself: the water reflects only a few percent
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 9.0        # (at 20 the bare margin's reflection, seen at a grazing angle
    #                                                   where the water gives back a quarter, was blown white)
    nt.links.new(P.picture(nt, "v4_u4_211"), em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    S.refl_ura = P.sheet("refl_ura", REFL.x + 0.002, REFL.y, glow, seed=95, top=2.25)
    glow2, nt2, out2 = P.nodes("refl_flash")         # and 表 lit the same way, for the beat the reflection is 表
    em2 = nt2.nodes.new("ShaderNodeEmission")         # again: the paper print itself in the mirror was dim and
    em2.inputs["Strength"].default_value = 9.0        # speckled with its fibre at that grazing angle
    nt2.links.new(P.picture(nt2, "v4_q1_211"), em2.inputs["Color"])
    nt2.links.new(em2.outputs[0], out2.inputs["Surface"])
    S.refl_flash = P.sheet("refl_flash", REFL.x + 0.001, REFL.y, glow2, seed=95, top=2.25)
    for ob in (S.refl_omote, S.refl_ura, S.refl_flash):
        ob.scale = (0.5, 0.5, 0.5)                    # small and low, so the print and all of its reflection fit
        ob.rotation_euler.z += math.pi                # the picture towards +X
    S.refl_omote.visible_glossy = False
    for ob in (S.refl_ura, S.refl_flash):
        for attr in ("visible_camera", "visible_transmission", "visible_diffuse", "visible_shadow"):
            setattr(ob, attr, False)                 # only the water's mirror sees her 裏 (P7.3); in front, unshaded
    S.refl_flash.visible_glossy = False
    board()
    al = cyc.area_light
    S.lights = {
        "sweep": (al("sweep", (1.0, 1.0, 4.7), (2.0, 0.55, 4.7), 1.5, 9000, 3, size_y=0.6, spread_deg=30), 3.0),
        "q_cold": (al("q_cold", QC + Vector((-3.0, -1.5, 0.7)), QC, 2.0, 9000, 300, color="#7C94FF"), 300.0),
        "q_rose": (al("q_rose", QC + Vector((3.0, 1.5, 0.1)), QC, 2.0, 2000, 400, color=ROSE), 400.0),
        "c1_rose": (al("c1_rose", C1C + Vector((0.9, 0, 0.3)), C1C + Vector((0, 0, 0.3)), 2.0, 2000, 260, size_y=3.6,
                       color=ROSE), 260.0),
        "c1_cold": (al("c1_cold", C1C + Vector((-2.4, -1.5, 0.4)), C1C, 2.0, 9000, 120, color="#7C94FF"), 120.0),
        "w1_cold": (al("w1_cold", W1C + Vector((-3.5, -1.0, -0.6)), W1C, 2.0, 9000, 250, color="#7C94FF"), 250.0),
        "w1_rose": (al("w1_rose", W1C + Vector((2.5, 0.5, 1.4)), W1C, 1.5, 2000, 60, color=ROSE), 60.0),
        "w1_back": (al("w1_back", W1C + Vector((3.2, -1.8, 1.2)), W1C + Vector((0, 0, -0.6)), 2.0, 9000, 140,
                       color="#7C94FF"), 140.0),
        "refl_cold": (al("refl_cold", REFL + Vector((4.0, 0, 2.0)), REFL + Vector((0, 0, 1.4)), 2.0, 9000, 120,
                         color="#7C94FF"), 120.0),
        "refl_rose": (al("refl_rose", REFL + Vector((-1.6, 0, 2.0)), REFL + Vector((0, 0, 1.4)), 2.0, 2000, 200,
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


def setup():
    scene = AN.scene()
    cyc.world((0.0004, 0.0004, 0.0008))
    h = V.hall(True)
    S.water, S.plaster = h["water"], h["plaster"]
    S.bulbs, S.lamp_glow = V.lamps()
    V.pipes()
    prints = V.hang(make=H.make_print)
    for key, (x, y) in STAGE.items():                   # the 2D shots' pictures, as prints too, each its own way up
        prints.append(H.make_print(f"stage_{key}", x, y, _pic(key), _pic(STAGE_BACKS[key]), seed=70 + len(prints),
                                   fit=True, margin=0.0 if key == "r0" else None))   # R0 full-bleed: its top
        #                                                 margin, lit, was a white bar across the frame as it tore
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
    S.sky_tex, S.sky_em = fx.sky_backdrop(h["sky_emission"])
    w = fx.water_ring(S.water, ROSE)
    S.rip, S.water_glow, S.water_bump, S.WATER_BUMP = w["rip"], w["glow"], w["bump"], w["bump0"]
    wall_panels(h)
    props()
    S.cam = cyc.camera("anim_cam", (0.0, -1.0, 2.0), (0.0, 0.0, 2.0), 35, 8.0)
    scene.camera = S.cam
    images()
    S.ink, S.burst = fx.ink_volume("ink", 1.0), fx.ink_volume("burst", 7.0)
    sill_glass()
    S.cracks = {}
    # widths are of the whole ribbon; the light is a core a tenth of it and a halo over the inner third, so from
    # 6-8 m (6-7 mm a pixel at 1280) the core is about a pixel and the glow two or three
    for k, x in enumerate((7.0, 15.0)):                               # P2: on the high windows' glass
        S.cracks[f"win{k}"] = fx.crack(f"win{k}", 40 + k, (x - 0.3, V.WD / 2 - 0.02, 8.4), (1, 0, 0), (0, 0, 1), 1.8,
                                       width=0.045)
    for k, name in enumerate(("print_2_+3.2", "print_4_-3.2")):      # P2: across the prints
        S.cracks[f"print{k}"] = fx.crack(f"print{k}", 50 + k, (-0.02, 0.9, -1.4), (0, -1, 0), (0, 0, -0.35), 1.9,
                                         width=0.02, parent=S.prints[name])
    S.cracks["face"] = fx.crack("face", 60, (-0.02, 0.62, -1.55), (0, -1, 0), (0, 0, -0.25), 1.3, width=0.03,
                                parent=S.float_print)
    for k in range(4):                                                 # P7.4: one window giving way
        S.cracks[f"win7_{k}"] = fx.crack(f"win7_{k}", 70 + k, (11.0, V.WD / 2 - 0.02, 8.3),
                                         (math.cos(k * 1.6), 0, math.sin(k * 1.6)),
                                         (-math.sin(k * 1.6), 0, math.cos(k * 1.6)), 1.6, width=0.05)
    S.halves = {name: fx.halves(S.prints[name]) for name in PATH + ["stage_r0"]}
    S.rain, S.rain_em = fx.rain()
    S.conf, S.scrap = fx.confetti(_path("kv"))
    S.dust, S.mote = fx.motes()
    S.shards = fx.shards({k: _path(k) for k in ("kvu", "a1", "q1", "c1", "w2", "u1", "u2", "c3")}, "kvu",
                         (V.SHEET_W, V.SHEET_H))
    # D1: 表 and 裏 cut out of the KV down its left side, and the lamps under them for the back cover (P11); paler
    # and dimmer than the rose: light through paper, not a sign (side by side with ROSE at 1.5 on the back cover;
    # at 6 the letters were a neon sign)
    glow = fx.emission_mat("letter_lamp", "#FF8DA6", 1.1)[0]
    S.letter_lamps = fx.cut_letters(S.kv, FONT, [("表", 0.78, -1.05), ("裏", 0.78, -1.95)], 0.72, glow)
    S.lineart, S.glare = AN.compositor()
    AN.stamp()
    S.mix = {p.name: p.data.materials[0].node_tree.nodes["wet"]
             for p in list(S.prints.values()) + [S.q_print, S.c1_print, S.float_print]}
    # where a 2D shot's picture is: the print, the picture's name, and whether it is on the print's back
    S.where = {key: (S.prints[f"stage_{key}"], _pic(key), False) for key in STAGE}
    S.where.update({"kv": (S.kv, _pic("kv"), False), "kvu": (S.kv, _pic("kvu"), True),
                    # row 2 hangs q1, a5, a1 (FRONTS from k 4): a5 is the middle print. Pointed at the first, the
                    # shot showed q1 under a5's relief, anchors and strands (strands loose in her sky)
                    "a5": (S.prints["print_2_+0.0"], _pic("a5"), False), "q1": (S.q_print, _pic("q1"), False),
                    "u2": (S.q_print, _pic("u2"), True), "c1": (S.c1_print, _pic("c1"), False)})
    S.hair_mats, S.strands = {}, []
    for key, (p, name, on_back) in S.where.items():                           # her hair off the paper, on the hero prints
        if not on_back and key != "c1":                                         # (none on C1: she lies across the page,
            st = fx.strands(p, name, seed=sum(map(ord, key)), mats=S.hair_mats)   # and every strand there was a scratch)
            if st is not None:
                S.strands.append(st)
    S.home = {ob.name: (ob.location.copy(), ob.rotation_euler.copy())
              for ob in list(S.prints.values()) + S.panels + [S.kv]}
    S.everything_lit = S.dawn + S.cold + S.fronts + S.bulbs + list(S.behind.values()) + list(S.lights.values())
    S.hidden = [S.rain, S.conf, S.dust, S.drop, S.zero, S.moon, S.glass_light, S.ink["ob"], S.burst["ob"],
                S.glass_ink["ob"]] + \
        [s["ob"] for s in S.shards] + [ob for hv in S.halves.values() for ob, _ in hv] + S.letter_lamps
    return scene


# ---------------------------------------------------------------- what a shot sets

def reset(scene, t, b):
    """The hall at rest, every light off, nothing in the air: each shot then sets what it needs."""
    S.t, S.b = t, b
    for ob, _ in S.everything_lit:
        if ob.data.energy != 0.0:
            ob.data.energy = 0.0
    for s in S.lamp_glow:
        put(s, 0.0)
    put(S.sky_em.inputs["Strength"], 0.0)
    haze(0.0)
    put(S.rip["a"], 0.0)
    put(S.water_glow, 0.0)
    put(S.water_bump, S.WATER_BUMP)
    for ob in S.hidden:
        if not ob.hide_render:
            ob.hide_render = True
    for p in list(S.prints.values()) + [S.float_print]:
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
    if S.refl_flash.visible_glossy:
        S.refl_flash.visible_glossy = False
    put(S.lineart, 0.0)
    put(S.glare, 0.4)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    scene.cycles.samples = SAMPLES
    scene.cycles.max_bounces = scene.cycles.transmission_bounces = 6
    scene.cycles.glossy_bounces = 4
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


def ripple(t0, x, y, amp=1.0, speed=2.4):
    age = S.t - t0
    if 0 <= age < 1.2:
        S.rip["x"].default_value, S.rip["y"].default_value = x, y
        S.rip["r"].default_value = 0.1 + speed * age
        S.rip["a"].default_value = amp * (1 - age / 1.2)


def ink(blob, loc, scale, density=1.0, glow=0.3):
    fx.ink(blob, loc, scale, density, glow, S.t)


def dust(t, center=(2.0, 0.0, 0.0)):
    fx.dust(S.dust, S.mote, t, center)


def scraps(center, t, radius=4.0, height=3.0, swirl=0.0, fall=0.0, n=None):
    fx.scraps(S.conf, S.scrap, center, t, radius, height, swirl, fall, n)


def look(eye, target, lens=35.0, fstop=8.0, roll=0.0, focus=None, up=(0, 0, 1), ortho=None):
    """Put the camera at `eye` looking at `target`, with the chorus's beat push and the Dutch angle where the script
    has them. `focus` is a distance or a point (default: the target)."""
    eye, target = Vector(eye), Vector(target)
    if any(a <= S.b < z for a, z in PUNCH):
        eye = eye + (target - eye) * punch(S.t, 0.03)
    if DUTCH[0] <= S.b < DUTCH[1]:
        roll += 12.0 if math.floor(S.b) % 2 else -12.0
    S.eye, S.fwd = AN.aim(S.cam, eye, target, lens, fstop, roll, focus, up, ortho)


def into(key, zoom=1.0, cx=None, cy=None, lens=35.0, fstop=2.8, cold=1.0, rose=0.0, yaw=0.0, pitch=0.0,
         sky_key=None, exposure=0.6):
    """A 2D shot: the camera in front of the print that carries picture `key`, the frame covering the picture's
    width over `zoom`, centred on (cx, cy) of the picture (0..1 from its bottom left; by default her face, from
    the parts map). The picture's planes are the hall's and its figure a relief, so the shot is inside the picture,
    not before a card. `yaw`, `pitch` (degrees) look at it a little from the side or above, for the parallax.
    Lit by its own cold lamp in front (`cold`) and the rose lamp behind it (`rose`); the other 2D pictures' prints
    are out of the way."""
    p, name, on_back = S.where[key]
    W, Hh = P.size_of(p)
    img = bpy.data.images.load(_path(key), check_existing=True)
    mu, mv, rw, rh, s = P.layout(*img.size, (W, Hh), H.margin_of(p))
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
        light("c1_cold", 2.4 * cold)                 # C1's lamp is set for the spill; alone it left her in the dark
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
    W, Hh = P.size_of(p)
    S.rain.hide_render = False
    S.rain.scale = (0.5, W / 14.0, 0.5)                   # spread through the depth between the camera and the paper,
    S.rain.location = (p.location.x - 3.6, p.location.y,  # so it is rain, not a curtain of lines
                       p.location.z - Hh - 0.5 * ((t * 6.5) % 8.0))
    put(S.rain_em.inputs["Strength"], 0.45)


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
    z = 4.7 - 1.2 * u                                                           # through the frame, over the cut 表
    cyc._aim(lt, (1.0, 1.0, z), (2.0, 0.55, z))
    sky("s1", 0.12)                                                             # the picture's sky, a portal in the paper,
    bpy.context.scene.view_settings.exposure = -0.8                             # was the white: it is dark before dawn
    # the paper filling the frame (aimed at its edge, half the frame was the dark hall past it)
    look((0.6, 0.3, 4.2), (2.0, 0.55, 4.0), lens=60, fstop=2.8, focus=(2.0, 0.55, 4.0))


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
    scene.cycles.glossy_bounces = 14           # a refraction counts as a glossy bounce too: at the default 4 the
    #                                            path died in the glass's far wall, and the glass was a black tube
    sky("s1", 1.5)                                                              # the glass against the bright window
    S.glass_light.hide_render = False                                           # and bright through its water
    scene.view_settings.exposure = -0.5
    g, t15 = S.glass_at, at(15)
    if t15 - 0.35 <= t < t15:
        S.drop.hide_render = False
        S.drop.location = g + Vector((0, 0, 0.065 + 0.6 * (t15 - t)))
    if t >= t15:
        v = ease((t - t15) / (at(16) - t15))
        s = 0.005 + 0.016 * v
        # from the surface down, taller than wide: a plume, not a blob sitting on the bottom (at 1.0 a balloon)
        ink(S.glass_ink, g + Vector((0, 0, 0.058 - 0.026 * v)), (s * 0.8, s * 0.8, s * 1.5), 0.4, 0.05)
    # level with the water, the glass between the camera and the window: the drop falls into the frame, meets the
    # surface, and the ink blooms down through the lit column. (From below the rim the glass was a black tube, and
    # from above it the water showed only the sill behind it, the bloom lost in the dark.)
    focus = g + Vector((0, 0, 0.045))
    look(g + Vector((0, -0.5, 0.05)), focus, lens=85, fstop=2.8, focus=focus)


def p1_seep(u, t, b):
    if b < 19:                                                                  # P1.4: the ink soaks in from her hair
        night(cold=0.0, rose=0.0)
        v = ease((b - 16) / 3)
        into("q1", 1.05 + 0.04 * u, yaw=-3 + 6 * u, cold=0.7, rose=0.4 * v, sky_key="s1")
        seep("q1", v, S.ink)
        return
    dawn()
    g = S.glass_at
    S.glass_light.hide_render = False
    ink(S.glass_ink, g + Vector((0, 0, 0.035)), (0.026, 0.026, 0.03), 1.2, 0.05)
    eye = Vector((5.35, 3.45, 4.85))
    look(eye, g + Vector((0, 0, 0.04)), lens=50, fstop=1.4, focus=0.9 + ((g - eye).length - 0.9) * ease(b - 19))


def p1_top(u, t, b):
    # the hall dark but for the one lamp on the print, so the water round it is black (at dawn 0.4 it mirrored the
    # lit ceiling as grey plaster, and a window as a white band across the frame)
    night(cold=0.0, rose=0.0, sky_key="s1")
    sky("s1", 0.15)
    light("float_sun", 0.4)                                                     # (at 3.5 the paper was a white slab)
    S.moon.hide_render = False                        # the lamp in the water beside the print, broken by its ripples
    put(S.water_bump, 0.06)                           # the water's own ripples up, so the lamp's disc wobbles
    bpy.context.scene.view_settings.exposure = 0.5
    v = ease((b - 20) / 4)
    # the ink spreads over her on the paper, small and dense enough to read from 5 m up (a 4 m pancake under the
    # print, the same ink spread that thin, was invisible; at 2.5 a faint blush)
    s = 0.8 + 1.2 * v
    ink(S.ink, FLOAT_C + Vector((0.6, 0.0, 0.045)), (s, s, 0.02), 4.0, 0.0)
    # the pulse must get out from under the print (1.2 m to its edge) within a beat to show in the lamp's disc
    ripple(last_beat(t), FLOAT_C.x, FLOAT_C.y, 0.6, speed=6.0)
    if b >= 23.75:
        S.cracks["face"]["reveal"] = ease((b - 23.75) * 4)                     # the first crack, across her face
    a = 0.3 * ease(u)                                                           # sinking towards her, turning a little
    # half a metre towards the open water: the dark wall's foot leaves the right edge and the lamp's disc has room
    look(FLOAT_C + Vector((0, 0.5, 7.2 - 2.4 * ease(u))), FLOAT_C + Vector((0, 0.5, 0)), lens=35, fstop=8,
         up=(math.cos(a), math.sin(a), 0))


WHIP = [("print_1_-1.6", 1), ("print_2_+3.2", -1), ("print_3_+1.6", 1), ("print_4_-3.2", -1)]
CRACKS_P2 = ["win0", "print0", "win1", "print1"]                               # 3D and 2D in turn


def p2_whip(u, t, b):
    dawn()
    k, v = min(3, math.floor(b) - 24), b % 1
    p, side = S.prints[WHIP[k][0]], WHIP[k][1]
    bpy.context.scene.view_settings.exposure = 0.5                              # the held print was white: the sun
    wet(p, 0.06)                                                                # behind it, through the paper
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
    # higher and further out than before: the nearest print's dark back, lifting, filled half the frame
    look((2.5, -6.4, 2.4), (14, 1.2, 3.6), lens=24, fstop=5.6)


def p2_out(u, t, b):
    dawn(1 - (math.floor(b % 1 * 4) + 1) / 4)                                  # the light goes beat by beat
    for name in CRACKS_P2:
        S.cracks[name]["reveal"] = 1.0
    # low, towards the windows: as the lamps go the prints are silhouettes against the glass, the crack in it
    # (looking along the row they were black slabs with slivers of window)
    look((4.0, -5.0, 1.0), (12.0, 5.0, 6.0), lens=28, fstop=5.6)


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
        zoom = 1.05 if k < 4 else 1.7                                           # the second time round, close on her
        into(key, zoom + 0.05 * p, yaw=6 - 12 * p, cold=1.0, rose=0.9)        # (at 0.7 her face was lost in a tile)
        seep(key, 0.3 + 0.7 * p, S.burst)
        return
    names = list(S.prints)
    red = ease((b - 41) / 5)
    night(cold=1.0 - 0.4 * red, rose=lambda n: clamp((b - 41 - 0.22 * names.index(n)) / 0.5),
          density=0.003 + 0.002 * red, red=red)
    bpy.context.scene.view_settings.exposure = 1.5 - 0.3 * red                 # (at 1.8 in that haze the near prints
    #                                                                              went milky white)
    cam = k % 5
    if cam == 0:                                                                # low along a row, between the prints
        y = 5.5 - 11 * v
        look((8.1, y, 0.35), (14, y - 1.5, 2.2), lens=24, fstop=5.6)
    elif cam == 1:                                                              # Q1's print: the rose flowering on her
        light("q_cold", 0.6)                                                    # (the ink as a volume on the water
        light("q_rose", 0.3 + 0.5 * v)                                          # read as a black disc from above)
        seep("q1", 0.2 + 0.8 * ease(v), S.ink)
        look(QC + Vector((-3.4 + 0.6 * v, 1.1 - 0.5 * v, 0.3)), QC + Vector((0, 0, 0.35)), lens=40, fstop=4)
    elif cam == 2:                                                              # round a print to its back
        c = S.prints["print_3_-1.6"].location + Vector((0, 0, -2.1))
        ang = math.radians(-25 + 230 * ease(v))
        look(c + Vector((-math.cos(ang) * 3.2, math.sin(ang) * 3.2, -0.4)), c, lens=28, fstop=4)
    elif cam == 3:                                                              # through a print, quickly: a wide lens,
        x = 6.8 + 7.0 * v                                                       # the paper wet so the light comes through
        wet(S.prints["print_2_+0.0"], V.WET + 0.5)
        look((x, 0.15, 2.9), (x + 5, 0.15, 2.9), lens=20, fstop=5.6, focus=(max(10.0, x + 2.0), 0.15, 2.9))
    else:                                                                       # from the water, looking up at the prints
        look((4.0 + 1.5 * v, -0.8, 0.02), (12, 0.5, 6.5), lens=20, fstop=8)    # (from under the surface it was a
    #                                                                              jumble: prints through Snell's window
    #                                                                              over a mirror of the floor)
    tb = at(math.floor(b) + beat / 4)
    if beat == 0 and t - tb < 1.0 / FPS:
        S.lineart.default_value = 1.0                                           # D4: one frame as the negative on paper
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
    light("c1_rose", 0.6)                                                       # less rose through the paper: its
    light("c1_cold", 2.4)                                                       # relief mottled the pink glow
    v = ease(u)
    # from her face filling the frame back and aside, behind the last row: it was a print hanging in the hall.
    # The frame starts a little off her face towards the picture's middle: the bare margin beside her head, under
    # the same lamp as her dark picture, was a white bar down the side of the frame
    face = H.anchor(S.c1_print, "v4_c1_211", 1)["point"] + Vector((0, -0.22, 0))
    eye = (face + Vector((-1.35, 0, 0.1))).lerp(Vector((27.2, -4.5, 3.8)), v)
    look(eye, face.lerp(C1C, v), lens=40 - 12 * v, fstop=4)
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
    put(S.rain_em.inputs["Strength"], 2.5 if lines else 0.45)    # (6 made the lines white rods)


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
    light("w1_back", 0.0 if b < 65 else 1.0 * ease((b - 65) * 3))              # cold, raking the kraft
    ang = math.radians(90 * ease(b - 64) if b < 65 else 90 + 90 * ease((b - 65) * 1.5))   # a line, then its back
    v = ease((b - 65) * 1.2) if b >= 65 else 0.0                                # then in, to the pencilled number
    look(W1C + Vector((-math.cos(ang) * 4.0, -math.sin(ang) * 4.0, -1.0)), W1C + Vector((0, -0.6 * v, -1.9 * v)),
         lens=40 + 30 * v, fstop=4)
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
        light("refl_rose")                                                      # the print and all of its reflection
        S.float_print.hide_render = True              # (it lies on the water just beyond the print, in this view)
        look(REFL + Vector((4.4, 0.5, 1.1)), REFL + Vector((0, 0, 0.3)), lens=24, fstop=5.6)
    elif key:
        night(cold=0.0, rose=0.0, density=0.003)
        into(key, 1.05 + 0.08 * v, yaw=-6 + 12 * v, cold=0.6, rose=0.7)      # rose on her, the paper still cold
        if key == "u1":                                                         # her water takes the beat
            ripple_in("u1", last_beat(t), 0.8)
    else:                                                                       # the hall, upside down, drifting in
        p7_night()
        look((-1.0 + 6.0 * v, -2.4 + 0.8 * v, 0.35), (16 + 2.0 * v, 0.5, 1.2), lens=24, roll=180)


def p7_reflect(u, t, b):
    night(cold=0.1, rose=0.3)
    light("refl_cold")
    light("refl_rose", 0.6)
    S.float_print.hide_render = True
    flash = t - at(math.floor(b)) < 2 / FPS                                     # once a bar the reflection is 表 again
    S.refl_ura.visible_glossy, S.refl_flash.visible_glossy = not flash, flash
    # after U3's whole print over its whole reflection: from her face in the print, a slow tilt down the paper,
    # over the water line, into her other face lying reflected on the water in front of the print (both faces in
    # one frame leave the print a sixth of the width), and every beat a ring through that reflected face
    eye = REFL + Vector((3.8, 0.5, 0.9))                                        # on the print's +X side: the hall behind her
    w = ease((u - 0.12) / 0.7)
    face, mirror = REFL + Vector((0, 0, 1.65)), REFL + Vector((3.8 - 3.8 * 0.9 / (0.9 + 1.65), 0.5, 0.0))
    # the water stilled and barely a ring: a long lens close to a mirror sees a far virtual image, and a normal
    # tilted a few degrees moves that image by most of a metre, so any ripple here was liquid chrome
    put(S.water_bump, 0.0)
    ripple(last_beat(t), mirror.x, mirror.y, 0.015)
    look(eye, face.lerp(mirror, w), lens=55, fstop=5.6, focus=face.lerp(eye + (mirror - eye) * 2.5, w))


def p7_crack(u, t, b):
    p7_night()
    for k in range(4):
        S.cracks[f"win7_{k}"]["reveal"] = ease(1.5 * u - 0.15 * k)
    look((9.0, 3.0, 3.0), (11.0, 7.0, 8.4), lens=35, fstop=5.6)


SHARD_CUTS = [((10, 2, 7), (16, 6.5, 9.5)), ((14, 6, 9), (18, 1, 5)), ((20, 1.5, 5.5), (22, 7, 7.8)),
              ((24, 4, 8), (19, 6.5, 5.5)), ((12, 4, 5.5), (18, 6.5, 10)), ((17, 6.2, 7.5), (17, -2, 6)),
              ((26, 2, 9), (16, 6, 6))]           # never down the hall's length: far plaster lit flat is a grey slab
#                                                   (the fourth cut, aimed at (16, 2, 6) and then (16, -2.5, 5), had
#                                                   one in its top corner both times)


def p8_shards(u, t, b):
    night(cold=0.6, rose=0.4, density=0.003)
    for key in STAGE:                                 # the three 2D stage prints at x -7, seen from behind 30 m down
        S.prints[f"stage_{key}"].hide_render = True   # the hall, were one flat grey slab of paper in the cuts
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
    if q < 0.05:
        S.lineart.default_value = 1.0                                           # each cut lands on one frame of the negative


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
FAST_VIEWS = {"h_wide": ((-1.5, -5, 0.9), (20, 1, 3.2), (0, 0, 1)), "h_high": ((1, 0, 7.5), (20, 0, 1.5), (0, 0, 1)),
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
    else:                                                                       # (at cold 0.2 the view from above
        night(cold=0.5, rose=1.0, sky_key="s3", density=0.004, red=1.0)        # was black shapes)
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
    put(S.glare, 0.15)                                                          # light through cut paper, not neon
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

AN.run(FRAMES, SHOTS, CLK, setup, reset, after=lambda t: fx.sway(S.strands, t), first=FIRST, last=LAST,
       name="animatic v4")
