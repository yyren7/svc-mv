"""模板的编排：从一首歌的 audio/bands.npz（scripts/audio_bands.py）和歌词排出段落、镜头、流星，以及三处歌名
（开头的大标题、左下角的歌名、结尾的制作信息）各自出现的时机，写进 <case>/plan.json。这是草稿，可以手改；
已有 plan.json 时不覆盖，除非 --force。在 AutoDL 上（只要 numpy）：
    $PY templates/kue_stars/plan.py make cases/<歌> [--force]      # 写 plan.json，打印段落表
    eval "$($PY templates/kue_stars/plan.py env cases/<歌>)"       # render.sh / preview.sh 用：歌名、文件、时机

怎么排的（照着 kimishira 手排的那份总结出来的）：
- 小节：拍子网格（grid_beat、grid_phase）上 4、6 或 8 拍一小节（按拍点强度的周期），重拍取最强的相位。
- 段落边界：每小节一个候选点，前后 2 小节、4 小节的响度、高频、低频、高音区、人声（有没有人在唱）差得多的地方切开，
  两刀至少隔约 7 秒；第一句歌词前、最后一句唱完后各切一刀。
- 每段的能量 = 这段的平均响度在整首里的位置（0.2–1.0，取到 0.05）；花瓣、光点、旋律盘、光束的开度按能量推。
  名字：开头安静的是 open，第一句前是 intro，唱完是 outro，中间没人唱的是 inst（间奏），有人唱的段落里最响的三成
  多是 chorus，能量 ≤ 0.45 的是 verse，其余 bridge。
- 镜头：始终看整张画，放大 1.04–1.10 倍；副歌升起一点、主歌左右慢慢挪、间奏往月亮那边偏、结尾漂向月亮；
  开头对焦在镜头前的标题上，标题淡出时拉回脸上。
- 流星：开头一颗，每段副歌两颗，间奏里约 2 秒一颗（流星雨），主歌里稀疏几颗，结尾一颗。
- 大标题在乐队进来（6–14 秒里第一个段落边界）后约 3 秒淡完（title_end），左下角的歌名在那之后 3 秒的第一个
  重拍淡入，最后一句唱完 1.5 秒淡出；制作信息在那之后的段落边界（或下一个重拍）出来，到片尾前 3.5 秒。
song.json 里给了 title_end、show、credits_at 就用给的。
"""
import json
import os
import re
import shlex
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 60


def load_song(case):
    song = json.load(open(os.path.join(case, "song.json"), encoding="utf-8"))
    for k in ("mix", "vocal", "lyrics", "lyrics_cn", "credits"):
        if song.get(k):
            song[k] = os.path.join(case, song[k])
    return song


def lyric_lines(path):
    """LRC -> [(秒, 文字)]（文字为空的是间奏开始的标记），跳过「作词 : ...」这类。"""
    out = []
    if not path or not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8-sig"):
        for m in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]", line):
            text = re.sub(r"\[[^\]]*\]", "", line).strip()
            if " : " in text or "：" in text[:6]:
                continue
            out.append((int(m.group(1)) * 60 + float(m.group(2)), text))
    return sorted(out)


def sung_spans(lines):
    """每句唱的时间段：到下一个时间标签，最长 8 秒。"""
    spans = []
    for (t0, text), (t1, _) in zip(lines, lines[1:] + [(1e9, "")]):
        if text:
            spans.append((t0, min(t1, t0 + 8.0)))
    return spans


def bars(d, dur):
    """小节的开始时刻：拍子网格上每 m 拍一小节。m 取 4、6、8 里拍点强度（低频 + 起音）自相关最强的（差不多一样强时
    取小的；kimishira 是 6，4/4 的歌是 4），重拍取这个周期里最强的那个相位。"""
    P, phi = float(d["grid_beat"]), float(d["grid_phase"])
    beats = phi + P * np.arange(int((dur - phi) / P) + 1)
    idx = np.clip((beats * FPS).astype(int), 0, len(d["bass"]) - 1)
    s = d["bass"][idx] / max(d["bass"].max(), 1e-6) + d["onset"][idx]
    s = s - s.mean()

    def ac(m):
        return float(np.dot(s[:-m], s[m:]) / np.sqrt(np.dot(s[:-m], s[:-m]) * np.dot(s[m:], s[m:]) + 1e-9))

    acs = {m: ac(m) for m in (4, 6, 8)}
    top = max(acs.values())
    m = min(k for k, v in acs.items() if v >= 0.9 * top)
    k = int(np.argmax([s[j::m].mean() for j in range(m)]))
    b = beats[k::m]
    if b[0] > 0.5:
        b = np.concatenate([[0.0], b])
    return b, P * m


