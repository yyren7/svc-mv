"""星环样式的 2D 小样（不进成片）：用和正片同一套 star_ring.Ring，只画星环的光点和滤镜，几种样式并排比。
在 AutoDL 上：
    $PY cases/kimishira/scripts/ring_poc.py [起始秒 70] [秒数 8]
-> renders/ring_poc/：grid_art.mp4（叠在插画上，人物挡在前面）、grid_black.mp4（黑底），每格 1280×720，
   *_zoom.mp4 是月亮周围放大；<样式>_art.mp4 / <样式>_black.mp4 每种单独一份（1920×1080）。
    A 现在       正片的样式（2D 近似：星芯 + 光晕 + 收细的尾巴），15 道轨道
    B 花哨光点   轨道减到 11 道、往外拉开（内圈原来 1.4、1.6、1.96、2.16 R 挤在一起）；每颗一种：普通、双子星（两颗互绕，
                尾巴拧成两股，中间一道光桥）、火花尾、脉冲星（十字星芒 + 拍点上一圈冲击波）、彗星（宽软尾巴 + 朝外的离子尾）、
                珠串（后面跟三四颗小卫星）、棱彩尾（尾巴沿长度变色、慢慢流动）；所有光头带小星芒，拍点上闪一下
    C B + 大星系  月亮是星系核：两条对数螺旋旋臂铺到 22 R（大半个天空），内暖外蓝、粉色星团团块，一万多颗小星差速转；只在天空上
    D C + 星云丝带 域扭曲噪声的细丝带（粉、青、紫），慢慢流动
    E C + 星芒滤镜 亮点都拉出六芒星芒、横向的蓝色光条（变形宽银幕镜头那种），光层加一点色散
    F C + 吸积环  月亮外一圈转得飞快的亮环，一侧亮一侧暗（多普勒），贴着月亮一道细的光子环，外面一圈淡淡的爱因斯坦环
2D 只是比样式，定了再做进 Blender（docs/onepic.md：比样式时在画面上叠 2D 的光，定了马上做进场景）。"""
import os
import sys
import json
import subprocess
from multiprocessing import Pool

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import star_ring as sr  # noqa: E402

C = os.path.join(ROOT, "cases", "kimishira")
OUT = os.path.join(C, "renders", "ring_poc")
W, H, SS = 1920, 1080, 2            # 每格的大小，画线时 2 倍超采样
FPS_OUT = 30
T0 = float(sys.argv[1]) if len(sys.argv) > 1 else 70.0
LEN = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
VARIANTS = ("A", "B", "C", "D", "E", "F")
LABELS = {"A": "A 现在", "B": "B 花哨光点 + 拉开间距", "C": "C B + 大星系", "D": "D C + 星云丝带",
          "E": "E C + 星芒滤镜", "F": "F C + 吸积环"}
TAU = 2 * np.pi

d = np.load(os.path.join(C, "audio", "bands.npz"))
FPS = int(d["fps"])
BEATS = np.asarray(d["beats"], float)
meta = json.load(open(os.path.join(C, "art", "prep", "meta.json")))
mu, mv, mr = meta["moon"]
CX, CY, R = mu * W, mv * H, mr * W      # 月亮中心、半径（像素）

KINDS = ("普通", "双子", "火花", "脉冲", "彗星", "珠串", "棱彩")
WARM = np.array((1.0, 0.78, 0.45), np.float32)


