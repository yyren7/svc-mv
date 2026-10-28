"""Shared Cycles setup for the miniature scenes: GPU device, lights with kelvin colours, cameras with
physical depth of field, autofocus by ray cast, haze volumes, and the still-render loop.

Scenes are built at real size in metres, Z up, so f-stops and focal lengths behave like a real macro lens
on a 1:12 set. Every scene script does: cyc.args() -> build -> cyc.camera()s -> cyc.render_shots().
"""
import os
import sys

import bpy
from mathutils import Vector

import assets as A
import mvlib as m

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_SAMPLES = int(os.environ.get("SAMPLES", 256))


def put(sock, v):
    """Set a socket's value only when it changes: setting it again, even to the same value, makes Cycles rebuild
    the material or light, and forty hybrid prints make that most of a frame's time."""
    cur = sock.default_value
    if isinstance(v, (int, float)):
        if cur != v:
            sock.default_value = v
    elif tuple(cur) != tuple(v):
        sock.default_value = v


def energy(ob, e):
    """A light's energy, written only on change (as put())."""
    if ob.data.energy != e:
        ob.data.energy = e


def args(default_out, default_shots):
    """`blender -b -P scene.py -- [out_dir] [shot ...]` -> (out_dir, shots). default_out is a path: each case
    keeps its renders in its own folder."""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else default_out
    return out, (argv[1:] or list(default_shots))


def cycles(samples=BASE_SAMPLES, caustics=True, bounces=10, volume_bounces=1, look="AgX - Medium High Contrast"):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                break
        except TypeError:
            continue
    # CYCLES_DEVICE=CPU: render on the processors while the GPU is busy (ComfyUI holds most of its memory)
    scene.cycles.device = "CPU" if os.environ.get("CYCLES_DEVICE") == "CPU" else "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    # keep the GPU fed: denoise on the GPU, and reuse scene data between renders instead of rebuilding
    try:
        scene.cycles.denoising_use_gpu = True
    except AttributeError:
        pass
    scene.render.use_persistent_data = True
    scene.cycles.max_bounces = bounces
    scene.cycles.transmission_bounces = bounces
    scene.cycles.volume_bounces = volume_bounces
    scene.cycles.caustics_refractive = caustics
    scene.cycles.caustics_reflective = caustics
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = look
    except TypeError:
        pass
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = int(os.environ.get("RES", 100))   # RES=40 for quick looks
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.unit_settings.system = "METRIC"
    return scene


def world(color=(0.002, 0.002, 0.004), name="world"):
    """Near-black world: the scene is lit by the lamps that are in the picture."""
    w = bpy.data.worlds.new(name)
    bpy.context.scene.world = w
    w.color = color
    return w


def _aim(ob, loc, target):
    ob.location = loc
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")


def area_light(name, loc, target, size, kelvin_k, power, shape="RECTANGLE", size_y=None, color=None,
               spread_deg=180.0, seen=False, volume=True):
    """Rectangle or disk softbox. color (hex) overrides the kelvin colour; spread narrows it like a grid.
    seen=False hides the lamp from camera and transmission rays (it would show as a white slab through
    any window or jar) while it still lights the scene and appears in reflections."""
    lt = bpy.data.lights.new(name, "AREA")
    lt.shape = shape
    lt.size = size
    if size_y:
        lt.size_y = size_y
    lt.color = m.srgb(color)[:3] if color else A.kelvin(kelvin_k)
    lt.energy = power
    try:
        lt.spread = __import__("math").radians(spread_deg)
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, lt)
    m._link(ob)
    _aim(ob, loc, target)
    if not seen:
        ob.visible_camera = False
        ob.visible_transmission = False
    if not volume:
        ob.visible_volume_scatter = False   # no glowing blob in the haze around a rim light
    return ob


def point_light(name, loc, kelvin_k, power, radius=0.002, color=None):
    """Tiny bulb-like source (a filament, a phone LED)."""
    lt = bpy.data.lights.new(name, "POINT")
    lt.color = m.srgb(color)[:3] if color else A.kelvin(kelvin_k)
    lt.energy = power
    lt.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, lt)
    m._link(ob)
    ob.location = loc
    ob.visible_camera = False
    ob.visible_transmission = False
    return ob


def haze(name, size, loc, density, color=None, anisotropy=0.3):
    """Thin volume box so beams and glows read. Keep density at 0.002-0.01: it is the main render cost."""
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = anisotropy
    if color:
        vol.inputs["Color"].default_value = m.srgb(color)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    box = A.rounded_box(name, size, 0.0, [mat])
    box.location = loc
    box.visible_shadow = False
    return box


