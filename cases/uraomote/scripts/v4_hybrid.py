"""The hybrid print: the 2D picture and the 3D hall set into each other, instead of a picture hung in a hall.
The flat planes of a picture, its sky, its water, its mirrors, are the hall's own surfaces: through her window a
sky that sits behind the paper and shifts as the camera moves, water that mirrors the hall's lamps and beams and
takes a ripple, mirror glass that shows the hall. The dimensional parts, her hair, face and clothes, rise off the
paper as a relief from the picture's depth map, so the light rakes them, the camera finds parallax, and 3D things
(ink, rain, ripples) can sit at their depth: anchor() gives a part's place in the world.

    blender -b --factory-startup -P cases/uraomote/scripts/v4_hybrid.py -- [out_dir] [shot ...]
    shots: kv_dawn kv_side_dawn | u1_rose u1_side_rose      (dawn and rose in separate runs)
    RELIEF=0.14 how far the nearest part of a picture stands off the paper, metres

Needs art/v4/maps/<name>_{depth,flat,parts}.png from scripts/maps.py. animatic_v4.py hangs every print with
make_print(); the stills here put the KV (row 0) and U1 (the row-1 print nearest the aisle) in a plain hall.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import cyc  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import v4_hall as V  # noqa: E402

MAPS = os.path.join(V.ART, "maps")
RELIEF = float(os.environ.get("RELIEF", 0.14))
SKY_DIST, SKY_H = 2.5, 7.0                  # the sky behind a window: a 16:9 picture this far behind the paper, this tall
SKY_TEX = []                                # every print's sky portal image node: a shot swaps the sky in all at once
SKY_EM = []                                 # and their emission nodes: the sky in a picture as bright as the hall's sky
RINGS = {}                                  # print name -> the ring in its water (x, y, r, a values), for ripples
STAINS = {}                                 # print name -> the rose stain soaking into it (u, v, r values)
ROSE = "#F0285A"
_MAPS = {}


def _load(path):
    """An image's pixels as (H, W, 4) floats 0..1, rows from the bottom, read as data (no colour transform)."""
    if path not in _MAPS:
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        w, h = img.size
        _MAPS[path] = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return _MAPS[path]


def has_maps(name):
    return os.path.exists(os.path.join(MAPS, f"{name}_depth.png"))


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


def _layout(w, h, size=None):
    """How V._picture lays a w x h picture on a sheet of `size`: the border (mu, mv), the picture rectangle's size
    (rw, rh) in sheet UVs and the crop (s) of the picture inside it."""
    W, Hh = size or (V.SHEET_W, V.SHEET_H)
    mu, mv = V.MARGIN / W, 1.4 * V.MARGIN / Hh
    rw, rh = 1 - 2 * mu, 1 - mv - V.MARGIN / Hh
    a, target = w / h, (W * rw) / (Hh * rh)
    s = (target / a, 1.0) if a > target else (1.0, a / target)
    return mu, mv, rw, rh, s


def size_of(ob):
    """A sheet's (width, height), as V.sheet remembered them."""
    return ob.get("sheet_w", V.SHEET_W), ob.get("sheet_h", V.SHEET_H)


def depth_relief(name, amount=RELIEF, size=None):
    """(u, v) -> dx for V.sheet from the picture's depth map: zero on the paper border and where the picture is a
    flat plane (its sky, water, mirrors stay in the paper), rising towards the viewer (-X) elsewhere."""
    d = _load(os.path.join(MAPS, f"{name}_depth.png"))[..., 0]
    flat = _load(os.path.join(MAPS, f"{name}_flat.png"))[..., :3].max(axis=2)
    d = _soften(_blocks(d * (1.0 - flat), 8))
    h, w = d.shape
    mu, mv, rw, rh, s = _layout(w, h, size)

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
    d = _load(os.path.join(MAPS, f"{name}_depth.png"))[..., 0]
    h, w = d.shape
    W, Hh = size_of(ob)
    mu, mv, rw, rh, s = _layout(w, h, (W, Hh))
    u = (pu - (1 - s[0]) / 2) * rw / s[0] + mu
    v = (pv - (1 - s[1]) / 2) * rh / s[1] + mv
    amount = ob.get("relief_amount", RELIEF)
    x = -amount * float(d[min(h - 1, int(pv * h)), min(w - 1, int(pu * w))]) - lift
    bpy.context.view_layer.update()
    return ob.matrix_world @ Vector((x, W / 2 - u * W, (v - 1) * Hh))


