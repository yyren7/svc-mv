"""把人物和权重图嵌进 rig_painter.html，出一份双击就能用的网页（不用再拖文件进去）：
    python scripts/rig_painter_embed.py <目录> [部位 ...]
目录里要有 ref_char.png 和 <部位>.png（默认 hair tail），输出 <目录>/rig_painter.html。只用标准库。
"""
import base64
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1]
parts = sys.argv[2:] or ["hair", "tail"]


def uri(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


embed = {"ref": uri(os.path.join(src, "ref_char.png")),
         "maps": {p: uri(os.path.join(src, p + ".png")) for p in parts},
         "first": parts[0]}
html = open(os.path.join(here, "rig_painter.html"), encoding="utf-8").read()
html = html.replace('<script>\n"use strict";', "<script>window.EMBED = " + json.dumps(embed) + ";</script>\n<script>\n\"use strict\";", 1)
out = os.path.join(src, "rig_painter.html")
open(out, "w", encoding="utf-8").write(html)
print(out, "%.1f MB" % (len(html) / 1e6))
