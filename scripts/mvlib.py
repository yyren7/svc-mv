"""Helpers for flat, print-like frames in Blender: an orthographic camera looking down -Z,
emission colours shown as-is (Standard view transform), toon-shaded 3D with inverted-hull outlines.

The frame is W x H scene units centred on the origin (1 unit = 120 px at 1920 x 1080).
Layers stack by z: the camera sits at z = 50, so larger z is nearer.
"""
import math
import os

import bpy

# Fonts: MV_FONT_DIR, else a fonts/ folder next to scripts/, else the Windows font folder.
# The faces are proprietary (Yu Mincho / Yu Gothic / DIN Next / Consolas), so fonts/ is not in git.
FONT_DIR = os.environ.get("MV_FONT_DIR") or next(
    (d for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts"),
                 r"C:\Windows\Fonts") if os.path.isdir(d)), r"C:\Windows\Fonts")
FONT_FILES = {
    "mincho": "yumindb.ttf",          # Yu Mincho Demibold
    "gothic": "YuGothB.ttc",          # Yu Gothic Bold
    "din": "DINNextLTPro-Bold.ttf",
    "din_medium": "DINNextLTPro-Medium.ttf",
    "din_light": "DINNextLTPro-Light.ttf",
    "mono": "consola.ttf",
}
W, H = 16.0, 9.0


def srgb(hexstr, alpha=1.0):
    """'#RRGGBB' -> linear RGBA, so the rendered pixel comes out as that hex value."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)


def reset(width=1920, height=1080, samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # keep Blender's temp files off drive C
    tmp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp")
    os.makedirs(tmp, exist_ok=True)
    bpy.context.preferences.filepaths.temporary_directory = tmp
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.eevee.taa_render_samples = samples
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    # Black world: no ambient light, so toon shading depends on the sun alone.
    # The visible background is a plane (see background()).
    world = bpy.data.worlds.new("world")
    world.color = (0, 0, 0)
    scene.world = world
    _MATS.clear()
    _FONTS.clear()
    _OUTLINES.clear()
    CREATED.clear()
    _camera(scene)
    return scene


def _camera(scene):
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = W
    cam.clip_start = 0.1
    cam.clip_end = 200
    obj = bpy.data.objects.new("cam", cam)
    obj.location = (0, 0, 50)
    scene.collection.objects.link(obj)
    scene.camera = obj


def sun(direction_deg=(40, -35), energy=3.0):
    """Sun tilted direction_deg = (around X, around Y) away from straight down the view axis."""
    light = bpy.data.lights.new("sun", "SUN")
    light.energy = energy
    obj = bpy.data.objects.new("sun", light)
    obj.rotation_euler = (math.radians(direction_deg[0]), math.radians(direction_deg[1]), 0)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- materials

_MATS = {}


def _new_mat(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return mat, nt, out


def flat(hexstr):
    key = ("flat", hexstr)
    if key not in _MATS:
        mat, nt, out = _new_mat(f"flat{hexstr}")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = srgb(hexstr)
        em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        _MATS[key] = mat
    return _MATS[key]


def toon(lit, dark, threshold=0.35):
    """Two-tone cel shading: diffuse light -> constant colour ramp."""
    key = ("toon", lit, dark, threshold)
    if key not in _MATS:
        mat, nt, out = _new_mat(f"toon{lit}{dark}")
        diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
        diff.inputs["Color"].default_value = (1, 1, 1, 1)
        s2r = nt.nodes.new("ShaderNodeShaderToRGB")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = srgb(dark)
        ramp.color_ramp.elements[1].position = threshold
        ramp.color_ramp.elements[1].color = srgb(lit)
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(diff.outputs[0], s2r.inputs[0])
        nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        _MATS[key] = mat
    return _MATS[key]


def outline_mat(hexstr):
    key = ("outline", hexstr)
    if key not in _MATS:
        mat = flat(hexstr).copy()
        mat.name = f"outline{hexstr}"
        mat.use_backface_culling = True
        # The hull encloses the object; without this it shadows the whole object from the sun.
        mat.use_backface_culling_shadow = True
        _MATS[key] = mat
    return _MATS[key]


def halftone_mat(hexstr, cell, axis, g0, g1, rmax=0.5):
    """Dot screen in object space: dots of colour hexstr on a transparent ground.
    The dot radius (in cells) goes from rmax at coordinate g0 to 0 at g1 along axis 'X' or 'Y'."""
    mat, nt, out = _new_mat(f"halftone{hexstr}")
    mat.use_backface_culling = False
    try:
        mat.surface_render_method = "BLENDED"
    except AttributeError:
        mat.blend_method = "BLEND"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    div = nt.nodes.new("ShaderNodeVectorMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = (cell, cell, 1.0)
    frac = nt.nodes.new("ShaderNodeVectorMath")
    frac.operation = "FRACTION"
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    length = nt.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.clamp = True
    rng.inputs[1].default_value = g0
    rng.inputs[2].default_value = g1
    rng.inputs[3].default_value = rmax
    rng.inputs[4].default_value = 0.0
    less = nt.nodes.new("ShaderNodeMath")
    less.operation = "LESS_THAN"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = srgb(hexstr)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    L = nt.links.new
    L(tc.outputs["Object"], div.inputs[0])
    L(div.outputs["Vector"], frac.inputs[0])
    L(frac.outputs["Vector"], sub.inputs[0])
    L(sub.outputs["Vector"], length.inputs[0])
    L(tc.outputs["Object"], sep.inputs[0])
    L(sep.outputs[axis], rng.inputs[0])
    L(length.outputs["Value"], less.inputs[0])
    L(rng.outputs[0], less.inputs[1])
    L(less.outputs[0], mix.inputs[0])
    L(tr.outputs[0], mix.inputs[1])
    L(em.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- shapes

CREATED = []   # every object made through this module, in order; animation scripts slice it per shot


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    CREATED.append(obj)
    return obj


def _mesh_obj(name, verts, faces, mat, loc=(0, 0, 0), rot_deg=0.0):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler.z = math.radians(rot_deg)
    obj.data.materials.append(mat)
    return _link(obj)


def rect(x0, y0, x1, y1, color, z=0.0, rot_deg=0.0, mat=None):
    """Axis-aligned rectangle (before rotation about its centre)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw, hh = abs(x1 - x0) / 2, abs(y1 - y0) / 2
    verts = [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)]
    return _mesh_obj("rect", verts, [(0, 1, 2, 3)], mat or flat(color), (cx, cy, z), rot_deg)


