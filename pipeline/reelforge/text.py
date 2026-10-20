"""Kinetic typography rendered with Pillow straight into output-resolution frames.

Sprites (one per word/style) are rasterised once with stroke and soft shadow, then every frame
transforms them (scale, offset, opacity) and alpha-blends only their bounding box. Fast moves are
rendered with real motion blur: the element is sampled across the shutter interval and the
premultiplied samples are averaged before compositing.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import clamp, ease_in_cubic, ease_out_back, ease_out_cubic, ease_out_expo, lerp

FONT_CANDIDATES = {
    "black": ["/usr/share/fonts/opentype/inter/InterDisplay-Black.otf", "/usr/share/fonts/opentype/inter/Inter-Black.otf",
              "/System/Library/Fonts/Supplemental/Arial Black.ttf", "C:/Windows/Fonts/ariblk.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "bold": ["/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf", "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
}


def find_font(kind="black", override=None):
    for p in ([override] if override else []) + FONT_CANDIDATES[kind]:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError("No usable font found; pass a .ttf/.otf path in the project file (style.font)")


class SpriteCache:
    def __init__(self):
        self._c = {}
        self._fonts = {}

    def font(self, path, size):
        k = (path, size)
        if k not in self._fonts:
            self._fonts[k] = ImageFont.truetype(path, size)
        return self._fonts[k]

    def word(self, text, font_path, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0),
             shadow=0.0, box=None, box_pad=0.18, tracking=0.0):
        """RGBA sprite (numpy float32 premultiplied, 0..1) plus the anchor of its text box centre."""
        key = (text, font_path, size, fill, stroke, stroke_fill, shadow, box, box_pad, tracking)
        if key in self._c:
            return self._c[key]
        font = self.font(font_path, size)
        asc, desc = font.getmetrics()
        widths = [font.getlength(ch) for ch in text]
        track = tracking * size
        tw = sum(widths) + track * max(0, len(text) - 1)
        th = asc + desc
        pad = int(size * (box_pad + 0.1)) + stroke + int(shadow * size * 2)
        W, H = int(tw + 2 * pad), int(th + 2 * pad)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if box is not None:
            bp = int(size * box_pad)
            d.rounded_rectangle([pad - bp, pad - bp * 0.55, pad + tw + bp, pad + th + bp * 0.35],
                                radius=int(size * 0.16), fill=box)
        x = pad
        for ch, wch in zip(text, widths):
            d.text((x, pad), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
            x += wch + track
        if shadow > 0:
            a = img.split()[3]
            sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
            sh.putalpha(a.filter(ImageFilter.GaussianBlur(shadow * size)).point(lambda v: int(v * 0.75)))
            off = int(size * 0.05)
            base = Image.new("RGBA", img.size, (0, 0, 0, 0))
            base.alpha_composite(sh, (0, off))
            base.alpha_composite(img)
            img = base
        arr = np.asarray(img, np.float32) / 255.0
        arr[..., :3] *= arr[..., 3:4]
        out = (arr, (W / 2.0, pad + th * 0.52), tw, th)
        self._c[key] = out
        return out


def _scaled(sprite, s):
    arr = sprite
    if abs(s - 1.0) < 1e-3:
        return arr
    h, w = arr.shape[:2]
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    chans = [Image.fromarray(np.ascontiguousarray(arr[..., i])).resize((nw, nh), Image.BILINEAR) for i in range(4)]
    return np.stack([np.asarray(c) for c in chans], -1)


class Layer:
    """Collects premultiplied RGBA draws; materialises only the union bounding box."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.items = []
        self._mat = None

    def _add(self, arr, x0, y0):
        h, w = arr.shape[:2]
        fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(self.W, x0 + w), min(self.H, y0 + h)
        if fx1 > fx0 and fy1 > fy0:
            self.items.append((arr[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0], fx0, fy0))
            self._mat = None

    def draw(self, sprite, anchor, cx, cy, scale=1.0, opacity=1.0, sx=1.0):
        if opacity <= 0.003 or scale <= 0.01:
            return
        arr = _scaled(sprite, scale)
        ax = anchor[0] * scale
        if abs(sx - 1.0) > 1e-3:
            h, w = arr.shape[:2]
            nw = max(1, int(round(w * sx)))
            arr = np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., i])).resize((nw, h), Image.BILINEAR)) for i in range(4)], -1)
            ax *= sx
        if opacity < 1:
            arr = arr * opacity
        self._add(arr, int(round(cx - ax)), int(round(cy - anchor[1] * scale)))

    def rect(self, x0, y0, x1, y1, color, opacity=1.0):
        x0, y0, x1, y1 = [int(round(v)) for v in (x0, y0, x1, y1)]
        if x1 <= x0 or y1 <= y0 or opacity <= 0:
            return
        c = np.array([color[0] / 255 * opacity, color[1] / 255 * opacity, color[2] / 255 * opacity, opacity], np.float32)
        self._add(np.broadcast_to(c, (y1 - y0, x1 - x0, 4)), x0, y0)

    def materialize(self):
        """-> (buf HxWx4 premultiplied, (x0, y0, x1, y1)) or None."""
        if not self.items:
            return None
        if self._mat is None:
            x0 = min(i[1] for i in self.items)
            y0 = min(i[2] for i in self.items)
            x1 = max(i[1] + i[0].shape[1] for i in self.items)
            y1 = max(i[2] + i[0].shape[0] for i in self.items)
            buf = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
            for arr, ax, ay in self.items:
                dst = buf[ay - y0:ay - y0 + arr.shape[0], ax - x0:ax - x0 + arr.shape[1]]
                dst *= (1 - arr[..., 3:4])
                dst += arr
            self._mat = (buf, (x0, y0, x1, y1))
        return self._mat


