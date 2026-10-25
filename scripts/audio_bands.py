"""逐帧的音频特征，给一图流 PV 的 Blender 场景用：节拍、重拍、响度、低频、高频、人声，以及 N 段对数频谱。

    python scripts/audio_bands.py <mix> <vocal> <out.npz> --fps 60 --bands 48
    python scripts/audio_bands.py <mix> - <out.npz> --grid-only      # 只给已有的 npz 补上拍子网格
    python scripts/audio_bands.py <mix> - <out.npz>                  # 没有人声分轨：vocal、voice 是 0

输出 npz（每一项都是逐视频帧的，第 k 帧对应 t = k / fps）：
  loud, bass, high, onset, vocal : (n_frames,)  0..1
  voice                          : 人声的快包络（跟到每个字），0..1
  spec                           : (n_frames, bands)  0..1，已做快起慢落的平滑
  beats, downbeats               : 秒（librosa 的 beat_track，会测成倍频）
  grid_beat, grid_phase          : 恒速的拍子网格：拍长、第 0 拍的时刻（秒），第 k 拍在 grid_phase + k·grid_beat
  fps, duration, tempo
"""
import argparse

import librosa
import numpy as np


def grid_score(oe, ofps, P, ph):
    """网格 ph + k·P（ph 是一组相位）落在拍上时 onset 包络 oe（每秒 ofps 帧）的平均值，和 ph 一样长。"""
    ph = np.atleast_1d(np.asarray(ph, np.float64))
    dur = len(oe) / ofps
    k = np.arange(np.floor(-ph.max() / P), np.ceil((dur - ph.min()) / P) + 1)
    g = ph[:, None] + P * k[None, :]
    ok = (g >= 0) & (g <= dur)
    return (np.interp(g * ofps, np.arange(len(oe)), oe) * ok).sum(1) / np.maximum(ok.sum(1), 1)


def beat_grid(y, sr, bpm=(70.0, 200.0)):
    """恒速的拍子网格 -> (拍长 P, 第 0 拍的时刻 φ, 拍点 / 反拍)，秒。每首歌自己量，不假定速度。
    onset 包络（hop 256、8 ms 高斯平滑）的自相关在 bpm 范围里的几个峰，连同它们的 2 倍、1/2、3/2、2/3 当候选；
    每个候选在 ±1% 里细搜拍长和相位，使网格点上 onset 的平均值最大（3:2 的网格一半落在反拍上，平均值低）。
    取平均值最大的；它的反拍（φ + P/2）若也差不多一样响（拍点/反拍 < 1.2，慢一倍的网格锁在重拍上时就是这样，
    反拍其实是弱拍），换成快一倍的网格再看，直到反拍明显弱下去或者超出 bpm。
    librosa 的 beat_track 常测成倍频：一首 165 BPM 的歌它测成 109；网格上平均值最高的是锁在重拍上的 82.5
    （拍点/反拍 1.06），这里换到 165.00（1.33）。"""
    hop = 256
    ofps = sr / hop
    oe = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    s = 0.008 * ofps
    k = np.arange(-int(4 * s), int(4 * s) + 1)
    oe = np.convolve(oe, np.exp(-0.5 * (k / s) ** 2) / (s * np.sqrt(2 * np.pi)), "same")
    oe = oe / oe.mean()
    lo, hi = 60.0 / bpm[1], 60.0 / bpm[0]

    def fit(P0):
        best = (-1.0, P0, 0.0)
        for P in np.linspace(P0 * 0.99, P0 * 1.01, 201):
            ph = np.arange(0, P, 0.002)
            sc = grid_score(oe, ofps, P, ph)
            if sc.max() > best[0]:
                best = (float(sc.max()), float(P), float(ph[np.argmax(sc)]))
        step = P0 * 0.0001
        for P in np.arange(best[1] - step, best[1] + step + 1e-12, step / 40):
            ph = np.arange(best[2] - 0.004, best[2] + 0.004 + 1e-9, 0.0005)
            sc = grid_score(oe, ofps, P, ph)
            if sc.max() > best[0]:
                best = (float(sc.max()), float(P), float(ph[np.argmax(sc)]))
        score, P, phi = best
        contrast = score / float(grid_score(oe, ofps, P, phi + P / 2)[0])
        print(f"  {60 / P0:6.1f} BPM 附近 -> {60 / P:8.3f} BPM, φ {phi % P:.4f} s, 网格上 {score:.3f}, 拍点/反拍 {contrast:.2f}")
        return score, P, phi % P, contrast

    ac = librosa.autocorrelate(oe - oe.mean(), max_size=int(hi * 2 * ofps) + 2)
    lags = np.arange(len(ac)) / ofps
    peak = np.flatnonzero((ac[1:-1] > ac[:-2]) & (ac[1:-1] >= ac[2:])) + 1
    peak = peak[(lags[peak] >= lo * 0.5) & (lags[peak] <= hi * 2)]
    peak = peak[np.argsort(ac[peak])[::-1][:6]]
    cands = sorted(c for c in {round(lags[i] * f, 4) for i in peak for f in (1, 2, 0.5, 1.5, 2 / 3)} if lo <= c <= hi)
    best = max((fit(P0) for P0 in cands), key=lambda x: x[0])
    while best[3] < 1.2 and best[1] / 2 >= lo:
        print("  反拍差不多一样响，换快一倍的网格")
        best = fit(best[1] / 2)
    return best[1], best[2], best[3]