def background(color, z=-10, size=150):
    return rect(-size, -size, size, size, color, z=z)


def bar(x, y, length, thick, color, z=0.0, rot_deg=0.0):
    """Horizontal bar whose origin is its left end, so scale.x grows it from there."""
    verts = [(0, -thick / 2, 0), (length, -thick / 2, 0), (length, thick / 2, 0), (0, thick / 2, 0)]
    return _mesh_obj("bar", verts, [(0, 1, 2, 3)], flat(color), (x, y, z), rot_deg)


def dashed_ring(cx, cy, radius, width, color, dashes=48, duty=0.55, z=0.0):
    verts, faces = [], []
    seg = 2 * math.pi / dashes
    for d in range(dashes):
        a0, a1 = d * seg, d * seg + seg * duty
        base = len(verts)
        steps = 4
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            verts.append(((radius + width / 2) * math.cos(a), (radius + width / 2) * math.sin(a), 0))
            verts.append(((radius - width / 2) * math.cos(a), (radius - width / 2) * math.sin(a), 0))
        for s in range(steps):
            i = base + 2 * s
            faces.append((i, i + 2, i + 3, i + 1))
    return _mesh_obj("dashring", verts, faces, flat(color), (cx, cy, z))


def perspective_camera(fov_deg=43.6):
    cam = bpy.context.scene.camera
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(fov_deg)
    cam.rotation_mode = "QUATERNION"
    return cam


