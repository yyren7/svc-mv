"""Hero props for the 3D miniature scenes, modeled procedurally (Blender only, no generated assets).

Miniature scenes are built at real size in metres with Z up (a 1:12 dollhouse world: the heart is
4.5 cm wide), so camera depth of field is physically right and the miniature look comes for free.
Materials target Cycles.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

import mvlib as m


# ---------------------------------------------------------------- colour

def kelvin(k):
    """Approximate blackbody colour (linear RGB) for a colour temperature in kelvin."""
    t = k / 100.0
    if t <= 66:
        r = 255
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
        b = 255
    srgb = [min(max(c, 0), 255) / 255 for c in (r, g, b)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


# ---------------------------------------------------------------- materials

def _principled(name, **inputs):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for k, v in inputs.items():
        bsdf.inputs[k].default_value = v
    return mat, bsdf


def _bump(mat, bsdf, scale, strength, detail=4.0, distance=0.0005):
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = distance
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return nz


def porcelain():
    """Unglazed white bisque: slightly translucent, matte, fine pores."""
    mat, b = _principled("porcelain", **{"Base Color": m.srgb("#F1EEE6"), "Roughness": 0.52,
                                         "Subsurface Weight": 0.25, "Subsurface Scale": 0.002})
    _bump(mat, b, 900.0, 0.25)
    return mat


def glaze(hexstr="#C9261B"):
    """Glossy red glaze lines with a clear coat."""
    mat, _ = _principled("glaze", **{"Base Color": m.srgb(hexstr), "Roughness": 0.06, "Coat Weight": 1.0,
                                     "Coat Roughness": 0.02})
    return mat


def smoked_glass(tint="#3A3440", density=40.0):
    """Blown smoky glass: clear surface with uneven waves, the colour comes from volume absorption."""
    mat, b = _principled("smoked_glass", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0,
                                            "Roughness": 0.015, "IOR": 1.52})
    _bump(mat, b, 60.0, 0.12, detail=2.0, distance=0.002)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = m.srgb(tint)
    vol.inputs["Density"].default_value = density
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat


def clear_glass(roughness=0.01):
    mat, b = _principled("clear_glass", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0,
                                           "Roughness": roughness, "IOR": 1.5})
    _bump(mat, b, 80.0, 0.05, detail=2.0, distance=0.001)
    return mat


def emissive(hexstr, strength):
    mat, b = _principled(f"emit{hexstr}", **{"Base Color": m.srgb(hexstr), "Emission Color": m.srgb(hexstr),
                                             "Emission Strength": strength, "Roughness": 0.2, "Coat Weight": 0.6})
    return mat


def metal(hexstr, roughness=0.3, name="metal"):
    mat, b = _principled(name, **{"Base Color": m.srgb(hexstr), "Metallic": 1.0, "Roughness": roughness})
    _bump(mat, b, 300.0, 0.15)
    return mat


def brass():
    return metal("#B88A3E", 0.28, "brass")


def chrome():
    return metal("#D7D9DE", 0.08, "chrome")


def plastic(hexstr, roughness=0.42, name="plastic"):
    mat, b = _principled(name, **{"Base Color": m.srgb(hexstr), "Roughness": roughness, "Coat Weight": 0.2})
    _bump(mat, b, 500.0, 0.08)
    return mat


def plaster(hexstr):
    mat, b = _principled("plaster", **{"Base Color": m.srgb(hexstr), "Roughness": 0.9})
    _bump(mat, b, 120.0, 0.4, detail=8.0, distance=0.001)
    return mat


def stained_wood(base="#5B3A22", stains=(("#E0301E", 0.62), ("#1B1A19", 0.66)), right_stains=(("#F2468A", 0.6),),
                 split_x=0.0):
    """Old worktop: wood grain (wave texture) with ink stains; stains on x > split_x use right_stains."""
    mat, b = _principled("bench_wood", **{"Roughness": 0.55})
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 220.0
    wave.inputs["Distortion"].default_value = 14.0
    wave.inputs["Detail"].default_value = 6.0
    wave.inputs["Detail Roughness"].default_value = 0.7
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = m.srgb(base)
    ramp.color_ramp.elements[1].color = m.srgb("#74492C")
    ramp.color_ramp.elements[0].position = 0.25
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    right = nt.nodes.new("ShaderNodeMath")
    right.operation = "GREATER_THAN"
    right.inputs[1].default_value = split_x
    nt.links.new(sep.outputs["X"], right.inputs[0])
    for i, (hexstr, thr) in enumerate(list(stains) + list(right_stains)):
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 18.0 + 7 * i
        nz.inputs["Detail"].default_value = 6.0
        next(sk for sk in nz.inputs if sk.name == "W").default_value = i * 3.3
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        cut = nt.nodes.new("ShaderNodeMath")
        cut.operation = "GREATER_THAN"
        cut.inputs[1].default_value = thr
        nt.links.new(nz.outputs["Fac"], cut.inputs[0])
        side = nt.nodes.new("ShaderNodeMath")
        side.operation = "MULTIPLY"
        nt.links.new(cut.outputs[0], side.inputs[0])
        if i < len(stains):
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = "SUBTRACT"
            inv.inputs[0].default_value = 1.0
            nt.links.new(right.outputs[0], inv.inputs[1])
            nt.links.new(inv.outputs[0], side.inputs[1])
        else:
            nt.links.new(right.outputs[0], side.inputs[1])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(side.outputs[0], mix.inputs["Factor"])
        nt.links.new(col, mix.inputs["A"])
        mix.inputs["B"].default_value = m.srgb(hexstr)
        col = mix.outputs["Result"]
    nt.links.new(col, b.inputs["Base Color"])
    _bump(mat, b, 40.0, 0.3, detail=6.0)
    return mat


def printed(image_path, rough=0.85):
    """Paper print: an image texture on matte paper with a fibre bump."""
    mat, b = _principled("print", **{"Roughness": rough})
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image_path, check_existing=True)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    _bump(mat, b, 700.0, 0.2)
    return mat


# ---------------------------------------------------------------- mesh helpers

def _obj(name, mesh, mats, parent=None):
    obj = bpy.data.objects.new(name, mesh)
    for mt in mats:
        obj.data.materials.append(mt)
    m._link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def lathe(name, profile, segments=64, mats=(), parent=None):
    """Revolve a (radius, z) profile around Z."""
    bm = bmesh.new()
    rings = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in profile])
    for i in range(segments):
        j = (i + 1) % segments
        for k in range(len(profile) - 1):
            bm.faces.new((rings[i][k], rings[j][k], rings[j][k + 1], rings[i][k + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    return _obj(name, mesh, mats, parent)


def tube_along(name, points, radius, mats=(), parent=None, resolution=6):
    """A curve through points with a round bevel (vessels, wires, cables)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, co in zip(sp.points, points):
        p.co = (*co, 1)
    sp.use_endpoint_u = True
    sp.order_u = min(4, len(points))
    obj = bpy.data.objects.new(name, cu)
    for mt in mats:
        cu.materials.append(mt)
    m._link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def rounded_box(name, size, bevel, mats=(), parent=None, segments=4):
    sx, sy, sz = (s / 2 for s in size)
    v = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(v, [], faces)
    obj = _obj(name, mesh, mats, parent)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = segments
    mod.limit_method = "NONE"
    for p in mesh.polygons:
        p.use_smooth = True
    obj.modifiers.new("wn", "WEIGHTED_NORMAL")
    return obj


