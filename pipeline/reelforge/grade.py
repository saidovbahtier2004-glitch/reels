"""Colour correction and look, applied at source resolution (cheap) before the upscale.

Per scene: highlight-safe exposure normalisation, filmic S-curve, split toning (cool shadows,
warm highlights), global saturation with an extra push on reds (the reference's accent colour),
and a soft vignette.
"""
import numpy as np


def scene_params(scene, strength=1.0, look=None):
    look = look or {}
    mean = max(1e-3, scene.get("mean_luma", 0.2))
    target = look.get("target_luma", 0.2)
    gain = float(np.clip((target / mean) ** 0.55, 0.9, 1.35))
    return {
        "gain": 1 + (gain - 1) * strength,
        "contrast": look.get("contrast", 0.32) * strength,
        "black": look.get("black_point", 0.012),
        "sat": 1 + (look.get("saturation", 1.12) - 1) * strength,
        "red": look.get("red_boost", 0.22) * strength,
        "split": look.get("split_tone", 0.025) * strength,
        "vignette": look.get("vignette", 0.28) * strength,
    }


def _curves(p):
    x = np.linspace(0, 1, 256, dtype=np.float32)
    g = p["gain"]
    y = x * g / (1 + (g - 1) * x)  # exposure with highlight roll-off (1 -> 1)
    s = y * y * (3 - 2 * y)
    y = y + (s - y) * p["contrast"]
    y = p["black"] + y * (1 - p["black"])
    sh = (1 - y) ** 2 * p["split"]
    hi = y ** 2 * p["split"]
    r = y - sh * 0.6 + hi * 0.8
    gch = y + sh * 0.15 + hi * 0.25
    b = y + sh * 1.0 - hi * 0.6
    return np.clip(np.stack([r, gch, b]), 0, 1).astype(np.float32)


class Grader:
    def __init__(self, scenes, w, h, strength=1.0, look=None):
        self.params = [scene_params(s, strength, look) for s in scenes]
        self.luts = [_curves(p) for p in self.params]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 * 0.8 + ((yy - h / 2) / (h / 2)) ** 2)
        self.vmask = np.clip(d - 0.55, 0, None) ** 1.6

    def apply(self, frame, scene_index):
        p, lut = self.params[scene_index], self.luts[scene_index]
        x = np.empty(frame.shape, np.float32)
        for c in range(3):
            x[..., c] = lut[c][frame[..., c]]
        lum = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        redness = np.clip((x[..., 0] - np.maximum(x[..., 1], x[..., 2])) * 3.0, 0, 1)
        sat = p["sat"] + p["red"] * redness
        x = lum[..., None] + (x - lum[..., None]) * sat[..., None]
        if p["vignette"] > 0:
            x *= (1 - p["vignette"] * self.vmask)[..., None]
        return np.clip(x * 255 + 0.5, 0, 255).astype(np.uint8)