def look_at(cam, eye, target, roll_deg=0.0, fov_deg=None):
    from mathutils import Quaternion, Vector
    cam.location = eye
    q = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y")
    cam.rotation_quaternion = q @ Quaternion(Vector((0, 0, 1)), math.radians(roll_deg))
    if fov_deg is not None:
        cam.data.angle = math.radians(fov_deg)


def ring(cx, cy, r_out, r_in, color, z=0.0, segments=128):
    verts, faces = [], []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append((r_out * math.cos(a), r_out * math.sin(a), 0))
        verts.append((r_in * math.cos(a), r_in * math.sin(a), 0))
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    return _mesh_obj("ring", verts, faces, flat(color), (cx, cy, z))


def corner_marks(inset, length, thick, color, z=5.0, corners="all"):
    """L-shaped marks in the frame corners, like the corners of a viewfinder."""
    x, y = W / 2 - inset, H / 2 - inset
    picks = {"tl": (-1, 1), "tr": (1, 1), "bl": (-1, -1), "br": (1, -1)}
    names = picks if corners == "all" else corners
    for name in names:
        sx, sy = picks[name]
        rect(sx * x, sy * y, sx * (x - length), sy * (y - thick), color, z)
        rect(sx * x, sy * y, sx * (x - thick), sy * (y - length), color, z)


def crop_mark(cx, cy, size, thick, color, z=5.0):
    """Registration mark: a ring with a cross through it."""
    ring(cx, cy, size * 0.55, size * 0.55 - thick, color, z)
    rect(cx - size, cy - thick / 2, cx + size, cy + thick / 2, color, z)
    rect(cx - thick / 2, cy - size, cx + thick / 2, cy + size, color, z)


def barcode(x0, y0, x1, y1, color, seed=7, z=1.0):
    import random
    rnd = random.Random(seed)
    x = x0
    while x < x1:
        w = rnd.choice((0.02, 0.02, 0.04, 0.06, 0.08))
        if x + w > x1:
            break
        rect(x, y0, x + w, y1, color, z)
        x += w + rnd.choice((0.02, 0.03, 0.05))


def halftone(x0, y0, x1, y1, color, cell, axis, g0, g1, z=-5.0, rmax=0.5):
    """Rectangle of halftone dots; g0 / g1 are in the rectangle's own coordinates
    (its centre is 0)."""
    obj = rect(x0, y0, x1, y1, color, z, mat=halftone_mat(color, cell, axis, g0, g1, rmax))
    return obj


# ---------------------------------------------------------------- text

_FONTS = {}


def font(name):
    if name not in _FONTS:
        _FONTS[name] = bpy.data.fonts.load(os.path.join(FONT_DIR, FONT_FILES[name]))
    return _FONTS[name]


def text(body, face, size, x, y, color, z=1.0, align="LEFT", valign="BASELINE",
         spacing=1.0, line=1.0, rot_deg=0.0):
    cu = bpy.data.curves.new("text", "FONT")
    cu.body = body
    cu.font = font(face)
    cu.size = size
    cu.align_x = align
    cu.align_y = {"BASELINE": "BOTTOM_BASELINE", "TOP": "TOP", "CENTER": "CENTER",
                  "BOTTOM": "BOTTOM"}[valign]
    cu.space_character = spacing
    cu.space_line = line
    obj = bpy.data.objects.new("text", cu)
    obj.location = (x, y, z)
    obj.rotation_euler.z = math.radians(rot_deg)
    cu.materials.append(flat(color))
    return _link(obj)


def vtext(body, face, size, x, y, color, z=1.0, valign="TOP", line=0.9):
    """Vertical writing: one character per line, centred on x."""
    return text("\n".join(body), face, size, x, y, color, z, align="CENTER", valign=valign, line=line)


# ---------------------------------------------------------------- 3D

