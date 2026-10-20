"""Procedural sound effects (no samples, no licences): whoosh, impact, riser, glitch, pop, tick.

Every generator returns float32 stereo [n, 2] at the given sample rate, peak about -3 dBFS.
"""
import numpy as np

SR = 48000


def _rng(seed):
    return np.random.default_rng(seed)


def _norm(x, peak=0.7):
    m = np.abs(x).max()
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


def _onepole_lp(x, cutoff, sr=SR):
    """Time-varying one-pole low-pass. cutoff: scalar or per-sample array (Hz)."""
    cutoff = np.broadcast_to(np.asarray(cutoff, np.float64), x.shape[:1])
    a = np.exp(-2 * np.pi * cutoff / sr)
    y = np.empty_like(x)
    acc = np.zeros(x.shape[1:]) if x.ndim > 1 else 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def _bandpass_sweep(noise, f0, f1, sr=SR):
    n = len(noise)
    f = np.geomspace(f0, f1, n)
    lp = _onepole_lp(noise, f * 1.6, sr)
    return lp - _onepole_lp(lp, f * 0.5, sr)


def whoosh(dur=0.55, seed=1, sr=SR, up=True):
    n = int(dur * sr)
    t = np.linspace(0, 1, n)
    noise = _rng(seed).standard_normal((n, 2))
    sw = _bandpass_sweep(noise, 300 if up else 4000, 4000 if up else 300, sr)
    env = np.sin(np.pi * t ** 0.7) ** 2
    pan = np.stack([1 - 0.6 * t, 0.4 + 0.6 * t], 1)
    return _norm(sw * env[:, None] * pan, 0.6)


def impact(dur=0.9, seed=2, sr=SR):
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = 32 + 90 * np.exp(-t * 18)
    sub = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 4.5)
    click = _rng(seed).standard_normal(n) * np.exp(-t * 90)
    body = _onepole_lp(_rng(seed + 1).standard_normal(n), 900) * np.exp(-t * 14) * 3
    x = np.tanh(1.8 * (sub + 0.35 * click + 0.5 * body))
    return _norm(np.stack([x, x], 1), 0.75)


def riser(dur=1.6, seed=3, sr=SR):
    n = int(dur * sr)
    t = np.linspace(0, 1, n)
    noise = _rng(seed).standard_normal((n, 2))
    sw = _bandpass_sweep(noise, 200, 7000, sr)
    tone = np.sin(2 * np.pi * np.cumsum(np.geomspace(120, 900, n)) / sr)
    env = t ** 2.2 * (1 - smooth_tail(t, 0.97))
    x = (sw + 0.25 * tone[:, None]) * env[:, None]
    return _norm(x, 0.5)


def smooth_tail(t, start):
    return np.clip((t - start) / (1 - start), 0, 1)


def glitch(dur=0.25, seed=4, sr=SR):
    n = int(dur * sr)
    r = _rng(seed)
    x = np.zeros(n)
    i = 0
    while i < n:
        seg = int(r.integers(sr // 200, sr // 40))
        f = r.choice([180, 360, 720, 1440, 2880])
        tt = np.arange(min(seg, n - i)) / sr
        x[i:i + seg] = np.sign(np.sin(2 * np.pi * f * tt)) * r.uniform(0.3, 1)
        i += seg + int(r.integers(0, sr // 100))
    x = np.round(x * 6) / 6
    return _norm(np.stack([x, np.roll(x, 37)], 1), 0.35)


def pop(dur=0.12, freq=900, sr=SR):
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = freq * (1 + 0.8 * np.exp(-t * 60))
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 38)
    return _norm(np.stack([x, x], 1), 0.45)


def tick(sr=SR):
    n = int(0.03 * sr)
    t = np.arange(n) / sr
    x = _rng(5).standard_normal(n) * np.exp(-t * 400)
    return _norm(np.stack([x, x], 1), 0.3)


LIBRARY = {"whoosh": whoosh, "whoosh_down": lambda: whoosh(up=False, seed=7), "impact": impact,
           "riser": riser, "glitch": glitch, "pop": pop, "tick": tick}


class Bank:
    def __init__(self):
        self._cache = {}

    def get(self, name):
        if name not in self._cache:
            self._cache[name] = LIBRARY[name]()
        return self._cache[name]
