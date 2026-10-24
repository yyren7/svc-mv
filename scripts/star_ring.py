"""月亮外圈的星环：月亮是唱片中间的标签，外面 15 道看不见的正圆轨道，光点沿着轨道顺时针转，拖着细尾巴。
只用 numpy（Blender 里由 onepic.star_ring() 搭成场景，外面也能单独算）；逐帧的值全由帧号算出来，任意一段帧都能单独渲染。

- 每道轨道一段频率（里低外高）。亮着的光点颗数跟这段频率的响度走，但哪颗、什么时候出现（落在拍子上）、
  什么时候熄灭是随机的（固定种子），不会一起亮一起灭。
- 每道轨道各有基准转速（2 到 14 小节一圈），同一道上的光点快慢拉开（0.6–1.6 倍），快的追过慢的；响的时候一起转快一点。
- 每颗光点按自己的周期明灭（4–12 拍，相位随机），这段频率再调亮暗一些，经过朝她和对面那两段（唱片的反光）亮一点。
- 同一道上后面的光点追近时，前面那颗的尾巴收短，光头不落在别人的尾巴上；新出现的光点挑这道上空的地方。
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


def lifecycle(rng, F, group, target, beat_frames, beat, fps, per_beat=2, room=None):
    """光点的生灭 -> 每颗逐帧的出现程度 (n, F)，0..1。group 是每颗属于哪一组，target (组数, F) 是每组逐帧应亮着的
    颗数；颗数跟着 target 走，但哪颗、什么时候是随机的：
    - 出现只落在拍子上（beat_frames，拍长 beat 秒），按各组缺的颗数以 2.5 秒的时间常数补，全部加起来一拍最多 per_beat 颗，
      先补缺得多的组；组里挑哪颗按 room(帧, 候选, 亮着的) 给的权重（不给就一样）；淡入 0.4–0.9 秒；
    - 每颗亮着时平均 8–20 秒自己熄灭（由别的补上，响度不变时也在轮换）；一组比目标多时按 2.5 秒的时间常数多灭一些；
      淡出 1.0–2.5 秒，淡出完再过 1 秒才能再出现。
    整首按固定种子模拟一遍，每次算出来都一样。"""
    n, G = len(group), len(target)
    on_beat = np.zeros(F, bool)
    on_beat[beat_frames[(beat_frames >= 0) & (beat_frames < F)]] = True
    life = rng.uniform(8, 20, n) * fps                      # 帧
    on = np.zeros(n, bool)
    free = np.zeros(n)                                      # 能再出现的帧
    t_on = np.full(n, -1e9)
    fin = np.ones(n)
    spans = []                                              # (光点, 出现帧, 淡入帧数, 熄灭帧, 淡出帧数)
    for g in range(G):
        mem = np.flatnonzero(group == g)
        on[rng.choice(mem, min(int(round(target[g, 0])), len(mem)), replace=False)] = True
    for f in range(F):
        k = np.bincount(group[on], minlength=G)
        over = np.maximum(k - target[:, f], 0) / (2.5 * fps * np.maximum(k, 1))
        for i in np.flatnonzero(on & (rng.random(n) < 1 / life + over[group])):
            fout = rng.uniform(1.0, 2.5) * fps
            spans.append((i, t_on[i], fin[i], f, fout))
            on[i] = False
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
            cand = np.flatnonzero(ok & (group == g))
            w = room(f, cand, on) if room else None
            i = rng.choice(cand, p=None if w is None else w / w.sum())
            on[i], t_on[i], fin[i] = True, f, rng.uniform(0.4, 0.9) * fps
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
    """星环的光点：每道轨道上的光点（颗数按轨道的周长，里圈 3 颗、外圈 19 颗，最多 128 颗亮着，各多备 2 颗轮换），
    各自的转速、明灭的周期和相位、大小、尾巴、颜色，以及逐帧的出现程度。
    spec (F, 频段) 是对数频谱，loud (F,) 是响度，beat / beat0 是拍长和第 0 拍的时刻（秒）。"""

    def __init__(self, spec, loud, fps, beat, beat0, seed=11):
        rng = np.random.default_rng(seed)
        self.fps = fps
        self.sheen = SHEEN
        self.F = F = len(loud)
        K = len(RADII)
        cmax = np.round(1.8 * RADII).astype(int)
        self.track = np.repeat(np.arange(K), cmax + 2)
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
        # 转速：这道轨道的基准速度乘 0.6–1.6，同一道上的几颗在这个范围里均匀拉开（再打乱、各 ±3%），快的会追过慢的
        m = np.empty(n)
        for k in range(K):
            idx = np.flatnonzero(self.track == k)
            m[idx] = rng.permutation(np.geomspace(0.6, 1.6, len(idx))) * rng.uniform(0.97, 1.03, len(idx))
        self.omega = 2 * np.pi / (np.array(TURN_BEATS, float)[self.track] * beat) * m
        self.sway_p = rng.uniform(5, 11, n)
        self.sway_ph = rng.uniform(0, 2 * np.pi, n)
        self.size = 0.8 + 0.6 * rng.random(n) ** 2
        # 尾巴按角度定：57°–97° 的弧；2 R 以外的轨道按 (2/r)^0.75 收短（外圈光点密，√ 时 10.4 R 那道一圈的尾巴加起来
        # 比一圈还长，挤着的时候总被收短）。单位秒
        self.tail = (1.0 + 0.7 * (self.size - 0.8) / 0.6) * np.minimum(1, (2.0 / self.r) ** 0.75) / self.omega
        nb = spec.shape[1]
        edges = np.round(np.linspace(0, nb, K + 1)).astype(int)
        raw = np.stack([spec[:, edges[k]:edges[k + 1]].mean(1) for k in range(K)])
        lvl = np.stack([smooth(x, 0.5 * fps) for x in raw])
        lo, hi = np.percentile(lvl, 10, axis=1)[:, None], np.percentile(lvl, 95, axis=1)[:, None]
        level = np.clip(0.12 + 0.88 * (lvl - lo) / (hi - lo), 0.05, 1.0)      # 每道轨道的响度 (K, F)
        speed = 0.7 + 0.6 * smooth(loud, 1.0 * fps)        # 响的时候一起转快一点
        self.A = np.concatenate([[0.0], np.cumsum(speed)[:-1]]) / fps
        # 明灭：每颗按自己的周期从暗到亮再暗下去（4、6、8 或 12 拍，和歌的拍子成倍数），相位随机，此起彼伏
        self.blink_p = rng.choice((4, 6, 8, 12), n) * beat
        self.blink_ph = rng.uniform(0, 2 * np.pi, n)
        self.env = envelopes(rng, raw[self.track], fps)
        beat_frames = np.round((beat0 + beat * np.arange(int((F / fps - beat0) / beat) + 1)) * fps).astype(int)
        th = self.theta()

        def room(f, cand, on):
            """离同一道上亮着的光点越远越容易被挑中：权重是到最近那颗的角距的平方。"""
            others = np.flatnonzero(on & (self.track == self.track[cand[0]]))
            if not len(others):
                return None
            d = (th[cand, f][:, None] - th[others, f][None, :]) % (2 * np.pi)
            return np.minimum(d, 2 * np.pi - d).min(1) ** 2 + 1e-4

        # 光点是 158 颗，一拍最多出现 4 颗才补得上
        self.alive = lifecycle(rng, F, self.track, 0.3 + (cmax[:, None] - 0.3) * level, beat_frames, beat, fps,
                               per_beat=4, room=room)

    def theta(self):
        """逐帧的极角 (n, F)：沿轨道顺时针转（θ 减小），再带一点很慢的前后晃。"""
        t = np.arange(self.F) / self.fps
        return (self.phase[:, None] - self.omega[:, None] * self.A[None, :]
                + 0.05 * np.sin(2 * np.pi * t[None, :] / self.sway_p[:, None] + self.sway_ph[:, None]))

    def tail_cut(self, th, c=0.8):
        """每颗光点逐帧的尾巴长度系数 (n, F)，0..1。尾巴在光头后面（θ 大的一侧）；同一道上跟在后面的光点离得比尾巴近时，
        尾巴收到两颗之间角距的 c 倍，后面那颗的光头不落在它的尾巴上。后面那颗按出现程度算，淡入时尾巴跟着慢慢收。
        收短是立刻的；放长最快按尾巴自己的时长（尾梢停在原地、光头往前走），被追过以后不会一下子甩出一整条。"""
        n, F = th.shape
        T = np.maximum(np.round(self.tail * self.fps).astype(int), 1)
        fr = np.arange(F)
        arc = np.stack([th[i, np.maximum(fr - T[i], 0)] - th[i] for i in range(n)])     # 整条尾巴的弧度
        k = np.ones((n, F))
        for g in np.unique(self.track):
            idx = np.flatnonzero(self.track == g)
            for i in idx:
                for j in idx[idx != i]:
                    gap = (th[j] - th[i]) % (2 * np.pi)
                    k[i] = np.minimum(k[i], 1 - self.alive[j] * (1 - np.minimum(1, c * gap / np.maximum(arc[i], 1e-6))))
        for f in range(1, F):
            k[:, f] = np.minimum(k[:, f], k[:, f - 1] + 1 / T)
        return k

    def tables(self):
        """逐帧的 (θ, 亮度, 响度, 反光, 尾巴长度系数)，各是 (n, F) 的 float32。亮度：明灭的周期从 0.15 到满，
        这段频率再调亮暗一些，经过反光处亮一点，0..1。"""
        t = np.arange(self.F) / self.fps
        th = self.theta()
        blink = 0.5 + 0.5 * np.sin(2 * np.pi * t[None, :] / self.blink_p[:, None] + self.blink_ph[:, None])
        sh = sheen(th)
        br = np.clip(self.alive * 1.15 * (0.15 + 0.85 * blink) * (0.65 + 0.35 * self.env ** 1.2) * (1 + 0.3 * sh), 0, 1)
        return tuple(a.astype(np.float32) for a in (th, br, self.env, sh, self.tail_cut(th)))