def anchor(ob, name, part=0, lift=0.03):
    """Where one of her parts is (0 hair, 1 face and skin, 2 clothes) on the print `ob` carrying picture `name`:
    its centroid as a world point just in front of the relief, its extent in metres, and its (pu, pv)."""
    mk = _load(os.path.join(MAPS, f"{name}_parts.png"))[..., part]
    h, w = mk.shape
    ys, xs = np.nonzero(mk > 0.5)
    if len(xs) == 0:
        ys, xs = np.array([h // 2]), np.array([w // 2])
    pu, pv = (xs.mean() + 0.5) / w, (ys.mean() + 0.5) / h
    W, Hh = size_of(ob)
    mu, mv, rw, rh, s = _layout(w, h, (W, Hh))
    size = ((xs.max() - xs.min() + 1) / w * rw / s[0] * W, (ys.max() - ys.min() + 1) / h * rh / s[1] * Hh)
    return dict(point=picture_point(ob, name, pu, pv, lift), size=size, uv=(pu, pv))


def _value(nt, v=0.0):
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


def _sky_portal(nt, sky, picture, size=None):
    """The sky behind her window: a picture SKY_DIST behind the paper, found where the eye's ray through the paper
    meets it, so it moves against the window as the camera moves; the picture's own dark lines (the window's
    frame) stay over it; and the hall reflected in the glass."""
    Hh = (size or (V.SHEET_W, V.SHEET_H))[1]
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
    tex.image = bpy.data.images.load(os.path.join(V.ART, f"{sky}_00001_.png"), check_existing=True)
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
    """Her water is the hall's: near-black, a mirror with a slow ripple, so the hall's lamps and beams lie on it;
    and one ring at a time, set per frame through RINGS[name] (its centre in the sheet's y, z, radius, height)."""
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
    ring = {k: _value(nt) for k in ("y", "z", "r", "a")}
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
    st = {k: _value(nt, -1.0 if k == "r" else 0.0) for k in ("u", "v", "r")}
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
    img = bpy.data.images.load(os.path.join(V.ART, f"{name}_00001_.png"), check_existing=True)
    mu, mv, rw, rh, s = _layout(*img.size, size_of(ob))
    return (pu - (1 - s[0]) / 2) * rw / s[0] + mu, (pv - (1 - s[1]) / 2) * rh / s[1] + mv


def stain(name, u, v, r):
    st = STAINS.get(name)
    if st is None:
        return
    for k, val in (("u", u), ("v", v), ("r", r)):
        _put(st[k], val)


def hybrid_mat(name, front, back, sky, size=None):
    """The print's material with its flat planes swapped for the hall's: by the facing picture's flat map, G water,
    B mirror, R the sky behind the window."""
    mat = V.print_mat(front, back, size=size)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    chain = out.inputs["Surface"].links[0].from_socket
    flats = []
    for pic in (front, back):
        path = os.path.join(MAPS, f"{pic}_flat.png")
        bpy.data.images.load(path, check_existing=True).colorspace_settings.name = "Non-Color"
        flats.append(V._picture(nt, pic, V.MARGIN, file=path, size=size)[0])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    flat = kit._mix_rgba(nt, geo.outputs["Backfacing"], flats[0], flats[1])
    picture = kit._mix_rgba(nt, geo.outputs["Backfacing"], V._picture(nt, front, V.MARGIN, size=size)[0],
                            V._picture(nt, back, V.MARGIN, size=size)[0])
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


LANDSCAPE = (V.SHEET_H, V.SHEET_W)          # a sheet turned on its side, for a picture wider than tall


def make_print(name, x, y, front, back, seed, sky="v4_s1_211", top=V.TOP, amount=None, fit=False):
    """V.sheet's hybrid twin: the print `name` at (x, y) with the pictures' planes as the hall's and the front
    picture's relief (the KV at the full RELIEF, the others a little flatter). With `fit`, a wide picture gets a
    sheet turned on its side instead of being cropped to the usual one. Without maps, a plain print."""
    size = None
    if fit:
        img = bpy.data.images.load(os.path.join(V.ART, f"{front}_00001_.png"), check_existing=True)
        size = LANDSCAPE if img.size[0] > img.size[1] else None
        if size == LANDSCAPE and top == V.TOP:
            top = V.TOP - 0.9                           # hung lower, so its middle is where a tall print's is
    if not (has_maps(front) and has_maps(back)):
        return V.sheet(name, x, y, V.print_mat(front, back, size=size), seed, top=top, size=size)
    amount = amount if amount is not None else (RELIEF if front == V.KV[0] else 0.65 * RELIEF)
    grid = (126, 72) if size == LANDSCAPE else (72, 126)
    ob = V.sheet(name, x, y, hybrid_mat(name, front, back, sky, size), seed, top=top, grid=grid,
                 relief=depth_relief(front, amount, size), size=size)
    ob["relief_amount"] = amount
    return ob


def _put(sock, v):
    if sock.default_value != v:                 # setting a value again makes Cycles rebuild the material
        sock.default_value = v


def ring(name, y, z, r, a):
    """The ripple in print `name`'s water: centre (y, z) in the sheet's own coordinates (z down from the top edge),
    radius and height; a = 0 puts it away."""
    rg = RINGS.get(name)
    if rg is None:
        return
    for k, v in (("y", y), ("z", z), ("r", r), ("a", a)):
        _put(rg[k], v)


def main():
    out, shots = cyc.args(os.path.join(C.RENDERS, "v4_hybrid"), ["kv_dawn", "kv_side_dawn"])
    dawn = all(s.endswith("dawn") for s in shots)
    if not dawn and any(s.endswith("dawn") for s in shots):
        sys.exit("dawn and rose shots need separate runs (the lights differ)")
    m.reset()
    cyc.cycles(bounces=8)
    cyc.world((0.0004, 0.0004, 0.0008))
    V.hall(dawn)
    if not dawn:
        V.LAMPS = 1.0                                   # lamps on at night: something for her water to mirror
    V.lamps()
    V.pipes()
    sky = "v4_s1_211" if dawn else "v4_s3_211"
    prints = V.hang(make=lambda name, x, y, front, back, seed: make_print(
        name, x, y, ("v4_u1_211" if name == "print_1_-1.6" else front), back, seed, sky))
    kv, u1 = next(p for p in prints if p.name == "print_0_+0.0"), next(p for p in prints if p.name == "print_1_-1.6")
    if dawn:
        V.dawn_light()
    else:
        V.rose_light(prints)
    V.haze(dawn)
    cyc.post(bloom=0.35 if dawn else 0.6, threshold=1.0 if dawn else 0.75)
    hair = anchor(u1, "v4_u1_211", 0)
    ring(u1.name, hair["point"].y - u1.location.y, -1.6, 0.5, 0.6)              # one ring below her hair
    kvc = (kv.location.x, 0.0, 3.4)
    u1c = (u1.location.x, u1.location.y, 3.2)
    cams = {"kv_dawn": cyc.camera("kv_dawn", (-4.2, -0.9, 3.3), kvc, 35, 4.0),
            "kv_side_dawn": cyc.camera("kv_side_dawn", (-1.6, -4.2, 3.4), (kvc[0], -0.3, 3.4), 40, 4.0),
            "u1_rose": cyc.camera("u1_rose", (1.2, -2.6, 3.0), u1c, 35, 4.0),
            "u1_side_rose": cyc.camera("u1_side_rose", (3.2, -5.2, 3.0), (u1c[0], u1c[1] - 0.3, 3.2), 40, 4.0)}
    focus = {"kv_dawn": kvc, "kv_side_dawn": kvc, "u1_rose": u1c, "u1_side_rose": u1c}
    cams = {k: v for k, v in cams.items() if k in shots}
    cyc.render_shots(cams, shots, out, "hybrid", focus={k: focus[k] for k in cams},
                     samples={k: V.SAMPLES or (128 if dawn else 160) for k in cams},
                     exposure={k: (1.0 if dawn else 0.3) for k in cams},
                     blend="hybrid_dawn.blend" if dawn else "hybrid_rose.blend")


if __name__ == "__main__":
    main()
