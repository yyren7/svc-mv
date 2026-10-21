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
from mathutils import Vector

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
    nr = tex("nor_gl", True)
    if nr is not None and bump > 0:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.space = "OBJECT"   # box projection has no tangents; object space matches the Object coordinates
        nm.inputs["Strength"].default_value = bump
        nt.links.new(nr.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
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
    for ob in dst.objects:
        if ob is None:
            continue
        if ob.type not in ("MESH", "CURVE"):
            bpy.data.objects.remove(ob)
            continue
        if picks and not any(p.lower() in ob.name.lower() for p in picks):
            bpy.data.objects.remove(ob)
            continue
        m._link(ob)
        if ob.parent is None or ob.parent.name not in {o.name for o in dst.objects if o}:
            ob.parent = root
        kept.append(ob)
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
