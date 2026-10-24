"""一图流 PV 左下角的"旋律盘"：半透明的唱片 + 一圈跟着音乐跳的频谱 + 歌名和进度条，逐帧画成透明 PNG，
onepic_finish.py 用 --overlay 叠到视频上。在 AutoDL 上跑（ComfyUI venv 有 PIL / numpy），多进程：

    python onepic_player.py <bands.npz> <输出目录> --art <唱片图> --art-uv 0.179 0.142 0.06 \
        --title 君の知らない物語 --sub "supercell · cover 旬夏" --fps 30 --height 540

- 唱片：从图里按 --art-uv（中心 u、v，半径按画面宽的比例）裁一个圆，慢慢转；低音来时整个盘和光晕像心跳一样鼓一下。
- 频谱：bands.npz 的 spec，72 根柱子绕盘一圈，左右对称（低频在下）。
- 文字：歌名、副标题、进度条和时间。
不给 --art 就不画唱片和频谱（画面里已经有旋律盘，比如月亮外圈的频谱），只留一条窄的歌名、进度条和时间。
--show t0 t1 只在这段时间里显示（前后淡入淡出），给开头的大标题和结尾的制作信息让开，同一时间画面上只有一处歌名。
尺寸按 1080p 设计，--height 等比缩放；输出 o_00000.png ...（第 k 张是 k / fps 秒），和 region.json（叠放的位置）。
"""
import argparse
import json
import math
import os
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "fonts")
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W0, H0 = 880, 236            # 区域大小（1080p 下）
C0, R0 = (124, 118), 60      # 唱片中心和半径
W1, H1 = 640, 150            # 不画唱片时的区域大小
SS = 2                       # 超采样

G = {}


def mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def setup(a):
    k = a.height / 1080 * SS
    d = np.load(a.bands)
    G.update(a=a, k=k, spec=d["spec"].astype(np.float32), bass=d["bass"], fps0=int(d["fps"]),
             dur=float(d["duration"]))
    if not a.art:
        setup_bar(a, k)
        return
    art = Image.open(a.art).convert("RGB")
    cu, cv, cr = a.art_uv
    cx, cy, r = cu * art.width, cv * art.height, cr * art.width
    disc = art.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r))).resize((int(2 * R0 * k),) * 2, Image.LANCZOS)
    G["disc"] = disc
    size = (int(W0 * k), int(H0 * k))
    # 不变的部分：文字、进度条的底、唱片后面的暗底和光晕
    static = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(static)
    cx, cy = C0[0] * k, C0[1] * k
    # 暗底：整块柔边的半透明深色板，花田很亮时文字和进度条也看得清；唱片后面再深一点
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    sh = ImageDraw.Draw(shade)
    sh.rounded_rectangle([34 * k, 30 * k, 800 * k, 206 * k], radius=60 * k, fill=(6, 10, 28, 105))
    sh.ellipse([cx - (R0 + 48) * k, cy - (R0 + 48) * k, cx + (R0 + 48) * k, cy + (R0 + 48) * k], fill=(6, 10, 28, 120))
    static.alpha_composite(shade.filter(ImageFilter.GaussianBlur(16 * k)))
    tf = ImageFont.truetype(os.path.join(FONTS, "yumindb.ttf"), int(40 * k))
    sf = ImageFont.truetype(NOTO, int(22 * k))
    x0 = 222 * k
    for dx, dy, col in ((2, 2, (0, 0, 0, 120)), (0, 0, (244, 248, 255, 240))):
        sd.text((x0 + dx * k, 44 * k + dy * k), a.title, font=tf, fill=col)
        sd.text((x0 + dx * k, 104 * k + dy * k), a.sub, font=sf, fill=col[:3] + (int(col[3] * 0.85),))
    G["static"] = static
    G["bar"] = (x0, 160 * k, 760 * k)
    G["time_y"] = 172 * k             # 时间在进度条下面、右对齐
    G["tf"] = ImageFont.truetype(os.path.join(FONTS, "DINNextLTPro-Light.ttf"), int(20 * k))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - R0 * 1.25 * k, cy - R0 * 1.25 * k, cx + R0 * 1.25 * k, cy + R0 * 1.25 * k],
                                 fill=(170, 205, 255, 255))
    G["glow"] = glow.filter(ImageFilter.GaussianBlur(18 * k))
    yy, xx = np.mgrid[:disc.height, :disc.width]
    rr = np.hypot(xx - disc.width / 2 + 0.5, yy - disc.height / 2 + 0.5) / (disc.width / 2)
    G["disc_mask"] = Image.fromarray((np.clip((1 - rr) * disc.width / 2, 0, 1) * 255).astype(np.uint8))


