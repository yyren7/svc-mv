"""v5 plates: the world rendered from each picture's camera, for her to be painted into it (docs/hybrid.md, 底板).
A picture painted over the real place has the world's own light, horizon, window and water, so a figure cut out
of it stands in the light it was painted in, and a picture the camera enters has its planes where the world's are.

    blender -b --factory-startup -P cases/uraomote/scripts/v5_plates.py -- [out_dir] [plate ...]
    -> <out>/<plate>_plate.png   the lit world, a grey mannequin where she stands (the picture's own size)
       <out>/<plate>_mask.png    flat colours, no mannequin: R the sky (beside the wall, through the window and
                                 the letters), G the water, black the wall and its frame
       <out>/<plate>_her.png     white where she may be painted: the mannequin, widened for hair, arms and skirt
    RES=30 SAMPLES=16 for a quick look.

PLATES is the one table of where she stands, the camera and the light of each picture; the jobs
(cases/uraomote/jobs/v5_t1.py) and the shots read it too.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402  (first: it puts the pipeline's scripts/ on the path)
import assets as A  # noqa: E402
import cyc  # noqa: E402
import hybrid_fx as fx  # noqa: E402
import mvlib as m  # noqa: E402
import v5_world as W  # noqa: E402
from v5_world import ROSE, S, WALL_T, WIN_Y, WIN_Z0, WIN_Z1  # noqa: E402

SAMPLES = int(os.environ.get("SAMPLES", 96))
WIDE, TALL = (1664, 928), (928, 1664)                    # Qwen's working sizes
SUN_DAWN = Vector((-16.0, 1.0, -2.8)).normalized()       # the dawn still's sun: low behind the wall, a little to the viewer's right

# name: the picture's size, its light, where she is (x, y, how), the camera (eye, target, lens, f-stop).
# The viewer's side is -X; the window's centre is y WIN_Y (the viewer's right), the letters are at y 2.5 (left).
PLATES = {
    # cut-out figures (TALL, she fills the height): the KV at the window, 表 standing at dusk, W1 in the rain,
    # R0 running at the camera, F1 leaping between two skies
    "kv": dict(size=TALL, light="dawn", her=(-1.6, -1.2, "stand"), eye=(-6.6, -2.6, 1.15), target=(-1.6, -1.2, 0.85),
               lens=90, fstop=4.0),
    "q1s": dict(size=TALL, light="dusk", her=(-3.0, 0.0, "stand"), eye=(-8.2, 0.0, 0.95), target=(-3.0, 0.0, 0.82),
                lens=90, fstop=4.0),
    "w1": dict(size=TALL, light="rain", her=(-6.0, 0.6, "stand"), eye=(-11.2, 0.6, 1.0), target=(-6.0, 0.6, 0.85),
               lens=90, fstop=4.0),
    "r0": dict(size=TALL, light="night", her=(-12.0, 0.0, "run"), eye=(-16.6, 0.0, 0.55), target=(-12.0, 0.0, 0.85),
               lens=75, fstop=4.0),
    "f1": dict(size=WIDE, light="twin", her=(-5.0, 10.0, "leap"), eye=(-11.5, 10.0, 1.6), target=(-5.0, 10.0, 2.5),
               lens=50, fstop=4.0),
    # pictures the camera enters (WIDE): at the window at dawn, lying on the night water
    "a1": dict(size=WIDE, light="dawn", her=(-0.55, -1.6, "stand"), eye=(-5.0, -3.3, 1.5), target=(-0.3, -1.2, 1.9),
               lens=40, fstop=4.0),
    "a2": dict(size=WIDE, light="dawn", her=(-2.6, -0.4, "stand"), eye=(-2.9, 3.4, 1.35), target=(-2.6, -0.9, 1.15),
               lens=50, fstop=2.8),
    "a3": dict(size=WIDE, light="dawn", her=(-0.7, -1.2, "stand"), eye=(-3.6, 1.4, 1.45), target=(-0.7, -1.3, 1.45),
               lens=55, fstop=2.8),
    "a4": dict(size=WIDE, light="dawn", her=(-0.6, -1.5, "stand"), eye=(-1.9, -2.7, 1.55), target=(-0.25, -1.45, 1.55),
               lens=60, fstop=2.8),
    "a5": dict(size=WIDE, light="dawn", her=(-0.5, -1.2, "stand"), eye=(-2.6, -0.9, 1.6), target=(-0.5, -1.2, 1.55),
               lens=85, fstop=2.8),
    "u1": dict(size=WIDE, light="night", her=(-6.0, 1.0, "lie"), eye=(-4.7, 1.0, 2.6), target=(-4.7, 1.0, 0.0),
               lens=40, fstop=4.0),
}
WIDEN = {"stand": (1.45, 1.45, 1.04), "run": (1.75, 1.75, 1.06), "leap": (1.9, 1.9, 1.15), "lie": (1.6, 1.6, 1.1)}


# ---------------------------------------------------------------- her place and the light

def mannequin(x, y, how):
    """A grey figure of her size where she will be: legs, torso and head on an empty at her feet, so the plate
    shows the light falling on a body there. Upright, leaning into a run, in mid-air, or lying on the water
    (along +X, her head to +X). Returns (the empty, her middle)."""
    grey = A._principled("mannequin", **{"Base Color": (0.42, 0.42, 0.44, 1.0), "Roughness": 0.8})[0]
    root = bpy.data.objects.new("mann_root", None)
    m._link(root)
    root.location = (x, y, 0.012)
    for name, add in (("mann_legs", lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.78, location=(0, 0, 0.39))),
                      ("mann_torso", lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.165, depth=0.66, location=(0, 0, 1.11))),
                      ("mann_head", lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.105, location=(0, 0, 1.52)))):
        add()
        ob = bpy.context.active_object
        ob.name = name
        ob.data.materials.append(grey)
        for poly in ob.data.polygons:
            poly.use_smooth = True
        ob.parent = root
    middle = Vector((x, y, 0.95))
    if how == "run":
        root.rotation_euler.y = math.radians(-14)                 # the top towards -X: into the camera
    elif how == "leap":
        root.location.z = 1.7                                     # her feet 1.7 m over the water
        root.rotation_euler.y = math.radians(-8)
        middle = Vector((x, y, 2.5))
    elif how == "lie":
        root.rotation_euler.y = math.radians(90)                  # along +X, her head to +X
        root.location.z = 0.17
        middle = Vector((x + 0.8, y, 0.17))
    return root, middle


def light_dawn(c):
    """The dawn still's light: the sun low behind the wall, through the letters and the window; a cold fill."""
    W.set_sky("s1", 1.8)
    W.sun(SUN_DAWN, 5.0, 6200, disc=40.0)
    cyc.put(S.haze_vol.inputs["Density"], 0.003)
    fill = cyc.area_light("fill", (c.x - 4.4, c.y - 3.7, 3.0), (c.x, c.y, c.z), 4.0, 9000, 70, color="#9FB2D8")
    fill.visible_glossy = False
    return -0.2


