"""一图流 PV 的 Blender 场景（Blender 5.x，EEVEE）。

一张插画按深度摆成 2.5D 的立体场景：每一层（补全后的背景、人物……）是一张按视差起伏的网格，从“原始机位”看过去和原画
逐像素一致，镜头一离开原始机位就有真实的视差。在这上面加：
- Geometry Nodes 的花瓣和光点：位置只由时间和随机种子算出来（不用模拟），所以任意一段帧都能单独渲染；
- 天空里原有的星星按各自的相位闪烁，月亮周围的光晕跟着低频呼吸；
- 月亮周围一圈频谱、流星、立在空中的标题；
- 合成器里的辉光和以月亮为源的光束。
音频特征（各频段、响度、段落强度……）存成一张数据贴图，着色器和 Geometry Nodes 都按当前帧去查，见 Audio。

坐标：原始机位在原点，看向 +Y，Z 朝上，单位米。插画坐标 (u, v)：u 从左到右 0..1，v 从上到下 0..1。
第 f 帧对应 t = f / fps，场景从第 0 帧开始。

素材来自 onepic_prep.py（color / plate / alpha / stars / disp / meta）。
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Euler, Vector

import kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAU = 2 * math.pi


# ---------------------------------------------------------------- 场景

def scene(fps=60, width=3840, height=2160, samples=32):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tmp = os.path.join(ROOT, "tmp")
    os.makedirs(tmp, exist_ok=True)
    bpy.context.preferences.filepaths.temporary_directory = tmp
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE"
    e = s.eevee
    e.taa_render_samples = samples
    e.use_bokeh_jittered = True       # 景深按采样抖动，比后处理的景深干净
    e.bokeh_max_size = 300
    e.use_shadows = False             # 全是自发光，没有灯
    e.use_raytracing = False
    s.render.fps, s.render.fps_base = fps, 1.0
    s.render.resolution_x, s.render.resolution_y = width, height
    s.render.resolution_percentage = int(os.environ.get("RES", 100))
    s.render.film_transparent = False
    s.render.dither_intensity = 1.0
    s.render.compositor_device = "GPU"
    # Standard：自发光 1.0 的贴图原样输出，插画的颜色不被色调映射改掉
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    w = bpy.data.worlds.new("world")
    w.color = (0, 0, 0)
    s.world = w
    s.frame_start = 0
    return s


def link(obj, hide=False):
    bpy.context.scene.collection.objects.link(obj)
    if hide:
        obj.hide_render = True
        obj.hide_viewport = True
    return obj


def mesh_obj(name, verts, faces, mat=None, hide=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    return link(ob, hide)


# ---------------------------------------------------------------- 数组小工具（Blender 自带 numpy，没有 scipy/cv2）

def blur(a, r, n=3):
    """n 次盒式模糊，近似高斯。"""
    if r < 1:
        return a
    for _ in range(n):
        for ax in (0, 1):
            p = np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="edge")
            c = np.cumsum(p, axis=ax, dtype=np.float64)
            a = ((c[2 * r + 1:] - c[:-2 * r - 1]) if ax == 0 else (c[:, 2 * r + 1:] - c[:, :-2 * r - 1])) / (2 * r + 1)
    return a.astype(np.float32)


def sample(a, u, v):
    """双线性取值，u / v 为 0..1（v 从上到下）。"""
    h, w = a.shape
    x = np.clip(np.asarray(u, np.float64) * w - 0.5, 0, w - 1)
    y = np.clip(np.asarray(v, np.float64) * h - 0.5, 0, h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = x - x0, y - y0
    top = a[y0, x0] * (1 - fx) + a[y0, x1] * fx
    bot = a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def grow(values, mask, steps):
    """把 mask 内的值一圈圈往外推 steps 次（外面取邻居里 mask 内的平均），网格边缘就不会折回背景的深度。"""
    v = np.where(mask, values, 0).astype(np.float32)
    m = mask.astype(np.float32)
    for _ in range(steps):
        sv = sum(np.roll(np.roll(v, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        sm = sum(np.roll(np.roll(m, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        new = (m == 0) & (sm > 0)
        v = np.where(new, sv / np.maximum(sm, 1e-6), v)
        m = np.where(new, 1.0, m)
    return np.where(m > 0, v, np.median(values[mask]))


# ---------------------------------------------------------------- 插画的投影

class Pic:
    """原始机位和插画的对应：视差 -> 距离，(u, v, 距离) -> 世界坐标，以及按深度起伏的层网格。

    距离只靠两个锚点：人物的中位视差 -> y_girl，天空的视差 -> y_sky；视差和 1/距离 成正比，两点之间线性插值，
    比人物近的部分顺势外推（最近截到 y_min），比天空远的截到 y_sky。
    """

    def __init__(self, prep, lens=35.0, y_girl=1.6, y_sky=220.0, y_min=0.6, sensor=36.0):
        self.dir = prep
        self.meta = json.load(open(os.path.join(prep, "meta.json")))
        self.W, self.H = self.meta["w"], self.meta["h"]
        self.aspect = self.W / self.H
        self.lens, self.sensor = lens, sensor
        self.sx = sensor / lens                 # 距离 Y 处画面宽 sx * Y
        self.sz = sensor / self.aspect / lens   # 距离 Y 处画面高 sz * Y
        self.y_girl, self.y_sky, self.y_min = y_girl, y_sky, y_min
        self.d_girl, self.d_sky = self.meta["girl_disp"], self.meta["sky_disp"]
        self.disp = np.load(os.path.join(prep, "disp.npy"))
        self.disp_bg = np.load(os.path.join(prep, "disp_bg.npy"))
        self.alpha = np.load(os.path.join(prep, "alpha.npy"))

    def path(self, name):
        return os.path.join(self.dir, name)

    def inv(self, d):
        t = (np.asarray(d) - self.d_sky) / (self.d_girl - self.d_sky)
        inv = 1 / self.y_sky + t * (1 / self.y_girl - 1 / self.y_sky)
        return np.clip(inv, 1 / self.y_sky, 1 / self.y_min)

    def point(self, u, v, y):
        return Vector(((u - 0.5) * self.sx * y, y, (0.5 - v) * self.sz * y))

    def depth(self, u, v):
        """(u, v) 处最前面那层的距离：人物上取人物的，其余取背景的。"""
        d = sample(self.disp, u, v) if sample(self.alpha, u, v) > 0.5 else sample(self.disp_bg, u, v)
        return float(1 / self.inv(d))

    def uv_of(self, p):
        """世界坐标 -> 原始机位下的插画坐标。"""
        return p.x / (self.sx * p.y) + 0.5, 0.5 - p.z / (self.sz * p.y)

    def layer(self, name, inv, mat, box=(0, 0, 1, 1), grid=480, margin=0.0):
        """一张起伏的网格：顶点 (u, v) 沿原始机位的视线放到 1/inv 的距离，UV 就是插画坐标。
        margin 把网格往插画外多铺一圈（贴图 EXTEND 拉边缘像素），镜头稍微出界时不至于露底。"""
        u0, v0, u1, v1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
        nx = grid
        ny = max(2, int(round(grid * (v1 - v0) / (u1 - u0) / self.aspect)))
        U, V = np.meshgrid(np.linspace(u0, u1, nx), np.linspace(v0, v1, ny))
        Y = 1 / sample(inv, np.clip(U, 0, 1), np.clip(V, 0, 1))
        verts = np.stack([(U - 0.5) * self.sx * Y, Y, (0.5 - V) * self.sz * Y], -1).reshape(-1, 3)
        idx = np.arange(nx * ny).reshape(ny, nx)
        faces = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
        ob = mesh_obj(name, verts, faces, mat)
        uvl = ob.data.uv_layers.new(name="UVMap")
        lv = np.empty(len(ob.data.loops), np.int32)
        ob.data.loops.foreach_get("vertex_index", lv)
        uv = np.stack([U.ravel(), 1 - V.ravel()], -1)
        uvl.data.foreach_set("uv", uv[lv].ravel().astype(np.float32))
        # 每个顶点的插画坐标，变形（deform）按它取权重、算位移
        for nm, val in (("pu", U.ravel()), ("pv", V.ravel())):
            at = ob.data.attributes.new(nm, "FLOAT", "POINT")
            at.data.foreach_set("value", val.astype(np.float32))
        print(f"layer {name}: {nx}x{ny} vertices, {Y.min():.2f}..{Y.max():.1f} m", flush=True)
        return ob

    def bg_inv(self, smooth=2):
        return blur(self.inv(self.disp_bg), smooth)

    def girl_inv(self, relief=0.5, smooth=3):
        """人物层：人物内部的起伏按 relief 收向中位距离（太立体会走形），人物外面把边缘的深度往外推。"""
        mask = self.alpha > 0.5
        inv = self.inv(self.disp)
        med = np.median(inv[mask])
        inv = med + (inv - med) * relief
        return blur(grow(inv, mask, 24), smooth)

    def girl_box(self, pad=0.03):
        b = self.meta["girl_bbox"]
        return (max(b[0] - pad, 0), max(b[1] - pad, 0), min(b[2] + pad, 1), min(b[3] + pad, 1))


# ---------------------------------------------------------------- 节点小工具

class B(kit.G):
    """kit.G 加上 1~3 个输入的标量 / 向量运算，常量直接写数。"""

    def _in(self, sock, x):
        if x is None:
            return
        if isinstance(x, (int, float)):
            sock.default_value = (x, x, x) if sock.type == "VECTOR" else x
        elif isinstance(x, (tuple, list, Vector)):
            sock.default_value = tuple(x)
        else:
            self.link(x, sock)

    def m(self, op, *xs, clamp=False):
        n = self.tree.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate(xs):
            self._in(n.inputs[i], x)
        return n.outputs[0]

    def v(self, op, *xs):
        n = self.tree.nodes.new("ShaderNodeVectorMath")
        n.operation = op
        for i, x in enumerate(xs):
            self._in(n.inputs[3] if (op == "SCALE" and i == 1) else n.inputs[i], x)
        return n.outputs[1] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs[0]

    def xyz(self, x, y, z):
        n = self.tree.nodes.new("ShaderNodeCombineXYZ")
        for i, c in enumerate((x, y, z)):
            self._in(n.inputs[i], c)
        return n.outputs[0]

    def sep(self, vec):
        n = self.tree.nodes.new("ShaderNodeSeparateXYZ")
        self.link(vec, n.inputs[0])
        return n.outputs

    def group(self, ng, **inputs):
        kind = "GeometryNodeGroup" if self.tree.bl_idname == "GeometryNodeTree" else "ShaderNodeGroup"
        n = self.tree.nodes.new(kind)
        n.node_tree = ng
        for k, x in inputs.items():
            self._in(n.inputs[k], x)
        return n.outputs


def new_group(name, kind, inputs=(), outputs=()):
    """inputs / outputs: [(name, socket_type, default)]。返回 (group, B, 输入节点, 输出节点)。"""
    ng = bpy.data.node_groups.new(name, kind)
    for nm, typ, dflt in inputs:
        kit._iface(ng, nm, "INPUT", typ, dflt)
    for nm, typ, _ in outputs:
        kit._iface(ng, nm, "OUTPUT", typ)
    g = B(ng)
    return ng, g, g.node("NodeGroupInput"), g.node("NodeGroupOutput")


def material(name, method="DITHERED"):
    mt = bpy.data.materials.new(name)
    if mt.node_tree is None:
        mt.use_nodes = True
    mt.surface_render_method = method
    nt = mt.node_tree
    nt.nodes.clear()
    return mt, B(nt), nt.nodes.new("ShaderNodeOutputMaterial")


def image(path, colorspace="sRGB"):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def tex(g, img, vector=None, interp="Linear", extension="EXTEND"):
    n = g.node("ShaderNodeTexImage")
    n.image = img
    n.interpolation = interp
    n.extension = extension
    if vector is not None:
        g.link(vector, n.inputs["Vector"])
    return n


# ---------------------------------------------------------------- 时间和音频数据

class Audio:
    """逐帧的数值存成一张浮点贴图：每帧一行、每个量一列，帧数太多时折成 K 块并排（GPU 贴图边长有上限）。
    着色器里用 self.at(g, 列名)、Geometry Nodes 里用 self.at_gn(g, 列名) 取当前帧的值。

    cols: {名字: 长度为 n_frames 的数组}；spec 是 (n_frames, bands)，列名 spec0..spec{bands-1}。
    """

    ROWS = 4096

    def __init__(self, fps, cols, spec=None):
        self.fps = fps
        names, data = [], []
        if spec is not None:
            for i in range(spec.shape[1]):
                names.append(f"spec{i}")
                data.append(spec[:, i])
        for k, a in cols.items():
            names.append(k)
            data.append(np.asarray(a, np.float32))
        n = min(len(a) for a in data)
        data = np.stack([a[:n] for a in data], 1).astype(np.float32)
        self.n, self.C = data.shape
        self.K = int(math.ceil(self.n / self.ROWS))
        self.col = {k: i for i, k in enumerate(names)}
        px = np.zeros((self.ROWS, self.C * self.K, 4), np.float32)
        px[..., 3] = 1
        for b in range(self.K):
            blk = data[b * self.ROWS:(b + 1) * self.ROWS]
            px[:len(blk), b * self.C:(b + 1) * self.C, 0] = blk
        img = bpy.data.images.new("audio", self.C * self.K, self.ROWS, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(px.ravel())
        img.pack()
        self.img = img
        self.data = data
        self._clock = self._clock_group()
        self._sh = self._shader_group()
        self._gn = self._gn_group()

    def value(self, name, frame):
        return float(self.data[min(int(frame), self.n - 1), self.col[name]])

    def _clock_group(self):
        """着色器里的时钟：一个由驱动器写入当前帧的 Value 节点。"""
        ng, g, gi, go = new_group("clock", "ShaderNodeTree", outputs=[("Frame", "NodeSocketFloat", 0),
                                                                     ("Seconds", "NodeSocketFloat", 0)])
        val = g.node("ShaderNodeValue")
        fc = val.outputs[0].driver_add("default_value")
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = "frame"
        g.link(val.outputs[0], go.inputs["Frame"])
        g.link(g.m("DIVIDE", val.outputs[0], float(self.fps)), go.inputs["Seconds"])
        return ng

    def _lookup(self, g, frame, column):
        block = g.m("FLOOR", g.m("DIVIDE", frame, float(self.ROWS)))
        row = g.m("SUBTRACT", frame, g.m("MULTIPLY", block, float(self.ROWS)))
        u = g.m("DIVIDE", g.m("ADD", g.m("MULTIPLY_ADD", block, float(self.C), column), 0.5), float(self.C * self.K))
        v = g.m("DIVIDE", g.m("ADD", row, 0.5), float(self.ROWS))
        return g.xyz(u, v, 0)

    def _shader_group(self):
        ng, g, gi, go = new_group("audio_at", "ShaderNodeTree", inputs=[("Column", "NodeSocketFloat", 0)],
                                  outputs=[("Value", "NodeSocketFloat", 0)])
        frame = g.group(self._clock)["Frame"]
        t = tex(g, self.img, self._lookup(g, frame, gi.outputs["Column"]), "Closest")
        sep = g.node("ShaderNodeSeparateColor")
        g.link(t.outputs["Color"], sep.inputs[0])
        g.link(sep.outputs[0], go.inputs["Value"])
        return ng

    def _gn_group(self):
        ng, g, gi, go = new_group("audio_at_gn", "GeometryNodeTree", inputs=[("Column", "NodeSocketFloat", 0)],
                                  outputs=[("Value", "NodeSocketFloat", 0)])
        frame = g.node("GeometryNodeInputSceneTime").outputs["Frame"]
        t = g.node("GeometryNodeImageTexture")
        t.interpolation = "Closest"
        t.extension = "EXTEND"
        t.inputs["Image"].default_value = self.img
        g.link(self._lookup(g, frame, gi.outputs["Column"]), t.inputs["Vector"])
        sep = g.node("FunctionNodeSeparateColor")
        g.link(t.outputs["Color"], sep.inputs[0])
        g.link(sep.outputs[0], go.inputs["Value"])
        return ng

    def seconds(self, g):
        return g.group(self._clock)["Seconds"]

    def at(self, g, name):
        return g.group(self._sh, Column=float(self.col[name]))["Value"]

    def at_gn(self, g, name):
        return g.group(self._gn, Column=float(self.col[name]))["Value"]


# ---------------------------------------------------------------- 插画层的材质

def painted(name, color, alpha=None, extra=None):
    """插画层：Emission 原样输出贴图；alpha 是遮罩图（或 "self" 用贴图自带的 alpha），有就混 Transparent。
    extra(g, uv, color_socket) -> color_socket，往颜色上加东西（星星闪烁、月晕）。"""
    mt, g, out = material(name)
    uv = g.node("ShaderNodeTexCoord").outputs["UV"]
    # 画外（网格多铺的那一圈）镜像延伸：星空、花田照着镜像出去很自然，EXTEND 会拉出条纹
    t = tex(g, image(color), uv, extension="MIRROR")
    col = t.outputs["Color"]
    if extra:
        col = extra(g, uv, col)
    em = g.node("ShaderNodeEmission")
    g.link(col, em.inputs["Color"])
    shader = em.outputs[0]
    if alpha:
        a = t.outputs["Alpha"] if alpha == "self" else \
            tex(g, image(alpha, "Non-Color"), uv, extension="MIRROR").outputs["Color"]
        mix = g.node("ShaderNodeMixShader")
        g.link(a, mix.inputs[0])
        g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
        g.link(shader, mix.inputs[2])
        shader = mix.outputs[0]
    g.link(shader, out.inputs["Surface"])
    return mt


def sky_extra(pic, audio, stars="stars.png", star_gain=1.4, star_color=(0.75, 0.86, 1.0),
              halo_color=(0.55, 0.72, 1.0)):
    """天空上加两样：星星按各自的相位、频率闪（stars.png：R 亮度，G 相位，B 频率），乘以 audio 的 "stars" 列；
    月亮外面一圈光晕，强度是 audio 的 "halo" 列。"""
    moon = pic.meta.get("moon")

    def f(g, uv, col):
        st = tex(g, image(pic.path(stars), "Non-Color"), uv, "Closest")
        sep = g.node("ShaderNodeSeparateColor")
        g.link(st.outputs["Color"], sep.inputs[0])
        amp, phase, freq = sep.outputs[0], sep.outputs[1], sep.outputs[2]
        t = audio.seconds(g)
        ph = g.m("ADD", g.m("MULTIPLY", t, g.m("MULTIPLY_ADD", freq, 1.4, 0.25)), phase)
        s = g.m("MULTIPLY_ADD", g.m("SINE", g.m("MULTIPLY", ph, TAU)), 0.5, 0.5)
        tw = g.m("MULTIPLY_ADD", g.m("POWER", s, 3.0), 1.3, -0.12)   # 多数时候原样或稍暗，偶尔一亮
        k = g.m("MULTIPLY", g.m("MULTIPLY", tw, amp), g.m("MULTIPLY", audio.at(g, "stars"), star_gain))
        col = g.v("MULTIPLY_ADD", star_color, g.xyz(k, k, k), col)
        if moon:
            mu, mv, mr = moon
            x, y, _ = g.sep(uv)
            du = g.m("SUBTRACT", x, mu)
            dv = g.m("DIVIDE", g.m("SUBTRACT", y, 1 - mv), pic.aspect)
            d = g.m("MAXIMUM", g.m("SUBTRACT", g.v("LENGTH", g.xyz(du, dv, 0)), mr), 0.0)
            near = g.m("EXPONENT", g.m("DIVIDE", d, -0.6 * mr))
            far = g.m("EXPONENT", g.m("DIVIDE", d, -2.5 * mr))
            h = g.m("MULTIPLY", g.m("MULTIPLY_ADD", near, 0.75, g.m("MULTIPLY", far, 0.25)), audio.at(g, "halo"))
            col = g.v("MULTIPLY_ADD", halo_color, g.xyz(h, h, h), col)
        return col
    return f


def glow_mat(name, color, strength, audio=None, gain_col=None, attr=None, additive=False):
    """发光体：颜色 × 强度 ×（audio 的某一列）×（实例属性 attr）。additive=True 时叠加在后面的东西上（流星、标题）。"""
    mt, g, out = material(name, "BLENDED" if additive else "DITHERED")
    k = strength
    if audio and gain_col:
        k = g.m("MULTIPLY", audio.at(g, gain_col), strength)
    if attr:
        a = g.node("ShaderNodeAttribute")
        a.attribute_type = "INSTANCER"
        a.attribute_name = attr
        k = g.m("MULTIPLY", a.outputs["Fac"], k)
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    g._in(em.inputs["Strength"], k)
    shader = em.outputs[0]
    if additive:
        add = g.node("ShaderNodeAddShader")
        g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
        g.link(shader, add.inputs[1])
        shader = add.outputs[0]
    g.link(shader, out.inputs["Surface"])
    return mt


# ---------------------------------------------------------------- 粒子的形状

def petal_mesh(name="petal_src", length=0.026, width=0.016, cup=0.25, segs=14):
    """一片花瓣：尖头的椭圆，中间微微下凹、沿长向弯一点。长在 +Y 方向，原点在中心。UV.y 从根到尖，UV.x 从左到右。"""
    verts, uvs = [(0.0, 0.0, 0.0)], [(0.5, 0.45)]
    for i in range(segs * 2):
        s = i / (segs * 2)
        a = s * TAU
        y = -math.cos(a) * 0.5
        side = math.sin(a)
        x = side * 0.5 * (1 - 0.35 * (y + 0.5)) * (1 - (2 * y) ** 6) ** 0.5
        verts.append((x * width, y * length, 0.0))
        uvs.append((x + 0.5, y + 0.5))
    for i, (x, y, _) in enumerate(verts):
        verts[i] = (x, y, cup * (x * x / width + (y * y) / length * 0.6))
    n = len(verts) - 1
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    ob = mesh_obj(name, verts, faces, hide=True)
    uvl = ob.data.uv_layers.new(name="UVMap")
    lv = np.empty(len(ob.data.loops), np.int32)
    ob.data.loops.foreach_get("vertex_index", lv)
    uvl.data.foreach_set("uv", np.array(uvs, np.float32)[lv].ravel())
    return ob


def petal_mat(name="petal", inner=(0.50, 0.80, 1.0), outer=(0.90, 0.97, 1.0), strength=1.45):
    """插画里那种发亮的淡蓝花瓣：中心偏青、边缘发白，正对镜头时更亮一点。"""
    mt, g, out = material(name)
    uv = g.node("ShaderNodeUVMap").outputs[0]
    x, y, _ = g.sep(uv)
    r = g.v("LENGTH", g.xyz(g.m("MULTIPLY", g.m("SUBTRACT", x, 0.5), 2.0), g.m("SUBTRACT", y, 0.45), 0))
    mix = g.node("ShaderNodeMix")
    mix.data_type = "RGBA"
    g.link(g.m("POWER", g.m("MINIMUM", r, 1.0), 1.5), kit.sock(mix.inputs, "Factor", "VALUE"))
    kit.sock(mix.inputs, "A", "RGBA").default_value = (*inner, 1)
    kit.sock(mix.inputs, "B", "RGBA").default_value = (*outer, 1)
    lw = g.node("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.4
    k = g.m("MULTIPLY_ADD", g.m("SUBTRACT", 1.0, lw.outputs["Facing"]), 0.5, strength * 0.75)
    a = g.node("ShaderNodeAttribute")
    a.attribute_type = "INSTANCER"
    a.attribute_name = "rnd"
    k = g.m("MULTIPLY", k, g.m("MULTIPLY_ADD", a.outputs["Fac"], 0.5, 0.75))
    em = g.node("ShaderNodeEmission")
    g.link(kit.sock(mix.outputs, "Result", "RGBA"), em.inputs["Color"])
    g.link(k, em.inputs["Strength"])
    g.link(em.outputs[0], out.inputs["Surface"])
    return mt


def ico(name, radius=1.0, subdiv=2, hide=True):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return link(bpy.data.objects.new(name, me), hide)


# ---------------------------------------------------------------- Geometry Nodes：漂流的粒子

def drift(name, src, audio, count, box_min, box_size, wind, size, seed=0, size_var=0.4, flutter=0.15,
          rate=0.7, spin=1.2, density="density", clock="wind", edge=0.05, tilt=0.0):
    """count 个粒子在一个盒子里漂：位置 = 随机初始位置 + wind × 时钟 + 摆动，出了盒子从对面回来（盒子要比画面大，
    回卷才看不见）。时钟是 audio 的 clock 列（风大时走得快的“风时间”），density 列（0..1）决定开着的粒子比例。
    tilt：盒子沿 Y 每米把 Z 抬高多少（贴着往远处降下去的花田飘）。
    每个实例存两个属性给着色器：rnd（0..1 随机）和 flick（0..1 闪烁）。"""
    ng, g, gi, go = new_group(name, "GeometryNodeTree", inputs=[("Geometry", "NodeSocketGeometry", None)],
                              outputs=[("Geometry", "NodeSocketGeometry", None)])
    pts = g.node("GeometryNodePoints", {"Count": count}).outputs[0]
    idx = g.node("GeometryNodeInputIndex").outputs[0]

    def rand(lo, hi, k, vec=True):
        n = g.node("FunctionNodeRandomValue")
        n.data_type = "FLOAT_VECTOR" if vec else "FLOAT"
        kind = "VECTOR" if vec else "VALUE"
        kit.sock(n.inputs, "Min", kind).default_value = (lo,) * 3 if vec else lo
        kit.sock(n.inputs, "Max", kind).default_value = (hi,) * 3 if vec else hi
        g.link(idx, kit.sock(n.inputs, "ID"))
        kit.sock(n.inputs, "Seed").default_value = seed * 10 + k
        return kit.sock(n.outputs, "Value", kind)

    r0, rs, ph, ax = rand(0, 1, 0), rand(0.6, 1.4, 1), rand(0, TAU, 2), rand(-1, 1, 3)
    rsz, rnd = rand(1 - size_var, 1 + size_var, 4, False), rand(0, 1, 5, False)
    tau = audio.at_gn(g, clock)
    t = g.node("GeometryNodeInputSceneTime").outputs["Seconds"]
    p = g.v("MULTIPLY_ADD", r0, tuple(box_size), tuple(box_min))
    p = g.v("ADD", p, g.v("MULTIPLY", g.v("SCALE", tuple(wind), tau), rs))
    # 摆动：三个轴各一条正弦，频率随粒子变
    arg = g.v("ADD", g.v("SCALE", g.v("MULTIPLY", rs, (rate, rate * 0.7, rate * 1.3)), tau), ph)
    p = g.v("ADD", p, g.v("MULTIPLY", g.v("SINE", arg), (flutter, flutter * 0.5, flutter)))
    hi = tuple(a + b for a, b in zip(box_min, box_size))
    p = g.v("WRAP", p, hi, tuple(box_min))
    # 靠近盒子边缘时缩小，回卷的那一下就看不见了
    f = g.v("DIVIDE", g.v("SUBTRACT", p, tuple(box_min)), tuple(box_size))
    e = g.v("MINIMUM", f, g.v("SUBTRACT", (1, 1, 1), f))
    ex, ey, ez = g.sep(e)
    fade = g.m("DIVIDE", g.m("MINIMUM", g.m("MINIMUM", ex, ey), ez), edge, clamp=True)
    # density：序号小于 density × count 的开着，交界处 4% 的粒子渐变
    dens = audio.at_gn(g, density)
    on = g.m("DIVIDE", g.m("SUBTRACT", g.m("MULTIPLY", dens, float(count)), idx), 0.04 * count + 1, clamp=True)
    scale = g.m("MULTIPLY", g.m("MULTIPLY", g.m("MULTIPLY", rsz, size), fade), on)
    if tilt:
        p = g.v("ADD", p, g.xyz(0.0, 0.0, g.m("MULTIPLY", g.sep(p)[1], tilt)))
    sp = g.node("GeometryNodeSetPosition")
    g.link(pts, sp.inputs["Geometry"])
    g.link(p, sp.inputs["Position"])
    base = g.node("FunctionNodeEulerToRotation")
    g.link(ph, base.inputs[0])
    _, rs_y, _ = g.sep(rs)
    ph_x, _, ph_z = g.sep(ph)
    aa = g.node("FunctionNodeAxisAngleToRotation")
    g.link(g.v("NORMALIZE", ax), aa.inputs["Axis"])
    g.link(g.m("MULTIPLY_ADD", g.m("MULTIPLY", rs_y, spin), tau, ph_x), aa.inputs["Angle"])
    rot = g.node("FunctionNodeRotateRotation")
    g.link(base.outputs[0], rot.inputs["Rotation"])
    g.link(aa.outputs[0], rot.inputs["Rotate By"])
    oi = g.node("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = src
    iop = g.node("GeometryNodeInstanceOnPoints")
    g.link(sp.outputs[0], iop.inputs["Points"])
    g.link(oi.outputs["Geometry"], iop.inputs["Instance"])
    g.link(rot.outputs[0], iop.inputs["Rotation"])
    g.link(g.xyz(scale, scale, scale), iop.inputs["Scale"])
    geo = iop.outputs[0]
    flick = g.m("MULTIPLY_ADD", g.m("SINE", g.m("ADD", g.m("MULTIPLY", t, g.m("MULTIPLY_ADD", rnd, 3.0, 1.2)),
                                                 ph_z)), 0.5, 0.5)
    for nm, val in (("rnd", rnd), ("flick", flick)):
        st = g.node("GeometryNodeStoreNamedAttribute")
        st.data_type = "FLOAT"
        st.domain = "INSTANCE"
        st.inputs["Name"].default_value = nm
        g.link(geo, st.inputs["Geometry"])
        g.link(val, st.inputs["Value"])
        geo = st.outputs[0]
    g.link(geo, go.inputs["Geometry"])
    ob, _ = kit.gn_object(name, ng)
    return ob


# ---------------------------------------------------------------- 人物的局部变形

DEFORM = dict(hair=0.007, hair_freq=(0.30, 0.53), ear=0.008, tail=(0.22, 0.08), tail_period=(3.4, 1.9),
              dress=0.0025, mouth_x=0.35, breath=0.004)


def deform(ob, pic, audio, prep=None, amp=None):
    """人物层的网格按 onepic_prep.py rig 的权重图局部变形（像 Live2D），贴图跟着网格走：
    - 头发、丝带：从发根往下传的波，跟着风时间（audio 的 wind 列）摆，幅度乘 sway 列；
    - 尾巴：绕根部转，越往尖转得越多（tail_s），两个周期叠加；
    - 耳朵：audio 的 earl / earr 列（抖一下的衰减振荡）；
    - 裙摆：横向的慢波；
    - 嘴：以嘴为中心上下伸缩、嘴角横向跟一点，伸缩量是 audio 的 mouth 列（负的是合一点）；
    - 呼吸：胸口和肩膀按 rig 的 breath 权重，随 audio 的 breath 列（0..1，1 是吸满，0.5 是插画本来的样子）抬起、
      落下，头几乎不动。没有这列或这张权重图就不动。整个人一起伸缩会连头一起上下晃，看着假。
    位移在插画坐标里算，再按顶点的距离换成米（u 方向 sx·Y，v 方向 sz·Y）。"""
    prep = prep or pic.dir
    A = dict(DEFORM, **(amp or {}))
    rig = np.load(os.path.join(prep, "rig.npz"))
    info = json.load(open(os.path.join(prep, "rig.json")))
    breathe = "breath" in rig.files and "breath" in audio.col
    me = ob.data
    pu = np.empty(len(me.vertices), np.float32)
    pv = np.empty(len(me.vertices), np.float32)
    me.attributes["pu"].data.foreach_get("value", pu)
    me.attributes["pv"].data.foreach_get("value", pv)
    for key in ("hair", "ear_l", "ear_r", "tail", "tail_s", "dress", "mouth") + (("breath",) if breathe else ()):
        at = me.attributes.new("w_" + key, "FLOAT", "POINT")
        at.data.foreach_set("value", sample(rig[key], np.clip(pu, 0, 1), np.clip(pv, 0, 1)).astype(np.float32))

    ng, g, gi, go = new_group("deform", "GeometryNodeTree", inputs=[("Geometry", "NodeSocketGeometry", None)],
                              outputs=[("Geometry", "NodeSocketGeometry", None)])

    def attr(name):
        n = g.node("GeometryNodeInputNamedAttribute")
        n.data_type = "FLOAT"
        n.inputs["Name"].default_value = name
        return kit.sock(n.outputs, "Attribute", "VALUE")

    def wave(phase_time, freq, k, offset=0.0):
        return g.m("SINE", g.m("SUBTRACT", g.m("MULTIPLY", phase_time, TAU * freq),
                                g.m("MULTIPLY_ADD", attr("pv"), k, -offset)))

    t = g.node("GeometryNodeInputSceneTime").outputs["Seconds"]
    tau = audio.at_gn(g, "wind")
    sway = audio.at_gn(g, "sway")
    u, v = attr("pu"), attr("pv")
    # 头发：两条传播的正弦叠加，发梢落后于发根
    f1, f2 = A["hair_freq"]
    wh = g.m("MULTIPLY", g.m("MULTIPLY", attr("w_hair"), A["hair"]), sway)
    du = g.m("MULTIPLY", wh, g.m("ADD", g.m("MULTIPLY", wave(tau, f1, 7.0), 0.65),
                                  g.m("MULTIPLY", wave(tau, f2, 11.0, 1.7), 0.35)))
    dv = g.m("MULTIPLY", wh, g.m("MULTIPLY", wave(tau, (f1 + f2) / 1.6, 9.0, 0.6), 0.25))
    # 耳朵
    ear = g.m("ADD", g.m("MULTIPLY", attr("w_ear_l"), audio.at_gn(g, "earl")),
              g.m("MULTIPLY", attr("w_ear_r"), audio.at_gn(g, "earr")))
    du = g.m("MULTIPLY_ADD", ear, A["ear"], du)
    dv = g.m("MULTIPLY_ADD", ear, -0.3 * A["ear"], dv)
    # 尾巴：绕根部转（在等比的坐标里转，再换回 u）
    bu, bv = info["tail_base"]
    p1, p2 = A["tail_period"]
    swing = g.m("ADD", g.m("MULTIPLY", g.m("SINE", g.m("MULTIPLY", t, TAU / p1)), A["tail"][0]),
                g.m("MULTIPLY", g.m("SINE", g.m("ADD", g.m("MULTIPLY", t, TAU / p2), 1.1)), A["tail"][1]))
    alpha = g.m("MULTIPLY", g.m("MULTIPLY", attr("w_tail"), g.m("POWER", attr("w_tail_s"), 1.2)),
                g.m("MULTIPLY", swing, g.m("MULTIPLY_ADD", sway, 0.4, 0.8)))
    x = g.m("MULTIPLY", g.m("SUBTRACT", u, bu), pic.aspect)
    y = g.m("SUBTRACT", v, bv)
    ca, sa = g.m("COSINE", alpha), g.m("SINE", alpha)
    xr = g.m("SUBTRACT", g.m("MULTIPLY", x, ca), g.m("MULTIPLY", y, sa))
    yr = g.m("ADD", g.m("MULTIPLY", x, sa), g.m("MULTIPLY", y, ca))
    du = g.m("ADD", du, g.m("DIVIDE", g.m("SUBTRACT", xr, x), pic.aspect))
    dv = g.m("ADD", dv, g.m("SUBTRACT", yr, y))
    # 裙摆
    du = g.m("ADD", du, g.m("MULTIPLY", g.m("MULTIPLY", attr("w_dress"), A["dress"]),
                            g.m("MULTIPLY", sway, g.m("SINE", g.m("SUBTRACT", g.m("MULTIPLY", tau, TAU * 0.25),
                                                                     g.m("MULTIPLY", u, 9.0))))))
    # 嘴
    mu, mv = info["mouth"]
    mo = g.m("MULTIPLY", attr("w_mouth"), audio.at_gn(g, "mouth"))
    du = g.m("ADD", du, g.m("MULTIPLY", g.m("MULTIPLY", mo, A["mouth_x"]), g.m("SUBTRACT", u, mu)))
    dv = g.m("ADD", dv, g.m("MULTIPLY", mo, g.m("SUBTRACT", v, mv)))
    # 呼吸：吸气时往上（v 变小）
    if breathe:
        br = g.m("MULTIPLY", g.m("SUBTRACT", audio.at_gn(g, "breath"), 0.5), A["breath"])
        dv = g.m("SUBTRACT", dv, g.m("MULTIPLY", attr("w_breath"), br))
    # 插画坐标的位移 -> 米：u 方向 sx·Y，v 方向（向下）-sz·Y
    py = g.sep(g.node("GeometryNodeInputPosition").outputs[0])[1]
    off = g.xyz(g.m("MULTIPLY", du, g.m("MULTIPLY", py, pic.sx)), 0.0,
                g.m("MULTIPLY", dv, g.m("MULTIPLY", py, -pic.sz)))
    sp = g.node("GeometryNodeSetPosition")
    g.link(gi.outputs["Geometry"], sp.inputs["Geometry"])
    g.link(off, sp.inputs["Offset"])
    g.link(sp.outputs[0], go.inputs["Geometry"])
    mod = ob.modifiers.new("deform", "NODES")
    mod.node_group = ng
    return mod


# ---------------------------------------------------------------- 月亮周围的频谱

def spectrum_ring(pic, audio, bands, y=None, inner=1.3, length=(0.04, 0.6), width=0.028, color=(0.72, 0.85, 1.0),
                  strength=1.3, gain="ring", pulse=None, pulse_amount=0.08, tilt=None, top=None):
    """2 × bands 根细柱，从月亮下方沿两侧对称长到上方：低频在下，高频在上。长度单位是月亮半径。
    整圈的大小乘 audio 的 gain 列（0 时收起来）；pulse 是 audio 的一列（0..1），整圈的半径跟着它鼓起来，
    最多大 pulse_amount（低音的心跳）。
    tilt = (k, 角度°)：朝那个方向的柱子拉长，最多 1 + k 倍，背面的不变（0° 朝右，−90° 朝下）。
    top：插画的 v，朝上的柱子不伸到这条线以上（月亮贴着画面上边时用）；是软上限，tanh 压缩，不会硬切。"""
    mu, mv, mr = pic.meta["moon"]
    y = y or pic.y_sky * 0.97
    c = pic.point(mu, mv, y)
    R = mr * pic.sx * y                      # 月亮半径（米）
    src = ico("ring_bar_src", 1.0, 2)
    src.data.materials.append(glow_mat("ring", color, strength, audio, "energy_glow"))
    ng, g, gi, go = new_group("ring", "GeometryNodeTree", inputs=[("Geometry", "NodeSocketGeometry", None)],
                              outputs=[("Geometry", "NodeSocketGeometry", None)])
    n2 = 2 * bands
    pts = g.node("GeometryNodePoints", {"Count": n2}).outputs[0]
    idx = g.node("GeometryNodeInputIndex").outputs[0]
    left = g.m("GREATER_THAN", idx, bands - 0.5)
    b = g.m("ADD", g.m("MULTIPLY", g.m("SUBTRACT", 1.0, left), idx),
            g.m("MULTIPLY", left, g.m("SUBTRACT", n2 - 1.0, idx)))
    frac = g.m("DIVIDE", g.m("ADD", b, 0.5), float(bands))
    right_th = g.m("MULTIPLY_ADD", frac, math.pi, -math.pi / 2)
    left_th = g.m("MULTIPLY_ADD", frac, -math.pi, 1.5 * math.pi)
    th = g.m("ADD", g.m("MULTIPLY", g.m("SUBTRACT", 1.0, left), right_th), g.m("MULTIPLY", left, left_th))
    # 每根柱子查自己那一列：列号 = spec0 的列 + b
    v = g.group(audio._gn, Column=g.m("ADD", b, float(audio.col["spec0"])))["Value"]
    gain_v = audio.at_gn(g, gain)
    L = g.m("MULTIPLY", g.m("MULTIPLY_ADD", g.m("POWER", v, 1.3), (length[1] - length[0]) * R, length[0] * R), gain_v)
    if tilt:
        k, deg = tilt
        toward = g.m("MAXIMUM", g.m("COSINE", g.m("SUBTRACT", th, math.radians(deg))), 0.0)
        L = g.m("MULTIPLY", L, g.m("MULTIPLY_ADD", toward, k, 1.0))
    r0 = inner * R
    if pulse:
        r0 = g.m("MULTIPLY", g.m("MULTIPLY_ADD", audio.at_gn(g, pulse), pulse_amount, 1.0), inner * R)
    if top is not None:
        # 顶线到环心的高度（米）除以 sin θ 是这根柱子能到的半径；朝下的柱子 sin 压到 1e-3，上限大到等于没有
        z_top = (mv - top) * pic.sz * y
        avail = g.m("SUBTRACT", g.m("DIVIDE", z_top, g.m("MAXIMUM", g.m("SINE", th), 1e-3)), r0)
        Lc = g.m("MAXIMUM", avail, length[0] * R)
        L = g.m("MULTIPLY", Lc, g.m("TANH", g.m("DIVIDE", L, Lc)))
    rr = g.m("ADD", r0, g.m("MULTIPLY", L, 0.5))
    pos = g.v("ADD", tuple(c), g.xyz(g.m("MULTIPLY", g.m("COSINE", th), rr), 0.0, g.m("MULTIPLY", g.m("SINE", th), rr)))
    sp = g.node("GeometryNodeSetPosition")
    g.link(pts, sp.inputs["Geometry"])
    g.link(pos, sp.inputs["Position"])
    rot = g.node("FunctionNodeEulerToRotation")
    g.link(g.xyz(0.0, g.m("MULTIPLY", th, -1.0), 0.0), rot.inputs[0])
    oi = g.node("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = src
    iop = g.node("GeometryNodeInstanceOnPoints")
    g.link(sp.outputs[0], iop.inputs["Points"])
    g.link(oi.outputs["Geometry"], iop.inputs["Instance"])
    g.link(rot.outputs[0], iop.inputs["Rotation"])
    w = g.m("MULTIPLY", width * R * 0.5, gain_v)
    g.link(g.xyz(g.m("MAXIMUM", g.m("MULTIPLY", L, 0.5), 1e-4), w, w), iop.inputs["Scale"])
    g.link(iop.outputs[0], go.inputs["Geometry"])
    ob, _ = kit.gn_object("ring", ng)
    return ob


# ---------------------------------------------------------------- 流星

def meteors(pic, events, fps, y=150.0, color=(0.8, 0.9, 1.0), strength=6.0):
    """events: [(开始秒, u, v, 方向角度°, 长度(画面宽的比例), 持续秒)]。每颗一个物体：头沿方向走，尾巴先拉长后收短。"""
    # 细长的带子：头在 x = 0，尾在 x = -1；宽度往尾巴收细，亮度用顶点色 fade 从头到尾渐暗
    n = 24
    verts, faces, fac = [], [], []
    for i in range(n + 1):
        s = i / n
        w = 0.004 + 0.012 * s ** 2
        verts += [(s - 1.0, 0, -w), (s - 1.0, 0, w)]
        fac += [s ** 2.2, s ** 2.2]
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    mt, g, out = material("meteor", "BLENDED")
    col = g.node("ShaderNodeVertexColor")
    col.layer_name = "fade"
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    g.link(g.m("MULTIPLY", g.sep(col.outputs["Color"])[0], strength), em.inputs["Strength"])
    add = g.node("ShaderNodeAddShader")
    g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    g.link(add.outputs[0], out.inputs["Surface"])
    obs = []
    width_m = pic.sx * y
    for k, (t0, u, v, ang, length, dur) in enumerate(events):
        ob = mesh_obj(f"meteor_{k}", verts, faces, mt)
        ca = ob.data.color_attributes.new("fade", "FLOAT_COLOR", "POINT")
        ca.data.foreach_set("color", np.repeat(np.array(fac, np.float32), 4))
        a = math.radians(ang)
        d = Vector((math.cos(a), 0, math.sin(a)))
        L = length * width_m
        start = pic.point(u, v, y)
        ob.rotation_euler = (0, -a, 0)
        f0, f1 = int(t0 * fps), int((t0 + dur) * fps)
        frames = list(range(f0 - 1, f1 + 2))
        locs, sx = [], []
        for f in frames:
            s = min(max((f - f0) / max(f1 - f0, 1), 0), 1)
            head = start + d * (L * 1.6 * s)
            locs.append(head)
            # 尾巴：前 40% 拉长，后面收短；首尾两帧缩成 0
            grow_ = min(s / 0.4, 1) * (1 - max(s - 0.6, 0) / 0.4)
            sx.append(L * grow_ if f0 <= f <= f1 else 0.0)
        for i in range(3):
            kit.fcurve(ob, "location", i, frames, [p[i] for p in locs])
        kit.fcurve(ob, "scale", 0, frames, sx)
        kit.fcurve(ob, "scale", 1, frames, [1.0] * len(frames))
        kit.fcurve(ob, "scale", 2, frames, [y / 40 if x > 0 else 0.0 for x in sx])
        obs.append(ob)
    return obs


# ---------------------------------------------------------------- 立在空中的字

def text_obj(body, font_path, size, loc, align="CENTER", spacing=1.0, mat=None):
    cu = bpy.data.curves.new("text", "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font_path, check_existing=True)
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    ob = bpy.data.objects.new(f"text_{body[:8]}", cu)
    ob.location = loc
    ob.rotation_euler = (math.pi / 2, 0, 0)   # 字面朝 -Y，对着镜头
    if mat:
        cu.materials.append(mat)
    return link(ob)


def fading_mat(name, color, strength):
    """可以淡入淡出的字：Emission 和 Transparent 按 obj["a"]（对象属性）混合。"""
    mt, g, out = material(name, "BLENDED")
    a = g.node("ShaderNodeAttribute")
    a.attribute_type = "OBJECT"
    a.attribute_name = "a"
    em = g.node("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    mix = g.node("ShaderNodeMixShader")
    g.link(a.outputs["Fac"], mix.inputs[0])
    g.link(g.node("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    g.link(em.outputs[0], mix.inputs[2])
    g.link(mix.outputs[0], out.inputs["Surface"])
    return mt


def key_prop(ob, prop, keys, interp="BEZIER"):
    """keys: [(帧, 值)] 写到对象的自定义属性 ob[prop]。"""
    ob[prop] = keys[0][1]
    kit.fcurve(ob, f'["{prop}"]', 0, [k[0] for k in keys], [k[1] for k in keys], interp)


# ---------------------------------------------------------------- 镜头

def ease(s, kind="inout"):
    s = min(max(s, 0.0), 1.0)
    if kind == "linear":
        return s
    if kind == "out":
        return 1 - (1 - s) ** 3
    if kind == "in":
        return s ** 3
    return s * s * (3 - 2 * s) if kind == "smooth" else (4 * s ** 3 if s < 0.5 else 1 - (-2 * s + 2) ** 3 / 2)


POSE_KEYS = ("u", "v", "zoom", "dx", "dy", "dz", "roll", "fstop", "blur")


def pchip(ts, ys, t):
    """单调三次插值（Fritsch-Carlson）：速度连续，不会冲过关键帧的值，在极值处自然停一下；两端速度为 0。"""
    ts, ys = np.asarray(ts, float), np.asarray(ys, float)
    h = np.diff(ts)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(ys) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    t = np.clip(np.asarray(t, float), ts[0], ts[-1])
    k = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
    s = (t - ts[k]) / h[k]
    return ((2 * s ** 3 - 3 * s ** 2 + 1) * ys[k] + (s ** 3 - 2 * s ** 2 + s) * h[k] * m[k]
            + (-2 * s ** 3 + 3 * s ** 2) * ys[k + 1] + (s ** 3 - s ** 2) * h[k] * m[k + 1])


def lerp_pose(a, b, s):
    out = dict(a)
    for k in POSE_KEYS:
        if k in a or k in b:
            out[k] = a.get(k, b.get(k)) + (b.get(k, a.get(k)) - a.get(k, b.get(k))) * s
    out["focus"] = b.get("focus", a.get("focus"))
    return out


class Camera:
    """镜头：一串 shot（开始秒、结束秒、起始 pose、结束 pose、缓动），逐帧写成关键帧。

    pose：u, v 是画面中心对准的插画坐标；zoom 是相对原始画幅的放大（1 = 整张画）；dx, dy, dz 是机位离开原点的
    米数（横移、推近、升降，带来视差）；roll 度；focus 对焦点 (u, v)（默认就是 u, v 那一点），或 focus_m 直接给对焦米数；
    blur 是无穷远处的虚化直径占画面宽的比例（默认 0.003），按焦距和对焦距离换算成光圈；也可以直接给 fstop。
    kick：{帧: 0..1} 重拍上的轻推（焦距乘 1 + kick × amount）。
    """

    def __init__(self, pic, fps, n_frames):
        self.pic, self.fps, self.n = pic, fps, n_frames
        cam = bpy.data.cameras.new("cam")
        cam.sensor_fit = "HORIZONTAL"
        cam.sensor_width = pic.sensor
        cam.lens = pic.lens
        cam.clip_start = 0.05
        cam.clip_end = 2000
        cam.dof.use_dof = True
        cam.dof.aperture_blades = 7
        self.ob = link(bpy.data.objects.new("cam", cam))
        bpy.context.scene.camera = self.ob
        self.poses = []
        self.near_dof = 1.2       # 景深按这个距离以外的东西算

    def pose_at(self, shots, t):
        for t0, t1, a, b, kind in shots:
            if t0 <= t < t1:
                return lerp_pose(a, b, ease((t - t0) / (t1 - t0), kind))
        return dict(shots[-1][3]) if t >= shots[-1][1] else dict(shots[0][2])

    def solve(self, p):
        """pose -> (机位, 旋转, 焦距, 对焦距离)。"""
        pic = self.pic
        c = Vector((p.get("dx", 0.0), p.get("dy", 0.0), p.get("dz", 0.0)))
        tgt = pic.point(p["u"], p["v"], pic.depth(p["u"], p["v"]))
        d = tgt - c
        rot = d.to_track_quat("-Z", "Y").to_euler("XYZ")
        if p.get("roll"):
            rot.rotate_axis("Z", math.radians(p["roll"]))
        lens = pic.lens * p.get("zoom", 1.0) * d.length / tgt.length
        return c, rot, lens, self.focus_dist(p, c)

    def focus_dist(self, p, c):
        """对焦距离：focus_m 直接给米数（比如对在镜头前的标题上），否则是 focus 那一点（默认画面中心）到机位的距离。"""
        if "focus_m" in p:
            return p["focus_m"]
        fu, fv = p.get("focus") or (p["u"], p["v"])
        return (self.pic.point(fu, fv, self.pic.depth(fu, fv)) - c).length

    def path(self, keys):
        """一条不断开的镜头：keys = [(秒, pose)]，每个参数用 pchip 在关键帧之间平滑过渡。对焦按屈光度（1/距离）插值，
        从月亮换到脸时焦点是一路拉过来的，不会跳。每个参数只在写了它的关键帧之间插值：只写 focus / focus_m / blur
        的关键帧单独管对焦，镜头不会在那里停一下。返回每帧的 (pose, 对焦距离)。"""
        t = np.arange(self.n) / self.fps

        def track(ks):
            ks = sorted(ks, key=lambda k: k[0])
            if len(ks) == 1:
                return np.full(len(t), float(ks[0][1]))
            return pchip([a for a, _ in ks], [b for _, b in ks], t)
        cols = {}
        for name in POSE_KEYS:
            ks = [(k[0], k[1][name]) for k in keys if name in k[1]]
            if ks:
                cols[name] = track(ks)
        diopter = []
        for tk, p in keys:
            if "focus" in p or "focus_m" in p:
                i = min(int(round(tk * self.fps)), self.n - 1)
                c = Vector([float(cols[a][i]) if a in cols else 0.0 for a in ("dx", "dy", "dz")])
                diopter.append((tk, 1 / self.focus_dist(dict(p, u=cols["u"][i], v=cols["v"][i]), c)))
        fd = 1 / track(diopter)
        return [({k: float(v[i]) for k, v in cols.items()}, float(fd[i])) for i in range(self.n)]

    def bake(self, shots=None, keys=None, kick=None, kick_amount=0.012, shake=0.0):
        """shots：分段的镜头（见类说明）；或 keys：一条连续的路径（见 path()）。"""
        fr = list(range(self.n))
        loc, rot, lens, focus, fstop = [], [], [], [], []
        prev = None
        smooth = self.path(keys) if keys else None
        for f in fr:
            if smooth:
                p, fd_ = smooth[f]
                c, r, ln, _ = self.solve(p)
                fd = fd_
            else:
                p = self.pose_at(shots, f / self.fps)
                c, r, ln, fd = self.solve(p)
            if prev is not None:
                r = r.to_matrix().to_euler("XYZ", prev)
            prev = r
            if kick:
                ln *= 1 + kick_amount * kick.get(f, 0.0)
            loc.append(c)
            rot.append(r)
            lens.append(ln)
            focus.append(fd)
            # blur：场景里（near_dof 米到无穷远）最大的虚化直径占画面宽的比例。弥散圆 = f²/N × |1/对焦 - 1/距离|，
            # 取两头里大的那个反解光圈：对焦在远处时近处的人物也不会糊成一片
            worst = max(abs(1 / fd - 1 / self.near_dof), 1 / fd)
            n_ = (ln / 1000) ** 2 * worst / (p.get("blur", 0.003) * self.pic.sensor / 1000)
            fstop.append(p.get("fstop", min(max(n_, 1.4), 64)))
            self.poses.append((c, r, ln))
        for i in range(3):
            kit.fcurve(self.ob, "location", i, fr, [x[i] for x in loc])
            kit.fcurve(self.ob, "rotation_euler", i, fr, [x[i] for x in rot])
        kit.fcurve(self.ob.data, "lens", 0, fr, lens)
        kit.fcurve(self.ob.data, "dof.focus_distance", 0, fr, focus)
        kit.fcurve(self.ob.data, "dof.aperture_fstop", 0, fr, fstop)
        if shake:   # 很轻的手持感
            for i, ph in ((0, 0.0), (2, 31.0)):
                kit.noise(self.ob, "rotation_euler", i, math.radians(shake), scale=90.0, phase=ph)

    def project(self, f, p):
        """第 f 帧，世界坐标 p 在画面上的位置（0..1，左下为原点；合成器的光束源用这个）。"""
        c, r, ln = self.poses[f]
        q = r.to_matrix().transposed() @ (Vector(p) - c)
        if q.z >= -1e-6:
            return None
        x = q.x / -q.z * ln / self.pic.sensor + 0.5
        y = q.y / -q.z * ln / (self.pic.sensor / self.pic.aspect) + 0.5
        return x, y

    def check(self, step=6, near=1.2, margin=0.03):
        """每 step 帧看一次：画面四角在天空和近处花丛两个距离上，有没有超出插画（加 margin）。返回出界的 (秒, 量)。"""
        pic = self.pic
        bad = []
        for f in range(0, self.n, step):
            c, r, ln = self.poses[f]
            m = r.to_matrix()
            hw = pic.sensor / 2 / ln
            hh = hw / pic.aspect
            worst = 0.0
            for sx_ in (-1, 1):
                for sy_ in (-1, 1):
                    d = m @ Vector((sx_ * hw, sy_ * hh, -1.0))
                    for yy in (pic.y_sky * 0.95, near):
                        if d.y <= 1e-6:
                            continue
                        if yy == near and sy_ > 0:
                            continue      # 近处只有画面下方是花丛
                        s = (yy - c.y) / d.y
                        u, v = pic.uv_of(c + d * s)
                        if yy == near and v < 0.6:
                            continue      # 那个角看到的是天空，不是近处的花
                        worst = max(worst, -u - margin, u - 1 - margin, -v - margin, v - 1 - margin)
            if worst > 0:
                bad.append((round(f / self.fps, 2), round(worst, 3)))
        return bad


# ---------------------------------------------------------------- 合成

def compositor(bloom=0.2, threshold=0.8, size=0.6, beam_size=0.3, beam_threshold=0.8):
    """辉光（Bloom）-> 月光光束 -> 一点色散。光束只从月亮那一块发出：画面乘一个跟着月亮走的椭圆遮罩再做 Sun Beams，
    只把光束加回去，白裙子、亮的花不会拉出光束，强度可以开大。返回 (tree, 光束节点, 遮罩节点)：
    光束的 Sun Position、Strength 和遮罩的 Position（0..1，左下为原点）、Size（直径，按画面宽算）逐帧写入。"""
    s = bpy.context.scene
    tree = bpy.data.node_groups.new("post", "CompositorNodeTree")
    s.compositing_node_group = tree
    kit._iface(tree, "Image", "OUTPUT", "NodeSocketColor")
    g = kit.G(tree)
    rl = g.node("CompositorNodeRLayers")
    glare = g.node("CompositorNodeGlare")
    def setup(node, values):
        for nm, val in values:
            try:
                kit.sock(node.inputs, nm).default_value = val
            except (KeyError, TypeError, ValueError) as e:
                print("glare", nm, e)
    setup(glare, (("Type", "Bloom"), ("Threshold", threshold), ("Strength", bloom), ("Size", size), ("Quality", "High")))
    g.link(rl.outputs["Image"], kit.sock(glare.inputs, "Image"))

    def mix(blend, a, b):
        n = g.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        kit.sock(n.inputs, "Factor", "VALUE").default_value = 1.0
        g.link(a, kit.sock(n.inputs, "A", "RGBA"))
        g.link(b, kit.sock(n.inputs, "B", "RGBA"))
        return kit.sock(n.outputs, "Result", "RGBA")
    mask = g.node("CompositorNodeEllipseMask")
    size_in = kit.sock(mask.inputs, "Size")
    for i in range(len(size_in.default_value)):
        size_in.default_value[i] = 0.0
    beams = g.node("CompositorNodeGlare")
    setup(beams, (("Type", "Sun Beams"), ("Threshold", beam_threshold), ("Strength", 0.0), ("Size", beam_size),
                  ("Jitter", 0.2), ("Quality", "High")))
    g.link(mix("MULTIPLY", glare.outputs[0], mask.outputs[0]), kit.sock(beams.inputs, "Image"))
    lit = mix("ADD", glare.outputs[0], kit.sock(beams.outputs, "Glare"))
    lens = g.node("CompositorNodeLensdist")
    kit.sock(lens.inputs, "Dispersion").default_value = 0.004
    g.link(lit, kit.sock(lens.inputs, "Image"))
    g.link(lens.outputs[0], g.node("NodeGroupOutput").inputs[0])
    s.render.use_compositing = True
    return tree, beams, mask


def video_output(path, crf="PERC_LOSSLESS"):
    """直接出 H.264 分段（4K 的 PNG 序列太占盘）。最终的颗粒、歌词、音轨在 ffmpeg 合成时加。"""
    s = bpy.context.scene
    im = s.render.image_settings
    im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    ff = s.render.ffmpeg
    ff.format = "MPEG4"
    ff.codec = "H264"
    ff.constant_rate_factor = crf
    ff.ffmpeg_preset = "GOOD"
    ff.gopsize = s.render.fps
    ff.audio_codec = "NONE"
    s.render.filepath = path
