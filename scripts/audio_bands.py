"""逐帧的音频特征，给一图流 PV 的 Blender 场景用：节拍、重拍、响度、低频、高频、人声，以及 N 段对数频谱。

    .venv/Scripts/python scripts/audio_bands.py <mix> <vocal> <out.npz> --fps 60 --bands 48

输出 npz（每一项都是逐视频帧的，第 k 帧对应 t = k / fps）：
  loud, bass, high, onset, vocal : (n_frames,)  0..1
  voice                          : 人声的快包络（跟到每个字），0..1
  spec                           : (n_frames, bands)  0..1，已做快起慢落的平滑
  beats, downbeats               : 秒
  fps, duration, tempo
"""
import argparse

import librosa
import numpy as np


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
    a = ap.parse_args()

    sr = 44100
    hop = sr // a.fps            # 一帧一个 hop，频谱和视频帧对齐
    mix, _ = librosa.load(a.mix, sr=sr, mono=True)
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
    vdb = norm(librosa.power_to_db(Sv.sum(axis=0) + 1e-10), 10, 99)
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
        a.out, fps=a.fps, duration=dur, tempo=tempo,
        beats=beat_t.round(4), downbeats=beat_t[phase::4].round(4),
        loud=fit(loud), bass=fit(bass), high=fit(high), vocal=fit(vocal), voice=fit(voice),
        onset=fit(np.clip(onset / (np.percentile(onset, 99) + 1e-9), 0, 1)),
        spec=np.stack([fit(spec[:, i]) for i in range(a.bands)], axis=1).astype(np.float16))
    print(f"{dur:.2f} s, {n} frames at {a.fps} fps, {tempo:.1f} BPM, {len(beat_t)} beats, "
          f"{len(beat_t[phase::4])} downbeats -> {a.out}")


if __name__ == "__main__":
    main()
