"""The hybrid print: the 2D picture and the 3D hall set into each other, instead of a picture hung in a hall.
The flat planes of a picture, its sky, its water, its mirrors, are the hall's own surfaces: through her window a
sky that sits behind the paper and shifts as the camera moves, water that mirrors the hall's lamps and beams,
mirror glass that shows the hall. The dimensional parts, her hair, face and clothes, rise off the paper as a
relief from the picture's depth map, so the light rakes them, the camera finds parallax, and 3D things can sit at
their depth. Stills in the hall, to judge the idea.

    blender -b --factory-startup -P cases/uraomote/scripts/v4_hybrid.py -- [out_dir] [shot ...]
    shots: kv_dawn kv_side_dawn | u1_rose u1_side_rose      (dawn and rose in separate runs)
    RELIEF=0.18 how far the nearest part of a picture stands off the paper, metres

Needs art/v4/maps/<name>_{depth,flat}.png from scripts/maps.py. The KV (row 0) and the row-1 print nearest the
aisle, which carries U1 (she lies on black water), become hybrids; the other prints stay as they are.
"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402
import cyc  # noqa: E402
import kit  # noqa: E402
import mvlib as m  # noqa: E402
import v4_hall as V  # noqa: E402

MAPS = os.path.join(V.ART, "maps")
RELIEF = float(os.environ.get("RELIEF", 0.14))
SKY_DIST, SKY_H = 2.5, 7.0                  # the sky behind a window: a 16:9 picture this far behind the paper, this tall


def _load(path):
    """An image's pixels as (H, W, 4) floats 0..1, rows from the bottom, read as data (no colour transform)."""
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    return np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)


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


def depth_relief(name, amount=RELIEF):
    """(u, v) -> dx for V.sheet from the picture's depth map: zero on the paper border and where the picture is a
    flat plane (its sky, water, mirrors stay in the paper), rising towards the viewer (-X) elsewhere."""
    d = _load(os.path.join(MAPS, f"{name}_depth.png"))[..., 0]
    flat = _load(os.path.join(MAPS, f"{name}_flat.png"))[..., :3].max(axis=2)
    d = _soften(_blocks(d * (1.0 - flat), 8))
    h, w = d.shape
    mu, mv = V.MARGIN / V.SHEET_W, 1.4 * V.MARGIN / V.SHEET_H           # as V._picture lays the picture out
    rw, rh = 1 - 2 * mu, 1 - mv - V.MARGIN / V.SHEET_H
    a, target = w / h, (V.SHEET_W * rw) / (V.SHEET_H * rh)
    s = (target / a, 1.0) if a > target else (1.0, a / target)

    def relief(u, v):
        pu = u * s[0] / rw - mu * s[0] / rw + (1 - s[0]) / 2
        pv = v * s[1] / rh - mv * s[1] / rh + (1 - s[1]) / 2
        if not (0.0 <= pu < 1.0 and 0.0 <= pv < 1.0):
            return 0.0
        return -amount * float(d[int(pv * h), int(pu * w)])
    return relief