def light_dusk(c):
    """P3: the sky gone dark, a cold lamp before her, a rose edge from behind (the waterline still's light)."""
    W.set_sky("s2", 0.35)
    cyc.put(S.haze_vol.inputs["Density"], 0.002)
    cyc.put(S.haze_vol.inputs["Color"], m.srgb("#C4BCD0"))
    cyc.put(S.sea_bump, 0.0)
    cold = cyc.area_light("cold", (c.x - 3.5, c.y - 2.0, 2.6), (c.x, c.y, c.z), 2.0, 9000, 160, color="#7C94FF")
    cold.visible_glossy = False
    rose = cyc.area_light("rose", (c.x + 1.6, c.y + 1.5, 2.2), (c.x, c.y, c.z - 0.1), 2.0, 2000, 120, color=ROSE)
    rose.visible_glossy = False
    return 0.4


def light_rain(c):
    """P6: a rainy night, the window's rose glow the only light before her, a faint cold key (the rain still's
    light). The rain itself is 3D in the film, so the plate has none."""
    W.set_sky("s2", 0.5)
    cyc.put(S.haze_vol.inputs["Density"], 0.008)
    cyc.put(S.haze_vol.inputs["Color"], m.srgb("#C8D0E0"))
    cyc.put(S.rain, 1.0)
    cyc.put(S.rain_t, 0.37)
    cyc.put(S.sea_bump, 0.12)
    glow = cyc.area_light("window_glow", (WALL_T + 0.9, WIN_Y, (WIN_Z0 + WIN_Z1) / 2), (c.x, WIN_Y, 1.5), 2.0, 2000,
                          520, size_y=3.4, color=ROSE)
    glow.visible_glossy = False
    key = cyc.area_light("key", (c.x - 3.5, c.y - 3.1, 2.4), (c.x, c.y, c.z), 1.5, 9000, 110, color="#7C94FF")
    key.visible_glossy = False
    return 0.6


