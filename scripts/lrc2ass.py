"""LRC 歌词（可带中文翻译）+ 制作信息 -> ASS 字幕，给 onepic_finish.py 烧进成片。

    python lrc2ass.py <输出.ass> [--lrc 歌词.lrc] [--tlrc 翻译.lrc] [--offset 0.0] [--credits 制作信息.txt]
                      [--credits-at 322 334] [--res 3840 2160]

- 双语 LRC：同一个时间戳出现两行时，第一行是原文、第二行是译文；也可以把译文放在单独的 --tlrc 里（按时间戳配对）。
  "作词 : …""作曲 : …"这类信息行跳过。
- 每句显示到下一句开始（最长 8 秒）；原文在上、译文在下，左对齐（一图流的人物多在中间偏右）。--style 选摆法：
  - line（默认，kimishira 成片那种）：一次一句，左下角，淡入淡出 0.25 秒；
  - stagger：左边中部的天空里上下两个位置交替，下面那个往右错开一点。下一句提前半透明挂在另一个位置，
    开唱时从左到右一个字一个字亮起来、由虚变实，整句往上浮一点；唱完淡出。中间停顿超过 3 秒就不提前挂，
    下一句从上面那个位置重新开始。字太多时按宽度缩小。
- --offset 秒：歌词整体提前（负）或推后（正），对不上拍时用。
- 制作信息：文本文件，每行一条，在 --credits-at 的时间段里显示在右下角。
字体：原文 Noto Serif CJK JP（歌词里没有假名就用 SC），译文 Noto Serif CJK SC（服务器上 fc-list 能找到）。
"""
import argparse
import re

KANA = re.compile(r"[぀-ヿ]")

TAG = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
META = re.compile(r"^(作词|作曲|编曲|制作人|演唱|原唱|词|曲|by)\s*[:：]", re.I)   # 网易云 LRC 开头的信息行


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


def ts(t):
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def esc(s):
    return s.replace("{", "｛").replace("}", "｝")


def lrc_lines(rows, trans):
    """(时间, 原文, 译文, 结束)：同一时间戳的第二行是译文；结束 = 下一行（空行也算）开始，最长 8 秒。"""
    lines = []
    for t, text in rows:
        if lines and abs(lines[-1][0] - t) < 1e-3 and not lines[-1][2] and text:
            lines[-1] = (lines[-1][0], lines[-1][1], text)
        else:
            lines.append((t, text, trans.get(t, "")))
    return [(t, jp, cn, min(lines[i + 1][0] if i + 1 < len(lines) else t + 6, t + 8))
            for i, (t, jp, cn) in enumerate(lines)]


def ms(x):
    return int(round(x * 1000))


