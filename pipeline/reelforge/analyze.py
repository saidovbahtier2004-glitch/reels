"""Stage 1: analyse the source clip.

Produces a JSON document with:
  * container/stream facts (ffprobe)
  * scene cuts (ffmpeg scdet)
  * audio: tempo, beat grid, downbeats, strong onsets, loudness envelope, silences
  * per scene: focal point / subject box (motion + detail saliency), mean luma and saturation,
    and the frame band that is quietest, so text never sits on top of the subject
  * on-screen text (OCR): the persistent title and the transient words, which become
    timed captions when no speech-recognition model or .srt file is available
"""
import difflib
import re
import subprocess

import numpy as np

from .util import FFMPEG, log, probe, read_audio

# --- scenes -------------------------------------------------------------------------------------


def detect_scenes(path, duration, threshold=8.0, min_gap=0.6):
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", path, "-an", "-vf", "scale=180:-2,scdet=threshold=%g" % threshold, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    cuts = []
    for m in re.finditer(r"lavfi\.scd\.score: ([0-9.]+), lavfi\.scd\.time: ([0-9.]+)", r.stderr):
        score, t = float(m.group(1)), float(m.group(2))
        if 0.3 < t < duration - 0.3:
            if cuts and t - cuts[-1]["t"] < min_gap:
                if score > cuts[-1]["score"]:
                    cuts[-1] = {"t": t, "score": score}
                continue
            cuts.append({"t": t, "score": score})
    bounds = [0.0] + [c["t"] for c in cuts] + [duration]
    scenes = [{"index": i, "start": bounds[i], "end": bounds[i + 1]} for i in range(len(bounds) - 1)]
    return cuts, scenes


# --- audio --------------------------------------------------------------------------------------


def _stft_flux(y, n_fft=2048, hop=512):
    win = np.hanning(n_fft).astype(np.float32)
    n = 1 + max(0, (len(y) - n_fft) // hop)
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    frames = y[idx] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    logm = np.log1p(10 * mag)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    rms = np.sqrt((frames ** 2).mean(axis=1))
    return flux, rms


def _track_beats(onset, fps_env, bpm_range=(70, 180)):
    env = onset - onset.mean()
    env /= env.std() + 1e-9
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    lags = np.arange(len(ac))
    lo, hi = int(fps_env * 60 / bpm_range[1]), int(fps_env * 60 / bpm_range[0])
    bpm_at = 60 * fps_env / np.maximum(lags, 1)
    prior = np.exp(-0.5 * (np.log2(bpm_at / 120.0) / 0.9) ** 2)
    score = ac * prior
    score[:lo] = -np.inf
    score[hi + 1:] = -np.inf
    period = int(np.argmax(score))
    bpm = 60 * fps_env / period
    # Ellis (2007) dynamic programming beat tracker
    tight = 100.0
    n = len(env)
    cum = env.copy()
    back = -np.ones(n, int)
    for t in range(n):
        a, b = t - 2 * period, t - period // 2
        if b <= 0:
            continue
        prev = np.arange(max(0, a), b)
        pen = -tight * np.log((t - prev) / period) ** 2
        c = cum[prev] + pen
        k = int(np.argmax(c))
        cum[t] = env[t] + c[k]
        back[t] = prev[k]
    tail = np.arange(max(0, n - period), n)
    t = int(tail[np.argmax(cum[tail])])
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return bpm, np.array(beats[::-1])


def analyse_audio(path, duration):
    sr, hop = 22050, 512
    y = read_audio(path, sr=sr, channels=1)[:, 0]
    if len(y) < sr:
        return None
    flux, rms = _stft_flux(y, hop=hop)
    fps_env = sr / hop
    k = np.hanning(5)
    onset = np.convolve(flux, k / k.sum(), "same")
    bpm, beat_idx = _track_beats(onset, fps_env)
    beats = (beat_idx * hop / sr).tolist()
    # downbeat phase: the bar position (of 4) with the largest onset energy
    phase = int(np.argmax([onset[beat_idx[p::4]].sum() for p in range(4)])) if len(beat_idx) >= 8 else 0
    downbeats = beats[phase::4]
    # strong onsets ("hits"): local maxima above the 92nd percentile, >= 0.25 s apart
    thr = np.percentile(onset, 92)
    hits, last = [], -1.0
    for i in range(1, len(onset) - 1):
        if onset[i] > thr and onset[i] >= onset[i - 1] and onset[i] >= onset[i + 1]:
            t = i * hop / sr
            if t - last >= 0.25:
                hits.append({"t": round(t, 3), "strength": float(onset[i] / (onset.max() + 1e-9))})
                last = t
    db = 20 * np.log10(rms + 1e-9)
    loud = np.interp(np.arange(0, duration, 0.1), np.arange(len(db)) * hop / sr, db)
    silences, start = [], None
    floor = max(-45.0, np.percentile(db, 10) + 3)
    for i, v in enumerate(loud):
        if v < floor and start is None:
            start = i
        elif v >= floor and start is not None:
            if (i - start) * 0.1 >= 0.35:
                silences.append([round(start * 0.1, 2), round(i * 0.1, 2)])
            start = None
    return {
        "bpm": round(float(bpm), 2),
        "beats": [round(b, 3) for b in beats],
        "downbeats": [round(b, 3) for b in downbeats],
        "hits": hits,
        "loudness_db_10hz": [round(float(v), 1) for v in loud],
        "silences": silences,
        "mean_db": round(float(db.mean()), 1),
    }


# --- vision -------------------------------------------------------------------------------------


def _read_small_frames(path, fps, w=90, h=160):
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-i", path, "-an", "-vf", "fps=%g,scale=%d:%d:flags=area" % (fps, w, h),
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        capture_output=True,
    )
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)


