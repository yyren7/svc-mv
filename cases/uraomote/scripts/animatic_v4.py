"""v4 picture animatic: script_v4.md section 5 cut on the song's downbeats, before the hall exists in 3D. 2D shots
show their illustration from round 2; 3D shots show a stand-in (her prints hanging in a row over black water with a
sky behind, the hall's first stills, or a glow on black) and are tagged 3D. Every frame names its section, its shot
and the bar, and carries the sung line, so the pacing can be judged against the script.

    python cases/uraomote/scripts/animatic_v4.py <frames_dir> [first_bar last_bar]      env: FPS=12 WIDTH=1280 STEP=1
    python cases/uraomote/scripts/animatic_cut.py <frames_dir> cases/uraomote/audio/urao_mix.m4a <out.mp4> 12

Needs PIL (on the server, ComfyUI's venv). The pictures are art/v4's, PICK says which seed stands for each, and a
picture not drawn yet (A6, Q2, U3, R1-R6) is a stand-in marked as such. STEP=12 draws one frame a second, for a
quick look. The lines come from audio/urao_lyrics.json, the cover's speech recognition, mistakes and all.
"""
import bisect
import json
import math
import os
import random
import sys
from collections import namedtuple
from multiprocessing import Pool

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import case as C  # noqa: E402

FPS = int(os.environ.get("FPS", 12))
W = int(os.environ.get("WIDTH", 1280))
H = W * 9 // 16
STEP = int(os.environ.get("STEP", 1))
TIMING = json.load(open(os.path.join(C.AUDIO, "urao_timing.json"), encoding="utf-8"))
DOWN, BEATS, DURATION = TIMING["downbeats"], TIMING["beats"], TIMING["duration"]
LYRICS = os.path.join(C.AUDIO, "urao_lyrics.json")
SUNG = json.load(open(LYRICS, encoding="utf-8"))["segments"] if os.path.exists(LYRICS) else []
ART = os.path.join(C.CASE, "art", "v4")
HALL = os.path.join(C.RENDERS, "v4_hall")
FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/msyh.ttc"]

SEED = 211                                           # every picture not picked yet stands in with this seed
PICK = {"kv": "v4_kv_211", "kvu": "v4_kvu_211_n75"}
INK, PAPER, MORNING, ROSE = (14, 13, 18), (242, 240, 235), (188, 211, 230), (240, 40, 90)
SHEET = 2.4 / 4.2                                    # a print's width over its height (v4_hall.py)
A = ["a1", "a2", "a3", "a4"]                         # her 表 mornings
URA = ["u1", "c2", "w2", "u2", "c4"]                 # 裏 pictures, for the backs of the prints
SECTIONS = {"P0": "前奏「表紙」", "P1": "主歌 1「目覚め」", "P2": "riff「ヒビ」", "P3": "导歌 1「自問自答」",
            "P4": "副歌 1「侵」", "P5": "副歌 1 后段「溢れ」", "P6": "间奏「雨」", "P7": "主歌 2「裏返り」",
            "P8": "导歌 2「乱反射」", "P9": "副歌 2「あっち」", "P10": "终段「表裏一体」", "P11": "尾「裏表紙」"}
PUNCH = [(35, 47), (51, 55), (87, 116)]              # bars with the impact push on every beat
DUTCH = (87, 99)                                     # bars with the Dutch angle, ±12° turning each bar

_cache = {}


# ---------------------------------------------------------------- the song's clock (as in animatic.py)

def at(bar):
    """Seconds at a bar (a downbeat index; fractions fall between downbeats, bars below 0 in the pickup)."""
    i = max(0, min(math.floor(bar), len(DOWN) - 2))
    return max(0.0, DOWN[i] + (bar - i) * (DOWN[i + 1] - DOWN[i]))


def bar_at(t):
    i = max(0, min(bisect.bisect_right(DOWN, t) - 1, len(DOWN) - 2))
    return i + (t - DOWN[i]) / (DOWN[i + 1] - DOWN[i])


def since_bar(b):
    """Seconds since the downbeat of the bar `b` is in."""
    return at(b) - at(math.floor(b))


def punch(t, amount, decay=0.12):
    i = bisect.bisect_right(BEATS, t) - 1
    return amount * math.exp(-(t - BEATS[i]) / decay) if i >= 0 else 0.0


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- pictures

def memo(name, make):
    if name not in _cache:
        _cache[name] = make()
    return _cache[name]


def pic(key):
    """An illustration by its name in the script (kv, kvu for KV', a1, c3, s2 ...) or a hall still (hall_*)."""
    def load():
        if key.startswith("hall_"):
            path = os.path.join(HALL, key + ".png")
        else:
            path = os.path.join(ART, PICK.get(key, f"v4_{key}_{SEED}") + "_00001_.png")
        return Image.open(path).convert("RGB")
    return memo(key, load)


