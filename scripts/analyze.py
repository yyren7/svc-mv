"""Timing data for the PV: beats, downbeats, loudness per video frame, sung lines.

    .venv/Scripts/python scripts/analyze.py cases/uraomote/audio/urao_mix.m4a cases/uraomote/audio/urao_vocal.wav \
        cases/uraomote/audio/urao_lines.jsonl cases/uraomote/audio/urao_timing.json --fps 30

The lines file is eval_lines.py's lines.jsonl from DDSP-SVC (start / end in seconds), filtered to one song.
"""
import argparse
import json
import subprocess

import imageio_ffmpeg
import librosa
import numpy as np


def load(path, sr):
    # m4a goes through ffmpeg, librosa's audioread fallback is slow and noisy on Windows
    if path.lower().endswith((".m4a", ".mp4", ".aac")):
        raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                             check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.float32)
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y


def per_frame(values, times, fps, n_frames):
    """Resample a curve onto video frames (frame k covers t = k / fps)."""
    t = np.arange(n_frames) / fps
    return np.interp(t, times, values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mix")
    ap.add_argument("vocal")
    ap.add_argument("lines")
    ap.add_argument("out")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()

    sr, hop = 22050, 512
    mix = load(a.mix, sr)
    voc = load(a.vocal, sr)
    dur = len(mix) / sr
    n_frames = int(np.ceil(dur * a.fps))

    onset = librosa.onset.onset_strength(y=mix, sr=sr, hop_length=hop)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=hop)

    # Downbeat phase: of the 4 possible phases, the one whose beats carry the most low-end onset energy.
    low = librosa.onset.onset_strength(y=mix, sr=sr, hop_length=hop, fmax=200, n_mels=32)
    phase = int(np.argmax([low[beats[p::4]].mean() if len(beats[p::4]) else 0 for p in range(4)]))
    downbeat_t = beat_t[phase::4]

    onset_t = librosa.times_like(onset, sr=sr, hop_length=hop)
    onset_n = onset / (np.percentile(onset, 99) + 1e-9)
    rms_mix = librosa.feature.rms(y=mix, hop_length=hop)[0]
    rms_voc = librosa.feature.rms(y=voc[:len(mix)], hop_length=hop)[0]
    rms_t = librosa.times_like(rms_mix, sr=sr, hop_length=hop)

    def norm_db(rms):
        db = librosa.amplitude_to_db(rms + 1e-6, ref=np.max)
        return np.clip((db + 40) / 40, 0, 1)

    lines = []
    with open(a.lines, encoding="utf-8") as f:
        for row in f:
            r = json.loads(row)
            lines.append({"start": r["start"], "end": r["end"]})
    lines.sort(key=lambda r: r["start"])

    out = {
        "fps": a.fps, "duration": dur, "n_frames": n_frames,
        "tempo": tempo, "beats": beat_t.round(3).tolist(), "downbeats": downbeat_t.round(3).tolist(),
        "onset": per_frame(np.clip(onset_n, 0, 1), onset_t, a.fps, n_frames).round(3).tolist(),
        "loud_mix": per_frame(norm_db(rms_mix), rms_t, a.fps, n_frames).round(3).tolist(),
        "loud_vocal": per_frame(norm_db(rms_voc), rms_t[:len(rms_voc)], a.fps, n_frames).round(3).tolist(),
        "lines": lines,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"{dur:.1f} s, {tempo:.1f} BPM, {len(beat_t)} beats, {len(downbeat_t)} downbeats, "
          f"{len(lines)} lines, {n_frames} frames at {a.fps} fps")


if __name__ == "__main__":
    main()