def analyse_scenes_visual(path, scenes, sample_fps=4.0):
    frames = _read_small_frames(path, sample_fps)
    times = np.arange(len(frames)) / sample_fps
    H, W = frames.shape[1:3]
    ys, xs = np.mgrid[0:H, 0:W]
    bands = {"top": (0.08, 0.26), "upper": (0.24, 0.40), "lower": (0.62, 0.80), "bottom": (0.76, 0.92)}
    for sc in scenes:
        sel = frames[(times >= sc["start"]) & (times < sc["end"])]
        if len(sel) == 0:
            sel = frames[[min(len(frames) - 1, int(sc["start"] * sample_fps))]]
        f = sel.astype(np.float32) / 255.0
        luma = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        mx, mn = f.max(axis=3), f.min(axis=3)
        sat = (mx - mn) / (mx + 1e-6)
        motion = luma.std(axis=0) if len(sel) > 1 else np.zeros((H, W), np.float32)
        gy, gx = np.gradient(luma.mean(axis=0))
        detail = np.hypot(gx, gy)
        bright = luma.mean(axis=0)
        sal = 0.5 * motion / (motion.max() + 1e-6) + 0.3 * detail / (detail.max() + 1e-6) + 0.2 * bright / (bright.max() + 1e-6)
        mask = sal >= np.percentile(sal, 80)
        wts = sal * mask
        cx = float((wts * xs).sum() / wts.sum() / W)
        cy = float((wts * ys).sum() / wts.sum() / H)
        px, py = xs[mask] / W, ys[mask] / H
        box = [float(np.percentile(px, 5)), float(np.percentile(py, 5)), float(np.percentile(px, 95)), float(np.percentile(py, 95))]
        band_energy = {}
        for name, (a, b) in bands.items():
            band_energy[name] = float(sal[int(a * H):int(b * H)].mean())
        sc.update({
            "focus": [round(cx, 3), round(cy, 3)],
            "subject_box": [round(v, 3) for v in box],
            "mean_luma": round(float(luma.mean()), 3),
            "mean_sat": round(float(sat.mean()), 3),
            "motion": round(float(motion.mean()), 4),
            "band_energy": {k: round(v, 4) for k, v in band_energy.items()},
            "text_band": min(band_energy, key=band_energy.get),
        })
    return scenes


