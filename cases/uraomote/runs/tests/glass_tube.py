"""Why is the glass of water a black tube? A bare scene: the glass and water of sill_glass() in front of a bright
emissive slab, rendered three ways (glass + water, glass alone, water alone) with the shot's camera and bounces."""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "scripts"))
import assets as A  # noqa: E402

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
scene.cycles.max_bounces = scene.cycles.transmission_bounces = 14
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.view_settings.view_transform = "AgX"
scene.view_settings.exposure = -0.5
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.002, 0.002, 0.004, 1)

g = Vector((0.0, 0.0, 0.0))
glass = A.lathe("glass", [(0.0, 0.004), (0.026, 0.004), (0.029, 0.095), (0.031, 0.095), (0.0285, 0.0), (0.0, 0.0)],
                mats=[A.clear_glass()])
wm = A._principled("glass_water", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                     "IOR": 1.33})[0]
water = A.lathe("glass_water", [(0.0, 0.0045), (0.0257, 0.0045), (0.0272, 0.065), (0.0, 0.065)], mats=[wm])
glass.visible_shadow = water.visible_shadow = False

# a bright slab 0.3 m behind, like the window's pane and the sky, and a grey sill under the glass
bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0, 0.3, 0.5), rotation=(1.5708, 0, 0))
slab = bpy.context.active_object
em = bpy.data.materials.new("slab")
em.use_nodes = True
nt = em.node_tree
e = nt.nodes.new("ShaderNodeEmission")
e.inputs["Color"].default_value = (0.8, 0.88, 1.0, 1)
e.inputs["Strength"].default_value = 1.5
nt.links.new(e.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
slab.data.materials.append(em)
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, -0.0005))
sill = bpy.context.active_object
sill.data.materials.append(A._principled("sill", **{"Base Color": (0.5, 0.5, 0.5, 1), "Roughness": 0.8})[0])

cam = bpy.data.cameras.new("cam")
cam.lens, cam.sensor_width = 85.0, 36.0
cam.clip_start = 0.003
cam.dof.use_dof, cam.dof.aperture_fstop = True, 2.8
cam.dof.focus_distance = 0.5
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
co.location = g + Vector((0, -0.5, 0.05))
d = (g + Vector((0, 0, 0.045))) - co.location
co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
scene.camera = co

for name, show_glass, show_water in (("both", True, True), ("glass", True, False), ("water", False, True)):
    glass.hide_render, water.hide_render = not show_glass, not show_water
    scene.render.filepath = os.path.join(out, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)

# the same, with the normals checked: the topmost faces must face up, else the whole lathe is flipped
for ob in (glass, water):
    me = ob.data
    top = max(p.center.z for p in me.polygons)
    s = sum(p.normal.z for p in me.polygons if p.center.z > top - 1e-4)
    print(ob.name, "top normals sum", round(s, 3), flush=True)
    if s < 0:
        me.flip_normals()
glass.hide_render = water.hide_render = False
scene.render.filepath = os.path.join(out, "fixed.png")
bpy.ops.render.render(write_still=True)
print("rendered fixed", flush=True)

# a refraction counts as a glossy bounce too: four glass faces and two of water need more than the default 4
scene.cycles.glossy_bounces = 14
scene.render.filepath = os.path.join(out, "glossy14.png")
bpy.ops.render.render(write_still=True)
print("rendered glossy14", flush=True)
