"""一图流星环的花哨样式（ring_poc.py 里比出来的 E）在 Blender 里的做法：star_ring_fancy() 是光点，galaxy() 是
月亮当星系核的旋臂盘面和上面的小星。和 onepic.star_ring() 一样，逐帧的角度、亮度存在一张数据贴图里，
Geometry Nodes 按帧去查，网格只是骨架；全是叠加的自发光（亮度按显示值写，着色器里过 Gamma 2.2 再发光）。

长度以月亮半径 R 为单位，角度 θ 的约定同 star_ring.py：从正下方 0 起，θ 减小是画面上的顺时针。
世界坐标里 X 朝右、Z 朝上；朝外 = (sin θ, 0, −cos θ)，切向（和走的方向相反）= (cos θ, 0, sin θ)。

着色器里用到 audio 的两列：beat（拍点上 1、0.16 秒衰减）和 since（离上一拍几秒），由调用的一方放进 Audio。
"""
import math

import bpy
import numpy as np

import kit
from onepic import TAU, new_group, material, mesh_obj

KINDS = ("plain", "twin", "spark", "pulsar", "comet", "beads", "prism")
K = {k: i for i, k in enumerate(KINDS)}
BEADS = ((0.93, 0.75), (0.86, 0.6), (0.79, 0.48), (0.72, 0.38))     # 珠串的小卫星：在尾巴上的位置 q、大小
# 每种的尾巴：(宽度倍数, 亮度倍数)
TRAIL = {"plain": (1.0, 1.0), "twin": (0.8, 0.85), "spark": (0.7, 1.0), "pulsar": (1.0, 1.0),
         "comet": (2.5, 1.6), "beads": (1.0, 1.0), "prism": (1.2, 1.3)}
FLARE = 2.4         # 星芒那片方块的半边长（R）：六芒星芒、脉冲星的长星芒和冲击波、彗星的离子尾都在里面
STREAK = (6.5, 0.09)    # 横向光条那片的半边长（R）


def items(name, m, nv, faces_per, per_item, per_vert, colors):
    """m 个条目、每个 nv 个顶点的网格。per_item：{名字: 长 m 的数组}，per_vert：{名字: 长 nv 的数组}（每个条目一样），
    colors：{名字: (m, 3)}。全存成点上的属性。"""
    faces = (np.arange(m)[:, None, None] * nv + np.asarray(faces_per)[None]).reshape(m * len(faces_per), -1)
    ob = mesh_obj(name, np.zeros((m * nv, 3)), faces.tolist())
    me = ob.data
    for k, v in per_item.items():
        me.attributes.new(k, "FLOAT", "POINT").data.foreach_set("value", np.repeat(np.asarray(v, np.float32), nv))
    for k, v in per_vert.items():
        me.attributes.new(k, "FLOAT", "POINT").data.foreach_set("value", np.tile(np.asarray(v, np.float32), m))
    for k, v in colors.items():
        col = np.concatenate([np.repeat(np.asarray(v, np.float32), nv, 0), np.ones((m * nv, 1), np.float32)], 1)
        me.attributes.new(k, "FLOAT_COLOR", "POINT").data.foreach_set("color", col.ravel())
    return ob


QUAD = ([(0, 1, 2, 3)], {"ox": [-1.0, 1.0, 1.0, -1.0], "oy": [-1.0, -1.0, 1.0, 1.0]})


