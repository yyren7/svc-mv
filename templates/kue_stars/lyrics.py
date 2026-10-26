"""KTV 式的歌词（左边中部的天空，两行一高一低），逐帧画成透明 PNG，onepic_finish.py 用 --overlay 叠上去：

    python templates/kue_stars/lyrics.py cases/<歌> <输出目录> [--height 1080] [--fps 60] [--range 秒 秒]

- 两行交替：唱这一句时另一行已经挂着下一句（淡的）；这句唱完，这一行换成下下句。一段唱完（后面停顿超过 GAP 秒），
  两行一起散掉，下一段的头两句马上挂上去等着，从第一句开唱前到最后一句唱完，画面上始终是两句。
  停顿长的（开头、间奏后）开唱前三颗小星一拍灭一颗（KTV 的倒数）。
- 逐字匀速走字：一句从开唱（LRC 的时间）到唱完（人声分轨的包络最后一次过门槛，bands.npz 的 vocal）平均分给每个字
  （空格算半个），一个字一个字从左往右划亮；划过的字亮一下再落到常亮。
- 星光：唱过的字是带蓝白辉光的亮字，里面零星的小星慢慢明灭；走字的前沿有一颗四芒星，一路往后撒星尘（往上飘、慢慢灭）；
  一句唱完被换掉时，字碎成星尘往上飘散；新的一句从虚到实浮现。没唱的字是半透明的淡色。字下面垫一层很淡的暗晕，
  亮的背景上也看得清。闪烁都慢（几秒一个来回），不踩拍子。
--range 只画这段时间里的帧（预览用）；帧号仍从 region.json 的 t0 起算，和整首画的一样。
位置、字号见 layout.py。
"""
import argparse
import json
import math
import os
import re
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import layout as L
from title import fallback_index

TAG = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
META = re.compile(r"^(作词|作曲|编曲|制作人|演唱|原唱|词|曲|by)\s*[:：]", re.I)
GAP = 5.0                   # 前一句唱完到这句开唱超过这么多秒，算新的一段（两行重新从上面那行起）
FADE_IN, DISSOLVE = 0.45, 0.7
LEAD = 0.05                 # 走字比 LRC 的时间早一点起
UNSUNG, SUNG = (205, 215, 240), (255, 255, 255)
GLOW, GLOW2, GOLD = (190, 220, 255), (110, 160, 255), (255, 236, 196)
DUST = ((235, 242, 255), (180, 210, 255), (255, 232, 190))

G = {}


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def parse_lrc(path):
    rows = []
    for line in open(path, encoding="utf-8-sig"):
        tags = TAG.findall(line)
        text = TAG.sub("", line).strip()
        if META.match(text):
            continue
        for m, s in tags:
            rows.append((int(m) * 60 + float(s), text))
    rows.sort(key=lambda r: r[0])
    return rows


def timing(rows, vocal, fps, end):
    """唱的每一句 -> dict(text, ts 开唱, te 唱完, chars 每个字的 (起, 止) 秒)。te：到下一行（空行也算）开始前，
    人声包络最后一次超过门槛（这句里最大值的 45%，不低于 0.22）的时刻。"""
    out = []
    for i, (t, text) in enumerate(rows):
        if not text:
            continue
        nxt = rows[i + 1][0] if i + 1 < len(rows) else min(t + 8.0, end)
        f0, f1 = int(t * fps), max(int(t * fps) + 1, int(min(nxt, t + 12.0) * fps))
        seg = vocal[f0:f1]
        on = np.flatnonzero(seg > max(0.22, 0.45 * float(seg.max()))) if len(seg) else []
        te = (f0 + on[-1] + 1) / fps if len(on) else nxt - 0.2
        te = min(max(te, t + 0.25 * len(text)), nxt)
        w = np.array([0.5 if c.isspace() else 1.0 for c in text])
        edges = (t - LEAD) + (te - (t - LEAD)) * np.concatenate([[0.0], np.cumsum(w) / w.sum()])
        out.append(dict(text=text, ts=t - LEAD, te=te, chars=list(zip(edges[:-1], edges[1:]))))
    return out