def camera(name, eye, target, lens, fstop, focus_obj=None, focus_dist=None, roll_deg=0.0, sensor=36.0,
           blades=9):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = sensor
    cam.clip_start = 0.003
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    cam.dof.aperture_blades = blades
    if focus_dist is not None:
        cam.dof.focus_distance = focus_dist
    if focus_obj is not None:
        cam.dof.focus_object = focus_obj
    ob = bpy.data.objects.new(name, cam)
    m._link(ob)
    _aim(ob, eye, target)
    if roll_deg:
        ob.rotation_mode = "XYZ"
        ob.rotation_euler.rotate_axis("Z", __import__("math").radians(roll_deg))
    return ob


SKIP_FOCUS = ("haze", "split_flag", "rain", "dust")


def glass_lets_light_through(names=("clear_glass",)):
    """Refractive glass blocks shadow rays, so a lamp outside a jar or a window never lights what is inside.
    Turn off shadow casting for every object made of the named glass materials; the light passes unbent,
    which is what a photographer's eye expects of thin glass. Call after the scene is built."""
    n = 0
    for ob in bpy.context.scene.objects:
        if ob.type in ("MESH", "CURVE") and any(ms.material and ms.material.name.startswith(names) for ms in ob.material_slots):
            ob.visible_shadow = False
            n += 1
    print(f"shadowless glass objects: {n}")
    return n


def autofocus(cam, target, skip=None, verbose=True):
    """Focus on the first surface along the ray from the camera to target, ignoring volumes and flags."""
    skip = tuple(SKIP_FOCUS) if skip is None else tuple(skip)   # read at call time: scenes extend SKIP_FOCUS
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    cam.data.dof.focus_object = None
    origin = cam.matrix_world.translation.copy()
    target = Vector(target)
    d = (target - origin).normalized()
    p, dist = origin.copy(), None
    for _ in range(24):
        hit, loc, _n, _i, ob, _mx = scene.ray_cast(deps, p, d)
        if not hit:
            break
        if ob.name.startswith(skip):
            p = loc + d * 1e-4
            continue
        dist = (loc - origin).length
        break
    cam.data.dof.focus_distance = dist if dist else (target - origin).length
    if verbose:
        print(f"focus {cam.name}: {cam.data.dof.focus_distance * 1000:.1f} mm")
    return cam.data.dof.focus_distance


def render_shots(cams, shots, out, prefix, focus=None, samples=None, hide=None, blend=None, exposure=None):
    """cams: {shot: camera}; focus: {shot: point} for autofocus; samples: {shot: n}; hide: {shot: [objects]}.
    Saves the .blend next to the stills so a shot can be reopened by hand."""
    scene = bpy.context.scene
    os.makedirs(out, exist_ok=True)
    for name, cam in cams.items():
        if focus and name in focus:
            autofocus(cam, focus[name])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out), blend or f"{prefix}.blend"))
    hidden = set()
    for name in shots:
        for ob in hidden:
            ob.hide_render = False
        hidden = set((hide or {}).get(name, ()))
        for ob in hidden:
            ob.hide_render = True
        scene.camera = cams[name]
        scene.cycles.samples = (samples or {}).get(name, BASE_SAMPLES)
        scene.view_settings.exposure = (exposure or {}).get(name, 0.0)   # a shot into a window exposes down
        scene.render.filepath = os.path.join(os.path.abspath(out), f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
    for ob in hidden:
        ob.hide_render = False


def post(bloom=0.5, threshold=0.9, size=0.6, dispersion=0.004):
    """A camera's finish on the render: bloom around bright lights and a hint of colour dispersion."""
    import kit
    scene = bpy.context.scene
    tree = bpy.data.node_groups.new("post", "CompositorNodeTree")
    scene.compositing_node_group = tree
    kit._iface(tree, "Image", "OUTPUT", "NodeSocketColor")
    g = kit.G(tree)
    rl = g.node("CompositorNodeRLayers")
    glare = g.node("CompositorNodeGlare")
    for name, val in (("Type", "Bloom"), ("Threshold", threshold), ("Strength", bloom), ("Size", size)):
        try:
            kit.sock(glare.inputs, name).default_value = val
        except (KeyError, TypeError, ValueError) as e:
            print("glare", name, e)
    g.link(rl.outputs["Image"], kit.sock(glare.inputs, "Image"))
    lens = g.node("CompositorNodeLensdist")
    g.link(glare.outputs[0], kit.sock(lens.inputs, "Image"))
    kit.sock(lens.inputs, "Dispersion").default_value = dispersion
    out = g.node("NodeGroupOutput")
    g.link(lens.outputs[0], out.inputs[0])
    scene.render.use_compositing = True
    return tree
