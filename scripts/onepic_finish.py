"""一图流 PV 的收尾：Blender 渲出的分段视频 -> 一条成片（给 B 站：H.264 High、yuv420p、AAC 320k、faststart）。

    python onepic_finish.py <分段目录> <音频> <输出.mp4> [--ass 字幕.ass] [--overlay 旋律盘目录] [--fade-in 1.5] [--fade-out 4]
                          [--start 秒]     # 分段是从这一秒起渲的（预览只看中间一段）：音轨、字幕、左下角的 PNG 跟着对齐

分段按文件名排序首尾相接（concat，不重编码）成 master.mkv，再一次编码时加：胶片颗粒（暗部渐变不出色带）、轻暗角、
开头结尾的淡入淡出、ASS 字幕（歌词、制作信息）、音轨。字幕改了只需重跑这一步，不用重渲染。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path):
    out = subprocess.run([ffmpeg(), "-i", path], capture_output=True, text=True).stderr
    hms = out.split("Duration: ")[1].split(",")[0]
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chunks")
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--ass")
    ap.add_argument("--overlay", help="onepic_player.py 的输出目录（o_*.png + region.json）")
    ap.add_argument("--fade-in", type=float, default=1.5)
    ap.add_argument("--fade-out", type=float, default=4.0)
    ap.add_argument("--grain", type=int, default=2)
    ap.add_argument("--vignette", type=float, default=0.35, help="四角最暗处压掉的比例")
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--start", type=float, default=0.0)
    a = ap.parse_args()

    parts = sorted(glob.glob(os.path.join(a.chunks, "*.mp4")))
    lst = os.path.join(a.chunks, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    master = os.path.join(a.chunks, "master.mkv")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", master],
                   check=True)
    dur = min(duration(master), duration(a.audio) - a.start)
    print(f"{len(parts)} chunks -> {master}, {dur:.2f} s", flush=True)

    # 暗角：ffmpeg 的 vignette 在 4K 上每帧要 0.1 秒多，比 x264 还慢；先算一张黑色、四角渐不透明的图，叠上去
    info = subprocess.run([ffmpeg(), "-i", master], capture_output=True, text=True).stderr
    w, h = (int(x) for x in re.search(r"Video: .*?(\d{3,5})x(\d{3,5})", info).groups())
    vig = os.path.join(a.chunks, "vignette.png")
    alpha = (f"255*{a.vignette}*pow(clip((hypot((X/W-0.5)*2,(Y/H-0.5)*2)-0.55)/0.9,0,1),1.6)")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=black:s={w}x{h},format=rgba",
                    "-vf", f"geq=r=0:g=0:b=0:a='{alpha}'", "-frames:v", "1", vig], check=True)
    chain = []
    if a.grain:
        chain.append(f"noise=alls={a.grain}:allf=t")
    fx = []
    if a.fade_in:
        fx.append(f"fade=t=in:st=0:d={a.fade_in}")
    if a.fade_out:
        fx.append(f"fade=t=out:st={dur - a.fade_out:.3f}:d={a.fade_out}")
    if a.ass:
        ass = os.path.abspath(a.ass).replace("\\", "/").replace(":", "\\:")
        if a.start:     # 字幕按整首的时间：先把时间戳挪到整首的位置，叠完再挪回来
            fx.append(f"setpts=PTS+{a.start}/TB,ass='{ass}',setpts=PTS-STARTPTS")
        else:
            fx.append(f"ass='{ass}'")
    fx.append("format=yuv420p")
    # overlay 要指定 yuv420：format=auto 会把整帧转成 RGB 叠，4K 下慢 7 倍
    graph = f"[0:v]{','.join(chain) or 'null'}[g];[1:v]format=yuva420p[m];[g][m]overlay=format=yuv420[o];"
    inputs = ["-i", master, "-i", vig]
    if a.overlay:      # onepic_player.py 画的透明 PNG 序列，叠在淡入淡出之前（跟着画面一起淡）
        reg = json.load(open(os.path.join(a.overlay, "region.json")))
        inputs += ["-framerate", str(reg["fps"]), "-start_number", str(int(round(a.start * reg["fps"]))),
                   "-i", os.path.join(a.overlay, "o_%05d.png")]
        graph += f"[2:v]format=yuva420p[p];[o][p]overlay=x={reg['x']}:y={reg['y']}:format=yuv420:eof_action=repeat[o];"
    graph += f"[o]{','.join(fx)}[v]"
    aidx = inputs.count("-i")
    inputs += (["-ss", str(a.start)] if a.start else []) + ["-i", a.audio]
    cmd = [ffmpeg(), "-v", "error", "-stats", "-y", "-filter_threads", "32", *inputs,
           "-filter_complex", graph, "-map", "[v]", "-map", f"{aidx}:a", "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-x264-params", "aq-mode=3", "-g", "120",
           "-c:a", "aac", "-b:a", "320k", "-af", f"afade=t=out:st={dur - 0.5:.3f}:d=0.5",
           "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print(a.out, flush=True)


if __name__ == "__main__":
    main()
