"""Blender-native building blocks for the PV, on top of mvlib's layout helpers.

- bake(): record per-frame values of transforms / visibility into real F-curves, then add F-curve
  modifiers (Stepped = animation on twos, Noise = handheld camera). The .blend stays editable and
  EEVEE motion blur sees the motion.
- Geometry Nodes groups: kinetic text (String to Curves, per-character reveal / scatter / spin),
  a simulation-zone particle burst system, anime speed lines, mesh shatter, a running timecode.
- toon_halftone(): 3-tone cel material whose mid tone is a screen-space halftone, plus a rim light.
- Line Art (Grease Pencil v3) outlines with a noise modifier for line boil.
- compositor(): Glare bloom, lens dispersion (RGB split), pixelate glitch, invert impact frames.
- Rigid body and cloth helpers.
"""
import math

import bpy

import mvlib as m


# ---------------------------------------------------------------- socket helpers

def sock(sockets, name, kind=None):
    """Socket by name among the available ones, optionally of a type ('VECTOR', 'VALUE', ...)."""
    for s in sockets:
        if s.name != name:
            continue
        if not getattr(s, "enabled", True) or getattr(s, "is_unavailable", False):
            continue
        if kind and s.type != kind:
            continue
        return s
    raise KeyError(f"no socket {name!r} ({kind}) in {[f'{s.name}:{s.type}' for s in sockets]}")