def schedule(lines, title_end, beat):
    """每句的行（0 上 1 下）、出现 a、开始散 d，和每段开唱前的倒数 (开始, 开唱时刻, 每颗间隔)。"""
    blocks, cur = [], []
    for i, ln in enumerate(lines):
        if cur and ln["ts"] - lines[i - 1]["te"] > GAP:
            blocks.append(cur)
            cur = []
        cur.append(i)
    if cur:
        blocks.append(cur)
    counts = []
    prev_end = None
    for b in blocks:
        first = lines[b[0]]
        show = max(title_end - 1.6, first["ts"] - 3.5) if prev_end is None else prev_end + 0.9
        last_te = lines[b[-1]]["te"]
        for j, i in enumerate(b):
            ln = lines[i]
            ln["row"] = j % 2
            ln["a"] = show + 0.15 * j if j < 2 else lines[b[j - 2]]["te"] + 0.2
            ln["d"] = ln["te"] + 0.05 if j + 2 < len(b) else last_te + 0.5
        if first["ts"] - show >= 1.5:
            counts.append((show + 0.3, first["ts"], min(beat, (first["ts"] - show - 0.3) / 3.0)))
        prev_end = last_te + 0.5
    return counts


def font_at(px):
    return ImageFont.truetype(L.LYRIC_FONT, max(8, int(round(px))), index=fallback_index())


def blur(m, r):
    """浮点遮罩的高斯模糊（PIL，8 位）。"""
    im = Image.fromarray((np.clip(m, 0, 1) * 255 + 0.5).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(max(r, 0.3))), np.float32) / 255


def dot(r):
    """半径 r 像素的高斯点（中心 1）。"""
    key = ("dot", int(round(r * 4)))
    if key not in G["sprites"]:
        n = int(math.ceil(r * 3)) + 1
        y, x = np.mgrid[-n:n + 1, -n:n + 1]
        G["sprites"][key] = np.exp(-(x * x + y * y) / (2 * r * r)).astype(np.float32)
    return G["sprites"][key]


def star(r):
    """四芒星：中心一团亮、横竖两道细长的光芒、斜着两道短的，r 是光芒的半长（像素）。"""
    key = ("star", int(round(r * 2)))
    if key not in G["sprites"]:
        n = int(math.ceil(r)) + 2
        y, x = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32)
        w = max(r * 0.045, 0.7)
        core = np.exp(-(x * x + y * y) / (2 * (r * 0.12) ** 2))
        arm = lambda a, b, ln: np.exp(-(b * b) / (2 * w * w)) * np.clip(1 - np.abs(a) / ln, 0, 1) ** 2   # noqa: E731
        d1, d2 = (x + y) / math.sqrt(2), (x - y) / math.sqrt(2)
        s = core + arm(x, y, r) + arm(y, x, r) + 0.5 * (arm(d1, d2, r * 0.45) + arm(d2, d1, r * 0.45))
        G["sprites"][key] = np.clip(s, 0, 1.5).astype(np.float32)
    return G["sprites"][key]


