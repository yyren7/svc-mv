"""kimishira 的头发、尾巴、呼吸三张权重图（替代 onepic_prep.py rig 按颜色算的那三张）-> rig_paint/<部位>.png，
另外出一览给人看 -> renders/rig_review/paint_overview.jpg（现在用的 | 这次画的）、paint_hair.jpg（头发全尺寸，
青线是衣服的边，衣服里的头发不动）、paint_tail.jpg（尾巴放大两倍）。在 AutoDL 上：
    PYTHONPATH=/root/autodl-tmp/pv/pylib $PY cases/kimishira/scripts/rig_paint.py
读的是 art/prep/rig_maps/ 里 rig 导出的人物（ref_char.png）和现在用的权重图；重跑会覆盖 rig_paint/ 里手改过的图。
画完要重跑 rig（rig_review.sh 会跑）才进场景。
按颜色算的那三张出的问题：左边受光的浅粉长发、尾巴（偏蓝紫）不在"头发色"里，只动了零碎几块；袖子多边形画宽了，
压住了袖子外面的长发；呼吸是一个方块，头也跟着动。
"""
import json
import os

import cv2
import numpy as np

CASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(CASE, "rig_paint")
SHOW = os.path.join(CASE, "renders", "rig_review")
os.makedirs(OUT, exist_ok=True)
os.makedirs(SHOW, exist_ok=True)
spec = json.load(open(os.path.join(CASE, "rig.json"), encoding="utf-8"))
maps_dir = os.path.join(CASE, "art", "prep", "rig_maps")
img = cv2.imread(os.path.join(maps_dir, "ref_char.png"), cv2.IMREAD_UNCHANGED)
h, w = img.shape[:2]
asp = w / h
alpha = img[..., 3].astype(np.float32) / 255
hsv = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV).astype(np.float32)
H, S, V = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
U, Y = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)


