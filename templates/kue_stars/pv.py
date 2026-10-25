"""模板：kue 的星空花田插画（4K 精修版）的一图流 PV，换歌、换歌词和文字就能出一支新的。
从 cases/kimishira/scripts/pv.py 来：插画、分层、人物的摆动、粒子、镜头的路子都一样，跟歌有关的全读这首歌的
<case>/song.json（歌名、歌手、文件）和 <case>/plan.json（plan.py 排的段落、镜头、流星、标题时机）。
星环默认是花哨样式（RING=fancy：拉开的 11 道轨道、七种光点、缓慢变化的星芒、横向光条，加上月亮当星系核的大星系，
scripts/onepic_fancy.py）；RING=classic 是 kimishira 成片里那种。

在 AutoDL 上（CASE 是这首歌的目录；一般用 render.sh / preview.sh，不直接跑）：
    CASE=cases/<歌> $B -b --factory-startup -P templates/kue_stars/pv.py -- build        # -> <case>/renders/scene.blend
    CASE=cases/<歌> $B -b <case>/renders/scene.blend -P templates/kue_stars/pv.py -- stills 5 70
    CASE=cases/<歌> $B -b <case>/renders/scene.blend -P templates/kue_stars/pv.py -s 4200 -e 4799 -j 2 -a -- clip <名字>
FX 同 kimishira（默认 bokeh）。插画处理好的东西在 ART_PREP（默认 characters/kue/art/stars_103_prep）。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(1, os.path.join(ROOT, "scripts"))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import kit  # noqa: E402
import onepic as op  # noqa: E402
import onepic_fancy as of  # noqa: E402
import star_ring as sr  # noqa: E402

CASE = os.path.join(ROOT, os.environ.get("CASE", ""))
if not os.path.exists(os.path.join(CASE, "song.json")):
    sys.exit(f"CASE={os.environ.get('CASE')!r}：找不到 song.json")
SONG = json.load(open(os.path.join(CASE, "song.json"), encoding="utf-8"))
PLAN = json.load(open(os.path.join(CASE, "plan.json"), encoding="utf-8"))
RENDERS = os.path.join(CASE, "renders")
AUDIO = os.path.join(CASE, "audio")

FPS = 60
PREP = os.path.join(ROOT, os.environ.get("ART_PREP", "characters/kue/art/stars_103_prep"))
BANDS = os.path.join(AUDIO, "bands.npz")
FONTS = os.path.join(ROOT, "fonts")
BLEND = os.environ.get("BLEND", os.path.join(RENDERS, "scene.blend"))
SECTIONS = [tuple(s) for s in PLAN["sections"]]       # (名字, 开始秒, 能量, 花瓣, 光点, 频谱环, 光束)
TITLE_END = PLAN["title_end"]

FX = {x for x in os.environ.get("FX", SONG.get("fx", "bokeh")).split(",") if x}
RING = os.environ.get("RING", SONG.get("ring", "fancy"))

# 跟插画走的（换歌不用动）
FACE = (0.620, 0.352)
MOON_DOWN = 0.035      # 天空整层往下挪这么多（画面高的比例）：插画里月亮贴着上边，旋律盘的顶上没地方
TITLE_Y = 0.5          # 开头的竖排标题离镜头 0.5 米：对焦在它上面时，人物和背景都在焦外
GLINTS = [(0.667, 0.283), (0.705, 0.313), (0.625, 0.114)]   # 发夹的花、丝带上的花、头顶的蝴蝶结（插画坐标）
LAYER_GAIN = {"near": 2.2, "far": 0.8}
BEAM_GAIN, BEAM_MASK, STREAK_GAIN = 2.0, 2.8, 0.8


def camera_keys():
    """plan.json 的镜头：机位关键帧（u、v、zoom、dx、dy、dz）和对焦关键帧（focus_m 是 "title" 时对在镜头前的标题上，
    focus 是 "face" 时对在脸上）。"""
    keys = []
    for t, k in PLAN["camera"]:
        if "zoom" in k:
            keys.append((t, dict(k)))
        elif k.get("focus_m") == "title":
            keys.append((t, dict(blur=k.get("blur", 0.014), focus_m=TITLE_Y)))
        else:
            keys.append((t, dict(blur=k.get("blur", 0.003), focus=FACE)))
    return keys


def ear_moves(n, seed):
    """两只耳朵的动作 (earl, earr)，-1..1：一直很慢地摆一点，隔 5~13 秒抽一下（3 Hz 的衰减振荡），一半两只一起。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FPS
    ears = [0.1 * np.sin(op.TAU * t / rng.uniform(4, 7) + rng.uniform(0, op.TAU)) for _ in range(2)]

    def twitch(ear, t0, amp):
        s = t - t0
        attack = np.clip(s / 0.08, 0, 1)
        env = np.sin(op.TAU * 3.0 * s) * np.exp(-s / 0.28) * attack * attack * (3 - 2 * attack)
        ears[ear] += amp * np.where((s >= 0) & (s < 1.2), env, 0.0)

    tt = rng.uniform(2, 8)
    while tt < n / FPS:
        amp = rng.uniform(0.7, 1.0) * rng.choice((-1.0, 1.0))
        if rng.uniform() < 0.5:
            twitch(0, tt, amp)
            twitch(1, tt + rng.uniform(0, 0.08), amp)
        else:
            twitch(int(rng.integers(2)), tt, amp)
        tt += rng.uniform(5, 13)
    return [e.astype(np.float32) for e in ears]


