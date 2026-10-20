"""Stage 3: render every output frame and encode the final MP4.

Decode (ffmpeg, once) -> grade at source res -> virtual camera (zoom, punch, shake, whip) sampled
over the shutter for true motion blur -> single Lanczos resample to output size -> transition
effects (flash, RGB-split glitch) -> kinetic text layers -> ffmpeg encode (one generation, BT.709).
"""
import collections
import math
import multiprocessing as mp
import os
import subprocess

import numpy as np
from PIL import Image

from . import text as tx
from .grade import Grader
from .mixer import mix
from .plan import write_srt
from .util import FFMPEG, clamp, ease_in_cubic, ease_in_out_cubic, ease_out_cubic, lerp, log

# --- camera model -------------------------------------------------------------------------------


class Camera:
    def __init__(self, plan):
        self.p = plan
        self.cam = plan["camera"]
        self.trans = plan["transitions"]
        self.punches = plan["punches"]
        self.shakes = plan["shakes"]

    def scene_index(self, t):
        for i, c in enumerate(self.cam):
            if c["start"] <= t < c["end"]:
                return i
        return len(self.cam) - 1 if t >= self.cam[-1]["start"] else 0

    def state(self, t):
        """-> zoom, focus x/y (0..1 of source), extra x offset (fraction of width), shake x/y."""
        i = self.scene_index(t)
        c = self.cam[i]
        u = clamp((t - c["start"]) / max(1e-6, c["end"] - c["start"]))
        z = lerp(c["zoom_from"], c["zoom_to"], ease_in_out_cubic(u))
        fx, fy = c["focus"]
        for p in self.punches:
            d = t - p["t"]
            if -0.06 <= d < 0.6:
                rise = clamp((d + 0.06) / 0.06)
                z *= 1 + p["amp"] * (rise if d < 0 else math.exp(-d * 7.0) * (1 + 0.15 * math.sin(d * 30)))
        ox = 0.0
        for tr in self.trans:
            d, h = t - tr["t"], tr["half"]
            if not -h <= d < h:
                continue
            if tr["type"] == "zoom_blur":
                z *= 1 + 0.55 * (ease_in_cubic((d + h) / h) if d < 0 else 1 - ease_out_cubic(d / h))
            elif tr["type"] == "whip":
                ox = 0.85 * ease_in_cubic((d + h) / h) if d < 0 else -0.85 * (1 - ease_out_cubic(d / h))
            elif tr["type"] == "punch" and d >= 0:
                z *= 1 + 0.12 * (1 - ease_out_cubic(d / h))
            elif tr["type"] == "glitch":
                z *= 1 + 0.06 * (1 - abs(d) / h)
        sx = sy = 0.0
        for s in self.shakes:
            d = t - s["t"]
            if 0 <= d < 0.45:
                a = s["amp"] * math.exp(-d * 9)
                sx += a * math.sin(d * 97 + s["t"] * 13)
                sy += a * math.cos(d * 83 + s["t"] * 7)
        return z, fx, fy, ox, sx, sy

    def fx(self, t):
        """Per-frame image effects: flash amount and glitch intensity."""
        flash = glitch = 0.0
        for tr in self.trans:
            d = t - tr["t"]
            if tr["type"] in ("zoom_blur", "punch") and -0.03 <= d < 0.14:
                flash = max(flash, (0.55 if tr["type"] == "zoom_blur" else 0.3) * (1 - clamp(d / 0.14)))
            if tr["type"] == "glitch" and abs(d) < tr["half"]:
                glitch = max(glitch, 1 - abs(d) / tr["half"])
            if tr["type"] == "whip" and abs(d) < 0.05:
                flash = max(flash, 0.12)
        return flash, glitch


# --- frame renderer (runs in worker processes) --------------------------------------------------

_G = {}


def _init_worker(plan):
    _G["plan"] = plan
    _G["cam"] = Camera(plan)
    sw, sh = plan["src_w"], plan["src_h"]
    _G["grader"] = Grader(plan["grade"]["scenes"], sw, sh, plan["grade"]["strength"], plan["grade"]["look"])
    W, H = plan["width"], plan["height"]
    sprites = tx.SpriteCache()
    bands = plan["captions"]["bands"]

    def band_for_time(t):
        for b in bands:
            if b["start"] <= t < b["end"]:
                return b["y"]
        return bands[-1]["y"]

    _G["captions"] = tx.Captions(plan["captions"]["lines"], W, H, plan["style"], sprites, band_for_time) if plan["captions"]["lines"] else None
    tt = plan.get("title")
    _G["title"] = tx.HookTitle(tt["text"], tt["start"], tt["duration"], W, H, plan["style"], sprites, tt["band_y"]) if tt else None
    _G["progress"] = tx.ProgressBar(plan["duration"], W, H, plan["style"]) if plan.get("progress_bar") else None
    # base crop (reframes non-9:16 sources around the subject)
    aspect = W / H
    bw = min(sw, sh * aspect)
    _G["base"] = (bw, bw / aspect)