def snap(t, grid):
    return float(grid[np.argmin(np.abs(grid - t))])


def make_sections(d, dur, spans):
    b, bar = bars(d, dur)
    n = len(b)
    edges = np.append(b, dur)
    upper = d["spec"][:, d["spec"].shape[1] * 2 // 3:].astype(np.float32).mean(1)
    feats = {"loud": d["loud"], "high": d["high"], "bass": d["bass"], "upper": upper}
    if d["vocal"].max() > 0:
        feats["vocal"] = d["vocal"]
    F = np.stack([[v[int(edges[i] * FPS):max(int(edges[i + 1] * FPS), int(edges[i] * FPS) + 1)].mean() for i in range(n)]
                  for v in feats.values()], 1)
    t_mid = (edges[:-1] + edges[1:]) / 2
    sing = np.array([any(a - 1.0 <= t <= c + 1.0 for a, c in spans) for t in t_mid], float)
    Z = np.concatenate([(F - F.mean(0)) / (F.std(0) + 1e-6), 1.5 * sing[:, None]], 1)
    nov = np.zeros(n)
    for i in range(2, n - 1):
        for w, k in ((4, 1.0), (2, 0.6)):
            lo, hi = max(i - w, 0), min(i + w, n)
            nov[i] += k * np.linalg.norm(Z[i:hi].mean(0) - Z[lo:i].mean(0))
    peaks = [i for i in range(2, n - 1) if nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1]]
    thr = np.median(nov[peaks]) if peaks else 0
    cuts = set()
    if spans:
        cuts.add(int(np.searchsorted(b, spans[0][0] - 0.3)) - 1)
        cuts.add(int(np.searchsorted(b, spans[-1][1])))
    cuts = {c for c in cuts if 0 < c < n}
    gap = max(3, int(round(7.0 / bar)))          # 两刀至少隔约 7 秒
    for i in sorted(peaks, key=lambda i: -nov[i]):
        if nov[i] < thr:
            break
        if all(abs(i - c) >= gap for c in cuts):
            cuts.add(i)
    cuts = sorted({0} | cuts)
    first_sung = spans[0][0] if spans else 0.0
    last_sung = spans[-1][1] if spans else dur
    lo, hi = np.percentile(F[:, 0], 10), np.percentile(F[:, 0], 95)
    Ln = np.clip((F[:, 0] - lo) / max(hi - lo, 1e-6), 0, 1)
    lo, hi = np.percentile(F[:, 1], 10), np.percentile(F[:, 1], 95)
    Hn = np.clip((F[:, 1] - lo) / max(hi - lo, 1e-6), 0, 1)
    raw, info = [], []
    for k, c in enumerate(cuts):
        e_ = cuts[k + 1] if k + 1 < len(cuts) else n
        raw.append(float((Ln[c:e_] + 0.5 * Hn[c:e_]).mean() / 1.5))
        info.append((float(b[c]), float(edges[e_]), sing[c:e_].mean() > 0.3))
    raw = np.array(raw)
    x = (raw - raw.min()) / max(raw.max() - raw.min(), 1e-6)
    sung_x = [x[k] for k, (_, _, s) in enumerate(info) if s]
    ch_thr = max(np.percentile(sung_x, 65) if sung_x else 1.0, 0.55)
    secs = []
    for k, (t0, t1, sung) in enumerate(info):
        energy = round((0.2 + 0.8 * float(x[k])) * 20) / 20
        if t0 == 0 and (not sung or energy <= 0.45):
            kind = "open"
        elif t1 <= first_sung + 0.5 and spans:
            kind = "intro"
        elif t0 >= last_sung - 0.5:
            kind = "outro"
        elif not sung:
            kind = "inst"
        elif x[k] >= ch_thr:
            kind = "chorus"
        elif energy <= 0.45:
            kind = "verse"
        else:
            kind = "bridge"
        petals = round(float(np.clip(1.05 * energy - 0.12, 0.1, 1.0)), 2)
        motes = round(float(np.clip(0.95 - 0.4 * energy, 0.5, 0.9)), 2)
        ring = round(float(np.clip(0.5 + 0.55 * energy, 0.45, 1.0)), 2)
        beams = {"open": 0.22, "intro": 0.18, "outro": 0.18, "inst": 0.18, "chorus": 0.15, "verse": 0.10}.get(kind, 0.12)
        secs.append([kind, round(t0, 2), energy, petals, motes, ring, beams])
    # 名字编号：chorus1、chorus2 …
    count = {}
    for s in secs:
        count[s[0]] = count.get(s[0], 0) + 1
        s[0] = f"{s[0]}{count[s[0]]}"
    if dur - 7.0 > secs[-1][1] + 4:
        secs.append(["end", round(dur - 7.0, 2), 0.25, 0.12, 0.6, 0.6, 0.22])
    return secs, b


