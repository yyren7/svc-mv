"""The hybrid print: the 2D picture and the 3D scene set into each other, instead of a picture hung in a room.

The flat planes of a picture, its sky, its water, its mirrors, are the scene's own surfaces: through her window a
sky that sits behind the paper and shifts as the camera moves, water that mirrors the scene's lamps and beams and
takes a ripple, mirror glass that shows the room. The dimensional parts, her hair, face and clothes, rise off the
paper as a relief from the picture's depth map, so the light rakes them, the camera finds parallax, and 3D things
(ink, rain, ripples, strands of hair) can sit at their depth: anchor() gives a part's place in the world.

Needs, per picture, the maps that scripts/maps.py makes: <name>_depth.png, <name>_flat.png (R sky or window,
G water, B mirror) and <name>_parts.png (R hair, G face and skin, B clothes), in MAPS (by default the `maps/`
folder beside the pictures). A case sets `hybrid.SKY` (the sky picture its windows look out on) and `hybrid.HERO`
(the pictures that get the full RELIEF; the others a little flatter) before hanging prints; RELIEF=0.14 (metres)
in the environment is how far the nearest part of a picture stands off the paper.
"""
import os

import bpy
import numpy as np
from mathutils import Vector

import cyc
import kit
import mvlib as m
import paper as P

MAPS = None                                 # the maps folder; None: <paper.ART>/maps
FIGURES = None                              # the cut-outs folder (scripts/figures.py); None: <paper.ART>/figures
SKY = None                                  # the sky picture behind every window, unless make_print is given one
HERO = ()                                   # pictures (by name) with the full relief
RELIEF = float(os.environ.get("RELIEF", 0.14))
SKY_DIST, SKY_H = 2.5, 7.0                  # the sky behind a window: a 16:9 picture this far behind the paper, this tall
SKY_TEX = []                                # every print's sky portal image node: a shot swaps the sky in all at once
SKY_EM = []                                 # and their emission nodes: the sky in a picture as bright as the room's sky
RINGS = {}                                  # print name -> the ring in its water (x, y, r, a values), for ripples
STAINS = {}                                 # print name -> the rose stain soaking into it (u, v, r values)
_MAPS = {}


def map_path(name, kind):
    """The `kind` (depth, flat, parts) map of picture `name`."""
    return os.path.join(MAPS or os.path.join(P.ART, "maps"), f"{name}_{kind}.png")


def load(path):
    """An image's pixels as (H, W, 4) floats 0..1, rows from the bottom, read as data (no colour transform)."""
    if path not in _MAPS:
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        w, h = img.size
        _MAPS[path] = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return _MAPS[path]


def has_maps(name):
    return os.path.exists(map_path(name, "depth"))


def margin_of(ob):
    """A print's bare border, as make_print remembered it (paper.MARGIN unless it was made full-bleed)."""
    return ob.get("margin", P.MARGIN)