def make_ring(radii, turns, seed):
    """按给定的轨道建一套 Ring，再给每颗定样式和随机参数。"""
    sr.RADII = np.array(radii, float)
    sr.TURN_BEATS = tuple(turns)
    ring = sr.Ring(d["spec"].astype(np.float32), d["loud"], FPS, float(d["grid_beat"]), float(d["grid_phase"]))
    th, br, env, sh, tk = ring.tables()
    rng = np.random.default_rng(seed)
    n = ring.n
    col = ring.color.astype(np.float32)
    D = dict(n=n, th=th, br=br, env=env, sh=sh, tk=tk, r=ring.r, size=ring.size, col=col,
             kind=rng.choice(7, n, p=(0.20, 0.15, 0.17, 0.10, 0.14, 0.12, 0.12)),
             tw_p=rng.uniform(0.7, 1.5, n), tw_ph=rng.uniform(0, TAU, n), spike0=rng.uniform(0, np.pi / 2, n),
             hue0=rng.random(n),
             col2=np.where((col[:, 2] > col[:, 0])[:, None], WARM[None, :],
                           np.array((0.55, 0.75, 1.0), np.float32)[None, :]))
    # 火花：每颗火花尾的光点按每秒 55 个掉火星，各自的出生帧、寿命、速度
    sparks = []
    f_lo, f_hi = int((T0 - 1.5) * FPS), int((T0 + LEN) * FPS)
    for i in np.flatnonzero(D["kind"] == 2):
        t = f_lo + np.cumsum(rng.exponential(FPS / 55.0, 1000))
        t = t[t < f_hi]
        k = len(t)
        sparks.append(dict(i=i, fb=t, life=rng.uniform(0.5, 1.6, k), back=rng.uniform(0.1, 0.8, k),
                           side=rng.normal(0, 0.3, k), ph=rng.uniform(0, 6.3, k), big=rng.random(k) < 0.25,
                           hue=rng.random(k)))
    D["sparks"] = sparks
    return D


OLD = make_ring(sr.RADII.copy(), sr.TURN_BEATS, 7)
# 拉开：11 道，内圈从 1.55 R 起、间距越往外越大（原来 1.40、1.60、1.96、2.16、2.67、3.00 …，内圈两两挤在一起）
NEW = make_ring((1.55, 2.05, 2.65, 3.35, 4.15, 5.05, 6.05, 7.15, 8.35, 9.65, 11.0),
                (16, 24, 12, 32, 20, 24, 28, 36, 32, 44, 56), 7)


def interp(a, i, fs):
    """第 i 颗在小数帧 fs 处的值。"""
    fs = np.clip(fs, 0, a.shape[1] - 1)
    f0 = np.floor(fs).astype(int)
    f1 = np.minimum(f0 + 1, a.shape[1] - 1)
    w = fs - f0
    return a[i, f0] * (1 - w) + a[i, f1] * w


def pos(th, r):
    """角度 θ、轨道半径 r（R 为单位）-> 画面像素（和 onepic.star_ring 一样：x = sin θ，往下 = cos θ）。"""
    return CX + np.sin(th) * r * R, CY + np.cos(th) * r * R


def hsv(h, s=0.65, v=1.0):
    """色相 h（0..1，可以是数组）-> RGB。"""
    h = np.asarray(h)[..., None]
    k = (np.array((5.0, 3.0, 1.0)) + h * 6) % 6
    return v - v * s * np.clip(np.minimum(k, 4 - k), 0, 1)


def beat_pulse(t, tau=0.16):
    """拍点上 1、tau 秒衰减；也返回离上一拍几秒。"""
    j = np.searchsorted(BEATS, t) - 1
    if j < 0:
        return 0.0, 9.0
    a = t - BEATS[j]
    return float(np.exp(-a / tau)), a


def line(img, p, q, col, w):
    cv2.line(img, (int(p[0] * SS), int(p[1] * SS)), (int(q[0] * SS), int(q[1] * SS)),
             tuple(float(c) for c in col), max(1, int(round(w * SS))), cv2.LINE_8)


def disk(img, p, r, col):
    cv2.circle(img, (int(p[0] * SS), int(p[1] * SS)), max(1, int(round(r * SS))), tuple(float(c) for c in col), -1)


def ring_line(img, p, r, col, w):
    cv2.circle(img, (int(p[0] * SS), int(p[1] * SS)), max(1, int(round(r * SS))), tuple(float(c) for c in col),
               max(1, int(round(w * SS))))


def cross(img, p, L, ang, col, w=0.6):
    """星芒：两条交叉的线，中间亮、往外三段变暗。"""
    for a in (0.0, np.pi / 2):
        for k, f in ((1.0, 0.3), (0.6, 0.6), (0.3, 1.0)):
            dx, dy = np.cos(ang + a) * L * k, np.sin(ang + a) * L * k
            line(img, (p[0] - dx, p[1] - dy), (p[0] + dx, p[1] + dy), col * f, w)


def down(img):
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)


def blur(img, s):
    return cv2.GaussianBlur(img, (0, 0), s)


