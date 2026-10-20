"""~15 s chorus sample: seven shots cut on downbeats, everything driven by the beat grid.

    blender -b -P scripts/sample.py -- assets/audio/urao_timing.json renders/sample/ [bars [first last [step]]]

Writes PNG frames f_0001.png ... and window.json (start / end seconds in the song) into the output folder.

The layouts sit on the z = 0 plane (16 x 9 units framed from z = 20) with their layers spread in depth,
and a perspective camera moves through every shot (dolly, truck, orbit, spiral push, crane, pull back)
with beat shakes and whip pans at the cuts, so the depth reads as parallax. The big graphic pieces never
stand still: bars stream, marquees scroll, rules extend on downbeats, dashed rings spin, halftone panels drift.
Motion that should feel hand-drawn (particles, slams, crystals) runs "on twos": 12 poses per second.
"""
import bisect
import json
import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mvlib as m  # noqa: E402

PAPER, INK, RED = "#EEEAE0", "#141414", "#E1251B"
NIGHT, PINK, CYAN, WHITE = "#0B0B10", "#FF2E88", "#00E5FF", "#F4F4F4"
FPS = 24
FOV = 43.6          # 16 units wide at distance 20
WHIP = 0.09         # seconds of whip pan on each side of a cut

argv = sys.argv[sys.argv.index("--") + 1:]
timing = json.load(open(argv[0], encoding="utf-8"))
OUT = argv[1]
BARS = int(argv[2]) if len(argv) > 2 else 10
BEATS = timing["beats"]
DOWN = timing["downbeats"]


def pick_window():
    """The run of BARS bars with the loudest mix (the chorus, usually)."""
    loud, lfps = timing["loud_mix"], timing["fps"]
    best, best_i = -1, 0
    for i in range(len(DOWN) - BARS):
        a, b = int(DOWN[i] * lfps), int(DOWN[i + BARS] * lfps)
        v = sum(loud[a:b]) / max(1, b - a)
        if v > best:
            best, best_i = v, i
    return best_i


D0 = pick_window()
BAR_T = DOWN[D0:D0 + BARS + 1]
T0, T1 = BAR_T[0], BAR_T[-1]
BEAT_LEN = (BAR_T[-1] - BAR_T[0]) / (BARS * 4)


# ---------------------------------------------------------------- timing helpers

def beat_phase(t):
    """(index of the last beat, seconds since it)."""
    i = bisect.bisect_right(BEATS, t) - 1
    return (i, t - BEATS[i]) if i >= 0 else (-1, 99.0)


def bar_phase(t):
    i = bisect.bisect_right(DOWN, t) - 1
    return (i, t - DOWN[i]) if i >= 0 else (-1, 99.0)


def twos(t):
    return math.floor(t * 12) / 12


def punch(phase, k=9.0):
    return math.exp(-max(phase, 0) * k)


def ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def ease_io(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u


def shake(t, amp):
    return (amp * (math.sin(t * 53.1) + math.sin(t * 31.7 + 1.3)) / 2,
            amp * (math.sin(t * 47.3 + 0.7) + math.sin(t * 27.1 + 2.1)) / 2)


def timecode(t):
    return f"00:{int(t // 60):02d}:{int(t % 60):02d}:{int((t % 1) * FPS):02d}"


def beats_in(t0, t1, every=1):
    return [b for b in BEATS if t0 - 1e-3 <= b < t1 - 1e-3][::every]


# ---------------------------------------------------------------- kinetic pieces

class Bursts:
    """Star bursts with soft halos from a pool of objects; one burst per trigger time."""

    def __init__(self, triggers, origin, colors, n=18, pool=3, speed=(6, 11), size=(0.12, 0.3),
                 life=0.6, halo=True, seed=1, z=4.0):
        rnd = random.Random(seed)
        self.triggers, self.origin, self.life, self.pool, self.n, self.z = triggers, origin, life, pool, n, z
        self.parts = []
        for _ in range(pool * n):
            c = rnd.choice(colors)
            s = m.star(c, z=z + rnd.random() * 0.3)
            h = m.disc(c, z=z - 0.1, mat=m.halo_mat(c)) if halo else None
            self.parts.append((s, h))
        self.params = [[(rnd.uniform(0, 2 * math.pi), rnd.uniform(*speed), rnd.uniform(*size),
                         rnd.uniform(-8, 8), rnd.uniform(-2, 2)) for _ in range(n)] for _ in triggers]

    def update(self, t):
        for s, h in self.parts:
            s.hide_render = True
            if h:
                h.hide_render = True
        ts = twos(t)
        for b, t0 in enumerate(self.triggers):
            age = ts - t0
            if not (0 <= age < self.life):
                continue
            slot = b % self.pool
            ox, oy = self.origin
            for k, (ang, spd, size, spin, vz) in enumerate(self.params[b]):
                s, h = self.parts[slot * self.n + k]
                dist = spd * (1 - math.exp(-4 * age)) / 4
                x, y = ox + dist * math.cos(ang), oy + dist * math.sin(ang)
                z = self.z + vz * age
                sc = size * (1 - age / self.life) * (1.6 if age < 1 / 12 else 1.0)
                s.hide_render = False
                s.location = (x, y, z)
                s.scale = (sc, sc, 1)
                s.rotation_euler.z = spin * age
                if h:
                    h.hide_render = False
                    h.location = (x, y, z - 0.05)
                    h.scale = (sc * 4, sc * 4, 1)


class Stripes:
    """Bars streaming across the frame at different speeds, wrapping around; rot_deg tilts the stream."""

    def __init__(self, n, colors, lo, hi, z, speed=(6, 18), length=(2, 9), thick=(0.03, 0.3),
                 rot_deg=0.0, direction=1, seed=3, span=26):
        rnd = random.Random(seed)
        self.span, self.rot = span, math.radians(rot_deg)
        self.items = []
        for _ in range(n):
            ln = rnd.uniform(*length)
            obj = m.bar(0, 0, ln, rnd.uniform(*thick), rnd.choice(colors), z=z + rnd.random() * 0.2,
                        rot_deg=rot_deg)
            self.items.append((obj, ln, rnd.uniform(-span, span), rnd.uniform(lo, hi),
                               direction * rnd.uniform(*speed)))

    def update(self, t):
        c, s = math.cos(self.rot), math.sin(self.rot)
        for obj, ln, x0, off, v in self.items:
            along = (x0 + v * t + self.span) % (2 * self.span) - self.span - ln / 2
            obj.location.x = along * c - off * s
            obj.location.y = along * s + off * c


class Marquee:
    """A text band that scrolls forever along its own direction."""

    def __init__(self, unit, face, size, x, y, color, z, rot_deg=0.0, speed=3.0, band=None):
        self.obj = m.text(unit, face, size, 0, 0, color, z=z, rot_deg=rot_deg, valign="CENTER")
        bpy.context.view_layer.update()
        self.period = self.obj.dimensions.x
        self.obj.data.body = unit * 12
        self.x, self.y, self.rot, self.speed = x, y, math.radians(rot_deg), speed
        self.band = band

    def update(self, t):
        along = -((self.speed * t) % self.period) - self.period * 4
        self.obj.location.x = self.x + along * math.cos(self.rot)
        self.obj.location.y = self.y + along * math.sin(self.rot)


def extend_rule(obj, length_t=None):
    """A bar that shoots out from its left end on each downbeat and flies off at the end of the bar."""
    def upd(t):
        _, ph = bar_phase(t)
        grow = ease_out(ph / (length_t or BEAT_LEN))
        exit_ = max(0.0, ph - BEAT_LEN * 3.5)
        obj.scale.x = max(grow, 1e-3)
        obj["x0"] = obj.get("x0", obj.location.x)
        obj.location.x = obj["x0"] + exit_ * 60
    return upd


def spin(obj, rate):
    def upd(t):
        obj.rotation_euler.z = rate * t
    return upd


def drift(obj, vx, vy):
    x0, y0 = obj.location.x, obj.location.y

    def upd(t):
        obj.location.x = x0 + vx * t
        obj.location.y = y0 + vy * t
    return upd


def hud(objs, cam, dist=10.0):
    """Pin layout-space objects to the camera: they stay put on screen while the world moves."""
    k = dist * math.tan(math.radians(FOV / 2)) / (m.W / 2)
    for o in objs:
        x, y = o.location.x, o.location.y
        o.parent = cam
        o.location = (x * k, y * k, -dist)
        o.scale = (o.scale.x * k, o.scale.y * k, o.scale.z * k)


# ---------------------------------------------------------------- shots

class Shot:
    def __init__(self, bar0, bar1):
        self.t0, self.t1 = BAR_T[bar0], BAR_T[bar1]
        self.start = len(m.CREATED)
        self.objs = []
        self.updaters = []
        self.camera = None   # f(t) -> (eye, target, roll)

    def u(self, t):
        return (t - self.t0) / (self.t1 - self.t0)

    def mark(self):
        return len(m.CREATED)

    def since(self, mark):
        return m.CREATED[mark:]

    def done(self):
        self.objs = m.CREATED[self.start:]
        return self

    def update(self, t):
        for f in self.updaters:
            f(t)


def chars(body, face, size, x, y, color, z=1.0, advance=1.0):
    """One text object per character so each can be animated (full-width scripts only)."""
    return [m.text(c, face, size, x + i * size * advance, y, color, z=z) for i, c in enumerate(body)]


def shot_a_intro(b0, b1, cam):
    """Paper / red print layout; slow dolly back with a roll, the red block wipes in, 表 lands on beat 2."""
    sh = Shot(b0, b1)
    m.background(PAPER, z=-12)
    block = m.rect(-3.2, -7, 3.2, 7, RED, z=-1)
    ura = m.text("裏", "mincho", 7.4, -3.2, 0.1, INK, z=1, align="CENTER", valign="CENTER")
    omote = m.text("表", "mincho", 7.4, 5.25, -0.2, PAPER, z=2, align="CENTER", valign="CENTER")
    ht = m.halftone(-9, -5.5, 1.5, -1.0, INK, 0.16, "X", -5.25, 5.25, z=-3, rmax=0.48)
    m.rect(-30, 2.85, 30, 3.55, INK, z=0.6, rot_deg=-4)
    mq = Marquee("URAOMOTE LOVERS  ◆  裏表ラバーズ  ◆  ", "gothic", 0.42, 0, 3.2, PAPER, z=0.7, rot_deg=-4, speed=4)
    rules = [m.bar(-7.6, -2.4, 9.5, 0.05, INK, z=0.8), m.bar(-7.6, -2.65, 6.0, 0.02, RED, z=0.8)]
    stripes = Stripes(10, [INK, RED, INK], -4.6, -3.0, 0.4, speed=(8, 22), seed=12)
    ring = m.dashed_ring(1.7, 1.3, 2.4, 0.06, RED, z=2.5)
    mk = sh.mark()
    m.text("URAOMOTE LOVERS", "din", 0.36, -7.45, 3.95, INK, spacing=1.25)
    m.rect(-7.62, -4.27, -4.1, -3.55, PAPER, z=0)
    tc = m.text("", "din", 0.48, -7.45, -4.05, INK, spacing=1.05)
    m.corner_marks(0.22, 0.45, 0.025, INK, corners=("tl", "bl"))
    hud(sh.since(mk), cam)
    heart = m.heart(1.7, 1.3, 1.75, -16, lit="#F7F4EC", dark=INK, outline=INK, outline_px=7, z=3.5)
    bursts = Bursts(beats_in(sh.t0, sh.t1, 2), (1.7, 1.3), [INK, RED, INK], n=16, seed=11, z=4.0)
    second = BEATS[bisect.bisect_left(BEATS, sh.t0) + 1]

    def upd(t):
        ts, lt = twos(t), t - sh.t0
        block.location.x = 5.35 + 14 * (1 - ease_out(lt / (BEAT_LEN * 0.75)))
        block.rotation_euler.z = math.radians(-4 + 3 * math.sin(lt * 2))
        s = 1 + 0.6 * (1 - ease_out((ts - sh.t0) / 0.17))
        ura.scale = (s, s, 1)
        ura.location.x = -3.2 - 0.5 * lt
        omote.hide_render = ts < second
        so = 1 + 0.6 * (1 - ease_out((ts - second) / 0.17))
        omote.scale = (so, so, 1)
        omote.location.y = -0.2 + 0.35 * lt
        ht.location.x = -3.75 + 0.6 * lt
        _, ph = beat_phase(t)
        hs = 1.75 * (1 + 0.14 * punch(ph))
        heart.scale = (hs, hs, hs)
        heart.rotation_euler.y = math.radians(-20) + 2.2 * (ts - sh.t0)
        ring.scale = (1 + 0.12 * punch(ph),) * 3
        tc.data.body = timecode(t)
        mq.update(lt)
        stripes.update(lt)
        bursts.update(t)
    sh.updaters += [upd, extend_rule(rules[0]), extend_rule(rules[1], BEAT_LEN * 1.5), spin(ring, 0.8)]

    def camera(t):
        u = ease_io(sh.u(t))
        eye = lerp((-4.0, -3.0, 11.0), (2.5, 1.2, 18.0), u)
        target = lerp((-0.5, -0.3, 0.0), (1.0, 0.2, 0.0), u)
        return eye, target, lerp(-10.0, 6.0, u)
    sh.camera = camera
    return sh.done()


def shot_b_type(b0, b1, cam):
    """Neon title typed in on eighth notes while the camera trucks past it; RGB split kicks on beats."""
    sh = Shot(b0, b1)
    m.background(NIGHT, z=-12)
    ht = m.halftone(-14, -6.5, 14, -1.2, PINK, 0.14, "Y", -2.65, 2.65, z=-3, rmax=0.42)
    title = "裏表ラバーズ"
    adv = 2.6 * 0.92
    layers = [chars(title, "gothic", 2.6, -7.3, 0.6, col, z=z, advance=0.92)
              for col, z in ((CYAN, 1.0), (PINK, 1.1), (WHITE, 1.2))]
    m.rect(-30, -2.35, 30, -1.45, PINK, z=2, rot_deg=7)
    mq = Marquee("URAOMOTE LOVERS  ◆  裏表ラバーズ  ◆  ", "gothic", 0.48, 0, -1.9, NIGHT, z=2.1, rot_deg=7, speed=6)
    stripes = Stripes(14, [CYAN, PINK, WHITE], -5, 5, -2, speed=(14, 30), length=(3, 12), thick=(0.02, 0.12),
                      direction=-1, seed=22)
    ring = m.dashed_ring(2, 0.5, 5.5, 0.08, CYAN, dashes=64, z=-1.5)
    mk = sh.mark()
    m.corner_marks(0.35, 0.7, 0.035, WHITE)
    m.text("SVC://PHEEBIE.MODEL   F0=RMVPE   SR=44100", "mono", 0.2, -7.4, 3.8, CYAN)
    rec = m.text("●REC", "gothic", 0.22, 4.9, 3.8, PINK)
    tc = m.text("", "mono", 0.22, 7.4, 3.8, WHITE, align="RIGHT")
    hud(sh.since(mk), cam)
    m.scanlines(z=0)
    hud(m.CREATED[-1:], cam, dist=0.5)

    def upd(t):
        ts, lt = twos(t), t - sh.t0
        shown = int((ts - sh.t0) / (BEAT_LEN / 2)) + 1
        _, ph = beat_phase(t)
        kick = punch(ph, 14)
        for layer, sgn in zip(layers, (-1, 1, 0)):
            for i, obj in enumerate(layer):
                obj.hide_render = i >= shown
                pop = 1 + 0.5 * (1 - ease_out((ts - (sh.t0 + i * BEAT_LEN / 2)) / 0.15))
                obj.scale = (pop, pop, 1)
                obj.location.x = -7.3 + i * adv + sgn * (0.05 + 0.25 * kick)
                obj.location.y = 0.6 - sgn * (0.03 + 0.12 * kick)
        ht.location.y = -3.85 + 0.5 * lt
        ring.rotation_euler.z = -0.6 * lt
        ring.scale = (1 + 0.08 * kick,) * 3
        rec.hide_render = int(t * 2) % 2 == 1
        tc.data.body = timecode(t)
        mq.update(lt)
        stripes.update(lt)
    sh.updaters.append(upd)

    def camera(t):
        u = ease_io(sh.u(t))
        x = lerp(-6.0, 5.0, u)
        return (x, -1.5, 13.0), (x + 1.8, 0.4, 0.0), 6.0
    sh.camera = camera
    return sh.done()


def shot_inverted(b0, b1, cam):
    """Ink ground; the camera orbits a stack of katakana and tumbling toon crystals."""
    sh = Shot(b0, b1)
    m.background(INK, z=-12)
    ura = m.vtext("ウラ", "gothic", 3.4, -4.6, 4.2, RED, z=-2)
    m.vtext("オモテ", "gothic", 2.3, 5.6, 4.0, PAPER, z=-1)
    ht = m.halftone(-12, 1.5, 12, 6.5, RED, 0.18, "Y", 2.5, -2.5, z=-4, rmax=0.45)
    stripes = Stripes(12, [PAPER, RED], -9, 9, -3, speed=(10, 24), length=(2, 7), thick=(0.02, 0.1),
                      rot_deg=90, seed=33)
    ring = m.dashed_ring(0.3, 0, 3.6, 0.05, PAPER, dashes=36, z=0)
    rnd = random.Random(5)
    gems = []
    for i in range(6):
        g = m.crystal(rnd.uniform(-2.5, 3.0), rnd.uniform(-3.2, 3.2), rnd.uniform(0.5, 0.95),
                      lit=RED if i % 2 else PAPER, dark="#5A0A07" if i % 2 else "#8C877C", outline=PAPER,
                      z=rnd.uniform(-0.5, 4.0))
        gems.append((g, rnd.uniform(-3, 3), rnd.uniform(-3, 3), g.location.y))
    mk = sh.mark()
    m.corner_marks(0.22, 0.45, 0.025, PAPER)
    hud(sh.since(mk), cam)
    bursts = Bursts(beats_in(sh.t0, sh.t1, 1), (0.3, 0.0), [PAPER, RED, PAPER], n=14, seed=21, halo=False, z=2.0)

    def upd(t):
        ts, lt = twos(t), t - sh.t0
        for g, rx, rz, y0 in gems:
            g.rotation_euler.x = rx * ts
            g.rotation_euler.z = rz * ts
            g.location.y = y0 + 0.25 * math.sin(ts * 3 + rx)
        ura.location.y = 4.2 - 0.8 * lt
        ht.location.x = 0.8 * lt
        ring.rotation_euler.z = 1.2 * lt
        stripes.update(lt)
        bursts.update(t)
    sh.updaters.append(upd)

    def camera(t):
        u = ease_io(sh.u(t))
        a = math.radians(lerp(-38.0, 28.0, u))
        r = 15.0
        return (r * math.sin(a), 1.5, r * math.cos(a)), (0.3, 0.0, 0.5), lerp(-4.0, 4.0, u)
    sh.camera = camera
    return sh.done()


def shot_b_burst(b0, b1, cam):
    """Chorus hit: a spiral push into the neon heart, a burst on every beat, rings and speed lines."""
    sh = Shot(b0, b1)
    m.background(NIGHT, z=-12)
    ht = m.halftone(-16, -9, 16, -1.0, PINK, 0.14, "Y", -4.0, 4.0, z=-4, rmax=0.42)
    heart = m.heart(0, 0.1, 2.5, 8, lit="#FF4FA0", dark="#7A0F45", outline=WHITE, outline_px=6, tilt=(10, 25), z=2)
    ring = m.ring(0, 0.1, 1.0, 0.985, WHITE, z=1)
    ring2 = m.ring(0, 0.1, 1.0, 0.97, CYAN, z=1.2)
    d1 = m.dashed_ring(0, 0.1, 4.2, 0.07, PINK, dashes=56, z=-0.5)
    d2 = m.dashed_ring(0, 0.1, 5.1, 0.04, WHITE, dashes=90, duty=0.3, z=-1)
    lines = Stripes(26, [PINK, CYAN, WHITE], -8, 8, -2.5, speed=(25, 45), length=(4, 14), thick=(0.015, 0.06),
                    seed=44)
    m.text("URAOMOTE LOVERS", "din", 0.42, 0, 3.6, WHITE, align="CENTER", spacing=1.6, z=0.5)
    m.text("裏表ラバーズ", "gothic", 0.3, 0, -3.9, PINK, align="CENTER", spacing=1.8, z=0.5)
    m.scanlines(z=0)
    hud(m.CREATED[-1:], cam, dist=0.5)
    mk = sh.mark()
    m.corner_marks(0.35, 0.7, 0.035, WHITE)
    hud(sh.since(mk), cam)
    bursts = Bursts(beats_in(sh.t0, sh.t1), (0, 0.1), [PINK, CYAN, WHITE, PINK], n=22, pool=3,
                    speed=(7, 13), seed=31, z=3.0)

    def upd(t):
        ts, lt = twos(t), t - sh.t0
        _, ph = beat_phase(t)
        k = punch(ph, 10)
        hs = 2.5 * (1 + 0.16 * k)
        heart.scale = (hs, hs, hs)
        heart.rotation_euler.y = math.radians(25) + 1.6 * (ts - sh.t0)
        r = 2.9 + 1.6 * (1 - k)
        ring.scale = (r, r, 1)
        r2 = 2.9 + 3.0 * (1 - punch(ph, 5))
        ring2.scale = (r2, r2, 1)
        ring2.hide_render = ph > 0.3
        d1.rotation_euler.z = 0.9 * lt
        d2.rotation_euler.z = -0.5 * lt
        ht.location.y = -5.0 + 0.6 * lt
        lines.update(lt)
        bursts.update(t)
    sh.updaters.append(upd)

    def camera(t):
        u = sh.u(t)
        _, ph = beat_phase(t)
        z = lerp(24.0, 10.0, ease_out(u)) - 2.0 * punch(ph, 9)
        return (0.0, -0.8, z), (0.0, 0.1, 0.0), lerp(0.0, 75.0, ease_io(u))
    sh.camera = camera
    return sh.done()


def shot_strobe(b0, b1, cam):
    """Eighth-note flash cuts: full-frame colour, one giant character, a new camera angle every flash."""
    sh = Shot(b0, b1)
    combos = [(RED, PAPER, "裏"), (INK, RED, "表"), (PAPER, INK, "ラ"), (PINK, NIGHT, "バ"),
              (NIGHT, PINK, "ー"), (PAPER, RED, "ズ"), (INK, PAPER, "裏"), (RED, INK, "表")]
    frames = []
    for i, (bg, fg, c) in enumerate(combos):
        mk = sh.mark()
        m.background(bg, z=-12)
        ch = m.text(c, "gothic" if i % 2 else "mincho", 8.2, 0, 0, fg, z=0, align="CENTER", valign="CENTER")
        st = Stripes(5, [fg], -5, 5, -2, speed=(20, 40), length=(6, 16), thick=(0.05, 0.5), seed=60 + i,
                     rot_deg=[0, 90, -30, 30][i % 4])
        num = m.text(f"{i + 1:02d}", "din", 0.5, -7.4, -4.0, fg, z=0)
        hud([num], cam)
        frames.append((sh.since(mk), ch, st))
    rnd = random.Random(7)
    angles = [(rnd.uniform(-22, 22), rnd.choice((11.0, 16.0)), rnd.uniform(-1.5, 1.5)) for _ in combos]

    def flash(t):
        return min(len(frames) - 1, int((t - sh.t0) / (BEAT_LEN / 2)))

    def upd(t):
        idx = flash(t)
        for i, (objs, _, _) in enumerate(frames):
            for o in objs:
                o.hide_render = i != idx
        _, ph = beat_phase(t)
        s = 1 + 0.25 * punch(twos(ph), 12)
        objs, ch, st = frames[idx]
        ch.scale = (s, s, 1)
        ch.rotation_euler.z = math.radians(8 * math.sin(t * 9))
        st.update(t - sh.t0)
    sh.updaters.append(upd)

    def camera(t):
        idx = flash(t)
        roll, dist, dx = angles[idx]
        local = (t - (sh.t0 + idx * BEAT_LEN / 2)) / (BEAT_LEN / 2)
        return (dx, -0.5, dist - 1.5 * local), (dx * 0.3, 0.0, 0.0), roll
    sh.camera = camera
    return sh.done()


def shot_a_lyric(b0, b1, cam):
    """Mirrored print layout, crane up; a lyric block shoots in and the line types on sixteenths."""
    sh = Shot(b0, b1)
    m.background(PAPER, z=-12)
    block = m.rect(-9.5, -8, -2.2, 8, RED, z=-1)
    omote = m.text("表", "mincho", 7.4, -5.25, 0.3, PAPER, z=0, align="CENTER", valign="CENTER")
    ht = m.halftone(0.5, 1.0, 12, 6.5, INK, 0.16, "X", 5.75, -5.75, z=-3, rmax=0.48)
    lyric_bar = m.bar(-2.2, -2.6, 10.7, 1.2, INK, z=0.5)
    line = "ウラオモテ ラバーズ ／ URAOMOTE LOVERS"
    lyric = m.text("", "gothic", 0.62, -1.8, -2.82, PAPER, z=0.6, spacing=1.05)
    caret = m.rect(0, -2.95, 0.08, -2.2, RED, z=0.7)
    stripes = Stripes(10, [INK, RED], 3.2, 4.6, 0.3, speed=(8, 20), seed=55, direction=-1)
    rules = [m.bar(-2.0, -3.55, 9.0, 0.04, INK, z=0.4), m.bar(-2.0, -1.7, 5.0, 0.02, RED, z=0.4)]
    ring = m.dashed_ring(2.6, 1.0, 2.1, 0.05, INK, z=2.0)
    heart = m.heart(2.6, 1.0, 1.5, 12, lit="#F7F4EC", dark=INK, outline=INK, outline_px=7, z=3.0)
    rnd = random.Random(9)
    gems = [m.crystal(rnd.uniform(4.5, 7.2), rnd.uniform(-1.2, 3.6), rnd.uniform(0.35, 0.6),
                      lit=RED, dark="#5A0A07", outline=INK, z=rnd.uniform(1, 4)) for _ in range(3)]
    mk = sh.mark()
    m.text("LYRIC 02-07", "din_medium", 0.2, -1.8, -3.9, INK, spacing=1.4)
    m.corner_marks(0.22, 0.45, 0.025, INK, corners=("tr", "br"))
    hud(sh.since(mk), cam)
    bursts = Bursts(beats_in(sh.t0, sh.t1, 2), (2.6, 1.0), [INK, RED], n=16, seed=41, halo=False, z=3.5)

    def upd(t):
        ts, lt = twos(t), t - sh.t0
        lyric_bar.scale.x = max(1e-3, ease_out(lt / (BEAT_LEN * 0.6)))
        n = int((ts - sh.t0) / (BEAT_LEN / 4))
        lyric.data.body = line[:n]
        bpy.context.view_layer.update()
        caret.location.x = -1.8 + lyric.dimensions.x + 0.12
        caret.hide_render = n >= len(line) and int(t * 4) % 2 == 1
        block.location.x = -0.5 * lt
        block.rotation_euler.z = math.radians(3 * math.sin(lt * 2.5))
        omote.location.y = 0.3 - 0.4 * lt
        ht.location.x = 6.25 - 0.7 * lt
        _, ph = beat_phase(t)
        hs = 1.5 * (1 + 0.14 * punch(ph))
        heart.scale = (hs, hs, hs)
        heart.rotation_euler.y = 1.8 * (ts - sh.t0)
        ring.rotation_euler.z = -1.0 * lt
        for i, g in enumerate(gems):
            g.rotation_euler.x = (1.5 + i) * ts
            g.rotation_euler.z = (2.0 - i) * ts
        stripes.update(lt)
        bursts.update(t)
    sh.updaters += [upd, extend_rule(rules[0]), extend_rule(rules[1], BEAT_LEN * 1.5)]

    def camera(t):
        u = ease_io(sh.u(t))
        eye = lerp((2.5, -7.5, 11.5), (-1.0, 3.0, 15.0), u)
        target = lerp((0.5, -1.5, 0.0), (1.0, 0.5, 0.0), u)
        return eye, target, lerp(5.0, -5.0, u)
    sh.camera = camera
    return sh.done()


def shot_b_end(b0, b1, cam):
    """Title lockup: starts inside the heart's crosshair and pulls back to reveal the whole layout."""
    sh = Shot(b0, b1)
    m.background(NIGHT, z=-12)
    ht = m.halftone(-14, -7.5, 14, -1.2, PINK, 0.14, "Y", -3.15, 3.15, z=-3, rmax=0.42)
    title = "裏表ラバーズ"
    split = [m.text(title, "gothic", 3.0, -7.6, 0.75, col, z=z) for col, z in ((CYAN, 1.0), (PINK, 1.1), (WHITE, 1.2))]
    m.rect(-30, -2.35, 30, -1.45, PINK, z=0.5, rot_deg=7)
    mq = Marquee("URAOMOTE LOVERS  ◆  裏表ラバーズ  ◆  ", "gothic", 0.48, 0, -1.9, NIGHT, z=0.6, rot_deg=7, speed=6)
    heart = m.heart(4.9, -0.3, 2.2, 14, lit="#FF4FA0", dark="#7A0F45", outline=WHITE, outline_px=6, tilt=(10, 25),
                    z=2.5)
    ring = m.ring(4.9, -0.3, 2.95, 2.92, WHITE, z=2.0)
    dr = m.dashed_ring(4.9, -0.3, 3.4, 0.06, CYAN, dashes=40, z=1.8)
    lines = Stripes(16, [PINK, CYAN, WHITE], -5, 5, -2, speed=(18, 35), length=(3, 10), thick=(0.02, 0.08), seed=77)
    mk = sh.mark()
    m.corner_marks(0.35, 0.7, 0.035, WHITE)
    m.text("WORDS & MUSIC / wowaka\nCOVER / PHEEBIE  VOICE / DDSP-SVC", "mono", 0.17, -7.4, -3.75, WHITE, line=1.1)
    hud(sh.since(mk), cam)
    m.scanlines(z=0)
    hud(m.CREATED[-1:], cam, dist=0.5)
    bursts = Bursts(beats_in(sh.t0, sh.t1), (4.9, -0.3), [PINK, CYAN, WHITE], n=20, seed=51, z=3.0)

    def upd(t):
        lt = t - sh.t0
        _, ph = beat_phase(t)
        k = punch(ph, 14)
        for obj, sgn in zip(split, (-1, 1, 0)):
            obj.location.x = -7.6 + sgn * (0.06 + 0.3 * k)
            obj.location.y = 0.75 - sgn * (0.04 + 0.1 * k)
        hs = 2.2 * (1 + 0.14 * punch(ph))
        heart.scale = (hs, hs, hs)
        heart.rotation_euler.y = math.radians(25) + 1.4 * (twos(t) - sh.t0)
        ring.scale = (1 + 0.1 * k,) * 3
        dr.rotation_euler.z = 1.1 * lt
        ht.location.y = -4.35 + 0.5 * lt
        mq.update(lt)
        lines.update(lt)
        bursts.update(t)
    sh.updaters.append(upd)

    def camera(t):
        u = ease_out(sh.u(t) * 1.4)
        eye = lerp((4.9, -0.6, 5.5), (0.0, -1.0, 19.0), u)
        target = lerp((4.9, -0.3, 0.0), (0.0, 0.0, 0.0), u)
        return eye, target, lerp(25.0, 0.0, u)
    sh.camera = camera
    return sh.done()


PLAN = [(shot_a_intro, 2), (shot_b_type, 1), (shot_inverted, 1), (shot_b_burst, 2),
        (shot_strobe, 1), (shot_a_lyric, 2), (shot_b_end, 1)]


def main():
    scene = m.reset(samples=16)
    cam = m.perspective_camera(FOV)
    m.sun((35, -30))
    shots, bar = [], 0
    for build, n in PLAN:
        if bar >= BARS:
            break
        shots.append(build(bar, min(bar + n, BARS), cam))
        bar += n
    for sh in shots:
        for o in sh.objs:
            o.hide_render = True

    def place_camera(t, i):
        sh = shots[i]
        eye, target, roll = sh.camera(t)
        # whip pan: accelerate sideways out of a shot, arrive from the other side into the next
        side = 1 if i % 2 == 0 else -1
        off = 0.0
        if t > sh.t1 - WHIP:
            off = side * 30 * ((t - (sh.t1 - WHIP)) / WHIP) ** 2
        elif t < sh.t0 + WHIP and i > 0:
            off = -(-side) * 30 * (1 - (t - sh.t0) / WHIP) ** 2
        _, ph = beat_phase(t)
        sx, sy = shake(t, 0.18 * punch(ph, 8))
        eye = (eye[0] + off + sx, eye[1] + sy, eye[2])
        target = (target[0] + off + sx * 0.5, target[1] + sy * 0.5, target[2])
        m.look_at(cam, eye, target, roll + 4 * punch(ph, 8) * (1 if i % 2 else -1))

    def on_frame(scene, *_):
        t = T0 + (scene.frame_current - 1) / FPS
        i = next((k for k, s in enumerate(shots) if s.t0 <= t < s.t1), len(shots) - 1)
        active = shots[i]
        for s in shots:
            if s is not active:
                for o in s.objs:
                    o.hide_render = True
        for o in active.objs:
            o.hide_render = False
        active.update(t)
        place_camera(t, i)

    # Frames are rendered one by one from here: toggling hide_render inside a frame-change handler
    # during render(animation=True) crashes the depsgraph (Blender 5.2.2).
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = int(round((T1 - T0) * FPS))
    if len(argv) > 3:
        scene.frame_start, scene.frame_end = int(argv[3]), int(argv[4])
    if len(argv) > 5:
        scene.frame_step = int(argv[5])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "window.json"), "w") as f:
        json.dump({"start": T0, "end": T1, "frames": int(round((T1 - T0) * FPS)), "fps": FPS,
                   "bpm": 60 / BEAT_LEN}, f)
    print(f"window {T0:.2f}-{T1:.2f} s, {scene.frame_end - scene.frame_start + 1} frames, {60 / BEAT_LEN:.1f} BPM")
    for f in range(scene.frame_start, scene.frame_end + 1, scene.frame_step):
        path = os.path.join(os.path.abspath(OUT), f"f_{f:04d}.png")
        if os.path.exists(path):
            continue
        scene.frame_set(f)
        on_frame(scene)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)


main()