def _blocks(a, n):
    """`a` averaged over n x n blocks: the map at the grid's coarseness, without its pixel noise."""
    h, w = (a.shape[0] // n) * n, (a.shape[1] // n) * n
    return a[:h, :w].reshape(h // n, n, w // n, n).mean(axis=(1, 3))


def _soften(a, passes=2):
    """A 3 x 3 mean, `passes` times: the relief's edges slope over a few grid cells instead of standing as a cliff
    of stretched paper."""
    for _ in range(passes):
        p = np.pad(a, 1, mode="edge")
        a = sum(p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
    return a


def depth_relief(name, amount=RELIEF, size=None, margin=None):
    """(u, v) -> dx for paper.sheet from the picture's depth map: zero on the paper border and where the picture is
    a flat plane (its sky, water, mirrors stay in the paper), rising towards the viewer (-X) elsewhere."""
    d = load(map_path(name, "depth"))[..., 0]
    flat = load(map_path(name, "flat"))[..., :3].max(axis=2)
    # the depth's grain (cloth folds, the model's noise) would mottle the paper under a raking lamp: smoothed hard,
    # then her silhouette put back as a step from the parts map, so the relief is a bas-relief, not a bumpy sheet
    d = _soften(_blocks(d * (1.0 - flat), 8), passes=8)
    parts = map_path(name, "parts")
    if os.path.exists(parts):
        fig = _soften(_blocks(load(parts)[..., :3].max(axis=2), 8), passes=1)
        if fig.shape != d.shape:
            fig = fig[(np.arange(d.shape[0]) * fig.shape[0] // d.shape[0])[:, None],
                      (np.arange(d.shape[1]) * fig.shape[1] // d.shape[1])[None, :]]
        d = d * (0.3 + 0.7 * fig)
    h, w = d.shape
    mu, mv, rw, rh, s = P.layout(w, h, size, margin)

    def relief(u, v):
        pu = u * s[0] / rw - mu * s[0] / rw + (1 - s[0]) / 2
        pv = v * s[1] / rh - mv * s[1] / rh + (1 - s[1]) / 2
        if not (0.0 <= pu < 1.0 and 0.0 <= pv < 1.0):
            return 0.0
        return -amount * float(d[int(pv * h), int(pu * w)])
    relief.amount = amount
    return relief


def picture_point(ob, name, pu, pv, lift=0.0):
    """The world point of the picture's (pu, pv) (0..1 from its bottom left) on the print `ob`, on the relief
    and `lift` metres in front of it."""
    d = load(map_path(name, "depth"))[..., 0]
    h, w = d.shape
    W, Hh = P.size_of(ob)
    mu, mv, rw, rh, s = P.layout(w, h, (W, Hh), margin_of(ob))
    u = (pu - (1 - s[0]) / 2) * rw / s[0] + mu
    v = (pv - (1 - s[1]) / 2) * rh / s[1] + mv
    amount = ob.get("relief_amount", RELIEF)
    x = -amount * float(d[min(h - 1, int(pv * h)), min(w - 1, int(pu * w))]) - lift
    bpy.context.view_layer.update()
    return ob.matrix_world @ Vector((x, W / 2 - u * W, (v - 1) * Hh))


def anchor(ob, name, part=0, lift=0.03):
    """Where one of her parts is (0 hair, 1 face and skin, 2 clothes) on the print `ob` carrying picture `name`:
    its centroid as a world point just in front of the relief, its extent in metres, and its (pu, pv)."""
    mk = load(map_path(name, "parts"))[..., part]
    h, w = mk.shape
    ys, xs = np.nonzero(mk > 0.5)
    if len(xs) == 0:
        ys, xs = np.array([h // 2]), np.array([w // 2])
    pu, pv = (xs.mean() + 0.5) / w, (ys.mean() + 0.5) / h
    W, Hh = P.size_of(ob)
    mu, mv, rw, rh, s = P.layout(w, h, (W, Hh), margin_of(ob))
    size = ((xs.max() - xs.min() + 1) / w * rw / s[0] * W, (ys.max() - ys.min() + 1) / h * rh / s[1] * Hh)
    return dict(point=picture_point(ob, name, pu, pv, lift), size=size, uv=(pu, pv))


def _sky_portal(nt, sky, picture, size=None):
    """The sky behind her window: a picture SKY_DIST behind the paper, found where the eye's ray through the paper
    meets it, so it moves against the window as the camera moves; the picture's own dark lines (the window's
    frame) stay over it; and the room reflected in the glass."""
    Hh = (size or (P.SHEET_W, P.SHEET_H))[1]
    g = kit.G(nt)
    geo = g.node("ShaderNodeNewGeometry")
    into = g.vmath("SCALE", geo.outputs["Incoming"], -1.0)          # from the eye into the picture, world
    local = g.node("ShaderNodeVectorTransform", vector_type="VECTOR", convert_from="WORLD", convert_to="OBJECT")
    g.link(into, local.inputs[0])
    wx = g.node("ShaderNodeSeparateXYZ")
    g.link(local.outputs[0], wx.inputs[0])
    t = g.math("DIVIDE", SKY_DIST, g.math("ABSOLUTE", wx.outputs["X"]))   # to the plane behind whichever face
    tc = g.node("ShaderNodeTexCoord")
    hit = g.vmath("ADD", tc.outputs["Object"], g.vmath("SCALE", local.outputs[0], t))
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(hit, sep.inputs[0])
    yz = g.node("ShaderNodeCombineXYZ")
    g.link(sep.outputs["Y"], yz.inputs["X"])
    g.link(sep.outputs["Z"], yz.inputs["Y"])
    sky_w = SKY_H * 16 / 9
    mp = g.node("ShaderNodeMapping")                                 # the picture's right is -Y; it is centred on the sheet
    mp.inputs["Scale"].default_value = (-1.0 / sky_w, 1.0 / SKY_H, 1.0)
    mp.inputs["Location"].default_value = (0.5, 0.5 + (Hh / 2) / SKY_H, 0.0)
    g.link(yz.outputs[0], mp.inputs["Vector"])
    tex = g.node("ShaderNodeTexImage", extension="CLIP")
    tex.image = P.image(sky)
    g.link(mp.outputs[0], tex.inputs["Vector"])
    SKY_TEX.append(tex)
    # beyond the sky picture, and seen at a grazing angle (the ray runs far along the plane), the window goes dark
    graze = g.node("ShaderNodeMapRange", {"From Min": 0.12, "From Max": 0.35, "To Min": 0.0, "To Max": 1.0})
    g.link(g.math("ABSOLUTE", wx.outputs["X"]), graze.inputs["Value"])
    seen = kit._mix_rgba(nt, g.math("MULTIPLY", tex.outputs["Alpha"], graze.outputs["Result"]),
                         (0.02, 0.025, 0.04, 1.0), tex.outputs["Color"])
    lum = g.node("ShaderNodeRGBToBW")
    g.link(picture, lum.inputs[0])
    frame = g.node("ShaderNodeMapRange", {"From Min": 0.3, "From Max": 0.7, "To Min": 0.1, "To Max": 1.0})
    g.link(lum.outputs[0], frame.inputs["Value"])
    lit = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    kit.sock(lit.inputs, "Factor", "VALUE").default_value = 1.0
    g.link(seen, kit.sock(lit.inputs, "A", "RGBA"))
    g.link(frame.outputs["Result"], kit.sock(lit.inputs, "B", "RGBA"))
    em = g.node("ShaderNodeEmission", {"Strength": 1.6})
    g.link(kit.sock(lit.outputs, "Result", "RGBA"), em.inputs["Color"])
    SKY_EM.append(em)
    glass = g.node("ShaderNodeBsdfGlossy", {"Roughness": 0.03})
    mix = g.node("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.15
    g.link(em.outputs[0], mix.inputs[1])
    g.link(glass.outputs[0], mix.inputs[2])
    return mix.outputs[0]


def _water(nt, name):
    """Her water is the room's: near-black, a mirror with a slow ripple, so the lamps and beams lie on it; and one
    ring at a time, set per frame through RINGS[name] (its centre in the sheet's y, z, radius, height)."""
    g = kit.G(nt)
    bsdf = g.node("ShaderNodeBsdfPrincipled", {"Base Color": (0.008, 0.009, 0.014, 1.0), "Roughness": 0.12,
                                               "Specular IOR Level": 0.5})
    tc = g.node("ShaderNodeTexCoord")
    nz = g.node("ShaderNodeTexNoise", {"Scale": 5.0, "Detail": 3.0})
    g.link(tc.outputs["Object"], nz.inputs["Vector"])
    bump = g.node("ShaderNodeBump", {"Strength": 0.5, "Distance": 0.002})
    g.link(nz.outputs["Fac"], bump.inputs["Height"])
    sep = g.node("ShaderNodeSeparateXYZ")
    g.link(tc.outputs["Object"], sep.inputs[0])
    ring = {k: kit.value(nt) for k in ("y", "z", "r", "a")}
    dy, dz = g.math("SUBTRACT", sep.outputs["Y"], ring["y"]), g.math("SUBTRACT", sep.outputs["Z"], ring["z"])
    e = g.math("SUBTRACT", g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dy, dy), g.math("MULTIPLY", dz, dz))),
               ring["r"])
    wave = g.math("SINE", g.math("MULTIPLY", e, 2 * 3.14159265 / 0.22))
    env = g.math("EXPONENT", g.math("MULTIPLY", g.math("MULTIPLY", e, e), -1 / 0.15 ** 2))
    rb = g.node("ShaderNodeBump", {"Strength": 1.0, "Distance": 0.02})
    g.link(g.math("MULTIPLY", g.math("MULTIPLY", wave, env), ring["a"]), rb.inputs["Height"])
    g.link(bump.outputs["Normal"], rb.inputs["Normal"])
    g.link(rb.outputs["Normal"], bsdf.inputs["Normal"])
    RINGS[name] = ring
    return bsdf.outputs[0]


def _mirror(nt):
    g = nt.nodes.new("ShaderNodeBsdfGlossy")
    g.inputs["Roughness"].default_value = 0.0
    g.inputs["Color"].default_value = (0.85, 0.87, 0.9, 1.0)
    return g.outputs[0]


def _stain(nt, name):
    """Rose ink soaking into the paper: a soft disc on the sheet's UVs that tints the picture, set per frame
    through STAINS[name] (centre u, v and radius; a radius below 0 is none)."""
    g = kit.G(nt)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = bsdf.inputs["Base Color"].links[0].from_socket
    st = {k: kit.value(nt, -1.0 if k == "r" else 0.0) for k in ("u", "v", "r")}
    uv = g.node("ShaderNodeTexCoord")
    centre = g.node("ShaderNodeCombineXYZ")
    g.link(st["u"], centre.inputs["X"])
    g.link(st["v"], centre.inputs["Y"])
    # ink soaks along the fibre, so the edge is ragged (noise moves the distance) and darker than the middle,
    # as a wet stain dries: a wine, not a glowing pink
    nz = g.node("ShaderNodeTexNoise", {"Scale": 26.0, "Detail": 5.0, "Roughness": 0.7})
    g.link(uv.outputs["UV"], nz.inputs["Vector"])
    d = g.math("ADD", g.vmath("DISTANCE", uv.outputs["UV"], centre.outputs[0]),
               g.math("MULTIPLY", g.math("SUBTRACT", nz.outputs["Fac"], 0.5), 0.05))
    edge = g.node("ShaderNodeMapRange", {"To Min": 0.9, "To Max": 0.0}, interpolation_type="SMOOTHSTEP")
    g.link(d, edge.inputs["Value"])
    g.link(g.math("SUBTRACT", st["r"], 0.03), edge.inputs["From Min"])
    g.link(g.math("ADD", st["r"], 0.03), edge.inputs["From Max"])
    rim = g.node("ShaderNodeMapRange", {"From Min": 0.0, "From Max": 0.025, "To Min": 1.0, "To Max": 0.55},
                 interpolation_type="SMOOTHSTEP")
    g.link(g.math("ABSOLUTE", g.math("SUBTRACT", d, st["r"])), rim.inputs["Value"])
    inked = g.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    kit.sock(inked.inputs, "Factor", "VALUE").default_value = 1.0
    g.link(src, kit.sock(inked.inputs, "A", "RGBA"))
    wine = g.node("ShaderNodeMix", data_type="RGBA")
    g.link(rim.outputs["Result"], kit.sock(wine.inputs, "Factor", "VALUE"))
    kit.sock(wine.inputs, "A", "RGBA").default_value = m.srgb("#B0405C")      # the stain's middle, thinned
    kit.sock(wine.inputs, "B", "RGBA").default_value = m.srgb("#4A0A20")      # its rim, where the pigment gathers
    g.link(kit.sock(wine.outputs, "Result", "RGBA"), kit.sock(inked.inputs, "B", "RGBA"))
    col = kit._mix_rgba(nt, g.math("MULTIPLY", edge.outputs["Result"], g.math("GREATER_THAN", st["r"], 0.0)), src,
                        kit.sock(inked.outputs, "Result", "RGBA"))
    nt.links.new(col, bsdf.inputs["Base Color"])
    STAINS[name] = st


def sheet_uv(ob, name, pu, pv):
    """The sheet UV under the picture `name`'s point (pu, pv) on the print `ob`."""
    img = P.image(name)
    mu, mv, rw, rh, s = P.layout(*img.size, P.size_of(ob), margin_of(ob))
    return (pu - (1 - s[0]) / 2) * rw / s[0] + mu, (pv - (1 - s[1]) / 2) * rh / s[1] + mv


def stain(name, u, v, r):
    """The stain on print `name`: centre (u, v) in sheet UVs and radius; r < 0 is none."""
    st = STAINS.get(name)
    if st is None:
        return
    for k, val in (("u", u), ("v", v), ("r", r)):
        cyc.put(st[k], val)


def ring(name, y, z, r, a):
    """The ripple in print `name`'s water: centre (y, z) in the sheet's own coordinates (z down from the top edge),
    radius and height; a = 0 puts it away."""
    rg = RINGS.get(name)
    if rg is None:
        return
    for k, v in (("y", y), ("z", z), ("r", r), ("a", a)):
        cyc.put(rg[k], v)


def hybrid_mat(name, front, back, sky, size=None, margin=None):
    """The print's material with its flat planes swapped for the room's: by the facing picture's flat map, G water,
    B mirror, R the sky behind the window. `margin` as paper.print_mat's (0: full bleed)."""
    margin = P.MARGIN if margin is None else margin
    mat = P.print_mat(front, back, size=size, margin=margin)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    chain = out.inputs["Surface"].links[0].from_socket
    flats = []
    for pic in (front, back):
        path = map_path(pic, "flat")
        bpy.data.images.load(path, check_existing=True).colorspace_settings.name = "Non-Color"
        flats.append(P.picture(nt, pic, margin, file=path, size=size, alpha=True)[0])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    flat = kit._mix_rgba(nt, geo.outputs["Backfacing"], flats[0], flats[1])
    picture = kit._mix_rgba(nt, geo.outputs["Backfacing"], P.picture(nt, front, margin, size=size, alpha=True)[0],
                            P.picture(nt, back, margin, size=size, alpha=True)[0])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(flat, sep.inputs[0])
    _stain(nt, name)
    for fac, shader in ((sep.outputs["Green"], _water(nt, name)), (sep.outputs["Blue"], _mirror(nt)),
                        (sep.outputs["Red"], _sky_portal(nt, sky, picture, size))):
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(fac, mix.inputs["Fac"])
        nt.links.new(chain, mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        chain = mix.outputs[0]
    nt.links.new(chain, out.inputs["Surface"])
    return mat


def figure_path(name):
    """scripts/figures.py's cut-out of her: <art>/figures/<name>_figure.png (L, 255 where she is)."""
    return os.path.join(FIGURES or os.path.join(P.ART, "figures"), f"{name}_figure.png")


def figure_box(name):
    """Where she is in picture `name`: (u0, v0, u1, v1) in picture coordinates, 0..1 from the bottom left."""
    a = load(figure_path(name))[..., 0]
    h, w = a.shape
    ys, xs = np.nonzero(a > 0.5)
    return (xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h)


def world_mat(name, picture, size=None, cutout=False, sky=True, water=True, emission=None):
    """The print's material for a picture set into the world itself: its flat planes cut through to whatever is
    behind the paper (R sky or window and G water become transparent, so the world's real sky and water show in
    them; B mirror stays mirror glass), the paper's back bare; with `cutout`, everything that is not her (the
    figure from scripts/figures.py) is transparent too, and the sheet is a 2D figure standing in a 3D place. The
    ink stain (STAINS) is on it as on a hybrid print. With `emission` (a strength) the picture is lit by itself
    instead of being paper: the version of her that only the water's mirror sees."""
    if emission is None:
        mat = P.print_mat(picture, None, size=size, margin=0.0)
        nt = mat.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        chain = out.inputs["Surface"].links[0].from_socket
        _stain(nt, name)
    else:
        mat, nt, out = P.nodes(f"lit_{picture}")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = emission
        nt.links.new(P.picture(nt, picture, 0.0, size=size, alpha=True)[0], em.inputs["Color"])
        chain = em.outputs[0]
    g = kit.G(nt)
    flat = map_path(picture, "flat")
    bpy.data.images.load(flat, check_existing=True).colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(P.picture(nt, picture, 0.0, file=flat, size=size, alpha=True)[0], sep.inputs[0])
    clear = g.node("ShaderNodeBsdfTransparent")
    planes = []
    if sky:
        planes.append((sep.outputs["Red"], clear.outputs[0]))
    if water:
        planes.append((sep.outputs["Green"], clear.outputs[0]))
    planes.append((sep.outputs["Blue"], _mirror(nt)))
    for fac, shader in planes:
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(fac, mix.inputs["Fac"])
        nt.links.new(chain, mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        chain = mix.outputs[0]
    if cutout:
        fig = figure_path(picture)
        bpy.data.images.load(fig, check_existing=True).colorspace_settings.name = "Non-Color"
        her = g.node("ShaderNodeRGBToBW")
        nt.links.new(P.picture(nt, picture, 0.0, file=fig, size=size, alpha=True)[0], her.inputs[0])
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(her.outputs[0], mix.inputs["Fac"])
        nt.links.new(clear.outputs[0], mix.inputs[1])
        nt.links.new(chain, mix.inputs[2])
        chain = mix.outputs[0]
    nt.links.new(chain, out.inputs["Surface"])
    return mat


def make_figure(name, picture, x, y, height=1.62, bottom=0.01, seed=0, amount=None, grid=None, emission=None,
                flat=0.3):
    """Her cut out of `picture` as a 2D figure standing in the world at (x, y): a sheet the picture's own aspect,
    sized so she is `height` metres tall with her feet `bottom` metres over the floor, her figure in relief, the
    rest of the paper transparent, no clips and nearly flat. Returns the sheet (origin: the middle of its top
    edge; it remembers the picture's size, margin 0 and the picture's name). `emission`: see world_mat."""
    img = P.image(picture)
    w, h = img.size
    u0, v0, u1, v1 = figure_box(picture)
    Hh = height / max(v1 - v0, 1e-3)
    size = (Hh * w / h, Hh)
    amount = amount if amount is not None else (RELIEF if picture in HERO else 0.65 * RELIEF)
    grid = grid or ((72, 126) if h >= w else (126, 72))
    ob = P.sheet(name, x, y, world_mat(name, picture, size, cutout=True, emission=emission), seed,
                 top=bottom + Hh * (1 - v0), grid=grid, relief=depth_relief(picture, amount, size, 0.0), size=size,
                 clips=False, flat=flat)
    ob["relief_amount"], ob["margin"], ob["picture"] = amount, 0.0, picture
    return ob


def landscape():
    """A sheet turned on its side, for a picture wider than tall."""
    return (P.SHEET_H, P.SHEET_W)


def make_print(name, x, y, front, back, seed, sky=None, top=None, amount=None, fit=False, margin=None):
    """paper.sheet's hybrid twin: the print `name` at (x, y) with the pictures' planes as the room's and the front
    picture's relief (a HERO picture at the full RELIEF, the others a little flatter). With `fit`, a wide picture
    gets a sheet turned on its side instead of being cropped to the usual one. `margin` 0 is a full-bleed print
    (a dark picture's white border under a lamp is a bar of light). Without maps, a plain print."""
    sky = sky or SKY
    margin = P.MARGIN if margin is None else margin
    size = None
    if fit:
        img = P.image(front)
        size = landscape() if img.size[0] > img.size[1] else None
        if size == landscape() and top is None:
            top = P.TOP - 0.9                           # hung lower, so its middle is where a tall print's is
    if not (has_maps(front) and has_maps(back)):
        ob = P.sheet(name, x, y, P.print_mat(front, back, size=size, margin=margin), seed, top=top, size=size)
        ob["margin"] = margin
        return ob
    amount = amount if amount is not None else (RELIEF if front in HERO else 0.65 * RELIEF)
    grid = (126, 72) if size == landscape() else (72, 126)
    ob = P.sheet(name, x, y, hybrid_mat(name, front, back, sky, size, margin), seed, top=top, grid=grid,
                 relief=depth_relief(front, amount, size, margin), size=size)
    ob["relief_amount"], ob["margin"] = amount, margin
    return ob