def ramp(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def blur(x, s):
    return cv2.GaussianBlur(x.astype(np.float32), (0, 0), s)


def dist(p):
    return np.hypot((U - p[0]) * asp, Y - p[1])


def box(b):
    return (U >= b[0]) & (U <= b[2]) & (Y >= b[1]) & (Y <= b[3])


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def fill_holes(m, max_area):
    n, lab, st, _ = cv2.connectedComponentsWithStats((1 - m).astype(np.uint8), connectivity=4)
    out = m.copy()
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a < max_area and x > 0 and y > 0 and x + bw < w and y + bh < h:
            out[lab == i] = 1
    return out


def drop_specks(m, min_area):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[lab].astype(np.uint8)


solid = alpha > 0.5
# 皮肤只在脸、脖子、肩膀、胸口、手（u 0.535–0.73、v 0.20–0.80，左肩往下到 u 0.47）：左边的粉色发丝最粉处
# （色相 348°–360°）、脸左边飘着的浅粉细发丝（饱和度 0.1–0.2，很亮）和皮肤同色
body = box((0.535, 0.20, 0.73, 0.80)) | box((0.47, 0.47, 0.535, 0.80))
skin = ((H >= 348) | (H <= 40)) & (S > 0.08) & (S < 0.6) & (V > 0.5) & solid & body
# 皮肤是成块的（脸、肩膀、手）：开运算去掉 6 px 以下宽的（从肩膀前面飘过的浅粉发丝），只留 1500 px 以上的块
skin = drop_specks(cv2.morphologyEx(skin.astype(np.uint8), cv2.MORPH_OPEN, disk(3)), 1500).astype(bool)
# 白：偏粉的白（袖子，饱和度 0.03–0.27，中位 0.08）和偏蓝的白（裙子、蝴蝶结，饱和度到 0.33）分开算：
# 左边受光的长发是浅粉，饱和度 0.25–0.31，按一个阈值会被当成白衣服
# 裙摆的阴影是淡紫（色相 235–280），也按偏蓝的白算，不然右下的裙子会被当成头发
pinkish = (H >= 280) | (H <= 20)
white = (V > 0.70) & ((pinkish & (S < 0.18)) | (~pinkish & (S < 0.36))) & solid
dark = (V < 0.30) & (S < 0.35) & solid                 # 话筒、话筒线、颈带
# 深色的硬物只在身体中间（话筒、话筒线、颈带都在 u 0.52–0.70）：两边飘出去的深蓝细发丝也是深色，不能当硬物
rigid = blur(cv2.dilate((skin | (dark & (U > 0.52) & (U < 0.70))).astype(np.uint8), np.ones((15, 15), np.uint8)), 4)
hard = np.zeros((h, w), np.uint8)
for line in spec.get("rigid", []):
    pts = np.round(np.array(line["line"]) * (w, h)).astype(np.int32)
    cv2.polylines(hard, [pts], False, 1, thickness=max(1, int(round(2 * line["width"] * h))))
rigid = np.maximum(rigid, blur(hard, 3))

# ---- 尾巴：拱心周围一圈（0.03–0.125 画面高）里不是白的人物像素，取含拱顶那块，补洞。拱顶左边（绕拱心 80°–130°）
# 有一绺头发搭在尾巴上，尾巴在那里外沿只到 0.08–0.095，那一段外径从 0.095（80°）收到 0.082（130°）
T = spec["tail"]
cx, cy = T["center"]


def angle(u, v):
    a = np.degrees(np.arctan2(-(v - cy), (u - cx) * asp))
    return np.where(a > -90, a, a + 360)


ang = angle(U, Y)
r_out = np.where((ang > 80) & (ang < 130), 0.095 - np.clip((ang - 80) / 50, 0, 1) * 0.013, 0.125)
ring = (dist((cx, cy)) > 0.03) & (dist((cx, cy)) < r_out) & box((0.79, 0.62, 0.96, 0.98))
tail_raw = (solid & ~white & ring).astype(np.uint8)
tail_raw = cv2.morphologyEx(tail_raw, cv2.MORPH_CLOSE, disk(3))
core = cv2.morphologyEx(tail_raw, cv2.MORPH_OPEN, disk(6))      # 开运算去掉搭在尾巴上的细发丝（尾巴约 40 px 粗）
n, lab, st, _ = cv2.connectedComponentsWithStats(core)
seed = lab[int(0.716 * h), int(0.858 * w)]
tail_m = (lab == (seed if seed else 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))))
tail_m = cv2.dilate(tail_m.astype(np.uint8), disk(6)) & tail_raw     # 长回开运算削掉的边
tail_m = fill_holes(tail_m, 4000)
tail_m = cv2.dilate(tail_m, disk(5)) & (alpha > 0.01)       # 抗锯齿的边和尾巴外面那圈淡淡的光一起走
a0, a1 = angle(*T["base"]), angle(*T["tip"])
tail_s = np.clip((a0 - ang) / (a0 - a1), 0, 1)
# tail_w 在头发之后算：外面那圈光要避开头发

# ---- 头发：不是皮肤、不是白衣服、不是深色硬物的人物像素（粉的、紫红的、蓝的描边都算），闭运算补上发丝间的缝、
# 填掉高光留下的洞，整片头发一起动；离头越远动得越多。左边飘出去的细发丝大半是半透明的（不透明度过 0.5 的只有
# 三分之一），按不透明度 0.08 起算；细发丝也是一小段一小段的，零碎的块到 40 px 才扔
semi = alpha > 0.08
skin_s = ((H >= 348) | (H <= 40)) & (S > 0.08) & (S < 0.6) & (V > 0.5) & semi & body
white_s = (V > 0.70) & ((pinkish & (S < 0.18)) | (~pinkish & (S < 0.36))) & semi
hair_raw = semi & ~skin_s & ~white_s & ~dark & (S > 0.12)
# 脸和身体的左边、右边长发的外面（左边 u < 0.53、右边 u > 0.76，尾巴除外）除了头发没有别的，淡到看不出颜色、
# 被当成白的浅粉细发丝也算；袖子（衣服）、肩膀（皮肤）后面另外压到 0
outer = (((U < 0.53) | (U > 0.76)) & (Y > 0.25) & (Y < 0.88) & (alpha > 0.06)
         & ~cv2.dilate(tail_m, disk(6)).astype(bool))
