"""月亮外圈"节奏盘"的样式实验：在不带频谱环的渲染帧（pv.py 的 RING=none + clip）上，按每帧月亮在画面上的位置和
大小把几种样式画成 2D 的光，滤色叠上去，几秒的小样并排比较。选定的样式再做进 Blender 场景（花瓣从前面飘过、辉光都对）。
在 AutoDL 上：
    PY=/root/autodl-tmp/ComfyUI/venv/bin/python; export PYTHONPATH=/root/autodl-tmp/pv/pylib
    # melody 要人声的音高（librosa 在 evalq 环境里）
    /root/autodl-tmp/conda_envs/evalq/bin/python scripts/ring_lab.py f0 <lead.flac> <f0.npz> --t0 60 --t1 75
    $PY scripts/ring_lab.py draw <帧目录> <输出目录> --style halo --bands <bands.npz> --moon <场景>_moon.npz [--f0 <f0.npz>]
    $PY scripts/ring_lab.py grid <输出目录> --moon <场景>_moon.npz --font <ttf> A=<帧目录> B=<帧目录> ...
样式（长度都以月亮半径 R 为单位）：
    bars    细线 + 峰值点：64 根细线绕满一圈（低频在下、高频在上，左右对称），根部亮、往梢上淡；顶上的峰值点停一下再慢慢落
    halo    光环：频谱绕成一条连续的平滑闭合曲线，外面两圈是 0.12、0.25 秒前的"回声"，里面一层很淡的光晕
    ripple  涟漪：每一拍从月亮边上放出一圈细环往外扩散、变淡（重拍更亮），环的起伏是那一拍的频谱；里圈一条细环跟着心跳
    melody  旋律：月亮外 12 个刻度是 12 个音名，一颗光点按人声的音高走（角度是音名，半径是音高），拖着 1.5 秒的尾巴
    halo+ripple  光环和涟漪叠在一起
帧文件名是 60 fps 的场景帧号（f_03960.png），间隔取帧（30 fps）也行。"""
import argparse
import glob
import math
import os
import re
from multiprocessing import Pool

import numpy as np

FPS = 60
SS = 2                          # 超采样
HALF = 3.3                      # 画布半宽（R）：涟漪最远到 3 R
MOON = (0.80, 0.90, 1.00)       # 月光的淡蓝白（RGB）
WARM = (1.00, 0.95, 0.86)       # 峰值点、旋律光点的暖白


# ---------------------------------------------------------------- 音频