def _crop_box(state, sw, sh, pad):
    z, fx, fy, ox, sx, sy = state
    bw0, bh0 = _G["base"]
    bw, bh = bw0 / z, bh0 / z
    cx = min(max(fx * sw, bw / 2), sw - bw / 2)
    cy = min(max(fy * sh, bh / 2), sh - bh / 2)
    cx += (ox + sx) * sw
    cy += sy * sh
    cx = min(max(cx, bw / 2 - pad[0]), sw + pad[0] - bw / 2)
    cy = min(max(cy, bh / 2 - pad[1]), sh + pad[1] - bh / 2)
    return (cx - bw / 2 + pad[0], cy - bh / 2 + pad[1], cx + bw / 2 + pad[0], cy + bh / 2 + pad[1])


def render_frame(args):
    idx, raw = args
    plan = _G["plan"]
    fps, W, H = plan["fps"], plan["width"], plan["height"]
    sw, sh = plan["src_w"], plan["src_h"]
    t = idx / fps
    cam = _G["cam"]
    si = cam.scene_index(t)
    src = np.frombuffer(raw, np.uint8).reshape(sh, sw, 3)
    graded = _G["grader"].apply(src, min(si, len(plan["grade"]["scenes"]) - 1))

    shutter = plan["motion_blur"]["shutter_deg"] / 360.0 / fps
    s0, s1 = cam.state(t - shutter / 2), cam.state(t + shutter / 2)
    motion = max(abs(math.log(s1[0] / s0[0])) / 0.004,
                 (abs(s1[3] - s0[3]) + abs(s1[4] - s0[4]) + abs(s1[5] - s0[5])) / 0.0025)
    n = int(clamp(math.ceil(motion), 1, plan["motion_blur"]["max_samples"]))
    states = [cam.state(t)] if n == 1 else [cam.state(t - shutter * (0.5 - (k + 0.5) / n)) for k in range(n)]

    need_pad = any(abs(s[3]) > 1e-4 or abs(s[4]) > 1e-4 or abs(s[5]) > 1e-4 for s in states)
    if need_pad:
        px, py = int(sw * 0.9), int(sh * 0.05)
        img = Image.fromarray(np.pad(graded, ((py, py), (px, px), (0, 0)), mode="reflect"))
        pad = (px, py)
    else:
        img, pad = Image.fromarray(graded), (0, 0)

    if n == 1:
        frame = np.asarray(img.resize((W, H), Image.LANCZOS, box=_crop_box(states[0], sw, sh, pad))).copy()
    else:
        acc = np.zeros((H, W, 3), np.float32)
        for s in states:
            acc += np.asarray(img.resize((W, H), Image.BICUBIC, box=_crop_box(s, sw, sh, pad)), np.float32)
        frame = np.clip(acc / n + 0.5, 0, 255).astype(np.uint8)

    flash, glitch = cam.fx(t)
    if glitch > 0:
        rng = np.random.default_rng(idx)
        shift = int(W * 0.018 * glitch)
        frame[..., 0] = np.roll(frame[..., 0], -shift, axis=1)
        frame[..., 2] = np.roll(frame[..., 2], shift, axis=1)
        for _ in range(int(3 + 6 * glitch)):
            y0 = int(rng.integers(0, H - 40))
            hh = int(rng.integers(20, max(21, int(H * 0.05))))
            frame[y0:y0 + hh] = np.roll(frame[y0:y0 + hh], int(rng.integers(-1, 2) * W * 0.06 * glitch), axis=1)
    if flash > 0:
        f = frame.astype(np.float32)
        frame = np.clip(f + (255 - f) * flash, 0, 255).astype(np.uint8)

    if _G["title"] is not None:
        tl = _G["title"]
        tx.composite(frame, tx.motion_blurred(W, H, tl.draw, t, 1.0 / fps, tl.blur_samples(t)))
    if _G["captions"] is not None:
        cp = _G["captions"]
        tx.composite(frame, tx.motion_blurred(W, H, cp.draw, t, 0.7 / fps, cp.blur_samples(t)))
    if _G["progress"] is not None:
        L = tx.Layer(W, H)
        _G["progress"].draw(L, t)
        tx.composite(frame, L)
    return frame.tobytes()


