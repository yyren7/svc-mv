"""Smoke test for kit.py: one scene with every piece, frames 1-24 rendered to tmp/kit_test/.

    blender -b -P scripts/test_kit.py
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import mvlib as m  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "kit_test")

scene = m.reset(samples=8)
kit.install_hooks()
cam = m.perspective_camera()
m.look_at(cam, (0, 0, 20), (0, 0, 0))
m.sun((35, -30))
m.background("#0B0B10", z=-12)
scene.render.use_motion_blur = True

kt = kit.kinetic_text("裏表ラバーズ", "gothic", 1.6, -7, 2.5, "#F4F4F4", z=1)
kit.key_input(kt, "Progress", [(1, 0.0), (20, 6.0)], "LINEAR")
tc_obj, _ = kit.gn_object("timecode", kit.timecode_group("din", m.flat("#00E5FF"), 0.5, 75.0), {}, 1)
tc_obj.location = (-7, -4, 1)
heart = m.heart(-3, -0.5, 1.6, 0, lit="#FF4FA0", dark="#7A0F45", outline="#F4F4F4", outline_px=5, z=2)
heart.rotation_euler.y = 0
heart.keyframe_insert("rotation_euler", frame=1)
heart.rotation_euler.y = 3
heart.keyframe_insert("rotation_euler", frame=24)
gem = m.crystal(3.5, -0.5, 1.0, lit="#E1251B", dark="#5A0A07", outline="#EEEAE0", z=2)
kit.bursts((0, 0), ["#FF2E88", "#00E5FF", "#F4F4F4"], [2, 10], count=24, z=4)
kit.speedlines("#F4F4F4", z=3)
big = m.text("表", "mincho", 3, 5.5, 2.5, "#E1251B", z=1, align="CENTER", valign="CENTER")
big = kit.to_mesh(big)
kit.shatter(big, [(1, 0.0), (8, 0.0), (24, 1.0)])
ribbon = kit.cloth_ribbon(-7, -2.5, 6, 0.5, "#E1251B", z=0.5, frames=24)
kit.rigid_world(frames=24, start=4)
floor = kit.box(-8, 8, -4.8, -4.4, -2, 2, "#333333")
kit.rigid(floor, "PASSIVE")
for i, c in enumerate("ウラ"):
    ch = kit.to_mesh(m.text(c, "gothic", 1.2, 1 + i * 1.3, 1.0, "#EEEAE0", z=0.5), thickness=0.3)
    kit.rigid(ch)
comp = kit.compositor()
kit.key_socket(comp["tree"], kit.sock(comp["lens"].inputs, "Dispersion"), [(1, 0.0), (12, 0.08), (13, 0.0)])
kit.key_socket(comp["tree"], kit.sock(comp["inv"].inputs, "Factor"), [(1, 0.0), (16, 1.0), (17, 0.0)])
if comp["pix_size"] is not None:
    kit.key_socket(comp["tree"], comp["pix_size"], [(1, 1), (18, 24), (19, 1)])
m.scanlines(z=0)
kit_hud = m.CREATED[-1]
kit_hud.parent = cam
kit_hud.location = (0, 0, -0.5)
k = 0.5 * math.tan(math.radians(43.6 / 2)) / 8
kit_hud.scale = (k, k, k)

scene.frame_start, scene.frame_end = 1, 24
scene.render.fps = 24
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, "f_####")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "kit_test.blend"))
bpy.ops.render.render(animation=True)