def ring_image(ring, rows):
    """(θ, 亮度, 响度, 尾巴往前的帧数) 的浮点贴图：每帧一行、每颗光点一列，帧数多时折成几块并排。"""
    th, br, env, _, tk = ring.tables()
    n, F = br.shape
    K_ = int(math.ceil(F / rows))
    px = np.zeros((rows, n * K_, 4), np.float32)
    for b in range(K_):
        blk = slice(b * rows, min((b + 1) * rows, F))
        m = blk.stop - blk.start
        for ch, a in enumerate((th, br, env, tk)):
            px[:m, b * n:(b + 1) * n, ch] = a[:, blk].T
    img = bpy.data.images.new("star_ring_fancy", n * K_, rows, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    img.alpha_mode = "CHANNEL_PACKED"
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img, n, F, K_


def emit(g, out, rgb, gain):
    """显示值 rgb -> Gamma 2.2 -> 叠加的自发光。"""
    rgb = g.v("MINIMUM", rgb, (1.0, 1.0, 1.0))
    gm = g.node("ShaderNodeGamma")
    g.link(rgb, gm.inputs["Color"])
    gm.inputs["Gamma"].default_value = 2.2
    em = g.node("ShaderNodeEmission")
    g.link(gm.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = gain
    add = g.node("ShaderNodeAddShader")
    g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    g.link(add.outputs[0], out.inputs["Surface"])


def sattr(g, nm, out="Fac"):
    a = g.node("ShaderNodeAttribute")
    a.attribute_type = "GEOMETRY"
    a.attribute_name = nm
    return a.outputs[out]


def fade(g, x, edge, soft):
    """x 到 edge 之前是 1，过了 edge 软软地落到 0。"""
    mr_ = g.node("ShaderNodeMapRange")
    mr_.interpolation_type = "SMOOTHSTEP"
    g.link(x, kit.sock(mr_.inputs, "Value", "VALUE"))
    g._in(kit.sock(mr_.inputs, "From Min", "VALUE"), g.m("SUBTRACT", edge, soft))
    g._in(kit.sock(mr_.inputs, "From Max", "VALUE"), g.m("ADD", edge, soft))
    kit.sock(mr_.inputs, "To Min", "VALUE").default_value = 1.0
    kit.sock(mr_.inputs, "To Max", "VALUE").default_value = 0.0
    return kit.sock(mr_.outputs, "Result", "VALUE")


def gauss(g, x, s):
    """exp(−(x / s)²)。"""
    r = g.m("DIVIDE", x, s)
    return g.m("EXPONENT", g.m("MULTIPLY", g.m("MULTIPLY", r, r), -1.0))


def mix(g, a, b, t):
    """颜色：a + (b − a) t，t 是数。"""
    return g.v("ADD", a, g.v("SCALE", g.v("SUBTRACT", b, a), t))


def lerp(g, a, b, t):
    """数：a + (b − a) t。"""
    return g.m("ADD", a, g.m("MULTIPLY", g.m("SUBTRACT", b, a), t))


def line(g, x, z, ang, width):
    """过原点、朝 ang 方向的直线：返回 (沿线的距离, 离线的距离)。"""
    ca, sa = math.cos(ang) if isinstance(ang, float) else g.m("COSINE", ang), \
        math.sin(ang) if isinstance(ang, float) else g.m("SINE", ang)
    along = g.m("ADD", g.m("MULTIPLY", x, ca), g.m("MULTIPLY", z, sa))
    across = g.m("ABSOLUTE", g.m("SUBTRACT", g.m("MULTIPLY", z, ca), g.m("MULTIPLY", x, sa)))
    return along, gauss(g, across, width)


def star_ring_fancy(pic, ring, fx, audio, y=None, tail_pts=64, gain=2.5, rows=4096, spike_gain=1.0,
                    streak_gain=1.0):
    """花哨样式的星环。ring 是 star_ring.Ring（建议用 FANCY_RADII 那套轨道），fx 是 star_ring.fancy(ring) 的结果。
    摆在月亮的视线上 y 米处（默认天空的 0.97）。几个物体：
    - stars_trail：尾巴，每颗一条（双子星两条，按当时的互绕相位左右错开），宽度、亮度按种类，彗星的软、颜色从白到本色
      再到偏紫，棱彩尾的颜色沿尾巴变、往前流；
    - stars_head：光头（双子星两颗互绕，珠串再跟四颗小卫星，各自闪），拍点上大一点；
    - stars_flare：每颗一片 FLARE 的方块：六芒星芒（约 40 秒转过 60°、长短 7 秒起伏、六条各自 5–9 秒强弱错开，只有亮的
      光头才拉得出来）；双子星以外的光头一个小十字星芒，脉冲星换成长的、踩着拍子亮，拍点上一圈冲击波往外扩；彗星朝外一条
      淡蓝的离子尾；
    - stars_streak：横向的淡蓝光条，按 11 秒明暗；
    - stars_spark：火花尾掉的火星，往后飘、往外散、稍微往下落，闪着熄掉，大的带小星芒。"""
    mu, mv, mr = pic.meta["moon"]
    y = y or pic.y_sky * 0.97
    c = pic.point(mu, mv, y)
    Rm = mr * pic.sx * y
    img, n, F, Kb = ring_image(ring, rows)
    fps = ring.fps
    kind = fx["kind"]
    T = tail_pts

    # ---- 骨架
    strands = [(i, 0.0) for i in range(n) if kind[i] != K["twin"]] + \
        [(i, s) for i in range(n) if kind[i] == K["twin"] for s in (1.0, -1.0)]
    li = np.array([i for i, _ in strands])
    ts = np.array([s for _, s in strands])
    wk = np.array([TRAIL[KINDS[kind[i]]][0] for i in li])
    bk = np.array([TRAIL[KINDS[kind[i]]][1] for i in li])
    col = ring.color[li].copy()
    col[ts < 0] = fx["col2"][li[ts < 0]]
    trail = items("stars_trail", len(li), 2 * T, [(2 * j, 2 * j + 1, 2 * j + 3, 2 * j + 2) for j in range(T - 1)],
                  dict(li=li, r=ring.r[li], rc=0.020 * ring.size[li], ts=ts, wk=wk, bk=bk,
                       tw_p=fx["tw_p"][li], tw_ph=fx["tw_ph"][li], hue0=fx["hue0"][li],
                       comet=kind[li] == K["comet"], prism=kind[li] == K["prism"]),
                  {"q": np.repeat(np.linspace(0, 1, T), 2), "side": np.tile([-1.0, 1.0], T)}, {"col": col})

    heads = [(i, 0.0, 1.0, 1.0, 0.0, 0.0) for i in range(n) if kind[i] != K["twin"]]     # (光点, ts, q, 大小, 珠串, 相位)
    heads += [(i, s, 1.0, 0.75, 0.0, 0.0) for i in range(n) if kind[i] == K["twin"] for s in (1.0, -1.0)]
    heads += [(i, 0.0, q, s, 1.0, 1.7 * k + i) for i in range(n) if kind[i] == K["beads"]
              for k, (q, s) in enumerate(BEADS)]
    H = np.array(heads, float)
    hli = H[:, 0].astype(int)
    hcol = ring.color[hli].copy()
    hcol[H[:, 1] < 0] = fx["col2"][hli[H[:, 1] < 0]]
    head = items("stars_head", len(H), 4, *QUAD[:1],
                 dict(li=hli, r=ring.r[hli], rc=0.020 * ring.size[hli], ts=H[:, 1], q=H[:, 2], hs=H[:, 3],
                      bead=H[:, 4], bph=H[:, 5], tw_p=fx["tw_p"][hli], tw_ph=fx["tw_ph"][hli]),
                 QUAD[1], {"col": hcol})
    all_ = np.arange(n)
    flare = items("stars_flare", n, 4, *QUAD[:1],
                  dict(li=all_, r=ring.r, rc=0.020 * ring.size, q=np.ones(n), pulsar=kind == K["pulsar"],
                       comet=kind == K["comet"], nocross=kind == K["twin"], spike0=fx["spike0"]),
                  QUAD[1], {"col": ring.color})
    streak = items("stars_streak", n, 4, *QUAD[:1], dict(li=all_, r=ring.r, rc=0.020 * ring.size, q=np.ones(n)),
                   QUAD[1], {"col": ring.color})
    sp = fx["sparks"]
    spark = items("stars_spark", len(sp["li"]), 4, *QUAD[:1],
                  dict(li=sp["li"], r=ring.r[sp["li"].astype(int)], fb=sp["fb"], life=sp["life"], back=sp["back"],
                       side=sp["side"], ph=sp["ph"], big=sp["big"]), QUAD[1], {"col": sp["col"]})

    # ---- Geometry Nodes
    def nodes(name, part):
        ng, g, gi, go = new_group(name, "GeometryNodeTree", inputs=[("Geometry", "NodeSocketGeometry", None)],
                                  outputs=[("Geometry", "NodeSocketGeometry", None)])
        M = g.m

        def attr(nm):
            a = g.node("GeometryNodeInputNamedAttribute", data_type="FLOAT")
            a.inputs["Name"].default_value = nm
            return kit.sock(a.outputs, "Attribute")

        def look(fs):
            fs = M("MINIMUM", M("MAXIMUM", M("ROUND", fs), 0.0), float(F - 1))
            block = M("FLOOR", M("DIVIDE", fs, float(rows)))
            row = M("SUBTRACT", fs, M("MULTIPLY", block, float(rows)))
            u = M("DIVIDE", M("ADD", M("MULTIPLY_ADD", block, float(n), attr("li")), 0.5), float(n * Kb))
            v = M("DIVIDE", M("ADD", row, 0.5), float(rows))
            t = g.node("GeometryNodeImageTexture")
            t.interpolation = "Closest"
            t.extension = "EXTEND"
            t.inputs["Image"].default_value = img
            g.link(g.xyz(u, v, 0), t.inputs["Vector"])
            return t

        st = g.node("GeometryNodeInputSceneTime")
        frame, sec = st.outputs["Frame"], st.outputs["Seconds"]
        if part == "spark":
            fs = attr("fb")
        else:
            tail = look(frame).outputs["Alpha"]
            fs = M("SUBTRACT", frame, M("MULTIPLY", M("SUBTRACT", 1.0, attr("q")), tail))
        a, b_, e = g.sep(look(fs).outputs["Color"])
        sa, ca = M("SINE", a), M("COSINE", a)
        radial = g.xyz(sa, 0.0, M("MULTIPLY", ca, -1.0))
        tangent = g.xyz(ca, 0.0, sa)
        center = g.v("ADD", tuple(c), g.v("SCALE", radial, M("MULTIPLY", attr("r"), Rm)))
        sh = M("POWER", M("ABSOLUTE", M("COSINE", M("SUBTRACT", a, ring.sheen))), 4.0)
        widen = M("MULTIPLY_ADD", sh, 0.2, 1.0)
        beat = audio.at_gn(g, "beat")
        store = []

        def twin_phase():
            ph = M("ADD", M("DIVIDE", M("MULTIPLY", fs, TAU / fps), attr("tw_p")), attr("tw_ph"))
            rh0 = M("MULTIPLY", M("MULTIPLY", attr("rc"), M("MULTIPLY_ADD", e, 0.3, 0.85)), widen)
            sep = M("MAXIMUM", M("MULTIPLY", rh0, 2.4), 0.09)
            return ph, M("MULTIPLY", M("MULTIPLY", sep, attr("ts")), Rm)

        def corner(ex, ez):
            return g.v("ADD", center, g.xyz(M("MULTIPLY", attr("ox"), ex * Rm if isinstance(ex, float) else M("MULTIPLY", ex, Rm)),
                                            0.0, M("MULTIPLY", attr("oy"), ez * Rm if isinstance(ez, float) else M("MULTIPLY", ez, Rm))))

        if part == "trail":
            ph, off = twin_phase()
            center = g.v("ADD", center, g.v("SCALE", radial, M("MULTIPLY", off, M("COSINE", ph))))
            q = attr("q")
            loud = M("MULTIPLY_ADD", e, 0.4, 0.8)
            w = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", attr("rc"), 1.1), M("MULTIPLY_ADD", q, 0.75, 0.25)),
                  M("MULTIPLY", M("MULTIPLY", loud, widen), attr("wk")))
            hw = M("MULTIPLY", w, 0.5)
            Hh = M("ADD", M("ADD", hw, 0.12), M("MULTIPLY", attr("comet"), 0.1))
            pos = g.v("ADD", center, g.v("SCALE", radial, M("MULTIPLY", M("MULTIPLY", attr("side"), Hh), Rm)))
            sv = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", b_, 0.85), M("POWER", q, 1.8)), attr("bk"))
            store = [("sv", sv), ("hw", hw), ("H", Hh)]
        elif part == "head":
            ph, off = twin_phase()
            orbit = g.v("ADD", g.v("SCALE", radial, M("COSINE", ph)), g.v("SCALE", tangent, M("MULTIPLY", M("SINE", ph), 0.5)))
            center = g.v("ADD", center, g.v("SCALE", orbit, off))
            rh = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", attr("rc"), M("MULTIPLY_ADD", e, 0.3, 0.85)), widen),
                   M("MULTIPLY", M("MULTIPLY_ADD", beat, 0.35, 1.0), attr("hs")))
            E = M("MULTIPLY_ADD", rh, 1.8, 0.12)
            tw = M("MULTIPLY_ADD", M("SINE", M("MULTIPLY_ADD", sec, 5.0, attr("bph"))), 0.4, 0.6)
            k = M("ADD", M("SUBTRACT", 1.0, attr("bead")), M("MULTIPLY", attr("bead"), M("MULTIPLY", M("MULTIPLY", tw, attr("hs")), 1.2)))
            pos = corner(E, E)
            store = [("hb", M("MULTIPLY", b_, k)), ("rh", rh), ("E", E)]
        elif part == "flare":
            rh = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", attr("rc"), M("MULTIPLY_ADD", e, 0.3, 0.85)), widen),
                   M("MULTIPLY_ADD", beat, 0.35, 1.0))
            vis = M("MULTIPLY", M("GREATER_THAN", b_, 0.003), FLARE)        # 看不见的缩成零，省得着色
            pos = corner(vis, vis)
            store = [("hb", b_), ("rh", rh), ("th", a)]
        elif part == "streak":
            vis = M("GREATER_THAN", b_, 0.3)
            pos = corner(M("MULTIPLY", vis, STREAK[0]), M("MULTIPLY", vis, STREAK[1]))
            store = [("hb", b_)]
        else:   # spark
            age = M("DIVIDE", M("SUBTRACT", frame, fs), float(fps))
            life = attr("life")
            alive = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", age, 0.0), M("LESS_THAN", age, life)),
                      M("GREATER_THAN", b_, 0.05))
            drift = M("MULTIPLY", age, M("SUBTRACT", 1.0, M("DIVIDE", M("MULTIPLY", age, 0.35), life)))
            vel = g.v("ADD", g.v("SCALE", tangent, attr("back")), g.v("SCALE", radial, attr("side")))
            p = g.v("ADD", center, g.v("SCALE", vel, M("MULTIPLY", drift, Rm)))
            center = g.v("ADD", p, g.xyz(0.0, 0.0, M("MULTIPLY", M("MULTIPLY", age, age), -0.05 * Rm)))
            left = M("SUBTRACT", 1.0, M("DIVIDE", age, life))
            fl = M("MULTIPLY", M("MULTIPLY", left, left),
                   M("MULTIPLY_ADD", M("SINE", M("MULTIPLY_ADD", age, 38.0, attr("ph"))), 0.45, 0.55))
            sv = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", b_, fl), M("MULTIPLY_ADD", attr("big"), 0.9, 1.3)), alive)
            size = M("MULTIPLY", alive, 0.07)
            pos = corner(size, size)
            store = [("sv", sv)]
        sp_ = g.node("GeometryNodeSetPosition")
        g.link(gi.outputs["Geometry"], sp_.inputs["Geometry"])
        g.link(pos, sp_.inputs["Position"])
        geo = sp_.outputs[0]
        for nm, val in store:
            s_ = g.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
            g.link(geo, s_.inputs["Geometry"])
            s_.inputs["Name"].default_value = nm
            g.link(val, kit.sock(s_.inputs, "Value"))
            geo = s_.outputs[0]
        g.link(geo, go.inputs["Geometry"])
        return ng

    # ---- 着色器
    def glow(g, d, k):
        """σ = 0.04 R 的高斯辉光，k 是峰值。"""
        return g.m("MULTIPLY", k, g.m("EXPONENT", g.m("MULTIPLY", g.m("MULTIPLY", d, d), -312.5)))

    def shader(name, part):
        mt, g, out = material(name, "BLENDED")
        M = g.m
        col = sattr(g, "col", "Color")
        t = audio.seconds(g)
        white = g.v("MULTIPLY_ADD", col, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        if part == "trail":
            hw, q = sattr(g, "hw"), sattr(g, "q")
            d = M("MULTIPLY", M("ABSOLUTE", sattr(g, "side")), sattr(g, "H"))
            hard = M("ADD", fade(g, d, hw, 0.008), glow(g, d, M("MULTIPLY", hw, 13.96)))
            soft = M("ADD", M("MULTIPLY", gauss(g, d, M("MULTIPLY", hw, 0.9)), 0.9), glow(g, d, M("MULTIPLY", hw, 6.0)))
            comet = sattr(g, "comet")
            prof = lerp(g, hard, soft, comet)
            hue = M("FRACT", M("ADD", M("ADD", sattr(g, "hue0"), M("MULTIPLY", M("SUBTRACT", 1.0, q), 0.9)),
                                M("MULTIPLY", t, -0.25)))
            cc = g.node("ShaderNodeCombineColor")
            cc.mode = "HSV"
            g.link(hue, cc.inputs[0])
            cc.inputs[1].default_value = 0.7
            cc.inputs[2].default_value = 1.0
            ccol = mix(g, (0.75, 0.45, 0.95), g.v("ADD", g.v("SCALE", col, 0.5), g.xyz(M("MULTIPLY", q, 0.5), M("MULTIPLY", q, 0.5), M("MULTIPLY", q, 0.5))), q)
            c2 = mix(g, col, cc.outputs[0], sattr(g, "prism"))
            c2 = mix(g, c2, ccol, comet)
            rgb = g.v("SCALE", c2, M("MULTIPLY", prof, sattr(g, "sv")))
        elif part == "head":
            rh, E = sattr(g, "rh"), sattr(g, "E")
            rho = M("MULTIPLY", g.v("LENGTH", g.xyz(sattr(g, "ox"), sattr(g, "oy"), 0.0)), E)
            core = M("ADD", M("MULTIPLY", fade(g, rho, rh, 0.006), 0.55),
                     M("MULTIPLY", fade(g, rho, M("MULTIPLY", rh, 0.5), 0.006), 0.45))
            halo = M("ADD", M("MULTIPLY", fade(g, rho, M("MULTIPLY", rh, 1.8), 0.05), 0.3),
                     glow(g, rho, M("MULTIPLY", M("MULTIPLY", rh, rh), 153.0)))
            w2 = g.v("MULTIPLY_ADD", col, (0.4, 0.4, 0.4), (0.6, 0.6, 0.6))
            rgb = g.v("SCALE", g.v("ADD", g.v("SCALE", w2, core), g.v("SCALE", col, halo)), sattr(g, "hb"))
        elif part == "flare":
            x = M("MULTIPLY", sattr(g, "ox"), FLARE)
            z = M("MULTIPLY", sattr(g, "oy"), FLARE)
            hb, rh = sattr(g, "hb"), sattr(g, "rh")
            beat, since = audio.at(g, "beat"), audio.at(g, "since")
            # 六芒星芒：约 40 秒转过 60°，长短 7 秒起伏，六条各自强弱
            rot = M("MULTIPLY_ADD", t, (math.pi / 3) / 40.0, 0.26)
            reach = M("MULTIPLY", M("MULTIPLY_ADD", M("SINE", M("MULTIPLY", t, TAU / 7.0)), 0.3, 1.0), 0.32)
            edge = M("POWER", M("MAXIMUM", M("SUBTRACT", 1.0, M("DIVIDE", g.v("LENGTH", g.xyz(x, z, 0.0)), FLARE)), 0.0), 2.0)   # 到方块边上淡完
            six = None
            for j in range(6):
                along, prof = line(g, x, z, M("ADD", rot, j * math.pi / 3), 0.013)
                gj = M("MULTIPLY_ADD", M("SINE", M("MULTIPLY_ADD", t, TAU / (5.0 + 0.8 * j), 1.3 * j)), 0.35, 0.75)
                s_ = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", along, 0.0),
                                     M("EXPONENT", M("DIVIDE", M("MULTIPLY", M("MAXIMUM", along, 0.0), -1.0), reach))),
                       M("MULTIPLY", M("MULTIPLY", prof, gj), edge))
                six = s_ if six is None else M("ADD", six, s_)
            six = M("MULTIPLY", six, M("MULTIPLY", M("MAXIMUM", M("SUBTRACT", hb, 0.25), 0.0), 0.75 * spike_gain))
            # 十字星芒：普通的短、拍点上亮一下；脉冲星的长、慢慢转、踩着拍子亮
            pulsar = sattr(g, "pulsar")
            amp = M("MULTIPLY_ADD", beat, 0.75, 0.25)
            L = lerp(g, M("MULTIPLY", M("MULTIPLY", rh, 4.5), M("MULTIPLY_ADD", beat, 0.5, 1.0)),
                    M("MULTIPLY", M("MULTIPLY", rh, 13.0), M("MULTIPLY_ADD", amp, 0.6, 0.7)), pulsar)
            ang = M("ADD", sattr(g, "spike0"), M("MULTIPLY", M("MULTIPLY", t, 0.15), pulsar))
            crs = None
            for k_ in (0.0, math.pi / 2):
                along, prof = line(g, x, z, M("ADD", ang, k_), 0.007)
                f_ = M("MAXIMUM", M("SUBTRACT", 1.0, M("DIVIDE", M("ABSOLUTE", along), L)), 0.0)
                s_ = M("MULTIPLY", M("POWER", f_, 1.5), prof)
                crs = s_ if crs is None else M("ADD", crs, s_)
            kb = lerp(g, M("MULTIPLY_ADD", beat, 0.5, 0.3), amp, pulsar)
            crs = M("MULTIPLY", M("MULTIPLY", crs, M("MULTIPLY", hb, kb)), M("SUBTRACT", 1.0, sattr(g, "nocross")))
            # 冲击波（脉冲星）：拍点上从 2 倍星芯半径往外扩，0.5 秒散完
            rho = g.v("LENGTH", g.xyz(x, z, 0.0))
            rr = M("MULTIPLY", rh, M("MULTIPLY_ADD", since, 60.0, 2.0))
            left = M("MAXIMUM", M("SUBTRACT", 1.0, M("DIVIDE", since, 0.5)), 0.0)
            shock = M("MULTIPLY", M("MULTIPLY", gauss(g, M("SUBTRACT", rho, rr), 0.008), M("MULTIPLY", left, left)),
                      M("MULTIPLY", M("MULTIPLY", hb, 0.6), pulsar))
            # 离子尾（彗星）：朝外 1.3 R
            th = sattr(g, "th")
            out_a = M("ADD", M("MULTIPLY", x, M("SINE", th)), M("MULTIPLY", z, M("MULTIPLY", M("COSINE", th), -1.0)))
            out_c = M("ABSOLUTE", M("SUBTRACT", M("MULTIPLY", x, M("COSINE", th)), M("MULTIPLY", z, M("MULTIPLY", M("SINE", th), -1.0))))
            frac = M("MAXIMUM", M("SUBTRACT", 1.0, M("DIVIDE", out_a, 1.3)), 0.0)
            ion = M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", M("POWER", frac, 1.5), M("GREATER_THAN", out_a, 0.0)),
                                  gauss(g, out_c, 0.014)), M("MULTIPLY", M("MULTIPLY", hb, 0.7), sattr(g, "comet")))
            rgb = g.v("ADD", g.v("SCALE", white, M("ADD", M("ADD", six, crs), shock)),
                      g.v("SCALE", (0.45, 0.7, 1.0), ion))
        elif part == "streak":
            x = M("MULTIPLY", sattr(g, "ox"), STREAK[0])
            z = M("MULTIPLY", sattr(g, "oy"), STREAK[1])
            k_ = M("MULTIPLY", M("MAXIMUM", M("SUBTRACT", sattr(g, "hb"), 0.3), 0.0),
                   M("MULTIPLY_ADD", M("SINE", M("MULTIPLY", t, TAU / 11.0)), 0.3, 0.8))
            prof = M("MULTIPLY", M("EXPONENT", M("MULTIPLY", M("MULTIPLY", x, x), -1 / (2 * 2.1 ** 2))), gauss(g, z, 0.024))
            rgb = g.v("SCALE", (0.5, 0.7, 1.0), M("MULTIPLY", M("MULTIPLY", prof, k_), 0.3 * streak_gain))
        else:   # spark
            rho = M("MULTIPLY", g.v("LENGTH", g.xyz(sattr(g, "ox"), sattr(g, "oy"), 0.0)), 0.07)
            big = sattr(g, "big")
            rad = M("MULTIPLY_ADD", big, 0.0095, 0.0107)
            core = M("ADD", fade(g, rho, rad, 0.004), M("MULTIPLY", gauss(g, rho, 0.022), 0.35))
            xs, zs = M("MULTIPLY", sattr(g, "ox"), 0.07), M("MULTIPLY", sattr(g, "oy"), 0.07)
            crs = None
            for k_ in (0.5, 0.5 + math.pi / 2):
                along, prof = line(g, xs, zs, k_, 0.005)
                s_ = M("MULTIPLY", M("MAXIMUM", M("SUBTRACT", 1.0, M("DIVIDE", M("ABSOLUTE", along), 0.06)), 0.0), prof)
                crs = s_ if crs is None else M("ADD", crs, s_)
            rgb = g.v("SCALE", col, M("MULTIPLY", M("ADD", core, M("MULTIPLY", M("MULTIPLY", crs, big), 0.6)), sattr(g, "sv")))
        emit(g, out, rgb, gain)
        return mt

    obs = []
    for ob, part in ((trail, "trail"), (head, "head"), (flare, "flare"), (streak, "streak"), (spark, "spark")):
        ob.data.materials.append(shader(ob.name, part))
        mod = ob.modifiers.new("stars", "NODES")
        mod.node_group = nodes(ob.name, part)
        obs.append(ob)
    kinds = ", ".join(f"{k} {int((kind == i).sum())}" for i, k in enumerate(KINDS))
    print(f"star ring (fancy): {n} lights ({kinds}), {len(sp['li'])} sparks, {F} frames, R {Rm:.2f} m at {y:.0f} m",
          flush=True)
    return obs


