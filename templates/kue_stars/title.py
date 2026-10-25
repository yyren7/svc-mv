"""开头月亮旁边竖排的歌名、结尾右下角的制作信息，逐帧画成透明 PNG（和 onepic_player.py 一样，onepic_finish.py
用 --overlay 叠上去）：

    python templates/kue_stars/title.py cases/<歌> <输出目录> --part opening|ending [--height 1080] [--fps 60]

原来开头是场景里镜头前 0.5 米的 3D 字，靠景深对焦：EEVEE 的抗锯齿和景深把字边磨掉一层，放大、加粗了还是糊；
结尾是字幕（lrc2ass 的 Credit），字小、细，也没有出场。现在都按成片的分辨率直接画，字边是锐的。
场景里开头照样对焦在镜头前 0.5 米（背景虚着），焦点拉到脸上时开头的字跟着虚开。
- 浮现：一个字（结尾是一行）一个字地由虚到实（模糊从字号的 12% 收到 0）、从下面浮上来一点，同时亮一下柔光再收住。
- 退场：开头是焦点往脸上拉的那两秒（title_end 前 2 秒到 title_end），结尾是最后 1.6 秒，从上往下依次虚开、淡掉。
- 字后面垫一圈很淡的暗晕，亮的背景上也看得清。
开头的排版和 3D 那版一样：8 个字一列是基准大小，更短的按字数放大（最多 2 倍），9 个字以上分两列（从右往左、
第二列往下错开），下面一行小字是 artist。结尾按 credits.txt 一行一条，右对齐，第一行（歌名）大一号。
位置按 1080p 的成片量的（这张插画月亮右边），换插画要改 COL_X、TOP_Y。
region.json 的 t0 是第一帧的秒数（开头是 0，结尾是 credits_at 的起点）。
"""
import argparse
import json
import math
import os
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONTS = os.path.join(ROOT, "fonts")
COL_X, TOP_Y = 0.357, 0.126        # 开头：第一列的中心 x、第一个字的中心 y（画面宽 / 高的比例）
EM8 = 0.04                         # 开头：8 个字一列时的字号（画面高的比例）
END_X, END_Y = 0.955, 0.93         # 结尾：右边线、最后一行的下沿
END_EM, END_EM1 = 0.03, 0.048      # 结尾：每行的字号、第一行（歌名）的字号
COLOR, GLOW = (237, 245, 255), (175, 212, 255)
# 标题字体（游明朝）是日文字体，没有部分简体字（"绘"会画成方框）：缺字时这一行换成思源宋体的简体中文粗体
FALLBACK = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
IN_D = 1.1                         # 每个字（每行）浮现用的秒数

G = {}


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def glyph(text, font, bold):
    """一个字（或一行）的灰度遮罩，四周留够模糊和柔光的边（左右对称，遮罩中心就是字的中心）。"""
    l, t, r, b = font.getbbox(text, stroke_width=bold)
    pad = int(font.size * 0.6)
    im = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=font, fill=255, stroke_width=bold, stroke_fill=255)
    return im, r - l, b - t


_CMAPS = {}


def covers(path, text):
    if path not in _CMAPS:
        from fontTools.ttLib import TTFont
        f = TTFont(path, fontNumber=0, lazy=True)
        _CMAPS[path] = set(f.getBestCmap())
    return all(c.isspace() or ord(c) in _CMAPS[path] for c in text)


def fallback_index():
    """思源宋体 .ttc 里简体中文（SC）是第几个。"""
    if "sc" not in _CMAPS:
        from fontTools.ttLib import TTFont
        _CMAPS["sc"] = 0
        for i in range(10):
            try:
                if " SC" in TTFont(FALLBACK, fontNumber=i, lazy=True)["name"].getDebugName(1):
                    _CMAPS["sc"] = i
                    break
            except Exception:
                break
    return _CMAPS["sc"]


def font_for(path, px, text):
    """path 的字体，缺 text 里的字时换成思源宋体（简体中文）。"""
    if covers(path, text):
        return ImageFont.truetype(path, int(round(px)))
    return ImageFont.truetype(FALLBACK, int(round(px)), index=fallback_index())