hair_raw = (hair_raw | outer).astype(np.uint8)
hair_m = cv2.morphologyEx(hair_raw, cv2.MORPH_CLOSE, disk(4))
hair_m = fill_holes(hair_m, 2500)
hair_m = drop_specks(hair_m, 40)
hair_m = cv2.dilate(hair_m, disk(2)) & (alpha > 0.03) & (1 - tail_m)    # 尾巴也是紫的，按颜色会算进来
away = np.ones((h, w), np.float32)
for b in spec["ears"]:
    away *= 1 - blur(box(b), 4)
center = blur((U > 0.525) & (U < 0.705) & (Y > 0.60), 8)    # 裙子正面和手：上面偏粉的反光不算头发
# 尾巴根（右下那头）一带和右下角的裙边没有头发，尾巴外面那圈光、裙边的淡紫会被当成发丝
away *= (1 - blur(box((0.86, 0.82, 1.0, 1.0)), 4)) * (1 - blur(box((0.76, 0.92, 1.0, 1.0)), 4))
# 右边发梢最低到 v 0.87，再往下（u 0.62–0.86）是裙子右边淡紫的阴影边和裙摆：不是白的，衣服里不算它
away *= 1 - blur(box((0.62, 0.885, 0.86, 1.0)), 6)
lo, hi = spec["hair_reach"]
# 先往外长 5 px 再模糊：1–2 px 的细发丝直接模糊会被稀释到 0.1 以下，几乎不动（长出去的是透明处，不影响）
hair_w = blur(cv2.dilate(hair_m, disk(5)), 2) * ramp(dist(spec["head"]), lo, hi) * away * (1 - center)
# 衣服（裙子、袖子）和尾巴本身不跟头发摆：半透明的袖子后面透出的头发是袖子的贴图。rig.json 画的袖子多边形左边
# 画宽了，把袖子外面垂着的长发也压住了；这里改用衣服本身：大块的白，闭运算、补洞（袖子里透出的头发是被白围住的洞）。
# 头发在衣服、尾巴外面一直是全量。原来是出了衣服 20 px、离尾巴 10 px 才在头发里放开，挨着的发丝 20 px 里从不动到
# 动 12 px，像粘在袖子、尾巴上，摆到头还会折过去。
# - 衣服：放开的那段放到衣服里面（3.5% 画面高），袖子的荷叶边跟着旁边的头发带一点；裙子正面、右下角照旧不动，
#   离皮肤、话筒 12 px 内也不带（不然在手臂边上从带着动一下子掉到 0）
# - 尾巴：只有 40 px 粗，往里放开会整条跟着头发摆。头发一直摆到尾巴边，和尾巴之间是透明的缝，两边反着动时挤的是缝
cloth = drop_specks((white_s & solid).astype(np.uint8), 3000)
cloth = fill_holes(cv2.morphologyEx(cloth, cv2.MORPH_CLOSE, disk(5)), 15000)
free = hair_w * (1 - cloth) * (1 - blur(tail_m, 1.5))
into = 1 - ramp(cv2.distanceTransform(cloth, cv2.DIST_L2, 5) / h, 0, 0.035)
keep = away * (1 - center) * (1 - blur(cv2.dilate((rigid > 0.05).astype(np.uint8), disk(12)), 5))
spread = blur(cv2.dilate(free, disk(int(0.04 * h))), 6) * into * cloth * keep
hair_w = np.maximum(free, spread)
hair_w = blur(hair_w * (1 - rigid), 3) * (1 - rigid)

