"""Poly Haven assets in the sets: PBR surfaces box-mapped in object space (the procedural meshes have no UVs),
HDRI worlds, and models appended from their .blend files and scaled to 1:12.

    import texlib as T
    mat = T.pbr("concrete_floor_01", scale=1/12)            # a 1 m texture tile becomes 8.3 cm
    T.hdri_world("belfast_sunset_puresky", strength=1.0, rotation_deg=120)
    bench = T.model("painted_wooden_bench", location=(0, 0, 0), scale=1/12)

Files come from scripts/fetch_assets.py (assets/polyhaven/). Real-world tile sizes come from the catalogue
JSON the fetcher caches in tmp/, else 1 m is assumed.
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

import mvlib as m

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PH = os.path.join(ROOT, "assets", "polyhaven")
_CATALOGUE = {}


def _catalogue(kind):
    if kind not in _CATALOGUE:
        p = os.path.join(ROOT, "tmp", f"ph_{kind}.json")
        try:
            _CATALOGUE[kind] = json.load(open(p, encoding="utf-8"))
        except Exception:   # noqa: BLE001
            _CATALOGUE[kind] = {}
    return _CATALOGUE[kind]


def texture_size_m(aid):
    """Real-world size (x, y) in metres of a texture tile, from the catalogue's dimensions in mm."""
    d = _catalogue("textures").get(aid, {}).get("dimensions")
    if d and len(d) >= 2 and d[0] and d[1]:
        return d[0] / 1000.0, d[1] / 1000.0
    return 1.0, 1.0


def _find(aid, key, res=None):
    folder = os.path.join(PH, "textures", aid)
    if not os.path.isdir(folder):
        return None
    cands = sorted(f for f in os.listdir(folder) if f"_{key}_" in f and (res is None or f"_{res}." in f))
    return os.path.join(folder, cands[-1]) if cands else None