def smooth(x, k):
    k = max(int(k) | 1, 1)
    return np.convolve(np.pad(x, (k // 2, k // 2), mode="edge"), np.ones(k) / k, "valid")


class Song:
    def __init__(self, bands, f0=None):
        d = np.load(bands)
        self.spec = d["spec"].astype(np.float32)
        self.bass = d["bass"].astype(np.float32)
        self.voice = d["voice"].astype(np.float32)
        self.beats = d["beats"]
        self.downbeats = d["downbeats"]
        self.pulse = smooth(self.bass ** 2, 0.3 * FPS)          # 和 pv.py 的 pulse 一样：低音平方的 0.3 秒滑动平均
        self.n = len(self.bass)
        self.f0 = np.load(f0) if f0 else None

    def angular(self, f, n=360, sigma_deg=9.0):
        """第 f 帧的频谱绕成一圈：θ 从正下方 0 起，右半圈往上到正上方 π，左半圈对称回来；低频在下、高频在上。
        沿圆周做高斯平滑（首尾相接），返回 (θ, 值)。"""
        th = np.arange(n) * 2 * np.pi / n
        phi = np.where(th <= np.pi, th, 2 * np.pi - th)
        b = self.spec.shape[1]
        v = np.interp(phi / np.pi * (b - 1), np.arange(b), self.spec[min(max(f, 0), self.n - 1)])
        k = int(3 * sigma_deg * n / 360)
        w = np.exp(-0.5 * (np.arange(-k, k + 1) * 360 / n / sigma_deg) ** 2)
        v = np.convolve(np.concatenate([v[-k:], v, v[:k]]), w / w.sum(), "valid")
        return th, v


def peaks(song, f_end, n_bars, hold=0.25, gravity=2.5):
    """细线的峰值点：碰到新高就跳上去，停 hold 秒，再按重力加速落下。从头算到 f_end，返回 (f_end+1, n_bars)。"""
    out = np.zeros((f_end + 1, n_bars), np.float32)
    p = np.zeros(n_bars)
    h = np.zeros(n_bars)
    vel = np.zeros(n_bars)
    dt = 1.0 / FPS
    for f in range(f_end + 1):
        v = bar_values(song, f, n_bars)
        up = v >= p
        p = np.where(up, v, p)
        h = np.where(up, hold, h - dt)
        vel = np.where(up | (h > 0), 0.0, vel + gravity * dt)
        p = np.where(up | (h > 0), p, np.maximum(p - vel * dt, 0.0))
        out[f] = p
    return out


def bar_values(song, f, n_bars):
    b = song.spec.shape[1]
    v = np.interp(np.linspace(0, b - 1, n_bars), np.arange(b), song.spec[min(max(f, 0), song.n - 1)])
    return np.convolve(np.pad(v, 1, mode="edge"), (0.25, 0.5, 0.25), "valid")


def f0_cmd(a):
    import librosa
    sr = 24000
    hop = sr // FPS
    y, _ = librosa.load(a.lead, sr=sr, offset=a.t0, duration=a.t1 - a.t0)
    f0, voiced, prob = librosa.pyin(y, fmin=110, fmax=1100, sr=sr, frame_length=2048, hop_length=hop)
    np.savez(a.out, t0=a.t0, f0=np.nan_to_num(f0).astype(np.float32), prob=np.nan_to_num(prob).astype(np.float32))
    print(a.out, len(f0), "frames,", f"{np.mean(prob > 0.3) * 100:.0f}% voiced", flush=True)


class Melody:
    """人声音高 -> 旋律盘上的位置。音名的角度：出现最多的音名在正上方，音高往上走时顺时针转；半径按整段的音域。"""

    def __init__(self, f0npz):
        self.t0 = float(f0npz["t0"])
        f0 = f0npz["f0"]
        self.voiced = (f0npz["prob"] > 0.3) & (f0 > 0)
        m = np.where(self.voiced, 69 + 12 * np.log2(np.maximum(f0, 1) / 440.0), np.nan)
        # 中值滤掉 pyin 的单帧跳动
        mm = m.copy()
        for i in range(2, len(m) - 2):
            w = m[i - 2:i + 3]
            if np.isfinite(m[i]) and np.isfinite(w).sum() >= 3:
                mm[i] = np.nanmedian(w)
        self.m = mm
        ok = np.isfinite(mm)
        pc = np.round(mm[ok]) % 12
        self.top = int(np.bincount(pc.astype(int), minlength=12).argmax())
        self.lo, self.hi = np.percentile(mm[ok], [5, 95])

    def at(self, f):
        i = int(round(f - self.t0 * FPS))
        if i < 0 or i >= len(self.m) or not np.isfinite(self.m[i]):
            return None
        return self.m[i]

    def theta(self, m):
        return np.pi - 2 * np.pi * (m - self.top) / 12.0

    def radius(self, m):
        return 1.24 + 0.55 * np.clip((m - self.lo) / max(self.hi - self.lo, 1), -0.1, 1.1)


# ---------------------------------------------------------------- 画

class Canvas:
    """以月亮为中心的方形画布，长度单位是 R；每组元素一张 8 位遮罩（cv2 的抗锯齿只对 8 位图有效），最后着色相加。"""

    def __init__(self, R):
        import cv2
        self.cv2 = cv2
        self.R = R
        self.S = int(math.ceil(2 * HALF * R * SS))
        self.c = self.S / 2
        self.layers = []

    def layer(self, color, gain):
        m = np.zeros((self.S, self.S), np.uint8)
        self.layers.append((m, color, gain))
        return m

    def px(self, x, y):
        """R 单位的点（x 朝右、y 朝下，月亮中心为原点）-> cv2 的定点坐标（shift=4）。"""
        return np.round(np.stack([self.c + np.asarray(x) * self.R * SS, self.c + np.asarray(y) * self.R * SS], -1)
                        * 16).astype(np.int32)

    def width(self, w):
        return max(1, int(round(w * self.R * SS)))

    def polar(self, th, r):
        return np.sin(th) * r, np.cos(th) * r     # θ = 0 正下方，π 正上方，(0, π) 右半圈

    def line(self, m, th, r0, r1, value, w):
        p = self.px(*self.polar(th, np.array([r0, r1]))).tolist()
        self.cv2.line(m, tuple(p[0]), tuple(p[1]), int(value * 255), self.width(w), self.cv2.LINE_AA, 4)

    def curve(self, m, th, r, value, w, closed=True):
        p = self.px(*self.polar(th, r))
        self.cv2.polylines(m, [p], closed, int(value * 255), self.width(w), self.cv2.LINE_AA, 4)

    def fill(self, m, th, r, value):
        self.cv2.fillPoly(m, [self.px(*self.polar(th, r))], int(value * 255), self.cv2.LINE_AA, 4)

    def dot(self, m, th, r, rad, value):
        p = self.px(*self.polar(th, r)).tolist()
        self.cv2.circle(m, tuple(p), int(round(rad * self.R * SS * 16)), int(value * 255), -1, self.cv2.LINE_AA, 4)

    def light(self, glow=(0.8, 0.5)):
        """着色相加，加两层辉光，缩回 1 倍；月亮圆盘里压暗（月亮本身的亮度由贴图决定）。返回 float32 RGB。"""
        cv2 = self.cv2
        rgb = np.zeros((self.S, self.S, 3), np.float32)
        for m, color, gain in self.layers:
            rgb += (m.astype(np.float32) / 255.0)[..., None] * (np.array(color, np.float32) * gain)
        s1, s2 = 0.04 * self.R * SS, 0.16 * self.R * SS
        rgb = rgb + glow[0] * cv2.GaussianBlur(rgb, (0, 0), s1) + glow[1] * cv2.GaussianBlur(rgb, (0, 0), s2)
        yy, xx = np.mgrid[0:self.S, 0:self.S]
        d = np.hypot(xx - self.c, yy - self.c) / (self.R * SS)
        rgb *= np.clip((d - 0.95) / 0.12, 0.2, 1.0)[..., None]
        n = int(round(self.S / SS))
        return cv2.resize(rgb, (n, n), interpolation=cv2.INTER_AREA)


def draw_bars(cv, song, f, pk):
    n = 32
    v = bar_values(song, f, n)
    base = cv.layer(MOON, 0.35)
    cv.curve(base, np.linspace(0, 2 * np.pi, 241), np.full(241, 1.10), 1.0, 0.010)
    bars = cv.layer(MOON, 0.9)
    caps = cv.layer(WARM, 0.9)
    r0 = 1.15
    for side in (1, -1):
        for k in range(n):
            phi = (k + 0.5) / n * np.pi
            th = phi if side > 0 else 2 * np.pi - phi
            L = 0.04 + 0.62 * v[k] ** 1.4
            segs = 5
            for s in range(segs):           # 根部亮、往梢上淡；从梢往根画，亮的盖在上面
                s = segs - 1 - s
                a, b = r0 + L * s / segs, r0 + L * (s + 1) / segs
                cv.line(bars, th, a, b, 0.95 - 0.6 * s / (segs - 1), 0.018)
            cv.dot(caps, th, r0 + 0.04 + 0.62 * pk[f][k] ** 1.4 + 0.05, 0.017, 0.9)


def halo_curve(song, f, lift=0.0):
    th, v = song.angular(f)
    return th, 1.16 + lift + 0.34 * v ** 1.3


def draw_halo(cv, song, f, gain=1.0):
    th, r = halo_curve(song, f)
    r = r * (1 + 0.03 * song.pulse[f])
    fill = cv.layer(MOON, 0.10 * gain)
    cv.fill(fill, th, r, 1.0)
    for lag, lift, val in ((15, 0.14, 0.22), (7, 0.07, 0.45)):
        e = cv.layer(MOON, gain)
        th_, r_ = halo_curve(song, f - lag, lift)
        cv.curve(e, th_, r_, val, 0.010)
    main = cv.layer(MOON, gain)
    cv.curve(main, th, r, 1.0, 0.016)


def draw_ripple(cv, song, f, gain=1.0):
    t = f / FPS
    inner = cv.layer(MOON, gain)
    cv.curve(inner, np.linspace(0, 2 * np.pi, 241), np.full(241, 1.10), 0.3 + 0.5 * song.pulse[f], 0.014)
    life = 2.4
    for tb in song.beats[(song.beats > t - life) & (song.beats <= t)]:
        fb = int(round(tb * FPS))
        s = float(song.bass[min(fb, song.n - 1)])
        if np.min(np.abs(song.downbeats - tb)) < 0.05:
            s *= 1.4
        if s < 0.15:
            continue
        x = (t - tb) / life
        rad = 1.12 + 1.9 * (1 - (1 - x) ** 3)
        th, v = song.angular(fb)
        r = rad * (1 + 0.05 * (v - v.mean()))
        m = cv.layer(MOON, gain)
        cv.curve(m, th, r, min(s, 1.0) * (1 - x) ** 1.5, 0.016 * (1 - 0.5 * x))


def draw_melody(cv, song, f, mel):
    guide = cv.layer(MOON, 0.18)
    cv.curve(guide, np.linspace(0, 2 * np.pi, 241), np.full(241, 1.13), 1.0, 0.008)
    # 刻度：12 个音名，最近唱到的亮一点（0.5 秒衰减）
    energy = np.zeros(12)
    for g in range(f - 90, f + 1):
        m = mel.at(g)
        if m is not None:
            energy[int(round(m - mel.top)) % 12] += float(song.voice[g]) * math.exp(-(f - g) / (0.5 * FPS)) / 12
    ticks = cv.layer(MOON, 0.9)
    for k in range(12):
        th = mel.theta(mel.top + k)
        cv.line(ticks, th, 1.09, 1.17, min(0.25 + 0.75 * energy[k], 1.0), 0.012)
    # 尾巴：最近 1.5 秒，不唱的地方断开；相邻两帧在极坐标里插值，换音时走圆弧
    trail = cv.layer(MOON, 1.0)
    span = int(1.5 * FPS)
    prev = None
    for g in range(f - span, f + 1):
        m = mel.at(g)
        if m is None:
            prev = None
            continue
        th, r = mel.theta(m), mel.radius(m)
        if prev is not None and abs(th - prev[0]) < np.pi / 2:
            age = (f - g) / span
            k = max(2, int(abs(th - prev[0]) / 0.03))
            tt = np.linspace(prev[0], th, k)
            rr = np.linspace(prev[1], r, k)
            cv.curve(trail, tt, rr, 0.85 * (1 - age) ** 1.5, 0.004 + 0.014 * (1 - age), closed=False)
        prev = (th, r)
    m = mel.at(f)
    if m is not None:
        head = cv.layer(WARM, 1.0)
        cv.dot(head, mel.theta(m), mel.radius(m), 0.028 * (0.7 + 0.6 * float(song.voice[f])), 1.0)


# ---------------------------------------------------------------- 合成

G = {}


def setup(a):
    G["a"] = a
    G["song"] = Song(a.bands, a.f0)
    G["moon"] = np.load(a.moon)
    if a.style == "melody":
        G["mel"] = Melody(G["song"].f0)
    if a.style == "bars":
        G["pk"] = peaks(G["song"], a.f_end, 32)


def frame_no(path):
    return int(re.findall(r"(\d+)\.png$", path)[0])


def draw_one(path):
    import cv2
    a, song = G["a"], G["song"]
    f = frame_no(path)
    img = cv2.imread(path)[..., ::-1].astype(np.float32) / 255.0
    H, W = img.shape[:2]
    q, r = G["moon"]["pos"][f], float(G["moon"]["r"][f])
    cx, cy, R = q[0] * W, (1 - q[1]) * H, r * W
    cv = Canvas(R)
    for st in a.style.split("+"):
        if st == "bars":
            draw_bars(cv, song, f, G["pk"])
        elif st == "halo":
            draw_halo(cv, song, f, 0.8 if "+" in a.style else 1.0)
        elif st == "ripple":
            draw_ripple(cv, song, f)
        elif st == "melody":
            draw_melody(cv, song, f, G["mel"])
    light = cv.light()
    n = light.shape[0]
    x0, y0 = int(round(cx - n / 2)), int(round(cy - n / 2))
    sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x0 + n, W), min(y0 + n, H)
    sub = light[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * a.gain
    reg = img[sy0:sy1, sx0:sx1]
    img[sy0:sy1, sx0:sx1] = 1 - (1 - reg) * (1 - np.clip(sub, 0, 1))      # 滤色
    out = os.path.join(a.out, os.path.basename(path))
    cv2.imwrite(out, (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)[..., ::-1])


def draw_cmd(a):
    frames = sorted(glob.glob(os.path.join(a.frames, "f_*.png")))
    a.f_end = frame_no(frames[-1])
    os.makedirs(a.out, exist_ok=True)
    with Pool(a.procs, initializer=setup, initargs=(a,)) as pool:
        for _ in pool.imap_unordered(draw_one, frames, chunksize=4):
            pass
    print(a.style, len(frames), "frames ->", a.out, flush=True)


def grid_cmd(a):
    """几种样式月亮附近的同一块并排（3 列），左上角写样式名；输出 PNG 序列。"""
    from PIL import Image, ImageDraw, ImageFont
    tiles = [x.split("=", 1) for x in a.tiles]
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(tiles[0][1], "f_*.png")))
    mo = np.load(a.moon)
    first = Image.open(os.path.join(tiles[0][1], names[0]))
    W, H = first.size
    fs = [frame_no(n) for n in names]
    cx = float(np.mean(mo["pos"][fs, 0])) * W
    cy = (1 - float(np.mean(mo["pos"][fs, 1]))) * H
    R = float(np.mean(mo["r"][fs])) * W
    half = int(2.9 * R)
    box = (int(cx - half), int(max(cy - half, 0)), int(cx + half), int(max(cy - half, 0) + 2 * half))
    T = a.tile
    font = ImageFont.truetype(a.font, int(T * 0.06))
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    os.makedirs(a.out, exist_ok=True)
    for n in names:
        sheet = Image.new("RGB", (cols * T, rows * T), (8, 10, 18))
        for i, (label, d) in enumerate(tiles):
            im = Image.open(os.path.join(d, n)).convert("RGB").crop(box).resize((T, T), Image.LANCZOS)
            dr = ImageDraw.Draw(im)
            dr.text((int(T * 0.04), int(T * 0.03)), label, font=font, fill=(235, 240, 255))
            sheet.paste(im, ((i % cols) * T, (i // cols) * T))
        sheet.save(os.path.join(a.out, n))
    print("grid", len(names), "frames ->", a.out, flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("f0")
    p.add_argument("lead")
    p.add_argument("out")
    p.add_argument("--t0", type=float, required=True)
    p.add_argument("--t1", type=float, required=True)
    p = sub.add_parser("draw")
    p.add_argument("frames")
    p.add_argument("out")
    p.add_argument("--style", required=True)
    p.add_argument("--bands", required=True)
    p.add_argument("--moon", required=True)
    p.add_argument("--f0")
    p.add_argument("--gain", type=float, default=1.0, help="整体亮度")
    p.add_argument("--procs", type=int, default=16)
    p = sub.add_parser("grid")
    p.add_argument("out")
    p.add_argument("tiles", nargs="+", help="名字=帧目录")
    p.add_argument("--moon", required=True)
    p.add_argument("--font", required=True)
    p.add_argument("--tile", type=int, default=640)
    a = ap.parse_args()
    {"f0": f0_cmd, "draw": draw_cmd, "grid": grid_cmd}[a.cmd](a)


if __name__ == "__main__":
    main()
