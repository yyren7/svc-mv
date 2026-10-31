"""星环的 2D 画法：star_ring.Ring 的模拟（轨道、生灭、转速、追逐让路）照旧，只是不进 Blender，按成片的分辨率逐帧画成透明 PNG，
onepic_finish.py 用 --overlay 叠上去（线条不过景深、不过抗锯齿，4K 上是锐的）。

    python templates/kue_stars/ring2d.py cases/<歌> <输出目录> [--height 2160] [--fps 60] [--matte 遮罩目录] [--frames 3600 7200] [--range T0 T1]

镜头：pv.py 的 build 存的 renders/ring_cam.npz（每帧月亮中心和 R 的两个方向在画面上的位置）。
遮挡：pv.py 的 matte 渲的人物、花丛的 alpha（m_#####.png），星环在她们身后。

美术上的规矩（长曝光星轨 + 动画里的小星）：
- 星等分三档：六成偏暗、三成中等、不到一成亮，亮的也只是小而锐的点，没有大光球；
- 尾巴是一笔收锋：头细而亮、越往后越细越淡，颜色从近白退到本色；后面三成碎成星尘（亮暗按轨道上固定的位置，像光扫过尘埃）；
- 星芒：只有亮的那档有，小的四芒，全部同一个朝向（同一支镜头的衍射），按每颗 6–14 秒慢慢明灭；
- 配色收敛：轨道本色（里暖白 -> 外冰蓝），少数淡金、淡玫瑰、淡紫，不要彩虹、麻花、离子尾；
- 掉的星尘慢慢飘散（1.2–3.5 秒），不闪；
- 每道轨道一圈很淡的发丝线，盘面看得出结构；
- 开头对焦在镜头前时不出现，焦点拉到脸上的那两秒淡入；歌词那块（layout.QUIET）压暗。
"""
import argparse
import json
import os
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, os.path.join(ROOT, "scripts")]
import layout as L
import star_ring as sr

SRC_FPS = 60
W_FRAC = 0.80           # 只画画面左边这么宽（最外道到不了更右）
PALETTE = (((1.00, 0.78, 0.45), 0.13), ((1.00, 0.62, 0.78), 0.08), ((0.72, 0.62, 1.00), 0.06))  # 淡金、淡玫瑰、淡紫，占比
SPIKE_ANGLE = np.radians(12.0)
HAIRLINE = 0.045        # 轨道发丝线的亮度


def tables(case):
    d = np.load(os.path.join(case, "audio/bands.npz"))
    ring = sr.Ring(d["spec"].astype(np.float32), d["loud"], SRC_FPS, float(d["grid_beat"]), float(d["grid_phase"]),
                   radii=sr.ORBIT_RADII, turns=sr.ORBIT_TURNS, dirs=sr.ORBIT_DIRS, tail_k=sr.ORBIT_TAIL_K,
                   dens=3.0, tail_floor=1.75, size_max=1.1)
    th, br, _, _, tail = ring.tables()
    # 亮度过 1 秒的平滑：Ring 里有一项跟着这段频率走，直接用会踩拍子
    k = np.ones(SRC_FPS) / SRC_FPS
    br = np.stack([np.convolve(np.pad(x, SRC_FPS, mode="edge"), k, "same")[SRC_FPS:-SRC_FPS] for x in br])
    rng = np.random.default_rng(23)
    n = ring.n
    u = rng.random(n)
    mag = np.where(u < 0.60, 0.50 + 0.20 * rng.random(n),
                   np.where(u < 0.92, 0.70 + 0.15 * rng.random(n), 0.90 + 0.10 * rng.random(n)))
    tk = np.asarray(sr.ORBIT_TAIL_K)[ring.track]
    mag = mag * (0.75 + 0.25 * np.minimum(tk * 1.5, 1.0))        # 短尾的密道暗一些
    INNER, OUTER = np.array((1.0, 0.90, 0.74)), np.array((0.50, 0.74, 1.0))      # 比 Ring 的本色饱和一些，细线上才看得出颜色
    col = np.array(ring.track)[:, None] / (len(sr.ORBIT_RADII) - 1) * (OUTER - INNER) + INNER
    v = rng.random(n)
    lo = 0.0
    for c, p in PALETTE:
        col[(v >= lo) & (v < lo + p)] = c
        lo += p
    # 掉的星尘：亮的掉得多。列：光点、出生帧、寿命（秒）、朝外的速度、往后的速度（R/秒）、相位、亮度
    D = []
    for i in range(n):
        rate = 1.5 + 10.0 * mag[i]
        t = np.cumsum(rng.exponential(SRC_FPS / rate, int(ring.F / SRC_FPS * rate * 1.2) + 5))
        t = t[t < ring.F - 1]
        m = len(t)
        D.append(np.stack([np.full(m, i), t, rng.uniform(1.2, 3.5, m), rng.normal(0, 0.05, m),
                           rng.uniform(0.0, 0.05, m) * ring.dir[i], rng.uniform(0, 6.28, m), rng.uniform(0.5, 1.0, m)], 1))
    dust = np.concatenate(D).astype(np.float32)
    dust = dust[br[dust[:, 0].astype(int), dust[:, 1].astype(int)] > 0.05]      # 看不见时不掉
    return dict(th=th, br=br.astype(np.float32), tail=tail, r=ring.r.astype(np.float32), mag=mag.astype(np.float32),
                col=col.astype(np.float32), dust=dust, spike_p=rng.uniform(6, 14, n).astype(np.float32),
                spike_ph=rng.uniform(0, 6.28, n).astype(np.float32), noise=rng.uniform(0, 100, n).astype(np.float32),
                radii=np.asarray(sr.ORBIT_RADII, np.float32))