def P_(u, v, zoom, dx=0.0, dy=0.0, dz=0.0):
    return dict(u=u, v=v, zoom=zoom, dx=dx, dy=dy, dz=dz)


def make_camera(secs, dur, title_end):
    """镜头关键帧：[秒, 机位]，机位有 u/v/zoom/dx/dy/dz（Camera.path 的写法）或者只有对焦（blur 和 focus_m / focus）。"""
    keys = [[0.0, dict(blur=0.014, focus_m="title")], [round(title_end - 2.85, 2), dict(blur=0.014, focus_m="title")],
            [round(title_end + 0.4, 2), dict(blur=0.003, focus="face")]]
    poses = [[0.0, P_(0.47, 0.46, 1.10, dx=-0.006)], [round(title_end - 2.85, 2), P_(0.48, 0.47, 1.09, dx=-0.004)]]
    side = 1
    for i, (name, t0, energy, *_) in enumerate(secs):
        t1 = secs[i + 1][1] if i + 1 < len(secs) else dur
        if t0 < title_end + 2:
            continue
        kind = name.rstrip("0123456789")
        if kind == "chorus":
            poses.append([t0, P_(0.50, 0.49, 1.05, dz=0.006)])
            if t1 - t0 > 16:
                poses.append([round(t0 + 0.6 * (t1 - t0), 2), P_(0.49 + 0.01 * side, 0.49, 1.04, dx=-0.008 * side, dz=0.010)])
        elif kind == "inst":
            poses.append([t0, P_(0.50, 0.48, 1.06)])
            if t1 - t0 > 10:
                poses.append([round(t0 + 0.6 * (t1 - t0), 2), P_(0.47, 0.46, 1.09)])
        elif kind in ("outro", "end"):
            poses.append([t0, P_(0.49, 0.48, 1.05)])
        else:
            poses.append([t0, P_(0.50 + 0.01 * side, 0.48, 1.06 + 0.01 * (side > 0), dx=0.006 * side)])
        side = -side
    poses.append([round(dur, 2), P_(0.46, 0.45, 1.08)])
    keep = []
    for t, p in poses:                    # 挨得太近（不到 3 秒）的留后一个
        if keep and t - keep[-1][0] < 3.0:
            keep[-1] = [t, p] if t >= keep[-1][0] else keep[-1]
            continue
        keep.append([t, p])
    return keys + keep


def make_meteors(secs, dur, spans, seed=11):
    rng = np.random.default_rng(seed)
    out = [5.0]
    for i, (name, t0, *_) in enumerate(secs):
        t1 = secs[i + 1][1] if i + 1 < len(secs) else dur
        kind = name.rstrip("0123456789")
        if kind == "chorus":
            out += [t0 + 4.2, t0 + rng.uniform(0.45, 0.75) * (t1 - t0)]
        elif kind == "inst" and t0 > 20:
            t = t0 + 2.0
            while t < t1 - 1.5:
                out.append(t)
                t += rng.uniform(1.4, 2.8)
        elif kind in ("verse", "bridge"):
            t = t0 + rng.uniform(4, 10)
            while t < t1 - 3:
                out.append(t)
                t += rng.uniform(10, 22)
        elif kind in ("outro", "end"):
            out.append(min(t0 + 6, dur - 4))
    return sorted(round(float(t), 2) for t in out if 1.0 < t < dur - 2)