def setup_bar(a, k):
    """不画唱片：歌名、副标题（右边是时间）、进度条，垫一块柔边的深色底板。"""
    size = (int(W1 * k), int(H1 * k))
    static = Image.new("RGBA", size, (0, 0, 0, 0))
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle([22 * k, 16 * k, 600 * k, 134 * k], radius=50 * k, fill=(6, 10, 28, 100))
    static.alpha_composite(shade.filter(ImageFilter.GaussianBlur(16 * k)))
    sd = ImageDraw.Draw(static)
    tf = ImageFont.truetype(os.path.join(FONTS, "yumindb.ttf"), int(38 * k))
    sf = ImageFont.truetype(NOTO, int(21 * k))
    x0 = 64 * k
    for dx, dy, col in ((2, 2, (0, 0, 0, 120)), (0, 0, (244, 248, 255, 240))):
        sd.text((x0 + dx * k, 22 * k + dy * k), a.title, font=tf, fill=col)
        sd.text((x0 + dx * k, 76 * k + dy * k), a.sub, font=sf, fill=col[:3] + (int(col[3] * 0.85),))
    G["static"] = static
    G["bar"] = (x0, 120 * k, 560 * k)
    G["time_y"] = 80 * k              # 时间在副标题那一行、右对齐
    G["tf"] = ImageFont.truetype(os.path.join(FONTS, "DINNextLTPro-Light.ttf"), int(20 * k))


def shown(t):
    """--show 的出现程度，0..1：t0 起淡入、t1 淡出完，淡入淡出各 --fade 秒（smoothstep）。"""
    a = G["a"]
    if not a.show:
        return 1.0
    x = min((t - a.show[0]) / a.fade, (a.show[1] - t) / a.fade, 1.0)
    return 0.0 if x <= 0 else x * x * (3 - 2 * x)