def _dist_to_outline(px, py, outline):
    best = float("inf")
    n = len(outline)
    for i in range(n):
        ax, ay = outline[i]
        bx, by = outline[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        ex, ey = ax + t * dx - px, ay + t * dy - py
        best = min(best, ex * ex + ey * ey)
    return math.sqrt(best)


def pillow_mesh(name, outline, centre, depth, rings=24):
    """Closed, puffy mesh from a 2D outline that is star-shaped around centre.
    Vertices sit on rings shrinking towards the centre; their height follows the distance d
    to the outline, depth * sqrt(1 - (1 - d / dmax)^2), so the rim is round and the middle flat."""
    import bmesh
    n = len(outline)
    cx, cy = centre
    layout = [[(cx + (k / rings) * (x - cx), cy + (k / rings) * (y - cy)) for x, y in outline]
              for k in range(1, rings)]
    dist = [[_dist_to_outline(x, y, outline) for x, y in ring_] for ring_ in layout]
    d_tip = _dist_to_outline(cx, cy, outline)
    dmax = max(max(max(r) for r in dist), d_tip)

    def height(d):
        u = min(1.0, d / dmax)
        return depth * math.sqrt(max(0.0, 1 - (1 - u) ** 2))

    bm = bmesh.new()
    sides = []
    for sign in (1, -1):
        grid = [[bm.verts.new((x, y, sign * height(d))) for (x, y), d in zip(ring_, dring)]
                for ring_, dring in zip(layout, dist)]
        grid.append([bm.verts.new((x, y, 0.0)) for x, y in outline])
        tip = bm.verts.new((cx, cy, sign * height(d_tip)))
        sides.append((tip, grid))
    # the outermost ring (z = 0) is shared by both faces
    rim = sides[0][1][-1]
    for i, v in enumerate(sides[1][1][-1]):
        bm.verts.remove(v)
        sides[1][1][-1][i] = rim[i]
    for tip, grid in sides:
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((tip, grid[0][i], grid[0][j]))
            for k in range(rings - 1):
                bm.faces.new((grid[k][i], grid[k + 1][i], grid[k + 1][j], grid[k][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    return mesh


def heart_outline(n=160):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 17.0, (y + 2.5) / 17.0))
    return pts


_OUTLINES = {}


def outlined(color, width_px=4.0):
    """Collection whose objects get Freestyle silhouette lines of this colour and width.
    Freestyle follows the real silhouette, so concave meshes (hair, folds) draw cleanly,
    where an inverted hull pokes through."""
    key = (color, width_px)
    if key not in _OUTLINES:
        scene = bpy.context.scene
        scene.render.use_freestyle = True
        scene.render.line_thickness_mode = "ABSOLUTE"
        scene.render.line_thickness = 1.0
        vl = scene.view_layers[0]
        vl.use_freestyle = True
        fs = vl.freestyle_settings
        fs.crease_angle = math.radians(120)
        coll = bpy.data.collections.new(f"outline{color}")
        scene.collection.children.link(coll)
        ls = fs.linesets.new(f"outline{color}")
        ls.select_by_visibility = True
        ls.select_by_edge_types = True
        ls.select_by_collection = True
        ls.collection = coll
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = False
        ls.select_contour = True
        style = ls.linestyle
        style.color = srgb(color)[:3]
        style.thickness = width_px
        style.thickness_position = "CENTER"
        style.caps = "ROUND"
        _OUTLINES[key] = coll
    return _OUTLINES[key]


def heart(cx, cy, scale, rot_deg, lit, dark, outline, outline_px=5.0, z=10.0, tilt=(15, -20)):
    """Puffy heart, toon shaded, with a Freestyle outline."""
    mesh = pillow_mesh("heart", heart_outline(), centre=(0.0, 0.0), depth=0.32)
    obj = bpy.data.objects.new("heart", mesh)
    obj.data.materials.append(HOOKS["toon"](lit, dark))
    obj.location = (cx, cy, z)
    obj.scale = (scale, scale, scale)
    obj.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), math.radians(rot_deg))
    _link(obj)
    HOOKS["outlined"](outline, outline_px).objects.link(obj)
    return obj