def _half(mesh_src, keep_positive_x, gap):
    bm = bmesh.new()
    bm.from_mesh(mesh_src)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=(1, 0, 0),
                                 clear_inner=keep_positive_x, clear_outer=not keep_positive_x)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(gap if keep_positive_x else -gap, 0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out = bpy.data.meshes.new("half")
    bm.to_mesh(out)
    bm.free()
    for p in out.polygons:
        p.use_smooth = True
    return out


# ---------------------------------------------------------------- the 表裏 heart

def uraomote_heart(width=0.045, seed=3):
    """The front/back heart: left half unglazed porcelain with red glaze vessels, right half smoked glass
    with trapped cyan motes, a pink resin seam between them (kintsugi), three cut vessels on top.
    Built in the XY plane facing +Z, then stood up to face -Y. Returns the root empty."""
    rnd = random.Random(seed)
    s = width / 2.0
    root = bpy.data.objects.new("uraomote_heart", None)
    m._link(root)

    # anatomical asymmetry: a fuller left ventricle (viewer's left), the apex leaning to the right
    outline = [(x * (1.07 if x < 0 else 0.95) + 0.12 * max(0.0, -y - 0.25), y) for x, y in m.heart_outline(200)]
    base = m.pillow_mesh("heart_src", outline, centre=(0.0, 0.0), depth=0.42, rings=36)
    base.transform(__import__("mathutils").Matrix.Scale(s, 4))
    gap = 0.0006
    left = _obj("heart_porcelain", _half(base, False, gap), [porcelain()], root)
    right = _obj("heart_glass", _half(base, True, gap), [smoked_glass()], root)
    for o in (left, right):
        sub = o.modifiers.new("sub", "SUBSURF")
        sub.levels, sub.render_levels = 1, 2

    # resin seam: the cross-section at x = 0, a little proud of the surface, glowing pink
    bm = bmesh.new()
    bm.from_mesh(base)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0),
                                 plane_no=(1, 0, 0))
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    keep = set(cut)
    for e in list(bm.edges):
        if e not in keep:
            bm.edges.remove(e)
    for v in list(bm.verts):
        if not v.link_edges:
            bm.verts.remove(v)
    seam_mesh = bpy.data.meshes.new("seam")
    bm.to_mesh(seam_mesh)
    bm.free()
    seam = _obj("heart_seam", seam_mesh, [emissive("#FF3D8B", 70.0)], root)
    sk = seam.modifiers.new("skin", "SKIN")
    for v in seam.data.skin_vertices[0].data:
        r = s * rnd.uniform(0.055, 0.085)
        v.radius = (r, r)
    seam.modifiers.new("sub", "SUBSURF").render_levels = 2
    _ = sk

    # glaze vessels on the porcelain face (front, +Z) and back: meander down from the top cleft
    # One BVH per half from the base mesh, reused for every ray. Object.ray_cast rebuilds a BVH on each
    # call, and BVHTree.FromObject on the subdivided object took ~26 s apiece in Blender 5.2.
    from mathutils.bvhtree import BVHTree

    def bvh(mesh):
        return BVHTree.FromPolygons([v.co for v in mesh.vertices], [p.vertices[:] for p in mesh.polygons])
    bvh_left, bvh_right = bvh(left.data), bvh(right.data)

    def project(x, y, front=True):
        z0 = 2 * s if front else -2 * s
        d = Vector((0, 0, -1 if front else 1))
        loc, nrm, _i, _d = bvh_left.ray_cast(Vector((x, y, z0)), d, 4 * s)
        return (loc + nrm * s * 0.004) if loc is not None else None

    glaze_mat = glaze()
    for front in (True, False):
        for k in range(3):
            x, y = -s * rnd.uniform(0.08, 0.2), s * rnd.uniform(0.2, 0.45)
            pts = []
            ang = math.radians(rnd.uniform(-130, -100))
            for step in range(14):
                p = project(x, y, front)
                if p is None:
                    break
                pts.append(tuple(p))
                ang += math.radians(rnd.uniform(-22, 22))
                x += math.cos(ang) * s * 0.09
                y += math.sin(ang) * s * 0.09
                if x > -s * 0.03:
                    x = -s * 0.03
            if len(pts) > 3:
                tube_along(f"vessel{k}", pts, s * rnd.uniform(0.012, 0.02), [glaze_mat], root)

    # three cut vessels on top: open tubes with wall thickness, ends cut flat
    specs = [(-0.32, 0.62, 0.11, -18, porcelain()), (-0.12, 0.48, 0.085, -4, porcelain()),
             (0.3, 0.6, 0.095, 15, smoked_glass())]
    for i, (fx, fy, r, tilt, mat) in enumerate(specs):
        prof = [(r * s, -0.05 * s), (r * s, 0.38 * s)]
        tube = lathe(f"artery{i}", prof, 40, [mat], root)
        sol = tube.modifiers.new("wall", "SOLIDIFY")
        sol.thickness = r * s * 0.28
        tube.location = (fx * s, fy * s, 0)
        tube.rotation_euler = (math.radians(-90), 0, math.radians(tilt))
        inner = lathe(f"artery{i}_in", [(r * s * 0.7, 0.3 * s), (r * s * 0.7, 0.37 * s)], 32,
                      [glaze("#7A1410")], root)
        inner.location = tube.location
        inner.rotation_euler = tube.rotation_euler

    # trapped cyan motes inside the glass half
    motes = bmesh.new()
    count = 0
    while count < 160:
        x, y = rnd.uniform(0.05, 0.9) * s, rnd.uniform(-0.8, 0.8) * s
        loc, _n, _i, _d = bvh_right.ray_cast(Vector((x, y, 2 * s)), Vector((0, 0, -1)), 4 * s)
        if loc is None:
            continue
        top = loc.z
        if top < 0.12 * s:
            continue
        z = rnd.uniform(-0.75, 0.75) * top
        r = s * rnd.uniform(0.006, 0.016)
        bmesh.ops.create_icosphere(motes, subdivisions=1, radius=r,
                                   matrix=__import__("mathutils").Matrix.Translation((x, y, z)))
        count += 1
    mm = bpy.data.meshes.new("motes")
    motes.to_mesh(mm)
    motes.free()
    _obj("heart_motes", mm, [emissive("#34E3E8", 40.0)], root)

    root.rotation_euler = (math.radians(90), 0, 0)   # stand up, front faces -Y
    bpy.data.meshes.remove(base)
    return root