def draw_stars(f, D, styled):
    """一帧的光点（显示值），返回 (锐的, 软的) 两层，软的之后再模糊（彗星的尾巴）。"""
    sharp = np.zeros((H * SS, W * SS, 3), np.float32)
    soft = np.zeros_like(sharp)
    t = f / FPS
    pulse, since = beat_pulse(t)
    T = 48
    q = np.linspace(0, 1, T)
    TH, BR, ENV, SH, TK = D["th"], D["br"], D["env"], D["sh"], D["tk"]
    for i in np.flatnonzero(BR[:, f] > 0.01):
        kind = D["kind"][i] if styled else 0
        e, b = ENV[i, f], BR[i, f]
        widen = 1 + 0.2 * SH[i, f]
        rc = 0.020 * D["size"][i]
        rh = rc * (0.85 + 0.3 * e) * widen * R * ((1 + 0.35 * pulse) if styled else 1)     # 星芯半径（像素）
        fs = f - (1 - q) * TK[i, f]
        th = interp(TH, i, fs)
        bq = interp(BR, i, fs)
        eq = interp(ENV, i, fs)
        x, y = pos(th, D["r"][i])
        hw = 0.5 * 1.1 * rc * (0.25 + 0.75 * q) * (0.8 + 0.4 * eq) * widen * R
        sv = bq * 0.85 * q ** 1.8
        col = D["col"][i]
        er = np.stack([np.sin(th), np.cos(th)], 1)               # 朝外
        p = (x[-1], y[-1])
        if kind == 1:           # 双子星：两股尾巴按当时的互绕相位左右错开，两颗之间一道光桥
            ph = TAU * (fs / FPS) / D["tw_p"][i] + D["tw_ph"][i]
            sep = max(2.4 * rh, 0.09 * R)
            for sgn, cc in ((1, col), (-1, D["col2"][i])):
                ox, oy = x + sgn * sep * np.cos(ph) * er[:, 0], y + sgn * sep * np.cos(ph) * er[:, 1]
                for j in range(T - 1):
                    line(sharp, (ox[j], oy[j]), (ox[j + 1], oy[j + 1]), cc * sv[j + 1] * 0.85, 1.6 * hw[j + 1])
            php = ph[-1]
            ends = []
            for sgn, cc in ((1, col), (-1, D["col2"][i])):
                off = np.array((np.cos(php) * er[-1, 0] - 0.5 * np.sin(php) * er[-1, 1],
                                np.cos(php) * er[-1, 1] + 0.5 * np.sin(php) * er[-1, 0])) * sep * sgn
                pp = (p[0] + off[0], p[1] + off[1])
                ends.append(pp)
                disk(sharp, pp, 2.0 * rh * 0.75, cc * 0.35 * b)
                disk(sharp, pp, rh * 0.75, (0.4 * cc + 0.6) * b)
            line(sharp, ends[0], ends[1], (0.5 * col + 0.5 * D["col2"][i]) * 0.45 * b, 0.7)
        else:
            if kind == 4:       # 彗星：宽软的尾巴从白到本色再到偏紫，外加朝外的离子尾
                for j in range(T - 1):
                    k = q[j + 1]
                    cc = (1 - k) * np.array((0.75, 0.45, 0.95)) + k * (0.5 * col + 0.5 * k)
                    line(soft, (x[j], y[j]), (x[j + 1], y[j + 1]), cc * sv[j + 1] * 1.6, 5.0 * hw[j + 1])
                for s in range(12):
                    a0, a1 = s / 12, (s + 1) / 12
                    line(soft, (p[0] + er[-1, 0] * a0 * 1.3 * R, p[1] + er[-1, 1] * a0 * 1.3 * R),
                         (p[0] + er[-1, 0] * a1 * 1.3 * R, p[1] + er[-1, 1] * a1 * 1.3 * R),
                         np.array((0.45, 0.7, 1.0)) * 0.7 * b * (1 - a0) ** 1.5, 1.3)
            elif kind == 6:     # 棱彩尾：沿尾巴变色，颜色往前流
                cs = hsv((D["hue0"][i] + 0.9 * (1 - q) - 0.25 * t) % 1.0, 0.7)
                for j in range(T - 1):
                    line(sharp, (x[j], y[j]), (x[j + 1], y[j + 1]), cs[j + 1] * sv[j + 1] * 1.3, 2.4 * hw[j + 1])
            else:
                thin = 0.7 if kind == 2 else 1.0
                for j in range(T - 1):
                    line(sharp, (x[j], y[j]), (x[j + 1], y[j + 1]), col * sv[j + 1], 2 * hw[j + 1] * thin)
            disk(sharp, p, 1.8 * rh, col * 0.3 * b)
            disk(sharp, p, rh, (0.4 * col + 0.6) * b)
            disk(sharp, p, 0.5 * rh, np.full(3, b))
        if kind == 5:           # 珠串：后面跟着几颗小卫星，各自闪
            for k, (qq, s) in enumerate(((0.93, 0.75), (0.86, 0.6), (0.79, 0.48), (0.72, 0.38))):
                j = int(qq * (T - 1))
                tw = 0.6 + 0.4 * np.sin(5.0 * t + 1.7 * k + i)
                disk(sharp, (x[j], y[j]), rh * s * 1.8, col * 0.3 * b * s)
                disk(sharp, (x[j], y[j]), rh * s, (0.5 * col + 0.5) * b * s * tw * 1.2)
        if kind == 3:           # 脉冲星：十字星芒踩着拍子亮、慢慢转；拍点上一圈冲击波往外扩
            amp = 0.25 + 0.75 * pulse
            cross(sharp, p, 13 * rh * (0.7 + 0.6 * amp), D["spike0"][i] + 0.15 * t, (0.5 * col + 0.5) * amp * b)
            if since < 0.5:
                ring_line(sharp, p, rh * (2 + 60 * since), (0.5 * col + 0.5) * 0.6 * b * (1 - since / 0.5) ** 2, 0.8)
        elif styled and kind != 1:   # 其他光头一个小星芒，拍点上亮一下
            cross(sharp, p, 4.5 * rh * (1 + 0.5 * pulse), D["spike0"][i], (0.5 * col + 0.5) * b * (0.3 + 0.5 * pulse), 0.5)
    if styled:                  # 火花
        for s in D["sparks"]:
            i = s["i"]
            age = (f - s["fb"]) / FPS
            for k in np.flatnonzero((age >= 0) & (age < s["life"])):
                fb = s["fb"][k]
                b0 = interp(BR, i, np.array([fb]))[0]
                if b0 < 0.05:
                    continue
                th = interp(TH, i, np.array([fb]))[0]
                x0, y0 = pos(th, D["r"][i])
                back = np.array((np.cos(th), -np.sin(th)))          # 和走的方向相反
                out = np.array((np.sin(th), np.cos(th)))
                a = age[k]
                drift = a * (1 - 0.35 * a / s["life"][k])
                v = (back * s["back"][k] + out * s["side"][k]) * R
                px = (x0 + v[0] * drift, y0 + v[1] * drift + 0.05 * R * a * a)
                fade = (1 - a / s["life"][k]) ** 2 * (0.55 + 0.45 * np.sin(38 * a + s["ph"][k]))
                base = 0.6 * WARM + 0.4 * D["col"][i] if s["hue"][k] < 0.7 else hsv(s["hue"][k], 0.5)
                cc = base * b0 * fade * (2.2 if s["big"][k] else 1.3)
                disk(sharp, px, 1.7 if s["big"][k] else 0.9, cc)
                if s["big"][k] and fade > 0.3:
                    cross(sharp, px, 5.0, 0.5, cc * 0.6, 0.5)
    return down(sharp), down(soft)


