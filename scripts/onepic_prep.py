"""一图流 PV 的素材准备：一张插画 -> Blender 里 2.5D 场景要用的各层。在 AutoDL 的 GPU 上跑：

    PYTHONPATH=/root/autodl-tmp/pv/pylib /root/autodl-tmp/ComfyUI/venv/bin/python onepic_prep.py <插画> <输出目录>
    ... onepic_prep.py layers <分层目录> <输出目录>     # 另外做好的分层（远/中/近/人物）接进来，见 import_layers()
    UPSCALER2=.../2x-AnimeSharpV4_RCAN.safetensors ... layers ...   # 同时把每层放大 2 倍
    UPSCALER2=... ... upscale <分层目录>/char.png <输出目录>/layer_char.png   # 单独放大一层，几层并行跑更快

借用 ComfyUI venv 的 torch / transformers / spandrel，pylib 里是 onnxruntime 和 OpenCV（onepic_setup.sh 装的）。
插画宽不到 2500 像素时先用 4x-AnimeSharp 放大；已经是 4K 的直接用。深度、抠图、补全在 1920 宽的工作分辨率上做，
结果再放回全分辨率。输出：
  color.png   全分辨率的插画（放大过的或原图）
  plate.png   去掉人物、LaMa 补全背后的背景；人物以外的像素和 color.png 一致
  alpha.png   人物的遮罩（ISNet 抠图，再用插画做导向滤波细化到全分辨率）；alpha.npy 是工作分辨率的
  disp.npy    Depth Anything V2 的相对视差（越大越近），0..1，工作分辨率
  disp_bg.npy 人物区域用周围补齐后的视差，给背景层用
  stars.png   天空里的星点：R = 亮度，G = 闪烁相位，B = 闪烁频率（Blender 里用 Closest 采样）
  sky.npy     天空的范围（按颜色判定，0..1），工作分辨率
  meta.json   尺寸；月亮的位置和半径、人物外框（都按 0..1 归一，左上为原点）；视差的分位数
  check.png   检查用的拼图
人物和背景的分层若另有更好的来源（比如 Qwen 补画的分层），Blender 那边可以替换 plate / alpha。
"""
import json
import os
import sys

import cv2
import numpy as np
import torch
import torch.nn.functional as F

PV = os.environ.get("PV", "/root/autodl-tmp/pv")
MODELS = os.path.join(PV, "models")
UPSCALER = os.environ.get("UPSCALER", "/root/autodl-tmp/ComfyUI/models/upscale_models/4x-AnimeSharp.pth")
WORK_W = 1920
DEV = "cuda"


def imread(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def imwrite(path, rgb):
    x = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    if x.ndim == 3:
        x = cv2.cvtColor(x, cv2.COLOR_RGB2BGR)
    cv2.imwrite(path, x)


def resize(x, w, h, interp=cv2.INTER_AREA):
    return cv2.resize(x, (w, h), interpolation=interp)


def to_t(img):
    return torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1)[None].to(DEV)


def from_t(t):
    return t[0].permute(1, 2, 0).float().cpu().numpy()


# ---------------------------------------------------------------- 放大

def upscale(img, tile=512, pad=24, scale=4, model_path=None):
    """放大模型（默认 4x-AnimeSharp），按块跑，块与块之间留 pad 像素重叠，避免接缝。"""
    from spandrel import ModelLoader
    model = ModelLoader().load_from_file(model_path or UPSCALER).model.to(DEV).eval().half()
    h, w, _ = img.shape
    s = scale
    out = np.zeros((h * s, w * s, 3), np.float32)
    x = to_t(img).half()
    with torch.no_grad():
        for y0 in range(0, h, tile):
            for x0 in range(0, w, tile):
                y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
                ya, xa = max(y0 - pad, 0), max(x0 - pad, 0)
                yb, xb = min(y1 + pad, h), min(x1 + pad, w)
                y = model(x[:, :, ya:yb, xa:xb]).clamp(0, 1)
                y = y[:, :, (y0 - ya) * s:(y0 - ya + y1 - y0) * s, (x0 - xa) * s:(x0 - xa + x1 - x0) * s]
                out[y0 * s:y1 * s, x0 * s:x1 * s] = from_t(y)
    del model
    torch.cuda.empty_cache()
    return out