def composite(frame, layer):
    """frame: uint8 HxWx3 (modified in place); layer: Layer or (buf, box)."""
    m = layer.materialize() if isinstance(layer, Layer) else layer
    if m is None:
        return frame
    src, (x0, y0, x1, y1) = m
    dst = frame[y0:y1, x0:x1].astype(np.float32) * (1.0 / 255.0)
    out = dst * (1 - src[..., 3:4]) + src[..., :3]
    frame[y0:y1, x0:x1] = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return frame


def motion_blurred(W, H, fn, t, shutter, samples):
    """Average `samples` evaluations of fn(layer, t_k) across the shutter interval -> (buf, box) or None."""
    if samples <= 1:
        L = Layer(W, H)
        fn(L, t)
        return L.materialize()
    mats = []
    for k in range(samples):
        L = Layer(W, H)
        fn(L, t - shutter * (0.5 - (k + 0.5) / samples))
        m = L.materialize()
        if m is not None:
            mats.append(m)
    if not mats:
        return None
    x0 = min(m[1][0] for m in mats); y0 = min(m[1][1] for m in mats)
    x1 = max(m[1][2] for m in mats); y1 = max(m[1][3] for m in mats)
    acc = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
    for buf, (bx0, by0, bx1, by1) in mats:
        acc[by0 - y0:by1 - y0, bx0 - x0:bx1 - x0] += buf
    acc /= samples
    return acc, (x0, y0, x1, y1)


# --- elements -----------------------------------------------------------------------------------