# ---------------------------------------------------------------- 星系和别的滤镜

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot(xx - CX, yy - CY) / R                   # 离月亮中心几个 R
PHI = np.arctan2(xx - CX, yy - CY)                    # 和 θ 一样的约定
LNR = np.log(np.maximum(RR, 0.3))
RMAX = 22.0
WIN = np.clip((RR - 1.1) / 0.8, 0, 1) * np.exp(-np.maximum(RR - 6.0, 0) / 9.0) * np.clip((RMAX + 2 - RR) / 6.0, 0, 1)
SKY = cv2.resize(np.load(os.path.join(C, "art", "prep", "sky.npy")), (W, H))[..., None]   # 天空 1、地面和人物 0


def tile_noise(shape, beta, seed):
    """首尾相接的噪声（1/f^beta 的频谱），0..1。"""
    g = np.random.default_rng(seed)
    fy = np.fft.fftfreq(shape[0])[:, None]
    fx = np.fft.fftfreq(shape[1])[None, :]
    amp = np.hypot(fx, fy)
    amp[0, 0] = 1
    spec = (g.normal(size=shape) + 1j * g.normal(size=shape)) / amp ** beta
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec)).astype(np.float32)
    return (n - n.min()) / (n.max() - n.min())


NZ = tile_noise((192, 512), 1.6, 3)                  # 极坐标里的团块（行 = ln r，列 = θ）
STREAK = tile_noise((64, 1024), 1.2, 5)               # 吸积环的条纹：θ 方向拉长
STREAK = cv2.GaussianBlur(STREAK, (0, 0), sigmaX=12, sigmaY=0.8)
STREAK = (STREAK - STREAK.min()) / (STREAK.max() - STREAK.min())
NEB1, NEB2 = tile_noise((512, 512), 2.0, 11), tile_noise((512, 512), 2.4, 12)
K_PITCH = 1.3
rng = np.random.default_rng(9)
M = 14000
g_r = 1.3 * np.exp(rng.random(M) ** 1.15 * np.log(RMAX / 1.3))
g_arm = rng.integers(0, 2, M)
g_th = g_arm * np.pi - K_PITCH * np.log(g_r) + rng.normal(0, 0.2 + 0.03 * g_r, M)
g_b = rng.uniform(0.08, 0.45, M) * (rng.random(M) ** 3 * 2.5 + 0.4)
g_tw = rng.uniform(0, 6.3, M)
g_col = np.where((g_r < 4.0)[:, None], np.array((1.0, 0.85, 0.65)), np.array((0.6, 0.72, 1.0))).astype(np.float32)
g_col[rng.random(M) < 0.08] = (1.0, 0.55, 0.75)
OMEGA0 = -TAU / 120.0                                 # 内圈约 2 分钟一圈，和光点一样顺着 θ 减小的方向