# --- OCR ----------------------------------------------------------------------------------------


def _norm(s):
    return re.sub(r"[^A-Z0-9']", "", s.upper())


def ocr_text(path, info, scenes, fps=2.0):
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        log("OCR skipped (pip install rapidocr-onnxruntime to enable)")
        return None
    W, H = info["width"], info["height"]
    scale = min(1.0, 720.0 / min(W, H))
    w, h = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-i", path, "-an", "-vf", "fps=%g,scale=%d:%d" % (fps, w, h), "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
        capture_output=True,
    )
    frames = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    engine = RapidOCR()
    samples = []
    for i, fr in enumerate(frames):
        res, _ = engine(fr)
        toks = []
        for box, text, conf in res or []:
            conf = float(conf)
            if conf < 0.6 or not text.strip():
                continue
            b = np.array(box, np.float32)
            x0, y0, x1, y1 = b[:, 0].min() / w, b[:, 1].min() / h, b[:, 0].max() / w, b[:, 1].max() / h
            toks.append({"text": text.strip(), "conf": round(conf, 3), "box": [round(float(v), 4) for v in (x0, y0, x1, y1)]})
        samples.append({"t": round(i / fps, 3), "tokens": toks})
        if i % 40 == 0:
            log("  OCR %d/%d" % (i, len(frames)))
    return {"fps": fps, "samples": samples}


def _scene_of(t, scenes):
    for sc in scenes:
        if sc["start"] <= t < sc["end"]:
            return sc["index"]
    return scenes[-1]["index"]


def derive_text(ocr, scenes):
    """Split OCR tokens into a persistent title and transient, timed words (spoken-text proxy)."""
    if not ocr:
        return {"title": None, "words": [], "caption_scenes": []}
    samples, fps = ocr["samples"], ocr["fps"]
    n = len(samples)
    # 1) static text: same normalized string in many samples of a scene
    count, per_scene = {}, {}
    for s in samples:
        si = _scene_of(s["t"], scenes)
        per_scene[si] = per_scene.get(si, 0) + 1
        for k in {(_norm(t["text"]), si) for t in s["tokens"]}:
            count[k] = count.get(k, 0) + 1
    static = {k for k, c in count.items() if c >= max(3, 0.25 * per_scene[k[1]])}
    # title: most frequent static text in the upper third with the largest glyphs
    title, best = None, 0
    for s in samples:
        for t in s["tokens"]:
            k = (_norm(t["text"]), _scene_of(s["t"], scenes))
            if k in static and t["box"][3] < 0.33 and len(k[0]) >= 4:
                c = count[k]
                if c > best:
                    title, best = t["text"], c
    if title:
        # prefer the spelling with spaces (OCR sometimes drops them)
        variants = [t["text"] for s in samples for t in s["tokens"] if _norm(t["text"]) == _norm(title)]
        title = max(variants, key=lambda v: (v.count(" "), variants.count(v)))
    # scenes whose text is all transient (no UI, keyboard or static title) carry their own burned-in captions
    static_scenes = {k[1] for k in static}
    caption_scenes = [sc["index"] for sc in scenes if sc["index"] in static_scenes]
    # 2) transient large words -> tracks
    tracks = []
    for s in samples:
        si = _scene_of(s["t"], scenes)
        if si not in static_scenes:
            continue
        for t in s["tokens"]:
            k = (_norm(t["text"]), si)
            hgt = t["box"][3] - t["box"][1]
            if k in static or hgt < 0.018 or len(k[0]) < 2 or not re.search(r"[A-Z]", k[0]):
                continue
            match = None
            for tr in tracks:
                if tr["scene"] != si or s["t"] - tr["last"] > 1.01 / fps:
                    continue
                a, b = tr["key"], k[0]
                if a == b or a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.72:
                    match = tr
                    break
            if match:
                match["last"] = s["t"]
                match["variants"].append(t)
                if len(k[0]) > len(match["key"]):
                    match["key"] = k[0]
            else:
                tracks.append({"key": k[0], "scene": si, "first": s["t"], "last": s["t"], "variants": [t]})
    words = []
    for tr in tracks:
        texts = [v["text"] for v in tr["variants"]]
        longest = max(len(_norm(x)) for x in texts)
        cands = [x for x in texts if len(_norm(x)) >= longest - 1]
        text = max(cands, key=lambda x: (x.count(" "), sum(v["conf"] for v in tr["variants"] if v["text"] == x)))
        text = _resegment(text)
        box = np.mean([v["box"] for v in tr["variants"]], axis=0).tolist()
        words.append({"text": text, "start": tr["first"], "end": tr["last"] + 1.0 / fps, "scene": tr["scene"],
                      "box": [round(float(b), 3) for b in box], "conf": round(float(np.mean([v["conf"] for v in tr["variants"]])), 3)})
    words.sort(key=lambda w: (w["start"], w["box"][1]))
    # drop words fully contained in a longer overlapping word (OCR saw "FROM" and "FROM THE FIRST")
    keep = []
    for w in words:
        nw = _norm(w["text"])
        dup = any(o is not w and nw in _norm(o["text"]) and len(_norm(o["text"])) > len(nw)
                  and o["start"] <= w["end"] and w["start"] <= o["end"] for o in words)
        if not dup:
            keep.append(w)
    return {"title": title, "words": keep, "caption_scenes": caption_scenes}