class Captions:
    """Word-by-word animated captions: each word pops in on its timestamp, the newest word is
    boxed in the accent colour, emphasised words are bigger and red."""

    def __init__(self, lines, W, H, style, sprites, band_for_time):
        self.lines = lines
        self.W, self.H = W, H
        self.st = style
        self.sp = sprites
        self.band_for_time = band_for_time
        self.font = find_font("black", style.get("font"))
        self.size = int(W * style.get("caption_size", 0.082))
        self._layouts = {}

    def _layout(self, li):
        if li in self._layouts:
            return self._layouts[li]
        line = self.lines[li]
        font = self.sp.font(self.font, self.size)
        space = font.getlength(" ") * 1.15 + self.size * 0.24
        maxw = self.W * 0.84
        rows, row, roww = [], [], 0.0
        for w in line["words"]:
            sz = self.size * (1.14 if w["emph"] else 1.0)
            ww = self.sp.font(self.font, int(sz)).getlength(w["text"])
            if row and roww + space + ww > maxw:
                rows.append((row, roww))
                row, roww = [], 0.0
            row.append((w, ww, sz))
            roww += (space if len(row) > 1 else 0) + ww
        if row:
            rows.append((row, roww))
        placed = []
        lh = self.size * 1.18
        for ri, (row, roww) in enumerate(rows):
            x = (self.W - roww) / 2
            for w, ww, sz in row:
                placed.append({"w": w, "cx": x + ww / 2, "row": ri, "size": int(sz)})
                x += ww + space
        lay = {"words": placed, "rows": len(rows), "lh": lh}
        self._layouts[li] = lay
        return lay

    def active_line(self, t):
        for i, ln in enumerate(self.lines):
            if ln["start"] - 0.05 <= t < ln["end"] + 0.15:
                return i
        return None

    def draw(self, L, t):
        li = self.active_line(t)
        if li is None:
            return
        ln = self.lines[li]
        lay = self._layout(li)
        band = self.band_for_time(ln["start"])
        cy0 = self.H * band - (lay["rows"] - 1) * lay["lh"] / 2
        exit_k = clamp((t - ln["end"]) / 0.15)
        accent = tuple(self.st.get("accent", (255, 45, 45)))
        words = lay["words"]
        current = None
        for i, pw in enumerate(words):
            if pw["w"]["t"] <= t:
                current = i
        for i, pw in enumerate(words):
            w = pw["w"]
            age = t - w["t"]
            if age < 0:
                continue
            k = clamp(age / 0.2)
            s = 0.55 + 0.45 * ease_out_back(k, 2.2)
            dy = (1 - ease_out_cubic(k)) * self.size * 0.45
            op = clamp(age / 0.08)
            if exit_k > 0:
                s *= 1 - 0.25 * ease_in_cubic(exit_k)
                op *= 1 - exit_k
            is_cur = i == current
            if is_cur:
                fill, box = (255, 255, 255), accent
            elif w["emph"]:
                fill, box = accent, None
            else:
                fill, box = (255, 255, 255), None
            spr, anc, _, _ = self.sp.word(w["text"], self.font, pw["size"], fill=fill, stroke=0 if box else max(2, pw["size"] // 22),
                                          stroke_fill=(0, 0, 0), shadow=0.06, box=box)
            cy = cy0 + pw["row"] * lay["lh"] + dy
            L.draw(spr, anc, pw["cx"], cy, scale=s, opacity=op)

    def blur_samples(self, t):
        li = self.active_line(t)
        if li is None:
            return 1
        for w in self.lines[li]["words"]:
            if 0 <= t - w["t"] < 0.16:
                return 5
        return 1


class HookTitle:
    """Stacked title; each word slams in from 2.6x scale with motion blur, accent bar wipes under it."""

    def __init__(self, text, start, duration, W, H, style, sprites, band_y):
        self.words = text.upper().split()
        self.start, self.dur = start, duration
        self.W, self.H, self.st, self.sp = W, H, style, sprites
        self.font = find_font("black", style.get("font"))
        self.band_y = band_y
        self.rows = self._rows()

    def _rows(self):
        size = int(self.W * self.st.get("title_size", 0.105))
        rows, cur = [], []
        for w in self.words:
            test = " ".join(cur + [w])
            if cur and self.sp.font(self.font, size).getlength(test) > self.W * 0.82:
                rows.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            rows.append(" ".join(cur))
        fitted = []
        for r in rows:
            s = size
            while self.sp.font(self.font, s).getlength(r) > self.W * 0.86 and s > 40:
                s -= 4
            fitted.append((r, s))
        return fitted

    def hit_times(self):
        return [self.start + i * 0.22 for i in range(len(self.rows))]

    def draw(self, L, t):
        lt = t - self.start
        if lt < 0 or lt > self.dur + 0.4:
            return
        accent = tuple(self.st.get("accent", (255, 45, 45)))
        out_k = clamp((lt - self.dur) / 0.35)
        total_h = sum(s * 1.05 for _, s in self.rows)
        y = self.H * self.band_y - total_h / 2
        for i, (row, s) in enumerate(self.rows):
            k = clamp((lt - i * 0.22) / 0.28)
            if k <= 0:
                y += s * 1.05
                continue
            e = ease_out_expo(k)
            scale = lerp(2.6, 1.0, e)
            op = clamp(k * 3)
            dy = -ease_in_cubic(out_k) * self.H * 0.08
            op *= 1 - out_k
            hl = i == len(self.rows) - 1
            spr, anc, tw, th = self.sp.word(row, self.font, s, fill=(255, 255, 255), box=accent if hl else None,
                                            stroke=0 if hl else max(3, s // 24), shadow=0.08, box_pad=0.12)
            L.draw(spr, anc, self.W / 2, y + s * 0.52 + dy, scale=scale, opacity=op)
            y += s * 1.05

    def blur_samples(self, t):
        lt = t - self.start
        for i in range(len(self.rows)):
            if 0 <= lt - i * 0.22 < 0.3:
                return 7
        if self.dur <= lt <= self.dur + 0.35:
            return 5
        return 1


class ProgressBar:
    def __init__(self, duration, W, H, style):
        self.d, self.W, self.H = duration, W, H
        self.c = tuple(style.get("accent", (255, 45, 45)))

    def draw(self, L, t):
        h = max(6, int(self.H * 0.004))
        y = self.H - h - int(self.H * 0.012)
        L.rect(0, y, self.W, y + h, (255, 255, 255), 0.18)
        L.rect(0, y, self.W * clamp(t / self.d), y + h, self.c, 0.95)