def frame(i):
    a, k = G["a"], G["k"]
    t = i / a.fps
    s = shown(t)
    path = os.path.join(a.out, f"o_{i:05d}.png")
    if s <= 0:
        Image.new("RGBA", (G["static"].width // SS, G["static"].height // SS)).save(path, compress_level=1)
        return
    f0 = min(int(round(t * G["fps0"])), len(G["bass"]) - 1)
    spec, bass = G["spec"][f0], float(G["bass"][f0])
    pulse = bass ** 2
    img = G["static"].copy()
    if "disc" in G:
        disc_frame(img, t, spec, pulse)
    d = ImageDraw.Draw(img)
    # 进度条和时间；进度点跟低音轻轻鼓一下
    x0, y, x1 = G["bar"]
    p = min(t / G["dur"], 1.0)
    d.line([x0, y, x1, y], fill=(230, 238, 255, 70), width=int(3 * k))
    d.line([x0, y, x0 + (x1 - x0) * p, y], fill=(236, 243, 255, 225), width=int(3 * k))
    kx, kr = x0 + (x1 - x0) * p, (5.5 + 2.5 * pulse) * k
    d.ellipse([kx - kr, y - kr, kx + kr, y + kr], fill=(246, 249, 255, 240))
    txt = f"{mmss(t)} / {mmss(G['dur'])}"
    tw = d.textlength(txt, font=G["tf"])
    d.text((x1 - tw, G["time_y"]), txt, font=G["tf"], fill=(230, 238, 255, 210))
    out = img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
    if s < 1:
        out.putalpha(out.getchannel("A").point(lambda v: int(v * s + 0.5)))
    out.save(path, compress_level=1)


def disc_frame(img, t, spec, pulse):
    """唱片、光晕和一圈频谱。"""
    k = G["k"]
    cx, cy = C0[0] * k, C0[1] * k
    # 光晕：跟低音呼吸
    g = G["glow"].copy()
    g.putalpha(g.getchannel("A").point(lambda v: int(v * (0.18 + 0.32 * pulse))))
    img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    # 频谱：72 根，右半圈从下往上 36 段，左半圈镜像
    n = 36
    r_in = (R0 * (1 + 0.05 * pulse) + 9) * k
    for j in range(2 * n):
        b = j if j < n else 2 * n - 1 - j
        val = float(spec[int(b * len(spec) / n)])
        L = (3 + 30 * val ** 1.3) * k
        th = -math.pi / 2 + (b + 0.5) / n * math.pi
        if j >= n:
            th = math.pi - th
        c, s = math.cos(th), -math.sin(th)
        x1, y1, x2, y2 = cx + c * r_in, cy + s * r_in, cx + c * (r_in + L), cy + s * (r_in + L)
        wdt = 3.2 * k
        col = (222, 236, 255, int(150 + 90 * val))
        d.line([x1, y1, x2, y2], fill=col, width=int(wdt))
        for px, py in ((x1, y1), (x2, y2)):
            d.ellipse([px - wdt / 2, py - wdt / 2, px + wdt / 2, py + wdt / 2], fill=col)
    # 唱片：月亮慢慢转，跟低音鼓一下
    scale = 1 + 0.05 * pulse
    disc = G["disc"].rotate(-t * 15 % 360, resample=Image.BICUBIC)
    size = int(G["disc"].width * scale)
    disc = disc.resize((size, size), Image.BICUBIC)
    mask = G["disc_mask"].resize((size, size), Image.BICUBIC).point(lambda v: int(v * 0.92))
    img.paste(disc, (int(cx - size / 2), int(cy - size / 2)), mask)
    rr = size / 2
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(235, 242, 255, 170), width=int(2 * k))
    d.ellipse([cx - rr * 0.62, cy - rr * 0.62, cx + rr * 0.62, cy + rr * 0.62], outline=(10, 14, 32, 70), width=int(2 * k))
    d.ellipse([cx - 6 * k, cy - 6 * k, cx + 6 * k, cy + 6 * k], fill=(12, 16, 34, 220), outline=(235, 242, 255, 200),
              width=int(1.5 * k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bands")
    ap.add_argument("out")
    ap.add_argument("--art", help="唱片图；不给就不画唱片和频谱")
    ap.add_argument("--art-uv", type=float, nargs=3, default=(0.5, 0.5, 0.1))
    ap.add_argument("--title", required=True)
    ap.add_argument("--sub", default="")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--height", type=int, default=2160)
    ap.add_argument("--x", type=float, default=36, help="区域左上角，1080p 下的像素")
    ap.add_argument("--y", type=float, help="默认贴底，离下边 26")
    ap.add_argument("--procs", type=int, default=64)
    ap.add_argument("--seconds", type=float, help="只画前这么多秒（预览用）；进度条和时间仍按整首算")
    ap.add_argument("--show", type=float, nargs=2, metavar=("T0", "T1"),
                    help="只在这段时间里显示：t0 起淡入、t1 淡出完（开头的大标题、结尾的制作信息时让开）；不给就一直在")
    ap.add_argument("--fade", type=float, default=1.5, help="--show 的淡入淡出秒数")
    a = ap.parse_args()
    if a.y is None:
        a.y = 1080 - (H0 if a.art else H1) - 26
    os.makedirs(a.out, exist_ok=True)
    setup(a)
    n = int(min(G["dur"], a.seconds or G["dur"]) * a.fps)
    with Pool(a.procs, initializer=setup, initargs=(a,)) as pool:
        for _ in pool.imap_unordered(frame, range(n), chunksize=16):
            pass
    k = a.height / 1080
    json.dump({"x": int(a.x * k), "y": int(a.y * k), "fps": a.fps, "frames": n},
              open(os.path.join(a.out, "region.json"), "w"))
    print(f"{n} frames -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
