"""星环样式的 2D 小样（不进成片）：用和正片同一份 star_ring.Ring 数据，只画星环的光点和滤镜，几种样式并排比。
在 AutoDL 上：
    $PY cases/kimishira/scripts/ring_poc.py [起始秒 70] [秒数 8]
-> renders/ring_poc/grid_black.mp4（黑底）、grid_art.mp4（叠在插画上，人物挡在前面），每格 1920×1080：
    A 现在     正片的样式（2D 近似：星芯 + 光晕 + 收细的尾巴）
    B 个性光点  每颗一种：普通、双子星（两颗互绕，尾巴拧成两股）、火花尾（一路掉小火星）、脉冲星（十字星芒，踩着拍子闪）、
               彗星（宽软的尾巴从白过渡到本色，外加一条朝外的淡蓝离子尾）
    C B + 星系  月亮是星系核：暖色核心光、两条对数螺旋旋臂（内暖外蓝，带粉色的星团团块）慢慢转，旋臂上几千颗小星
               按离心距离差速转；插画上旋臂内侧有暗的尘埃带
    D B + 光晕  大的多层辉光（红的晕得开一点，像镜头色散）、离月亮 7 R 的一圈彩虹晕、盘面的蓝紫薄雾、亮星加星芒
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
VARIANTS = ("A", "B", "C", "D")
LABELS = {"A": "A 现在", "B": "B 个性光点", "C": "C 个性光点 + 星系", "D": "D 个性光点 + 光晕"}

d = np.load(os.path.join(C, "audio", "bands.npz"))
FPS = int(d["fps"])
ring = sr.Ring(d["spec"].astype(np.float32), d["loud"], FPS, float(d["grid_beat"]), float(d["grid_phase"]))
TH, BR, ENV, SH, TK = ring.tables()
N = ring.n
meta = json.load(open(os.path.join(C, "art", "prep", "meta.json")))
mu, mv, mr = meta["moon"]
CX, CY, R = mu * W, mv * H, mr * W      # 月亮中心、半径（像素）
BEATS = np.asarray(d["beats"], float)
rng = np.random.default_rng(7)

# 每颗的样式：0 普通、1 双子星、2 火花尾、3 脉冲星、4 彗星
KIND = rng.choice(5, N, p=(0.40, 0.16, 0.18, 0.10, 0.16))
TW_P = rng.uniform(0.7, 1.5, N)                  # 双子星互绕的周期（秒）
TW_PH = rng.uniform(0, 2 * np.pi, N)
SPIKE0 = rng.uniform(0, np.pi / 2, N)
COL = ring.color.astype(np.float32)
WARM = np.array((1.0, 0.78, 0.45), np.float32)
# 双子星的另一颗：偏蓝的配暖的，偏暖的配蓝的
COL2 = np.where((COL[:, 2] > COL[:, 0])[:, None], WARM[None, :], np.array((0.55, 0.75, 1.0), np.float32)[None, :])


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


# 火花：每颗火花尾的光点按每秒 22 个掉火星，各自的出生帧、寿命、速度
SPARKS = []
f_lo, f_hi = int((T0 - 1.5) * FPS), int((T0 + LEN) * FPS)
for i in np.flatnonzero(KIND == 2):
    t = f_lo + np.cumsum(rng.exponential(FPS / 22.0, 400))
    t = t[t < f_hi]
    k = len(t)
    SPARKS.append(dict(i=i, fb=t, life=rng.uniform(0.35, 1.1, k), back=rng.uniform(0.05, 0.4, k),
                       side=rng.normal(0, 0.14, k), ph=rng.uniform(0, 6.3, k), big=rng.random(k) < 0.15))


def beat_pulse(t):
    """拍点上 1、0.16 秒衰减。"""
    j = np.searchsorted(BEATS, t) - 1
    return float(np.exp(-(t - BEATS[j]) / 0.16)) if j >= 0 else 0.0


def line(img, p, q, col, w):
    cv2.line(img, (int(p[0] * SS), int(p[1] * SS)), (int(q[0] * SS), int(q[1] * SS)),
             tuple(float(c) for c in col), max(1, int(round(w * SS))), cv2.LINE_8)


def disk(img, p, r, col):
    cv2.circle(img, (int(p[0] * SS), int(p[1] * SS)), max(1, int(round(r * SS))), tuple(float(c) for c in col), -1)


def down(img):
    return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)


def blur(img, s):
    return cv2.GaussianBlur(img, (0, 0), s)


def draw_stars(f, styled):
    """一帧的光点（显示值，0..1 以上），返回 (锐的, 软的) 两层，软的之后再模糊（彗星的尾巴）。"""
    sharp = np.zeros((H * SS, W * SS, 3), np.float32)
    soft = np.zeros_like(sharp)
    t = f / FPS
    pulse = beat_pulse(t)
    T = 48
    q = np.linspace(0, 1, T)
    for i in np.flatnonzero(BR[:, f] > 0.01):
        kind = KIND[i] if styled else 0
        e, b = ENV[i, f], BR[i, f]
        widen = 1 + 0.2 * SH[i, f]
        rc = 0.020 * ring.size[i]
        rh = rc * (0.85 + 0.3 * e) * widen * R                  # 星芯半径（像素）
        fs = f - (1 - q) * TK[i, f]
        th = interp(TH, i, fs)
        bq = interp(BR, i, fs)
        eq = interp(ENV, i, fs)
        x, y = pos(th, ring.r[i])
        hw = 0.5 * 1.1 * rc * (0.25 + 0.75 * q) * (0.8 + 0.4 * eq) * widen * R
        sv = bq * 0.85 * q ** 1.8
        col = COL[i]
        er = np.stack([np.sin(th), np.cos(th)], 1)               # 朝外
        if kind == 1:           # 双子星：两股尾巴按当时的互绕相位左右错开
            ph = 2 * np.pi * (fs / FPS) / TW_P[i] + TW_PH[i]
            sep = max(1.3 * rh, 2.2)
            for sgn, cc in ((1, col), (-1, COL2[i])):
                ox, oy = x + sgn * sep * np.cos(ph) * er[:, 0], y + sgn * sep * np.cos(ph) * er[:, 1]
                for j in range(T - 1):
                    line(sharp, (ox[j], oy[j]), (ox[j + 1], oy[j + 1]), cc * sv[j + 1] * 0.75, 1.6 * hw[j + 1])
            php = ph[-1]
            for sgn, cc in ((1, col), (-1, COL2[i])):
                off = np.array((np.cos(php) * er[-1, 0] - 0.5 * np.sin(php) * er[-1, 1],
                                np.cos(php) * er[-1, 1] + 0.5 * np.sin(php) * er[-1, 0])) * sep * sgn
                p = (x[-1] + off[0], y[-1] + off[1])
                disk(sharp, p, 1.8 * rh * 0.7, cc * 0.3 * b)
                disk(sharp, p, rh * 0.7, (0.4 * cc + 0.6) * b)
            continue
        if kind == 4:           # 彗星：宽软的尾巴从白到本色再到偏紫，外加朝外的离子尾
            for j in range(T - 1):
                k = q[j + 1]
                cc = (1 - k) * np.array((0.75, 0.45, 0.95)) + k * (0.5 * col + 0.5 * k)
                line(soft, (x[j], y[j]), (x[j + 1], y[j + 1]), cc * sv[j + 1] * 1.1, 3.2 * hw[j + 1])
            hx, hy = x[-1], y[-1]
            for s in range(10):
                a0, a1 = s / 10, (s + 1) / 10
                line(soft, (hx + er[-1, 0] * a0 * 0.6 * R, hy + er[-1, 1] * a0 * 0.6 * R),
                     (hx + er[-1, 0] * a1 * 0.6 * R, hy + er[-1, 1] * a1 * 0.6 * R),
                     np.array((0.45, 0.7, 1.0)) * 0.35 * b * (1 - a0) ** 1.5, 0.9)
        else:
            thin = 0.7 if kind == 2 else 1.0
            for j in range(T - 1):
                line(sharp, (x[j], y[j]), (x[j + 1], y[j + 1]), col * sv[j + 1], 2 * hw[j + 1] * thin)
        p = (x[-1], y[-1])
        disk(sharp, p, 1.8 * rh, col * 0.3 * b)
        disk(sharp, p, rh, (0.4 * col + 0.6) * b)
        disk(sharp, p, 0.5 * rh, np.full(3, b))
        if kind == 3:           # 脉冲星：十字星芒，踩着拍子亮、慢慢转
            amp = 0.25 + 0.75 * pulse
            for a in (0.0, np.pi / 2):
                ang = SPIKE0[i] + 0.15 * t + a
                for L, k in ((7.0, 0.25), (4.5, 0.5), (2.5, 0.9)):
                    L = L * rh * (0.7 + 0.6 * amp)
                    dx, dy = np.cos(ang) * L, np.sin(ang) * L
                    line(sharp, (p[0] - dx, p[1] - dy), (p[0] + dx, p[1] + dy), (0.5 * col + 0.5) * k * amp * b, 0.6)
    if styled:                  # 火花
        for s in SPARKS:
            i = s["i"]
            age = (f - s["fb"]) / FPS
            live = (age >= 0) & (age < s["life"])
            for k in np.flatnonzero(live):
                fb = s["fb"][k]
                b0 = interp(BR, i, np.array([fb]))[0]
                if b0 < 0.05:
                    continue
                th = interp(TH, i, np.array([fb]))[0]
                x0, y0 = pos(th, ring.r[i])
                back = np.array((np.cos(th), -np.sin(th)))          # 和走的方向相反
                out = np.array((np.sin(th), np.cos(th)))
                a = age[k]
                drift = a * (1 - 0.35 * a / s["life"][k])
                v = (back * s["back"][k] + out * s["side"][k]) * R
                px = (x0 + v[0] * drift, y0 + v[1] * drift + 0.04 * R * a * a)
                fade = (1 - a / s["life"][k]) ** 2 * (0.6 + 0.4 * np.sin(38 * a + s["ph"][k]))
                cc = (0.5 * WARM + 0.5 * COL[i]) * b0 * fade * (1.4 if s["big"][k] else 0.9)
                disk(sharp, px, 1.1 if s["big"][k] else 0.6, cc)
    return down(sharp), down(soft)


# ---------------------------------------------------------------- 星系、光晕

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.hypot(xx - CX, yy - CY) / R                   # 离月亮中心几个 R
PHI = np.arctan2(xx - CX, yy - CY)                    # 和 θ 一样的约定
LNR = np.log(np.maximum(RR, 0.3))
WIN = np.clip((RR - 1.1) / 0.8, 0, 1) * np.exp(-np.maximum(RR - 4.0, 0) / 5.0) * np.clip((13.0 - RR) / 3.0, 0, 1)
# 极坐标里的团块噪声（θ 方向首尾相接），旋臂转的时候团块跟着转
nz = np.random.default_rng(3).random((96, 256)).astype(np.float32)
nz = sum(cv2.resize(cv2.GaussianBlur(np.tile(nz, (1, 3)), (0, 0), s), (768, 96))[:, 256:512] * w_
         for s, w_ in ((1.0, 0.5), (3.0, 0.35), (8.0, 0.15)))
nz = (nz - nz.min()) / (nz.max() - nz.min())
NZ = cv2.resize(nz, (512, 192))
K_PITCH = 2.4
# 旋臂上的小星：沿两条对数螺旋撒开，离中心越远越疏，按 1/r 差速转
M = 3200
g_r = 1.3 * np.exp(rng.random(M) ** 1.3 * np.log(11.5 / 1.3))
g_arm = rng.integers(0, 2, M)
g_th = g_arm * np.pi - K_PITCH * np.log(g_r) + rng.normal(0, 0.22 + 0.04 * g_r, M)
g_b = rng.uniform(0.05, 0.3, M) * (rng.random(M) ** 3 * 2.5 + 0.4)
g_tw = rng.uniform(0, 6.3, M)
g_col = np.where((g_r < 3.5)[:, None], np.array((1.0, 0.85, 0.65)), np.array((0.6, 0.72, 1.0))).astype(np.float32)
g_col[rng.random(M) < 0.08] = (1.0, 0.55, 0.75)
OMEGA0 = -2 * np.pi / 120.0                           # 内圈约 2 分钟一圈，和光点一样顺着 θ 减小的方向


def galaxy(t):
    """(加在上面的光, 尘埃带)。"""
    rot = OMEGA0 * t * 0.6
    psi = 2 * (PHI - rot) + 2 * K_PITCH * LNR
    arm = ((1 + np.cos(psi)) / 2) ** 3
    lane = ((1 + np.cos(psi - 0.9)) / 2) ** 8 * WIN
    mx = (((PHI - rot) / (2 * np.pi)) % 1.0) * 511
    my = np.clip((LNR - np.log(0.3)) / (np.log(14) - np.log(0.3)), 0, 1) * 191
    clump = cv2.remap(NZ, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR)
    dens = arm * WIN * (0.35 + 0.9 * clump ** 2)
    inner = np.clip((5.0 - RR) / 3.5, 0, 1)[..., None]
    col = inner * np.array((1.0, 0.75, 0.55)) + (1 - inner) * np.array((0.45, 0.55, 1.0))
    light = dens[..., None] * col * 0.11
    hii = (np.clip(clump - 0.62, 0, 1) * 2.6) ** 2 * arm * WIN
    light += hii[..., None] * np.array((1.0, 0.45, 0.7)) * 0.10
    light += (0.22 * np.exp(-np.maximum(RR - 1.0, 0) / 1.4) * (RR > 0.95))[..., None] * np.array((1.0, 0.85, 0.65))
    # 小星
    th = g_th + OMEGA0 * t * (2.0 / g_r)
    gx, gy = CX + np.sin(th) * g_r * R, CY + np.cos(th) * g_r * R
    pts = np.zeros((H, W, 3), np.float32)
    ok = (gx >= 0) & (gx < W - 1) & (gy >= 0) & (gy < H - 1)
    tw = 0.6 + 0.4 * np.sin(2.3 * t + g_tw)
    np.add.at(pts, (gy[ok].astype(int), gx[ok].astype(int)), g_col[ok] * (g_b[ok] * tw[ok])[:, None])
    light += pts + blur(pts, 1.2) * 1.5
    return light.astype(np.float32), lane.astype(np.float32)


def halo_filter(stars):
    """D：大的多层辉光（红的晕开一点）、7 R 的彩虹晕、盘面薄雾。"""
    out = np.zeros_like(stars)
    for s, k in ((3.0, 0.55), (10.0, 0.4), (30.0, 0.25)):
        for c, scale in ((0, 1.25), (1, 1.0), (2, 0.85)):
            out[..., c] += blur(stars[..., c], s * scale) * k
    for c, (dr, k) in enumerate(((-0.18, 0.06), (0.0, 0.05), (0.18, 0.07))):
        out[..., c] += k * np.exp(-((RR - 7.0 - dr) / 0.32) ** 2)
    out += (0.10 * np.exp(-np.maximum(RR - 1.0, 0) / 4.0) * (RR > 0.95))[..., None] * np.array((0.35, 0.3, 0.65))
    return out.astype(np.float32)


art = cv2.imread(os.path.join(C, "art", "prep", "color.png"))[..., ::-1]
ART = cv2.resize(art, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
ch = cv2.imread(os.path.join(C, "art", "prep", "layer_char.png"), cv2.IMREAD_UNCHANGED)
CHAR = cv2.resize(ch[..., 3], (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255


def frame(fo):
    f = int(round((T0 + fo / FPS_OUT) * FPS))
    t = f / FPS
    plain_s, plain_soft = draw_stars(f, False)
    sty_s, sty_soft = draw_stars(f, True)
    base = blur(plain_s, 0.7) + blur(plain_s, 3.0) * 0.35
    styled = blur(sty_s, 0.7) + blur(sty_s, 3.0) * 0.35 + blur(sty_soft, 2.2)
    gal, lane = galaxy(t)
    layers = {"A": (base, None), "B": (styled, None),
              "C": (styled + blur(sty_s, 9.0) * 0.25 + gal, lane), "D": (styled + halo_filter(styled), None)}
    for v, (light, ln) in layers.items():
        black = np.clip(light, 0, 1)
        bg = ART if ln is None else ART * (1 - 0.35 * ln[..., None] * (1 - CHAR))
        onart = 1 - (1 - bg) * (1 - np.clip(light * (1 - CHAR), 0, 1))
        for tag, img in (("black", black), ("art", onart)):
            cv2.imwrite(os.path.join(OUT, f"{v}_{tag}", f"f_{fo:04d}.png"),
                        (np.clip(img, 0, 1)[..., ::-1] * 255 + 0.5).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    return fo


def grid(tag):
    font = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ins, fl = [], []
    for k, v in enumerate(VARIANTS):
        ins += ["-framerate", str(FPS_OUT), "-i", os.path.join(OUT, f"{v}_{tag}", "f_%04d.png")]
        fl.append(f"[{k}:v]drawtext=fontfile={font}:text='{LABELS[v]}':x=36:y=H-90:fontsize=54:"
                  f"fontcolor=white:borderw=4[v{k}]")
    fl.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-ss", str(T0), "-t", str(LEN),
                    "-i", os.path.join(C, "audio", "kimishira_sakura_shunka_mix.wav"),
                    "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "4:a", "-shortest",
                    "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
                    os.path.join(OUT, f"grid_{tag}.mp4")], check=True)
    for v in VARIANTS:          # 每个样式单独一份，看细节用
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS_OUT),
                        "-i", os.path.join(OUT, f"{v}_{tag}", "f_%04d.png"), "-c:v", "libx264", "-crf", "16",
                        "-preset", "fast", "-pix_fmt", "yuv420p", os.path.join(OUT, f"{v}_{tag}.mp4")], check=True)


if __name__ == "__main__":
    for v in VARIANTS:
        for tag in ("black", "art"):
            os.makedirs(os.path.join(OUT, f"{v}_{tag}"), exist_ok=True)
    n_out = int(LEN * FPS_OUT)
    kinds = ", ".join(f"{k} {int((KIND == j).sum())}" for j, k in enumerate(("普通", "双子", "火花", "脉冲", "彗星")))
    print(f"ring poc: {N} lights ({kinds}), R {R:.1f} px, {n_out} frames from {T0} s", flush=True)
    with Pool(14) as p:
        for k in p.imap_unordered(frame, range(n_out)):
            if k % 30 == 0:
                print("frame", k, flush=True)
    for tag in ("black", "art"):
        grid(tag)
    print("->", OUT)