def _image(path, non_color):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def pbr(aid, scale=1.0 / 12, rough=None, tint=None, bump=1.0, displace=0.0, coat=0.0, name=None, res=None,
        rotation_deg=0.0, blend=0.25, metallic=None, emission=None, ao=0.7, flat=None):
    """Principled material from a Poly Haven texture set, box-projected in object space.
    scale multiplies the real-world tile size (1/12 for the miniature sets). bump scales the normal map;
    displace > 0 adds true displacement (needs adaptive subdivision or a dense mesh) in metres."""
    mat = bpy.data.materials.new(name or f"ph_{aid}")
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    sx, sy = texture_size_m(aid)
    mp.inputs["Scale"].default_value = (1.0 / (sx * scale), 1.0 / (sy * scale), 1.0 / (sx * scale))
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation_deg))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    def tex(key, non_color):
        path = _find(aid, key, res)
        if path is None:
            return None
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = _image(path, non_color)
        node.projection = "BOX"
        node.projection_blend = blend
        nt.links.new(mp.outputs[0], node.inputs["Vector"])
        return node

    diff = tex("diffuse", False) or tex("diff", False)
    col = diff.outputs["Color"] if diff else None
    aon = tex("ao", True)
    if col is not None and aon is not None and ao > 0:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = ao
        nt.links.new(col, mix.inputs["A"])
        nt.links.new(aon.outputs["Color"], mix.inputs["B"])
        col = mix.outputs["Result"]
    if col is not None and flat is not None:
        # flat = (hex, factor): a painted colour with only `1 - factor` of the map's grime showing through
        fx = nt.nodes.new("ShaderNodeMix")
        fx.data_type = "RGBA"
        fx.inputs["Factor"].default_value = flat[1]
        nt.links.new(col, fx.inputs["A"])
        fx.inputs["B"].default_value = m.srgb(flat[0])
        col = fx.outputs["Result"]
    if col is not None and tint is not None:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(col, mix.inputs["A"])
        mix.inputs["B"].default_value = m.srgb(tint) if isinstance(tint, str) else tint
        col = mix.outputs["Result"]
    if col is not None:
        nt.links.new(col, bsdf.inputs["Base Color"])
        if emission:
            nt.links.new(col, bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = emission
    rg = tex("rough", True)
    if rg is not None:
        if rough is None:
            nt.links.new(rg.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            # scale the map so its mid value lands on `rough`
            mr = nt.nodes.new("ShaderNodeMath")
            mr.operation = "MULTIPLY"
            mr.inputs[1].default_value = rough / 0.5
            nt.links.new(rg.outputs["Color"], mr.inputs[0])
            nt.links.new(mr.outputs[0], bsdf.inputs["Roughness"])
    elif rough is not None:
        bsdf.inputs["Roughness"].default_value = rough
    mt = tex("metal", True)
    if mt is not None:
        nt.links.new(mt.outputs["Color"], bsdf.inputs["Metallic"])
    elif metallic is not None:
        bsdf.inputs["Metallic"].default_value = metallic
    # relief from the height map as a Bump: the nor_gl maps are tangent space, which box projection can't
    # use (read as object space they tilt every wall's normal towards +Z and the walls go dark)
    hm = tex("displacement", True)
    if hm is not None and bump > 0:
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = min(1.0, 0.6 * bump)
        bp.inputs["Distance"].default_value = 0.0004 * scale * 12
        nt.links.new(hm.outputs["Color"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    if displace > 0:
        dp = tex("displacement", True)
        if dp is not None:
            dn = nt.nodes.new("ShaderNodeDisplacement")
            dn.inputs["Scale"].default_value = displace
            dn.inputs["Midlevel"].default_value = 0.5
            nt.links.new(dp.outputs["Color"], dn.inputs["Height"])
            nt.links.new(dn.outputs["Displacement"], out.inputs["Displacement"])
            mat.displacement_method = "BOTH"
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def hdri_world(aid, strength=1.0, rotation_deg=0.0, res=None, tint=None, name=None):
    """Light the scene with a Poly Haven HDRI; returns the world. The camera still sees the sky."""
    folder = os.path.join(PH, "hdris")
    cands = sorted(f for f in os.listdir(folder) if f.startswith(aid + "_") and (res is None or f"_{res}." in f))
    if not cands:
        raise FileNotFoundError(f"no HDRI {aid} in {folder}; run scripts/fetch_assets.py")
    w = bpy.data.worlds.new(name or f"hdri_{aid}")
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(os.path.join(folder, cands[-1]), check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation_deg))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    if tint:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(env.outputs["Color"], mix.inputs["A"])
        mix.inputs["B"].default_value = m.srgb(tint)
        nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    else:
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = w
    return w


def model(aid, location=(0, 0, 0), rotation_deg=(0, 0, 0), scale=1.0 / 12, name=None, pick=None):
    """Append every mesh object of a Poly Haven model .blend under one empty, scaled to the miniature.
    pick: substring(s) of object names to keep (modular packs hold several pieces)."""
    path = os.path.join(PH, "models", aid, f"{aid}.blend")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no model {aid}; run scripts/fetch_assets.py")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    root = bpy.data.objects.new(name or aid, None)
    m._link(root)
    root.location = location
    root.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    root.scale = (scale, scale, scale)
    kept = []
    picks = (pick,) if isinstance(pick, str) else pick
    objs = [ob for ob in dst.objects if ob is not None]
    names = {o.name for o in objs}
    wanted = [ob for ob in objs if ob.type in ("MESH", "CURVE")
              and (not picks or any(p.lower() in ob.name.lower() for p in picks))]
    # keep the empties that the wanted meshes hang from (rigged props such as the desk lamp), drop the rest
    needed = set()
    for ob in wanted:
        p = ob.parent
        while p is not None and p.name in names:
            needed.add(p.name)
            p = p.parent
    for ob in objs:
        if ob in wanted or ob.name in needed:
            m._link(ob)
            if ob.parent is None or ob.parent.name not in names:
                ob.parent = root
            if ob in wanted:
                kept.append(ob)
    for ob in objs:
        if ob not in wanted and ob.name not in needed:
            bpy.data.objects.remove(ob)
    for ob in kept:
        for ms in ob.material_slots:
            if ms.material is None:
                continue
            for n in ms.material.node_tree.nodes if ms.material.node_tree else []:
                if n.type == "TEX_IMAGE" and n.image is not None and n.image.filepath:
                    # the zip puts textures beside the .blend; point relative paths there
                    rel = n.image.filepath.replace("\\", "/").lstrip("/")
                    if rel.startswith("//"):
                        rel = rel[2:]
                    cand = os.path.join(os.path.dirname(path), rel)
                    if os.path.exists(cand):
                        n.image.filepath = cand
                        n.image.reload()
    return root


def model_bounds(root):
    """World-space bounding box (min, max) of a model root's children."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    bpy.context.view_layer.update()
    for ob in root.children_recursive:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def hdri_sun(aid, rotation_deg=0.0, res=None):
    """Direction (unit vector, pointing from the scene towards the sun) of the brightest spot of an HDRI,
    after the same Z rotation hdri_world() applies, so a Sun lamp can sharpen its shadows."""
    folder = os.path.join(PH, "hdris")
    cands = sorted(f for f in os.listdir(folder) if f.startswith(aid + "_") and (res is None or f"_{res}." in f))
    img = bpy.data.images.load(os.path.join(folder, cands[-1]), check_existing=True)
    w, h = img.size
    px = img.pixels[:]
    best, bi = -1.0, 0
    step = 4 if w > 1024 else 1
    for y in range(0, h, step):
        row = y * w * 4
        for x in range(0, w, step):
            i = row + x * 4
            v = px[i] + px[i + 1] + px[i + 2]
            if v > best:
                best, bi = v, (x, y)
    u, v = (bi[0] + 0.5) / w, (bi[1] + 0.5) / h
    # equirectangular: u -> longitude around Z (Blender maps u=0.5 to -Y... use the same convention as the
    # Environment node with Generated coords: direction = (-sin(phi)?)); derive numerically instead
    phi = (u - 0.5) * 2 * math.pi            # 0 at the image centre
    theta = (v - 0.5) * math.pi              # +pi/2 at the top row
    d = Vector((-math.cos(theta) * math.cos(phi), -math.cos(theta) * math.sin(phi), math.sin(theta)))
    d.rotate(__import__("mathutils").Euler((0, 0, math.radians(rotation_deg))))
    print(f"hdri_sun {aid}: brightest at u={u:.3f} v={v:.3f}, elevation {math.degrees(theta):.1f} deg")
    return d


def sun_lamp(direction, strength=4.0, kelvin_k=3200, angle_deg=0.6, name="sun"):
    """A Sun lamp shining along -direction (direction points towards the sun)."""
    import assets as A
    lt = bpy.data.lights.new(name, "SUN")
    lt.energy = strength
    lt.angle = math.radians(angle_deg)
    lt.color = A.kelvin(kelvin_k)
    ob = bpy.data.objects.new(name, lt)
    m._link(ob)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (-Vector(direction)).to_track_quat("-Z", "Y")
    return ob


def place(root, location, align="base", yaw_deg=0.0):
    """Move a model root so its children's bounding box is centred in x/y at location and, with
    align='base', rests on location.z. Modular packs keep their layout offsets; this cancels them."""
    lo, hi = model_bounds(root)
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z if align == "base" else (lo.z + hi.z) / 2))
    root.location = Vector(root.location) + (Vector(location) - centre)
    if yaw_deg:
        # rotate about the new anchor, not the pack origin
        piv = bpy.data.objects.new(root.name + "_piv", None)
        m._link(piv)
        piv.location = location
        bpy.context.view_layer.update()
        root.parent = piv
        root.matrix_parent_inverse = piv.matrix_world.inverted()
        piv.rotation_euler.z = math.radians(yaw_deg)
        return piv
    return root


def cut_faces(ob, keep):
    """Delete the faces of a mesh object whose world-space centre fails keep(Vector) -> bool.
    Used to take a part off an appended model, such as the handset off a payphone."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    mw = ob.matrix_world
    doomed = [f for f in bm.faces if not keep(mw @ f.calc_center_median())]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    return len(doomed)


def cut_islands(ob, keep):
    """Delete whole connected pieces of a mesh object: keep(lo, hi) gets each island's world-space bounds
    and returns False for the ones to drop (the handset and cord of the payphone, say)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    mw = ob.matrix_world
    seen = set()
    doomed = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            comp.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen:
                    stack.append(o)
        cos = [mw @ c.co for c in comp]
        lo = Vector((min(c.x for c in cos), min(c.y for c in cos), min(c.z for c in cos)))
        hi = Vector((max(c.x for c in cos), max(c.y for c in cos), max(c.z for c in cos)))
        if not keep(lo, hi):
            doomed.extend(comp)
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    return len(doomed)


def split_islands(ob, take, name="split"):
    """Move the connected pieces of a mesh for which take(lo, hi) is True (world-space bounds) into a new
    object with the same materials and transform; returns it (None when nothing matched)."""
    import bmesh
    dup = ob.copy()
    dup.data = ob.data.copy()
    dup.name = name
    for c in ob.users_collection:
        c.objects.link(dup)
    keep_in_dup = lambda lo, hi: take(lo, hi)            # noqa: E731
    cut_islands(dup, keep_in_dup)
    n = cut_islands(ob, lambda lo, hi: not take(lo, hi))
    if n == 0 or len(dup.data.vertices) == 0:
        bpy.data.objects.remove(dup)
        return None
    return dup


THIRD = os.path.join(ROOT, "assets", "thirdparty")


def glb(path, name="glb", length=None, scale=None):
    """Import a glTF binary (a path, or an Objaverse key from fetch_assets.py) under a new empty.
    The empty sits at the model's footprint centre on its base; length scales the longest side to that many
    metres, scale is a plain factor (1/12 for a model built in real metres). Returns (pivot, meshes)."""
    if not os.path.isabs(path) and not path.endswith(".glb"):
        path = os.path.join(THIRD, "objaverse", f"{path}.glb")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    tops = [o for o in new if o.parent is None]
    meshes = [o for o in new if o.type == "MESH"]
    pivot = bpy.data.objects.new(name, None)
    m._link(pivot)
    for t in tops:
        t.parent = pivot
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in meshes:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for t in tops:
        t.matrix_world = Matrix.Translation(-centre) @ t.matrix_world
    s = scale if scale is not None else (length / max(hi - lo) if length else 1.0)
    pivot.scale = (s, s, s)
    bpy.context.view_layer.update()
    print(f"glb {os.path.basename(path)}: {len(meshes)} meshes, native size {tuple(round(v, 3) for v in (hi - lo))}, scale {s:.4f}")
    return pivot, meshes


def mask_rects(img, test, step=2, min_px=40):
    """Connected regions of an image where test(r, g, b) is true, as pixel boxes (x0, y0, x1, y1), origin at
    the bottom left like UVs. Sampled every `step` pixels."""
    w, h = img.size
    px = img.pixels[:]
    gw, gh = w // step, h // step
    on = bytearray(gw * gh)
    for gy in range(gh):
        row = gy * step * w
        for gx in range(gw):
            i = (row + gx * step) * 4
            if test(px[i], px[i + 1], px[i + 2]):
                on[gy * gw + gx] = 1
    seen = bytearray(gw * gh)
    rects = []
    for start in range(gw * gh):
        if not on[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        n = 0
        while stack:
            k = stack.pop()
            x, y = k % gw, k // gw
            n += 1
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < gw and 0 <= ny < gh:
                    kk = ny * gw + nx
                    if on[kk] and not seen[kk]:
                        seen[kk] = 1
                        stack.append(kk)
        if n * step * step >= min_px:
            rects.append((x0 * step, y0 * step, (x1 + 1) * step, (y1 + 1) * step))
    return rects


def uv_to_world(meshes, uv):
    """Every place on the meshes whose UV is `uv`: a list of (world point, world normal). A texture used on
    mirrored faces (both sides of a train) gives one hit per side."""
    from mathutils.geometry import barycentric_transform, intersect_point_tri_2d
    p = Vector((uv[0], uv[1], 0.0))
    hits = []
    for ob in meshes:
        me = ob.data
        if not me.uv_layers:
            continue
        me.calc_loop_triangles()
        uvd = me.uv_layers.active.data
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        for tri in me.loop_triangles:
            a, b, c = (uvd[li].uv for li in tri.loops)
            if abs((b - a).cross(c - a)) < 1e-12:   # collapsed UVs (unmapped faces)
                continue
            # textures repeat: try the query point in every UV tile the triangle touches
            for du in range(math.floor(min(a.x, b.x, c.x)), math.floor(max(a.x, b.x, c.x)) + 1):
                for dv in range(math.floor(min(a.y, b.y, c.y)), math.floor(max(a.y, b.y, c.y)) + 1):
                    pt = Vector((p.x + du, p.y + dv, 0.0))
                    if not intersect_point_tri_2d(pt.xy, a, b, c):
                        continue
                    va, vb, vc = (me.vertices[vi].co for vi in tri.vertices)
                    q = barycentric_transform(pt, a.to_3d(), b.to_3d(), c.to_3d(), va, vb, vc)
                    if q.x != q.x:   # NaN
                        continue
                    hits.append((mw @ q, (nm @ tri.normal).normalized()))
    return hits


def _math(nt, op, *args, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for k, v in enumerate(args):
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            nt.links.new(v, n.inputs[k])
    return n.outputs[0]


def ripple_height(nt, scale=125.0, spacing=0.08, mask=None):
    """Rain rings on standing water. In each Voronoi cell (object space, `scale` cells per metre) a drop has
    landed: its rings run out to a front 0.2-0.45 of a cell from the impact, `spacing` apart, fading behind the
    front; a third of the cells are still. Returns a height socket in [-1, 1], times mask if given."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.voronoi_dimensions = "2D"
    vo.inputs["Scale"].default_value = 1.0
    vo.inputs["Randomness"].default_value = 1.0
    nt.links.new(mp.outputs[0], vo.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vo.outputs["Color"], sep.inputs["Color"])
    front = _math(nt, "MULTIPLY_ADD", sep.outputs["Red"], 0.25, 0.2)
    behind = _math(nt, "SUBTRACT", front, vo.outputs["Distance"])
    fade_in = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", behind, 3.0 * spacing), clamp=True)
    fade_out = _math(nt, "ADD", 1.0, _math(nt, "DIVIDE", behind, 0.5 * spacing), clamp=True)
    wave = _math(nt, "SINE", _math(nt, "MULTIPLY", behind, 2.0 * math.pi / spacing))
    h = _math(nt, "MULTIPLY", wave, _math(nt, "MULTIPLY", fade_in, fade_out))
    h = _math(nt, "MULTIPLY", h, _math(nt, "GREATER_THAN", sep.outputs["Green"], 0.33))
    h = _math(nt, "MULTIPLY", h, _math(nt, "MULTIPLY_ADD", sep.outputs["Blue"], 0.5, 0.5))
    if mask is not None:
        h = _math(nt, "MULTIPLY", h, mask)
    return h


def ripple_normal(nt, height, depth=0.00002, strength=1.0):
    """A Bump normal from a ripple height: `depth` metres of swell (20 um at 1:12 is a quarter millimetre of
    real ripple)."""
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = depth
    nt.links.new(height, bp.inputs["Height"])
    return bp.outputs["Normal"]


def wet(mat, cover=0.4, scale=8.0, seed=0.0, dark=0.72, puddle_dark=0.45, film_rough=0.14, ripple=0.0,
        ripple_scale=125.0):
    """Rain on a Principled material: darker, glossier, a clear water coat, and puddles where a noise mask
    (object space, `scale` per metre) passes; in them the surface is mirror-flat. ripple > 0 puts rain rings
    on the puddles' water (the coat's normal), that strong. Returns the mask socket."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    next(sk for sk in nz.inputs if sk.name == "W").default_value = seed
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 3.0
    nz.inputs["Roughness"].default_value = 0.55
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    t = 0.5 + (0.5 - cover) * 0.3
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = t, t + 0.025
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mask = mr.outputs["Result"]

    def mix_val(a, b):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "FLOAT"
        nt.links.new(mask, mx.inputs["Factor"])
        for sk, v in ((mx.inputs[2], a), (mx.inputs[3], b)):
            if isinstance(v, float):
                sk.default_value = v
            else:
                nt.links.new(v, sk)
        return mx.outputs[0]

    # colour: everything darker when wet, the puddles darker still
    links = bsdf.inputs["Base Color"].links
    if links:
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(links[0].from_socket, mul.inputs["A"])
        k = mix_val(dark, puddle_dark)
        comb = nt.nodes.new("ShaderNodeCombineColor")
        for ch in ("Red", "Green", "Blue"):
            nt.links.new(k, comb.inputs[ch])
        nt.links.new(comb.outputs[0], mul.inputs["B"])
        nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    # roughness: the map damped, the puddles glassy
    rl = bsdf.inputs["Roughness"].links
    if rl:
        damp = nt.nodes.new("ShaderNodeMath")
        damp.operation = "MULTIPLY"
        damp.inputs[1].default_value = 0.55
        nt.links.new(rl[0].from_socket, damp.inputs[0])
        nt.links.new(mix_val(damp.outputs[0], 0.015), bsdf.inputs["Roughness"])
    else:
        nt.links.new(mix_val(bsdf.inputs["Roughness"].default_value * 0.55, 0.015), bsdf.inputs["Roughness"])
    # a water film on top: thin and a little blurred on the asphalt, a mirror in the puddles
    nt.links.new(mix_val(0.8, 1.0), bsdf.inputs["Coat Weight"])
    nt.links.new(mix_val(film_rough, 0.0), bsdf.inputs["Coat Roughness"])
    bsdf.inputs["Coat IOR"].default_value = 1.33
    if ripple:
        nt.links.new(ripple_normal(nt, ripple_height(nt, ripple_scale, mask=mask), strength=ripple),
                     bsdf.inputs["Coat Normal"])
    # puddles are flat: fade the relief under water
    nl = bsdf.inputs["Normal"].links
    if nl and nl[0].from_node.type == "BUMP":
        bp = nl[0].from_node
        s0 = bp.inputs["Strength"].default_value
        nt.links.new(mix_val(s0, 0.0), bp.inputs["Strength"])
    return mask
