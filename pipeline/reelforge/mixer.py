"""Audio: original track + synthesized SFX + optional music (beat-aligned, ducked under the source)."""
import numpy as np

from .sfx import SR, Bank
from .util import log, read_audio


def _db(g):
    return 10 ** (g / 20.0)


def _envelope(x, win):
    p = np.convolve((x ** 2).mean(axis=1), np.ones(win) / win, "same")
    return np.sqrt(p)


def mix(plan, out_raw):
    dur = plan["duration"]
    n = int(round(dur * SR))
    try:
        base = read_audio(plan["source"], SR, 2)
    except RuntimeError:
        base = np.zeros((0, 2), np.float32)
    voice = np.zeros((n, 2), np.float32)
    voice[:min(n, len(base))] = base[:n]
    bus = voice.copy()

    bank = Bank()
    placed = 0
    for ev in plan["sfx"]:
        clip = bank.get(ev["name"]) * _db(ev.get("gain_db", -10))
        L = len(clip)
        if ev.get("align") == "center":
            s = int(round(ev["t"] * SR)) - L // 2
        elif ev.get("align") == "end":
            s = int(round(ev["t"] * SR)) - L
        else:
            s = int(round(ev["t"] * SR))
        a, b = max(0, s), min(n, s + L)
        if b > a:
            bus[a:b] += clip[a - s:b - s]
            placed += 1

    m = plan.get("music") or {}
    if m.get("path"):
        music = read_audio(m["path"], SR, 2)
        offset = int(m.get("offset", 0.0) * SR)
        music = music[offset:]
        if len(music) < n:
            music = np.tile(music, (int(np.ceil(n / max(1, len(music)))), 1))
        music = music[:n] * _db(m.get("gain_db", -14))
        if m.get("duck", True):
            env = _envelope(voice, int(0.08 * SR))
            norm = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
            gain = 1 - m.get("duck_depth", 0.65) * norm
            k = int(0.25 * SR)
            gain = np.convolve(gain, np.ones(k) / k, "same")
            music *= gain[:, None]
        fi, fo = int(1.0 * SR), int(2.0 * SR)
        music[:fi] *= np.linspace(0, 1, fi)[:, None]
        music[-fo:] *= np.linspace(1, 0, fo)[:, None]
        bus += music
        log("Music mixed: %s (%.1f dB, ducking=%s)" % (m["path"], m.get("gain_db", -14), m.get("duck", True)))

    # gentle safety limiter (loudness is normalised by ffmpeg loudnorm afterwards)
    knee = 0.8
    mag = np.abs(bus)
    over = mag > knee
    bus[over] = np.sign(bus[over]) * (knee + (1 - knee) * np.tanh((mag[over] - knee) / (1 - knee)))
    bus.astype(np.float32).tofile(out_raw)
    log("Audio mix: %d SFX placed, %.2fs, peak %.2f" % (placed, n / SR, float(np.abs(bus).max())))
    return SR