class G:
    """Tiny node-graph builder: G(tree).node('Type', **props) and G.link(a, b)."""

    def __init__(self, tree):
        self.tree = tree

    def node(self, kind, inputs=None, **props):
        n = self.tree.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            name, typ = (k if isinstance(k, tuple) else (k, None))
            sock(n.inputs, name, typ).default_value = v
        return n

    def link(self, out, inp):
        self.tree.links.new(out, inp)

    def math(self, op, a, b=None, clamp=False):
        n = self.tree.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def vmath(self, op, a, b=None):
        n = self.tree.nodes.new("ShaderNodeVectorMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            target = n.inputs[3] if (op == "SCALE" and i == 1) else n.inputs[i]
            if isinstance(v, (int, float, tuple)):
                target.default_value = v
            else:
                self.link(v, target)
        out = n.outputs[1] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs[0]
        return out


def _iface(ng, name, io, kind, default=None, lo=None, hi=None):
    s = ng.interface.new_socket(name=name, in_out=io, socket_type=kind)
    if default is not None:
        s.default_value = default
    if lo is not None:
        s.min_value = lo
    if hi is not None:
        s.max_value = hi
    return s


def gn_object(name, group, inputs=None, z=0.0):
    """An object carrying a Geometry Nodes modifier; returns (object, modifier)."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.location.z = z
    m._link(obj)
    mod = obj.modifiers.new("GN", "NODES")
    mod.node_group = group
    for k, v in (inputs or {}).items():
        set_input(obj, k, v)
    return obj, mod


def _ident(group, name):
    for item in group.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            return item.identifier
    raise KeyError(name)


def _input(obj, name):
    """Blender 5.x: modifier inputs live at modifier.properties.inputs.<identifier>.value."""
    mod = obj.modifiers["GN"]
    ident = _ident(mod.node_group, name)
    return getattr(mod.properties.inputs, ident), f'modifiers["GN"].properties.inputs.{ident}.value'


def set_input(obj, name, value):
    _input(obj, name)[0].value = value


def key_input(obj, name, keys, interp="CONSTANT"):
    """keys: [(frame, value)] on a Geometry Nodes modifier input."""
    st, path = _input(obj, name)
    for f, v in keys:
        st.value = v
        obj.keyframe_insert(data_path=path, frame=f)
    set_interp(obj, path, interp)


# ---------------------------------------------------------------- F-curves

def _channelbag(idblock):
    from bpy_extras import anim_utils
    ad = idblock.animation_data or idblock.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f"{idblock.name}_act")
    if ad.action_slot is None:
        slot = ad.action.slots.new(idblock.id_type, idblock.name)
        ad.action_slot = slot
    return anim_utils.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)


def fcurve(idblock, path, index, frames, values, interp="LINEAR"):
    cb = _channelbag(idblock)
    fc = cb.fcurves.find(path, index=index) or cb.fcurves.new(path, index=index)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    co = []
    for f, v in zip(frames, values):
        co += [f, v]
    fc.keyframe_points.foreach_set("co", co)
    fc.keyframe_points.foreach_set("interpolation", [_INTERP[interp]] * len(frames))
    fc.update()
    return fc


_INTERP = {"CONSTANT": 0, "LINEAR": 1, "BEZIER": 2}


def set_interp(idblock, path, interp):
    cb = _channelbag(idblock)
    for fc in cb.fcurves:
        if fc.data_path == path:
            for k in fc.keyframe_points:
                k.interpolation = interp


def stepped(idblock, step=2):
    """Animation on twos: hold every pose for `step` frames."""
    if not idblock.animation_data or not idblock.animation_data.action:
        return
    for fc in _channelbag(idblock).fcurves:
        mod = fc.modifiers.new("STEPPED")
        mod.frame_step = step
        mod.frame_offset = 0.5


def noise(idblock, path, index, strength, scale=8.0, phase=0.0):
    fc = _channelbag(idblock).fcurves.find(path, index=index)
    if fc is None:
        fc = fcurve(idblock, path, index, [1], [getattr(idblock, path)[index]])
    mod = fc.modifiers.new("NOISE")
    mod.strength = strength
    mod.scale = scale
    mod.phase = phase
    return mod


class Recorder:
    """Samples object transforms / visibility at every frame and writes them as F-curves,
    keeping only the channels that actually change."""

    CHANNELS = (("location", 3), ("rotation_euler", 3), ("rotation_quaternion", 4), ("scale", 3))

    def __init__(self, objs):
        self.objs = [o for o in objs]
        self.data = {o.name: {} for o in self.objs}
        self.frames = []

    def sample(self, frame):
        self.frames.append(frame)
        for o in self.objs:
            d = self.data[o.name]
            for path, n in self.CHANNELS:
                if path == "rotation_quaternion" and o.rotation_mode != "QUATERNION":
                    continue
                if path == "rotation_euler" and o.rotation_mode == "QUATERNION":
                    continue
                v = getattr(o, path)
                for i in range(n):
                    d.setdefault((path, i), []).append(v[i])
            d.setdefault(("hide_render", -1), []).append(float(o.hide_render))

    def write(self):
        for o in self.objs:
            for (path, i), vals in self.data[o.name].items():
                if max(vals) - min(vals) < 1e-6:
                    continue
                if path == "hide_render":
                    fcurve(o, "hide_render", 0, self.frames, vals, "CONSTANT")
                else:
                    fcurve(o, path, i, self.frames, vals, "LINEAR")
            if o.get("twos"):
                stepped(o)


# ---------------------------------------------------------------- materials

def value(nt, v=0.0):
    """A Value node's output: the way a shot sets a material's number per frame (an object custom property read
    by an Attribute node is not re-read under persistent render data)."""
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


def _mix_rgba(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    for s, v in ((sock(n.inputs, "Factor", "VALUE"), fac), (sock(n.inputs, "A", "RGBA"), a),
                 (sock(n.inputs, "B", "RGBA"), b)):
        if isinstance(v, tuple) or isinstance(v, (int, float)):
            s.default_value = v
        else:
            nt.links.new(v, s)
    return sock(n.outputs, "Result", "RGBA")


def toon_halftone(lit, dark, threshold=0.35, mid=0.18, cells=90, rim="#FFFFFF", rim_amount=0.0):
    """3-tone cel shading: lit, a screen-space halftone band, solid dark; optional rim light.
    Brightness above `threshold` is lit, below `mid` is dark, in between the dots grow as it darkens."""
    key = ("toonht", lit, dark, threshold, mid, cells, rim, rim_amount)
    if key in m._MATS:
        return m._MATS[key]
    mat, nt, out = m._new_mat(f"toonht{lit}{dark}")
    g = G(nt)
    diff = g.node("ShaderNodeBsdfDiffuse")
    s2r = g.node("ShaderNodeShaderToRGB")
    g.link(diff.outputs[0], s2r.inputs[0])
    bw = g.node("ShaderNodeRGBToBW")
    g.link(s2r.outputs["Color"], bw.inputs[0])
    L = bw.outputs[0]
    tc = g.node("ShaderNodeTexCoord")
    win = tc.outputs["Window"]
    aspect = g.vmath("MULTIPLY", win, (cells * 16 / 9, cells, 1.0))
    frac = g.vmath("FRACTION", aspect)
    centred = g.vmath("SUBTRACT", frac, (0.5, 0.5, 0.0))
    dist = g.vmath("LENGTH", centred)
    rng = g.node("ShaderNodeMapRange", clamp=True)
    sock(rng.inputs, "From Min", "VALUE").default_value = mid
    sock(rng.inputs, "From Max", "VALUE").default_value = threshold
    sock(rng.inputs, "To Min", "VALUE").default_value = 0.62
    sock(rng.inputs, "To Max", "VALUE").default_value = 0.0
    g.link(L, sock(rng.inputs, "Value", "VALUE"))
    dot = g.math("LESS_THAN", dist, rng.outputs[0])
    is_dark = g.math("LESS_THAN", L, mid)
    darkness = g.math("MAXIMUM", dot, is_dark)
    col = _mix_rgba(nt, darkness, m.srgb(lit), m.srgb(dark))
    if rim_amount > 0:
        lw = g.node("ShaderNodeLayerWeight", inputs={"Blend": 0.35})
        rim_mask = g.math("GREATER_THAN", lw.outputs["Facing"], 1 - rim_amount)
        col = _mix_rgba(nt, rim_mask, col, m.srgb(rim))
    em = g.node("ShaderNodeEmission")
    g.link(col, em.inputs["Color"])
    g.link(em.outputs[0], out.inputs["Surface"])
    m._MATS[key] = mat
    return mat


def glow(hexstr, strength=2.5):
    """Emission brighter than 1 so the compositor's bloom picks it up."""
    key = ("glow", hexstr, strength)
    if key not in m._MATS:
        mat = m.flat(hexstr).copy()
        mat.name = f"glow{hexstr}"
        for n in mat.node_tree.nodes:
            if n.type == "EMISSION":
                n.inputs["Strength"].default_value = strength
        m._MATS[key] = mat
    return m._MATS[key]


# ---------------------------------------------------------------- Line Art

_LINEART = {}


def lineart_collection(color, width_px=5.0, boil=True):
    """Collection whose meshes get Grease Pencil Line Art outlines (replaces Freestyle).
    width_px is approximate, for objects about 20 units from the camera."""
    key = (color, width_px)
    if key in _LINEART:
        return _LINEART[key]
    scene = bpy.context.scene
    coll = bpy.data.collections.new(f"la{color}")
    scene.collection.children.link(coll)
    gp = bpy.data.grease_pencils.new(f"la{color}")
    gp.layers.new("Lines")
    mat = bpy.data.materials.new(f"la{color}")
    bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color = m.srgb(color)
    gp.materials.append(mat)
    obj = bpy.data.objects.new(f"la{color}", gp)
    scene.collection.objects.link(obj)
    mod = obj.modifiers.new("lineart", "LINEART")
    mod.source_type = "COLLECTION"
    mod.source_collection = coll
    mod.target_layer = "Lines"
    mod.target_material = mat
    mod.radius = width_px / 2 * (m.W / 1920)
    for prop, val in (("use_contour", True), ("use_crease", True), ("crease_threshold", math.radians(130)),
                      ("use_intersection", False), ("use_material", False), ("use_edge_mark", False)):
        if hasattr(mod, prop):
            setattr(mod, prop, val)
    if boil:
        try:
            nz = obj.modifiers.new("boil", "GREASE_PENCIL_NOISE")
            nz.factor = 0.012
            nz.factor_thickness = 0.4
            nz.noise_scale = 0.6
            nz.use_random = True
            nz.step = 2
        except Exception as e:   # noqa: BLE001 - the look still works without boil
            print("lineart boil unavailable:", e)
    _LINEART[key] = coll
    return coll


def install_hooks():
    m.HOOKS["toon"] = lambda lit, dark, threshold=0.35: toon_halftone(lit, dark, threshold, rim="#FFFFFF",
                                                                       rim_amount=0.12)
    m.HOOKS["outlined"] = lineart_collection
    _LINEART.clear()


# ---------------------------------------------------------------- Geometry Nodes groups

def kinetic_text_group(font_name, material, size=1.0, spacing=1.0):
    """String to Curves with a per-character reveal.
    Inputs: String, Progress (characters shown, fractional = mid-animation), Scatter, Spin, Seed, Pop.
    Character i animates while Progress goes from i to i + 1: it flies in from a random offset
    (Scatter), unspins (Spin), and overshoots its scale (Pop)."""
    ng = bpy.data.node_groups.new(f"KineticText_{font_name}", "GeometryNodeTree")
    _iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    _iface(ng, "String", "INPUT", "NodeSocketString", "")
    _iface(ng, "Progress", "INPUT", "NodeSocketFloat", 1000.0)
    _iface(ng, "Scatter", "INPUT", "NodeSocketFloat", 3.0)
    _iface(ng, "Spin", "INPUT", "NodeSocketFloat", 1.5)
    _iface(ng, "Pop", "INPUT", "NodeSocketFloat", 0.6)
    _iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    g = G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    s2c = g.node("GeometryNodeStringToCurves")
    sock(s2c.inputs, "Size").default_value = size
    sock(s2c.inputs, "Character Spacing").default_value = spacing
    sock(s2c.inputs, "Font").default_value = m.font(font_name)
    g.link(gin.outputs["String"], sock(s2c.inputs, "String"))
    idx = g.node("GeometryNodeInputIndex").outputs[0]
    local = g.math("SUBTRACT", gin.outputs["Progress"], idx)
    p = g.node("ShaderNodeMapRange", clamp=True, interpolation_type="SMOOTHSTEP")
    g.link(local, sock(p.inputs, "Value", "VALUE"))
    p = p.outputs[0]
    inv = g.math("SUBTRACT", 1.0, p)
    # scale: 0 -> 1 + Pop -> 1 (bump peaks mid-way)
    bump = g.math("MULTIPLY", g.math("MULTIPLY", p, inv), g.math("MULTIPLY", gin.outputs["Pop"], 4.0))
    scl = g.math("ADD", p, bump)
    rnd = g.node("FunctionNodeRandomValue", data_type="FLOAT_VECTOR")
    sock(rnd.inputs, "Min", "VECTOR").default_value = (-1, -1, -0.3)
    sock(rnd.inputs, "Max", "VECTOR").default_value = (1, 1, 0.3)
    g.link(idx, sock(rnd.inputs, "ID"))
    g.link(gin.outputs["Seed"], sock(rnd.inputs, "Seed"))
    rvec = sock(rnd.outputs, "Value", "VECTOR")
    off = g.vmath("SCALE", rvec, g.math("MULTIPLY", inv, gin.outputs["Scatter"]))
    tr = g.node("GeometryNodeTranslateInstances")
    g.link(s2c.outputs["Curve Instances"], tr.inputs["Instances"])
    g.link(off, tr.inputs["Translation"])
    sock(tr.inputs, "Local Space").default_value = False
    euler = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", inv, gin.outputs["Spin"]), euler.inputs["Z"])
    e2r = g.node("FunctionNodeEulerToRotation")
    g.link(euler.outputs[0], e2r.inputs[0])
    rot = g.node("GeometryNodeRotateInstances")
    g.link(tr.outputs[0], rot.inputs["Instances"])
    g.link(e2r.outputs[0], rot.inputs["Rotation"])
    g.link(s2c.outputs["Pivot Point"], sock(rot.inputs, "Pivot Point"))
    sc = g.node("GeometryNodeScaleInstances")
    g.link(rot.outputs[0], sc.inputs["Instances"])
    sv = g.node("ShaderNodeCombineXYZ")
    for ax in "XYZ":
        g.link(scl, sv.inputs[ax])
    g.link(sv.outputs[0], sock(sc.inputs, "Scale"))
    g.link(s2c.outputs["Pivot Point"], sock(sc.inputs, "Center"))
    cap = g.node("GeometryNodeCaptureAttribute", domain="INSTANCE")
    cap.capture_items.new("INT", "Char")
    g.link(sc.outputs[0], cap.inputs[0])
    g.link(idx, cap.inputs[1])
    real = g.node("GeometryNodeRealizeInstances")
    g.link(cap.outputs[0], real.inputs[0])
    fill = g.node("GeometryNodeFillCurve")
    g.link(real.outputs[0], fill.inputs["Curve"])
    g.link(cap.outputs[1], fill.inputs["Group ID"])
    try:
        sock(fill.inputs, "Fill Rule").default_value = "Even-Odd"
    except (TypeError, KeyError):
        pass
    setm = g.node("GeometryNodeSetMaterial")
    g.link(fill.outputs[0], setm.inputs["Geometry"])
    sock(setm.inputs, "Material").default_value = material
    g.link(setm.outputs[0], gout.inputs["Geometry"])
    return ng


def kinetic_text(body, font_name, size, x, y, color, z=1.0, spacing=1.0, seed=0, scatter=3.0, spin=1.5,
                 pop=0.6, material=None):
    ng = kinetic_text_group(font_name, material or m.flat(color), size, spacing)
    obj, _ = gn_object("ktext", ng, {"String": body, "Seed": seed, "Scatter": scatter, "Spin": spin, "Pop": pop}, z)
    obj.location.x, obj.location.y = x, y
    return obj


def timecode_group(font_name, material, size, offset_s, fps=24):
    """'00:MM:SS:FF' of the song time, computed from the scene frame."""
    ng = bpy.data.node_groups.new("Timecode", "GeometryNodeTree")
    _iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    g = G(ng)
    gout = g.node("NodeGroupOutput")
    st = g.node("GeometryNodeInputSceneTime")
    t = g.math("ADD", g.math("DIVIDE", g.math("SUBTRACT", st.outputs["Frame"], 1.0), float(fps)), offset_s)

    def two(v):
        s = g.node("FunctionNodeValueToString")
        g.link(g.math("FLOOR", v), s.inputs["Value"])
        less = g.math("LESS_THAN", v, 10.0)
        pad = g.node("GeometryNodeStringJoin")
        z = g.node("FunctionNodeInputString", string="0")
        g.link(s.outputs[0], pad.inputs["Strings"])
        g.link(z.outputs[0], pad.inputs["Strings"])
        sw = g.node("GeometryNodeSwitch", input_type="STRING")
        g.link(less, sw.inputs["Switch"])
        g.link(s.outputs[0], sw.inputs["False"])
        g.link(pad.outputs[0], sw.inputs["True"])
        return sw.outputs[0]

    mins = two(g.math("FLOOR", g.math("DIVIDE", t, 60.0)))
    secs = two(g.math("FLOOR", g.math("MODULO", t, 60.0)))
    frs = two(g.math("FLOOR", g.math("MULTIPLY", g.math("FRACT", t), float(fps))))
    join = g.node("GeometryNodeStringJoin")
    sock(join.inputs, "Delimiter").default_value = ":"
    head = g.node("FunctionNodeInputString", string="00")
    for s in (frs, secs, mins, head.outputs[0]):   # multi-input sockets list links last-first
        g.link(s, join.inputs["Strings"])
    s2c = g.node("GeometryNodeStringToCurves")
    sock(s2c.inputs, "Size").default_value = size
    sock(s2c.inputs, "Font").default_value = m.font(font_name)
    g.link(join.outputs[0], sock(s2c.inputs, "String"))
    real = g.node("GeometryNodeRealizeInstances")
    g.link(s2c.outputs["Curve Instances"], real.inputs[0])
    fill = g.node("GeometryNodeFillCurve")
    g.link(real.outputs[0], fill.inputs["Curve"])
    setm = g.node("GeometryNodeSetMaterial")
    g.link(fill.outputs[0], setm.inputs["Geometry"])
    sock(setm.inputs, "Material").default_value = material
    g.link(setm.outputs[0], gout.inputs["Geometry"])
    return ng


def burst_group(stars_collection):
    """Simulation-zone particles. While the Emit input is > 0.5 (key it to 1 on the trigger frames),
    Count points spawn at Origin with random directions and speeds; they slow down with drag,
    age, and die after Life seconds. Each point instances a random star from the collection,
    spinning, shrinking with age."""
    ng = bpy.data.node_groups.new("Bursts", "GeometryNodeTree")
    _iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    _iface(ng, "Emit", "INPUT", "NodeSocketFloat", 0.0)
    _iface(ng, "Count", "INPUT", "NodeSocketInt", 20)
    _iface(ng, "Origin", "INPUT", "NodeSocketVector", (0.0, 0.0, 0.0))
    _iface(ng, "Speed Min", "INPUT", "NodeSocketFloat", 6.0)
    _iface(ng, "Speed Max", "INPUT", "NodeSocketFloat", 12.0)
    _iface(ng, "Drag", "INPUT", "NodeSocketFloat", 4.0)
    _iface(ng, "Life", "INPUT", "NodeSocketFloat", 0.6)
    _iface(ng, "Size", "INPUT", "NodeSocketFloat", 0.25)
    _iface(ng, "Seed", "INPUT", "NodeSocketInt", 0)
    g = G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    si = g.node("GeometryNodeSimulationInput")
    so = g.node("GeometryNodeSimulationOutput")
    si.pair_with_output(so)
    dt = si.outputs["Delta Time"]
    geo = si.outputs["Geometry"]

    def named(name, kind):
        n = g.node("GeometryNodeInputNamedAttribute", data_type=kind)
        n.inputs["Name"].default_value = name
        return sock(n.outputs, "Attribute")

    def store(geom, name, kind, value):
        n = g.node("GeometryNodeStoreNamedAttribute", data_type=kind, domain="POINT")
        g.link(geom, n.inputs["Geometry"])
        n.inputs["Name"].default_value = name
        tgt = sock(n.inputs, "Value")
        if isinstance(value, (int, float, tuple)):
            tgt.default_value = value
        else:
            g.link(value, tgt)
        return n.outputs[0]

    # existing particles: move, drag, age, die
    vel = named("vel", "FLOAT_VECTOR")
    sp = g.node("GeometryNodeSetPosition")
    g.link(geo, sp.inputs["Geometry"])
    g.link(g.vmath("SCALE", vel, dt), sp.inputs["Offset"])
    damp = g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gin.outputs["Drag"], dt)), 0.0)
    moved = store(sp.outputs[0], "vel", "FLOAT_VECTOR", g.vmath("SCALE", vel, damp))
    age = g.math("ADD", named("age", "FLOAT"), dt)
    aged = store(moved, "age", "FLOAT", age)
    dead = g.math("GREATER_THAN", named("age", "FLOAT"), gin.outputs["Life"])
    dl = g.node("GeometryNodeDeleteGeometry", domain="POINT")
    g.link(aged, dl.inputs["Geometry"])
    g.link(dead, dl.inputs["Selection"])

    # new particles
    on = g.math("GREATER_THAN", gin.outputs["Emit"], 0.5)
    cnt = g.math("MULTIPLY", on, gin.outputs["Count"])
    pts = g.node("GeometryNodePoints")
    g.link(cnt, pts.inputs["Count"])
    g.link(gin.outputs["Origin"], pts.inputs["Position"])
    frame = g.node("GeometryNodeInputSceneTime").outputs["Frame"]
    seed = g.math("ADD", g.math("MULTIPLY", frame, 7.0), gin.outputs["Seed"])
    idx = g.node("GeometryNodeInputIndex").outputs[0]

    def rand(lo, hi, salt):
        r = g.node("FunctionNodeRandomValue", data_type="FLOAT")
        sock(r.inputs, "Min", "VALUE").default_value = lo
        sock(r.inputs, "Max", "VALUE").default_value = hi
        g.link(idx, sock(r.inputs, "ID"))
        g.link(g.math("ADD", seed, float(salt)), sock(r.inputs, "Seed"))
        return sock(r.outputs, "Value", "VALUE")

    ang = rand(0.0, 2 * math.pi, 1)
    spd_r = g.node("ShaderNodeMapRange")
    g.link(rand(0.0, 1.0, 2), sock(spd_r.inputs, "Value", "VALUE"))
    g.link(gin.outputs["Speed Min"], sock(spd_r.inputs, "To Min", "VALUE"))
    g.link(gin.outputs["Speed Max"], sock(spd_r.inputs, "To Max", "VALUE"))
    spd = spd_r.outputs[0]
    v = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", g.math("COSINE", ang), spd), v.inputs["X"])
    g.link(g.math("MULTIPLY", g.math("SINE", ang), spd), v.inputs["Y"])
    g.link(rand(-2.0, 2.0, 3), v.inputs["Z"])
    newp = store(pts.outputs[0], "vel", "FLOAT_VECTOR", v.outputs[0])
    newp = store(newp, "age", "FLOAT", 0.0)
    newp = store(newp, "spin", "FLOAT", rand(-9.0, 9.0, 4))
    newp = store(newp, "size", "FLOAT", rand(0.5, 1.2, 5))
    pick = g.node("GeometryNodeStoreNamedAttribute", data_type="INT", domain="POINT")
    g.link(newp, pick.inputs["Geometry"])
    pick.inputs["Name"].default_value = "pick"
    ri = g.node("FunctionNodeRandomValue", data_type="INT")
    sock(ri.inputs, "Min", "INT").default_value = 0
    sock(ri.inputs, "Max", "INT").default_value = 64
    g.link(idx, sock(ri.inputs, "ID"))
    g.link(g.math("ADD", seed, 6.0), sock(ri.inputs, "Seed"))
    g.link(sock(ri.outputs, "Value", "INT"), sock(pick.inputs, "Value"))
    join = g.node("GeometryNodeJoinGeometry")
    g.link(pick.outputs[0], join.inputs[0])
    g.link(dl.outputs[0], join.inputs[0])
    g.link(join.outputs[0], so.inputs["Geometry"])

    # draw
    coll = g.node("GeometryNodeCollectionInfo", transform_space="ORIGINAL")
    sock(coll.inputs, "Collection").default_value = stars_collection
    sock(coll.inputs, "Separate Children").default_value = True
    sock(coll.inputs, "Reset Children").default_value = True
    iop = g.node("GeometryNodeInstanceOnPoints")
    g.link(so.outputs["Geometry"], iop.inputs["Points"])
    g.link(coll.outputs[0], iop.inputs["Instance"])
    sock(iop.inputs, "Pick Instance").default_value = True
    g.link(named("pick", "INT"), sock(iop.inputs, "Instance Index"))
    e = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", named("spin", "FLOAT"), named("age", "FLOAT")), e.inputs["Z"])
    e2r = g.node("FunctionNodeEulerToRotation")
    g.link(e.outputs[0], e2r.inputs[0])
    g.link(e2r.outputs[0], sock(iop.inputs, "Rotation"))
    life_left = g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("DIVIDE", named("age", "FLOAT"), gin.outputs["Life"])), 0.0)
    s = g.math("MULTIPLY", g.math("MULTIPLY", life_left, named("size", "FLOAT")), gin.outputs["Size"])
    g.link(s, sock(iop.inputs, "Scale", "VECTOR") if any(i.name == "Scale" and i.type == "VECTOR" for i in iop.inputs)
           else sock(iop.inputs, "Scale"))
    g.link(iop.outputs[0], gout.inputs["Geometry"])
    return ng