def heart_bulb(state="clean", size=0.006, seed=0):
    """Fingernail-sized heart light bulb: glass shell, heart-shaped filament, brass screw base.
    state: 'clean' (clear glass, warm filament), 'fever' (fogged, flickers) or 'infected' (pink glass, cyan)."""
    s = size / 2
    root = bpy.data.objects.new("heart_bulb", None)
    m._link(root)
    shell_mesh = m.pillow_mesh("bulb", m.heart_outline(64), centre=(0.0, 0.0), depth=0.5, rings=10)
    shell_mesh.transform(__import__("mathutils").Matrix.Scale(s, 4))
    if state == "infected":
        glass = smoked_glass("#FF3D8B", density=600.0)
    elif state == "fever":
        glass = clear_glass(roughness=0.25)
    else:
        glass = clear_glass()
    shell = _obj("bulb_glass", shell_mesh, [glass], root)
    sol = shell.modifiers.new("wall", "SOLIDIFY")
    sol.thickness = s * 0.06
    pts = [(0.55 * x * s, 0.55 * y * s, 0.0) for x, y in m.heart_outline(24)]
    pts.append(pts[0])
    fil_col, fil_k = ("#34E3E8", 30.0) if state == "infected" else ("#FFB46B", 18.0)
    tube_along("filament", pts, s * 0.02, [emissive(fil_col, fil_k)], root, resolution=2)
    # brass screw base under the heart's tip: lathe along +Z, turned so +Z points down (-Y)
    base = lathe("bulb_base", [(0.22 * s, 0.8 * s), (0.26 * s, 0.95 * s), (0.22 * s, 1.1 * s),
                               (0.26 * s, 1.25 * s), (0.22 * s, 1.4 * s), (0.12 * s, 1.5 * s)], 24, [brass()], root)
    base.rotation_euler = (math.radians(90), 0, 0)
    root.rotation_euler = (math.radians(90), 0, 0)
    return root
