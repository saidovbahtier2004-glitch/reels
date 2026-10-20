"""Small helpers shared by every stage: ffmpeg/ffprobe calls, easing, logging."""
import json
import math
import shutil
import subprocess
import sys
import time

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def require_tools():
    missing = [n for n, p in (("ffmpeg", FFMPEG), ("ffprobe", FFPROBE)) if not p]
    if missing:
        sys.exit(
            "Missing: %s. Install it first (Debian/Ubuntu: apt-get install ffmpeg; "
            "macOS: brew install ffmpeg; Windows: winget install ffmpeg)." % ", ".join(missing)
        )
    out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "libx264" not in out:
        sys.exit("ffmpeg was built without libx264; install a full ffmpeg build.")


_T0 = time.time()


def log(*a):
    print("[%6.1fs]" % (time.time() - _T0), *a, flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError("Command failed (%d): %s\n%s" % (r.returncode, " ".join(cmd), r.stderr[-3000:]))
    return r


def probe(path):
    r = run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", path])
    info = json.loads(r.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise ValueError("%s has no video stream" % path)
    num, den = (v.get("avg_frame_rate") or v["r_frame_rate"]).split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) in (90, 270):
        w, h = h, w
    dur = float(v.get("duration") or info["format"]["duration"])
    return {
        "path": path,
        "width": w,
        "height": h,
        "fps": fps,
        "duration": dur,
        "frames": int(v.get("nb_frames") or round(dur * fps)),
        "vcodec": v["codec_name"],
        "pix_fmt": v.get("pix_fmt"),
        "vbitrate": int(v.get("bit_rate") or 0),
        "color_space": v.get("color_space"),
        "has_audio": a is not None,
        "acodec": a["codec_name"] if a else None,
        "sample_rate": int(a["sample_rate"]) if a else None,
        "channels": int(a["channels"]) if a else 0,
        "format": info["format"],
        "streams": info["streams"],
    }


def read_audio(path, sr=48000, channels=2):
    """Decode any audio track to float32 [n, channels]."""
    import numpy as np

    r = subprocess.run(
        [FFMPEG, "-v", "error", "-i", path, "-vn", "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[-2000:])
    return np.frombuffer(r.stdout, np.float32).reshape(-1, channels).copy()


# --- easing -------------------------------------------------------------------------------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t):
    t = clamp(t)
    return t ** 3


def ease_in_out_cubic(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t, s=1.70158):
    t = clamp(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else float(x >= e1)
    return t * t * (3 - 2 * t)


def damped_spring(t, freq=4.0, decay=6.0):
    """1 at t=0 falling to 0 with a small overshoot; used for zoom punches."""
    if t < 0:
        return 0.0
    return math.exp(-decay * t) * math.cos(2 * math.pi * freq * t * 0.5)
