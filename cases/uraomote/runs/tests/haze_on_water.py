"""Is it the haze? The hall's haze box has its bottom face exactly on the water surface (z = 0). The bare scene of
moontest.py with the panel glossy-only, rendered with no haze, with a haze box whose bottom is at z = 0, and with
one whose bottom is half a metre under the water."""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "scripts"))
import assets as A  # noqa: E402
import cyc  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)

scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob)
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.use_persistent_data = True
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.view_settings.view_transform = "AgX"
scene.view_settings.exposure = 0.5
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)

bed = A.rounded_box("floor", (20, 14, 0.1), 0.0,
                    [A._principled("floor", **{"Base Color": (0.1, 0.1, 0.11, 1), "Roughness": 0.9})[0]])
bed.location = (0, 0, -0.08)
water, b = A._principled("water", **{"Base Color": (0.03, 0.03, 0.035, 1.0), "Roughness": 0.015, "IOR": 1.33,
                                     "Transmission Weight": 1.0})
A._bump(water, b, 0.35, 0.015, detail=2.0, distance=0.03)
A.rounded_box("water", (20, 14, 0.03), 0.0, [water]).location = (0, 0, -0.015)

bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0.03))
card = bpy.context.active_object
card.scale = (1.2, 2.1, 1.0)
card.data.materials.append(A._principled("card", **{"Base Color": (0.9, 0.9, 0.9, 1), "Roughness": 0.6})[0])

lt = bpy.data.lights.new("sun", "AREA")
lt.size, lt.energy = 3.0, 360.0
lo = bpy.data.objects.new("sun", lt)
scene.collection.objects.link(lo)
lo.location = (3.5, 0, 6.0)
lo.rotation_euler = Vector((-3.5, 0, -6)).to_track_quat("-Z", "Y").to_euler()
lo.visible_glossy = False

bpy.ops.mesh.primitive_plane_add(size=1.6, location=(3.5, 0, 6.0))
moon = bpy.context.active_object
em = bpy.data.materials.new("moon")
em.use_nodes = True
e = em.node_tree.nodes.new("ShaderNodeEmission")
e.inputs["Strength"].default_value = 10.0
em.node_tree.links.new(e.outputs[0], em.node_tree.nodes["Material Output"].inputs["Surface"])
moon.data.materials.append(em)
for attr in ("visible_camera", "visible_diffuse", "visible_transmission", "visible_volume_scatter", "visible_shadow"):
    setattr(moon, attr, False)

cam = bpy.data.cameras.new("cam")
cam.lens = 35.0
cam.dof.use_dof, cam.dof.aperture_fstop, cam.dof.focus_distance = True, 8.0, 7.2
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
co.location = (0, 0, 7.2)
co.rotation_euler = Vector((0, 0, -1)).to_track_quat("-Z", "Y").to_euler()
scene.camera = co


def shot(name):
    scene.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)


shot("a_no_haze")
haze = cyc.haze("haze", (24, 14, 12), (0, 0, 6.0), 0.0035, color="#E6D4DC", anisotropy=0.4)
shot("b_haze_on_water")                          # bottom face on the water surface, as in the hall
haze.location = (0, 0, 5.75)
shot("c_haze_lower")                             # bottom face half a metre under the water
haze.location = (0, 0, 6.25)
shot("d_haze_higher")                            # bottom face a quarter metre above the water