def bursts(origin, colors, trigger_frames, count=20, speed=(6, 12), size=0.25, life=0.6, z=4.0, seed=0,
           glow_strength=2.2):
    """A particle system object; stars of the given colours glow (bloom) through the compositor."""
    stars = bpy.data.collections.new("stars")   # not linked to the scene: drawn only as instances
    for c in colors:
        s = m.star(c, z=0)
        s.data.materials[0] = glow(c, glow_strength)
        s.location = (0, 0, 0)
        bpy.context.scene.collection.objects.unlink(s)
        m.CREATED.remove(s)
        stars.objects.link(s)
    obj, _ = gn_object("bursts", burst_group(stars), {"Count": count, "Origin": (origin[0], origin[1], 0.0),
                                        "Speed Min": float(speed[0]), "Speed Max": float(speed[1]),
                                        "Size": size, "Life": life, "Seed": seed}, z)
    keys = []
    for f in trigger_frames:
        keys += [(f, 1.0), (f + 1, 0.0)]
    key_input(obj, "Emit", [(1, 0.0)] + keys)
    return obj


def speedlines_group(wedge_obj, count=80):
    """Anime focus lines: wedges around the origin, re-randomised every second frame."""
    ng = bpy.data.node_groups.new("SpeedLines", "GeometryNodeTree")
    _iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    _iface(ng, "Density", "INPUT", "NodeSocketFloat", 0.7)
    g = G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    pts = g.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = count
    frame = g.node("GeometryNodeInputSceneTime").outputs["Frame"]
    step = g.math("FLOOR", g.math("DIVIDE", g.math("ADD", frame, 0.5), 2.0))
    idx = g.node("GeometryNodeInputIndex").outputs[0]

    def rand(lo, hi, salt, kind="FLOAT"):
        r = g.node("FunctionNodeRandomValue", data_type=kind)
        if kind == "FLOAT":
            sock(r.inputs, "Min", "VALUE").default_value = lo
            sock(r.inputs, "Max", "VALUE").default_value = hi
        g.link(idx, sock(r.inputs, "ID"))
        g.link(g.math("ADD", step, float(salt)), sock(r.inputs, "Seed"))
        return r

    oi = g.node("GeometryNodeObjectInfo")
    sock(oi.inputs, "Object").default_value = wedge_obj
    iop = g.node("GeometryNodeInstanceOnPoints")
    g.link(pts.outputs[0], iop.inputs["Points"])
    g.link(oi.outputs["Geometry"], iop.inputs["Instance"])
    keep = rand(0, 0, 11, "BOOLEAN")
    g.link(gin.outputs["Density"], sock(keep.inputs, "Probability"))
    g.link(sock(keep.outputs, "Value", "BOOLEAN"), sock(iop.inputs, "Selection"))
    e = g.node("ShaderNodeCombineXYZ")
    g.link(sock(rand(0, 2 * math.pi, 12).outputs, "Value", "VALUE"), e.inputs["Z"])
    e2r = g.node("FunctionNodeEulerToRotation")
    g.link(e.outputs[0], e2r.inputs[0])
    g.link(e2r.outputs[0], sock(iop.inputs, "Rotation"))
    sv = g.node("ShaderNodeCombineXYZ")
    g.link(sock(rand(0.75, 1.35, 13).outputs, "Value", "VALUE"), sv.inputs["X"])
    g.link(sock(rand(0.5, 1.6, 14).outputs, "Value", "VALUE"), sv.inputs["Y"])
    sv.inputs["Z"].default_value = 1.0
    g.link(sv.outputs[0], sock(iop.inputs, "Scale", "VECTOR"))
    g.link(iop.outputs[0], gout.inputs["Geometry"])
    return ng