# ---------------------------------------------------------------- 深度

def depth(img, height=924):
    """Depth Anything V2 Large 的相对视差，按输入尺寸返回，0..1（越大越近）。"""
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    d = os.path.join(MODELS, "depth-anything-v2-large")
    proc = AutoImageProcessor.from_pretrained(d)
    model = AutoModelForDepthEstimation.from_pretrained(d).to(DEV).eval()
    h, w, _ = img.shape
    hh = height // 14 * 14
    ww = int(round(w * hh / h / 14)) * 14
    x = resize(img, ww, hh, cv2.INTER_CUBIC)
    mean = np.array(proc.image_mean, np.float32)
    std = np.array(proc.image_std, np.float32)
    with torch.no_grad():
        pred = model(pixel_values=to_t((x - mean) / std).float()).predicted_depth
    pred = F.interpolate(pred[:, None], (h, w), mode="bicubic", align_corners=False)[0, 0].cpu().numpy()
    lo, hi = np.percentile(pred, 0.5), np.percentile(pred, 99.5)
    del model
    torch.cuda.empty_cache()
    return np.clip((pred - lo) / (hi - lo), 0, 1).astype(np.float32)


# ---------------------------------------------------------------- 抠图

def matte(img, s=1024):
    """skytnt/anime-segmentation 的 ISNet，按 anime-seg 的做法：等比缩到 s 见方，四周补零。"""
    import onnxruntime as ort
    sess = ort.InferenceSession(os.path.join(MODELS, "anime-seg", "isnetis.onnx"), providers=["CPUExecutionProvider"])
    h0, w0, _ = img.shape
    h, w = (s, int(s * w0 / h0)) if h0 > w0 else (int(s * h0 / w0), s)
    ph, pw = s - h, s - w
    x = np.zeros((s, s, 3), np.float32)
    x[ph // 2:ph // 2 + h, pw // 2:pw // 2 + w] = resize(img, w, h)
    pred = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0, 0]
    pred = pred[ph // 2:ph // 2 + h, pw // 2:pw // 2 + w]
    return np.clip(resize(pred, w0, h0, cv2.INTER_CUBIC), 0, 1)


def guided(I, p, r, eps):
    """导向滤波（He et al.）：I 是 (H,W,3) 的导向图，p 是 (H,W) 的待细化遮罩，都是 GPU 上的张量。"""
    def box(x):
        return F.avg_pool2d(x, 2 * r + 1, stride=1, padding=r, count_include_pad=False)
    I = I.permute(2, 0, 1)[None]
    p = p[None, None]
    mI, mp = box(I), box(p)
    cov = box(I * p) - mI * mp
    var = box((I[:, :, None] * I[:, None]).flatten(1, 2)) - (mI[:, :, None] * mI[:, None]).flatten(1, 2)
    var = var.view(1, 3, 3, *I.shape[2:]).permute(0, 3, 4, 1, 2) + eps * torch.eye(3, device=I.device)
    a = torch.linalg.solve(var, cov.permute(0, 2, 3, 1)[..., None])[..., 0].permute(0, 3, 1, 2)
    b = mp - (a * mI).sum(1, keepdim=True)
    return ((box(a) * I).sum(1, keepdim=True) + box(b))[0, 0]


def refine_full(alpha, full):
    """工作分辨率的遮罩 -> 全分辨率，用插画做导向，让发丝边缘贴住线稿。"""
    H, W, _ = full.shape
    a = resize(alpha, W, H, cv2.INTER_CUBIC)
    out = guided(torch.from_numpy(full).to(DEV), torch.from_numpy(a).to(DEV), r=8, eps=1e-3).clamp(0, 1).cpu().numpy()
    return np.where(a > 0.98, 1.0, np.where(a < 0.02, 0.0, out)).astype(np.float32)


# ---------------------------------------------------------------- 补全

def lama(img, mask):
    """big-lama（TorchScript）。mask 为 1 的地方重画。尺寸补到 8 的倍数。"""
    model = torch.jit.load(os.path.join(MODELS, "big-lama.pt"), map_location=DEV).eval()
    h, w, _ = img.shape
    H, W = (h + 7) // 8 * 8, (w + 7) // 8 * 8
    x = np.pad(img, ((0, H - h), (0, W - w), (0, 0)), mode="reflect")
    m = np.pad(mask, ((0, H - h), (0, W - w)), mode="reflect")
    with torch.no_grad():
        y = model(to_t(x).float(), torch.from_numpy(m)[None, None].float().to(DEV))
    del model
    torch.cuda.empty_cache()
    return np.clip(from_t(y)[:h, :w], 0, 1)


# ---------------------------------------------------------------- 星星、月亮

def sky_mask(img, alpha):
    """天空 = 大范围平均亮度低的深色区域（花田整片发亮，星星和银河的细线被大窗口平均掉）。深度在这里靠不住：
    Depth Anything 把远处花田估得和天空一样远。"""
    L = img.mean(axis=2)
    k = max(3, img.shape[1] // 64) | 1
    sky = (cv2.blur(L, (k, k)) < 0.33).astype(np.float32)
    sky = cv2.morphologyEx(sky, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    sky = cv2.GaussianBlur(sky, (0, 0), k / 4)
    return sky * (1 - np.clip(alpha * 3, 0, 1))


def find_moon(img):
    """画面上半部分最大、最圆的一块高亮就是月亮；返回 (cx, cy, r)（工作分辨率像素）。"""
    h = img.shape[0]
    m = (img.mean(axis=2) > 0.75).astype(np.uint8)
    m[h // 2:] = 0
    n, _, stats, cent = cv2.connectedComponentsWithStats(m)
    best, score = None, 0
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        r = max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) / 2
        round_ = area / (np.pi * r * r + 1e-6)          # 正圆约 1，细长的银河、花瓣小得多
        if round_ > 0.6 and area * round_ > score:
            best, score = (float(cent[i][0]), float(cent[i][1]), float(np.sqrt(area / np.pi))), area * round_
    return best


def star_map(img, sky, moon, seed=7, k=7):
    """白顶帽找出小亮点，每颗星一个随机相位和频率。"""
    L = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    th = cv2.morphologyEx(L, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    amp = np.clip((th - 0.05) / 0.35, 0, 1) * sky
    if moon:
        yy, xx = np.mgrid[:img.shape[0], :img.shape[1]]
        amp[(xx - moon[0]) ** 2 + (yy - moon[1]) ** 2 < (moon[2] * 1.6) ** 2] = 0
    n, lab = cv2.connectedComponents((amp > 0.05).astype(np.uint8))
    rng = np.random.default_rng(seed)
    phase = rng.random(n).astype(np.float32)
    freq = rng.uniform(0.15, 1.0, n).astype(np.float32)
    phase[0] = freq[0] = 0
    return amp, phase[lab], freq[lab], n - 1


def read_depth(path, w, h):
    """16 位的深度图（前面白）或 .npy -> 工作分辨率的 0..1 浮点。"""
    if path.endswith(".npy"):
        d = np.load(path).astype(np.float32)
    else:
        d = cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(np.float32)
        d = (d[..., 0] if d.ndim == 3 else d) / (65535.0 if d.max() > 255 else 255.0)
    return resize(d, w, h)


def bleed(rgb, a):
    """透明处的颜色换成附近不透明像素的颜色（push-pull：预乘颜色和 alpha 逐级缩小，再逐级放大补进覆盖不足的地方），
    放大和贴图过滤时边缘才不会混进黑色。"""
    levels = []
    c, w = rgb * a[..., None], a.copy()
    while min(w.shape) > 4:
        levels.append((c, w))
        size = (max(w.shape[1] // 2, 1), max(w.shape[0] // 2, 1))
        c, w = cv2.resize(c, size, interpolation=cv2.INTER_AREA), cv2.resize(w, size, interpolation=cv2.INTER_AREA)
    fill = c / np.maximum(w, 1e-6)[..., None]
    for c, w in reversed(levels):
        up = cv2.resize(fill, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR)
        k = np.clip(w * 4, 0, 1)[..., None]
        fill = c / np.maximum(w, 1e-6)[..., None] * k + up * (1 - k)
    k = np.clip(a * 4, 0, 1)[..., None]
    return rgb * k + fill * (1 - k)


def upscale_layer(path, dst, model):
    """一层 2 倍放大：RGB 走放大模型（透明处先 bleed），alpha 用三次插值。"""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    rgb = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    a = img[..., 3].astype(np.float32) / 255 if img.shape[2] == 4 else None
    if a is not None:
        rgb = bleed(rgb, a)
    up = upscale(rgb, scale=2, model_path=model)
    out = (np.clip(up, 0, 1) * 255 + 0.5).astype(np.uint8)
    out = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    if a is not None:
        aa = resize(a, up.shape[1], up.shape[0], cv2.INTER_CUBIC)
        out = np.dstack([out, (np.clip(aa, 0, 1) * 255 + 0.5).astype(np.uint8)])
    cv2.imwrite(dst, out)


def import_layers(src, out, up_model=None):
    """把别处做好的分层（layers.json：从后往前，每层 file / depth_file / bbox，加 depth.npy）接进来：
    每层的视差存成工作分辨率的 <名字>_disp.npy，人物（char）的遮罩存成 alpha.npy，层的列表写进 meta.json 给 Blender。
    up_model 给了就把每层用它放大 2 倍（特写时贴图更清楚）。星点和天空范围按最后面那层重做（被挡住的地方重画过，
    星星的位置和原图不同）；月亮仍用原图找的。"""
    spec = json.load(open(os.path.join(src, "layers.json")))
    meta = json.load(open(os.path.join(out, "meta.json")))
    W, H = spec["size"]
    w, h = meta["work_w"], meta["work_h"]
    full = read_depth(os.path.join(src, "depth.npy"), w, h)
    layers = []
    for L in spec["layers"]:
        name = L["name"]
        img = cv2.imread(os.path.join(src, L["file"]), cv2.IMREAD_UNCHANGED)
        has_alpha = img.ndim == 3 and img.shape[2] == 4
        disp = read_depth(os.path.join(src, L["depth_file"]), w, h) if L.get("depth_file") else full
        np.save(os.path.join(out, f"{name}_disp.npy"), disp)
        if has_alpha:
            np.save(os.path.join(out, f"{name}_alpha.npy"), resize(img[..., 3].astype(np.float32) / 255, w, h))
        color = os.path.abspath(os.path.join(src, L["file"]))
        dst = os.path.abspath(os.path.join(out, f"layer_{name}.png"))
        if up_model and not (os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(color)):
            upscale_layer(color, dst, up_model)
            print("upscaled", name, flush=True)
        if os.path.exists(dst):      # 放大过的（这次或之前单独跑 upscale 做的）就用放大的
            color = dst
        x0, y0, x1, y1 = L["bbox"]
        layers.append({"name": name, "color": color, "alpha": "self" if has_alpha else None,
                       "disp": f"{name}_disp.npy", "box": [x0 / W, y0 / H, x1 / W, y1 / H]})
    char = np.load(os.path.join(out, "char_alpha.npy"))
    np.save(os.path.join(out, "alpha.npy"), char)
    np.save(os.path.join(out, "disp.npy"), full)
    # 背景（对焦、对准用）：人物以外取原图深度，人物身后取补全背景的深度
    plate = next((np.load(os.path.join(out, f"{n}_disp.npy")) for n in ("mid", "far")
                  if os.path.exists(os.path.join(out, f"{n}_disp.npy"))), full)
    np.save(os.path.join(out, "disp_bg.npy"), np.where(char > 0.5, plate, full).astype(np.float32))
    back = resize(imread(os.path.join(src, spec["layers"][0]["file"])), w, h)
    sky = sky_mask(back, np.zeros((h, w), np.float32))
    mw = meta["moon"]
    moon = (mw[0] * w, mw[1] * h, mw[2] * w) if mw else None
    amp, phase, freq, n_stars = star_map(back, sky, moon)
    imwrite(os.path.join(out, "stars.png"), np.dstack([resize(amp, W, H, cv2.INTER_CUBIC),
                                                       resize(phase, W, H, cv2.INTER_NEAREST),
                                                       resize(freq, W, H, cv2.INTER_NEAREST)]))
    np.save(os.path.join(out, "sky.npy"), sky.astype(np.float32))
    meta["stars"] = n_stars
    far = np.load(os.path.join(out, f"{spec['layers'][0]['name']}_disp.npy"))
    meta["girl_disp"] = float(np.median(full[char > 0.9]))
    meta["sky_disp"] = float(np.percentile(far[sky > 0.9], 90))
    meta["layers"] = layers
    meta["layers_from"] = os.path.abspath(src)
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
    print(json.dumps({k: meta[k] for k in ("girl_disp", "sky_disp")}), [L["name"] for L in layers], flush=True)


def rig(char_path, spec_path, out):
    """人物会动的部位 -> 工作分辨率的权重图 rig.npz（0..1），加 rig_check.png 检查图。部位的大致位置在 case 的 rig.json：
    hair          头发和丝带：按颜色（紫红、粉、浅蓝）取，离头中心越远权重越大（hair_reach 两个距离之间从 0 到 1）
    ear_l, ear_r  两只耳朵：框里的人物像素，从耳根（框底）到耳尖从 0 到 1
    tail, tail_s  尾巴：框里的紫色像素；tail_s 是沿尾巴从根（0）到尖（1）的位置，按绕拱心的角度算
    dress         裙摆：白色、在 dress 的 v 范围里，越往下越大
    mouth         嘴：以嘴为中心的圆形衰减（嘴的位置按颜色在给定位置附近修正）
    breath        呼吸（rig.json 有 breath 才有）：v 是下巴、肩线、胸口、腰四条线，肩线到胸口为 1，往上到下巴降到
                  head（默认 0.15，头几乎不动，脖子吸收这点差），往下到腰降到 0；u 是身体连袖子的左右范围，往外
                  0.06 内放开到 0；尾巴不动
    皮肤、话筒、话筒线、颈带附近（加上 rigid 折线画的一条带子），头发、裙摆、嘴的权重都压到 0；
    sleeves 的多边形里头发也是 0；距离都以画面高为单位。
    最后 solidify() 把人物内部半透明的地方补满（translucent 的框里不动）。"""
    spec = json.load(open(spec_path, encoding="utf-8"))
    meta = json.load(open(os.path.join(out, "meta.json")))
    w, h = meta["work_w"], meta["work_h"]
    img = cv2.resize(cv2.imread(char_path, cv2.IMREAD_UNCHANGED), (w, h), interpolation=cv2.INTER_AREA)
    alpha = img[..., 3].astype(np.float32) / 255
    hsv = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV).astype(np.float32)
    H, S, V = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    U, Y = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    asp = w / h

    def dist(p):
        return np.hypot((U - p[0]) * asp, Y - p[1])

    def smooth(x, s):
        return cv2.GaussianBlur(x.astype(np.float32), (0, 0), s)

    def ramp(x, lo, hi):
        t = np.clip((x - lo) / (hi - lo), 0, 1)
        return t * t * (3 - 2 * t)

    def box(b):
        return (U >= b[0]) & (U <= b[2]) & (Y >= b[1]) & (Y <= b[3])

    solid = alpha > 0.5
    skin = (H > 5) & (H < 45) & (S > 0.08) & (S < 0.55) & (V > 0.55) & solid
    dark = (V < 0.3) & (S < 0.35) & solid
    k = np.ones((15, 15), np.uint8)
    rigid = smooth(cv2.dilate((skin | dark).astype(np.uint8), k), 4)
    # rig.json 的 rigid 折线（话筒、话筒线：插画坐标，width 是半宽，画面高为单位）：线到下面变细变浅，按颜色抓不全
    hard = np.zeros((h, w), np.uint8)
    for line in spec.get("rigid", []):
        pts = np.round(np.array(line["line"]) * (w, h)).astype(np.int32)
        cv2.polylines(hard, [pts], False, 1, thickness=max(1, int(round(2 * line["width"] * h))))
    hard = smooth(hard, 3)
    rigid = np.maximum(rigid, hard)
    skin_d = smooth(cv2.dilate(skin.astype(np.uint8), k), 4)
    # 头发是饱和的紫红；裙子的阴影也带淡紫，但饱和度低，归到裙摆
    hairc = ((H > 255) | (H < 12)) & (S > 0.34) & (V > 0.12) & solid
    ribbon = (H > 185) & (H < 235) & (S > 0.2) & solid

    T = spec["tail"]
    tail_m = box(T["box"]) & hairc
    n, lab, stats, _ = cv2.connectedComponentsWithStats(tail_m.astype(np.uint8))
    if n > 1:
        tail_m = lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    tail = smooth(tail_m, 3)
    cx, cy = T["center"]

    def angle(u, v):
        a = np.degrees(np.arctan2(-(v - cy), (u - cx) * asp))
        return np.where(a > -90, a, a + 360)
    a0, a1 = angle(*T["base"]), angle(*T["tip"])
    tail_s = np.clip((a0 - angle(U, Y)) / (a0 - a1), 0, 1)

    away = 1 - smooth(box(T["box"]), 6)
    ears = []
    for b in spec["ears"]:
        ears.append(smooth(box(b) & solid, 2) * ramp((b[3] - Y) / (b[3] - b[1]), 0, 1))
        away *= 1 - smooth(box(b), 4)
    # 裙子正中那一竖条的下半部只算裙摆：长发垂在两侧，裙子上偏粉的反光不能当成头发
    d0, d1 = spec["dress"]
    c0, c1 = spec["dress_u"]
    center = smooth((U > c0) & (U < c1) & (Y > d0 - 0.12), 8)
    lo, hi = spec["hair_reach"]
    hair = smooth(hairc | ribbon, 3) * ramp(dist(spec["head"]), lo, hi) * away * (1 - center)
    hair = smooth(hair * (1 - rigid), 4) * (1 - rigid)     # 模糊会把权重渗回手上，再乘一次
    # 袖子：半透明的袖子后面透出头发，按颜色分不开，按 rig.json 画的多边形整块压到 0；
    # 出了袖子按距离慢慢放开，贴着袖子的发丝不会被挤成一道折痕
    still = np.ones((h, w), np.uint8)
    for poly in spec.get("sleeves", []):
        cv2.fillPoly(still, [np.round(np.array(poly) * (w, h)).astype(np.int32)], 0)
    hair *= ramp(cv2.distanceTransform(still, cv2.DIST_L2, 5) / h, 0.002, 0.025)
    side_hair = smooth(hairc, 3) * (1 - center)
    # 裙摆：话筒线垂在裙子上，跟着摆会弯，和手一样不动
    dress = smooth(solid, 4) * ramp(Y, d0, d1) * (1 - rigid) * (1 - side_hair) * (1 - smooth(box(T["box"]), 6))
    # 呼吸：按位置的平滑权重，不按颜色——肩膀抬起时手、话筒、搭在肩上的头发一起走
    breath = np.zeros((h, w), np.float32)
    if "breath" in spec:
        B = spec["breath"]
        chin, sh, chest, waist = B["v"]
        k0 = B.get("head", 0.15)
        prof = np.where(Y < sh, k0 + (1 - k0) * ramp(Y, chin, sh), 1 - ramp(Y, chest, waist))
        b0, b1 = B["u"]
        breath = (prof * ramp(U, b0 - 0.06, b0) * (1 - ramp(U, b1, b1 + 0.06))
                  * (1 - smooth(box(T["box"]), 6))).astype(np.float32)

    mu, mv, mr = spec["mouth"]
    inside = ((H < 15) | (H > 330)) & (S > 0.3) & (V > 0.35) & (V < 0.92) & (dist((mu, mv)) < mr * 0.6) & solid
    n, lab, stats, cent = cv2.connectedComponentsWithStats(inside.astype(np.uint8))
    if n > 1:
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mu, mv = cent[i][0] / w, cent[i][1] / h
    # 话筒头就在下巴边上，不能跟着嘴伸缩；只排除连成大块的深色（话筒、线、颈带），嘴里零星的暗处照常跟着动
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8))
    big = np.isin(lab, 1 + np.nonzero(stats[1:, cv2.CC_STAT_AREA] >= 300)[0])
    mouth = (1 - ramp(dist((mu, mv)), mr * 0.45, mr)) * (1 - smooth(cv2.dilate(big.astype(np.uint8), np.ones((5, 5), np.uint8)), 2)) \
        * (1 - hard)

    np.savez_compressed(os.path.join(out, "rig.npz"), hair=hair, ear_l=ears[0], ear_r=ears[1], tail=tail,
                        tail_s=tail_s.astype(np.float32), dress=dress, mouth=mouth.astype(np.float32), breath=breath)
    info = {"mouth": [mu, mv], "tail_base": T["base"], "head": spec["head"]}
    json.dump(info, open(os.path.join(out, "rig.json"), "w"), indent=1)
    print("rig", json.dumps(info), flush=True)
    solidify(out, spec.get("translucent", []))

    base = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255 * alpha[..., None] * 0.6
    colors = [(hair, (1, 0.2, 0.2)), (ears[0] + ears[1], (0.2, 1, 0.2)), (tail * (0.3 + 0.7 * tail_s), (0.3, 0.5, 1)),
              (dress, (1, 1, 0.2)), (mouth, (0.2, 1, 1))]
    for m, c in colors:
        base = base * (1 - m[..., None] * 0.7) + m[..., None] * 0.7 * np.array(c, np.float32)
    imwrite(os.path.join(out, "rig_check.png"), base)


def solidify(out, keep):
    """人物层内部的 alpha 补满，写成 layer_char_solid.png，meta.json 里人物层改用它。分层时抠出来的人物，
    尾巴、几缕头发是半透明的，渲染时后面的花会透出来，看着像糊了。离边缘约画面宽 0.16% 以内（抗锯齿的边、
    细发丝）不动；keep 是本来就该透的地方（插画坐标的框，比如透出花的裙边），也不动。"""
    mpath = os.path.join(out, "meta.json")
    meta = json.load(open(mpath))
    L = next(x for x in meta["layers"] if x["name"] == "char")
    src = L.get("color_src", L["color"])
    img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    a = img[..., 3].astype(np.float32) / 255
    H, W = a.shape
    r = max(2, round(W * 0.0016))
    core = cv2.erode((a > 0.25).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
    core = cv2.GaussianBlur(core.astype(np.float32), (0, 0), r / 2)
    still = np.zeros((H, W), np.float32)
    for b in keep:
        still[int(b[1] * H):int(b[3] * H), int(b[0] * W):int(b[2] * W)] = 1
    core *= 1 - cv2.GaussianBlur(still, (0, 0), 4 * r)
    a2 = np.maximum(a, core)
    print(f"solidify: alpha raised on {(a2 - a > 0.05).mean() * 100:.2f}% of the layer", flush=True)
    img[..., 3] = (a2 * 255 + 0.5).astype(np.uint8)
    dst = os.path.join(out, "layer_char_solid.png")
    cv2.imwrite(dst, img)
    L["color_src"], L["color"] = src, os.path.abspath(dst)
    json.dump(meta, open(mpath, "w"), indent=1)


def main():
    if sys.argv[1] == "rig":        # rig <人物层 png> <case 的 rig.json> <输出目录>
        rig(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    if sys.argv[1] == "layers":
        import_layers(sys.argv[2], sys.argv[3], os.environ.get("UPSCALER2"))
        return
    if sys.argv[1] == "upscale":     # 单独放大一层（几层可以并行跑），import_layers 会直接用放大好的
        upscale_layer(sys.argv[2], sys.argv[3], os.environ["UPSCALER2"])
        return
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    full = imread(src)
    if full.shape[1] < 2500:
        full = upscale(full)
        print("upscaled", flush=True)
    H, W, _ = full.shape
    w, h = WORK_W, int(round(WORK_W * H / W))
    img = resize(full, w, h)
    imwrite(os.path.join(out, "color.png"), full)
    print(f"{src}: {W}x{H}, work {w}x{h}", flush=True)

    disp = depth(img)
    np.save(os.path.join(out, "disp.npy"), disp)
    print("depth done", flush=True)

    alpha = matte(img)
    n, lab, stats, _ = cv2.connectedComponentsWithStats((alpha > 0.5).astype(np.uint8))
    if n > 1:   # 只留最大的一块：零星的误检（花瓣、亮星）不算人物
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        alpha = alpha * cv2.dilate((lab == keep).astype(np.uint8), np.ones((9, 9), np.uint8))
    imwrite(os.path.join(out, "alpha.png"), refine_full(alpha, full))
    np.save(os.path.join(out, "alpha.npy"), alpha.astype(np.float32))
    print("matte done", flush=True)

    # 补背景：遮罩外扩一圈，连同发丝的半透明边一起重画
    hole = cv2.dilate((alpha > 0.05).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    plate = lama(img, hole.astype(np.float32))
    keep = resize(cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 3), W, H, cv2.INTER_LINEAR)[..., None]
    imwrite(os.path.join(out, "plate.png"), full * (1 - keep) + resize(plate, W, H, cv2.INTER_CUBIC) * keep)
    # 背景层的视差：人物区域用周围（花田、天空）补齐
    small = resize(disp, w // 2, h // 2)
    hs = resize(hole, w // 2, h // 2, cv2.INTER_NEAREST)
    fill = cv2.inpaint((small * 65535).astype(np.uint16), hs, 15, cv2.INPAINT_TELEA).astype(np.float32) / 65535
    disp_bg = np.where(hole > 0, resize(fill, w, h, cv2.INTER_CUBIC), disp).astype(np.float32)
    np.save(os.path.join(out, "disp_bg.npy"), disp_bg)
    print("plate done", flush=True)

    girl_disp = float(np.median(disp[alpha > 0.9]))
    sky = sky_mask(img, alpha)
    sky_disp = float(np.percentile(disp_bg[sky > 0.9], 90))
    moon = find_moon(img)
    amp, phase, freq, n_stars = star_map(img, sky, moon)
    np.save(os.path.join(out, "sky.npy"), sky.astype(np.float32))
    stars = np.dstack([resize(amp, W, H, cv2.INTER_CUBIC), resize(phase, W, H, cv2.INTER_NEAREST),
                       resize(freq, W, H, cv2.INTER_NEAREST)])
    imwrite(os.path.join(out, "stars.png"), stars)

    ys, xs = np.where(alpha > 0.5)
    meta = {"w": W, "h": H, "work_w": w, "work_h": h, "stars": n_stars,
            "moon": [moon[0] / w, moon[1] / h, moon[2] / w] if moon else None,
            "girl_bbox": [xs.min() / w, ys.min() / h, xs.max() / w, ys.max() / h],
            "girl_disp": girl_disp, "sky_disp": sky_disp,
            "disp_pct": {p: float(np.percentile(disp_bg, p)) for p in (1, 5, 25, 50, 75, 95, 99)}}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
    print(json.dumps(meta), flush=True)

    def tile(x):
        x = resize(x, w // 2, h // 2)
        return np.dstack([x] * 3) if x.ndim == 2 else x
    row1 = np.hstack([tile(img), tile(disp), tile(alpha)])
    marks = np.clip(amp * 3, 0, 1)
    marks = np.dstack([marks, marks, np.maximum(marks, sky * 0.35)])     # 星点白色，天空范围淡蓝
    if moon:
        cv2.circle(marks, (int(moon[0]), int(moon[1])), int(moon[2] * 1.3), (1.0, 0.3, 0.3), 3)
    row2 = np.hstack([tile(plate), tile(disp_bg), tile(marks)])
    imwrite(os.path.join(out, "check.png"), np.vstack([row1, row2]))
    print("== prep done", flush=True)


if __name__ == "__main__":
    main()