def twinkle(n, seed, every=(3.0, 8.0), dur=0.6):
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
    out = {}
    k = np.arange(int(0.35 * FPS))
    env = np.exp(-k / (0.09 * FPS))
    for tb in downbeats:
        f0 = int(round(float(tb) * FPS))
        for i, e in enumerate(env):
            if f0 + i < n:
                out[f0 + i] = max(out.get(f0 + i, 0.0), float(e))
    return out


def mouth_moves(n, seed=4):
    """嘴：两条慢正弦（周期 3.3、5.1 秒）叠加，慢慢变小变大；跟着人声走会一直张着。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FPS
    s = (0.6 * np.sin(op.TAU * t / 3.3 + rng.uniform(0, op.TAU))
         + 0.4 * np.sin(op.TAU * t / 5.1 + rng.uniform(0, op.TAU)))
    return (-0.10 + 0.14 * s).astype(np.float32)


def breathing(n):
    """呼吸（0..1）：每句歌词开唱前 0.5 秒吸一口，唱的时候慢慢呼出去，不唱的时候 4.6 秒一次平静地起伏。
    没有歌词就一直平静地起伏。"""
    marks = []
    path = os.path.join(CASE, SONG["lyrics"]) if SONG.get("lyrics") else ""
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
            if m and " : " not in m.group(3):
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


def beat_columns(n, d):
    """拍子网格上的 beat（拍点上 1、0.16 秒衰减）和 since（离上一拍几秒）：花哨星环的光头闪、脉冲星的冲击波。"""
    P, phi = float(d["grid_beat"]), float(d["grid_phase"])
    t = np.arange(n) / FPS
    since = np.where(t >= phi, (t - phi) % P, 9.0)
    return np.exp(-since / 0.16).astype(np.float32), since.astype(np.float32)


def section_arrays(n, d):
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
    gust = 0.85 + 0.15 * (0.6 * np.sin(op.TAU * t / 11.0 + 0.7) + 0.4 * np.sin(op.TAU * t / 17.3 + 2.9))
    earl, earr = ear_moves(n, 3)
    k = int(0.3 * FPS) | 1
    pulse = np.convolve(np.pad(bass ** 2, (k // 2, k // 2), mode="edge"), np.ones(k) / k, "valid")
    beat, since = beat_columns(n, d)
    return {
        "energy": cols["energy"],
        "density": cols["petals"],
        "motes": cols["motes"],
        "ring": cols["ring"],
        "wind": np.cumsum(speed) / FPS,
        "breeze": np.cumsum(0.85 + 0.3 * cols["energy"]) / FPS,
        "stars": 0.85 + 0.45 * high,
        "heart": bass ** 2,
        "pulse": pulse,
        "halo": 0.06 + 0.04 * cols["energy"] + 0.08 * pulse * (0.4 + 0.6 * cols["energy"]),
        "energy_glow": 0.5 + 0.7 * cols["energy"] + 0.15 * bass,
        "sway": (0.75 + 0.3 * cols["energy"]) * gust,
        "mouth": mouth_moves(n),
        "earl": earl,
        "earr": earr,
        "breath": breathing(n),
        "rim": 0.45 + 0.55 * bass ** 2,
        "beat": beat,
        "since": since,
    }, cols["beams"]


def pick_meteors(pic, cam, sky):
    """每颗流星：在它出现那一刻镜头看得到的天空上半部里挑起点，往远离人物的方向斜着划下。"""
    from mathutils import Vector
    rng = np.random.default_rng(11)
    events = []
    for t in PLAN["meteors"]:
        f = min(int(t * FPS), cam.n - 1)
        c, r, ln = cam.poses[f]
        z = ln / pic.lens
        best = None
        for _ in range(200):
            sx, sy = rng.uniform(0.15, 0.85), rng.uniform(0.55, 0.92)
            dv = r.to_matrix() @ Vector(((sx - 0.5) * pic.sensor / ln, (sy - 0.5) * pic.sensor / pic.aspect / ln, -1.0))
            p = c + dv * ((150.0 - c.y) / dv.y)
            u, v = pic.uv_of(p)
            if not (0.02 < u < 0.98 and 0.02 < v < 0.98):
                continue
            if op.sample(sky, u, v) > 0.9 and op.sample(sky, u, min(v + 0.08 / z, 0.99)) > 0.5:
                best = (u, v)
                break
        if best is None:
            continue
        u, v = best
        ang = rng.uniform(200, 220) if u < 0.55 else rng.uniform(-40, -20)
        events.append((t, u, v, ang, rng.uniform(0.10, 0.17) / z, rng.uniform(0.55, 0.85)))
    return events


def title(pic):
    """开头月亮旁边竖排的歌名（song.json 的 title），一个字一个字浮现，下面一行小字是 artist，到 TITLE_END 淡完。
    8 个字以内是 kimishira 的大小，再长按字数缩小，排得下就一列。字放在镜头前 TITLE_Y 米，开头对焦在字上。"""
    mu, mv, _ = pic.meta["moon"]
    y = TITLE_Y
    k = y / 40.0
    mat = op.fading_mat("title", (0.93, 0.96, 1.0), 1.7)
    chars = [ch for ch in SONG["title"] if not ch.isspace()]
    s = min(1.0, 8.0 / max(len(chars), 1))
    size, line = 1.1 * k * s, 1.18 * k * s
    top = mv - 0.055
    x0 = op.Vector(pic.point(mu + 0.155, top, y))
    f = lambda sec: int(round(sec * FPS))   # noqa: E731
    out0, out1 = TITLE_END - 2.0, TITLE_END
    font = os.path.join(FONTS, SONG.get("title_font", "yumindb.ttf"))
    obs = []
    for i, ch in enumerate(chars):
        loc = x0 + op.Vector((0, 0, -i * line))
        ob = op.text_obj(ch, font, size, loc, mat=mat)
        t_in = 1.2 + min(0.22, 1.8 / len(chars)) * i
        op.key_prop(ob, "a", [(0, 0.0), (f(t_in), 0.0), (f(t_in + 0.9), 1.0), (f(out0), 1.0), (f(out1), 0.0)])
        kit.fcurve(ob, "location", 2, [0, f(t_in), f(t_in + 1.2)], [loc.z - 0.12 * k, loc.z - 0.12 * k, loc.z], "BEZIER")
        obs.append(ob)
    if SONG.get("artist"):
        sub_loc = x0 + op.Vector((0, 0, -len(chars) * line - 0.3 * k))
        sub = op.text_obj(SONG["artist"], os.path.join(FONTS, SONG.get("artist_font", "DINNextLTPro-Light.ttf")),
                          0.36 * k, sub_loc, spacing=1.3, mat=op.fading_mat("title_sub", (0.85, 0.9, 1.0), 1.3))
        op.key_prop(sub, "a", [(0, 0.0), (f(3.6), 0.0), (f(4.6), 0.85), (f(out0), 0.85), (f(out1), 0.0)])
        obs.append(sub)
    return obs


def layers(pic, audio, moon_tex):
    """插画的各层（prep/meta.json 的 layers），最后面那层带星星闪烁和月晕、整个往下挪 MOON_DOWN。返回人物那层。"""
    char = None
    for i, L in enumerate(pic.meta["layers"]):
        name = L["name"]
        extra, shift = None, None
        if i == 0:
            extra, shift = op.sky_extra(pic, audio, moon=moon_tex), (0.0, MOON_DOWN)
        elif name == "char" and "rim" in FX:
            mu, mv, _ = pic.meta["moon"]
            dd = np.array([mu - FACE[0], (FACE[1] - mv) / pic.aspect])
            extra = op.rim_extra(L["color"], dd / np.linalg.norm(dd), pic.aspect, strength=0.8, audio=audio, gain_col="rim")
        color = L["color"] if os.path.isabs(L["color"]) else pic.path(L["color"])
        alpha = L["alpha"]               # "self" 是用贴图自带的 alpha
        if alpha and alpha != "self" and not os.path.isabs(alpha):
            alpha = pic.path(alpha)
        mat = op.painted(name, color, alpha=alpha, extra=extra, shift=shift)
        if name == "char":
            char = pic.layer(name, pic.girl_inv(), mat, box=pic.girl_box(), grid=560, margin=0.05)
            continue
        if name == "far":
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
    moon_tex = tuple(pic.meta["moon"])
    pic.meta["moon"] = [moon_tex[0], moon_tex[1] + MOON_DOWN, moon_tex[2]]
    cols, beams = section_arrays(n, d)
    audio = op.Audio(FPS, cols, spec=d["spec"].astype(np.float32))

    char = layers(pic, audio, moon_tex)
    op.deform(char, pic, audio, amp={"ear": 0.010}, clock="breeze")

    petal = op.petal_mesh()
    petal.data.materials.append(op.petal_mat())
    op.drift("petals", petal, audio, 1400, (-5.0, 0.45, -3.0), (10.0, 7.5, 8.0), (0.30, -0.05, -0.10), 1.0,
             seed=1, size_var=0.45, flutter=0.12, rate=0.9, spin=1.6, density="density")
    mote = op.ico("mote_src", 1.0, 2)
    mote.data.materials.append(op.glow_mat("mote", (0.80, 0.92, 1.0), 2.6, attr="flick"))
    op.drift("motes", mote, audio, 320, (-9.0, 2.0, -0.35), (18.0, 22.0, 1.3), (0.02, -0.02, 0.05), 0.006,
             seed=2, size_var=0.5, flutter=0.08, rate=0.5, spin=0.0, density="motes", tilt=-0.12)
    if "bokeh" in FX:
        bp = op.petal_mesh("bokeh_src")
        bp.data.materials.append(op.bokeh_petal_mat())
        op.drift("bokeh", bp, audio, 26, (-0.85, 0.5, -0.5), (1.7, 0.8, 1.0), (0.025, 0.0, 0.035), 2.5,
                 seed=5, size_var=0.35, flutter=0.03, rate=0.35, spin=0.5, density="motes", edge=0.12)
    sky = np.load(os.path.join(PREP, "sky.npy"))
    spec = d["spec"].astype(np.float32)
    if RING == "fancy":
        ring = sr.Ring(spec, d["loud"], FPS, float(d["grid_beat"]), float(d["grid_phase"]),
                       radii=sr.FANCY_RADII, turns=sr.FANCY_TURNS)
        of.star_ring_fancy(pic, ring, sr.fancy(ring), audio)
        of.galaxy(pic, audio, sky)
    elif RING == "classic":
        op.star_ring(pic, sr.Ring(spec, d["loud"], FPS, float(d["grid_beat"]), float(d["grid_phase"])))
    title(pic)
    if "glint" in FX:
        op.glints(pic, GLINTS, [twinkle(n, 20 + i) for i in range(len(GLINTS))])

    cam = op.Camera(pic, FPS, n)
    cam.bake(keys=camera_keys(), kick=kicks(n, d["downbeats"]) if "kick" in FX else None, kick_amount=0.004)
    bad = cam.check(margin=0.07)
    spans = []
    for t, w in bad:
        if spans and t - spans[-1][1] < 0.3:
            spans[-1] = [spans[-1][0], t, max(spans[-1][2], w)]
        else:
            spans.append([t, t, w])
    print("camera out of the picture:", [f"{a:.1f}-{b:.1f}s +{w:.3f}" for a, b, w in spans if w > 0.008], flush=True)
    op.meteors(pic, pick_meteors(pic, cam, sky), FPS)

    src = op.beam_source({"far"})
    tree, beam, bmask, streak, moonmask = op.compositor(streak="streak" in FX, beam_layer=src)
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
        strength.append(BEAM_GAIN * beams[f] * (0.85 + 0.3 * float(cols["pulse"][f])) if inside else 0.0)
        ssize.append(2 * 1.25 * r)
        msize.append(2 * 1.08 * r)
        sstr.append(STREAK_GAIN * (0.3 + 0.7 * float(cols["energy"][f])) * (0.85 + 0.3 * float(cols["pulse"][f]))
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

    op.video_output(os.path.join(RENDERS, "chunks", "c_#####"))
    os.makedirs(RENDERS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("saved", BLEND, flush=True)


def stills(seconds):
    """在已存的场景里渲几张静帧（PNG）到 <case>/renders/stills/，RES 默认 50（1080p）。"""
    s = bpy.context.scene
    im = s.render.image_settings
    im.media_type = "IMAGE"
    im.file_format = "PNG"
    im.color_mode = "RGB"
    s.render.resolution_percentage = int(os.environ.get("RES", 50))
    out = os.path.join(RENDERS, "stills")
    os.makedirs(out, exist_ok=True)
    for sec in seconds:
        s.frame_set(int(round(float(sec) * FPS)))
        s.render.filepath = os.path.join(out, f"t_{float(sec):06.2f}.png")
        bpy.ops.render.render(write_still=True)
        print("still", s.render.filepath, flush=True)


def clip(name):
    """几秒的 PNG 小样：RES（默认 50）、SAMPLES（默认 16），到 <case>/renders/clips/<name>/；帧号是 60 fps 的。"""
    s = bpy.context.scene
    s.render.resolution_percentage = int(os.environ.get("RES", 50))
    s.eevee.taa_render_samples = int(os.environ.get("SAMPLES", 16))
    im = s.render.image_settings
    im.media_type = "IMAGE"
    im.file_format = "PNG"
    im.color_mode = "RGB"
    s.render.filepath = os.path.join(RENDERS, "clips", name, "f_#####")


def preview():
    """快速预览：960×540、30 fps（隔一帧渲一帧）、8 采样，到 <case>/renders/preview/。"""
    s = bpy.context.scene
    s.render.resolution_percentage = 25
    s.eevee.taa_render_samples = 8
    s.render.fps = FPS // 2
    s.render.ffmpeg.constant_rate_factor = "MEDIUM"
    s.render.filepath = os.path.join(RENDERS, "preview", "p_#####")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv and argv[0] == "stills":
        stills(argv[1:])
    elif argv and argv[0] == "preview":
        preview()
    elif argv and argv[0] == "clip":
        clip(argv[1])
    else:
        build()