def crystal(cx, cy, scale, lit, dark, outline, outline_px=4.0, z=10.0, stretch=1.6):
    """Faceted gem: a flat-shaded icosphere stretched along its axis."""
    import bmesh
    bm = bmesh.new()
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    except TypeError:
        bmesh.ops.create_icosphere(bm, subdivisions=1, diameter=1.0)
    mesh = bpy.data.meshes.new("crystal")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("crystal", mesh)
    obj.data.materials.append(HOOKS["toon"](lit, dark, threshold=0.45))
    obj.location = (cx, cy, z)
    obj.scale = (scale, scale, scale * stretch)
    _link(obj)
    HOOKS["outlined"](outline, outline_px).objects.link(obj)
    return obj


def star(color, z=20.0, points=5, inner=0.42):
    """Flat star of radius 1 (scale the object to size it)."""
    verts = [(0, 0, 0)]
    for i in range(points * 2):
        a = math.pi / 2 + math.pi * i / points
        r = 1.0 if i % 2 == 0 else inner
        verts.append((r * math.cos(a), r * math.sin(a), 0))
    faces = [(0, 1 + i, 1 + (i + 1) % (points * 2)) for i in range(points * 2)]
    return _mesh_obj("star", verts, faces, flat(color), (0, 0, z))


def halo_mat(hexstr, strength=0.55):
    """Soft round glow, opaque-ish in the middle and fading to nothing at radius 1."""
    key = ("halo", hexstr, strength)
    if key not in _MATS:
        mat, nt, out = _new_mat(f"halo{hexstr}")
        try:
            mat.surface_render_method = "BLENDED"
        except AttributeError:
            mat.blend_method = "BLEND"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        length = nt.nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.clamp = True
        rng.inputs[1].default_value = 0.0
        rng.inputs[2].default_value = 1.0
        rng.inputs[3].default_value = 1.0
        rng.inputs[4].default_value = 0.0
        pw = nt.nodes.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = 2.2
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = strength
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = srgb(hexstr)
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        L = nt.links.new
        L(tc.outputs["Object"], length.inputs[0])
        L(length.outputs["Value"], rng.inputs[0])
        L(rng.outputs[0], pw.inputs[0])
        L(pw.outputs[0], mul.inputs[0])
        L(mul.outputs[0], mix.inputs[0])
        L(tr.outputs[0], mix.inputs[1])
        L(em.outputs[0], mix.inputs[2])
        L(mix.outputs[0], out.inputs["Surface"])
        _MATS[key] = mat
    return _MATS[key]


def disc(color, z=19.0, mat=None, segments=48):
    verts = [(0, 0, 0)] + [(math.cos(2 * math.pi * i / segments), math.sin(2 * math.pi * i / segments), 0)
                           for i in range(segments)]
    faces = [(0, 1 + i, 1 + (i + 1) % segments) for i in range(segments)]
    return _mesh_obj("disc", verts, faces, mat or flat(color), (0, 0, z))


def scanlines(z=40.0, period_px=4, opacity=0.22, height_px=1080):
    """Full-frame overlay of dark horizontal lines, period_px apart on screen."""
    mat, nt, out = _new_mat("scanlines")
    try:
        mat.surface_render_method = "BLENDED"
    except AttributeError:
        mat.blend_method = "BLEND"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = height_px / period_px
    frac = nt.nodes.new("ShaderNodeMath")
    frac.operation = "FRACT"
    less = nt.nodes.new("ShaderNodeMath")
    less.operation = "LESS_THAN"
    less.inputs[1].default_value = 1.0 / period_px
    amt = nt.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.inputs[1].default_value = opacity
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    L = nt.links.new
    L(tc.outputs["Window"], sep.inputs[0])
    L(sep.outputs["Y"], mul.inputs[0])
    L(mul.outputs[0], frac.inputs[0])
    L(frac.outputs[0], less.inputs[0])
    L(less.outputs[0], amt.inputs[0])
    L(amt.outputs[0], mix.inputs[0])
    L(tr.outputs[0], mix.inputs[1])
    L(em.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    return rect(-W, -H, W, H, "#000000", z=z, mat=mat)


def render(path):
    scene = bpy.context.scene
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)


# Swappable implementations for 3D pieces: kit.py replaces these with the halftone toon material
# and Grease Pencil Line Art collections.
HOOKS = {"toon": toon, "outlined": outlined}