def font(size):
    def load():
        path = next(p for p in FONTS if os.path.exists(p))
        return ImageFont.truetype(path, size, index=2 if "Noto" in path else 0)   # 2: the SC face of the .ttc
    return memo(("font", size), load)


def blank(rgb=INK):
    return Image.new("RGB", (W, H), rgb)


def cover(im, zoom=1.0, cx=0.5, cy=0.5):
    """`im` (or a picture's name) filling the frame, `zoom` times closer, centred as near (cx, cy) of it as its edges
    allow."""
    if isinstance(im, str):
        im = pic(im)
    s = max(W / im.width, H / im.height) * max(zoom, 1.0)
    cw, ch = W / s, H / s
    x0 = min(max(cx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(cy * im.height - ch / 2, 0), im.height - ch)
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def poster(im, height=0.86):
    """A picture as a sheet in the dark, on a 16:9 card at the picture's own resolution, so cover() can push in."""
    if isinstance(im, str):
        im = pic(im)
    ch = int(im.height / height)
    card = Image.new("RGB", (max(ch * 16 // 9, im.width), ch), INK)
    card.paste(im, ((card.width - im.width) // 2, (ch - im.height) // 2))
    return card


def sheet_of(key):
    """The middle of a picture at the prints' aspect, as v4_hall.py hangs it; tall pictures as they are."""
    def make():
        im = pic(key)
        w = im.height * SHEET
        if w >= im.width:
            return im
        x = (im.width - w) / 2
        return im.crop((int(x), 0, int(x + w), im.height))
    return memo("sheet_" + key, make)


def show_through(front, back, a):
    """Light from behind the sheet: the back's picture (printed mirrored, so from the front it reads the right way
    round) multiplies into the front's, warmed by the rose lamp behind."""
    lit = ImageChops.multiply(front, back.resize(front.size))
    lit = ImageChops.screen(lit, Image.new("RGB", front.size, tuple(int(c * 0.35) for c in ROSE)))
    return Image.blend(front, ImageEnhance.Brightness(lit).enhance(1.6), min(1.0, a))


def tint(im, rgb, a):
    return Image.blend(im, ImageChops.multiply(im, Image.new("RGB", im.size, rgb)), min(1.0, a)) if a > 0 else im


def lineart(im):
    """D4: the frame as its own line drawing, dark lines on paper."""
    g = im.convert("L").filter(ImageFilter.GaussianBlur(1)).filter(ImageFilter.FIND_EDGES)
    g = g.point(lambda v: 255 - min(255, v * 5))
    return Image.merge("RGB", (g, g, g))


def turn(im, s):
    """A sheet seen turning round its vertical axis: `s` is how much of its width faces the camera."""
    out, w = blank(), int(W * abs(s))
    if w > 1:
        out.paste(im.resize((w, H), Image.BILINEAR), ((W - w) // 2, 0))
    return out


def smear(im):
    """A whip pan's motion blur, sideways."""
    return im.resize((W // 24, H), Image.BILINEAR).resize((W, H), Image.BILINEAR)


def tear(im, d, behind=None):
    """D6: the frame torn down the middle, the halves `d` of the width apart, `behind` (or paper) in the gap."""
    out = behind.copy() if behind else blank(PAPER)
    dx = int(d * W / 2)
    out.paste(im.crop((0, 0, W // 2, H)), (-dx, 0))
    out.paste(im.crop((W // 2, 0, W, H)), (W // 2 + dx, 0))
    return out


def hang(f, im, height, cx=0.5, cy=0.5, squash=1.0):
    """Paste a sheet onto `f`, `height` of the frame high, centred at (cx, cy); `squash` as in turn()."""
    if isinstance(im, str):
        im = pic(im)
    h = int(H * height)
    w = int(h * im.width / im.height * abs(squash))
    if w > 1:
        f.paste(im.resize((w, h), Image.BILINEAR), (int(cx * W - w / 2), int(cy * H - h / 2)))
    return f


def stand(f, im, height, cx, top, water, squash=1.0):
    """Hang a print with its top at `top` and its reflection in the black water below the line `water`."""
    h = int(H * height)
    w = int(h * im.width / im.height * abs(squash))
    if w < 2:
        return
    im = im.resize((w, h), Image.BILINEAR)
    x, y, wy = int(cx * W - w / 2), int(top * H), int(water * H)
    f.paste(im, (x, y))
    f.paste(Image.blend(ImageOps.flip(im), Image.new("RGB", (w, h), INK), 0.72), (x, 2 * wy - y - h))


def row(keys, bg, shift, backs=None, through=0.0, height=0.5, top=0.1, dark=0.5, turning=None):
    """3D stand-in for the hall: prints of `keys` on a wire over black water, `bg` (a sky or a hall still) behind,
    slid along by `shift` print pitches. `backs` light through them by `through` (a number, or a function of the
    print's index); `turning` is (index, squash) for a print turning in the wind."""
    f = Image.blend(cover(bg, 1.15), blank(), dark)
    water = top + height + 0.04
    d = ImageDraw.Draw(f)
    d.rectangle([0, int(water * H), W, H], fill=INK)
    d.line([(0, int(top * H) - 3), (W, int(top * H) - 3)], fill=(70, 70, 78), width=1)
    pitch = height * SHEET * H / W * 1.5
    base = math.floor(shift)
    for j in range(-1, int(1 / pitch) + 2):
        i = base + j
        im = sheet_of(keys[i % len(keys)])
        a = through(i) if callable(through) else through
        if backs and a > 0:
            im = show_through(im, sheet_of(backs[i % len(backs)]), a)
        s = turning[1] if turning and i % len(keys) == turning[0] else 1.0
        stand(f, im, height, (j - (shift - base) + 0.5) * pitch, top, water, s)
    return f


# ---------------------------------------------------------------- what moves over the pictures

def over(im, draw):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(layer))
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def ink(im, cx, cy, r, a=1.0, rgb=ROSE):
    """A soft glowing cloud, rose ink unless `rgb` says otherwise, screened onto `im`."""
    if r < 1 or a <= 0:
        return im
    q = 4
    m = Image.new("L", (W // q, H // q), 0)
    ImageDraw.Draw(m).ellipse([(cx * W - r) / q, (cy * H - r) / q, (cx * W + r) / q, (cy * H + r) / q],
                              fill=int(255 * min(a, 1.0)))
    m = m.filter(ImageFilter.GaussianBlur(r / q * 0.4)).resize((W, H), Image.BILINEAR)
    return ImageChops.screen(im, Image.composite(blank(rgb), blank((0, 0, 0)), m))


def rings(im, t, starts, cx=0.5, cy=0.82, squash=0.22):
    """A pulse ripple on the water from each of `starts` in the last second (no hearts: script 0.3)."""
    def draw(d):
        for s in starts:
            age = t - s
            if 0 <= age < 1.0:
                r = W * (0.04 + 0.5 * age)
                d.ellipse([cx * W - r, cy * H - r * squash, cx * W + r, cy * H + r * squash],
                          outline=(255, 255, 255, int(170 * (1 - age))), width=2)
    return over(im, draw)


def rain(im, t, density=1.0, streaks=False):
    """D5: rain, scattered anew every frame; `streaks` turns it into 2D speed lines."""
    r = random.Random(int(t * FPS))

    def draw(d):
        for _ in range(int(220 * density)):
            x, y = r.uniform(0, W), r.uniform(-0.1 * H, H)
            ln = r.uniform(0.04, 0.09) * H * (4 if streaks else 1)
            d.line([(x, y), (x - ln * 0.08, y + ln)], fill=(255, 255, 255, 230 if streaks else 70),
                   width=3 if streaks else 1)
    return over(im, draw)


def crack(im, seed, grow=1.0, x=0.5, y=0.4, ang=None, rgb=ROSE):
    """A jagged crack from (x, y), `grow` of its length drawn."""
    r = random.Random(seed)
    a = r.uniform(0, 2 * math.pi) if ang is None else ang
    pts = [(x * W, y * H)]
    for _ in range(int(24 * min(grow, 1.0))):
        a += r.uniform(-0.7, 0.7) if ang is None else r.uniform(-0.35, 0.35)
        step = r.uniform(0.01, 0.03) * W
        pts.append((pts[-1][0] + step * math.cos(a), pts[-1][1] + step * math.sin(a)))
    return over(im, lambda d: d.line(pts, fill=rgb + (255,), width=max(2, W // 640))) if len(pts) > 1 else im


def glass(im, seed):
    """P8: the frame seen in a shard of glass, its edges as thin white lines."""
    r = random.Random(seed)

    def draw(d):
        for _ in range(7):
            d.line([(r.uniform(0, W), r.uniform(0, H)), (r.uniform(0, W), r.uniform(0, H))],
                   fill=(255, 255, 255, 110), width=2)
    return over(im, draw)


def confetti(im, t, n=80, swirl=0.0, fall=0.0, seed=7):
    """Torn paper (D5): white scraps round the middle turning by `swirl`, or dropping by `fall` frame heights."""
    r = random.Random(seed)

    def draw(d):
        for _ in range(n):
            a0, rad, size, spin = r.uniform(0, 2 * math.pi), r.uniform(0.1, 0.95), r.uniform(0.006, 0.02), r.uniform(-5, 5)
            a = a0 + swirl * t * (1.4 - rad)
            x = 0.5 * W + math.cos(a) * rad * 0.62 * W
            y = 0.5 * H + math.sin(a) * rad * 0.62 * H + fall * H * r.uniform(0.6, 1.4)
            q = spin * t
            pts = [(x + size * W * math.cos(q + k * math.pi / 2) * (1.6 if k % 2 else 1),
                    y + size * W * math.sin(q + k * math.pi / 2)) for k in range(4)]
            d.polygon(pts, fill=PAPER + (210,))
    return over(im, draw)


def missing(im, what, instead):
    """A picture the script needs that is not drawn yet: its stand-in, dimmed, with its name."""
    im = Image.blend(im, blank(), 0.45)
    d = ImageDraw.Draw(im)
    d.text((W / 2, H / 2), f"{what} 未画", font=font(H // 9), anchor="mm", fill=PAPER)
    d.text((W / 2, H / 2 + H // 9), f"暂用 {instead}", font=font(H // 28), anchor="mm", fill=PAPER)
    return im


# ---------------------------------------------------------------- the shots, script_v4.md section 5

def p0_paper(u, t, b):
    paper = memo("fibres", lambda: Image.effect_noise((W // 2, H // 2), 50).filter(ImageFilter.GaussianBlur(1))
                 .resize((W, H)).convert("RGB"))
    band = Image.new("L", (1, H))
    band.putdata([int(210 * math.exp(-((y / H - (1.4 * u - 0.2)) / 0.09) ** 2)) for y in range(H)])
    return Image.composite(tint(paper, MORNING, 0.5), blank(), band.resize((W, H)))


def p0_lights(u, t, b):
    level = (math.floor(b) + min(1.0, b % 1 * 6)) / 4         # one ceiling lamp a downbeat
    return Image.blend(blank(), cover(memo("kv_poster", lambda: poster("kv"))), min(1.0, max(0.0, level)))


def p0_through(u, t, b):
    return cover(poster(show_through(pic("kv"), pic("kvu"), 0.85 * ease(u))))


def p0_space(u, t, b):
    f = row(URA, "s2", 0.3 * u, dark=0.75)
    return hang(f, show_through(pic("kv"), pic("kvu"), 0.85), 0.8, 0.52 - 0.14 * u)


def p0_dive(u, t, b):
    f = cover(poster(show_through(pic("kv"), pic("kvu"), 0.85), 0.8), 1 + 14 * ease(u) ** 3, 0.42, 0.3)
    return Image.blend(f.filter(ImageFilter.GaussianBlur(8)), blank(PAPER), 0.3) if u > 0.8 else f


def p1_hall(u, t, b):
    s = 1 - 0.4 * math.sin(math.pi * min(1.0, b % 1 * 2))   # each downbeat one print turns a little in the wind
    return row(A, "s1", 1.5 * u, dark=0.3, turning=(math.floor(b) % 4, s))


def p1_eyes(u, t, b):
    return cover("a5", 1.05 + 0.05 * u) if b < 13 else missing(cover("q1", 1.1), "A6", "Q1")


def p1_drop(u, t, b):
    f = ink(blank(), 0.5, 0.45, H * 0.22, 0.25, MORNING)       # the glass on the sill, its caustics
    return ink(f, 0.5, 0.45 + 0.1 * ease(b - 15), H * (0.02 + 0.3 * ease(b - 15)), 0.9) if b >= 15 else f


def p1_seep(u, t, b):
    f = cover("q1", 1.05 + 0.06 * u)
    r = H * 0.5 * ease((b - 16) / 3)
    if r > 1:
        q = 4
        m = Image.new("L", (W // q, H // q), 0)
        ImageDraw.Draw(m).ellipse([(0.46 * W - r) / q, (0.55 * H - r) / q, (0.46 * W + r) / q, (0.55 * H + r) / q],
                                  fill=200)
        f = Image.composite(tint(f, ROSE, 0.75), f, m.filter(ImageFilter.GaussianBlur(r / q * 0.5)).resize((W, H)))
    if b >= 19:                                                 # the focus pulls past her; she blurs to white
        w = ease(b - 19)
        f = Image.blend(f.filter(ImageFilter.GaussianBlur(1 + 18 * w)), blank(PAPER), 0.7 * w)
    return f


def p1_top(u, t, b):
    f = ink(blank(), 0.55, 0.55, H * (0.2 + 0.25 * ease((b - 20) / 4)), 0.5)
    hang(f, sheet_of("q1").rotate(84, expand=True, fillcolor=INK), 0.62, 0.5, 0.5)
    f = rings(f, t, BEATS, 0.5, 0.5, 1.0)
    return crack(f, 23, ease((b - 23.75) * 4), 0.3, 0.42, ang=0.1) if b >= 23.75 else f


def p2_whip(u, t, b):
    k, v = math.floor(b) - 24, b % 1
    hall = lambda x: row(A, "s1", 2 * k + x, dark=0.3)
    first, second = (hall(v), cover(A[k], 1.1)) if k % 2 == 0 else (cover(A[k], 1.1), hall(v))
    f = first if v < 0.45 else smear(first if v < 0.5 else second) if v < 0.56 else second
    if 0.47 < v < 0.53:                                         # the paper's edge flying past the lens
        x = int(W * (v - 0.47) / 0.06)
        ImageDraw.Draw(f).rectangle([W - x - W // 30, 0, W - x, H], fill=PAPER)
    return crack(f, 24 + k, ease(v / 0.15), 0.3 + 0.12 * k, 0.35)


def p2_wind(u, t, b):
    lift = math.sin(math.pi * min(1.0, max(0.0, b - 28.5)))
    return row(A, "s1", 4 + u, backs=URA, through=0.9 * lift, top=0.1 - 0.05 * lift, dark=0.3)


def p2_out(u, t, b):
    f = row(A, "s1", 5 + 0.2 * u, dark=min(1.0, 0.3 + 0.7 * (math.floor(b % 1 * 4) + 1) / 4))
    for k in range(4):
        f = crack(f, 24 + k, 1.0, 0.3 + 0.12 * k, 0.35)
    return f


def q2():
    """Q2 is not drawn: Q1 mirrored, in the 裏 light."""
    return memo("q2", lambda: missing(ink(tint(ImageOps.mirror(cover("q1", 1.08)), (90, 70, 150), 0.8), 0.7, 0.3,
                                          H * 0.5, 0.6), "Q2", "Q1 镜像"))


def p3_turn(u, t, b):
    n = (b - 31) * 4 if b < 34 else 12 + (b - 34) * 8           # a side a beat, on bar 34 a side a half beat
    p = n % 1
    return turn(cover("q1", 1.08) if int(n) % 2 == 0 else q2(), min(1.0, p / 0.2, (1 - p) / 0.2))


def p4_chorus(u, t, b):
    k, v = math.floor(b) - 35, b % 1
    beat, p = int(v * 4), v * 4 % 1
    if beat == 3 and p < 0.5:                                   # half a beat of a chorus picture
        return cover(f"c{k % 4 + 1}", 1.05 + 0.05 * p)

    def lit(i):                                                 # from bar 41 the prints light up one by one
        return min(1.0, max(0.0, b - 41 - 0.7 * (i % 6)))
    cam = k % 5
    if cam == 1:                                                # straight down: the ink flowering in the water
        f = rings(ink(blank(), 0.5, 0.5, H * (0.08 + 0.45 * v), 0.9), t, [at(math.floor(b) + 0.25)], 0.5, 0.5, 1.0)
    elif cam == 2:                                              # round one print to its back
        f = row(A, "s2", 0.3 * v, backs=URA, through=lit, dark=0.7)
        s = math.cos(math.pi * ease(v))
        hang(f, sheet_of("a2") if s > 0 else ImageOps.mirror(sheet_of("u2")), 0.8, 0.5, 0.48, s)
    else:
        f = row(A, "s2", k + 1.2 * v, backs=URA, through=lit, dark=0.7)
        if cam == 3:                                            # through her silhouette cut in a print
            f = cover(f, 1 + 2.5 * v ** 2)
        if cam == 4:                                            # from under the water
            f = tint(ImageOps.flip(f), (70, 90, 160), 0.6)
    if beat == 0 and since_bar(b) < 2 / FPS:
        f = lineart(f)
    if beat == 1:
        f = rings(f, t, [at(math.floor(b) + 0.25)])
    if beat == 2:
        f = ink(f, 0.5, 0.8, H * (0.1 + 0.35 * p), 0.9 * (1 - p))
    return tint(f, ROSE, 0.5 * ease((b - 41) / 5))


def p5_spill(u, t, b):
    f = cover(memo("c1_poster", lambda: poster("c1", 0.62)), (1 / 0.62) ** (1 - ease(u)))
    return ink(f, 0.5, 1.0, H * 0.7 * u, 0.9 * u)


def p5_full(u, t, b):
    f = tint(row(A, "s2", 0.5 * u, backs=URA, through=1.0, dark=0.7), ROSE, 0.5)
    return ink(f, 0.5, 1.1, H * 0.9, 0.7)


def p5_vertigo(u, t, b):
    return hang(cover("hall_aisle_rose", 1.9 - 0.9 * ease(u)), "kv", 0.8)


def p5_cut(u, t, b):
    return blank((0, 0, 0))


def p6_rain(u, t, b):
    return rain(row(A, "s2", 0.4 * u, backs=URA, through=0.85 * ease(u), dark=0.4), t)


def w1_stage(im, s, t):
    f = Image.blend(cover("s2", 1.15), blank(), 0.6)
    ImageDraw.Draw(f).rectangle([0, int(0.86 * H), W, H], fill=INK)
    stand(f, im, 0.72, 0.5, 0.1, 0.86, s)
    return rain(f, t)


def blank_back():
    """The back of her cardboard: plain paper with a pencilled number."""
    def make():
        im = Image.blend(Image.new("RGB", sheet_of("w1").size, PAPER),
                         Image.effect_noise(sheet_of("w1").size, 30).convert("RGB"), 0.08)
        ImageDraw.Draw(im).text((im.width * 0.82, im.height * 0.94), "No. 17", font=font(40), anchor="rm",
                                fill=(120, 120, 128))
        return im
    return memo("blank_back", make)


def p6_w1(u, t, b):
    return w1_stage(sheet_of("w1"), 1.0, t)


def p6_w2(u, t, b):
    return rain(cover("w2", 1.05 + 0.08 * u), t, 0.5)


def p6_side(u, t, b):
    if b < 65:
        return w1_stage(sheet_of("w1"), math.cos(math.pi / 2 * ease(b - 64)), t)
    return w1_stage(blank_back(), math.sin(math.pi / 2 * ease((b - 65) * 1.5)), t)


def p6_lines(u, t, b):
    f = rain(row(A, "s2", 0.5 + 0.3 * u, backs=URA, through=0.85, dark=0.55), t, streaks=b < 67)
    return turn(f, math.cos(math.pi / 2 * ease((b - 67.75) * 4))) if b >= 67.75 else f


def p7_roll(u, t, b):
    return cover("hall_aisle_rose", 1.4).rotate(180 * ease(u), Image.BILINEAR)


def u3():
    """U3 is not drawn: two of her across the water line, 表 above (Q1) and 裏 upside down below (U2)."""
    def make():
        f = hang(blank(), sheet_of("q1"), 0.48, 0.5, 0.25)
        hang(f, Image.blend(ImageOps.flip(sheet_of("u2")), Image.new("RGB", sheet_of("u2").size, INK), 0.3),
             0.48, 0.5, 0.75)
        return missing(f, "U3", "Q1 + U2 倒影")
    return memo("u3", make)


URA_SEQ = [(70, "u1"), (72, "hall_front_rose"), (73, "u2"), (75, "hall_aisle_rose"), (76, "u4"), (77, "U3"), (78, None)]


def p7_ura(u, t, b):
    k = max(i for i, (bar, _) in enumerate(URA_SEQ[:-1]) if b >= bar)
    (bar, key), nxt = URA_SEQ[k], URA_SEQ[k + 1][0]
    if key == "U3":
        return u3()
    f = cover(key, 1.05 + 0.08 * (b - bar) / (nxt - bar))
    return f.rotate(180) if key.startswith("hall_") else f      # the hall is upside down now


def p7_reflect(u, t, b):
    f = hang(blank(), sheet_of("a2"), 0.46, 0.5, 0.25)
    below = ImageOps.flip(sheet_of("a2" if since_bar(b) < 2 / FPS else "u2"))   # once a bar it is 表 again
    return hang(f, Image.blend(below, Image.new("RGB", below.size, INK), 0.35), 0.46, 0.5, 0.75)


def p7_crack(u, t, b):
    f = cover("hall_aisle_rose", 1.2).rotate(180)
    for k in range(5):
        f = crack(f, 82 + k, ease(1.5 * u), 0.2 + 0.15 * k, 0.15 + 0.05 * (k % 2), rgb=(220, 230, 255))
    return f


SHARDS = ["a1", "q1", "c1", "w2", "u1", "u2", "c3", "f2"]


def p8_shards(u, t, b):
    if b >= 86.75:                                              # the shards line up into her silhouette
        return tint(cover(memo("kvu_poster", lambda: poster("kvu"))), ROSE, 0.6)
    n, q = int((b - 83) * 2), (b - 83) * 2 % 1
    f = cover(SHARDS[n % len(SHARDS)], 1.1 + 0.1 * q)
    return glass(lineart(f) if q < 0.25 else f, n)              # line art first, half a beat later the real thing


def p9_run(u, t, b):
    f = rings(tint(row(URA, "s2", b - 87, dark=0.6), ROSE, 0.3), t, BEATS, 0.5, 0.88)
    v = b % 1
    return tear(f, 0.3 * ease(v / 0.18)) if v < 0.18 else f     # she breaks through a print on every downbeat


def p9_r0(u, t, b):
    f = cover("r0", 1.0 + 0.3 * ease(u))
    return tear(f, ease(b - 96), cover("hall_aisle_rose", 1.1)) if b >= 96 else f


def p9_back(u, t, b):
    f = tint(row(URA, "s2", 0.3 * u, top=0.1 - 0.08 * ease(2 * u), dark=0.6), ROSE, 0.3)
    return hang(f, "kvu", 0.86)


def p10_walls(u, t, b):
    f = tear(tint(row(URA, "s2", 0.2 * u, dark=0.6), ROSE, 0.3), 1.1 * ease(u), cover("s3", 1.1 + 0.1 * u))
    return confetti(f, t, 60, swirl=0.4)


def p10_f1(u, t, b):
    return confetti(cover("f1", 1.2, cy=0.7 - 0.4 * u), t, 90, swirl=0.6 + 1.5 * u)


FAST = ["f1", "hall_front_rose", "c1", "hall_aisle_rose", "r0", "u2", "kv", "kvu", "w2", "s3", "c4", "a2"]


def p10_fast(u, t, b):
    n = int((b - 107) * 2) if b < 111 else 8 + int((b - 111) * 4)
    key = FAST[n % len(FAST)]
    f = cover(memo(key + "_poster", lambda: poster(key, 0.9)) if key in ("kv", "kvu") else key, 1.08)
    cold = int(b % 1 * 4) % 2 == 0                              # cold and rose light change places every beat
    return confetti(tint(f, MORNING if cold else ROSE, 0.45), t, 70, swirl=1.6)


def p10_f2(u, t, b):
    f = cover("f2", 1.05 + 0.05 * u)
    return confetti(f, t, 90, fall=ease((b - 115.75) * 4)) if b >= 115.75 else f


LAST_BEAT = DURATION - (BEATS[-1] - BEATS[-2])               # the beats found stop at bar 116; the song rings on


def p11_back(u, t, b):
    if t >= LAST_BEAT:                                          # the last beat: black, and a tiny rose page 0
        f = blank((0, 0, 0))
        ImageDraw.Draw(f).text((W / 2, H * 0.93), "0", font=font(H // 40), fill=ROSE, anchor="mm")
        return f
    f = cover(memo("kvu_back", lambda: poster(ImageOps.mirror(pic("kvu")))))
    out = math.floor((t - at(116)) / (LAST_BEAT - at(116)) * 6)  # the lamps behind the letters go out one by one
    return Image.blend(f, blank(), min(1.0, out / 6))


Shot = namedtuple("Shot", "bar sec title dim note fn")
SHOTS = [
    Shot(-2, "P0", "1 纸", "3D", "微距：纸边和纤维，冷光扫过", p0_paper),
    Shot(0, "P0", "2 亮起来", "3D", "每个重拍亮一盏顶灯，照出 KV（D1）", p0_lights),
    Shot(4, "P0", "3 透出来", "3D", "纸后亮起红光，KV' 透过来", p0_through),
    Shot(6, "P0", "4 原来有空间", "3D", "正交换成透视、横移，后面是大厅（暂用定帧和一排画）", p0_space),
    Shot(7, "P0", "5 穿窗", "3D", "急推进“表”字的镂空（字还没有）", p0_dive),
    Shot(8, "P1", "1 黎明的大厅", "3D", "贴水面滑过 A1–A4，窗外 S1，每个重拍一张画转一下", p1_hall),
    Shot(12, "P1", "2 睁眼", "2D", "A5 闭眼 → A6 睁眼", p1_eyes),
    Shot(14, "P1", "3 第一滴", "3D", "微距：窗台上的水杯，15 小节墨滴落下", p1_drop),
    Shot(16, "P1", "4 渗过来", "2D", "红从纸背渗进她的脸，最后焦点拉走", p1_seep),
    Shot(20, "P1", "5 正上方", "3D", "平躺在黑水上的画，墨渗出，每拍一圈涟漪", p1_top),
    Shot(23, "P1", "6 第一道裂", "3D", "最后一拍，红线划过她的脸", p1_top),
    Shot(24, "P2", "1 甩镜 · 2 裂", "2D+3D", "每小节甩进一张画再甩出，每个重拍一道裂", p2_whip),
    Shot(28, "P2", "3 风", "3D", "一整排画扬起，逆光里透出裏", p2_wind),
    Shot(30, "P2", "4 熄", "3D", "灯一拍一拍熄掉，只剩裂缝的红", p2_out),
    Shot(31, "P3", "绕着一张画转", "2D+3D", "Q1 / Q2 一拍一面，34 小节半拍一面，最后翻页", p3_turn),
    Shot(35, "P4", "每拍一次维度事件", "3D", "1 推+线稿 2 涟漪 3 墨 4 半拍 C1–C4；41 起逐张变红", p4_chorus),
    Shot(47, "P5", "1 溢出", "2D→3D", "C1 的墨流出纸边，倾进黑水", p5_spill),
    Shot(51, "P5", "2 满", "3D", "红水从下往上照亮每一张画", p5_full),
    Shot(55, "P5", "3 拉开", "3D", "对着 KV 的希区柯克变焦", p5_vertigo),
    Shot(56, "P5", "4 断", "—", "黑", p5_cut),
    Shot(57, "P6", "1 雨落在纸上", "3D", "湿纸变透明，透出裏，窗外 S2", p6_rain),
    Shot(61, "P6", "2 她在雨里", "3D", "水面上的背影纸板 W1", p6_w1),
    Shot(62.5, "P6", "2 她在雨里", "2D", "W2，眼角化开的红", p6_w2),
    Shot(64, "P6", "3 绕到侧面", "3D", "纸板转成一条线，背面是铅笔编号", p6_side),
    Shot(66, "P6", "4 雨变线", "2D+3D", "雨变速度线一小节，最后一拍翻页", p6_lines),
    Shot(68, "P7", "1 翻转", "3D", "镜头滚转 180°", p7_roll),
    Shot(70, "P7", "2 裏的她", "2D+3D", "U1、U2、U4、U3 和倒过来的大厅交替", p7_ura),
    Shot(78, "P7", "3 倒影是另一个人", "3D", "表的画，水里的倒影是裏；每小节闪回一次表", p7_reflect),
    Shot(82, "P7", "4 裂", "3D", "高窗玻璃爬开裂纹", p7_crack),
    Shot(83, "P8", "乱反射", "2D+3D", "碎玻璃里的她，半小节一切，先线稿后三维", p8_shards),
    Shot(87, "P9", "1 跑", "3D", "贴水面跟拍，撞穿一张张画（R1–R6 未画）", p9_run),
    Shot(93, "P9", "2 冲破画面", "2D", "R0 冲向镜头，画面从中间撕开", p9_r0),
    Shot(97, "P9", "3 回头", "2D", "两排画之间停下回头（暂用 KV'），身后的画扬起", p9_back),
    Shot(99, "P10", "第一遍：墙是纸", "3D", "墙撕开，外面是 S3", p10_walls),
    Shot(103, "P10", "第一遍：跃起", "2D", "F1，镜头跟着升起，碎纸旋涡", p10_f1),
    Shot(107, "P10", "第二遍", "2D+3D", "半小节一切，最后四小节每拍一切，冷光红光每拍互换", p10_fast),
    Shot(115, "P10", "F2", "2D", "最后一小节第一拍 F2，最后一拍碎纸落向水面", p10_f2),
    Shot(116, "P11", "裏表紙", "3D", "正上方，KV' 的背面，灯一盏盏熄灭，页码 0", p11_back),
]
STARTS = [at(s.bar) for s in SHOTS]


# ---------------------------------------------------------------- frames

def post(f, t, b):
    if any(a <= b < z for a, z in PUNCH):
        f = cover(f, 1 + punch(t, 0.03))
    if DUTCH[0] <= b < DUTCH[1]:
        f = cover(f, 1.36).rotate(12 if math.floor(b) % 2 else -12, Image.BILINEAR)
    return f


def label(f, t, b, shot):
    d = ImageDraw.Draw(f, "RGBA")
    big, small = font(H // 24), font(H // 34)
    head = f"{shot.sec} {SECTIONS[shot.sec]} · {shot.title}"
    x0, y0, x1, y1 = d.textbbox((W // 60, H // 40), head, font=big)
    d.rectangle([x0 - 8, y0 - 6, x1 + 8, y1 + 6], fill=(0, 0, 0, 150))
    d.text((W // 60, H // 40), head, font=big, fill=PAPER)
    tag = {"2D": PAPER, "3D": (120, 200, 255)}.get(shot.dim, (200, 200, 200))
    x0, y0, x1, y1 = d.textbbox((W - W // 60, H // 40), shot.dim, font=big, anchor="ra")
    d.rectangle([x0 - 8, y0 - 6, x1 + 8, y1 + 6], fill=(0, 0, 0, 150), outline=tag, width=2)
    d.text((W - W // 60, H // 40), shot.dim, font=big, fill=tag, anchor="ra")
    d.rectangle([0, H - H // 18, W, H], fill=(0, 0, 0, 170))
    d.text((W // 60, H - H // 36), shot.note, font=small, fill=(230, 230, 230), anchor="lm")
    bar = math.floor(b)
    d.text((W - W // 60, H - H // 36), f"小节 {bar} · {int(b % 1 * 4) + 1}   {int(t // 60)}:{t % 60:04.1f}",
           font=small, fill=(230, 230, 230), anchor="rm")
    line = next((s["text"].strip() for s in SUNG if s["start"] <= t < s["end"]), "")
    if line:
        d.text((W / 2, H - H // 18 - H // 30), line, font=small, fill=(255, 255, 255), anchor="ms",
               stroke_width=2, stroke_fill=(0, 0, 0))


def render(n):
    t = n / FPS
    k = bisect.bisect_right(STARTS, t) - 1
    shot = SHOTS[k]
    end = STARTS[k + 1] if k + 1 < len(SHOTS) else DURATION
    b = max(bar_at(t), shot.bar)                                # rounding can put a shot's first frame just before it
    f = post(shot.fn((t - STARTS[k]) / (end - STARTS[k]), t, b), t, b)
    label(f, t, b, shot)
    f.save(os.path.join(OUT, f"f_{n:05d}.png"), compress_level=1)


OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    first, last = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (-2, None)
    n0 = int(round(at(first) * FPS))
    n1 = int(round((at(last) if last is not None else DURATION) * FPS))
    frames = range(n0, n1, STEP)
    with Pool(min(32, os.cpu_count())) as pool:
        for k, _ in enumerate(pool.imap_unordered(render, frames, chunksize=8)):
            if k % 200 == 0:
                print(f"{k}/{len(frames)}", flush=True)
    print(OUT, len(frames), "frames")