def _sky_portal(nt, sky, picture):
    """The sky behind her window: a picture SKY_DIST behind the paper, found where the eye's ray through the paper
    meets it, so it moves against the window as the camera moves; the picture's own dark lines (the window's
    frame) stay over it; and the hall reflected in the glass."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    into = nt.nodes.new("ShaderNodeVectorMath")                      # from the eye into the picture, world
    into.operation = "SCALE"
    into.inputs["Scale"].default_value = -1.0
    nt.links.new(geo.outputs["Incoming"], into.inputs[0])
    local = nt.nodes.new("ShaderNodeVectorTransform")
    local.vector_type, local.convert_from, local.convert_to = "VECTOR", "WORLD", "OBJECT"
    nt.links.new(into.outputs[0], local.inputs[0])
    wx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(local.outputs[0], wx.inputs[0])
    t = nt.nodes.new("ShaderNodeMath")                               # how far along the ray the sky plane is
    t.operation = "DIVIDE"
    t.inputs[0].default_value = SKY_DIST
    nt.links.new(wx.outputs["X"], t.inputs[1])
    step = nt.nodes.new("ShaderNodeVectorMath")
    step.operation = "SCALE"
    nt.links.new(local.outputs[0], step.inputs[0])
    nt.links.new(t.outputs[0], step.inputs["Scale"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    hit = nt.nodes.new("ShaderNodeVectorMath")
    hit.operation = "ADD"
    nt.links.new(tc.outputs["Object"], hit.inputs[0])
    nt.links.new(step.outputs[0], hit.inputs[1])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(hit.outputs[0], sep.inputs[0])
    yz = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["Y"], yz.inputs["X"])
    nt.links.new(sep.outputs["Z"], yz.inputs["Y"])
    mp = nt.nodes.new("ShaderNodeMapping")                           # the picture's right is -Y; it is centred on the sheet
    sky_w = SKY_H * 16 / 9
    mp.inputs["Scale"].default_value = (-1.0 / sky_w, 1.0 / SKY_H, 1.0)
    mp.inputs["Location"].default_value = (0.5, 0.5 + (V.SHEET_H / 2) / SKY_H, 0.0)
    nt.links.new(yz.outputs[0], mp.inputs["Vector"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(V.ART, f"{sky}_00001_.png"), check_existing=True)
    tex.extension = "EXTEND"
    nt.links.new(mp.outputs[0], tex.inputs["Vector"])
    lum = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(picture, lum.inputs[0])
    frame = nt.nodes.new("ShaderNodeMapRange")                       # dark in the picture -> dark over the sky
    frame.inputs["From Min"].default_value = 0.3
    frame.inputs["From Max"].default_value = 0.7
    frame.inputs["To Min"].default_value = 0.1
    frame.inputs["To Max"].default_value = 1.0
    nt.links.new(lum.outputs[0], frame.inputs["Value"])
    lit = nt.nodes.new("ShaderNodeMix")
    lit.data_type = "RGBA"
    lit.blend_type = "MULTIPLY"
    kit.sock(lit.inputs, "Factor", "VALUE").default_value = 1.0
    nt.links.new(tex.outputs["Color"], kit.sock(lit.inputs, "A", "RGBA"))
    nt.links.new(frame.outputs["Result"], kit.sock(lit.inputs, "B", "RGBA"))
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.6
    nt.links.new(kit.sock(lit.outputs, "Result", "RGBA"), em.inputs["Color"])
    glass = nt.nodes.new("ShaderNodeBsdfGlossy")
    glass.inputs["Roughness"].default_value = 0.03
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(glass.outputs[0], mix.inputs[2])
    return mix.outputs[0]


def _water(nt):
    """Her water is the hall's: near-black, a mirror with a slow ripple, so the hall's lamps and beams lie on it."""
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.008, 0.009, 0.014, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.12                    # black water: the hall in it dim and a little soft
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 5.0
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return bsdf.outputs[0]


def _mirror(nt):
    g = nt.nodes.new("ShaderNodeBsdfGlossy")
    g.inputs["Roughness"].default_value = 0.0
    g.inputs["Color"].default_value = (0.85, 0.87, 0.9, 1.0)
    return g.outputs[0]


def hybrid_mat(front, back, sky):
    """The print's material with its flat planes swapped for the hall's: by the flat map's channels, G water, B
    mirror, R the sky behind the window."""
    mat = V.print_mat(front, back)
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    chain = out.inputs["Surface"].links[0].from_socket
    path = os.path.join(MAPS, f"{front}_flat.png")
    bpy.data.images.load(path, check_existing=True).colorspace_settings.name = "Non-Color"
    flat, _ = V._picture(nt, front, V.MARGIN, file=path)
    picture, _ = V._picture(nt, front, V.MARGIN)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(flat, sep.inputs[0])
    for fac, shader in ((sep.outputs["Green"], _water(nt)), (sep.outputs["Blue"], _mirror(nt)),
                        (sep.outputs["Red"], _sky_portal(nt, sky, picture))):
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(fac, mix.inputs["Fac"])
        nt.links.new(chain, mix.inputs[1])
        nt.links.new(shader, mix.inputs[2])
        chain = mix.outputs[0]
    nt.links.new(chain, out.inputs["Surface"])
    return mat


def swap(prints, name, front, back, sky, seed):
    """The print `name` replaced by a hybrid one in its place."""
    old = next(p for p in prints if p.name == name)
    x, y = old.location.x, old.location.y
    for ch in list(old.children):
        bpy.data.objects.remove(ch)
    bpy.data.objects.remove(old)
    prints.remove(old)
    new = V.sheet(name, x, y, hybrid_mat(front, back, sky), seed, grid=(72, 126), relief=depth_relief(front))
    prints.append(new)
    return new


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
    prints = V.hang()
    sky = "v4_s1_211" if dawn else "v4_s3_211"
    kv = swap(prints, "print_0_+0.0", *V.KV, sky, seed=0)
    u1 = swap(prints, "print_1_-1.6", "v4_u1_211", "v4_a1_211", sky, seed=5)
    if dawn:
        V.dawn_light()
    else:
        V.rose_light(prints)
    V.haze(dawn)
    cyc.post(bloom=0.35 if dawn else 0.6, threshold=1.0 if dawn else 0.75)
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