def galaxy(t):
    """(加在上面的光, 尘埃带)。"""
    rot = OMEGA0 * t * 0.6
    psi = 2 * (PHI - rot) + 2 * K_PITCH * LNR
    arm = ((1 + np.cos(psi)) / 2) ** 4
    lane = ((1 + np.cos(psi - 0.9)) / 2) ** 8 * WIN
    mx = (((PHI - rot) / TAU) % 1.0) * 511
    my = np.clip((LNR - np.log(0.3)) / (np.log(RMAX + 4) - np.log(0.3)), 0, 1) * 191
    clump = cv2.remap(NZ, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR)
    dens = arm * WIN * (0.35 + 0.9 * clump ** 2)
    inner = np.clip((6.0 - RR) / 4.5, 0, 1)[..., None]
    col = inner * np.array((1.0, 0.85, 0.7)) + (1 - inner) * np.array((0.5, 0.65, 1.0))
    light = dens[..., None] * col * 0.38
    hii = (np.clip(clump - 0.6, 0, 1) * 2.5) ** 2 * arm * WIN
    light += hii[..., None] * np.array((1.0, 0.45, 0.7)) * 0.3
    light += (0.05 * WIN)[..., None] * np.array((0.45, 0.5, 0.9))               # 整个盘面一层很淡的底光
    light += (0.16 * np.exp(-np.maximum(RR - 1.0, 0) / 0.9) * (RR > 0.95))[..., None] * np.array((1.0, 0.92, 0.8))
    th = g_th + OMEGA0 * t * (2.0 / g_r)
    gx, gy = CX + np.sin(th) * g_r * R, CY + np.cos(th) * g_r * R
    pts = np.zeros((H, W, 3), np.float32)
    ok = (gx >= 0) & (gx < W - 1) & (gy >= 0) & (gy < H - 1)
    tw = 0.6 + 0.4 * np.sin(2.3 * t + g_tw)
    np.add.at(pts, (gy[ok].astype(int), gx[ok].astype(int)), g_col[ok] * (g_b[ok] * tw[ok])[:, None])
    light += pts + blur(pts, 1.2) * 1.5
    return light.astype(np.float32), lane.astype(np.float32)


