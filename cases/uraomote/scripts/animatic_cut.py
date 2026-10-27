"""Join the animatic's frames with the song into an MP4 (H.264 + AAC). A frame that is missing (a part that has
not run yet) is filled with the frame before it, and the count of those is printed. The film's finish goes on
here, not in the render, so it can be changed without rendering again: halation (the highlights bled warm and
soft over their surroundings), a vignette and a fine grain; LOOK=0 leaves the frames as they are.

    python cases/uraomote/scripts/animatic_cut.py <frames_dir> <song> <out.mp4> [fps]
"""
import json
import os
import shutil
import subprocess
import sys

LOOK = ("[0:v]format=gbrp,split[base][hi];"                                  # planar: blend on packed rgb goes purple
        "[hi]lutrgb=r='clip((val-170)*3,0,255)':g='clip((val-170)*2.4,0,255)':b='clip((val-170)*2,0,255)',"
        "gblur=sigma=22[glow];"
        "[base][glow]blend=all_mode=screen:all_opacity=0.4,format=gbrp,"
        "vignette=angle=PI/4.6,noise=alls=9:allf=t+u,format=yuv420p[v]")


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main():
    frames, song, out = sys.argv[1:4]
    fps = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    timing = json.load(open(os.path.join(os.path.dirname(song), "urao_timing.json"), encoding="utf-8"))
    n = int(round(timing["duration"] * fps))
    filled, last = [], None
    for f in range(n):
        p = os.path.join(frames, f"f_{f:05d}.png")
        if os.path.exists(p):
            last = p
        elif last:
            shutil.copyfile(last, p)
            filled.append(f)
    if filled:
        print(f"{len(filled)} of {n} frames missing, filled with the frame before: {filled[:10]}...")
    look = os.environ.get("LOOK", "1") != "0"
    cmd = [ffmpeg(), "-v", "error", "-y", "-framerate", str(fps), "-start_number", "0",
           "-i", os.path.join(frames, "f_%05d.png"), "-i", song] + \
          (["-filter_complex", LOOK, "-map", "[v]"] if look else ["-map", "0:v", "-pix_fmt", "yuv420p"]) + \
          ["-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    subprocess.run(cmd, check=True)
    for f in filled:
        os.remove(os.path.join(frames, f"f_{f:05d}.png"))   # so a later run of the missing part renders them
    print(out, f"{n} frames at {fps} fps")


if __name__ == "__main__":
    main()