def make(case, force=False):
    path = os.path.join(case, "plan.json")
    song = load_song(case)
    d = np.load(os.path.join(case, "audio", "bands.npz"))
    dur = float(d["duration"])
    lines = lyric_lines(song.get("lyrics"))
    spans = sung_spans(lines)
    secs, b = make_sections(d, dur, spans)
    title_end = song.get("title_end")
    if title_end is None:       # 乐队进来（6–14 秒里第一个段落边界）后约 3 秒淡完，对焦在那之后拉回脸上
        cand = [s[1] for s in secs if 6.0 <= s[1] <= 14.0]
        title_end = (cand[0] if cand else 8.0) + 2.85
    show = song.get("show")
    if show is None:
        last = spans[-1][1] if spans else dur - 12
        show = [snap(title_end + 3.0, b[b >= title_end + 3.0]) if (b >= title_end + 3.0).any() else title_end + 3.0,
                round(min(last + 1.5, dur - 6), 2)]
    credits_at = song.get("credits_at")
    if credits_at is None:      # 歌名淡出后的第一个段落边界（8 秒内），没有就下一个重拍
        nxt = [s[1] for s in secs if show[1] - 0.5 <= s[1] <= show[1] + 8.0]
        after = np.array(nxt) if nxt else b[b >= show[1] + 1.0]
        credits_at = [round(float(after[0]) if len(after) else show[1] + 1.5, 2), round(dur - 3.5, 2)]
    plan = dict(duration=round(dur, 3), bpm=round(60 / float(d["grid_beat"]), 2), title_end=round(float(title_end), 2),
                show=[round(float(x), 2) for x in show], credits_at=credits_at, sections=secs,
                camera=make_camera(secs, dur, float(title_end)), meteors=make_meteors(secs, dur, spans))
    if os.path.exists(path) and not force:
        print(f"{path} 已经有了（手改过的不覆盖），要重排加 --force；下面是这次排出来的，没写进去")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump(plan))
        print("->", path)
    print(f"{dur:.1f} 秒，{plan['bpm']} BPM；大标题到 {plan['title_end']} 秒，左下角歌名 {plan['show']}，"
          f"制作信息 {plan['credits_at']}，流星 {len(plan['meteors'])} 颗")
    for s in secs:
        print(f"  {s[0]:<10} {s[1]:7.2f}  能量 {s[2]:.2f}  花瓣 {s[3]:.2f}  光点 {s[4]:.2f}  旋律盘 {s[5]:.2f}  光束 {s[6]:.2f}")
    return plan


def dump(plan):
    """一行一个段落、一个关键帧，手改的时候好找。"""
    lines = ["{"]
    for k, v in plan.items():
        if k in ("sections", "camera"):
            body = ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in v)
            lines.append(f'  "{k}": [\n{body}\n  ],')
        else:
            lines.append(f'  "{k}": {json.dumps(v, ensure_ascii=False)},')
    lines[-1] = lines[-1].rstrip(",")
    return "\n".join(lines + ["}"]) + "\n"


def env(case):
    """给 shell 用的变量（eval）。还没有 plan.json 时时机那几个是空的。"""
    song = load_song(case)
    p = os.path.join(case, "plan.json")
    plan = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else dict(show=[], credits_at=[], sections=[])
    name = os.path.basename(os.path.normpath(case))
    vals = dict(NAME=name, TITLE=song["title"], SUB=song.get("sub", ""), MIX=song["mix"],
                VOCAL=song.get("vocal") or "-", LRC=song.get("lyrics") or "", TLRC=song.get("lyrics_cn") or "",
                CREDITS=song.get("credits") or "", LYRICS_OFFSET=str(song.get("lyrics_offset", 0.15)),
                SHOW=" ".join(str(x) for x in plan["show"]), CREDITS_AT=" ".join(str(x) for x in plan["credits_at"]),
                COVER_AT=str(next((s[1] + 4.0 for s in plan["sections"] if s[0].startswith("chorus")), 60.0)))
    print("\n".join(f"{k}={shlex.quote(str(v))}" for k, v in vals.items()))


if __name__ == "__main__":
    cmd, case = sys.argv[1], sys.argv[2]
    if cmd == "make":
        make(case, force="--force" in sys.argv)
    elif cmd == "env":
        env(case)
    else:
        sys.exit(f"不认识的命令 {cmd}：make 或 env")