hy, hx = np.mgrid[0:H // 2, 0:W // 2].astype(np.float32)


def nebula(t):
    """D：域扭曲噪声的细丝带，半分辨率算再放大。"""
    u = hx / (W / 2) * 1.4 * 512
    v = hy / (H / 2) * 0.8 * 512

    def look(img, a, b):
        return cv2.remap(img, (a % 512).astype(np.float32), (b % 512).astype(np.float32), cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_WRAP)

    w = look(NEB2, u * 0.8 + t * 3.0, v * 0.8)
    w2 = look(NEB2, u * 0.6 + 200, v * 0.6 - t * 2.0 + 300)
    n = look(NEB1, u + 160 * (w - 0.5) + t * 1.5, v + 120 * (w2 - 0.5))
    rib = (np.exp(-((n - 0.5) / 0.022) ** 2) + 0.6 * np.exp(-((n - 0.36) / 0.016) ** 2)
           + 0.4 * np.exp(-((n - 0.64) / 0.03) ** 2))
    pink, cyan, violet = np.array((1.0, 0.4, 0.75)), np.array((0.3, 0.9, 1.0)), np.array((0.6, 0.45, 1.0))
    m = np.clip((w2 - 0.3) / 0.4, 0, 1)[..., None]
    col = 0.75 * ((1 - m) * pink + m * cyan) + 0.25 * violet
    glow = (rib[..., None] * col).astype(np.float32)
    glow = glow + blur(glow, 6) * 1.2
    out = cv2.resize(glow, (W, H)) * 0.2
    return out * np.clip((RR - 1.3) / 1.0, 0, 1)[..., None]


def star_filter(light):
    """E：亮点拉出六芒星芒（半分辨率卷积）、横向蓝光条，整层一点色散。"""
    lum = light.max(2)
    bright = np.clip(light - 0.3, 0, None) * (lum > 0.3)[..., None]
    small = cv2.resize(bright, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    L = 121
    k = np.zeros((L, L), np.float32)
    c = L // 2
    for a in (0.26, 0.26 + np.pi / 3, 0.26 + 2 * np.pi / 3):
        for s in np.linspace(-c, c, 4 * L):
            k[int(round(c + s * np.sin(a))), int(round(c + s * np.cos(a)))] = np.exp(-abs(s) / 18.0)
    k /= k.sum() / 6.0
    spikes = cv2.filter2D(small, -1, k)
    streak = cv2.GaussianBlur(small, (0, 0), sigmaX=90, sigmaY=0.7) * np.array((0.5, 0.7, 1.0), np.float32) * 6.0
    add = cv2.resize(spikes + streak, (W, H))
    out = light + add
    # 色散：红往外、蓝往里各挪一点（以画面中心为准）
    cx, cy = W / 2, H / 2
    for ch, sc in ((0, 1.004), (2, 0.996)):
        mx = (xx - cx) / sc + cx
        my = (yy - cy) / sc + cy
        out[..., ch] = cv2.remap(np.ascontiguousarray(out[..., ch]), mx, my, cv2.INTER_LINEAR)
    return out


def accretion(t):
    """F：月亮外转得飞快的吸积环（多普勒一侧亮）、光子环、淡淡的爱因斯坦环。"""
    om = 1.6 / np.maximum(RR, 1.0) ** 1.5           # 越靠里转得越快
    mx = ((((PHI + om * t) / TAU) % 1.0) * 1023).astype(np.float32)
    my = (np.clip((RR - 1.0) / 0.8, 0, 1) * 63).astype(np.float32)
    st = cv2.remap(STREAK, mx, my, cv2.INTER_LINEAR)
    prof = np.exp(-((RR - 1.25) / 0.13) ** 2) * (0.35 + 0.9 * st ** 1.5)
    doppler = 0.35 + 0.65 * (0.5 + 0.5 * np.cos(PHI - 2.2)) ** 2
    hot = np.clip((1.45 - RR) / 0.4, 0, 1)[..., None]
    col = hot * np.array((1.0, 0.92, 0.75)) + (1 - hot) * np.array((1.0, 0.55, 0.45))
    out = (prof * doppler)[..., None] * col * 0.9
    out += (0.8 * np.exp(-((RR - 1.04) / 0.018) ** 2) * (0.6 + 0.4 * doppler))[..., None] * np.array((1.0, 0.97, 0.9))
    out += (0.1 * np.exp(-((RR - 2.3) / 0.05) ** 2) * (0.7 + 0.3 * np.cos(3 * PHI + 0.4 * t)))[..., None] \
        * np.array((0.6, 0.8, 1.0))
    out = out.astype(np.float32)
    return out + blur(out, 5) * 0.8


art = cv2.imread(os.path.join(C, "art", "prep", "color.png"))[..., ::-1]
ART = cv2.resize(art, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
ch = cv2.imread(os.path.join(C, "art", "prep", "layer_char.png"), cv2.IMREAD_UNCHANGED)
CHAR = cv2.resize(ch[..., 3], (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255


def frame(fo):
    f = int(round((T0 + fo / FPS_OUT) * FPS))
    t = f / FPS
    a_s, _ = draw_stars(f, OLD, False)
    b_s, b_soft = draw_stars(f, NEW, True)
    base = blur(a_s, 0.7) + blur(a_s, 3.0) * 0.35
    stars = blur(b_s, 0.7) + blur(b_s, 3.0) * 0.45 + blur(b_soft, 2.2) + blur(b_s, 9.0) * 0.2
    gal, lane = galaxy(t)
    gal = gal * SKY
    # (光点那层, 星系一类铺在天上的那层, 尘埃带)
    layers = {"A": (base, None, None), "B": (stars, None, None), "C": (stars, gal, lane),
              "D": (stars, gal + nebula(t) * SKY, lane), "E": (star_filter(stars), gal, lane),
              "F": (stars, gal + accretion(t), lane)}
    for v, (st, sky, ln) in layers.items():
        light = st if sky is None else st + sky
        bg = ART if ln is None else ART * (1 - 0.12 * ln[..., None] * SKY)
        onart = 1 - (1 - bg) * (1 - np.clip(light * (1 - CHAR), 0, 1))
        for tag, img in (("black", np.clip(light, 0, 1)), ("art", onart)):
            ext = "png" if tag == "black" else "jpg"
            cv2.imwrite(os.path.join(OUT, f"{v}_{tag}", f"f_{fo:04d}.{ext}"),
                        (np.clip(img, 0, 1)[..., ::-1] * 255 + 0.5).astype(np.uint8),
                        [cv2.IMWRITE_PNG_COMPRESSION, 1] if ext == "png" else [cv2.IMWRITE_JPEG_QUALITY, 96])
    return fo


def grid(tag, zoom=False):
    """3 × 2 格，每格 1280×720；zoom 时每格只取月亮周围左上的 1152×648 放大。"""
    font = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ext = "png" if tag == "black" else "jpg"
    ins, fl = [], []
    for k, v in enumerate(VARIANTS):
        ins += ["-framerate", str(FPS_OUT), "-i", os.path.join(OUT, f"{v}_{tag}", f"f_%04d.{ext}")]
        crop = "crop=1152:648:0:0," if zoom else ""
        fl.append(f"[{k}:v]{crop}scale=1280:720:flags=lanczos,drawtext=fontfile={font}:text='{LABELS[v]}':"
                  f"x=24:y=H-64:fontsize=38:fontcolor=white:borderw=3[v{k}]")
    fl.append("[v0][v1][v2][v3][v4][v5]xstack=inputs=6:layout=0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-ss", str(T0), "-t", str(LEN),
                    "-i", os.path.join(C, "audio", "kimishira_sakura_shunka_mix.wav"),
                    "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "6:a", "-shortest",
                    "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
                    os.path.join(OUT, f"grid_{tag}" + ("_zoom" if zoom else "") + ".mp4")], check=True)
    if zoom:
        return
    for v in VARIANTS:          # 每个样式单独一份，看细节用
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS_OUT),
                        "-i", os.path.join(OUT, f"{v}_{tag}", f"f_%04d.{ext}"), "-ss", str(T0), "-t", str(LEN),
                        "-i", os.path.join(C, "audio", "kimishira_sakura_shunka_mix.wav"), "-shortest",
                        "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", os.path.join(OUT, f"{v}_{tag}.mp4")], check=True)


if __name__ == "__main__":
    for v in VARIANTS:
        for tag in ("black", "art"):
            os.makedirs(os.path.join(OUT, f"{v}_{tag}"), exist_ok=True)
    n_out = int(LEN * FPS_OUT)
    kinds = ", ".join(f"{k} {int((NEW['kind'] == j).sum())}" for j, k in enumerate(KINDS))
    print(f"ring poc: {OLD['n']} -> {NEW['n']} lights ({kinds}), R {R:.1f} px, {n_out} frames from {T0} s", flush=True)
    with Pool(14) as p:
        for k in p.imap_unordered(frame, range(n_out)):
            if k % 30 == 0:
                print("frame", k, flush=True)
    for tag in ("black", "art"):
        grid(tag)
        grid(tag, zoom=True)
    print("->", OUT)
