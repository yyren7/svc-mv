"""S1「醒來の卧室」: a three-walled 1:12 set, 30 x 25 x 22 cm, the morning after. One low shaft of 6:59 light
through the window; the iron bed, the twin-bell clock, the lit phone and the half-drunk milk. Cycles stills.

    blender -b -P scripts/s1_bedroom.py -- [renders/s1] [clock wide pov]

The same builder makes S6 (the inverted bedroom) with palette="ura". Metres, Z up, the open side faces -Y.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets as A  # noqa: E402
import cyc  # noqa: E402
import mvlib as m  # noqa: E402
import props as P  # noqa: E402
import texlib as T  # noqa: E402

OUT, SHOTS = cyc.args("s1", ["clock", "wide", "pov"])
W, D, H = 0.30, 0.25, 0.22

PALETTES = {
    "omote": dict(wall="#EEE8DA", floor="#B48A5C", paint="#F1EEE6", sheet="#E6E2D8", duvet="#DED6C6",
                  pillow="#EFEBE2", sky_ink="#6F86B8", sky_paper="#EEE8DA", reveal="#121116", clock="#E0301E",
                  wall_mix=0.62, floor_mix=0.35, sheet_tex="cotton_jersey", duvet_tex="rough_linen"),
    "ura": dict(wall="#121116", floor="#2A2630", paint="#15141A", sheet="#101014", duvet="#0E0D12",
                pillow="#141318", sky_ink="#F2468A", sky_paper="#121116", reveal="#EEE8DA", clock="#E0301E",
                wall_mix=0.8, floor_mix=0.75, sheet_tex="crepe_satin", duvet_tex="crepe_satin"),
}
BED = (-0.02, D / 2 - 0.0415 - 0.004, 0.0)   # the bed's centre on the floor, along X, head to the right
BED_BASE = 0.041                              # the wire mesh of old_bed_frame, probed at 1:12


def build(palette="omote", ceiling=False):
    pal = PALETTES[palette]
    m.reset()
    cyc.cycles()
    cyc.world()
    window = (-0.02, 0.07, 0.09, 0.105)          # y0, z0, wy, wz on the left wall
    wall_mat = T.pbr("decrepit_wallpaper", flat=(pal["wall"], pal["wall_mix"]), rough=0.85, scale=1 / 12, name="wallpaper")
    floor_mat = T.pbr("wood_floor_worn", flat=(pal["floor"], pal["floor_mix"]), scale=1 / 12, rotation_deg=90, name="floorboards",
                      coat=0.6)   # varnish: the window light lies on it as a long reflection
    walls = P.set_box(W, D, H, wall=wall_mat, floor=floor_mat, window=window, ceiling=ceiling)
    xl = -W / 2
    P.window(xl, *window, paint=P.painted(pal["paint"], name="window_paint"))
    y0, z0, wy, wz = window
    P.sky_card(xl - 0.01 - 0.03, y0 + wy / 2, z0 + wz / 2 + 0.01, wy + 0.07, wz + 0.07, pal["sky_ink"], pal["sky_paper"],
               emit=0.3 if palette == "omote" else 0.4)
    P.curtain(xl + 0.012, y0 + wy * 0.66, y0 + wy + 0.012, z0 + wz + 0.012, z0 - 0.02)

    # the bed along the back wall, head to the right; the clock on a stool by the head
    # cloth maps at 1/4 instead of 1/12: a true 1:12 weave is finer than a pixel, the script wants fibres at macro
    sheet = T.pbr(pal["sheet_tex"], flat=(pal["sheet"], 0.55), scale=1 / 4, rough=0.3 if palette == "ura" else None, name="sheet")
    duvet = T.pbr(pal["duvet_tex"], flat=(pal["duvet"], 0.5), scale=1 / 4, name="duvet")
    pillow = T.pbr(pal["sheet_tex"], flat=(pal["pillow"], 0.6), scale=1 / 4, name="pillow")
    frame = T.model("old_bed_frame", name="bed_frame")
    T.place(frame, BED, yaw_deg=90)
    if palette == "ura":
        for ob in frame.children_recursive:
            for ms in ob.material_slots:
                if ms.material and ms.material.node_tree:
                    b = next(n for n in ms.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
                    hs = ms.material.node_tree.nodes.new("ShaderNodeHueSaturation")
                    hs.inputs["Value"].default_value = 0.12
                    link = b.inputs["Base Color"].links[0] if b.inputs["Base Color"].links else None
                    if link:
                        ms.material.node_tree.links.new(link.from_socket, hs.inputs["Color"])
                        ms.material.node_tree.links.new(hs.outputs["Color"], b.inputs["Base Color"])
    bed = P.iron_bed(BED, length=0.160, width=0.070, head=+1, sheet=sheet, duvet=duvet, pillow_mat=pillow,
                     mattress_z=BED_BASE, frame=False)
    stool_top = 0.046
    stool = A.rounded_box("stool", (0.032, 0.032, stool_top), 0.001, [A.stained_wood("#8A6A48", (), ())])
    stool.location = (0.105, 0.072, stool_top / 2)
    clock, dial = P.alarm_clock((0.105, 0.072, stool_top), size=0.016, time=(6, 59, 20), red=pal["clock"], yaw_deg=-28)

    # the desk on the right, front: phone, milk, a stack of proofs
    desk = T.model("small_wooden_table_01", name="desk")
    T.place(desk, (0.100, -0.045, 0.0))
    desk_top = 0.0439
    chair = T.model("painted_wooden_chair_01", name="chair")
    T.place(chair, (0.122, 0.002, 0.0), yaw_deg=-100)
    lamp = T.model("desk_lamp_arm_01", name="desk_lamp", scale=1 / 34)   # the arm is modelled fully stretched out
    T.place(lamp, (0.128, -0.036, desk_top), yaw_deg=-150)
    lo, hi = T.model_bounds(lamp)
    print(f"desk lamp size mm {tuple(round(v * 1000) for v in (hi - lo))}")
    frame01 = T.model("standing_picture_frame_01", name="desk_frame")
    T.place(frame01, (0.070, -0.034, desk_top), yaw_deg=-15)
    P.phone((0.086, -0.056, desk_top), yaw_deg=18)
    P.milk_glass((0.110, -0.052, desk_top))
    P.print_stack((0.097, -0.036, desk_top), os.path.join(cyc.ROOT, "renders", "frame_A.png"))

    # the walls: polaroids of the heart from different angles, the peeled corner that shows the other paper
    yb = D / 2
    for i, (x, z, tilt, img) in enumerate([(-0.095, 0.16, 3, "s3_three.png"), (-0.065, 0.165, -5, "s3_macro.png"),
                                           (-0.035, 0.155, 2, "s3_wide.png"), (0.035, 0.175, -3, "s3_macro.png")]):
        P.polaroid((x, yb, z), os.path.join(cyc.ROOT, "renders", "s3", img), tilt_deg=tilt)
    P.wallpaper_peel((0.125, yb, 0.035), reveal=pal["reveal"], wall_hex=pal["wall"])
    poster = T.model("hanging_picture_frame_01", name="poster_frame")
    T.place(poster, (0.050, yb - 0.0015, 0.105), align="centre")
    clock_w = T.model("wall_clock", name="wall_clock")
    T.place(clock_w, (W / 2 - 0.0025, -0.03, 0.165), align="centre", yaw_deg=-90)
    nb = A.rounded_box("notebook", (0.026, 0.019, 0.0012), 0.0003, [P.paper("#F4F0E6", name="notebook")])
    nb.location = (-0.06, bed["front_y"] - 0.03, 0.0006)
    nb.rotation_euler.z = math.radians(12)

    # light: the window softbox, the backlit sky card, a paper bounce, the phone, a pink rim from behind
    if palette == "omote":
        cyc.area_light("window_key", (-0.36, 0.06, 0.28), (-0.02, -0.03, 0.0), 0.06, 4300, 7.0, spread_deg=30)
        cyc.area_light("paper_bounce", (0.26, -0.16, 0.14), (0.0, 0.08, 0.04), 0.15, 4800, 0.25, color="#F3E3C8")
        cyc.area_light("rim_pink", (0.0, 0.08, 0.21), (-0.02, 0.0, 0.04), 0.06, 6500, 0.03, color="#FF3D8B", spread_deg=35, volume=False)
        P.dust(((-0.14, -0.02), (-0.03, 0.07), (0.02, 0.16)), 300)
        cyc.haze("haze", (W, D, H), (0, 0, H / 2), 0.003)
    else:
        cyc.area_light("moon", (-0.36, -0.10, 0.30), (-0.08, 0.03, 0.06), 0.12, 9000, 2.0, spread_deg=90)
        cyc.haze("haze", (W, D, H), (0, 0, H / 2), 0.004, color="#F2468A")
    cyc.point_light("phone_glow", (0.082, -0.058, desk_top + 0.012), 6500, 0.02, radius=0.004)
    cyc.glass_lets_light_through()
    cyc.post(bloom=0.4 if palette == "omote" else 0.6, threshold=1.0 if palette == "omote" else 0.7)
    return dict(dial=dial, pillow=bed["pillow_top"], bed_front=bed["front_y"], desk_top=desk_top, walls=walls)


def main():
    info = build("omote")
    dial = info["dial"]
    n = Vector((-math.sin(math.radians(28)), -math.cos(math.radians(28)), 0.0))   # the dial's normal (yaw -28)
    eye_clock = dial + n * 0.15 + Vector((0, 0, 0.018))
    cams = {
        "clock": cyc.camera("cam_clock", tuple(eye_clock), tuple(dial), 100, 8.0),
        "wide": cyc.camera("cam_wide", (0.02, -0.47, 0.15), (0.0, 0.02, 0.09), 24, 8.0),
        "pov": cyc.camera("cam_pov", tuple(info["pillow"]), (-0.155, 0.01, 0.105), 50, 5.6),
    }
    focus = {"clock": dial, "wide": (0.0, 0.0, 0.05), "pov": (-0.19, 0.01, 0.105)}
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("clock_glass", "window_glass", "curtain")
    objs = bpy.context.scene.objects
    haze, rim = [objs["haze"]], [objs["rim_pink"]]
    # the rim lamp glows as a blob in the haze of the wide shot (lamps ignore visible_volume_scatter), so it
    # only lights the close shots, which have no haze
    cyc.render_shots(cams, SHOTS, OUT, "s1", focus=focus, hide={"clock": haze, "pov": haze, "wide": rim},
                     exposure={"pov": -1.2})


if __name__ == "__main__":
    main()
