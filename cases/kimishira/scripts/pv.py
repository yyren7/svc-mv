"""君の知らない物語 的一图流 PV：kue 的星空花田插画（4K 精修版）在 Blender 里摆成 2.5D 场景，镜头和特效跟着歌走。

在 AutoDL 上（素材先用 scripts/onepic_prep.py 做到 art/prep/，音频特征 audio/bands.npz 来自 scripts/audio_bands.py）：
    B=/root/autodl-tmp/tools/blender-5.2.2-linux-x64/blender
    $B -b --factory-startup -P cases/kimishira/scripts/pv.py -- build                    # 搭场景 -> renders/scene.blend
    $B -b cases/kimishira/renders/scene.blend -P cases/kimishira/scripts/pv.py -- stills 5 20 70   # 这几秒的静帧
    bash cases/kimishira/scripts/render.sh                                              # 分段渲染、合成成片
可选的特效用环境变量 FX 开，逗号隔开（FX=bokeh,rim,kick,streak,glint）：
    bokeh   镜头前的虚焦光斑        rim     月亮那一侧她的轮廓光，跟着心跳
    kick    重拍上镜头轻推 0.4%     streak  月亮的水平光条          glint   发饰上偶尔闪一下的四芒星
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import kit  # noqa: E402
import onepic as op  # noqa: E402

FPS = 60
PREP = os.path.join(C.ART, "prep")
BANDS = os.path.join(C.AUDIO, "bands.npz")
FONTS = os.path.join(C.ROOT, "fonts")
BLEND = os.path.join(C.RENDERS, "scene.blend")

# 段落：开始秒都落在重拍上。能量管花瓣的风、频谱环的亮度；其余几列是各特效的开度（0..1）。
SECTIONS = [
    # 名字         开始     能量  花瓣  光点  频谱环 光束
    ("open",       0.00,  0.25, 0.12, 0.55, 0.45, 0.22),
    ("open_band",  8.75,  0.45, 0.30, 0.55, 0.75, 0.18),
    ("intro",     15.30,  0.75, 0.60, 0.50, 1.0, 0.12),
    ("a1",        28.57,  0.30, 0.22, 0.70, 0.75, 0.10),
    ("a1_band",   42.03,  0.50, 0.35, 0.65, 0.85, 0.10),
    ("b1",        54.93,  0.60, 0.45, 0.60, 0.9, 0.12),
    ("ch1",       65.98,  0.90, 0.80, 0.55, 1.0, 0.15),
    ("brk1",      98.55,  0.55, 0.50, 0.60, 0.9, 0.18),
    ("a2",       102.92,  0.40, 0.30, 0.70, 0.8, 0.10),
    ("b2",       127.32,  0.60, 0.45, 0.60, 0.9, 0.12),
    ("ch2",      136.03,  0.95, 0.85, 0.55, 1.0, 0.15),
    ("drop",     175.07,  0.50, 0.40, 0.65, 0.8, 0.12),
    ("ch2b",     181.48,  1.00, 0.90, 0.55, 1.0, 0.15),
    ("solo",     203.12,  0.85, 0.60, 0.50, 1.0, 0.18),
    ("c",        226.95,  0.20, 0.12, 0.90, 0.7, 0.15),
    ("c_swell",  239.98,  0.55, 0.45, 0.80, 0.85, 0.15),
    ("c_end",    244.58,  0.40, 0.35, 0.80, 0.8, 0.15),
    ("ch3",      250.95,  1.00, 1.00, 0.60, 1.0, 0.15),
    ("ch3_soft", 264.40,  0.70, 0.60, 0.70, 0.9, 0.12),
    ("ch3_b",    273.12,  1.00, 1.00, 0.60, 1.0, 0.15),
    ("outro",    321.65,  0.60, 0.40, 0.70, 0.85, 0.18),
    ("end",      330.00,  0.25, 0.12, 0.60, 0.6, 0.22),
]

FX = {x for x in os.environ.get("FX", "").split(",") if x}

FACE = (0.620, 0.352)
MOON = (0.179, 0.142)
MOON_DOWN = 0.035      # 天空整层往下挪这么多（画面高的比例）：插画里月亮贴着上边，频谱盘的顶上没地方
TITLE_Y = 0.5          # 开头的竖排标题离镜头 0.5 米：对焦在它上面时，人物和背景都在焦外
GLINTS = [(0.667, 0.283), (0.705, 0.313), (0.625, 0.114)]   # 发夹的花、丝带上的花、头顶的蝴蝶结（插画坐标）


def P(u, v, zoom, dx=0.0, dy=0.0, dz=0.0):
    return dict(u=u, v=v, zoom=zoom, dx=dx, dy=dy, dz=dz)


def F(blur=0.003, focus=FACE, at=None):
    """只管对焦的关键帧：focus 是插画上的点，at 是米数（对在镜头前的标题上）。"""
    return dict(blur=blur, focus_m=at) if at else dict(blur=blur, focus=focus)


def camera_keys():
    """一条从头到尾不断开的镜头：关键帧放在段落交界，中间平滑过渡（Camera.path 的 pchip）。
    始终是整张画：放大只在 1.04~1.10 倍之间，画面中心只在正中附近漂，不推近人物，整首的氛围是稳的。
    动感来自机位的平移（左右、上下最多约 1.2 厘米）带出的前后景视差：副歌升起一点，主歌左右慢慢挪。
    对焦另走一条：第一帧起就对在镜头前的标题上，人物和背景都在焦外，歌名在虚的星空里浮现；乐队进来、标题淡出时
    再拉回她脸上。开头不先清楚再虚下去：那样像对焦失误。"""
    return [
        # 对焦
        (0.00, F(0.014, at=TITLE_Y)),
        (8.75, F(0.014, at=TITLE_Y)),
        (12.0, F()),
        # 开头：整张画
        (0.00, P(0.47, 0.46, 1.10, dx=-0.006)),
        (8.75, P(0.48, 0.47, 1.09, dx=-0.004)),
        (15.30, P(0.50, 0.48, 1.07)),
        # 前奏、主歌 1：左右慢慢挪
        (28.57, P(0.51, 0.49, 1.05, dx=0.008)),
        (42.03, P(0.51, 0.48, 1.07, dx=0.004)),
        (54.93, P(0.51, 0.48, 1.08, dx=-0.004)),
        # 副歌 1：升起一点
        (65.98, P(0.50, 0.49, 1.05, dz=0.006)),
        (87.32, P(0.49, 0.49, 1.04, dx=-0.008, dz=0.010)),
        (98.55, P(0.49, 0.48, 1.05, dx=-0.010)),
        # 主歌 2
        (102.92, P(0.48, 0.48, 1.07, dx=-0.008)),
        (127.32, P(0.51, 0.48, 1.08, dx=0.004)),
        # 副歌 2
        (136.03, P(0.50, 0.49, 1.05, dz=0.006)),
        (175.07, P(0.50, 0.49, 1.04, dx=0.010, dz=0.010)),
        (181.48, P(0.51, 0.48, 1.06, dx=0.006)),
        # 间奏：往左上的星空和月亮那边偏一点，看流星雨
        (203.12, P(0.50, 0.48, 1.06)),
        (218.00, P(0.47, 0.46, 1.09)),
        (226.95, P(0.47, 0.46, 1.09)),
        # C 段
        (239.98, P(0.50, 0.47, 1.08)),
        (244.58, P(0.50, 0.48, 1.07)),
        # 最后的副歌
        (250.95, P(0.50, 0.49, 1.05, dz=0.008)),
        (273.12, P(0.50, 0.49, 1.04, dx=-0.010)),
        (290.00, P(0.51, 0.48, 1.06, dx=0.006)),
        (305.00, P(0.50, 0.49, 1.05, dz=0.008)),
        # 尾奏：往月亮那边漂一点，淡出
        (321.65, P(0.49, 0.48, 1.05)),
        (332.00, P(0.47, 0.46, 1.07)),
        (337.60, P(0.46, 0.45, 1.08)),
    ]


# 流星出现的秒数 —— 位置在建场景时按当时的镜头在画面里的天空中挑
METEOR_TIMES = [5.0, 17.48, 24.00, 70.20, 81.0, 92.0, 140.37, 150.92, 168.4, 186.0, 196.5,
                205.3, 207.0, 209.7, 211.2, 214.0, 216.2, 217.6, 220.5, 222.6, 224.8,
                233.0, 255.3, 259.6, 277.6, 286.4, 297.3, 306.2, 312.7, 317.0, 333.0]


def ear_moves(n, seed):
    """两只耳朵的动作 (earl, earr)，-1..1，正值是往外、往上张一点。慢，像在听歌，不抽（7 Hz 的抖动太快太突然）：
    一直有一点很慢的摆（周期 4~7 秒、幅度 0.12），隔 6~14 秒转一下：0.45 秒转过去、停 0.25~0.6 秒、0.9 秒回来，
    幅度 ±0.5~1；一半的动作两只耳朵一起（相差不到 0.1 秒），其余各动各的。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FPS
    ears = [0.12 * np.sin(op.TAU * t / rng.uniform(4, 7) + rng.uniform(0, op.TAU)) for _ in range(2)]

    def smooth(x):
        x = np.clip(x, 0, 1)
        return x * x * (3 - 2 * x)

    def turn(ear, t0, amp):
        rise, hold, fall = 0.45, rng.uniform(0.25, 0.6), 0.9
        s = t - t0
        env = np.where(s < rise, smooth(s / rise), np.where(s < rise + hold, 1.0, smooth(1 - (s - rise - hold) / fall)))
        ears[ear] += amp * np.where((s >= 0) & (s <= rise + hold + fall), env, 0.0)

    tt = rng.uniform(2, 8)
    while tt < n / FPS:
        amp = rng.uniform(0.5, 1.0) * rng.choice((-1.0, 1.0))
        if rng.uniform() < 0.5:
            turn(0, tt, amp)
            turn(1, tt + rng.uniform(0, 0.1), amp)
        else:
            turn(int(rng.integers(2)), tt, amp)
        tt += rng.uniform(6, 14)
    return [e.astype(np.float32) for e in ears]


