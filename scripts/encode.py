"""Frames + the matching slice of the song -> MP4, with a light film grain.

    .venv/Scripts/python scripts/encode.py cases/uraomote/renders/sample cases/uraomote/audio/urao_mix.m4a cases/uraomote/renders/sample.mp4
"""
import json
import os
import subprocess
import sys

import imageio_ffmpeg


def main():
    frames, audio, out = sys.argv[1:4]
    win = json.load(open(os.path.join(frames, "window.json")))
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y",
           "-framerate", str(win["fps"]), "-i", os.path.join(frames, "f_%04d.png"),
           "-ss", f"{win['start']:.3f}", "-t", f"{win['end'] - win['start']:.3f}", "-i", audio,
           "-vf", "noise=alls=6:allf=t+u,format=yuv420p",
           "-c:v", "libx264", "-crf", "16", "-preset", "slow",
           "-c:a", "aac", "-b:a", "256k", "-shortest", out]
    subprocess.run(cmd, check=True)
    print(out)


if __name__ == "__main__":
    main()
