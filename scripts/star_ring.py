"""月亮外圈的星环：月亮是唱片中间的标签，外面 15 道看不见的正圆轨道，光点沿着轨道顺时针转，拖着细尾巴。
只用 numpy（Blender 里由 onepic.star_ring() 搭成场景，外面也能单独算）；逐帧的值全由帧号算出来，任意一段帧都能单独渲染。

- 每道轨道一段频率（里低外高）。亮着的光点颗数跟这段频率的响度（3 秒的滑动平均）慢慢走，但哪颗、什么时候出现
  （落在拍子上）是随机的（固定种子），不会一起亮一起灭。每次出现亮 LIFE 秒；被追着的会早一点熄灭让路。
- 每道轨道各有基准转速（2 到 14 小节一圈），同一道上的光点快慢拉开（0.6–1.6 倍）；响的时候一起转快一点。
- 每颗光点按自己的周期明灭（4–12 拍，相位随机，最暗 0.4），这段频率再调亮暗一些，经过朝她和对面那两段（唱片的反光）亮一点。
- 尾巴是一段定长的弧（原来的 TAIL 倍）。同一道上快的追上慢的就慢下来跟在后面，光头不进别人的尾巴；新出现的光点
  放在这道上最大的空当里，放不下就不出，所以一道上最多亮几颗按一圈放得下几条整尾巴算。
- 颜色从里圈暖白到外圈冰蓝，个别几颗是金、红、粉的点缀。
长度以月亮半径 R 为单位；极角 θ 从正下方 0 起，θ = π/2 在右边，θ 减小是画面上的顺时针。
"""
import math

import numpy as np

# 轨道半径（R）：里面 9 道 1.40–4.60 R，间距大体往外变宽（按 1 + 0.25 k），每个间距再随机放宽或收窄（×0.55–1.6，
# 种子 1）：0.20、0.36、0.20、0.51、0.33、0.42、0.67、0.51 R，有松有紧；外面 6 道间距更宽（0.70、0.90、0.75、1.05、
# 1.15、1.25 R），到 10.40 R，盘超过半个画面。最外两道从她身后过（kimishira 里猫耳约 8 R，脸约 10.8 R），被她挡住
RADII = np.array((1.40, 1.60, 1.96, 2.16, 2.67, 3.00, 3.42, 4.09, 4.60, 5.30, 6.20, 6.95, 8.00, 9.15, 10.40))
# 每道轨道转一圈的拍数（里 -> 外）：2 到 14 小节，各转各的；外 6 道慢，光点走的线速度和 4.60 R 那道差不多
TURN_BEATS = (16, 8, 24, 12, 32, 16, 20, 12, 24, 28, 36, 32, 44, 48, 56)
INNER, OUTER = (1.00, 0.94, 0.86), (0.70, 0.85, 1.00)       # 里圈暖白 -> 外圈冰蓝（显示的颜色，0..1）
# 点缀：158 颗光点里个别几颗不用轨道的颜色，金 9 颗、红 7 颗、粉 5 颗；星芯往白里调，读起来是带颜色的星
ACCENTS = (((1.00, 0.76, 0.36), 9), ((1.00, 0.40, 0.34), 7), ((1.00, 0.64, 0.80), 5))
SHEEN = math.radians(78)        # 唱片上的反光朝她（θ = 78°，右下），对面也有一道
TAIL = 1.6                      # 尾巴比最早定的样式（57°–97° 的弧）长这么多倍
FOLLOW = 1.05                   # 跟在后面的光点，光头离前面那颗至少它尾巴的这么多倍（尾梢本来就淡，留出的空当看得清）
LIFE = (20, 45)                 # 每次出现亮这么多秒（这个范围里随机）才熄灭
CHASED = 12.0                   # 被追着的另外平均这么多秒就熄灭，给后面快的让路
# 拉开间距的一套（花哨样式用）：11 道，内圈从 1.55 R 起、间距越往外越大；原来里面几道两两挤在一起（1.40 / 1.60、1.96 / 2.16）
FANCY_RADII = (1.55, 2.05, 2.65, 3.35, 4.15, 5.05, 6.05, 7.15, 8.35, 9.65, 11.0)
FANCY_TURNS = (16, 24, 12, 32, 20, 24, 28, 36, 32, 44, 56)