def opening(song, plan, W, H):
    """[(遮罩, 中心 x, 中心 y, 进场秒, 退场开始, 退场结束, 不透明度上限)], 字号"""
    chars = [c for c in song["title"] if not c.isspace()]
    n = len(chars)
    per = n if n <= 9 else -(-n // 2)
    s = min(2.0, 8.0 / max(per, 1))
    em = EM8 * s * H
    line = 1.34 * em
    path = os.path.join(FONTS, song.get("title_font", "yumindb.ttf"))
    bold = max(1, int(round(em * 0.025)))
    end = plan["title_end"]
    stagger = min(0.35, 2.4 / n)
    items = []
    for i, ch in enumerate(chars):
        col, row = divmod(i, per)
        m, _, _ = glyph(ch, font_for(path, em, ch), bold)
        items.append((m, COL_X * W - col * 1.45 * line, TOP_Y * H + (row + 0.9 * col) * line,
                      1.2 + stagger * i, end - 2.0 + 0.12 * i, end, 1.0))
    if song.get("artist"):
        cjk = any(ord(c) >= 0x2E80 for c in song["artist"])
        afont = song.get("artist_font", song.get("title_font", "yumindb.ttf") if cjk else "DINNextLTPro-Light.ttf")
        f2 = font_for(os.path.join(FONTS, afont), em * (0.55 if cjk else 0.34), song["artist"])
        ncol, last = divmod(n - 1, per)
        m, _, _ = glyph(song["artist"], f2, max(1, bold // 2))
        items.append((m, COL_X * W - ncol * 1.45 * line, TOP_Y * H + (last + 0.9 * ncol) * line + 1.2 * line,
                      3.6, end - 2.0 + 0.12 * n, end, 0.85))
    return items, em, 0.0, end


def ending(song, plan, W, H, case):
    lines = [ln.strip() for ln in open(os.path.join(case, song["credits"]), encoding="utf-8-sig") if ln.strip()]
    t0, t1 = plan["credits_at"]
    em, em1 = END_EM * H, END_EM1 * H
    path = os.path.join(FONTS, song.get("title_font", "yumindb.ttf"))
    rows = []
    for i, ln in enumerate(lines):
        big = i == 0 and len(lines) > 1
        px = em1 if big else em
        rows.append((glyph(ln, font_for(path, px, ln), max(1, int(round(px * 0.025)))), big))
    # 从最后一行往上排：每行 1.55 个字号，歌名下面多空半行
    y = END_Y * H
    pos = []
    for (g, big) in reversed(rows):
        h = (em1 if big else em)
        pos.append(y - h / 2)
        y -= h * 1.55 + (0.5 * em if big else 0)
    pos.reverse()
    items = []
    for i, (((m, tw, _), big), cy) in enumerate(zip(rows, pos)):
        items.append((m, END_X * W - tw / 2, cy, t0 + 0.3 * i, t1 - 1.6 + 0.12 * i, t1, 1.0 if big else 0.9))
    return items, em1, t0, t1


def setup(a):
    song = json.load(open(os.path.join(a.case, "song.json"), encoding="utf-8"))
    plan = json.load(open(os.path.join(a.case, "plan.json"), encoding="utf-8"))
    H = a.height
    W = H * 16 // 9
    items, em, t0, t1 = opening(song, plan, W, H) if a.part == "opening" else ending(song, plan, W, H, a.case)
    # 叠放的区域：所有字的范围（加上浮上来的那一点）
    x0 = min(cx - m.width / 2 for m, cx, *_ in items)
    x1 = max(cx + m.width / 2 for m, cx, *_ in items)
    y0 = min(cy - m.height / 2 for m, _, cy, *_ in items)
    y1 = max(cy + m.height / 2 for m, _, cy, *_ in items) + 0.2 * em
    rx, ry = max(0, int(x0)) & ~1, max(0, int(y0)) & ~1
    rw, rh = (min(W, int(math.ceil(x1))) - rx + 1) & ~1, (min(H, int(math.ceil(y1))) - ry + 1) & ~1
    G.update(items=items, em=em, rx=rx, ry=ry, rw=rw, rh=rh, t0=t0, fps=a.fps, out=a.out)
    return int(math.ceil((t1 - t0) * a.fps)) + 2


def frame(k):
    g = G
    t = g["t0"] + k / g["fps"]
    canvas = np.zeros((g["rh"], g["rw"], 4), np.float32)      # 预乘 alpha
    for m, cx, cy, t_in, o0, o1, top in g["items"]:
        em = m.height / 2.2
        p = ease((t - t_in) / IN_D)
        q = ease((t - o0) / max(o1 - o0, 0.3))
        a = top * p * (1 - q)
        if a <= 0.002:
            continue
        blur = em * (0.12 * (1 - p) ** 2 + 0.3 * q ** 1.5)
        rise = em * 0.18 * (1 - p)
        flash = 0.55 * math.exp(-(((t - t_in) - 0.55 * IN_D) / (0.35 * IN_D)) ** 2) + 0.18
        mask = np.asarray(m.filter(ImageFilter.GaussianBlur(blur)) if blur > 0.3 else m, np.float32) / 255
        glow = np.asarray(m.filter(ImageFilter.GaussianBlur(em * 0.14 + blur)), np.float32) / 255
        shade = np.asarray(m.filter(ImageFilter.GaussianBlur(em * 0.28 + blur)), np.float32) / 255
        x = int(round(cx - m.width / 2)) - g["rx"]
        y = int(round(cy - m.height / 2 + rise)) - g["ry"]
        sx0, sy0 = max(0, -x), max(0, -y)
        sx1, sy1 = min(m.width, g["rw"] - x), min(m.height, g["rh"] - y)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        dst = canvas[y + sy0:y + sy1, x + sx0:x + sx1]
        # 从下往上叠：暗晕（压暗后面）-> 柔光 -> 字
        for layer, color, k_ in ((shade, (0, 0, 0), 0.6), (glow, GLOW, 0.6 * flash), (mask, COLOR, 1.0)):
            al = np.clip(layer[sy0:sy1, sx0:sx1] * k_ * a, 0, 1)
            dst[..., :3] = dst[..., :3] * (1 - al[..., None]) + np.array(color, np.float32) / 255 * al[..., None]
            dst[..., 3] = dst[..., 3] * (1 - al) + al
    nz = canvas[..., 3] > 1e-4
    canvas[..., :3][nz] /= canvas[..., 3][nz][..., None]      # 预乘 -> 直通 alpha
    Image.fromarray((np.clip(canvas, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(g["out"], f"o_{k:05d}.png"), compress_level=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("out")
    ap.add_argument("--part", choices=("opening", "ending"), default="opening")
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--procs", type=int, default=32)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.startswith("o_") and f.endswith(".png"):
            os.remove(os.path.join(a.out, f))
    if a.part == "ending":
        song = json.load(open(os.path.join(a.case, "song.json"), encoding="utf-8"))
        if not song.get("credits") or not os.path.exists(os.path.join(a.case, song["credits"])):
            json.dump(dict(x=0, y=0, fps=a.fps, t0=0.0, frames=0), open(os.path.join(a.out, "region.json"), "w"))
            print("ending: 没有制作信息（song.json 的 credits），不画", flush=True)
            return      # 没有 o_00000.png，onepic_finish 会跳过这一层
    n = setup(a)
    with Pool(a.procs, initializer=setup, initargs=(a,)) as pool:
        pool.map(frame, range(n), chunksize=8)
    json.dump(dict(x=G["rx"], y=G["ry"], fps=a.fps, t0=G["t0"], frames=n), open(os.path.join(a.out, "region.json"), "w"))
    print(f"{a.part}: {n} frames from {G['t0']:.2f} s, region {G['rw']}x{G['rh']} at ({G['rx']}, {G['ry']}) -> {a.out}",
          flush=True)


if __name__ == "__main__":
    main()