def speedlines(color, inner=4.0, outer=16.0, width=0.07, z=6.0, count=90):
    verts = [(inner, 0, 0), (outer, -width, 0), (outer, width, 0)]
    wedge = m._mesh_obj("wedge", verts, [(0, 1, 2)], m.flat(color), (0, 0, -100))
    wedge.hide_render = True
    m.CREATED.remove(wedge)
    obj, _ = gn_object("speedlines", speedlines_group(wedge, count), {}, z)
    return obj


def shatter_group():
    """Breaks a mesh into its faces, which fly apart and fall with Progress (0 = intact)."""
    ng = bpy.data.node_groups.new("Shatter", "GeometryNodeTree")
    _iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    _iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    _iface(ng, "Progress", "INPUT", "NodeSocketFloat", 0.0)
    _iface(ng, "Force", "INPUT", "NodeSocketFloat", 9.0)
    g = G(ng)
    gin = g.node("NodeGroupInput")
    gout = g.node("NodeGroupOutput")
    tri = g.node("GeometryNodeTriangulate")
    g.link(gin.outputs["Geometry"], tri.inputs["Mesh"])
    split = g.node("GeometryNodeSplitEdges")
    g.link(tri.outputs[0], split.inputs["Mesh"])
    cap = g.node("GeometryNodeCaptureAttribute", domain="FACE")
    cap.capture_items.new("VECTOR", "Dir")
    g.link(split.outputs[0], cap.inputs[0])
    r = g.node("FunctionNodeRandomValue", data_type="FLOAT_VECTOR")
    sock(r.inputs, "Min", "VECTOR").default_value = (-1, -0.4, -0.5)
    sock(r.inputs, "Max", "VECTOR").default_value = (1, 1.2, 1.5)
    g.link(sock(r.outputs, "Value", "VECTOR"), cap.inputs[1])
    p = gin.outputs["Progress"]
    fly = g.vmath("SCALE", cap.outputs[1], g.math("MULTIPLY", p, gin.outputs["Force"]))
    fall = g.node("ShaderNodeCombineXYZ")
    g.link(g.math("MULTIPLY", g.math("MULTIPLY", p, p), -14.0), fall.inputs["Y"])
    sp = g.node("GeometryNodeSetPosition")
    g.link(cap.outputs[0], sp.inputs["Geometry"])
    g.link(g.vmath("ADD", fly, fall.outputs[0]), sp.inputs["Offset"])
    se = g.node("GeometryNodeScaleElements", domain="FACE")
    g.link(sp.outputs[0], se.inputs["Geometry"])
    g.link(g.math("MAXIMUM", g.math("SUBTRACT", 1.0, g.math("MULTIPLY", p, 0.8)), 0.0), se.inputs["Scale"])
    g.link(se.outputs[0], gout.inputs["Geometry"])
    return ng