# --- pipeline -----------------------------------------------------------------------------------


def _decoder(plan):
    vf = "scale=in_color_matrix=bt709:in_range=tv:out_range=full:flags=accurate_rnd+full_chroma_int,format=rgb24"
    if abs(plan["fps"] - plan["src_fps"]) > 1e-3:
        vf = "fps=%g," % plan["fps"] + vf
    return subprocess.Popen([FFMPEG, "-v", "error", "-i", plan["source"], "-an", "-sn", "-vf", vf, "-pix_fmt", "rgb24",
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=10 ** 8)


def _frames(dec, plan, limit):
    size = plan["src_w"] * plan["src_h"] * 3
    i = 0
    while limit is None or i < limit:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        yield i, buf
        i += 1


def render(plan, out_path, workdir, workers=None, limit_frames=None, start_frame=0):
    os.makedirs(workdir, exist_ok=True)
    W, H, fps = plan["width"], plan["height"], plan["fps"]
    audio_raw = os.path.join(workdir, "mix.f32")
    sr = mix(plan, audio_raw)
    srt = os.path.join(workdir, "captions.srt")
    has_subs = bool(plan["captions"]["lines"])
    if has_subs:
        write_srt(plan["captions"]["lines"], srt)

    enc = plan["encode"]
    total = int(round(plan["duration"] * fps)) if limit_frames is None else limit_frames
    vcodec = ["-c:v", "libx264", "-preset", enc["preset"], "-crf", str(enc["crf"]), "-profile:v", "high", "-level:v", "5.2",
              "-x264-params", "aq-mode=3:deblock=-1,-1"]
    if enc["codec"] == "hevc":
        vcodec = ["-c:v", "libx265", "-preset", enc["preset"], "-crf", str(enc["crf"]), "-tag:v", "hvc1",
                  "-x265-params", "log-level=error"]
    cmd = [FFMPEG, "-y", "-v", "error", "-stats",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "%g" % fps, "-i", "-",
           "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", audio_raw]
    if has_subs:
        cmd += ["-i", srt]
    vf = ("unsharp=5:5:0.45:5:5:0.0,noise=c0s=4:c0f=t+u,"
          "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p")
    af = "loudnorm=I=%g:TP=-1.0:LRA=11,aresample=48000" % enc["loudness_lufs"]
    cmd += ["-map", "0:v", "-map", "1:a"] + (["-map", "2:s"] if has_subs else [])
    cmd += ["-vf", vf] + vcodec + ["-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                                   "-color_trc", "bt709", "-color_range", "tv", "-r", "%g" % fps]
    cmd += ["-af", af, "-c:a", "aac", "-b:a", enc["audio_bitrate"], "-ar", "48000"]
    if has_subs:
        cmd += ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=Captions"]
    if limit_frames is not None:
        cmd += ["-t", "%.3f" % (limit_frames / fps)]
    cmd += ["-movflags", "+faststart", "-metadata", "title=ReelForge render", out_path]
    log("Encoding %dx%d @ %g fps, %d frames -> %s" % (W, H, fps, total, out_path))
    enc_log = open(os.path.join(workdir, "ffmpeg_encode.log"), "w")
    encp = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=enc_log)

    dec = _decoder(plan)
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    done = 0
    try:
        with mp.get_context("fork").Pool(workers, initializer=_init_worker, initargs=(plan,)) as pool:
            # bounded in-flight window: decoding is far faster than rendering, so an unbounded
            # imap would queue every decoded frame in RAM
            pending = collections.deque()
            frames = _frames(dec, plan, limit_frames)
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < workers * 2:
                    item = next(frames, None)
                    if item is None:
                        exhausted = True
                    else:
                        pending.append(pool.apply_async(render_frame, (item,)))
                if not pending:
                    break
                encp.stdin.write(pending.popleft().get())
                done += 1
                if done % 60 == 0 or done == total:
                    log("  frame %d/%d (%.0f%%)" % (done, total, 100.0 * done / max(1, total)))
    finally:
        encp.stdin.close()
        rc = encp.wait()
        enc_log.close()
        dec.kill()
        err = open(enc_log.name, errors="replace").read()
    if rc != 0:
        raise RuntimeError("ffmpeg encode failed (%d):\n%s" % (rc, err[-3000:]))
    log("Rendered %d frames" % done)
    return done