def envelope(x, fps, attack=0.03, release=0.25):
    """快起慢落：上升跟得快，回落慢一点，柱子和光才不会抖。"""
    a = 1 - np.exp(-1 / (fps * attack))
    r = 1 - np.exp(-1 / (fps * release))
    out = np.empty_like(x)
    y = 0.0
    for i, v in enumerate(x):
        y += (a if v > y else r) * (v - y)
        out[i] = y
    return out


def norm(x, lo=5, hi=99):
    a, b = np.percentile(x, lo), np.percentile(x, hi)
    return np.clip((x - a) / (b - a + 1e-9), 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mix")
    ap.add_argument("vocal")
    ap.add_argument("out")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--bands", type=int, default=48)
    ap.add_argument("--grid-only", action="store_true", help="只量拍子网格，补进已有的 out.npz，别的不动")
    a = ap.parse_args()

    sr = 44100
    hop = sr // a.fps            # 一帧一个 hop，频谱和视频帧对齐
    mix, _ = librosa.load(a.mix, sr=sr, mono=True)
    P, phi, contrast = beat_grid(mix, sr)
    print(f"拍子网格：{60 / P:.3f} BPM（拍长 {P:.6f} s），第 0 拍 {phi:.4f} s，拍点/反拍 {contrast:.2f}")
    if a.grid_only:
        d = dict(np.load(a.out))
        d.update(grid_beat=P, grid_phase=phi)
        np.savez_compressed(a.out, **d)
        print("->", a.out)
        return
    if a.vocal == "-":          # 没有人声分轨：人声那两列是 0（嘴、呼吸不靠它们）
        voc = np.zeros_like(mix)
    else:
        voc, _ = librosa.load(a.vocal, sr=sr, mono=True)
        voc = np.pad(voc, (0, max(0, len(mix) - len(voc))))[:len(mix)]
    dur = len(mix) / sr
    n = int(np.ceil(dur * a.fps))

    S = np.abs(librosa.stft(mix, n_fft=4096, hop_length=hop, center=True)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    def band_db(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        return librosa.power_to_db(S[m].sum(axis=0) + 1e-10)

    edges = np.geomspace(55, 14000, a.bands + 1)
    spec = np.stack([band_db(edges[i], edges[i + 1]) for i in range(a.bands)], axis=1)
    # 每段各自归一：高频本来能量就小，各段按自己的分布拉开才看得出动静
    spec = np.stack([norm(spec[:, i], 20, 99.5) for i in range(a.bands)], axis=1)
    spec = np.stack([envelope(spec[:, i], a.fps, 0.02, 0.18) for i in range(a.bands)], axis=1)

    loud = envelope(norm(librosa.power_to_db(S.sum(axis=0) + 1e-10), 2, 99.5), a.fps, 0.05, 0.4)
    bass = envelope(norm(band_db(30, 150)), a.fps, 0.01, 0.15)
    high = envelope(norm(band_db(5000, 14000)), a.fps, 0.02, 0.3)
    Sv = np.abs(librosa.stft(voc, n_fft=2048, hop_length=hop)) ** 2
    vdb = norm(librosa.power_to_db(Sv.sum(axis=0) + 1e-10), 10, 99) if a.vocal != "-" else np.zeros(Sv.shape[1])
    vocal = envelope(vdb, a.fps, 0.05, 0.3)
    voice = envelope(vdb, a.fps, 0.012, 0.07)      # 快的：跟得上一个个字，给嘴的张合用

    onset = librosa.onset.onset_strength(y=mix, sr=sr, hop_length=hop)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=hop)
    low = librosa.onset.onset_strength(y=mix, sr=sr, hop_length=hop, fmax=200, n_mels=32)
    phase = int(np.argmax([low[beats[p::4]].mean() if len(beats[p::4]) else 0 for p in range(4)]))

    def fit(x):
        x = np.asarray(x, dtype=np.float32)
        return np.pad(x, (0, max(0, n - len(x))), mode="edge")[:n]

    np.savez_compressed(
        a.out, fps=a.fps, duration=dur, tempo=tempo, grid_beat=P, grid_phase=phi,
        beats=beat_t.round(4), downbeats=beat_t[phase::4].round(4),
        loud=fit(loud), bass=fit(bass), high=fit(high), vocal=fit(vocal), voice=fit(voice),
        onset=fit(np.clip(onset / (np.percentile(onset, 99) + 1e-9), 0, 1)),
        spec=np.stack([fit(spec[:, i]) for i in range(a.bands)], axis=1).astype(np.float16))
    print(f"{dur:.2f} s, {n} frames at {a.fps} fps, {tempo:.1f} BPM, {len(beat_t)} beats, "
          f"{len(beat_t[phase::4])} downbeats -> {a.out}")


if __name__ == "__main__":
    main()