def twinkle(n, seed, every=(3.0, 8.0), dur=0.6):
    """发饰的星光：隔 every 秒闪一下，一次 dur 秒，包络尖一点（sin³）。"""
    rng = np.random.default_rng(seed)
    out = np.zeros(n, np.float32)
    k = np.arange(int(dur * FPS))
    flash = np.sin(np.pi * k / len(k)) ** 3
    t = rng.uniform(1.0, every[1])
    while t < n / FPS:
        f0 = int(t * FPS)
        m = min(len(k), n - f0)
        out[f0:f0 + m] = np.maximum(out[f0:f0 + m], flash[:m])
        t += rng.uniform(*every)
    return out


def kicks(n, downbeats):
    """重拍上镜头的轻推：{帧: 0..1}，拍点上是 1，0.09 秒的指数衰减，持续 0.35 秒。"""
    out = {}
    k = np.arange(int(0.35 * FPS))
    env = np.exp(-k / (0.09 * FPS))
    for tb in downbeats:
        f0 = int(round(float(tb) * FPS))
        for i, e in enumerate(env):
            if f0 + i < n:
                out[f0 + i] = max(out.get(f0 + i, 0.0), float(e))
    return out


def breathing(n):
    """呼吸（0..1，1 是吸满）：每句歌词开唱前 0.5 秒很快吸一口，唱的时候慢慢呼出去；不唱的时候（间奏）按 4.6 秒
    一次平静地起伏。句子的起止取 lyrics.lrc：一句唱到下一个时间标签（空行标的是间奏开始），最长 6 秒。"""
    marks = []
    for line in open(os.path.join(C.AUDIO, "lyrics.lrc"), encoding="utf-8"):
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
        if m and " : " not in m.group(3):          # 跳过「作词 : ...」
            marks.append((int(m.group(1)) * 60 + float(m.group(2)), bool(m.group(3).strip())))
    marks.sort()
    t = np.arange(n) / FPS
    inhale, sing = np.zeros(n, bool), np.zeros(n, bool)
    for (t0, words), (t1, _) in zip(marks, marks[1:] + [(1e9, False)]):
        if words:
            inhale |= (t >= t0 - 0.5) & (t < t0)
            sing |= (t >= t0) & (t < min(t1, t0 + 6.0))
    idle = 0.5 + 0.3 * np.sin(op.TAU * t / 4.6)
    out = np.empty(n, np.float32)
    level, dt = 0.5, 1.0 / FPS
    for i in range(n):
        if inhale[i]:
            level += (1.0 - level) * dt / 0.15
        elif sing[i]:
            level -= level * dt / 3.0
        else:
            level += (idle[i] - level) * dt / 0.8
        out[i] = level
    k = FPS // 5
    return np.convolve(np.pad(out, (k // 2, k - k // 2 - 1), mode="edge"), np.ones(k) / k, "valid")


def section_arrays(n, d):
    """把段落表展开成逐帧的数组，交界处用 1 秒的滑动平均过渡（变化会提前半秒开始，听感上更跟拍）。"""
    t = np.arange(n) / FPS
    names = ("energy", "petals", "motes", "ring", "beams")
    cols = {k: np.zeros(n, np.float32) for k in names}
    for i, (_, t0, *vals) in enumerate(SECTIONS):
        t1 = SECTIONS[i + 1][1] if i + 1 < len(SECTIONS) else 1e9
        m = (t >= t0) & (t < t1)
        for k, val in zip(names, vals):
            cols[k][m] = val
    k = FPS
    for key in cols:
        cols[key] = np.convolve(np.pad(cols[key], (k // 2, k - k // 2 - 1), mode="edge"), np.ones(k) / k, "valid")
    loud, bass, high = d["loud"][:n], d["bass"][:n], d["high"][:n]
    speed = 0.55 + 1.1 * cols["energy"] + 0.35 * loud
    earl, earr = ear_moves(n, 3)
    return {
        "energy": cols["energy"],
        "density": cols["petals"],
        "motes": cols["motes"],
        "ring": cols["ring"],
        "wind": np.cumsum(speed) / FPS,                       # 风时间：风大时走得快
        "stars": 0.85 + 0.45 * high,
        # 心跳：低音的平方，旋律盘（月亮外圈的频谱）跟着鼓起来，月晕跟着亮
        "heart": bass ** 2,
        "halo": 0.056 + 0.056 * cols["energy"] + 0.24 * bass ** 2 * (0.4 + 0.6 * cols["energy"]),
        "energy_glow": 0.45 + 0.8 * cols["energy"] + 0.35 * bass,
        "sway": 0.6 + 0.6 * cols["energy"],                    # 头发、裙摆、尾巴摆动的幅度
        # 嘴：人声快包络 -> 伸缩量；不唱的时候合一点（-0.28），唱得响时再张开一点（+0.18）
        "mouth": -0.28 + 0.46 * np.clip((d["voice"][:n] - 0.30) / 0.6, 0, 1),
        "earl": earl,
        "earr": earr,
        "breath": breathing(n),
        "rim": 0.45 + 0.55 * bass ** 2,                        # 轮廓光跟着心跳
    }, cols["beams"]


def pick_meteors(pic, cam, sky):
    """每颗流星：在它出现那一刻镜头看得到的天空上半部里挑起点，往远离人物的方向斜着划下。"""
    rng = np.random.default_rng(11)
    events = []
    for t in METEOR_TIMES:
        f = min(int(t * FPS), cam.n - 1)
        c, r, ln = cam.poses[f]
        z = ln / pic.lens
        best = None
        for _ in range(200):
            sx, sy = rng.uniform(0.15, 0.85), rng.uniform(0.55, 0.92)     # 画面坐标（左下原点）
            d = r.to_matrix() @ kit_vec((sx - 0.5) * pic.sensor / ln, (sy - 0.5) * pic.sensor / pic.aspect / ln, -1.0)
            p = c + d * ((150.0 - c.y) / d.y)
            u, v = pic.uv_of(p)
            if not (0.02 < u < 0.98 and 0.02 < v < 0.98):
                continue
            if op.sample(sky, u, v) > 0.9 and op.sample(sky, u, min(v + 0.08 / z, 0.99)) > 0.5:
                best = (u, v)
                break
        if best is None:
            continue
        u, v = best
        ang = rng.uniform(200, 220) if u < 0.55 else rng.uniform(-40, -20)   # 左半边往左下，右半边往右下
        events.append((t, u, v, ang, rng.uniform(0.10, 0.17) / z, rng.uniform(0.55, 0.85)))
    return events


def kit_vec(x, y, z):
    from mathutils import Vector
    return Vector((x, y, z))


def title(pic):
    """开头月亮旁边竖排的「君の知らない物語」，一个字一个字浮现，乐队进来后淡出。
    镜头是整张画，字要大一些（约画面宽的 2.7%），离月亮远一点，让开月亮外圈的频谱。
    字放在镜头前 TITLE_Y 米（尺寸按距离缩小，画面上一样大）：开头对焦在字上，后面的人物和背景一起虚下去。"""
    mu, mv, _ = pic.meta["moon"]
    y = TITLE_Y
    k = y / 40.0                          # 下面的尺寸按 40 米处写的
    mat = op.fading_mat("title", (0.93, 0.96, 1.0), 1.7)
    chars = "君の知らない物語"
    size, line = 1.1 * k, 1.18 * k
    top = mv - 0.055
    x0 = op.Vector(pic.point(mu + 0.155, top, y))
    obs = []
    for i, ch in enumerate(chars):
        loc = x0 + op.Vector((0, 0, -i * line))
        ob = op.text_obj(ch, os.path.join(FONTS, "yumindb.ttf"), size, loc, mat=mat)
        t_in = 1.2 + 0.22 * i
        f = lambda s: int(round(s * FPS))   # noqa: E731
        op.key_prop(ob, "a", [(0, 0.0), (f(t_in), 0.0), (f(t_in + 0.9), 1.0), (f(9.6), 1.0), (f(11.6), 0.0)])
        kit.fcurve(ob, "location", 2, [0, f(t_in), f(t_in + 1.2)], [loc.z - 0.12 * k, loc.z - 0.12 * k, loc.z], "BEZIER")
        obs.append(ob)
    sub_loc = x0 + op.Vector((0, 0, -len(chars) * line - 0.3 * k))
    sub = op.text_obj("supercell", os.path.join(FONTS, "DINNextLTPro-Light.ttf"), 0.36 * k, sub_loc, spacing=1.3,
                      mat=op.fading_mat("title_sub", (0.85, 0.9, 1.0), 1.3))
    f = lambda s: int(round(s * FPS))   # noqa: E731
    op.key_prop(sub, "a", [(0, 0.0), (f(3.6), 0.0), (f(4.6), 0.85), (f(9.6), 0.85), (f(11.6), 0.0)])
    return obs + [sub]


# 月光光束：强度 = BEAM_GAIN × 段落表的光束列 × 心跳；光源遮罩是月亮半径的 BEAM_MASK 倍（包住外圈的频谱）
BEAM_GAIN = 2.0
BEAM_MASK = 2.8
STREAK_GAIN = 0.8      # 月亮水平光条（FX=streak）的强度：× (0.3 + 0.7 × 能量) × 心跳

# Depth Anything 把左下、右下角的大花估得比人物还远；按画面它们离镜头最近，这层的 1/距离 乘一下。
# far 整层放平在天空再往后一点（220 / 0.8 = 275 米），在中景花田最远处（220 米）后面，不会重叠打架
LAYER_GAIN = {"near": 2.2, "far": 0.8}


def layers(pic, audio, moon_tex):
    """插画的各层。有 prep/meta.json 的 layers（另外做好的远/中/近/人物分层）就用它；没有就用 onepic_prep.py
    自己做的两层（LaMa 补全的背景 + 人物）。最后面那层带星星闪烁和月晕，贴图整个往下挪 MOON_DOWN（moon_tex 是
    贴图里月亮的位置，pic.meta 里的已经是画面里的）。开了 rim 时人物层带朝月亮的轮廓光。返回人物那层。"""
    spec = pic.meta.get("layers")
    if not spec:
        sky_mat = op.painted("bg", pic.path("plate.png"), extra=op.sky_extra(pic, audio))
        pic.layer("bg", pic.bg_inv(), sky_mat, grid=720, margin=0.04)
        girl_mat = op.painted("girl", pic.path("color.png"), alpha=pic.path("alpha.png"))
        return pic.layer("girl", pic.girl_inv(), girl_mat, box=pic.girl_box(), grid=560)
    char = None
    for i, L in enumerate(spec):
        name = L["name"]
        extra, shift = None, None
        if i == 0:
            extra, shift = op.sky_extra(pic, audio, moon=moon_tex), (0.0, MOON_DOWN)
        elif name == "char" and "rim" in FX:
            # 朝月亮的方向（画面像素坐标，y 朝上）；亮度 0.35 + 0.45 × 心跳
            mu, mv, _ = pic.meta["moon"]
            d = np.array([mu - FACE[0], (FACE[1] - mv) / pic.aspect])
            extra = op.rim_extra(L["color"], d / np.linalg.norm(d), pic.aspect, strength=0.8, audio=audio, gain_col="rim")
        mat = op.painted(name, L["color"], alpha=L["alpha"], extra=extra, shift=shift)
        if name == "char":
            char = pic.layer(name, pic.girl_inv(), mat, box=pic.girl_box(), grid=560, margin=0.05)
            continue
        if name == "far":
            # 远层只有天空和月亮：Depth Anything 把月亮上方、左上方的天空估到 60~100 米，比 213 米处的频谱环还近，
            # 环的左上那一段被挡掉了。镜头只平移一两厘米，天空放平看不出差别
            inv = np.full((2, 2), LAYER_GAIN["far"] / pic.y_sky, np.float32)
        else:
            inv = op.blur(pic.inv(np.load(pic.path(L["disp"]))) * LAYER_GAIN.get(name, 1.0), 2)
        box = (0, 0, 1, 1) if i == 0 else (L["box"][0], max(L["box"][1] - 0.02, 0), L["box"][2], L["box"][3])
        pic.layer(name, inv, mat, box=box, grid=720 if i == 0 else 640, margin=0.08)
    return char


def build():
    s = op.scene(FPS, 3840, 2160, samples=int(os.environ.get("SAMPLES", 32)))
    d = np.load(BANDS)
    n = len(d["loud"])
    s.frame_end = n - 1
    pic = op.Pic(PREP, lens=35.0, y_girl=1.6, y_sky=220.0)
    moon_tex = tuple(pic.meta["moon"])                                   # 贴图里的月亮
    pic.meta["moon"] = [moon_tex[0], moon_tex[1] + MOON_DOWN, moon_tex[2]]   # 画面里的：频谱盘、光束、标题按这个
    cols, beams = section_arrays(n, d)
    audio = op.Audio(FPS, cols, spec=d["spec"].astype(np.float32))

    char = layers(pic, audio, moon_tex)
    op.deform(char, pic, audio, amp={"ear": 0.010})      # 头发、尾巴、耳朵、裙摆、嘴、呼吸；耳朵动得慢，幅度给大一点

    # 粒子
    petal = op.petal_mesh()
    petal.data.materials.append(op.petal_mat())
    op.drift("petals", petal, audio, 1400, (-5.0, 0.45, -3.0), (10.0, 7.5, 8.0), (0.30, -0.05, -0.10), 1.0,
             seed=1, size_var=0.45, flutter=0.12, rate=0.9, spin=1.6, density="density")
    mote = op.ico("mote_src", 1.0, 2)
    mote.data.materials.append(op.glow_mat("mote", (0.80, 0.92, 1.0), 2.6, attr="flick"))
    # 光点贴着花田：花田往远处降下去（约 -0.12 m / m），盒子跟着倾斜
    op.drift("motes", mote, audio, 320, (-9.0, 2.0, -0.35), (18.0, 22.0, 1.3), (0.02, -0.02, 0.05), 0.006,
             seed=2, size_var=0.5, flutter=0.08, rate=0.5, spin=0.0, density="motes", tilt=-0.12)
    if "bokeh" in FX:
        # 镜头前 0.5~1.3 米的虚焦光斑：几十个，慢慢飘、慢慢明灭，镜头一动它们的视差最大
        orb = op.ico("bokeh_src", 1.0, 3)
        orb.data.materials.append(op.bokeh_mat())
        op.drift("bokeh", orb, audio, 40, (-0.85, 0.5, -0.5), (1.7, 0.8, 1.0), (0.025, 0.0, 0.035), 0.016,
                 seed=5, size_var=0.5, flutter=0.03, rate=0.35, spin=0.0, density="motes", edge=0.12)
    # 旋律盘就是月亮：外圈的频谱，低音来时整圈像心跳一样鼓起来。朝右下（人物那边）的柱子拉长到 1.3 倍，像月光
    # 斜着照出来的；左上只压到 0.85 倍（压到 0.4 太短，不压又显得挤）。正上方的柱子软压在 v = 0.035 以下，
    # 整首不出画框（镜头最高到 v ≈ -0.013），辉光也留得下
    op.spectrum_ring(pic, audio, d["spec"].shape[1], length=(0.06, 0.85), width=0.04, strength=1.8, pulse="heart",
                     tilt=(0.3, -50), squeeze=0.15, top=0.035)
    title(pic)
    if "glint" in FX:
        op.glints(pic, GLINTS, [twinkle(n, 20 + i) for i in range(len(GLINTS))])

    cam = op.Camera(pic, FPS, n)
    cam.bake(keys=camera_keys(), kick=kicks(n, d["downbeats"]) if "kick" in FX else None, kick_amount=0.004)
    bad = cam.check(margin=0.07)         # 网格往外多铺了 0.08（镜像延伸）
    spans = []
    for t, w in bad:
        if spans and t - spans[-1][1] < 0.3:
            spans[-1] = [spans[-1][0], t, max(spans[-1][2], w)]
        else:
            spans.append([t, t, w])
    print("camera out of the picture:", [f"{a:.1f}-{b:.1f}s +{w:.3f}" for a, b, w in spans if w > 0.008], flush=True)

    sky = np.load(os.path.join(PREP, "sky.npy"))
    op.meteors(pic, pick_meteors(pic, cam, sky), FPS)

    # 月光光束：只从月亮和外圈的频谱发出（遮罩跟着月亮走），跟低音的心跳一起亮；开了 streak 还有月亮的水平光条
    tree, beam, bmask, streak, moonmask = op.compositor(streak="streak" in FX)
    mu, mv, mr = pic.meta["moon"]
    moon = pic.point(mu, mv, pic.y_sky)
    edge = moon + op.Vector((mr * pic.sx * pic.y_sky, 0, 0))
    pos, strength, size, ssize, sstr, msize = [], [], [], [], [], []
    for f in range(n):
        q, e = cam.project(f, moon), cam.project(f, edge)
        inside = q is not None and -0.1 < q[0] < 1.1 and -0.1 < q[1] < 1.1
        pos.append(q if q else (0.5, 0.5))
        r = (e[0] - q[0]) if inside and e else 0.0
        size.append(2 * BEAM_MASK * r)
        strength.append(BEAM_GAIN * beams[f] * (0.6 + 0.8 * float(cols["heart"][f])) if inside else 0.0)
        ssize.append(2 * 1.25 * r)
        msize.append(2 * 1.08 * r)
        sstr.append(STREAK_GAIN * (0.3 + 0.7 * float(cols["energy"][f])) * (0.6 + 0.8 * float(cols["heart"][f]))
                    if inside else 0.0)
    fr = list(range(n))

    def key2(sock, vals):
        for i in range(2):
            kit.fcurve(tree, sock.path_from_id("default_value"), i, fr, [p[i] for p in vals])
    key2(kit.sock(beam.inputs, "Sun Position"), pos)
    key2(kit.sock(bmask.inputs, "Position"), pos)
    key2(kit.sock(bmask.inputs, "Size"), [(x, x) for x in size])
    kit.fcurve(tree, kit.sock(beam.inputs, "Strength").path_from_id("default_value"), 0, fr, strength)
    key2(kit.sock(moonmask.inputs, "Position"), pos)
    key2(kit.sock(moonmask.inputs, "Size"), [(x, x) for x in msize])
    if streak:
        st, smask = streak
        key2(kit.sock(smask.inputs, "Position"), pos)
        key2(kit.sock(smask.inputs, "Size"), [(x, x) for x in ssize])
        kit.fcurve(tree, kit.sock(st.inputs, "Strength").path_from_id("default_value"), 0, fr, sstr)

    op.video_output(os.path.join(C.RENDERS, "chunks", "c_#####"))   # 5 位帧号，文件名排序就是时间顺序
    os.makedirs(C.RENDERS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved", BLEND, flush=True)


def stills(seconds):
    """在已存的 scene.blend 里渲几张静帧（PNG）到 renders/stills/。"""
    s = bpy.context.scene
    im = s.render.image_settings
    im.media_type = "IMAGE"
    im.file_format = "PNG"
    im.color_mode = "RGB"
    s.render.resolution_percentage = int(os.environ.get("RES", 50))
    out = os.path.join(C.RENDERS, "stills")
    os.makedirs(out, exist_ok=True)
    for sec in seconds:
        s.frame_set(int(round(float(sec) * FPS)))
        s.render.filepath = os.path.join(out, f"t_{float(sec):06.2f}.png")
        bpy.ops.render.render(write_still=True)
        print("still", s.render.filepath, flush=True)


def preview():
    """快速预览：960×540、30 fps（每隔一帧渲一帧）、8 采样。只改设置，渲染由命令行后面的 -s -e -j 2 -a 来做：
        $B -b scene.blend -P pv.py -s 0 -e 5059 -j 2 -a -- preview"""
    s = bpy.context.scene
    s.render.resolution_percentage = 25
    s.eevee.taa_render_samples = 8
    s.render.fps = FPS // 2           # 每隔一帧取一帧，按 30 fps 写进视频，时长不变
    s.render.ffmpeg.constant_rate_factor = "MEDIUM"
    s.render.filepath = os.path.join(C.RENDERS, "preview", "p_#####")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv and argv[0] == "stills":
        stills(argv[1:])
    elif argv and argv[0] == "preview":
        preview()
    else:
        build()