def to_mesh(obj, thickness=0.0):
    """Replace a text / curve object with a mesh copy (same transform and materials).
    thickness extrudes flat text first, so rigid bodies get a real collision volume."""
    if thickness and obj.type in ("FONT", "CURVE"):
        obj.data.extrude = thickness / 2
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    new = bpy.data.objects.new(obj.name + "_mesh", mesh)
    new.matrix_world = obj.matrix_world
    m._link(new)
    bpy.data.objects.remove(obj)
    if obj in m.CREATED:
        m.CREATED.remove(obj)
    return new


def shatter(obj, keys):
    """keys: [(frame, progress)] — progress 0 intact, ~1 fully blown apart."""
    mod = obj.modifiers.new("GN", "NODES")
    mod.node_group = bpy.data.node_groups.get("Shatter") or shatter_group()
    key_input(obj, "Progress", keys, "LINEAR")
    return obj


# ---------------------------------------------------------------- physics

def rigid_world(gravity=(0.0, -30.0, 0.0), frames=400, start=1):
    """Objects hold their place until `start`, then fall."""
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        with bpy.context.temp_override(scene=scene):
            bpy.ops.rigidbody.world_add()
    scene.gravity = gravity
    scene.use_gravity = True
    rw = scene.rigidbody_world
    rw.point_cache.frame_start = start
    rw.point_cache.frame_end = frames
    rw.substeps_per_frame = 10
    rw.collection = rw.collection or bpy.data.collections.new("RigidBodyWorld")
    return rw