def setup(a):
    global G
    z = np.load(a.cache)
    G = {k: z[k] for k in z.files}
    G["cam"] = np.load(os.path.join(a.case, "renders/ring_cam.npz"))["xy"]
    G["a"] = a
    W, H = int(round(a.height * 16 / 9)), a.height
    G["W"], G["H"] = int(W * W_FRAC), H
    G["FW"] = W
    x0, y0, x1, y1, floor, soft = L.QUIET
    yy, xx = np.mgrid[0:H, 0:G["W"]].astype(np.float32)
    wx, wy = xx / W, 1 - yy / H
    dx = np.maximum(np.maximum(x0 - wx, wx - x1), 0) * 16 / 9
    dy = np.maximum(np.maximum(y0 - wy, wy - y1), 0)
    t = np.clip(np.hypot(dx, dy) / soft, 0, 1)
    G["quiet"] = floor + (1 - floor) * (t * t * (3 - 2 * t))
    G["t_in"] = json.load(open(os.path.join(a.case, "plan.json")))["title_end"]


class Acc:
    """分批收 (x, y, 颜色) 的点，最后一次累加（双线性）。"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.x, self.y, self.c = [], [], []

    def add(self, x, y, c):
        self.x.append(x)
        self.y.append(y)
        self.c.append(c)

    def image(self):
        W, H = self.W, self.H
        out = np.zeros((H, W, 3), np.float32)
        if not self.x:
            return out
        x, y, c = np.concatenate(self.x), np.concatenate(self.y), np.concatenate(self.c)
        keep = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
        x, y, c = x[keep], y[keep], c[keep]
        ix, iy = x.astype(np.int64), y.astype(np.int64)
        fx, fy = (x - ix)[:, None], (y - iy)[:, None]
        for dx, dy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            i = (iy + dy) * W + ix + dx
            v = c * w
            for ch in range(3):
                out[..., ch] += np.bincount(i, v[:, ch], W * H).reshape(H, W).astype(np.float32)
        return out


def frame(args):
    f, fsrc = args
    a, th, br, tail, r, mag, col = G["a"], G["th"], G["br"], G["tail"], G["r"], G["mag"], G["col"]
    s = a.height / 2160
    W, H, FW = G["W"], G["H"], G["FW"]
    size = np.array((FW, H), np.float32)
    c, ex, ez = G["cam"][fsrc] * size
    ax, az = ex - c, ez - c
    Rpx = float(np.hypot(*ax))
    t = fsrc / SRC_FPS

    def pos(theta, rad):
        sa, ca = np.sin(theta), -np.cos(theta)
        return c[0] + rad * (sa * ax[0] + ca * az[0]), c[1] + rad * (sa * ax[1] + ca * az[1])

    A = Acc(W, H)
    # 发丝线：每道一圈
    for rad in G["radii"]:
        m = int(2 * np.pi * rad * Rpx / 1.2)
        tt = np.linspace(0, 2 * np.pi, m, endpoint=False, dtype=np.float32)
        x, y = pos(tt, rad)
        A.add(x, y, np.tile(np.array((0.72, 0.82, 1.0), np.float32) * HAIRLINE * 0.6, (m, 1)))
    # 尾巴
    F = th.shape[1]
    # 光头灭了尾巴还亮着：尾巴窗口里还有亮的就接着画，尾巴慢慢收进灭掉的地方，不会整条一帧没了
    vis = [i for i in range(len(r)) if br[i, max(fsrc - int(tail[i, fsrc]), 0):fsrc + 1].max() > 0.004]
    for i in vis:
        tk = float(tail[i, fsrc])
        arc = abs(float(th[i, fsrc] - th[i, max(fsrc - int(tk), 0)])) * r[i] * Rpx
        m = max(int(arc / 0.9), 2)
        q = np.linspace(0, 1, m, dtype=np.float32)
        fs = np.clip(fsrc - (1 - q) * tk, 0, F - 1)
        i0 = fs.astype(int)
        i1 = np.minimum(i0 + 1, F - 1)
        fr = fs - i0
        theta = th[i, i0] * (1 - fr) + th[i, i1] * fr
        b = br[i, i0] * (1 - fr) + br[i, i1] * fr
        x, y = pos(theta, r[i])
        sig = s * (0.7 + 1.0 * mag[i]) * (0.35 + 0.65 * q ** 1.2)      # 收锋
        I = b * mag[i] * (0.10 + 0.90 * q ** 1.5) * np.minimum(q / 0.06, 1)
        # 尾巴后面碎成尘：亮暗按轨道上固定的位置
        n1 = np.sin(theta * r[i] * 37.0 + G["noise"][i]) * np.sin(theta * r[i] * 91.0 + 2.1 * G["noise"][i])
        grain = np.clip(0.5 + 1.6 * n1, 0, 1)
        dis = np.clip((0.40 - q) / 0.30, 0, 1)
        I = I * (1 - dis + dis * grain)
        hot = (q ** 7)[:, None]
        cc = col[i] * (1 - hot) + hot
        nx, ny = (x - c[0]) / (r[i] * Rpx), (y - c[1]) / (r[i] * Rpx)      # 屏幕上朝外
        for off in (-3.0, -2.25, -1.5, -0.75, 0.0, 0.75, 1.5, 2.25, 3.0):
            g = np.exp(-0.5 * (off * s / sig) ** 2)
            A.add(x + off * s * nx, y + off * s * ny, cc * (I * g * 0.62)[:, None])
    # 星尘
    dust = G["dust"]
    age = (fsrc - dust[:, 1]) / SRC_FPS
    live = (age > 0) & (age < dust[:, 2])
    dl = dust[live]
    if len(dl):
        li = dl[:, 0].astype(int)
        ag = age[live]
        x, y = pos(th[li, dl[:, 1].astype(int)] + dl[:, 4] * ag / r[li], r[li] + dl[:, 3] * ag)
        left = 1 - ag / dl[:, 2]
        I = 0.55 * mag[li] * left * left * dl[:, 6] * (0.75 + 0.25 * np.sin(1.2 * ag + dl[:, 5]))
        A.add(x, y, col[li] * I[:, None])
    img = A.image()
    # 光头和星芒
    heads = Acc(W, H)
    rad = int(np.ceil(11 * s)) + 2
    yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    for i in vis:
        b = br[i, fsrc]
        x0, y0 = pos(th[i, fsrc], r[i])
        if not (-rad <= x0 < W + rad and -rad <= y0 < H + rad):      # 中心出了画，光晕还有一半在里面
            continue
        xs, ys = np.round(x0) + xx, np.round(y0) + yy
        d2 = (xs - x0) ** 2 + (ys - y0) ** 2
        sg = s * (1.2 + 1.2 * mag[i])
        I = b * mag[i] * (1.4 * np.exp(-d2 / (2 * sg * sg)) + 0.20 * np.exp(-d2 / (2 * (3.2 * sg) ** 2)))
        white = col[i] * 0.3 + 0.7
        heads.add(xs.ravel().astype(np.float32), ys.ravel().astype(np.float32), (white[None] * I.ravel()[:, None]).astype(np.float32))
        if mag[i] > 0.85:         # 小四芒：同一个朝向，慢慢明灭
            tw = 0.5 + 0.5 * np.sin(2 * np.pi * t / G["spike_p"][i] + G["spike_ph"][i])
            Ls = s * (18 + 26 * tw) * mag[i]
            for an in (SPIKE_ANGLE, SPIKE_ANGLE + np.pi / 2):
                u = np.linspace(-1, 1, int(2 * Ls / 0.8) + 2, dtype=np.float32)
                k = b * mag[i] * (0.15 + 0.5 * tw) * (1 - np.abs(u)) ** 2.2 * 0.7
                heads.add(x0 + u * Ls * np.cos(an), y0 + u * Ls * np.sin(an), white[None] * k[:, None])
    img += heads.image()
    # 辉光：两层，都很淡
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.GaussianBlur(small, (0, 0), max(1.5 * s, 0.6))
    g2 = cv2.GaussianBlur(small, (0, 0), max(6.0 * s, 1.0))
    img = img + cv2.resize(2.5 * g1 + 2.0 * g2, (W, H), interpolation=cv2.INTER_LINEAR)
    # 淡入、让位、遮挡
    k = np.clip((t - (G["t_in"] - 2.0)) / 2.0, 0, 1)
    img *= (k * k * (3 - 2 * k)) * G["quiet"][..., None]
    if a.matte:
        m = cv2.imread(os.path.join(a.matte, f"m_{fsrc:05d}.png"), cv2.IMREAD_UNCHANGED)
        if m is not None:
            m = cv2.resize(m if m.ndim == 2 else m[..., 3], (FW, H), interpolation=cv2.INTER_CUBIC)[:, :W]
            img *= (1 - m.astype(np.float32) / 255)[..., None]
    # 透明 PNG：alpha 取最亮的通道，颜色除回去（普通 alpha 叠就接近滤色）
    img = np.clip(img, 0, 1)
    al = img.max(2)
    al[al < 3 / 255] = 0        # 辉光很淡的外缘不要，PNG 小很多
    rgb = img / np.maximum(al, 1e-4)[..., None]
    rgb[al == 0] = 0
    out = np.dstack([(np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), (al * 255 + 0.5).astype(np.uint8)])
    cv2.imwrite(os.path.join(a.out, f"o_{f:05d}.png"), cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA), [cv2.IMWRITE_PNG_COMPRESSION, 3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("out")
    ap.add_argument("--height", type=int, default=2160)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--matte")
    ap.add_argument("--frames", type=int, nargs="*", help="只画这几帧（60 fps 的帧号，试效果用；文件名就是帧号）")
    ap.add_argument("--range", type=float, nargs=2)
    ap.add_argument("--procs", type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    a.cache = os.path.join(a.case, "renders/ring2d_tables.npz")
    if not os.path.exists(a.cache):
        np.savez(a.cache, **tables(a.case))
    n = len(np.load(os.path.join(a.case, "renders/ring_cam.npz"))["xy"])
    step = SRC_FPS // a.fps
    if a.frames:
        jobs = [(f, f) for f in a.frames]
    else:
        t0, t1 = a.range if a.range else (0, n / SRC_FPS)
        jobs = [(k, k * step) for k in range(int(t0 * a.fps), min(int(t1 * a.fps), n // step))]
    with Pool(a.procs, initializer=setup, initargs=(a,)) as pool:
        for k, _ in enumerate(pool.imap_unordered(frame, jobs, chunksize=4)):
            if k % 600 == 0:
                print(k, "/", len(jobs), flush=True)
    json.dump({"x": 0, "y": 0, "fps": a.fps, "t0": 0.0, "frames": n // step}, open(os.path.join(a.out, "region.json"), "w"))


if __name__ == "__main__":
    main()