_WS = None


def _resegment(text):
    """'ANDBEFORE' -> 'AND BEFORE' using a unigram model, only for long unspaced all-caps runs."""
    global _WS
    out = []
    for part in text.split():
        core = re.sub(r"[^A-Za-z']", "", part)
        if len(core) >= 7 and core.isupper():
            try:
                if _WS is None:
                    import wordsegment
                    wordsegment.load()
                    _WS = wordsegment
                seg = _WS.segment(core)
                if 1 < len(seg) <= 5 and all(len(x) > 1 or x in ("a", "i") for x in seg):
                    trail = re.sub(r"^[A-Za-z']+", "", part)
                    part = " ".join(x.upper() for x in seg) + trail
            except ImportError:
                pass
        out.append(part)
    return " ".join(out)


# --- entry --------------------------------------------------------------------------------------


def analyse(path, scene_threshold=8.0, ocr_fps=2.0, with_ocr=True):
    info = probe(path)
    log("Source: %dx%d @ %.3f fps, %.2fs, %s/%s" % (info["width"], info["height"], info["fps"], info["duration"], info["vcodec"], info["acodec"]))
    cuts, scenes = detect_scenes(path, info["duration"], scene_threshold)
    log("Scenes: %d (cuts at %s)" % (len(scenes), ", ".join("%.2f" % c["t"] for c in cuts)))
    audio = analyse_audio(path, info["duration"]) if info["has_audio"] else None
    if audio:
        log("Audio: %.1f BPM, %d beats, %d hits, %d silences" % (audio["bpm"], len(audio["beats"]), len(audio["hits"]), len(audio["silences"])))
    analyse_scenes_visual(path, scenes)
    ocr = ocr_text(path, info, scenes, ocr_fps) if with_ocr else None
    text = derive_text(ocr, scenes)
    log("Text: title=%r, %d timed words" % (text["title"], len(text["words"])))
    info = {k: v for k, v in info.items() if k not in ("streams", "format")}
    return {"source": info, "cuts": cuts, "scenes": scenes, "audio": audio, "text": text, "ocr": ocr}
