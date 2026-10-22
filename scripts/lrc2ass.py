"""LRC 歌词（可带中文翻译）+ 制作信息 -> ASS 字幕，给 onepic_finish.py 烧进成片。

    python lrc2ass.py <输出.ass> [--lrc 歌词.lrc] [--tlrc 翻译.lrc] [--offset 0.0] [--credits 制作信息.txt]
                      [--credits-at 322 334] [--res 3840 2160]

- 双语 LRC：同一个时间戳出现两行时，第一行是原文、第二行是译文；也可以把译文放在单独的 --tlrc 里（按时间戳配对）。
  "作词 : …""作曲 : …"这类信息行跳过。
- 每句显示到下一句开始（最长 8 秒），淡入淡出 0.25 秒；原文在上、译文在下，左下角左对齐（一图流的人物多在中间偏右）。
- --offset 秒：歌词整体提前（负）或推后（正），对不上拍时用。
- 制作信息：文本文件，每行一条，在 --credits-at 的时间段里显示在右下角。
字体：原文 Noto Serif CJK JP，译文 Noto Serif CJK SC（服务器上 fc-list 能找到）。
"""
import argparse
import re

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--lrc")
    ap.add_argument("--tlrc")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--credits")
    ap.add_argument("--credits-at", type=float, nargs=2, default=(322.0, 334.0))
    ap.add_argument("--res", type=int, nargs=2, default=(3840, 2160))
    ap.add_argument("--lift", type=float, default=0, help="歌词整体上抬（1080p 下的像素），给左下角的旋律盘让位")
    a = ap.parse_args()
    W, H = a.res
    k = H / 1080
    lift = a.lift * k

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: JP,Noto Serif CJK JP,{int(62 * k)},&H00FFFFFF,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{2 * k:.0f},0,1,{2.4 * k:.1f},0,1,{int(110 * k)},{int(80 * k)},{int(112 * k + lift)},1
Style: CN,Noto Serif CJK SC,{int(42 * k)},&H00F4ECE6,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{1 * k:.0f},0,1,{1.9 * k:.1f},0,1,{int(113 * k)},{int(80 * k)},{int(56 * k + lift)},1
Style: Credit,Noto Serif CJK SC,{int(34 * k)},&H00F4ECE6,&H00FFFFFF,&H00502814,&H64000000,0,0,0,0,100,100,{2 * k:.0f},0,1,{1.5 * k:.1f},0,3,{int(90 * k)},{int(110 * k)},{int(70 * k)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if a.lrc:
        rows = parse_lrc(a.lrc)
        trans = dict(parse_lrc(a.tlrc)) if a.tlrc else {}
        lines = []          # (时间, 原文, 译文)
        for t, text in rows:
            if lines and abs(lines[-1][0] - t) < 1e-3 and not lines[-1][2] and text:
                lines[-1] = (lines[-1][0], lines[-1][1], text)      # 同一时间戳的第二行 = 译文
            else:
                lines.append((t, text, trans.get(t, "")))
        for i, (t, jp, cn) in enumerate(lines):
            if not jp:
                continue
            end = min(lines[i + 1][0] if i + 1 < len(lines) else t + 6, t + 8)
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