def smooth(x, k):
    k = max(int(k) | 1, 1)
    return np.convolve(np.pad(x, (k // 2, k // 2), mode="edge"), np.ones(k) / k, "valid")


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def sheen(th):
    """极角 th 处的反光，0..1：朝她和对面最亮，横着的两边暗。"""
    return np.abs(np.cos(np.asarray(th) - SHEEN)) ** 4


def envelopes(rng, raw, fps):
    """每颗光点对自己那段频谱 raw (n, F) 的反应 -> (n, F)：起得快慢（0.08–0.25 s）、落得快慢（0.6–2.0 s）、
    晚多少（0–0.5 s）各不相同，鼓点来时此起彼伏地亮，不会齐刷刷一闪。"""
    n, F = raw.shape
    ka = 1 - np.exp(-1 / (fps * rng.uniform(0.08, 0.25, n)))
    kr = 1 - np.exp(-1 / (fps * rng.uniform(0.6, 2.0, n)))
    env = np.empty((n, F), np.float32)
    x = raw[:, 0].copy()
    for f in range(F):
        x += np.where(raw[:, f] > x, ka, kr) * (raw[:, f] - x)
        env[:, f] = x
    lag = rng.integers(0, int(0.5 * fps) + 1, n)
    return np.stack([np.concatenate([np.full(k, env[i, 0]), env[i, :F - k]]) for i, k in enumerate(lag)])


def lifecycle(rng, F, group, target, beat_frames, beat, fps, per_beat=2, life=(8, 20), drop=2.5, protect=0.0,
              tick=None, place=None):
    """光点的生灭 -> 每颗逐帧的出现程度 (n, F)，0..1。group 是每颗属于哪一组，target (组数, F) 是每组逐帧应亮着的
    颗数；颗数跟着 target 走，但哪颗、什么时候是随机的：
    - 出现只落在拍子上（beat_frames，拍长 beat 秒），按各组缺的颗数以 2.5 秒的时间常数补，全部加起来一拍最多 per_beat 颗，
      先补缺得多的组；淡入 0.4–0.9 秒；
    - 每次出现亮 life 秒（这个范围里随机）就熄灭，由别的补上，响度不变时也在轮换；一组比目标多时按 drop 秒的时间常数
      多灭一些，刚出现不到 protect 秒的不灭；淡出 1.0–2.5 秒，淡出完再过 1 秒才能再出现。
    给了 tick(帧, 看得见的) 就每帧先调一次（看得见的 = 亮着的和还在淡出的），在里面走这一帧；它返回的 (n,) 数组是这一帧
    每颗另外熄灭的概率。给了 place(帧, 组, 候选, 看得见的)，组里出哪颗、出在哪由它定，返回 None 是这组放不下了，
    这一拍不再补它；不给就随机挑一颗。整首按固定种子模拟一遍，每次算出来都一样。"""
    n, G = len(group), len(target)
    on_beat = np.zeros(F, bool)
    on_beat[beat_frames[(beat_frames >= 0) & (beat_frames < F)]] = True
    end = np.full(n, np.inf)                                # 这次出现到哪一帧为止
    on = np.zeros(n, bool)
    free = np.zeros(n)                                      # 能再出现的帧
    gone = np.zeros(n)                                      # 淡出完的帧
    t_on = np.full(n, -1e9)
    fin = np.ones(n)
    spans = []                                              # (光点, 出现帧, 淡入帧数, 熄灭帧, 淡出帧数)

    def pick(f, g, cand):
        if not len(cand):
            return None
        return place(f, g, cand, on | (gone > f)) if place else rng.choice(cand)

    for f in range(F):
        extra = tick(f, on | (gone > f)) if tick else None
        if f == 0:                                          # 开头就亮着的
            for g in range(G):
                for _ in range(int(round(target[g, 0]))):
                    i = pick(0, g, np.flatnonzero(~on & (group == g)))
                    if i is None:
                        break
                    on[i], end[i] = True, rng.uniform(0.2, 1.0) * rng.uniform(*life) * fps     # 开头的错开着灭
        k = np.bincount(group[on], minlength=G)
        over = np.maximum(k - target[:, f], 0) / (drop * fps * np.maximum(k, 1))
        hazard = over[group] * (f - t_on >= protect * fps) + (0 if extra is None else extra)
        for i in np.flatnonzero(on & ((f >= end) | (rng.random(n) < hazard))):
            fout = rng.uniform(1.0, 2.5) * fps
            spans.append((i, t_on[i], fin[i], f, fout))
            on[i] = False
            gone[i] = f + fout
            free[i] = f + fout + fps
        if not on_beat[f]:
            continue
        short = np.maximum(target[:, f] - np.bincount(group[on], minlength=G), 0)
        for _ in range(min(rng.poisson(short.sum() * beat / 2.5), per_beat)):
            ok = ~on & (free <= f)
            gw = np.maximum(short, 0) * (np.bincount(group[ok], minlength=G) > 0)
            if gw.sum() <= 0:
                break
            g = rng.choice(G, p=gw / gw.sum())
            i = pick(f, g, np.flatnonzero(ok & (group == g)))
            if i is None:
                short[g] = 0
                continue
            on[i], t_on[i], fin[i] = True, f, rng.uniform(0.4, 0.9) * fps
            end[i] = f + rng.uniform(*life) * fps
            short[g] -= 1
    for i in np.flatnonzero(on):
        spans.append((i, t_on[i], fin[i], F + 1e9, 1.0))
    out = np.zeros((n, F), np.float32)
    fr = np.arange(F)
    for i, a, fi, b, fo in spans:
        lo, hi = int(max(a, 0)), int(min(b + fo + 1, F))
        x = fr[lo:hi]
        out[i, lo:hi] = smoothstep((x - a) / fi) * (1 - smoothstep((x - b) / fo))
    return out


class Ring:
    """星环的光点：每道轨道上的光点（最多亮着的颗数按一圈放得下几条整尾巴，里圈 3 颗、外圈 6 颗，共 61 颗，各多备 3 颗
    轮换），各自的转速、明灭的周期和相位、大小、尾巴、颜色，以及逐帧的角度和出现程度。
    spec (F, 频段) 是对数频谱，loud (F,) 是响度，beat / beat0 是拍长和第 0 拍的时刻（秒）。radii / turns 换一套轨道
    （半径、每道转一圈的拍数，一样长），不给就是 RADII / TURN_BEATS；FANCY_RADII 是拉开间距的 11 道。"""

    def __init__(self, spec, loud, fps, beat, beat0, seed=11, radii=None, turns=None, tail_floor=None, size_max=1.4):
        """tail_floor（rad）：尾巴至少这么长（外圈按 √(2/r) 收短后太短时用它，比如 1.75 ≈ 100°，三分之一圈不到）；
        size_max：光点大小的上限（0.8 起，原来 1.4，大的那几颗亮得晃眼）。"""
        RADII = np.asarray(radii if radii is not None else globals()["RADII"], float)
        TURN_BEATS = turns if turns is not None else globals()["TURN_BEATS"]
        rng = np.random.default_rng(seed)
        self.fps = fps
        self.sheen = SHEEN
        self.F = F = len(loud)
        K = len(RADII)
        # 一圈放得下几颗：每颗占它尾巴的 FOLLOW 倍（尾巴平均是 TAIL × 1.23 rad × min(1, √(2/r))，不短于 tail_floor）
        mean_tail = TAIL * 1.233 * np.minimum(1, (2.0 / RADII) ** 0.5)
        if tail_floor:
            mean_tail = np.maximum(mean_tail, tail_floor * 1.1)
        fit = 2 * np.pi / (FOLLOW * mean_tail)
        cmax = np.minimum(np.round(1.8 * RADII), np.floor(fit)).astype(int)
        self.track = np.repeat(np.arange(K), cmax + 3)
        n = self.n = len(self.track)
        self.r = RADII[self.track]
        track_color = [tuple(a + (b - a) * k / (K - 1) for a, b in zip(INNER, OUTER)) for k in range(K)]
        # 点缀用另一个种子挑，别的随机数（位置、转速、明灭、出现熄灭）和不加点缀时一样
        self.color = np.array([track_color[k] for k in self.track], np.float32)
        pick = np.random.default_rng(seed + 1).permutation(n)
        j = 0
        for c, m in ACCENTS:
            self.color[pick[j:j + m]] = c
            j += m
        self.phase = rng.uniform(0, 2 * np.pi, n)
        # 转速：这道轨道的基准速度乘 0.6–1.6，同一道上的几颗在这个范围里均匀拉开（再打乱、各 ±3%）；快的追上慢的就跟在后面
        m = np.empty(n)
        for k in range(K):
            idx = np.flatnonzero(self.track == k)
            m[idx] = rng.permutation(np.geomspace(0.6, 1.6, len(idx))) * rng.uniform(0.97, 1.03, len(idx))
        self.omega = 2 * np.pi / (np.array(TURN_BEATS, float)[self.track] * beat) * m
        self.size = 0.8 + (size_max - 0.8) * rng.random(n) ** 2
        # 尾巴是一段弧（rad）：TAIL × 57°–97°，2 R 以外的轨道按 √(2/r) 收短，外圈的弧不至于拖过半个画面。
        # 按角度定，光点慢下来尾巴也一样长；给了 tail_floor 就不短于它（大的长两成）
        self.L = TAIL * (1.0 + 0.7 * (self.size - 0.8) / 0.6) * np.minimum(1, (2.0 / self.r) ** 0.5)
        if tail_floor:
            self.L = np.maximum(self.L, tail_floor * (1.0 + 0.2 * (self.size - 0.8) / max(size_max - 0.8, 1e-6)))
        nb = spec.shape[1]
        edges = np.round(np.linspace(0, nb, K + 1)).astype(int)
        raw = np.stack([spec[:, edges[k]:edges[k + 1]].mean(1) for k in range(K)])
        lvl = np.stack([smooth(x, 3.0 * fps) for x in raw])
        lo, hi = np.percentile(lvl, 10, axis=1)[:, None], np.percentile(lvl, 95, axis=1)[:, None]
        level = np.clip(0.12 + 0.88 * (lvl - lo) / (hi - lo), 0.05, 1.0)      # 每道轨道的响度 (K, F)
        speed = 0.7 + 0.6 * smooth(loud, 1.0 * fps)        # 响的时候一起转快一点
        # 明灭：每颗按自己的周期从暗到亮再暗下去（4、6、8 或 12 拍，和歌的拍子成倍数），相位随机，此起彼伏
        self.blink_p = rng.choice((4, 6, 8, 12), n) * beat
        self.blink_ph = rng.uniform(0, 2 * np.pi, n)
        self.env = envelopes(rng, raw[self.track], fps)
        beat_frames = np.round((beat0 + beat * np.arange(int((F / fps - beat0) / beat) + 1)) * fps).astype(int)

        # 逐帧走：θ 减小是顺时针。同一道上看得见的光点，后面那颗的光头离前面那颗不到它尾巴的 FOLLOW 倍时就慢下来，
        # 按 1 秒的时间常数贴到这个距离、跟前面那颗一样快，不会追进别人的尾巴；看不见的照自己的速度走。
        # 被追着的（后面有一颗因为它慢下来）平均 CHASED 秒就熄灭让路，没被追着的亮得久（LIFE 秒）
        TAU = 2 * np.pi
        self.th = th = np.empty((n, F))
        self.step = step = np.zeros((n, F))               # 每帧走的角度
        self.born = np.zeros((n, F), bool)                # 这一帧出现（尾巴从这一帧起算）
        want = self.omega[:, None] * speed[None, :] / fps
        same = (self.track[:, None] == self.track[None, :]) & ~np.eye(n, dtype=bool)
        rows = np.arange(n)

        def tick(f, vis):
            if f == 0:
                th[:, 0] = self.phase
                return
            p = th[:, f - 1]
            ahead = np.where(same & vis[None, :], (p[:, None] - p[None, :]) % TAU, np.inf)    # [i, j]：j 在 i 前面多远
            lead = ahead.argmin(1)
            gap = ahead[rows, lead]
            limit = step[lead, f - 1] + (gap - FOLLOW * self.L[lead]) / fps
            go = np.where(vis & np.isfinite(gap), np.clip(limit, 0, want[:, f - 1]), want[:, f - 1])
            step[:, f] = go
            th[:, f] = p - go
            chased = np.zeros(n)
            chased[lead[vis & np.isfinite(gap) & (go < 0.9 * want[:, f - 1])]] = 1 / (CHASED * fps)
            return chased

        def place(f, g, cand, vis):
            """新出现的一颗放进这道上最大的空当：离前面那颗至少它尾巴的 FOLLOW 倍，离后面那颗至少自己尾巴的 FOLLOW 倍，
            在这段里随机偏中间；放不下返回 None。"""
            i = rng.choice(cand)
            others = np.flatnonzero(vis & (self.track == g))
            if len(others):
                q = th[others, f] % TAU
                o = np.argsort(q)
                a, b = q[o], np.roll(q[o], -1)
                b[-1] += TAU
                lo = a + FOLLOW * self.L[others[o]]          # a 在前面（θ 小），b 在后面
                slack = b - FOLLOW * self.L[i] - lo
                k = slack.argmax()
                if slack[k] < 0:
                    return None
                th[i, f] = lo[k] + slack[k] * rng.uniform(0.3, 0.7)
            self.born[i, f] = True
            return i

        self.alive = lifecycle(rng, F, self.track, 0.3 + (cmax[:, None] - 0.3) * level, beat_frames, beat, fps,
                               per_beat=4, life=LIFE, drop=20.0, protect=10.0, tick=tick, place=place)

    def tail_frames(self):
        """每颗光点逐帧的尾巴往前几帧 (n, F)：往前走过 L 那么长的弧要几帧；不往前超过这次出现的那一帧。"""
        n, F = self.th.shape
        fr = np.arange(F, dtype=float)
        last = np.maximum.accumulate(np.where(self.born, fr[None, :], 0.0), axis=1)
        out = np.empty((n, F))
        for i in range(n):
            S = np.cumsum(self.step[i]) + 1e-9 * fr          # 走过的角度，严格递增
            out[i] = fr - np.interp(S - self.L[i], S, fr)
        return np.minimum(out, fr[None, :] - last)

    def tables(self):
        """逐帧的 (θ, 亮度, 响度, 反光, 尾巴往前的帧数)，各是 (n, F) 的 float32。亮度：明灭的周期从 0.4 到满（暗到 0.15
        时连尾巴一起像灭了一样），这段频率再调亮暗一些，经过反光处亮一点，0..1。"""
        t = np.arange(self.F) / self.fps
        th = self.th
        blink = 0.5 + 0.5 * np.sin(2 * np.pi * t[None, :] / self.blink_p[:, None] + self.blink_ph[:, None])
        sh = sheen(th)
        br = np.clip(self.alive * 1.15 * (0.4 + 0.6 * blink) * (0.65 + 0.35 * self.env ** 1.2) * (1 + 0.3 * sh), 0, 1)
        return tuple(a.astype(np.float32) for a in (th, br, self.env, sh, self.tail_frames()))


# ---------------------------------------------------------------- 花哨样式：每颗光点一种

KINDS = ("plain", "twin", "spark", "pulsar", "comet", "beads", "prism")
KIND_P = (0.20, 0.15, 0.17, 0.10, 0.14, 0.12, 0.12)
WARM = (1.0, 0.78, 0.45)


def fancy(ring, seed=7, spark_rate=40.0, kind_p=None):
    """花哨样式里每颗光点的样式和参数（onepic.star_ring_fancy 用）：
    - kind：KINDS 里的一种，按 KIND_P 随机（固定种子）。plain 普通；twin 双子星（两颗一冷一暖互绕，周期 tw_p 秒，
      尾巴按当时的相位拧成两股）；spark 火花尾（一路往后掉火星）；pulsar 脉冲星（十字星芒踩着拍子亮、拍点上一圈冲击波）；
      comet 彗星（宽软的尾巴从白到本色再到偏紫，朝外一条淡蓝的离子尾）；beads 珠串（后面跟四颗小卫星）；
      prism 棱彩尾（尾巴沿长度变色、颜色往前流）。
    - col2：双子星另一颗的颜色（偏蓝的配暖的，偏暖的配蓝的）；spike0：星芒的起始角度；hue0：棱彩尾的起始色相。
    - sparks：整首的火星，每颗火花尾的光点每秒 spark_rate 个（指数分布的间隔），各自的光点 li、出生帧 fb、
      寿命 life（秒）、往后飘的速度 back、往外的速度 side（R / 秒）、闪烁相位 ph、大的 big（四分之一，带小星芒）、
      颜色（七成暖金偏本色，三成随机色相）。
    kind_p：各种的比例（和 KINDS 对应，自动归一），不给是 KIND_P；某种给 0 就不出（比如不要脉冲星）。"""
    rng = np.random.default_rng(seed)
    n = ring.n
    col = ring.color.astype(np.float32)
    p = np.asarray(kind_p if kind_p is not None else KIND_P, float)
    out = dict(kind=rng.choice(len(KINDS), n, p=p / p.sum()), tw_p=rng.uniform(0.7, 1.5, n), tw_ph=rng.uniform(0, 2 * np.pi, n),
               spike0=rng.uniform(0, np.pi / 2, n), hue0=rng.random(n))
    out["col2"] = np.where((col[:, 2] > col[:, 0])[:, None], np.array(WARM, np.float32)[None, :],
                           np.array((0.55, 0.75, 1.0), np.float32)[None, :])
    keys = ("li", "fb", "life", "back", "side", "ph", "big", "col")
    sp = {k: [] for k in keys}
    for i in np.flatnonzero(out["kind"] == KINDS.index("spark")):
        t = np.cumsum(rng.exponential(ring.fps / spark_rate, int(ring.F / ring.fps * spark_rate * 1.2) + 10))
        t = t[t < ring.F - 1]
        k = len(t)
        hue = rng.random(k)
        warm = 0.6 * np.array(WARM) + 0.4 * col[i]
        c = np.where((hue < 0.7)[:, None], warm[None, :], hsv(hue, 0.5))
        for key, v in (("li", np.full(k, i)), ("fb", t), ("life", rng.uniform(0.5, 1.6, k)),
                       ("back", rng.uniform(0.1, 0.8, k)), ("side", rng.normal(0, 0.3, k)),
                       ("ph", rng.uniform(0, 6.3, k)), ("big", (rng.random(k) < 0.25).astype(float)), ("col", c)):
            sp[key].append(v)
    out["sparks"] = {k: (np.concatenate(v) if v else np.zeros((0, 3) if k == "col" else 0)).astype(np.float32)
                     for k, v in sp.items()}
    return out


def hsv(h, s=0.65, v=1.0):
    """色相 h（0..1，可以是数组）-> RGB。"""
    h = np.asarray(h, float)[..., None]
    k = (np.array((5.0, 3.0, 1.0)) + h * 6) % 6
    return v - v * s * np.clip(np.minimum(k, 4 - k), 0, 1)