def rigid(obj, kind="ACTIVE", bounce=0.35, friction=0.6, mass=1.0):
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.rigidbody.object_add(type=kind)
    rb = obj.rigid_body
    rb.restitution = bounce
    rb.friction = friction
    rb.mass = mass
    # passive ground pieces are often flat planes: mesh collision keeps them solid
    rb.collision_shape = "MESH" if kind == "PASSIVE" else "CONVEX_HULL"
    rb.collision_margin = 0.04
    return rb


def cloth_ribbon(x0, y0, length, width, color, z=1.0, segs=(48, 6), wind=6.0, frames=400):
    """A ribbon pinned at its left end, flapping in a wind field blowing along +x."""
    nx, ny = segs
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((length * i / nx, width * (j / ny - 0.5), 0))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    obj = m._mesh_obj("ribbon", verts, faces, m.flat(color), (x0, y0, z))
    vg = obj.vertex_groups.new(name="pin")
    vg.add([j * (nx + 1) for j in range(ny + 1)], 1.0, "REPLACE")
    cl = obj.modifiers.new("cloth", "CLOTH")
    cl.settings.vertex_group_mass = "pin"
    cl.settings.quality = 6
    cl.settings.mass = 0.15
    cl.settings.air_damping = 0.4
    cl.point_cache.frame_start = 1
    cl.point_cache.frame_end = frames
    bpy.context.scene.gravity = (0.0, -6.0, 0.0)
    bpy.ops.object.effector_add(type="WIND", location=(x0 - 2, y0, z), rotation=(0, math.radians(90), 0))
    field = bpy.context.active_object
    m.CREATED.append(field)
    field.field.strength = wind
    field.field.noise = 2.0
    return obj


