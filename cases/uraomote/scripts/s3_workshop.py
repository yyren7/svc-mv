"""S3「表裏心臓の祭壇」: a corner of a risograph workshop at 1:12, split down the middle into day (表, left)
and night (裏, right), with the front/back heart on a brass stand at the seam. Cycles stills.

    blender -b -P cases/uraomote/scripts/s3_workshop.py -- [cases/uraomote/renders/s3] [shot ...]     shots: wide macro three

Real size in metres, Z up, the camera looks along +Y.
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
import mvlib as m  # noqa: E402
from cyc import area_light, camera, cycles  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.join(C.RENDERS, "s3")
SHOTS = argv[1:] or ["wide", "macro", "three"]
BENCH_TOP = 0.072
BASE_SAMPLES = int(os.environ.get('SAMPLES', 256))
SHOT_SAMPLES = {}
NO_HAZE = {"three"}


def build():
    m.reset()
    scene = bpy.context.scene
    cycles()
    scene.unit_settings.system = "METRIC"
    w = bpy.data.worlds.new("night")
    scene.world = w
    w.color = (0.002, 0.002, 0.004)
    rnd = random.Random(4)

    # room: floor planks and two walls; left half is the daytime room, right half the same room at night
    floor = A.rounded_box("floor", (0.8, 0.6, 0.01), 0.0005, [A.stained_wood("#3B2618", (("#1B1A19", 0.7),),
                                                                             (("#F2468A", 0.72),))])
    floor.location = (0, 0.1, -0.005)
    wall_mat = A.plaster("#E6E0D2")
    back = A.rounded_box("back_wall", (0.8, 0.02, 0.45), 0.001, [wall_mat])
    back.location = (0, 0.26, 0.22)
    side = A.rounded_box("side_wall", (0.02, 0.6, 0.45), 0.001, [wall_mat])
    side.location = (-0.36, 0.0, 0.22)

    # workbench with decades of ink: red / black on the day side, pink on the night side
    top = A.rounded_box("bench_top", (0.34, 0.16, 0.014), 0.0015, [A.stained_wood()])
    top.location = (0, 0.03, BENCH_TOP - 0.007)
    leg_mat = A.stained_wood("#4A2E1B", (), ())
    for sx in (-0.15, 0.15):
        for sy in (-0.035, 0.095):
            leg = A.rounded_box("leg", (0.016, 0.016, BENCH_TOP - 0.014), 0.001, [leg_mat])
            leg.location = (sx, sy, (BENCH_TOP - 0.014) / 2)

    # brass stand: a ring on three thin legs
    brass = A.brass()
    ring = A.lathe("stand_ring", [(0.0085, 0.0), (0.0095, 0.0005), (0.0085, 0.001), (0.0075, 0.0005), (0.0085, 0.0)],
                   48, [brass])
    ring.location = (0, 0.0, BENCH_TOP + 0.012)
    for k in range(3):
        a = 2 * math.pi * k / 3
        p0 = (0.012 * math.cos(a), 0.012 * math.sin(a), BENCH_TOP)
        p1 = (0.008 * math.cos(a), 0.008 * math.sin(a), BENCH_TOP + 0.0125)
        A.tube_along(f"stand_leg{k}", [p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, BENCH_TOP + 0.005), p1],
                     0.0006, [brass])

    heart = A.uraomote_heart(0.045)
    heart.location = (0, 0.0, BENCH_TOP + 0.012 + 0.021)
    heart.rotation_euler.z = math.radians(-6)

    # a few heart bulbs and paper offcuts on the bench and floor
    for i, (x, y, st) in enumerate([(-0.09, -0.02, "clean"), (0.075, 0.01, "infected"), (0.11, -0.03, "infected"),
                                    (-0.05, 0.06, "fever")]):
        b = A.heart_bulb(st, 0.007, seed=i)
        b.location = (x, y, BENCH_TOP + 0.0045)
        b.rotation_euler = (math.radians(rnd.uniform(60, 100)), 0, math.radians(rnd.uniform(0, 360)))

    # risograph machine behind the bench: cream body, drum, chrome handle
    body = A.rounded_box("riso_body", (0.13, 0.08, 0.07), 0.008, [A.plastic("#E8E0CC", name="riso_plastic")])
    body.location = (0.0, 0.17, BENCH_TOP + 0.035)
    drum = A.lathe("riso_drum", [(0.012, -0.05), (0.012, 0.05)], 48, [A.metal("#2B2B2E", 0.35, "drum")])
    drum.rotation_euler = (0, math.radians(90), 0)
    drum.location = (0.0, 0.128, BENCH_TOP + 0.06)
    A.tube_along("riso_handle", [(0.066, 0.15, BENCH_TOP + 0.05), (0.08, 0.15, BENCH_TOP + 0.055),
                                 (0.082, 0.15, BENCH_TOP + 0.075)], 0.0018, [A.chrome()])

    # drying lines with prints: day prints on the left, night prints on the right
    wire_mat = A.metal("#9A9A9A", 0.4, "wire")
    imgs = [os.path.join(C.RENDERS, "frame_A.png"), os.path.join(C.RENDERS, "frame_B.png")]
    for wy, wz in ((0.07, 0.215), (0.14, 0.235)):
        A.tube_along("wire", [(-0.34, wy, wz), (0.0, wy, wz - 0.006), (0.34, wy, wz)], 0.0004, [wire_mat])
        for i in range(9):
            x = -0.3 + i * 0.075 + rnd.uniform(-0.01, 0.01)
            img = imgs[0] if x < 0 else imgs[1]
            sheet = A.rounded_box("print", (0.054, 0.0004, 0.034), 0.0001, [A.printed(img)])
            sheet.location = (x, wy, wz - 0.019 - 0.006 * (1 - abs(x) / 0.34))
            sheet.rotation_euler = (math.radians(rnd.uniform(-6, 6)), 0, math.radians(rnd.uniform(-8, 8)))
            # map the print image across the front face
            uv = sheet.data.uv_layers.new()
            for loop in sheet.data.loops:
                co = sheet.data.vertices[loop.vertex_index].co
                uv.data[loop.index].uv = (co.x / 0.054 + 0.5, co.z / 0.034 + 0.5)
            clip = A.rounded_box("clip", (0.004, 0.003, 0.009), 0.0005, [A.plastic("#C9A97A", 0.6, "clip")])
            clip.location = (x, wy, wz - 0.004)

    # night side: a hand-bent neon 「裏」 on a black acrylic board, hung between the heart and the machine so it
    # sits near the focus plane of the wide shot instead of melting into bokeh on the back wall
    NEON = (0.115, 0.1, 0.138)
    board = A.rounded_box("neon_board", (0.085, 0.003, 0.085), 0.001, [A.plastic("#0B0B0D", 0.25, "acrylic")])
    board.location = (NEON[0], NEON[1] + 0.006, NEON[2])
    for dx in (-0.03, 0.03):
        A.tube_along("neon_hanger", [(NEON[0] + dx, NEON[1] + 0.006, NEON[2] + 0.042), (NEON[0] + dx, 0.14, 0.235)],
                     0.0003, [wire_mat])
    neon = m.text("裏", "mincho", 0.07, 0.2, 0.249, "#FF3D8B", z=0)
    neon.data.align_x, neon.data.align_y = "CENTER", "CENTER"
    neon.data.body = "裏"
    neon.data.fill_mode = "NONE"
    neon.data.bevel_depth = 0.0016
    neon.data.offset = -0.0
    neon.data.materials.clear()
    neon.data.materials.append(A.emissive("#FF3D8B", 3.0))
    neon.rotation_euler = (math.radians(90), 0, 0)
    neon.location = NEON

    # lights. Day: a large north-window softbox from the left. Night: neon + pink bounce + cyan from the heart.
    area_light("north_window", (-0.32, -0.08, 0.32), (-0.04, 0.05, BENCH_TOP), 0.35, 6000, 22.0)
    area_light("paper_bounce", (-0.1, -0.35, 0.1), (0.0, 0.0, BENCH_TOP + 0.02), 0.2, 4800, 1.2)
    area_light("neon_spill", (NEON[0], NEON[1] - 0.004, NEON[2]), (0.1, -0.05, BENCH_TOP), 0.09, 6500, 0.03, size_y=0.06).data.color = \
        tuple(c for c in m.srgb("#FF3D8B")[:3])
    rim = area_light("rim_pink", (NEON[0] + 0.01, NEON[1] - 0.004, NEON[2]), (0.0, 0.0, BENCH_TOP + 0.03), 0.03, 6500, 0.1)
    rim.data.color = tuple(c for c in m.srgb("#FF3D8B")[:3])

    # the day/night split: an invisible flag on x = 0 stops the window light from reaching the right half
    flag = A.rounded_box("split_flag", (0.002, 0.7, 0.6), 0.0, [A.plaster("#000000")])
    flag.location = (0.002, 0.05, 0.27)
    flag.visible_camera = False
    flag.visible_glossy = False
    flag.visible_transmission = False

    # haze: thin volume everywhere so the neon and the window light read as beams
    haze_mat = bpy.data.materials.new("haze")
    try:
        haze_mat.use_nodes = True
    except AttributeError:
        pass
    nt = haze_mat.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.06
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    haze = A.rounded_box("haze", (0.78, 0.6, 0.44), 0.0, [haze_mat])
    haze.location = (0, 0.06, 0.22)
    import cyc as _cyc
    _cyc.post(bloom=0.5, threshold=0.85)
    return heart, haze


def main():
    heart, haze = build()
    scene = bpy.context.scene
    hc = Vector((0, 0.0, BENCH_TOP + 0.033))
    seam = Vector((0.0, -0.011, hc.z + 0.002))   # the resin seam where it crosses the front face
    focus = bpy.data.objects.new("focus", None)
    m._link(focus)
    focus.location = (0.0, -0.012, hc.z + 0.004)
    cams = {
        "wide": camera("wide", (0.0, -0.36, BENCH_TOP + 0.07), (0.0, 0.08, BENCH_TOP + 0.05), 50, 5.6, focus),
        "macro": camera("macro", (0.03, -0.17, seam.z + 0.014), tuple(seam), 100, 8.0, focus),
        "three": camera("three", (-0.16, -0.2, BENCH_TOP + 0.11), (0.0, 0.02, BENCH_TOP + 0.03), 85, 2.0, focus),
    }
    from cyc import autofocus
    for cam in cams.values():
        autofocus(cam, seam)
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(OUT), "s3_workshop.blend"))
    for name in SHOTS:
        scene.camera = cams[name]
        scene.cycles.samples = SHOT_SAMPLES.get(name, BASE_SAMPLES)
        # the haze behind the three-quarter shot is all out of focus and only adds volume noise there
        haze.hide_render = name in NO_HAZE
        scene.render.filepath = os.path.join(os.path.abspath(OUT), f"s3_{name}.png")
        bpy.ops.render.render(write_still=True)
    _ = heart


if __name__ == "__main__":
    main()