def over(canvas, x, y, sprite, color, alpha):
    """把 sprite（0..1，乘 alpha）以 color 叠到 canvas（预乘 RGBA）的 (x, y)（sprite 中心）上。"""
    if alpha <= 0.003:
        return
    h, w = sprite.shape
    x0, y0 = int(round(x)) - w // 2, int(round(y)) - h // 2
    H, W = canvas.shape[:2]
    sx0, sy0, sx1, sy1 = max(0, -x0), max(0, -y0), min(w, W - x0), min(h, H - y0)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    a = np.minimum(sprite[sy0:sy1, sx0:sx1] * alpha, 1.0)
    dst = canvas[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
    dst[..., :3] = dst[..., :3] * (1 - a[..., None]) + np.array(color, np.float32)[None, None] / 255 * a[..., None]
    dst[..., 3] = dst[..., 3] * (1 - a) + a


def layer(dst, a, color):
    a = np.clip(a, 0, 1)
    dst[..., :3] = dst[..., :3] * (1 - a[..., None]) + np.array(color, np.float32)[None, None] / 255 * a[..., None]
    dst[..., 3] = dst[..., 3] * (1 - a) + a


def prep(i):
    """一句的字形和要用的东西（每个进程按需算，留最近几句）。"""
    cache = G["cache"]
    if i in cache:
        return cache[i]
    ln = G["lines"][i]
    W, H = G["W"], G["H"]
    r = ln["row"]
    em = L.LYRIC_EM * H
    font = font_at(em)
    width = font.getlength(ln["text"])
    if width > L.LYRIC_W[r] * W:
        em *= L.LYRIC_W[r] * W / width
        font = font_at(em)
        width = font.getlength(ln["text"])
    pad = int(em * 0.9)
    up = int(em * 1.15)                         # 基线以上留的高度
    mw, mh = int(width) + 2 * pad, pad + up + int(em * 0.35) + pad
    im = Image.new("L", (mw, mh), 0)
    ImageDraw.Draw(im).text((pad, pad + up), ln["text"], font=font, fill=255, anchor="ls")
    M = np.asarray(im, np.float32) / 255
    cum = [pad + font.getlength(ln["text"][:k]) for k in range(len(ln["text"]) + 1)]
    rng = np.random.default_rng(1000 + i)
    # 字里零星的小星：两组，各自慢慢明灭
    dil = blur(M, em * 0.05) > 0.25
    ys, xs = np.nonzero(dil)
    sparks = []
    for _ in range(2):
        S = np.zeros_like(M)
        k = min(len(xs), 4 * len(ln["text"]))
        for j in rng.choice(len(xs), k, replace=False) if len(xs) else []:
            s = dot(rng.uniform(0.025, 0.05) * em)
            h_, w_ = s.shape
            y0, x0 = ys[j] - h_ // 2, xs[j] - w_ // 2
            if 0 <= y0 and 0 <= x0 and y0 + h_ <= mh and x0 + w_ <= mw:
                S[y0:y0 + h_, x0:x0 + w_] = np.maximum(S[y0:y0 + h_, x0:x0 + w_], s)
        sparks.append(S)
    # 散开的星尘：从字形上取点
    ys2, xs2 = np.nonzero(M > 0.5)
    n_exit = min(len(xs2), 26 * len(ln["text"]))
    pick = rng.choice(len(xs2), n_exit, replace=False) if len(xs2) else np.zeros(0, int)
    exit_p = dict(x=xs2[pick].astype(np.float32), y=ys2[pick].astype(np.float32),
                  vx=rng.normal(0.1, 0.35, n_exit) * em, vy=-rng.uniform(0.5, 1.4, n_exit) * em,
                  life=rng.uniform(0.7, 1.4, n_exit), size=rng.uniform(0.03, 0.075, n_exit) * em,
                  ph=rng.uniform(0, 6.3, n_exit), col=rng.integers(0, len(DUST), n_exit))
    # 走字前沿撒的星尘：每秒 24 颗
    dur = ln["te"] - ln["ts"]
    n_tr = max(1, int(dur * 24))
    te_k = ln["ts"] + np.sort(rng.uniform(0, dur, n_tr))
    trail_p = dict(t=te_k, vx=rng.normal(-0.25, 0.25, n_tr) * em, vy=-rng.uniform(0.15, 0.7, n_tr) * em,
                   dy=rng.normal(0, 0.18, n_tr) * em, life=rng.uniform(0.6, 1.3, n_tr),
                   size=rng.uniform(0.03, 0.08, n_tr) * em, ph=rng.uniform(0, 6.3, n_tr),
                   col=rng.integers(0, len(DUST), n_tr))
    ox = L.LYRIC_X[r] * W - pad - G["rx"]
    oy = L.LYRIC_Y[r] * H - pad - up - G["ry"]
    d = dict(M=M, glow=blur(M, em * 0.10), glow2=blur(M, em * 0.30), shade=np.clip(blur(M, em * 0.32) * 1.7, 0, 1),
             sparks=sparks, cum=np.array(cum), em=em, pad=pad, base=pad + up, ox=ox, oy=oy, exit=exit_p, trail=trail_p)
    cache[i] = d
    if len(cache) > 8:
        cache.pop(next(iter(cache)))
    return d


def front(ln, d, t):
    """t 时走字前沿的 x（这句遮罩里的像素）；还没开唱是 −∞，唱完是 +∞。t 可以是数组。"""
    t = np.asarray(t, float)
    edges = np.array([c[0] for c in ln["chars"]] + [ln["chars"][-1][1]])
    k = np.clip(np.searchsorted(edges, t, side="right") - 1, 0, len(ln["chars"]) - 1)
    f = np.clip((t - edges[k]) / np.maximum(edges[k + 1] - edges[k], 1e-6), 0, 1)
    x = d["cum"][k] + f * (d["cum"][k + 1] - d["cum"][k])
    return np.where(t < edges[0], -1e9, np.where(t >= edges[-1], 1e9, x))


def draw_line(canvas, i, t):
    ln = G["lines"][i]
    d = prep(i)
    em, M = d["em"], d["M"]
    vin = ease((t - ln["a"]) / FADE_IN)
    dis = ease((t - ln["d"]) / DISSOLVE) if t > ln["d"] else 0.0
    al = vin * (1 - dis)
    ox, oy = d["ox"], d["oy"] + (1 - vin) * 0.18 * em
    xs = np.arange(M.shape[1], dtype=np.float32)
    xf = float(front(ln, d, t))
    w = np.clip((xf - xs) / (0.12 * em) + 0.5, 0, 1)[None, :]
    # 划过的字亮一下（字划满的那一刻最亮，0.25 秒落回去）
    boost = np.zeros(M.shape[1], np.float32)
    for k, (c0, c1) in enumerate(ln["chars"]):
        f = math.exp(-((t - c1) / 0.25) ** 2)
        if f > 0.01:
            boost[int(d["cum"][k]):int(d["cum"][k + 1]) + 1] = f
    boost = boost[None, :]
    if al > 0.003:
        x0, y0 = int(round(ox)), int(round(oy))
        H, W = canvas.shape[:2]
        sx0, sy0 = max(0, -x0), max(0, -y0)
        sx1, sy1 = min(M.shape[1], W - x0), min(M.shape[0], H - y0)
        if sx1 > sx0 and sy1 > sy0:
            cut = (slice(sy0, sy1), slice(sx0, sx1))
            dst = canvas[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
            ww, bb = w[:, sx0:sx1], boost[:, sx0:sx1]
            tw1 = 0.5 + 0.5 * math.sin(t * 0.9 + i)
            tw2 = 0.5 + 0.5 * math.sin(t * 0.67 + 2.0 + i)
            layer(dst, d["shade"][cut] * 0.40 * al, (0, 0, 0))
            layer(dst, M[cut] * (1 - ww) * 0.55 * al, UNSUNG)
            layer(dst, d["glow2"][cut] * ww * (0.45 + 0.5 * bb) * al, GLOW2)
            layer(dst, d["glow"][cut] * ww * (0.65 + 0.35 * bb) * al, GLOW)
            layer(dst, M[cut] * ww * al, SUNG)
            layer(dst, M[cut] * ww * bb * 0.55 * al, GOLD)
            layer(dst, (d["sparks"][0][cut] * tw1 + d["sparks"][1][cut] * tw2) * ww * 0.9 * al, SUNG)
    # 走字前沿的四芒星和撒下的星尘
    tr = d["trail"]
    k0, k1 = np.searchsorted(tr["t"], [t - 1.4, t])
    if k1 > k0:
        hx = front(ln, d, tr["t"][k0:k1])
        for j, x in zip(range(k0, k1), hx):
            age = t - tr["t"][j]
            if age > tr["life"][j]:
                continue
            a = (1 - age / tr["life"][j]) ** 2 * (0.6 + 0.4 * math.sin(age * 3.0 + tr["ph"][j])) * (1 - dis)
            px = ox + x + tr["vx"][j] * age
            py = oy + d["base"] - 0.45 * em + tr["dy"][j] + tr["vy"][j] * age
            over(canvas, px, py, dot(tr["size"][j]), DUST[tr["col"][j]], 0.85 * a)
    if ln["ts"] <= t <= ln["te"] + 0.3 and al > 0.003:
        k = 1 - ease((t - ln["te"]) / 0.3)
        hx = float(front(ln, d, min(t, ln["te"] - 1e-3)))
        s = star(0.42 * em * (0.9 + 0.1 * math.sin(t * 1.3)))
        over(canvas, ox + hx, oy + d["base"] - 0.45 * em, s, (240, 246, 255), 0.95 * k * al)
        over(canvas, ox + hx, oy + d["base"] - 0.45 * em, dot(0.16 * em), GLOW2, 0.5 * k * al)
    # 唱完被换掉：字碎成星尘往上飘
    if t > ln["d"]:
        ex = d["exit"]
        span = M.shape[1]
        for j in range(len(ex["x"])):
            age = t - ln["d"] - 0.35 * ex["x"][j] / span           # 从左往右依次散
            if age <= 0 or age > ex["life"][j]:
                continue
            a = (1 - age / ex["life"][j]) ** 1.5 * (0.65 + 0.35 * math.sin(age * 2.5 + ex["ph"][j]))
            px = ox + ex["x"][j] + ex["vx"][j] * age
            py = oy + ex["y"][j] + ex["vy"][j] * age
            over(canvas, px, py, dot(ex["size"][j]), DUST[ex["col"][j]], 0.8 * a)


def draw_count(canvas, t):
    """开唱前的倒数：上面那行左上方三颗小星，一拍灭一颗。"""
    em = L.LYRIC_EM * G["H"]
    for t0, ts, step in G["counts"]:
        if not (t0 <= t <= ts + 0.3):
            continue
        for k in range(3):
            off = ts - (2 - k) * step                               # 第 k 颗在这时灭
            a = ease((t - t0) / 0.4) * (1 - ease((t - off) / 0.25))
            if a <= 0.003:
                continue
            x = L.LYRIC_X[0] * G["W"] + 0.12 * em + k * 0.5 * em - G["rx"]
            y = L.LYRIC_Y[0] * G["H"] - 1.25 * em - G["ry"]
            tw = 0.8 + 0.2 * math.sin(t * 1.1 + k)
            over(canvas, x, y, star(0.2 * em), GOLD, a * tw)
            over(canvas, x, y, dot(0.07 * em), (255, 255, 255), a)


def setup(a):
    song = json.load(open(os.path.join(a.case, "song.json"), encoding="utf-8"))
    plan = json.load(open(os.path.join(a.case, "plan.json"), encoding="utf-8"))
    bands = np.load(os.path.join(a.case, "audio", "bands.npz"))
    fps0 = int(bands["fps"])
    end = float(song.get("end") or bands["duration"])
    rows = parse_lrc(os.path.join(a.case, song["lyrics"]))
    lines = timing(rows, bands["vocal"].astype(np.float32), fps0, end)
    counts = schedule(lines, plan["title_end"], 60.0 / plan["bpm"])
    H = a.height
    W = H * 16 // 9
    em = L.LYRIC_EM * H
    rx = 0
    rw = int(math.ceil(max(x + w for x, w in zip(L.LYRIC_X, L.LYRIC_W)) * W + 2.5 * em)) & ~1
    ry = int(L.LYRIC_Y[0] * H - 2.8 * em) & ~1
    rh = (int(L.LYRIC_Y[1] * H + 1.0 * em) - ry + 1) & ~1
    t0 = min(ln["a"] for ln in lines) - 0.2
    t1 = max(ln["d"] for ln in lines) + DISSOLVE + 1.6
    G.update(lines=lines, counts=counts, W=W, H=H, rx=rx, ry=ry, rw=rw, rh=rh, t0=t0, t1=t1, fps=a.fps, out=a.out,
             cache={}, sprites={})
    return int(math.ceil((t1 - t0) * a.fps)) + 1


def render(span):
    k0, k1 = span
    g = G
    for k in range(k0, k1):
        t = g["t0"] + k / g["fps"]
        canvas = np.zeros((g["rh"], g["rw"], 4), np.float32)      # 预乘 alpha
        for i, ln in enumerate(g["lines"]):
            if ln["a"] - 0.05 <= t <= ln["d"] + DISSOLVE + 1.5:
                draw_line(canvas, i, t)
        draw_count(canvas, t)
        nz = canvas[..., 3] > 1e-4
        canvas[..., :3][nz] /= canvas[..., 3][nz][..., None]
        Image.fromarray((np.clip(canvas, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
            os.path.join(g["out"], f"o_{k:05d}.png"), compress_level=1)
    return k1 - k0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("out")
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--procs", type=int, default=32)
    ap.add_argument("--range", type=float, nargs=2, metavar=("T0", "T1"), help="只画这段时间（秒）里的帧")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.startswith("o_") and f.endswith(".png"):
            os.remove(os.path.join(a.out, f))
    n = setup(a)
    k0, k1 = 0, n
    if a.range:
        k0 = max(0, int((a.range[0] - G["t0"]) * a.fps))
        k1 = min(n, int(math.ceil((a.range[1] - G["t0"]) * a.fps)) + 1)
    step = 30
    spans = [(k, min(k + step, k1)) for k in range(k0, k1, step)]
    with Pool(a.procs, initializer=setup, initargs=(a,)) as pool:
        done = sum(pool.imap_unordered(render, spans))
    json.dump(dict(x=G["rx"], y=G["ry"], fps=a.fps, t0=round(G["t0"], 4), frames=n),
              open(os.path.join(a.out, "region.json"), "w"))
    for ln in G["lines"]:
        print(f"{ln['ts']:7.2f}-{ln['te']:7.2f}  row {ln['row']}  on {ln['a']:7.2f}  off {ln['d']:7.2f}  {ln['text']}")
    print(f"lyrics: {len(G['lines'])} lines, {done} frames ({k0}-{k1}) from {G['t0']:.2f} s, region {G['rw']}x{G['rh']} "
          f"at ({G['rx']}, {G['ry']}) -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