def light_night(c):
    """P7-P9: the world turned 裏: the letters glow rose from behind the wall, rose from low behind her, a faint
    cold light from above."""
    W.set_sky("s2", 0.35)
    cyc.put(S.haze_vol.inputs["Density"], 0.003)
    cyc.put(S.haze_vol.inputs["Color"], m.srgb("#C4BCD0"))
    glow = cyc.area_light("letters_glow", (WALL_T + 1.0, 2.5, 3.6), (-12.0, 2.5, 1.0), 1.2, 2000, 400, size_y=2.6,
                          color=ROSE)
    glow.visible_glossy = False
    rose = cyc.area_light("rose", (c.x + 1.2, c.y - 1.6, c.z - 0.6), (c.x, c.y, c.z), 2.0, 2000, 140, color=ROSE)
    rose.visible_glossy = False
    cold = cyc.area_light("cold", (c.x - 3.0, c.y + 1.5, c.z + 2.2), (c.x, c.y, c.z + 0.2), 2.0, 9000, 90, color="#7C94FF")
    cold.visible_glossy = False
    return 0.5


def light_twin(c):
    """P10: two suns, a cold one from the viewer's left and a rose one from the right."""
    W.set_sky("s3", 1.6)
    cyc.put(S.haze_vol.inputs["Density"], 0.002)
    cold = W.sun(Vector((0.3, -1.0, -0.6)), 3.0, 9000, name="sun_cold")
    cold.data.color = m.srgb("#7C94FF")[:3]
    rose = W.sun(Vector((0.3, 1.0, -0.4)), 3.0, 2000, name="sun_rose")
    rose.data.color = m.srgb(ROSE)[:3]
    return 0.0


LIGHTS = {"dawn": light_dawn, "dusk": light_dusk, "rain": light_rain, "night": light_night, "twin": light_twin}


# ---------------------------------------------------------------- the flat renders

def _mats(ob, mat):
    if ob.material_slots:
        for slot in ob.material_slots:
            slot.material = mat
    else:
        ob.data.materials.append(mat)


def paint(mode):
    """Every surface a flat emission colour, no lights, no glass, no haze. "planes": R the sky, G the water, the
    wall and its frame black, the mannequin hidden; "her": the mannequin white, all else black. The letters stay
    open in the wall (its mask in the flat material too)."""
    black = fx.emission_mat("flat_black", "#000000", 1.0)[0]
    white = fx.emission_mat("flat_white", "#FFFFFF", 1.0)[0]
    planes = {"sky": fx.emission_mat("flat_sky", "#FF0000", 1.0)[0], "sea": fx.emission_mat("flat_sea", "#00FF00", 1.0)[0]}
    planes["seabed"] = planes["sea"]
    for ob in list(bpy.context.scene.objects):
        if ob.type == "LIGHT":
            ob.hide_render = True
        elif ob.type == "MESH":
            n = ob.name
            if n in ("pane", "haze") or n.startswith("glass") or n.endswith("_disc"):
                ob.hide_render = True
            elif n.startswith("mann_"):
                ob.hide_render = mode != "her"
                _mats(ob, white)
            elif n == "wall":
                _mats(ob, black)
                W.letters(ob, black)
            elif n in planes:
                _mats(ob, planes[n] if mode == "planes" else black)
            else:
                _mats(ob, black)


def render(cam, samples, denoise, exposure, path, look=True):
    scene = bpy.context.scene
    scene.camera = cam
    scene.cycles.samples = samples
    scene.cycles.use_denoising = denoise
    scene.view_settings.exposure = exposure
    if not look:
        scene.view_settings.view_transform = "Standard"
        try:
            scene.view_settings.look = "None"
        except TypeError:
            pass
        cam.data.dof.use_dof = False
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("wrote", path, flush=True)


def plate(name, out):
    p = PLATES[name]
    W.build()
    root, middle = mannequin(*p["her"])
    exposure = LIGHTS[p["light"]](middle)
    cam = cyc.camera(name, p["eye"], p["target"], p["lens"], p["fstop"])
    cam.data.clip_end = 10000.0
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = p["size"]
    scene.camera = cam
    cyc.autofocus(cam, middle)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{name}.blend"))
    render(cam, SAMPLES, True, exposure, os.path.join(out, f"{name}_plate.png"))
    paint("planes")
    render(cam, 16, False, 0.0, os.path.join(out, f"{name}_mask.png"), look=False)
    paint("her")
    root.scale = WIDEN[p["her"][2]]
    render(cam, 16, False, 0.0, os.path.join(out, f"{name}_her.png"), look=False)


def main():
    out, names = cyc.args(os.path.join(C.RENDERS, "v5_plates"), list(PLATES))
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    for name in names:
        plate(name, out)


if __name__ == "__main__":
    main()
