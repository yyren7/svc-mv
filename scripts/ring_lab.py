"""月亮外圈"节奏盘"的样式实验：在不带频谱环的渲染帧（pv.py 的 RING=none + clip）上，按每帧月亮在画面上的位置和
大小把几种样式画成 2D 的光，滤色叠上去，几秒的小样并排比较。选定的样式再做进 Blender 场景（花瓣从前面飘过、辉光都对）。
在 AutoDL 上：
    PY=/root/autodl-tmp/ComfyUI/venv/bin/python; export PYTHONPATH=/root/autodl-tmp/pv/pylib
    EQ=/root/autodl-tmp/conda_envs/evalq/bin/python         # librosa
    DD=/root/autodl-tmp/conda_envs/ddsp/bin/python          # RMVPE（DDSP-SVC 的环境）
    # melody 要人声的音高：pyin 只算一段（60 fps）；rmvpe 整首一次算完，带后处理和句首（100 fps，melody2 系列用）
    $EQ scripts/ring_lab.py f0 <lead.flac> <f0.npz> --t0 60 --t1 75
    $DD scripts/ring_lab.py f0 --method rmvpe --ddsp <DDSP-SVC 目录> --lrc <lyrics.lrc> <lead.flac> <melody.npz>
    # 165 BPM 的拍子网格和小节线；混音叠咔哒声，听着核对小节线、星名的时刻
    $EQ scripts/ring_lab.py beatgrid <mix.wav> <grid.npz>
    $EQ scripts/ring_lab.py click <mix.wav> <out.wav> --t0 165 --t1 200 --grid <grid.npz>
    $EQ scripts/ring_lab.py click <mix.wav> <out.wav> --t0 101 --t1 114 --at 103.09 103.65 104.55 --at-low 106.40 108.04
    # 夏季大三角的三颗星：在底图上核对位置（TRI_STARS 是在 101–114 s 的底图上用 --t0 103 --t1 114 定的）
    $PY scripts/ring_lab.py stars <帧目录> --moon <场景>_moon.npz [--t0 103 --t1 114]
    $PY scripts/ring_lab.py draw <帧目录> <输出目录> --style halo --bands <bands.npz> --moon <场景>_moon.npz [--f0 <f0.npz>]
    $PY scripts/ring_lab.py grid <输出目录> --moon <场景>_moon.npz --font <ttf> A=<帧目录> B=<帧目录> ...
拍子网格、句首、星名、大三角、结尾的时刻都在下面"拍子网格和时刻表"的常量里；section_col 用 ast 从 pv.py 读段落表的一列。
样式（长度都以月亮半径 R 为单位）：
    bars    细线 + 峰值点：64 根细线绕满一圈（低频在下、高频在上，左右对称），根部亮、往梢上淡；顶上的峰值点停一下再慢慢落
    halo    光环：频谱绕成一条连续的平滑闭合曲线，外面两圈是 0.12、0.25 秒前的"回声"，里面一层很淡的光晕
    ripple  涟漪：每一拍从月亮边上放出一圈细环往外扩散、变淡（重拍更亮），环的起伏是那一拍的频谱；里圈一条细环跟着心跳
    melody  旋律：一颗光点每两小节顺时针绕月亮一圈（每隔一个小节线回到正上方），离月亮的远近是人声的音高，
            画出来的旋律线像唱片的纹路，转一圈后淡掉；圈上 8 个刻度是这两小节的 8 拍，拍子到时亮一下
    halo+ripple  光环和涟漪叠在一起
    melody2 精修的旋律盘：整首的 RMVPE 音高（--f0 给 f0 --method rmvpe 的 npz），165 BPM 网格上每两小节一圈、正上方
            对着 TOP_BEATS 的小节线；刻度按网格的拍子亮，小节第一拍更亮；每句开头留一颗句星；「あれがデネブ、アルタイル、
            ベガ」唱到哪颗，画里那颗星就亮，「夏の大三角」时按唱名的顺序连成三角形，旋律盘让一点；最后的长音画成一个
            闭合的圆留到 END_HOLD，乐队最后一下之后光点减速，最后一个和弦停在正上方。亮度跟 pv.py 段落表的 ring 列
    $PY scripts/ring_lab.py draw <帧目录> <输出目录> --style melody2 --bands <bands.npz> --moon <场景>_moon.npz \
        --f0 <melody.npz> [--pv cases/kimishira/scripts/pv.py]
    orbit   环绕的星群：ORBIT_N 颗星各在一条略扁、略斜的轨道上绕月亮顺时针转，拖着长尾巴；转得慢（里圈四小节一圈），
            每颗星快慢略有不同、还各自慢慢起伏，响的时候一起转快一点。每颗星管一段频谱（里圈低频、外圈高频），那段越响越亮、尾巴越长，很响时带四芒光。
            星的多少跟整体响度走：每颗星有自己的门槛（还慢慢上下漂），响度过了门槛就淡入，回落就熄灭
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


# ---------------------------------------------------------------- 拍子网格和时刻表（君の知らない物語，单位秒）
# 这首歌是 165 BPM 的恒速点击轨。bands.npz 里 librosa 估的 110 BPM 是 3:2 的倍频错误，一半"拍子"落在反拍的八分音符上。
BEAT = 0.363636                 # 拍长 P
BEAT_PHI = 0.036                # 第 0 拍；第 k 拍在 BEAT_PHI + k·BEAT
# 小节第一拍：从这一秒起，拍号 ≡ 第二列 (mod 4) 的拍是小节第一拍。第三列 False 的两段（drop、ch2b）是按和弦变化填的，
# 人声起句给的答案不一样（那里可能有一个 2 拍的小节），待人耳确认
BAR_PHASE = ((0.0, 2, True), (167.3, 0, False), (181.7, 2, False), (197.5, 0, True))
# 旋律盘正上方对着的小节线（拍号），4 小节一圈和 2 小节一圈都用它：第 186 拍 67.672 s（102.582、108.400 s 也在正上方，
# 「あれが」「覚えて」都从正上方起笔）；197.5 s 起是第 864 拍 314.218 s。167.3–197.5 s 还没定，暂时沿用前一段
TOP_BEATS = ((0.0, 186), (197.5, 864))
VIS_LEAD = 1 / 30               # 所有视觉事件一律提前 1/30 秒，看起来才和声音同时
# 句首：人工核对过的值，替换同一句自动测出的起点（自动测的 104.89 是「ベガ」的「ガ」，107.84 是「大三角」的「か」）
LINE_CHECKED = (61.75, 68.70, 75.63, 102.53, 105.30, 108.36, 302.18, 308.00, 313.77)
# 「あれがデネブ、アルタイル、ベガ」「君は指さす夏の大三角」「覚えて空を見る」：主唱分轨上测的音节起点（翻唱的时间一致）
ARE_GA = 102.53                 # あれが：句首，比小节线 102.582 早 0.05 秒
STAR_NAMES = (("Deneb", 103.09), ("Altair", 103.65), ("Vega", 104.55))     # デネブ、アルタイル、ベガ，唱名的顺序
VEGA_GA, VEGA_END = 104.89, 105.06      # 「ベガ」的「ガ」；发声到这里
KIMI_WA = 105.30                # 君は：句首
TRIANGLE = (106.40, 108.04)     # 夏の大三角：「な」到「く」（清化）
OBOETE = 108.36                 # 覚えて：句首
MIRU = (112.0, 113.55)          # 見る
NO_LINE_STAR = (ARE_GA, KIMI_WA)        # 这两句不留句星，让给大三角
# 大三角用画里月亮右边本来就有的三颗星：off 以 R 为单位、相对月亮中心，x 向右、y 向下（见 tri_px）。第 4166 帧上量的是
# Vega (3.841, 0.107)、Deneb (5.073, -0.140)、Altair (4.480, 1.946)，到 101–114 s 镜头动了，天津四偏出 2 像素；
# 现在的值是 stars 子命令在 101–114 s 的底图上、103–114 s（三颗星亮着的时候）测的中位数
TRI_STARS = {"Vega": (3.845, 0.103), "Deneb": (5.088, -0.154), "Altair": (4.489, 1.947)}
TRI_EDGES = (("Deneb", "Altair", 106.40, 106.85), ("Altair", "Vega", 106.85, 107.30),
             ("Vega", "Deneb", 107.30, 107.75))         # 按唱名的顺序一条条连上：起点、终点、开始长、长满
TRI_FADE = (112.6, 113.6)       # 连线保持到 112.6 秒，「見る」时淡出
TRI_DIM = (112.6, 114.0)        # 三颗星的增亮在这段里从 1 降到 0.35
DIAL_YIELD = (106.40, 113.6)    # 旋律盘在这段里整体乘 0.8（两端 0.5 秒缓变），让给大三角
# 结尾
LAST_LINE = 313.77              # 「無邪気な声で」
FINAL_NOTE = (315.11, 318.11)   # 最后的 A4：真正唱出来的部分，后面的混响已被响度门去掉
END_HOLD = 326.0                # 闭合的圆亮度保持到这里
BAND_HIT = 328.06               # 乐队最后一下重击：之后光点减速
LAST_CHORD = 335.05             # 最后一个和弦：光点停在正上方
SONG_END = 337.5                # 成片在最后 4 秒淡出


def beat_time(k):
    """第 k 拍（165 BPM 网格）的时刻。"""
    return BEAT_PHI + BEAT * np.asarray(k, np.float64)


def bar_phase(t):
    """t 时刻小节第一拍的拍号余数（mod 4），以及这一段是否已确认；t 可以是数组。"""
    i = np.clip(np.searchsorted([x[0] for x in BAR_PHASE], t, side="right") - 1, 0, len(BAR_PHASE) - 1)
    return np.array([x[1] for x in BAR_PHASE])[i], np.array([x[2] for x in BAR_PHASE])[i]


def t_top(t):
    """t 时刻旋律盘正上方对着的小节线：θ(t) = π − 2π·(t − t_top(t))/T，一圈 T = 4 小节（16 拍）或 2 小节（8 拍）。"""
    i = np.clip(np.searchsorted([x[0] for x in TOP_BEATS], t, side="right") - 1, 0, len(TOP_BEATS) - 1)
    return beat_time(np.array([x[1] for x in TOP_BEATS])[i])


# ---------------------------------------------------------------- 音频

def smooth(x, k):
    k = max(int(k) | 1, 1)
    return np.convolve(np.pad(x, (k // 2, k // 2), mode="edge"), np.ones(k) / k, "valid")


class Song:
    def __init__(self, bands, f0=None):
        d = np.load(bands)
        self.spec = d["spec"].astype(np.float32)
        self.bass = d["bass"].astype(np.float32)
        self.loud = d["loud"].astype(np.float32)
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
    if a.method == "rmvpe":
        f0_rmvpe(a)
        return
    if a.t0 is None or a.t1 is None:
        raise SystemExit("pyin 只算一段：要给 --t0 和 --t1")
    import librosa
    sr = 24000
    hop = sr // FPS
    y, _ = librosa.load(a.lead, sr=sr, offset=a.t0, duration=a.t1 - a.t0)
    f0, voiced, prob = librosa.pyin(y, fmin=110, fmax=1100, sr=sr, frame_length=2048, hop_length=hop)
    np.savez(a.out, t0=a.t0, f0=np.nan_to_num(f0).astype(np.float32), prob=np.nan_to_num(prob).astype(np.float32))
    print(a.out, len(f0), "frames,", f"{np.mean(prob > 0.3) * 100:.0f}% voiced", flush=True)


def runs(mask):
    """布尔数组里连续为 True 的段：[(起, 止), ...]，左闭右开。"""
    d = np.diff(np.concatenate([[0], np.asarray(mask, np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def gauss1d(x, sigma):
    """高斯平滑（sigma 以样本为单位），两端按边上的值延伸；和 scipy 的 gaussian_filter1d(mode="nearest") 一样。"""
    k = int(4 * sigma + 0.5)
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / sigma) ** 2)
    return np.convolve(np.pad(np.asarray(x, np.float64), k, mode="edge"), w / w.sum(), "valid")


def lrc_lines(path):
    """LRC 里唱的句子：[(秒, 歌词)]，跳过空行（间奏）和作词、作曲。"""
    out = []
    for s in open(path, encoding="utf-8"):
        mt = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", s.strip())
        if mt and mt.group(3).strip() and not mt.group(3).strip().startswith("作"):
            out.append((int(mt.group(1)) * 60 + float(mt.group(2)), mt.group(3).strip()))
    return out


def line_starts(conf, lines, fps=100):
    """句首：LRC 时刻减 0.15 秒之后（1.2 秒以内）第一个 conf > 0.5、至少持续 50 ms 的发声段的起点（LRC 比真实起音
    平均早 0.43 秒，不能直接用）。人工核对过的 LINE_CHECKED 替换同一句（LRC 时刻在它前面的最后一句）的自动值。
    返回 (句首, 每句的自动值)；找不到起点的句子，自动值是 NaN。"""
    if not lines:
        return np.zeros(0), np.zeros(0)
    on = np.array([s / fps for s, e in runs(conf > 0.5) if e - s >= round(0.05 * fps)])
    lt = np.array([t for t, _ in lines])
    auto = np.full(len(lines), np.nan)
    for i, t in enumerate(lt):
        c = on[(on > t - 0.15) & (on < t + 1.2)]
        if len(c):
            auto[i] = c[0]
    final = auto.copy()
    for h in LINE_CHECKED:
        final[np.searchsorted(lt, h + 0.1, side="right") - 1] = h
    return np.unique(final[np.isfinite(final)]), auto


def rmvpe_f0(y, ddsp):
    """RMVPE（DDSP-SVC 里的那份，翻唱本身就用它提音高）：y 是 16 kHz 单声道，返回 100 fps 的 (f0 Hz, 置信度 conf)。
    直接调 mel_extractor 和 model 拿 hidden (n, 360)：F0_Extractor.extract() 会丢掉置信度，还会把不发声的帧插值填满。
    conf 是 hidden 每帧的最大值；f0 取 argmax 前后各 4 个 bin 的加权平均（一个 bin 20 音分）。"""
    import sys
    import torch
    import torch.nn.functional as F
    sys.path.insert(0, ddsp)
    from encoder.rmvpe import RMVPE
    from encoder.rmvpe.constants import CONST, N_CLASS
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = RMVPE(os.path.join(ddsp, "pretrain", "rmvpe", "model.pt"), hop_length=160)
    audio = torch.from_numpy(y).float().unsqueeze(0).to(dev)
    n = audio.shape[1] // 160 + 1
    t1 = audio.shape[1] + 160
    audio = F.pad(audio, (0, m.seg_length * ((t1 - 1) // m.seg_length + 1) - t1))
    mel = m.mel_extractor.to(dev)(audio, center=True)
    model = m.model.to(dev)
    L, ch, ov = mel.shape[-1], 3200, 96         # 分块推理：一块 32 秒，两边各多带 0.96 秒
    hid = []
    with torch.no_grad():
        for s in range(0, L, ch):
            a, b = max(0, s - ov), min(L, s + ch + ov)
            x = mel[..., a:b]
            h = model(F.pad(x, (0, 32 * ((x.shape[-1] - 1) // 32 + 1) - x.shape[-1])))[:, :x.shape[-1]]
            hid.append(h[:, s - a:s - a + min(ch, L - s)])
    H = torch.cat(hid, 1)[0, :n].float().cpu().numpy()
    j = H.argmax(1)[:, None] + np.arange(-4, 5)
    ok = (j >= 0) & (j < N_CLASS)
    w = np.where(ok, np.take_along_axis(H, np.clip(j, 0, N_CLASS - 1), 1), 0.0)
    cents = (w * (j * 20 + CONST)).sum(1) / np.maximum(w.sum(1), 1e-9)
    return (10 * 2 ** (cents / 1200)).astype(np.float32), H.max(1).astype(np.float32)


def melody_post(f0, conf, db, starts, fps=100):
    """RMVPE 的逐帧音高 -> 画旋律线用的 MIDI，按下面的顺序：
    a 滞回判定发声：conf > 0.5 开、< 0.25 关
    b 去掉短于 40 ms 的段
    c 响度门：主唱 RMS（db，dBFS）低于 −40 的帧一律不发声，去掉混响尾巴
    d 八度修正：和 0.5 秒的滑动中位数（只算发声帧）差 9 个半音以上，就加减 12
    e 段内 5 帧中值
    f 去毛刺：短于 0.08 秒、中位数和前一段末尾、后一段开头都差 1.5 个半音以上的段，置为不发声
    g 补缝：短于 0.20 秒、缝内和缝后 0.05 秒内都没有句首的缝，在 MIDI 上用 smoothstep 从前一段末尾补到后一段开头，
      标成 bridge（辅音处的缝在 0.15 秒以内，换气在 0.3 秒以上，0.2 秒正好在全曲缝长的低谷里）
    h voiced 或 bridge 连起来的每一段里做 σ = 30 ms 的高斯平滑，两端按边上的值延伸（换音处成了 30–50 ms 的短滑音）
    i 响度 g：db 在发声帧上按 p5..p95 归一到 0..1，再做 σ = 30 ms 的平滑
    返回 (dict(midi 既不发声也不是 bridge 的帧为 NaN, voiced, bridge, g), 各步的统计)。"""
    n = len(f0)
    m = 69 + 12 * np.log2(np.maximum(np.asarray(f0, np.float64), 1.0) / 440.0)
    starts = np.asarray(starts, np.float64)
    st = {}
    v = np.zeros(n, bool)                                       # a
    on = False
    for i in range(n):
        on = conf[i] > (0.25 if on else 0.5)
        v[i] = on
    st["a"] = v.copy()
    for s, e in runs(v):                                        # b
        if e - s < round(0.04 * fps):
            v[s:e] = False
    st["b"] = v.copy()
    v &= db >= -40.0                                            # c
    st["c"] = v.copy()
    k = round(0.25 * fps)                                       # d
    idx = np.flatnonzero(v)
    mv = np.pad(np.where(v, m, np.nan), k, constant_values=np.nan)
    d = m[idx] - np.nanmedian(np.lib.stride_tricks.sliding_window_view(mv, 2 * k + 1)[idx], axis=1)
    fix = np.abs(d) > 9
    m[idx[fix]] -= 12 * np.round(d[fix] / 12)
    st["octave"] = int(fix.sum())
    for s, e in runs(v):                                        # e
        m[s:e] = np.median(np.lib.stride_tricks.sliding_window_view(np.pad(m[s:e], 2, mode="edge"), 5), axis=1)
    rr = runs(v)                                                # f
    drop = []
    for j, (s, e) in enumerate(rr):
        if e - s >= round(0.08 * fps):
            continue
        md = np.median(m[s:e])
        if (j == 0 or abs(md - m[rr[j - 1][1] - 1]) > 1.5) and (j == len(rr) - 1 or abs(md - m[rr[j + 1][0]]) > 1.5):
            drop.append((s, e))
    for s, e in drop:
        v[s:e] = False
    st["spikes"] = len(drop)
    bridge = np.zeros(n, bool)                                  # g
    rr = runs(v)
    st["bridged"] = st["kept_at_line"] = 0
    for (_, s), (e, _) in zip(rr[:-1], rr[1:]):
        if (e - s) / fps >= 0.20:
            continue
        if np.any((starts >= s / fps) & (starts <= e / fps + 0.05)):
            st["kept_at_line"] += 1
            continue
        x = (np.arange(s, e) - s + 1) / (e - s + 1)
        m[s:e] = m[s - 1] + (m[e] - m[s - 1]) * x * x * (3 - 2 * x)
        bridge[s:e] = True
        st["bridged"] += 1
    vb = v | bridge                                             # h
    for s, e in runs(vb):
        m[s:e] = gauss1d(m[s:e], 0.03 * fps)
    lo, hi = np.percentile(db[v], [5, 95])                      # i
    g = gauss1d(np.clip((db - lo) / max(hi - lo, 1e-6), 0, 1), 0.03 * fps)
    st["db_p5_p95"] = (float(lo), float(hi))
    return dict(midi=np.where(vb, m, np.nan).astype(np.float32), voiced=v, bridge=bridge, g=g.astype(np.float32)), st


def f0_rmvpe(a):
    """整首的主唱音高 -> melody npz（j）：fps = 100、t0 = 0、midi、voiced、bridge、conf、g、line_starts；另存
    line_auto（每句自动测的句首）、line_lrc（LRC 时刻）、f0（RMVPE 原始的 Hz）、db（主唱 RMS，dBFS）。"""
    import librosa
    fps = 100
    y, _ = librosa.load(a.lead, sr=16000, mono=True)
    f0, conf = rmvpe_f0(y, os.path.abspath(a.ddsp))
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=160, center=True)[0][:len(f0)]
    db = 20 * np.log10(np.maximum(rms, 1e-10))
    lines = lrc_lines(a.lrc) if a.lrc else []
    starts, auto = line_starts(conf, lines, fps)
    mel, st = melody_post(f0, conf, db, starts, fps)
    np.savez(a.out, fps=float(fps), t0=0.0, conf=conf, line_starts=starts, line_auto=auto,
             line_lrc=np.array([t for t, _ in lines]), f0=f0, db=db.astype(np.float32), **mel)
    v, vb = mel["voiced"], mel["voiced"] | mel["bridge"]

    def pieces(mask, t0, t1, cut=()):
        """t0..t1 里连起来的段数；cut 里的时刻（句首）落在段中间的，算断开。"""
        x = mask[int(round(t0 * fps)):int(round(t1 * fps))]
        i = [int(round((c - t0) * fps)) for c in cut if t0 < c < t1]
        return len(runs(x)) + sum(1 for j in i if 0 < j < len(x) and x[j] and x[j - 1])

    mm = mel["midi"][v]
    print(a.out, f"{len(f0)} 帧（{len(f0) / fps:.1f} s），{len(starts)} 个句首", flush=True)
    print(f"  全曲：滞回后 {len(runs(st['a']))} 截 -> 最后 {len(runs(vb))} 截；响度门去掉 {int((st['b'] & ~st['c']).sum())} 帧，"
          f"八度修正 {st['octave']} 帧，去毛刺 {st['spikes']} 段，补缝 {st['bridged']} 处（句首处不补 {st['kept_at_line']} 处）")
    for t0, t1 in ((60, 75), (101, 108)):
        print(f"  {t0}–{t1} s：滞回后 {pieces(st['a'], t0, t1)} 截，最后 {pieces(vb, t0, t1)} 截"
              f"（在句首再断开：{pieces(vb, t0, t1, starts)} 截）")
    print(f"  midi（发声帧）p5/p95 {np.percentile(mm, 5):.1f}/{np.percentile(mm, 95):.1f}，"
          f"最低 {mm.min():.1f}，最高 {mm.max():.1f}；主唱响度 p5/p95 {st['db_p5_p95'][0]:.1f}/{st['db_p5_p95'][1]:.1f} dBFS")
    s = slice(int(318.6 * fps), int(320.2 * fps))
    print(f"  318.6–320.2 s：发声 {int(vb[s].sum())} 帧（门前 {int(st['b'][s].sum())} 帧）")
    s = slice(int(227 * fps), int(250 * fps))
    print(f"  227–250 s 的轻声：门前发声 {int(st['b'][s].sum())} 帧，门后 {int(st['c'][s].sum())} 帧")


class Melody:
    """人声音高 -> 旋律盘上的半径（按这一段的音域）；角度跟时间走，每两小节一圈。"""

    def __init__(self, f0npz, song):
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
        self.lo, self.hi = np.percentile(mm[np.isfinite(mm)], [5, 95])
        db = song.downbeats
        self.bar = float(np.median(np.diff(db)))
        self.ref = float(db[0])
        self.rev = 2 * self.bar              # 一圈两小节

    def at(self, f):
        i = int(round(f - self.t0 * FPS))
        if i < 0 or i >= len(self.m) or not np.isfinite(self.m[i]):
            return None
        return self.m[i]

    def theta(self, t):
        """顺时针（画面上从正上方往右转），每隔一个小节线在正上方。"""
        return np.pi - 2 * np.pi * (t - self.ref) / self.rev

    def radius(self, m):
        return 1.20 + 0.42 * np.clip((m - self.lo) / max(self.hi - self.lo, 1), -0.1, 1.1)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ramp(t, t0, t1):
    """t0 以前 0，t1 以后 1，中间 smoothstep。"""
    return float(smoothstep((t - t0) / max(t1 - t0, 1e-6)))


class Melody2:
    """melody2 的数据：f0 rmvpe 的 npz（100 fps，midi 里不发声的帧是 NaN），角度按 165 BPM 网格，每两小节一圈。"""

    def __init__(self, npz, pv, n):
        d = np.load(npz)
        self.fps = float(d["fps"])
        self.midi = d["midi"]
        self.g = d["g"]
        self.bridge = d["bridge"]
        ok = np.isfinite(self.midi) & d["voiced"]
        self.lo, self.hi = np.percentile(self.midi[ok], [5, 95])
        self.T = 8 * BEAT                                   # 一圈两小节
        self.lines = [s for s in d["line_starts"] if min(abs(s - x) for x in NO_LINE_STAR) > 0.05]
        a, b = self.i(FINAL_NOTE[0]), self.i(FINAL_NOTE[1])
        self.r_final = float(self.radius(np.nanmedian(self.midi[a:b])))
        self.ring = section_col(pv, n)
        # 尾声：乐队最后一下（BAND_HIT）起，转速按 (1 − x)^p 降到 0，到最后一个和弦（LAST_CHORD）正好停在正上方。
        # 剩下的圈数取最接近匀减速（p = 1）的那个：剩到下一个正上方的零头 + 整数圈
        self.D = LAST_CHORD - BAND_HIT
        self.u_hit = self.turns(BAND_HIT)
        frac = math.ceil(self.u_hit) - self.u_hit
        left = min((frac + k for k in range(4)), key=lambda x: abs(x - self.D / (2 * self.T)))
        self.p1 = self.D / (self.T * left)                  # p + 1

    def i(self, t):
        return int(round(t * self.fps))

    def turns(self, t):
        """从正上方起转过的圈数（不含尾声的减速）。"""
        return (np.asarray(t, np.float64) - t_top(t)) / self.T

    def theta(self, t):
        """顺时针，θ = π 是正上方。BAND_HIT 以后按减速走。"""
        t = np.asarray(t, np.float64)
        x = np.clip((t - BAND_HIT) / self.D, 0, 1)
        late = self.u_hit + self.D / self.T * (1 - (1 - x) ** self.p1) / self.p1
        return np.pi - 2 * np.pi * np.where(t > BAND_HIT, late, self.turns(t))

    def radius(self, m):
        return 1.20 + 0.50 * np.clip((m - self.lo) / max(self.hi - self.lo, 1), -0.1, 1.1)

    def at(self, t):
        """t 秒的 midi，不发声是 NaN。"""
        j = self.i(t)
        return self.midi[j] if 0 <= j < len(self.midi) else np.nan


ORBIT_N = 90


class Orbits:
    """orbit 样式的数据：每颗星的轨道、转速、频段、出现的门槛（固定的随机数），逐帧的星群密度和累计转角。
    全部只由帧号算出来，任意一段帧都能单独画。"""

    def __init__(self, song, seed=7):
        rng = np.random.default_rng(seed)
        n = ORBIT_N
        u = rng.random(n)
        self.a = 1.45 + 2.6 * u ** 0.9                      # 半长轴（R）：1.45–4.05，星之间留得开
        self.b = self.a * rng.uniform(0.82, 1.0, n)         # 半短轴：略扁，像斜着看的圆轨道
        self.tilt = rng.uniform(0, np.pi, n)
        self.phase = rng.uniform(0, 2 * np.pi, n)
        # 里圈四小节一圈，往外只慢一点；每颗星快慢差几个百分点，转速还各自慢慢起伏（转角上 ±0.12 弧度）
        self.omega = 2 * np.pi / (16 * BEAT) * (1.3 / self.a) ** 0.5 * rng.uniform(0.93, 1.07, n)
        self.sway_p = rng.uniform(5, 11, n)
        self.sway_ph = rng.uniform(0, 2 * np.pi, n)
        nb = song.spec.shape[1]
        self.band = np.clip(np.round(u ** 0.9 * (nb - 1) + rng.normal(0, 3, n)), 1, nb - 2).astype(int)
        self.h = rng.random(n)                              # 出现的门槛
        self.wob_p = rng.uniform(6, 14, n)                  # 门槛上下漂的周期（秒）：响度不变时也有星生灭
        self.wob_ph = rng.uniform(0, 2 * np.pi, n)
        self.warm = rng.random(n) < 0.25
        lvl = smooth(song.spec.mean(1), 0.5 * FPS)
        lo, hi = np.percentile(lvl, [10, 95])
        self.level = np.clip(0.12 + 0.88 * (lvl - lo) / (hi - lo), 0.05, 1.0)
        speed = 0.7 + 0.6 * smooth(song.loud, 1.0 * FPS)   # 响的时候一起转快一点
        self.A = np.concatenate([[0.0], np.cumsum(speed)[:-1]]) / FPS

    def xy(self, i, g):
        """第 i 颗星在第 g 帧（可以是数组）的位置，R 单位，x 朝右、y 朝下；θ 减小是顺时针。"""
        th = (self.phase[i] - self.omega[i] * self.A[g]
              + 0.12 * np.sin(2 * np.pi * np.asarray(g) / FPS / self.sway_p[i] + self.sway_ph[i]))
        X, Y = self.a[i] * np.sin(th), self.b[i] * np.cos(th)
        c, s = math.cos(self.tilt[i]), math.sin(self.tilt[i])
        return X * c - Y * s, X * s + Y * c


# ---------------------------------------------------------------- 画

class Canvas:
    """以月亮为中心的方形画布，长度单位是 R；每组元素一张 8 位遮罩（cv2 的抗锯齿只对 8 位图有效），最后着色相加。
    off 是月亮中心相对画布正中的亚像素偏移（输出像素），画布贴回画面时按整像素对齐，这样星位才准。"""

    def __init__(self, R, half=HALF, off=(0.0, 0.0)):
        import cv2
        self.cv2 = cv2
        self.R = R
        self.n = int(math.ceil(2 * half * R))
        self.S = self.n * SS
        self.c = np.array([(self.n / 2 + off[0]) * SS - 0.5, (self.n / 2 + off[1]) * SS - 0.5])
        self.layers = []

    def layer(self, color, gain):
        m = np.zeros((self.S, self.S), np.uint8)
        self.layers.append((m, color, gain))
        return m

    def px(self, x, y):
        """R 单位的点（x 朝右、y 朝下，月亮中心为原点）-> cv2 的定点坐标（shift=4）。"""
        return np.round(np.stack([self.c[0] + np.asarray(x) * self.R * SS, self.c[1] + np.asarray(y) * self.R * SS], -1)
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

    def dot_xy(self, m, x, y, rad, value):
        p = self.px(x, y).tolist()
        self.cv2.circle(m, tuple(p), int(round(rad * self.R * SS * 16)), int(value * 255), -1, self.cv2.LINE_AA, 4)

    def line_xy(self, m, p0, p1, value, w):
        a, b = self.px(*np.array([p0, p1], np.float64).T).tolist()
        self.cv2.line(m, tuple(a), tuple(b), int(value * 255), self.width(w), self.cv2.LINE_AA, 4)

    def sparkle(self, m, x, y, rad, arm, value, w=0.006):
        """一颗四芒星：圆点加横竖两道细光芒。"""
        self.dot_xy(m, x, y, rad, value)
        for dx, dy in ((arm, 0), (0, arm)):
            self.line_xy(m, (x - dx, y - dy), (x + dx, y + dy), value * 0.8, w)

    def light(self, glow=(0.8, 0.5)):
        """着色相加，加两层辉光，缩回 1 倍；月亮圆盘里压暗（月亮本身的亮度由贴图决定）。返回 float32 RGB。"""
        cv2 = self.cv2
        rgb = np.zeros((self.S, self.S, 3), np.float32)
        for m, color, gain in self.layers:
            rgb += (m.astype(np.float32) / 255.0)[..., None] * (np.array(color, np.float32) * gain)
        s1, s2 = 0.04 * self.R * SS, 0.16 * self.R * SS
        rgb = rgb + glow[0] * cv2.GaussianBlur(rgb, (0, 0), s1) + glow[1] * cv2.GaussianBlur(rgb, (0, 0), s2)
        yy, xx = np.mgrid[0:self.S, 0:self.S]
        d = np.hypot(xx - self.c[0], yy - self.c[1]) / (self.R * SS)
        rgb *= np.clip((d - 0.95) / 0.12, 0.2, 1.0)[..., None]
        return cv2.resize(rgb, (self.n, self.n), interpolation=cv2.INTER_AREA)


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
    t = f / FPS
    guide = cv.layer(MOON, 0.16)
    cv.curve(guide, np.linspace(0, 2 * np.pi, 241), np.full(241, 1.12), 1.0, 0.008)
    # 刻度：一圈 8 拍，拍子到时亮一下（0.35 秒衰减，重拍更亮）
    ticks = cv.layer(MOON, 0.9)
    beat = mel.bar / 4
    for k in range(8):
        th = mel.theta(mel.ref + k * beat)
        val = 0.22
        for tb in song.beats[(song.beats > t - 1.0) & (song.beats <= t)]:
            if abs(((tb - mel.ref) / beat - k + 4) % 8 - 4) < 0.3:
                down = np.min(np.abs(song.downbeats - tb)) < 0.05
                val += (0.8 if down else 0.5) * math.exp(-(t - tb) / 0.35)
        cv.line(ticks, th, 1.07, 1.15 if k % 4 else 1.18, min(val, 1.0), 0.012)
    # 旋律线：最近 0.9 圈，不唱的地方断开，越旧越暗越细
    trail = cv.layer(MOON, 1.0)
    span = int(0.9 * mel.rev * FPS)
    seg = []

    def flush():
        if len(seg) >= 2:
            for i in range(len(seg) - 1):               # 一段段画，亮度和粗细随时间变
                (t0, r0), (t1, r1) = seg[i], seg[i + 1]
                age = (f - t1 * FPS) / span
                v = float(song.voice[min(int(t1 * FPS), song.n - 1)])
                cv.curve(trail, mel.theta(np.array([t0, t1])), np.array([r0, r1]),
                         0.95 * (1 - age) ** 1.2 * (0.55 + 0.45 * v), 0.005 + 0.016 * (1 - age), closed=False)
        seg.clear()
    for g in range(f - span, f + 1):
        m = mel.at(g)
        if m is None:
            flush()
            continue
        seg.append((g / FPS, mel.radius(m)))
    flush()
    m = mel.at(f)
    if m is not None:
        head = cv.layer(WARM, 1.0)
        cv.dot(head, mel.theta(t), mel.radius(m), 0.032 * (0.75 + 0.5 * float(song.voice[f])), 1.0)


def draw_melody2(cv, song, f, mel):
    t = f / FPS + VIS_LEAD
    yd = ramp(t, DIAL_YIELD[0] - 0.25, DIAL_YIELD[0] + 0.25) * (1 - ramp(t, DIAL_YIELD[1] - 0.25, DIAL_YIELD[1] + 0.25))
    gain = (0.6 + 0.4 * float(mel.ring[min(f, len(mel.ring) - 1)])) * (1 - 0.2 * yd)
    guide = cv.layer(MOON, 0.16 * gain)
    cv.curve(guide, np.linspace(0, 2 * np.pi, 241), np.full(241, 1.12), 1.0, 0.008)
    # 刻度：一圈 8 拍，网格上的拍子到时亮一下（0.35 秒衰减，小节第一拍更亮）；尾声减速以后淡掉
    tg = 1 - ramp(t, BAND_HIT, BAND_HIT + 1.5)
    if tg > 0:
        ticks = cv.layer(MOON, 0.9 * gain * tg)
        val = np.full(8, 0.22)
        for k in range(int(math.floor((t - 1.0 - BEAT_PHI) / BEAT)), int(math.floor((t - BEAT_PHI) / BEAT)) + 1):
            tb = float(beat_time(k))
            if tb > t or k < 0:
                continue
            j = int(round(float(mel.turns(tb)) * 8)) % 8
            down = k % 4 == int(bar_phase(tb)[0])
            val[j] += (0.8 if down else 0.5) * math.exp(-(t - tb) / 0.35)
        for j in range(8):
            cv.line(ticks, np.pi - 2 * np.pi * j / 8, 1.07, 1.19 if j == 0 else 1.17 if j % 4 == 0 else 1.15,
                    min(val[j], 1.0), 0.012)
    # 旋律线：最近 0.9 圈，不唱的地方断开，越旧越暗越细；补缝处暗一点。最后的长音不随时间变旧，闭成一个圆留到 END_HOLD
    trail = cv.layer(MOON, gain)
    j1 = mel.i(t)
    j0 = mel.i(t - 0.9 * mel.T)
    fa, fb = mel.i(FINAL_NOTE[0]), mel.i(FINAL_NOTE[1])
    hold = 1 - ramp(t, END_HOLD, BAND_HIT)
    js = set(range(max(j0, 0), j1))
    if hold > 0 and j1 > fa:
        js |= set(range(fa, min(fb, j1)))
    for j in sorted(js):
        if j + 1 >= len(mel.midi) or not (np.isfinite(mel.midi[j]) and np.isfinite(mel.midi[j + 1])):
            continue
        tj = (j + 1) / mel.fps
        g = float(mel.g[j])
        if fa <= j < fb:
            age, g, k = 0.0, max(g, 0.7), hold
        else:
            age, k = (t - tj) / (0.9 * mel.T), 1.0
            if age >= 1:
                continue
        k *= 0.7 if mel.bridge[j] else 1.0
        cv.curve(trail, mel.theta(np.array([j / mel.fps, tj])), mel.radius(mel.midi[j:j + 2]),
                 0.95 * (1 - age) ** 1.2 * (0.5 + 0.5 * g) * k, 0.005 + 0.016 * (1 - age), closed=False)
    # 句星：每句开头留一颗，闪一下，两圈里淡掉
    stars = cv.layer(WARM, gain)
    for s in mel.lines:
        if not s <= t < s + 2 * mel.T:
            continue
        seg = mel.midi[mel.i(s):mel.i(s + 0.3)]
        seg = seg[np.isfinite(seg)]
        r = float(mel.radius(seg[0])) if len(seg) else 1.12
        flash = math.exp(-(t - s) / 0.4)
        th = float(mel.theta(s))
        cv.sparkle(stars, math.sin(th) * r, math.cos(th) * r, 0.02, 0.06 + 0.12 * flash,
                   min(1.0, 0.45 + 0.55 * flash) * (1 - (t - s) / (2 * mel.T)) ** 1.5)
    # 光点：唱的时候在音高上；不唱时是导引圈上一颗暗的；最后的长音以后留在那个圆上，最后一个和弦停在正上方闪一下
    head = cv.layer(WARM, gain)
    m = mel.at(t)
    th = float(mel.theta(t))
    if np.isfinite(m):
        g = float(mel.g[min(mel.i(t), len(mel.g) - 1)])
        cv.dot(head, th, float(mel.radius(m)), 0.032 * (0.75 + 0.5 * g), 1.0)
    elif t > FINAL_NOTE[1]:
        # 拖着 0.6 秒的尾巴：减速时尾巴跟着缩短，停下就收成一个点
        tt = t - 0.6 * np.linspace(1, 0, 31)
        for a in range(30):
            x = (a + 1) / 30
            cv.curve(trail, mel.theta(tt[a:a + 2]), np.full(2, mel.r_final), 0.8 * x ** 1.5, 0.006 + 0.012 * x,
                     closed=False)
        cv.dot(head, th, mel.r_final, 0.045, 0.95)
        if t >= LAST_CHORD:
            flash = math.exp(-(t - LAST_CHORD) / 0.8)
            cv.sparkle(head, math.sin(th) * mel.r_final, math.cos(th) * mel.r_final, 0.03, 0.12 + 0.35 * flash,
                       0.6 + 0.4 * flash, 0.008)
    else:
        cv.dot(head, th, 1.12, 0.018, 0.3)
    # 夏季大三角：唱到哪颗星，画里那颗就亮；「夏の大三角」时按唱名的顺序连线，「見る」时淡出；之后三颗星暗回去
    if ARE_GA - 1 < t < TRI_DIM[1] + 5:
        tri = cv.layer(MOON, 1.0)
        dim = (1 - 0.65 * ramp(t, *TRI_DIM)) * (1 - ramp(t, TRI_DIM[1] + 2, TRI_DIM[1] + 5))
        for name, tk in STAR_NAMES:
            on = ramp(t, tk - 0.02, tk + 0.10)
            if on <= 0:
                continue
            flash = math.exp(-(t - tk) / 0.5) if t >= tk else 0.0
            if name == "Vega" and t >= VEGA_GA:
                flash += 0.5 * math.exp(-(t - VEGA_GA) / 0.4)
            x, y = TRI_STARS[name]
            cv.sparkle(tri, x, y, 0.035, (0.14 + 0.30 * min(flash, 1.0)) * on,
                       min(1.0, on * dim * (0.7 + 0.3 * min(flash, 1.0))))
        fade = 1 - ramp(t, *TRI_FADE)
        for a, b, e0, e1 in TRI_EDGES:
            p = ramp(t, e0, e1)
            if p <= 0 or fade <= 0:
                continue
            A, B = np.array(TRI_STARS[a]), np.array(TRI_STARS[b])
            L = float(np.linalg.norm(B - A))
            u = (B - A) / L
            gap = 0.15
            p0 = A + u * gap
            p1 = p0 + u * (L - 2 * gap) * p
            cv.line_xy(tri, p0, p1, 0.6 * fade, 0.007)
            if p < 1:
                cv.dot_xy(tri, p1[0], p1[1], 0.02, 0.9 * fade)


def draw_orbit(cv, song, f, ob):
    t = f / FPS
    f = min(f, song.n - 1)
    hh = ob.h + 0.12 * np.sin(2 * np.pi * t / ob.wob_p + ob.wob_ph)
    alive = smoothstep((ob.level[f] - hh) / 0.08)
    layers = {False: cv.layer(MOON, 1.0), True: cv.layer(WARM, 1.0)}
    for i in np.flatnonzero(alive > 0.01):
        e = float(song.spec[f, ob.band[i] - 1:ob.band[i] + 2].mean())
        v = float(alive[i]) * (0.3 + 0.7 * e ** 1.2)
        m = layers[bool(ob.warm[i])]
        # 尾巴：1.0–2.4 秒走过的弧，越往后越暗越细
        g = np.arange(max(f - int((1.0 + 1.4 * e) * FPS), 0), f + 1, 2)
        if g[-1] != f:
            g = np.append(g, f)
        p = cv.px(*ob.xy(i, g)).tolist()
        for s in range(len(p) - 1):
            x = (s + 1) / (len(p) - 1)
            cv.cv2.line(m, tuple(p[s]), tuple(p[s + 1]), int(255 * v * x ** 1.6), cv.width(0.004 + 0.012 * x),
                        cv.cv2.LINE_AA, 4)
        x, y = ob.xy(i, f)
        cv.dot_xy(m, x, y, 0.014 + 0.016 * e, v)
        if e > 0.75:
            cv.sparkle(m, x, y, 0.0, (0.05 + 0.4 * (e - 0.75)) * float(alive[i]), v * 0.8)


# ---------------------------------------------------------------- 合成

G = {}


def setup(a):
    G["a"] = a
    G["song"] = Song(a.bands, a.f0)
    G["moon"] = np.load(a.moon)
    if a.style == "melody":
        G["mel"] = Melody(G["song"].f0, G["song"])
    if a.style == "melody2":
        G["mel"] = Melody2(a.f0, a.pv, G["song"].n)
    if a.style == "orbit":
        G["orb"] = Orbits(G["song"])
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
    # melody2 要画到大三角（天津四在 5.1 R），orbit 的外圈到 4.05 R
    half = {"melody2": 5.6, "orbit": 4.6}.get(a.style, HALF)
    n = int(math.ceil(2 * half * R))
    x0, y0 = int(round(cx - n / 2)), int(round(cy - n / 2))
    cv = Canvas(R, half, (cx - x0 - n / 2, cy - y0 - n / 2))
    for st in a.style.split("+"):
        if st == "bars":
            draw_bars(cv, song, f, G["pk"])
        elif st == "halo":
            draw_halo(cv, song, f, 0.8 if "+" in a.style else 1.0)
        elif st == "ripple":
            draw_ripple(cv, song, f)
        elif st == "melody":
            draw_melody(cv, song, f, G["mel"])
        elif st == "melody2":
            draw_melody2(cv, song, f, G["mel"])
        elif st == "orbit":
            draw_orbit(cv, song, f, G["orb"])
    light = cv.light()
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


# ---------------------------------------------------------------- 数据：拍子网格、听音核对、星位、段落

def grid_score(x, fps, P, ph, lo=0.0, hi=None):
    """网格 ph + k·P 落在 lo..hi 里的拍上，onset 包络 x（fps 帧每秒）的平均值；ph 可以是一组相位，返回同样长的数组。"""
    hi = len(x) / fps if hi is None else hi
    ph = np.atleast_1d(np.asarray(ph, np.float64))
    k = np.arange(np.floor((lo - ph.max()) / P), np.ceil((hi - ph.min()) / P) + 1)
    g = ph[:, None] + P * k[None, :]
    ok = (g >= lo) & (g <= hi)
    return (np.interp(g * fps, np.arange(len(x)), x) * ok).sum(1) / np.maximum(ok.sum(1), 1)


def beatgrid_cmd(a):
    """165 BPM 的拍子网格 -> grid npz（只给 ring_lab 用，不改 bands.npz 和 pv.py）。网格本身用 BEAT、BEAT_PHI，
    小节第一拍按 BAR_PHASE，旋律盘的正上方按 TOP_BEATS；下面几步是核对，结果也存进去：
    1 拍长和相位：混音的 onset 包络（22.05 kHz、hop 128、8 ms 高斯平滑）在 P ∈ [0.360, 0.367] s、相位步长 2 ms 上
      搜索（再在最好的附近细搜），使网格点上的平均值最大；每 4 小节再找一次局部相位，应在 ±0.02 s 以内
    2 小节第一拍：和弦、低音的 chroma（谐波部分）每拍的变化，按拍号 mod 4 在 8 小节的滑动窗里投票
    3 旋律盘正上方：67.67、102.58、108.40、314.22 s 应正好是小节线（|Δ| < 0.02 s），4 小节和 2 小节一圈都查"""
    import librosa
    sr, hop = 22050, 128
    y, _ = librosa.load(a.mix, sr=sr, mono=True)
    fps, dur = sr / hop, len(y) / sr
    oe = gauss1d(librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop), 0.008 * fps)
    oe /= oe.mean()
    best = (-1.0, 0.0, 0.0)
    for P in np.arange(0.360, 0.367 + 1e-9, 1e-5):
        ph = np.arange(0, P, 0.002)
        s = grid_score(oe, fps, P, ph)
        if s.max() > best[0]:
            best = (float(s.max()), float(P), float(ph[np.argmax(s)]))
    for P in np.arange(best[1] - 2e-5, best[1] + 2e-5 + 1e-12, 5e-7):
        ph = np.arange(best[2] - 0.004, best[2] + 0.004 + 1e-9, 0.0005)
        s = grid_score(oe, fps, P, ph)
        if s.max() > best[0]:
            best = (float(s.max()), float(P), float(ph[np.argmax(s)]))
    score, P_fit, phi_fit = best
    P, phi = BEAT, BEAT_PHI
    s0 = float(grid_score(oe, fps, P, phi)[0])
    print(f"拍长、相位：搜索 P {P_fit:.6f} s（{60 / P_fit:.3f} BPM）phi {phi_fit:.4f} s；"
          f"用 P {P:.6f} phi {phi:.3f}：网格上 {s0:.3f}，反拍八分 {float(grid_score(oe, fps, P, phi + P / 2)[0]):.3f}")
    nb = int((dur - phi) / P) + 1
    k = np.arange(nb)
    beats = beat_time(k)
    phase, ok = bar_phase(beats)
    bar1 = k % 4 == phase
    # 每 4 小节（从第一个小节第一拍起，16 拍一窗）的局部相位
    dd = np.arange(-0.12, 0.12 + 1e-9, 0.002)
    win = []
    for k0 in range(2, nb - 16, 16):
        lo, hi = beats[k0] - P / 2, beats[k0 + 15] + P / 2
        s = grid_score(oe, fps, P, phi + dd, lo, hi)
        j = int(np.argmax(s))
        win.append((beats[k0], dd[j], s[j] / float(grid_score(oe, fps, P, phi + dd[j] + P / 2, lo, hi)[0])))
    win = np.array(win)
    good = win[:, 2] >= 1.15                    # 拍点比反拍明显的窗才算数（前奏的清唱、尾奏的长音不算）
    off = win[good, 1]
    print(f"每 4 小节的局部相位（{good.sum()}/{len(win)} 窗算数）：{off.min():+.3f}..{off.max():+.3f} s，"
          f"p5/p95 {np.percentile(off, 5):+.3f}/{np.percentile(off, 95):+.3f}，std {off.std():.3f}，"
          f"±0.02 以内 {np.mean(np.abs(off) <= 0.02) * 100:.0f}%")
    for t, o, c in win[~good]:
        print(f"    不算数的窗 {t:6.1f} s：{o:+.3f}（拍点/反拍 {c:.2f}）")
    for t, o, c in win[good & (np.abs(win[:, 1]) > 0.02)]:
        print(f"    超出 ±0.02 的窗 {t:6.1f} s：{o:+.3f}（拍点/反拍 {c:.2f}）")
    # 小节第一拍：chroma 变化按拍号 mod 4 投票
    yh = librosa.effects.harmonic(y, margin=3.0)
    cf = sr / 512

    def change(X):
        Z = np.array([X[:, int(t * cf):max(int((t + P) * cf), int(t * cf) + 1)].mean(1) for t in beats])
        Z /= np.linalg.norm(Z, axis=1, keepdims=True) + 1e-9
        return np.r_[0, 1 - np.sum(Z[1:] * Z[:-1], 1)]
    chg = change(librosa.feature.chroma_cqt(y=yh, sr=sr, hop_length=512))
    bchg = change(librosa.feature.chroma_cqt(y=yh, sr=sr, hop_length=512, fmin=librosa.note_to_hz("C1"), n_octaves=3))
    votes = []
    for s in range(0, nb - 32, 8):
        i = np.arange(s, s + 32)
        votes.append((beats[s], beats[s + 31], *[int(np.argmax([x[i[i % 4 == p]].mean() for p in range(4)]))
                                                  for x in (chg, bchg)]))
    votes = np.array(votes)
    for t0, t1 in ((0.0, 167.3), (197.5, dur)):
        sel = (votes[:, 0] >= t0) & (votes[:, 1] < t1)
        want = int(bar_phase(t0)[0])
        print(f"小节第一拍 {t0:g}–{t1:g} s（≡{want}）：8 小节窗 {sel.sum()} 个，和弦变化投 ≡{want} 的 "
              f"{int((votes[sel, 2] == want).sum())} 个，低音 {int((votes[sel, 3] == want).sum())} 个")
    sel = (votes[:, 1] > 167.3) & (votes[:, 0] < 197.5)
    print("小节第一拍 167.3–197.5 s（待人耳确认，按 0、2 填）：各窗起点:和弦/低音投的余数 "
          + " ".join(f"{t:.1f}:{int(c)}/{int(b)}" for t, _, c, b in votes[sel]))
    # 旋律盘的正上方
    down = beats[bar1]
    for bars in (4, 2):
        T = 4 * bars * P
        rows = []
        for tc in (67.67, 102.58, 108.40, 314.22):
            top = float(t_top(tc))
            top += round((tc - top) / T) * T
            dn = down[np.argmin(np.abs(down - top))]
            lo = win[np.argmin(np.abs(win[:, 0] + 8 * P - top)), 1]          # 那一窗的局部相位：音频里的小节线
            rows.append(f"{top:.3f}（小节线 {dn:.3f}，Δ {top - dn:+.4f}；按局部相位 Δ {top - dn - lo:+.3f}）")
        print(f"正上方，{bars} 小节一圈（{T:.5f} s）：" + "；".join(rows))
    tops = np.array([[x[0], x[1], float(beat_time(x[1]))] for x in TOP_BEATS])
    np.savez(a.out, P=P, phi=phi, bpm=60 / P, beats=beats, bar1=bar1, downbeats=down, downbeat_ok=ok[bar1],
             unconfirmed=np.array([167.3, 197.5]), phase_from=np.array([x[0] for x in BAR_PHASE]),
             phase_mod=np.array([x[1] for x in BAR_PHASE]), phase_ok=np.array([x[2] for x in BAR_PHASE]),
             top_from=tops[:, 0], top_beat=tops[:, 1].astype(int), top_t=tops[:, 2],
             P_fit=P_fit, phi_fit=phi_fit, win_t=win[:, 0], win_off=win[:, 1], win_contrast=win[:, 2],
             vote_t0=votes[:, 0], vote_t1=votes[:, 1], vote_chord=votes[:, 2].astype(int),
             vote_bass=votes[:, 3].astype(int), chg=chg, bchg=bchg)
    print(a.out, f"{nb} 拍、{int(bar1.sum())} 个小节第一拍（{int((~ok[bar1]).sum())} 个待人耳确认）；"
          f"正上方 T_top = {', '.join(f'{x:.4f}' for x in tops[:, 2])} s", flush=True)


def click_cmd(a):
    """混音的一段（--t0..--t1 秒）叠上咔哒声存成 wav，听着核对：--grid 是每拍一下，小节第一拍高音（1760 Hz）、
    其余拍低音（880 Hz）；--at 是这些时刻一下轻的（1320 Hz），--at-low 也是轻的、音低一点（660 Hz）。"""
    import soundfile as sf
    sr = sf.info(a.mix).samplerate
    y, _ = sf.read(a.mix, start=int(round(a.t0 * sr)), stop=int(round(a.t1 * sr)), dtype="float32", always_2d=True)
    out = 0.5 * y.astype(np.float64)            # 音乐压低 6 dB，咔哒声才清楚

    def tick(t, hz, amp, tau):
        """t 秒处一下：hz 的正弦，1 ms 起音，按 tau 指数衰减。"""
        i = int(round((t - a.t0) * sr))
        if 0 <= i < len(out):
            tt = np.arange(min(int(8 * tau * sr), len(out) - i)) / sr
            s = amp * np.sin(2 * np.pi * hz * tt) * np.exp(-tt / tau) * np.minimum(tt / 0.001, 1)
            out[i:i + len(tt)] += s[:, None]
    if a.grid:
        g = np.load(a.grid)
        for t, b1 in zip(g["beats"], g["bar1"]):
            tick(t, 1760 if b1 else 880, 0.5 if b1 else 0.3, 0.012)
    for t in a.at or ():
        tick(t, 1320, 0.25, 0.02)
    for t in a.at_low or ():
        tick(t, 660, 0.25, 0.02)
    i = np.arange(len(out))
    out *= np.minimum(1, np.minimum(i, len(out) - 1 - i) / (0.02 * sr))[:, None]     # 两头 20 ms 淡入淡出
    out *= min(1.0, 0.98 / max(np.abs(out).max(), 1e-9))
    sf.write(a.out, out.astype(np.float32), sr, subtype="PCM_16")
    print(a.out, f"{a.t0:g}–{a.t1:g} s", flush=True)


def moon_px(moon, f, W, H):
    """第 f 帧月亮在画面上的中心（像素，x 向右、y 向下）和半径 R（像素）；moon 是场景的 _moon.npz。"""
    q, r = moon["pos"][f], float(moon["r"][f])
    return float(q[0]) * W, (1 - float(q[1])) * H, r * W


def tri_px(moon, f, W, H, stars=None):
    """第 f 帧夏季大三角三颗星在画面上的位置（像素）：月亮中心 + off·R，off 默认取 TRI_STARS。
    坐标和 moon_px 一样是连续的（第 i 个像素占 [i, i+1)），cv2 画图的像素中心在整数上，要减 0.5。"""
    cx, cy, R = moon_px(moon, f, W, H)
    return {k: (cx + ox * R, cy + oy * R) for k, (ox, oy) in (stars or TRI_STARS).items()}


def stars_cmd(a):
    """在底图上核对大三角三颗星的位置。每一帧在按 TRI_STARS 算出的位置 4 像素以内找星：亮度的高斯差（σ 1 和 3 像素，
    只留点状的星，压掉旁边大片亮区的边缘，比如织女旁边的银河）最大的那点，取亚像素重心。星会闪，前面还有光点飘过，
    高斯差不到这颗星 p90 的 0.6 倍的帧不算。首、中、尾（或 --at 给的帧号）前后 0.5 秒里算数的帧取中位数；偏差超过
    1.5 像素，就给出修正后的 off：--t0..--t1 秒（默认整段）里算数的帧的中位数。"""
    import cv2
    mo = np.load(a.moon)
    files = sorted(glob.glob(os.path.join(a.frames, "f_*.png")))
    nos = np.array([frame_no(p) for p in files])
    yy, xx = np.mgrid[-6:7, -6:7]
    near = np.hypot(xx, yy) <= 4
    names = list(TRI_STARS)
    rec = np.zeros((len(files), len(names), 5))         # 每帧每颗星：偏差 dx、dy（像素），高斯差，测到的 off（R）
    for n, path in enumerate(files):
        lum = cv2.imread(path).astype(np.float32).mean(-1)
        H, W = lum.shape
        cx, cy, R = moon_px(mo, nos[n], W, H)
        for s, (x, y) in enumerate(tri_px(mo, nos[n], W, H).values()):
            X, Y = int(math.floor(x)), int(math.floor(y))         # 预测位置所在的像素
            crop = lum[Y - 20:Y + 21, X - 20:X + 21]
            w = (cv2.GaussianBlur(crop, (0, 0), 1.0) - cv2.GaussianBlur(crop, (0, 0), 3.0))[14:27, 14:27]
            j, i = np.unravel_index(np.argmax(np.where(near, w, -np.inf)), w.shape)
            c = np.clip(w[j - 1:j + 2, i - 1:i + 2], 0, None)
            mx = X - 6 + i + 0.5 + float(c.sum(0) @ np.arange(-1, 2)) / max(float(c.sum()), 1e-6)
            my = Y - 6 + j + 0.5 + float(c.sum(1) @ np.arange(-1, 2)) / max(float(c.sum()), 1e-6)
            rec[n, s] = (mx - x, my - y, w[j, i], (mx - cx) / R, (my - cy) / R)
    good = rec[..., 2] > 0.6 * np.percentile(rec[..., 2], 90, axis=0)
    worst = 0.0
    for f0 in a.at or (nos[0], nos[len(nos) // 2], nos[-1]):
        near_t = np.abs(nos - f0) <= FPS // 2
        out = []
        for s, k in enumerate(names):
            m = near_t & good[:, s]
            if not m.any():
                out.append(f"{k} 没测到")
                continue
            dx, dy = np.median(rec[m, s, 0]), np.median(rec[m, s, 1])
            worst = max(worst, math.hypot(dx, dy))
            out.append(f"{k} 偏 ({dx:+.2f}, {dy:+.2f}) = {math.hypot(dx, dy):.2f} px（{m.sum()} 帧）")
        print(f"f_{int(f0):05d}（{f0 / FPS:.2f} s）前后 0.5 秒：" + "；".join(out), flush=True)
    sel = (nos >= (a.t0 or 0) * FPS) & (nos <= (a.t1 or 1e9) * FPS)
    fit = [np.median(rec[sel & good[:, s], s, 3:5], axis=0) for s in range(len(names))]
    msg = "，".join(f'"{k}": ({x:.3f}, {y:.3f})' for k, (x, y) in zip(names, fit))
    print(("偏差超过 1.5 像素，修正后的 off（R）：" if worst > 1.5 else f"最大偏差 {worst:.2f} px，不用修正；测到的 off（R）：")
          + msg, flush=True)


def section_col(pv, n, col="ring"):
    """pv.py 段落表（SECTIONS）里的一列展开成逐帧（60 fps，n 帧）的数组，交界处做 1 秒的滑动平均，和 pv.py 的
    section_arrays 一样；默认是「频谱环」那一列（ring，0.45–1.0）。pv.py 要 import bpy，这里用 ast 从源码里读。"""
    import ast
    tree = ast.parse(open(pv, encoding="utf-8").read())
    secs = names = None
    def assigns(node, name):
        """node 是不是给 name 赋值的语句。"""
        if isinstance(node, ast.Assign):
            tg = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            tg = [node.target]
        else:
            return False
        return any(isinstance(x, ast.Name) and x.id == name for x in tg)
    for node in tree.body:
        if assigns(node, "SECTIONS"):
            secs = ast.literal_eval(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == "section_arrays":
            for sub in ast.walk(node):
                if assigns(sub, "names"):
                    names = ast.literal_eval(sub.value)
    if secs is None or names is None:
        raise SystemExit(f"{pv} 里找不到 SECTIONS 或 section_arrays 的 names")
    j = list(names).index(col)
    t = np.arange(n) / FPS
    x = np.zeros(n, np.float32)
    for i, (_, t0, *vals) in enumerate(secs):
        t1 = secs[i + 1][1] if i + 1 < len(secs) else 1e9
        x[(t >= t0) & (t < t1)] = vals[j]
    k = FPS
    return np.convolve(np.pad(x, (k // 2, k - k // 2 - 1), mode="edge"), np.ones(k) / k, "valid").astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("f0")
    p.add_argument("lead")
    p.add_argument("out")
    p.add_argument("--method", choices=("pyin", "rmvpe"), default="pyin")
    p.add_argument("--t0", type=float, help="pyin 只算这一段（秒）")
    p.add_argument("--t1", type=float)
    p.add_argument("--lrc", help="rmvpe：歌词 LRC，用来定句首")
    p.add_argument("--ddsp", default=".", help="rmvpe：DDSP-SVC 的目录（RMVPE 的代码和权重 pretrain/rmvpe 在里面）")
    p = sub.add_parser("beatgrid")
    p.add_argument("mix")
    p.add_argument("out")
    p = sub.add_parser("click")
    p.add_argument("mix")
    p.add_argument("out")
    p.add_argument("--t0", type=float, required=True)
    p.add_argument("--t1", type=float, required=True)
    p.add_argument("--grid", help="grid npz：每拍一下，小节第一拍高音")
    p.add_argument("--at", type=float, nargs="+", help="这些时刻（秒）一下轻的")
    p.add_argument("--at-low", type=float, nargs="+", help="同上，音低一点")
    p = sub.add_parser("stars")
    p.add_argument("frames")
    p.add_argument("--moon", required=True)
    p.add_argument("--at", type=int, nargs="+", help="在这些帧号前后 0.5 秒核对（默认首、中、尾）")
    p.add_argument("--t0", type=float, help="修正 off 时只用这段（秒）")
    p.add_argument("--t1", type=float)
    p = sub.add_parser("draw")
    p.add_argument("frames")
    p.add_argument("out")
    p.add_argument("--style", required=True)
    p.add_argument("--bands", required=True)
    p.add_argument("--moon", required=True)
    p.add_argument("--f0")
    p.add_argument("--pv", default="cases/kimishira/scripts/pv.py", help="melody2：读段落表 ring 列的 pv.py")
    p.add_argument("--gain", type=float, default=1.0, help="整体亮度")
    p.add_argument("--procs", type=int, default=16)
    p = sub.add_parser("grid")
    p.add_argument("out")
    p.add_argument("tiles", nargs="+", help="名字=帧目录")
    p.add_argument("--moon", required=True)
    p.add_argument("--font", required=True)
    p.add_argument("--tile", type=int, default=640)
    a = ap.parse_args()
    {"f0": f0_cmd, "draw": draw_cmd, "grid": grid_cmd, "beatgrid": beatgrid_cmd, "click": click_cmd,
     "stars": stars_cmd}[a.cmd](a)


if __name__ == "__main__":
    main()
