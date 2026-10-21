"""2D material as a risograph print, with PIL: a paper, and a coverage layer per ink (halftone screens, flat
shapes, type) that overprint like riso drums do (each ink multiplies the paper, each drum sits a little out of
register, ink lies unevenly). This is the 2D side of the PV: printed skies behind the 3D sets, screens, signs,
and the pages the 3D scenes are seen through.

    p = Print(1920, 1080, seed=1)
    p.halftone("navy", 15, 12, lambda x, y: 6 * (1 - y / 600))
    p.text("vermilion", "表", "gothic", 700, (100, 50), outline=14)
    p.finish().save("sky.png")

Coordinates and sizes are in final pixels; it draws at `ss` times the size and scales down at the end.
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

INKS = {"paper": "#F1E9D6", "navy": "#1E2236", "pink": "#FF3D8B", "vermilion": "#E0301E", "yellow": "#F4C21B",
        "black": "#1B1A19", "teal": "#2BB6B0"}
FONT_DIR = os.environ.get("MV_FONT_DIR", r"C:\Windows\Fonts")
FONTS = {"gothic": "YuGothB.ttc", "gothic_m": "YuGothM.ttc", "mincho": "yumindb.ttf", "ud": "BIZ-UDGothicB.ttc",
         "din": "DINNextLTPro-Bold.ttf", "din_m": "DINNextLTPro-Medium.ttf", "din_l": "DINNextLTPro-Light.ttf"}


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _lab(c):
    """sRGB (0..1, ...x3 array) to CIE Lab, D65."""
    import numpy as np
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]], np.float32)
    xyz /= np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


class Print:
    def __init__(self, w, h, ss=2, paper=INKS["paper"], seed=0, register=2.0):
        self.w, self.h, self.ss = w, h, ss
        self.paper = paper
        self.rnd = random.Random(seed)
        self.register = register          # how far each drum may sit off register, in final pixels
        self.layers = {}                  # ink -> L coverage (255 = full ink) at ss scale
        self.order = []
        self._fonts = {}

    # ---------------------------------------------------------------- plumbing
    def ink(self, name):
        if name not in self.layers:
            self.layers[name] = Image.new("L", (self.w * self.ss, self.h * self.ss), 0)
            self.order.append(name)
        return self.layers[name]

    def _d(self, name):
        return ImageDraw.Draw(self.ink(name))

    def _s(self, v):
        return v * self.ss

    def font(self, face, size):
        key = (face, int(size * self.ss))
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, FONTS.get(face, face)), key[1])
        return self._fonts[key]

    def mask(self):
        """A blank coverage mask at working scale, for shapes that are drawn once and applied as ink or knockout."""
        return Image.new("L", (self.w * self.ss, self.h * self.ss), 0)

    def apply(self, name, mask, value=255):
        """Lay ink through a mask (value 255), or take it away (value 0) where the mask is set."""
        layer = self.ink(name)
        if value:
            self.layers[name] = ImageChops.lighter(layer, mask)
        else:
            self.layers[name] = ImageChops.subtract(layer, mask)

    def knockout(self, mask, keep=()):
        """Paper shows through: every ink but `keep` is removed under the mask."""
        for name in list(self.layers):
            if name not in keep:
                self.apply(name, mask, 0)

    # ---------------------------------------------------------------- shapes
    def poly(self, name, pts, fill=True, width=0):
        d = self._d(name)
        pts = [(self._s(x), self._s(y)) for x, y in pts]
        if fill:
            d.polygon(pts, fill=255)
        if width:
            d.line(pts + pts[:1], fill=255, width=int(self._s(width)), joint="curve")

    def circle(self, name, cx, cy, r, width=0, value=255, mask=None):
        d = ImageDraw.Draw(mask) if mask is not None else self._d(name)
        box = [self._s(cx - r), self._s(cy - r), self._s(cx + r), self._s(cy + r)]
        if width:
            d.ellipse(box, outline=value, width=int(self._s(width)))
        else:
            d.ellipse(box, fill=value)

    def rect(self, name, x0, y0, x1, y1, value=255, mask=None, radius=0):
        d = ImageDraw.Draw(mask) if mask is not None else self._d(name)
        box = [self._s(x0), self._s(y0), self._s(x1), self._s(y1)]
        if radius:
            d.rounded_rectangle(box, radius=self._s(radius), fill=value)
        else:
            d.rectangle(box, fill=value)

    def line(self, name, pts, width, value=255, mask=None):
        d = ImageDraw.Draw(mask) if mask is not None else self._d(name)
        d.line([(self._s(x), self._s(y)) for x, y in pts], fill=value, width=max(1, int(self._s(width))))

    def pill(self, x0, y0, x1, y1):
        """A mask of a rounded band (a kasumi cloud), ends fully round."""
        m = self.mask()
        self.rect(None, x0, y0, x1, y1, mask=m, radius=(y1 - y0) / 2)
        return m

    def heart(self, cx, cy, size, rot_deg=0.0):
        """A mask of a heart, size = its width."""
        pts = []
        for k in range(160):
            t = 2 * math.pi * k / 160
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            a = math.radians(rot_deg)
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            pts.append((self._s(cx + x * size / 34), self._s(cy + y * size / 34)))
        m = self.mask()
        ImageDraw.Draw(m).polygon(pts, fill=255)
        return m

    # ---------------------------------------------------------------- screens
    def halftone(self, name, angle_deg, cell, radius, clip=None, shape="dot"):
        """A dot screen at angle_deg with `cell` px pitch; radius(x, y) gives each dot's radius in px (<= 0: none).
        clip: an optional mask the screen is limited to."""
        layer = self.mask() if clip is not None else self.ink(name)
        d = ImageDraw.Draw(layer)
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        reach = math.hypot(self.w, self.h)
        n = int(reach / cell) + 2
        cx0, cy0 = self.w / 2, self.h / 2
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                u, v = i * cell, j * cell
                x, y = cx0 + u * ca - v * sa, cy0 + u * sa + v * ca
                if x < -cell or y < -cell or x > self.w + cell or y > self.h + cell:
                    continue
                r = radius(x, y)
                if r <= 0.15:
                    continue
                r = min(r, cell * 0.72)
                if shape == "line":
                    d.line([(self._s(x - cell * 0.5 * ca), self._s(y - cell * 0.5 * sa)),
                            (self._s(x + cell * 0.5 * ca), self._s(y + cell * 0.5 * sa))], fill=255, width=max(1, int(self._s(2 * r))))
                else:
                    d.ellipse([self._s(x - r), self._s(y - r), self._s(x + r), self._s(y + r)], fill=255)
        if clip is not None:
            self.apply(name, ImageChops.multiply(layer, clip))

    # ---------------------------------------------------------------- type
    def text_mask(self, s, face, size, xy, anchor="la", outline=0, vertical=False, spacing=1.0, mask=None):
        """Type into a mask. outline > 0 draws only the outline, that many px wide."""
        m = mask if mask is not None else self.mask()
        d = ImageDraw.Draw(m)
        f = self.font(face, size)
        chars = [(s, xy)]
        if vertical:
            x, y = xy
            chars = [(ch, (x, y + k * size * spacing)) for k, ch in enumerate(s)]
            anchor = "mt"
        for ch, (x, y) in chars:
            pos = (self._s(x), self._s(y))
            if outline:     # the glyph grown by the outline width, its own shape taken out again
                d.text(pos, ch, font=f, anchor=anchor, fill=255, stroke_width=int(self._s(outline)), stroke_fill=255)
                d.text(pos, ch, font=f, anchor=anchor, fill=0)
            else:
                d.text(pos, ch, font=f, anchor=anchor, fill=255)
        return m

    def text(self, name, s, face, size, xy, **kw):
        self.apply(name, self.text_mask(s, face, size, xy, **kw))

    # ---------------------------------------------------------------- pictures
    def separate(self, img, box, inks=("navy", "vermilion", "pink", "yellow"), key="black", screens=None, levels=6,
                 solid=0.8, dark=26.0, floor=0.15, mask=None):
        """Print a picture (an illustration) into box = (x0, y0, x1, y1). Line art and the darkest parts (grey
        below Lab L `dark`, anything below 0.4 x that) go to the key ink as solids, so lines stay lines; every
        other pixel takes the coverages of
        the colour inks whose overprint on this paper comes nearest to it in Lab (steps of 1/(levels-1)). The
        coverage maps are smoothed and anything under `floor` dropped (no speckle on near-paper colours); above
        `solid` prints solid, the rest goes through each ink's screen. screens: ink -> (angle_deg, cell_px).
        mask: an L image the size of img, limiting where it prints."""
        import numpy as np
        from itertools import product
        from scipy.ndimage import gaussian_filter
        from scipy.spatial import cKDTree
        x0, y0, x1, y1 = box
        W, H = int(self._s(x1 - x0)), int(self._s(y1 - y0))
        pic = np.asarray(img.convert("RGB").resize((W, H), Image.LANCZOS), np.float32) / 255
        lab = _lab(pic.reshape(-1, 3))
        paper = np.array(rgb(self.paper), np.float32) / 255
        ink_rgb = np.array([rgb(INKS.get(n, n)) for n in inks], np.float32) / 255
        steps = np.linspace(0, 1, levels)
        combos = np.array(list(product(steps, repeat=len(inks))), np.float32)
        cols = np.tile(paper, (len(combos), 1))
        for i in range(len(inks)):
            cols *= 1 - combos[:, i:i + 1] * (1 - ink_rgb[i])
        _, idx = cKDTree(_lab(cols)).query(lab)
        cov = combos[idx].reshape(H, W, len(inks))
        chroma = np.hypot(lab[:, 1], lab[:, 2])     # navy is as dark as line art (L 14) but not grey: keep it
        line = ((lab[:, 0] < dark * 0.4) | ((lab[:, 0] < dark) & (chroma < 9))).reshape(H, W)
        from scipy.ndimage import binary_dilation
        cov[binary_dilation(line, iterations=int(self.ss * 1.5))] = 0.0   # the grey fringe of a line is line, not a tint
        keep = None if mask is None else np.asarray(mask.convert("L").resize((W, H)), np.float32) / 255
        screens = screens or {}
        default = {"navy": (15, 9), "vermilion": (45, 9), "pink": (75, 8), "yellow": (0, 8), "black": (45, 9), "teal": (30, 8)}
        layers = [(key, line.astype(np.float32))] if key else []
        for i, name in enumerate(inks):
            c = gaussian_filter(cov[:, :, i], self.ss * 0.8)
            layers.append((name, np.where(c < floor, 0.0, c)))
        for name, c in layers:
            if keep is not None:
                c = c * keep
            full = Image.new("L", (self.w * self.ss, self.h * self.ss), 0)
            full.paste(Image.fromarray(((c > solid) * 255).astype(np.uint8)), (int(self._s(x0)), int(self._s(y0))))
            self.apply(name, full)
            tint = np.where(c > solid, 0.0, c)
            if not tint.any():
                continue
            angle, cell = screens.get(name, default.get(name, (45, 9)))
            sx, sy = W / (x1 - x0), H / (y1 - y0)

            def radius(x, y, tint=tint, cell=cell):
                u, v = int((x - x0) * sx), int((y - y0) * sy)
                if u < 0 or v < 0 or u >= W or v >= H:
                    return 0
                return cell * math.sqrt(tint[v, u] / math.pi)
            self.halftone(name, angle, cell, radius)
        return cov

    # ---------------------------------------------------------------- print marks
    def register_mark(self, name, cx, cy, r=14, width=1.6):
        self.circle(name, cx, cy, r, width=width)
        self.line(name, [(cx - r * 1.6, cy), (cx + r * 1.6, cy)], width)
        self.line(name, [(cx, cy - r * 1.6), (cx, cy + r * 1.6)], width)

    def crop_marks(self, name, x0, y0, x1, y1, length=36, gap=10, width=1.6):
        for x, sx in ((x0, -1), (x1, 1)):
            for y, sy in ((y0, -1), (y1, 1)):
                self.line(name, [(x + sx * gap, y), (x + sx * (gap + length), y)], width)
                self.line(name, [(x, y + sy * gap), (x, y + sy * (gap + length))], width)

    # ---------------------------------------------------------------- the press
    def finish(self, grain=0.07, alpha=False, shape=None):
        """Overprint the inks on the paper, each drum nudged off register, and scale down. alpha=True returns
        RGBA whose alpha is the union of the inks (for 2D laid over 3D); shape, a working-scale mask, is the alpha
        instead (a cut-out sheet: its paper is opaque too)."""
        import numpy as np
        W, H = self.w * self.ss, self.h * self.ss
        rng = np.random.default_rng(self.rnd.randrange(1 << 30))
        out = np.ones((H, W, 3), np.float32) * (np.array(rgb(self.paper), np.float32) / 255)
        union = np.zeros((H, W), np.float32)
        # ink lies unevenly: broad soft mottling of 88-100 % density, different on every drum
        bw, bh = W // 160 + 2, H // 160 + 2
        for name in self.order:
            dx = int(self._s(self.rnd.uniform(-self.register, self.register)))
            dy = int(self._s(self.rnd.uniform(-self.register, self.register)))
            cov = np.asarray(ImageChops.offset(self.layers[name], dx, dy), np.float32) / 255
            blotch = Image.fromarray((rng.random((bh, bw)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
            cov *= 0.88 + 0.12 * np.asarray(blotch, np.float32) / 255
            union = np.maximum(union, cov)
            ink = np.array(rgb(INKS.get(name, name)), np.float32) / 255
            out *= 1 - cov[..., None] * (1 - ink)          # overprint: inks multiply the paper
        if grain:
            out *= 1 + grain * rng.standard_normal((H, W, 1), np.float32) * 0.5
        img = Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((self.w, self.h), Image.LANCZOS)
        if alpha or shape is not None:
            a = shape if shape is not None else Image.fromarray((union * 255).astype(np.uint8))
            img = img.convert("RGBA")
            img.putalpha(a.resize((self.w, self.h), Image.LANCZOS))
        return img