# ---------------------------------------------------------------- compositor

def compositor():
    """Render Layers -> Glare (bloom) -> Lens Distortion (dispersion = RGB split) -> Pixelate
    (glitch) -> Invert (impact frames) -> output. Returns the nodes whose inputs get keyed."""
    scene = bpy.context.scene
    tree = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    scene.compositing_node_group = tree
    _iface(tree, "Image", "OUTPUT", "NodeSocketColor")
    g = G(tree)
    rl = g.node("CompositorNodeRLayers")
    glare = g.node("CompositorNodeGlare")
    for name, val in (("Type", "Bloom"), ("Threshold", 1.0), ("Strength", 0.9), ("Size", 0.6)):
        try:
            sock(glare.inputs, name).default_value = val
        except (KeyError, TypeError, ValueError) as e:
            print("glare", name, e)
    g.link(rl.outputs["Image"], sock(glare.inputs, "Image"))
    lens = g.node("CompositorNodeLensdist")
    g.link(glare.outputs[0], sock(lens.inputs, "Image"))
    sock(lens.inputs, "Dispersion").default_value = 0.0
    pix = g.node("CompositorNodePixelate")
    g.link(lens.outputs[0], pix.inputs[0])
    pix_size = next((s for s in pix.inputs if s.name == "Size"), None)
    if pix_size is not None:
        pix_size.default_value = 1
    inv = g.node("CompositorNodeInvert")
    g.link(pix.outputs[0], sock(inv.inputs, "Color"))
    sock(inv.inputs, "Factor").default_value = 0.0
    out = g.node("NodeGroupOutput")
    g.link(inv.outputs[0], out.inputs[0])
    return {"tree": tree, "lens": lens, "pix": pix, "inv": inv, "pix_size": pix_size}


def key_socket(tree, sock_, keys, interp="CONSTANT"):
    for f, v in keys:
        sock_.default_value = v
        sock_.keyframe_insert("default_value", frame=f)
    path = sock_.path_from_id("default_value")
    set_interp(tree, path, interp)


def box(x0, x1, y0, y1, z0, z1, color, mat=None):
    """Axis-aligned box (e.g. ground for rigid bodies falling along -Y)."""
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    obj = m._mesh_obj("box", v, faces, mat or m.flat(color))
    obj.data.update()
    return obj