# ---- 尾巴的权重（接上面的尾巴）：外面那圈光比 5 px 宽，只带 5 px 时尾巴尖转出去，光的外沿留在原地，下沿切成一道
# 硬边。透明处（不透明度 0.35 以下）再往外带 12 px、慢慢放开，头发（离尾巴 3 px 以外的）不算
glow = cv2.dilate(tail_m, disk(12)) & (alpha < 0.35) & ~(hair_m & (1 - cv2.dilate(tail_m, disk(3)))).astype(bool)
tail_soft = np.maximum(blur(tail_m, 1.5), blur(glow.astype(np.uint8), 4) * (alpha < 0.35))
tail_w = tail_soft * tail_s ** 1.2

# ---- 呼吸：以胸口（0.615, 0.59）为中心的软椭圆，横半径 0.23、竖半径 0.22（画面宽 / 高的比例），里面 55% 是 1，
# 往外落到 0；下巴（0.455）以上是 0，头完全不动，锁骨（0.54）起才全量。两边垂下的头发跟着肩膀抬一点，没有方框的边
r_ell = np.hypot((U - 0.615) / 0.23, (Y - 0.59) / 0.22)
breath_w = (1 - ramp(r_ell, 0.55, 1.0)) * ramp(Y, 0.455, 0.54) * (1 - blur(cv2.dilate(tail_m, disk(10)), 4))

new = {"hair": hair_w, "tail": tail_w, "breath": breath_w}
for k, m in new.items():
    cv2.imwrite(os.path.join(OUT, k + ".png"), (np.clip(m, 0, 1) * 255 + 0.5).astype(np.uint8))

# ---- 一览：每个部位现在用的 | 这次画的（热力图，和 onepic_prep.export_maps 同一种画法）
rgb = img[..., :3].astype(np.float32) / 255
gray = (rgb @ np.array([0.114, 0.587, 0.299], np.float32))[..., None] * alpha[..., None]
dim = np.repeat(0.15 + 0.55 * gray, 3, axis=2)


def heat(m):
    q = (np.clip(m, 0, 1) * 255 + 0.5).astype(np.uint8)
    hm = cv2.applyColorMap(q, cv2.COLORMAP_TURBO).astype(np.float32) / 255
    k = np.clip(m * 4, 0, 0.85)[..., None]
    return ((dim * (1 - k) + hm * k) * 255 + 0.5).astype(np.uint8)


def label(im, text):
    from PIL import Image, ImageDraw, ImageFont
    p = Image.fromarray(im[..., ::-1].copy())
    d = ImageDraw.Draw(p)
    f = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 30)
    d.text((16, 10), text, font=f, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    return np.asarray(p)[..., ::-1]


crops = {"hair": (660, 40, 1160, 1020), "tail": (1500, 640, 360, 410), "breath": (660, 40, 1160, 1020)}
names = {"hair": "头发", "tail": "尾巴（放大）", "breath": "呼吸"}
rows = []
for tag, src in (("现在", None), ("新画的", new)):
    cells = []
    for k in ("hair", "tail", "breath"):
        m = (cv2.imread(os.path.join(maps_dir, k + ".png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
             if src is None else src[k])
        x, y, cw, ch = crops[k]
        c = heat(m)[y:y + ch, x:x + cw]
        c = cv2.resize(c, (int(cw * 620 / ch), 620), interpolation=cv2.INTER_AREA)
        cells.append(label(c, f"{names[k]} · {tag}"))
    rows.append(np.hstack(cells))
sheet = np.vstack(rows)
cv2.imwrite(os.path.join(SHOW, "paint_overview.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
edge = heat(hair_w)
edge[cv2.Canny(cloth * 255, 50, 150) > 0] = (255, 255, 0)
cv2.imwrite(os.path.join(SHOW, "paint_hair.jpg"), label(edge[40:1060, 660:1820], "头发（青线是衣服的边）"),
            [cv2.IMWRITE_JPEG_QUALITY, 92])
cv2.imwrite(os.path.join(SHOW, "paint_tail.jpg"),
            label(cv2.resize(heat(tail_w)[640:1050, 1500:1860], None, fx=2, fy=2), "尾巴 ×2"), [cv2.IMWRITE_JPEG_QUALITY, 92])
print("rig_paint ->", OUT, "; sheets ->", SHOW, flush=True)