def galaxy(pic, audio, sky_mask, y=None, stars=14000, rmax=22.0, pitch=1.3, gain=2.5, arm_gain=1.0, seed=9):
    """月亮当星系核：两条对数螺旋旋臂铺到 rmax R（大半个天空），内暖外蓝，团块里带粉色的星团，盘面一层很淡的底光，
    核心一圈暖白的光；旋臂上 stars 颗小星按 1/r 差速转（内圈约 2 分钟一圈，和光点一样顺着 θ 减小的方向），各自闪。
    sky_mask (h, w) 是天空的遮罩（1 是天空），地面、花田上不铺。摆在星环后面一点（y 默认天空的 0.975）。"""
    mu, mv, mr = pic.meta["moon"]
    y = y or pic.y_sky * 0.975
    Rm = mr * pic.sx * y
    omega0 = -TAU / 120.0
    hgt, wid = sky_mask.shape
    mimg = bpy.data.images.new("sky_mask", wid, hgt, alpha=False, float_buffer=True)
    mimg.colorspace_settings.name = "Non-Color"
    px = np.zeros((hgt, wid, 4), np.float32)
    px[..., :3] = np.flipud(sky_mask)[..., None]
    px[..., 3] = 1
    mimg.pixels.foreach_set(px.ravel())
    mimg.pack()

    def mask_at(g, u, v, node="ShaderNodeTexImage"):
        t = g.node(node)
        if node == "ShaderNodeTexImage":
            t.image = mimg
            t.extension = "CLIP"
            g.link(g.xyz(u, g.m("SUBTRACT", 1.0, v), 0.0), t.inputs["Vector"])
            return t.outputs["Color"]
        t.inputs["Image"].default_value = mimg
        t.extension = "CLIP"
        g.link(g.xyz(u, g.m("SUBTRACT", 1.0, v), 0.0), t.inputs["Vector"])
        return t.outputs["Color"]

    # ---- 盘面：一片平的网格，UV 就是插画坐标
    mt, g, out = material("galaxy_disc", "BLENDED")
    M = g.m
    uv = g.node("ShaderNodeUVMap")
    uu, vv, _ = g.sep(uv.outputs["UV"])
    vv = M("SUBTRACT", 1.0, vv)
    xr = M("DIVIDE", M("SUBTRACT", uu, mu), mr)                       # R 为单位，往右
    zr = M("DIVIDE", M("SUBTRACT", vv, mv), mr / pic.aspect)          # 往下
    RR = g.v("LENGTH", g.xyz(xr, zr, 0.0))
    phi = M("ARCTAN2", xr, zr)
    lnr = M("LOGARITHM", M("MAXIMUM", RR, 0.3), math.e)
    win = M("MULTIPLY", M("MULTIPLY", g.m("DIVIDE", M("SUBTRACT", RR, 1.1), 0.8, clamp=True),
                          M("EXPONENT", M("DIVIDE", M("MAXIMUM", M("SUBTRACT", RR, 6.0), 0.0), -9.0))),
            g.m("DIVIDE", M("SUBTRACT", rmax + 2, RR), 6.0, clamp=True))
    t = audio.seconds(g)
    rot = M("MULTIPLY", t, omega0 * 0.6)
    psi = M("ADD", M("MULTIPLY", M("SUBTRACT", phi, rot), 2.0), M("MULTIPLY", lnr, 2 * pitch))
    arm = M("POWER", M("MULTIPLY_ADD", M("COSINE", psi), 0.5, 0.5), 4.0)
    # 团块：转着的坐标里的噪声，跟旋臂一起转
    cr, sr_ = M("COSINE", rot), M("SINE", rot)
    xq = M("SUBTRACT", M("MULTIPLY", xr, cr), M("MULTIPLY", zr, sr_))
    zq = M("ADD", M("MULTIPLY", xr, sr_), M("MULTIPLY", zr, cr))
    nz = g.node("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.35
    nz.inputs["Detail"].default_value = 4.0
    g.link(g.xyz(xq, zq, 0.37), nz.inputs["Vector"])
    clump = g.m("DIVIDE", M("SUBTRACT", nz.outputs["Fac"], 0.32), 0.38, clamp=True)
    dens = M("MULTIPLY", M("MULTIPLY", arm, win), M("MULTIPLY_ADD", M("MULTIPLY", clump, clump), 0.9, 0.35))
    inner = g.m("DIVIDE", M("SUBTRACT", 6.0, RR), 4.5, clamp=True)
    colr = mix(g, (0.5, 0.65, 1.0), (1.0, 0.85, 0.7), inner)
    light = g.v("SCALE", colr, M("MULTIPLY", dens, 0.38 * arm_gain))
    hii = M("MULTIPLY", M("MULTIPLY", M("POWER", g.m("MULTIPLY", M("MAXIMUM", M("SUBTRACT", clump, 0.6), 0.0), 2.5), 2.0),
                                     arm), win)
    light = g.v("ADD", light, g.v("SCALE", (1.0, 0.45, 0.7), M("MULTIPLY", hii, 0.3 * arm_gain)))
    light = g.v("ADD", light, g.v("SCALE", (0.45, 0.5, 0.9), M("MULTIPLY", win, 0.05 * arm_gain)))
    core = M("MULTIPLY", M("EXPONENT", M("DIVIDE", M("MAXIMUM", M("SUBTRACT", RR, 1.0), 0.0), -0.9)),
             M("GREATER_THAN", RR, 0.95))
    light = g.v("ADD", light, g.v("SCALE", (1.0, 0.92, 0.8), M("MULTIPLY", core, 0.16)))
    light = g.v("SCALE", light, g.sep(mask_at(g, uu, vv))[0])
    emit(g, out, light, gain)
    disc = pic.layer("galaxy_disc", np.full((2, 2), 1 / y, np.float32), mt, grid=24, margin=0.25)

    # ---- 旋臂上的小星
    rng = np.random.default_rng(seed)
    g_r = 1.3 * np.exp(rng.random(stars) ** 1.15 * np.log(rmax / 1.3))
    g_th = rng.integers(0, 2, stars) * np.pi - pitch * np.log(g_r) + rng.normal(0, 0.2 + 0.03 * g_r, stars)
    g_b = rng.uniform(0.08, 0.45, stars) * (rng.random(stars) ** 3 * 2.5 + 0.4)
    g_col = np.where((g_r < 4.0)[:, None], np.array((1.0, 0.85, 0.65)), np.array((0.6, 0.72, 1.0))).astype(np.float32)
    g_col[rng.random(stars) < 0.08] = (1.0, 0.55, 0.75)
    pts = items("galaxy_stars", stars, 4, *QUAD[:1],
                dict(r=g_r, th0=g_th, b=g_b, tw=rng.uniform(0, 6.3, stars)), QUAD[1], {"col": g_col})
    yp = pic.y_sky * 0.972
    Rp = mr * pic.sx * yp
    cp = pic.point(mu, mv, yp)
    ng, g, gi, go = new_group("galaxy_stars", "GeometryNodeTree", inputs=[("Geometry", "NodeSocketGeometry", None)],
                              outputs=[("Geometry", "NodeSocketGeometry", None)])
    M = g.m

    def attr(nm):
        a = g.node("GeometryNodeInputNamedAttribute", data_type="FLOAT")
        a.inputs["Name"].default_value = nm
        return kit.sock(a.outputs, "Attribute")

    sec = g.node("GeometryNodeInputSceneTime").outputs["Seconds"]
    r = attr("r")
    th = M("ADD", attr("th0"), M("MULTIPLY", M("DIVIDE", 2.0, r), M("MULTIPLY", sec, omega0)))
    sa, ca = M("SINE", th), M("COSINE", th)
    u = M("ADD", mu, M("DIVIDE", M("MULTIPLY", M("MULTIPLY", r, sa), mr), 1.0))
    v = M("ADD", mv, M("MULTIPLY", M("MULTIPLY", r, ca), mr * pic.aspect))
    sky = g.sep(mask_at(g, u, v, "GeometryNodeImageTexture"))[0]
    tw = M("MULTIPLY_ADD", M("SINE", M("MULTIPLY_ADD", sec, 2.3, attr("tw"))), 0.4, 0.6)
    center = g.v("ADD", tuple(cp), g.xyz(M("MULTIPLY", M("MULTIPLY", r, sa), Rp), 0.0,
                                          M("MULTIPLY", M("MULTIPLY", r, ca), -Rp)))
    pos = g.v("ADD", center, g.xyz(M("MULTIPLY", attr("ox"), 0.035 * Rp), 0.0, M("MULTIPLY", attr("oy"), 0.035 * Rp)))
    sp_ = g.node("GeometryNodeSetPosition")
    g.link(gi.outputs["Geometry"], sp_.inputs["Geometry"])
    g.link(pos, sp_.inputs["Position"])
    s_ = g.node("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
    g.link(sp_.outputs[0], s_.inputs["Geometry"])
    s_.inputs["Name"].default_value = "sv"
    g.link(M("MULTIPLY", M("MULTIPLY", attr("b"), tw), sky), kit.sock(s_.inputs, "Value"))
    g.link(s_.outputs[0], go.inputs["Geometry"])
    mod = pts.modifiers.new("galaxy", "NODES")
    mod.node_group = ng

    mt, g, out = material("galaxy_stars", "BLENDED")
    M = g.m
    rho = M("MULTIPLY", g.v("LENGTH", g.xyz(sattr(g, "ox"), sattr(g, "oy"), 0.0)), 0.035)
    k_ = M("ADD", fade(g, rho, 0.007, 0.003), M("MULTIPLY", gauss(g, rho, 0.016), 0.6))
    emit(g, out, g.v("SCALE", sattr(g, "col", "Color"), M("MULTIPLY", k_, sattr(g, "sv"))), gain)
    pts.data.materials.append(mt)
    print(f"galaxy: arms to {rmax} R, {stars} stars", flush=True)
    return disc, pts