def stagger(lines, off, k):
    """--style stagger 的事件。位置按 1080p 定（左边中部的天空），k 换算到实际分辨率。"""
    dual = any(cn for _, _, cn, _ in lines)
    gap = 118 if dual else 92                      # 上下两个位置的间距
    slots = [(120, 560 - (20 if dual else 0)), (182, 560 - (20 if dual else 0) + gap)]
    width = [780, 700]                             # 再往右是人物的头发
    size, sp = 64, 4
    adv = 0.69 * size + sp                          # 一个字实际占的宽（CJK 字形约是字号的 0.69）
    dim, rise, lead, sweep_max = 0xA0, 8, 4.0, 0.8
    ev = []
    sung = [(t + off, jp, cn, e + off) for t, jp, cn, e in lines if jp]
    slot = 0
    for i, (t, jp, cn, end) in enumerate(sung):
        prev = sung[i - 1] if i else None
        joined = prev is not None and t - prev[3] < 3.0           # 和上一句连着：提前挂出来，位置交替
        slot = 1 - slot if joined else 0
        t0 = max(prev[0], t - lead) if joined else t - 0.35
        if joined and i >= 2:
            t0 = max(t0, sung[i - 2][3] + 0.15)                   # 同一个位置上上上句淡完了再挂
        t1 = end + 0.1
        x, y = slots[slot]
        n = len(jp)
        sc = min(1.0, width[slot] / (n * adv))
        act = ms(t - t0)                                          # 事件里开唱的那一刻
        sweep = min(sweep_max, 0.3 * (end - t))

        def chars(text, a_dim, a_on, extra_on="", extra_off=""):
            """一个字一个字从 a_dim 亮到 a_on（\\alpha 或 \\3a 之类的标签名在 a_* 里给全）。"""
            out = []
            m = max(len(text), 1)
            for j, ch in enumerate(text):
                d0 = act + ms(sweep * j / m)
                out.append(f"{{{a_dim}{extra_off}\\t({d0},{d0 + 350},{a_on}{extra_on})}}{esc(ch)}")
            return "".join(out)

        fad = f"\\fad({ms(0.35)},{ms(0.45)})"
        mv = f"\\move({x * k:.0f},{(y + rise) * k:.0f},{x * k:.0f},{y * k:.0f},{act},{act + 600})"
        base = f"\\an1{mv}{fad}\\fscx{sc * 100:.0f}\\fscy{sc * 100:.0f}"
        # 底下一层模糊的深蓝粗描边当暗光晕（亮背景上也读得出），一层很淡的蓝白星光，最上面是字
        ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},JP,,0,0,0,,{{{base}\\1a&HFF&\\3c&H301808&\\bord{8 * k:.0f}\\blur{9 * k:.0f}}}"
                  + chars(jp, "\\3a&HF4&", "\\3a&H68&"))
        ev.append(f"Dialogue: 1,{ts(t0)},{ts(t1)},JP,,0,0,0,,{{{base}\\1a&HFF&\\3c&HFFE2C4&\\bord{3 * k:.0f}\\blur{7 * k:.0f}}}"
                  + chars(jp, "\\3a&HFF&", "\\3a&HB8&"))
        ev.append(f"Dialogue: 2,{ts(t0)},{ts(t1)},JP,,0,0,0,,{{{base}\\bord0}}"
                  + chars(jp, f"\\alpha&H{dim:02X}&", "\\alpha&H00&", f"\\blur{0.7 * k:.1f}", f"\\blur{1.4 * k:.1f}"))
        # 字下面一道细光，开唱时从左往右划开，唱完跟着淡出
        w = n * adv * sc + 24
        shape = f"m 0 0 l {w * k:.0f} 0 {w * k:.0f} {1.6 * k:.1f} 0 {1.6 * k:.1f}"
        ev.append(f"Dialogue: 1,{ts(t0)},{ts(t1)},JP,,0,0,0,,{{\\an7\\pos({x * k:.0f},{(y + 12) * k:.0f}){fad}\\bord0"
                  f"\\blur{1.5 * k:.1f}\\1c&HFFEAD2&\\alpha&HFF&\\fscx0\\t({act},{act + ms(sweep) + 500},0.6,"
                  f"\\fscx100\\alpha&H50&)\\p1}}{shape}{{\\p0}}")
        if cn:
            cy = y + 46
            mv2 = f"\\move({x * k:.0f},{(cy + rise) * k:.0f},{x * k:.0f},{cy * k:.0f},{act},{act + 600})"
            b2 = f"\\an1{mv2}{fad}"
            on = f"\\t({act},{act + 500},\\alpha&H00&)"
            ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},CN,,0,0,0,,{{{b2}\\1a&HFF&\\3c&H301808&\\bord{7 * k:.0f}"
                      f"\\blur{8 * k:.0f}\\3a&HE8&\\t({act},{act + 500},\\3a&H70&)}}{esc(cn)}")
            ev.append(f"Dialogue: 2,{ts(t0)},{ts(t1)},CN,,0,0,0,,{{{b2}\\bord0\\blur{0.7 * k:.1f}"
                      f"\\alpha&H{dim:02X}&{on}}}{esc(cn)}")
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--lrc")
    ap.add_argument("--tlrc")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--credits")
    ap.add_argument("--credits-at", type=float, nargs=2, default=(322.0, 334.0))
    ap.add_argument("--res", type=int, nargs=2, default=(3840, 2160))
    ap.add_argument("--lift", type=float, default=0, help="歌词整体上抬（1080p 下的像素），给左下角的旋律盘让位（line）")
    ap.add_argument("--style", choices=("line", "stagger"), default="line")
    a = ap.parse_args()
    W, H = a.res
    k = H / 1080
    lift = a.lift * k
    rows = parse_lrc(a.lrc) if a.lrc else []
    jp_font = "Noto Serif CJK JP" if any(KANA.search(text) for _, text in rows) else "Noto Serif CJK SC"
    size, sp = (64, 4) if a.style == "stagger" else (62, 2)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,{jp_font},{int(size * k)},&H00FFFFFF,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{sp * k:.0f},0,1,{2.4 * k:.1f},0,1,{int(110 * k)},{int(80 * k)},{int(112 * k + lift)},1
Style: CN,Noto Serif CJK SC,{int(42 * k)},&H00F4ECE6,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{1 * k:.0f},0,1,{1.9 * k:.1f},0,1,{int(113 * k)},{int(80 * k)},{int(56 * k + lift)},1
Style: Credit,Noto Serif CJK SC,{int(34 * k)},&H00F4ECE6,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{2 * k:.0f},0,1,{1.5 * k:.1f},0,3,{int(90 * k)},{int(110 * k)},{int(70 * k)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    lines = lrc_lines(rows, dict(parse_lrc(a.tlrc)) if a.tlrc else {}) if a.lrc else []
    if a.style == "stagger":
        ev += stagger(lines, a.offset, k)
    else:
        for t, jp, cn, end in lines:
            if not jp:
                continue
            t0, t1 = t + a.offset, end + a.offset - 0.05
            # 底下先画一层模糊的深蓝粗描边当暗光晕，亮背景（白裙、花田）上也读得出；再画字
            glow = f"{{\\fad(250,250)\\blur{8 * k:.0f}\\bord{8 * k:.0f}\\1a&HFF&\\3c&H301808&\\3a&H60&}}"
            # 每种事件各占一个图层：同一图层里同时出现的事件会被 libass 错开摆放（光晕会被推到别处）
            ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},JP,,0,0,0,,{glow}{esc(jp)}")
            ev.append(f"Dialogue: 2,{ts(t0)},{ts(t1)},JP,,0,0,0,,{{\\fad(250,250)\\blur{0.8 * k:.1f}}}{esc(jp)}")
            if cn:
                ev.append(f"Dialogue: 1,{ts(t0)},{ts(t1)},CN,,0,0,0,,{glow}{esc(cn)}")
                ev.append(f"Dialogue: 3,{ts(t0)},{ts(t1)},CN,,0,0,0,,{{\\fad(250,250)\\blur{0.8 * k:.1f}}}{esc(cn)}")
    if a.credits:
        lines = [ln.rstrip() for ln in open(a.credits, encoding="utf-8-sig") if ln.strip()]
        t0, t1 = a.credits_at
        ev.append(f"Dialogue: 4,{ts(t0)},{ts(t1)},Credit,,0,0,0,,{{\\fad(800,1200)}}" + "\\N".join(map(esc, lines)))
    open(a.out, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    print(f"{len(ev)} events -> {a.out}")


if __name__ == "__main__":
    main()
