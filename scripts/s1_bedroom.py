"""S1「醒來の卧室」: a three-walled 1:12 set, 30 x 25 x 22 cm, the morning after. One low shaft of 6:59 light
through the window; the iron bed, the twin-bell clock, the lit phone and the half-drunk milk. Cycles stills.

    blender -b -P scripts/s1_bedroom.py -- [renders/s1] [clock wide pov]

The same builder makes S6 (the inverted bedroom) with palette="ura". Metres, Z up, the open side faces -Y.
"""
import colorsys
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

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


def repaint_green(mat, hexstr, value=7.0):
    """Turn the green enamel in a model's texture into another colour, keeping its wear; the chrome and the cream
    dial are not green and keep theirs. value lifts the dark green to the new paint's brightness."""
    nt = mat.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = b.inputs["Base Color"].links[0].from_socket
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(src, sep.inputs["Color"])
    green = T._math(nt, "MULTIPLY", T._math(nt, "SUBTRACT", sep.outputs["Green"],
                                            T._math(nt, "MAXIMUM", sep.outputs["Red"], sep.outputs["Blue"])), 8.0, clamp=True)
    h, s, v = colorsys.rgb_to_hsv(*m.srgb(hexstr)[:3])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Hue"].default_value = (0.5 + h - 0.43) % 1.0     # the enamel's green sits at hue 0.43
    hsv.inputs["Saturation"].default_value = 1.3
    hsv.inputs["Value"].default_value = value
    nt.links.new(src, hsv.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(green, mix.inputs["Factor"])
    nt.links.new(src, mix.inputs["A"])
    nt.links.new(hsv.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])


def bedside_clock(loc, yaw_deg=-28.0, time=(6, 59, 20), red="#E0301E"):
    """Poly Haven's twin-bell alarm clock (alarm_clock_01) at 1:12, its green tin repainted in the set's vermilion
    and its hands put to the time. Returns (top object, dial empty): the empty sits on the dial centre with its Z
    out of the face, and goes wherever the clock goes (S6 throws it)."""
    root = T.model("alarm_clock_01", name="clock", pick="alarm_clock_01")
    top = T.place(root, loc, yaw_deg=yaw_deg)
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    part = lambda key: next(o for o in meshes if o.name.startswith("alarm_clock_01_" + key))   # noqa: E731
    for mat in {ms.material for o in meshes for ms in o.material_slots if ms.material}:
        if not mat.name.startswith("alarm_clock_01_glass"):
            repaint_green(mat, red)
    n = (root.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()   # modelled facing -Y
    deps = bpy.context.evaluated_depsgraph_get()

    def posed(ob):
        """World vertices as rendered: the model's rig poses the hands through an armature modifier."""
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        pts = [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
        return pts
    glass = part("glass")
    gc = sum((glass.matrix_world @ Vector(c) for c in glass.bound_box), Vector()) / 8
    hand_pts = posed(part("minute_hand"))
    plane = sum(hand_pts, Vector()) / len(hand_pts)
    c = gc - n * (gc - plane).dot(n)                 # the hands' axis, where it meets their plane
    up = (Vector((0.0, 0.0, 1.0)) - n * n.z).normalized()
    right = (-n).cross(up)
    hh, mi, se = time
    turns = {"hour_hand": ((hh % 12) + mi / 60 + se / 3600) / 12, "minute_hand": (mi + se / 60) / 60, "second_hand": se / 60}
    for key, turn in turns.items():
        hand = part(key)
        tip = max((p - c - n * (p - c).dot(n) for p in posed(hand)), key=lambda q: q.length)
        now = math.atan2(tip.dot(right), tip.dot(up))
        spin = Matrix.Translation(c) @ Matrix.Rotation(-(2 * math.pi * turn - now), 4, n) @ Matrix.Translation(-c)
        hand.matrix_world = spin @ hand.matrix_world
    dial = bpy.data.objects.new("clock_dial", None)
    m._link(dial)
    dial.matrix_world = Matrix.Translation(c) @ Vector((0.0, 0.0, 1.0)).rotation_difference(n).to_matrix().to_4x4()
    dial.parent = top
    dial.matrix_parent_inverse = top.matrix_world.inverted()
    return top, dial


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
    stool = T.model("side_table_01", name="stool")      # a bedside table; S6 lifts it by this name
    T.place(stool, (0.105, 0.085, 0.0))
    stool_top = T.model_bounds(stool)[1].z
    clock, dial_ob = bedside_clock((0.105, 0.082, stool_top), yaw_deg=-28, time=(6, 59, 20), red=pal["clock"])
    dial = dial_ob.matrix_world.translation.copy()

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
    return dict(dial=dial, dial_ob=dial_ob, pillow=bed["pillow_top"], bed_front=bed["front_y"], desk_top=desk_top,
                walls=walls)


def main():
    info = build("omote")
    dial = info["dial"]
    n = (info["dial_ob"].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    eye_clock = dial + n * 0.10 + Vector((0, 0, 0.012))
    cams = {
        "clock": cyc.camera("cam_clock", tuple(eye_clock), tuple(dial), 100, 8.0),
        "wide": cyc.camera("cam_wide", (0.02, -0.47, 0.15), (0.0, 0.02, 0.09), 24, 8.0),
        "pov": cyc.camera("cam_pov", tuple(info["pillow"]), (-0.155, 0.01, 0.105), 50, 5.6),
    }
    focus = {"clock": dial, "wide": (0.0, 0.0, 0.05), "pov": (-0.19, 0.01, 0.105)}
    cyc.SKIP_FOCUS = cyc.SKIP_FOCUS + ("alarm_clock_01_glass", "window_glass", "curtain")
    objs = bpy.context.scene.objects
    haze, rim = [objs["haze"]], [objs["rim_pink"]]
    # the rim lamp glows as a blob in the haze of the wide shot (lamps ignore visible_volume_scatter), so it
    # only lights the close shots, which have no haze
    cyc.render_shots(cams, SHOTS, OUT, "s1", focus=focus, hide={"clock": haze, "pov": haze, "wide": rim},
                     exposure={"pov": -1.2})


if __name__ == "__main__":
    main()
