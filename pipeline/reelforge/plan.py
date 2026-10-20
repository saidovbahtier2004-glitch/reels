"""Stage 2: turn the analysis (+ optional project settings) into a concrete edit decision list.

Everything the renderer does is listed here with a timestamp, so the plan JSON can be inspected
or hand-edited and rendered again.
"""
import json
import os
import re

from .util import log

BANDS = {"top": 0.17, "upper": 0.275, "lower": 0.71, "bottom": 0.845}
EMPH_RE = re.compile(r"^\*")


# --- captions -----------------------------------------------------------------------------------


def _srt_time(s):
    h, m, rest = s.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def load_captions(path):
    """.json: {"lines": [{"start","end","words": [[t, "WORD"], ...]}]} (word-level, '*' = emphasis)
       .srt : cues; words get times proportional to their length inside each cue."""
    if path.endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        lines = []
        for ln in data["lines"]:
            words = [{"t": float(t), "text": EMPH_RE.sub("", w), "emph": w.startswith("*")} for t, w in ln["words"]]
            lines.append({"start": float(ln.get("start", words[0]["t"])), "end": float(ln["end"]), "words": words})
        return lines
    text = open(path, encoding="utf-8-sig").read()
    lines = []
    for block in re.split(r"\n\s*\n", text.strip()):
        rows = [r for r in block.splitlines() if r.strip()]
        tl = next((r for r in rows if "-->" in r), None)
        if not tl:
            continue
        a, b = [_srt_time(x.split()[0]) for x in tl.split("-->")]
        body = " ".join(rows[rows.index(tl) + 1:])
        toks = body.split()
        total = sum(len(w) + 2 for w in toks) or 1
        acc, words = 0, []
        for w in toks:
            words.append({"t": a + (b - a) * 0.85 * acc / total, "text": EMPH_RE.sub("", w).upper(), "emph": w.startswith("*")})
            acc += len(w) + 2
        lines.append({"start": a, "end": b, "words": words})
    return lines


def captions_from_ocr(words, max_words=4, max_chars=22):
    """Group OCR-timed on-screen words into caption lines (fallback when no transcript exists)."""
    lines, cur = [], []
    for w in words:
        toks = w["text"].upper().split()
        for k, tok in enumerate(toks):
            t = w["start"] + k * 0.12
            new_line = cur and (len(cur) >= max_words or sum(len(x["text"]) + 1 for x in cur) + len(tok) > max_chars
                                or t - cur[-1]["t"] > 0.9)
            if new_line:
                lines.append(cur)
                cur = []
            cur.append({"t": t, "text": tok, "emph": len(tok) >= 6 and tok.isupper(), "end": w["end"]})
    if cur:
        lines.append(cur)
    out = []
    for i, ln in enumerate(lines):
        end = max(x["end"] for x in ln)
        if i + 1 < len(lines):
            end = min(end, lines[i + 1][0]["t"])
        out.append({"start": ln[0]["t"], "end": max(end, ln[-1]["t"] + 0.35),
                    "words": [{k: v for k, v in x.items() if k != "end"} for x in ln]})
    return out


def snap_words_to_onsets(lines, hits, window=(-0.45, 0.12)):
    """OCR/SRT word times are coarse; move each to the nearest audio onset inside the window."""
    ts = [h["t"] for h in hits]
    for ln in lines:
        prev = -1.0
        for w in ln["words"]:
            cands = [t for t in ts if window[0] <= t - w["t"] <= window[1] and t > prev + 0.06]
            if cands:
                w["t"] = round(min(cands, key=lambda t: abs(t - w["t"] + 0.15)), 3)
            w["t"] = max(w["t"], prev + 0.06)
            prev = w["t"]
        ln["start"] = min(ln["start"], ln["words"][0]["t"])
    return lines


# --- plan ---------------------------------------------------------------------------------------


def build_plan(analysis, settings):
    src = analysis["source"]
    dur, fps = src["duration"], settings.get("fps") or src["fps"]
    OW, OH = settings.get("width", 2160), settings.get("height", 3840)
    scenes = analysis["scenes"]
    audio = analysis.get("audio") or {"beats": [], "downbeats": [], "hits": [], "bpm": 0}
    style = {"accent": settings.get("accent", [255, 45, 45]), "font": settings.get("font"),
             "caption_size": settings.get("caption_size", 0.082),
             "title_size": settings.get("title_size", 0.105)}

    # camera: alternate slow push-in / pull-out per scene toward the detected subject
    cam = []
    for i, sc in enumerate(scenes):
        length = sc["end"] - sc["start"]
        box = sc.get("subject_box", [0, 0, 1, 1])
        fill = max(box[2] - box[0], 0.35)
        zmax = min(settings.get("max_zoom", 1.18), max(1.04, 0.98 / fill))
        lo, hi = 1.0, zmax if length > 2.5 else min(zmax, 1.06)
        zf, zt = (lo, hi) if i % 2 == 0 else (hi, lo)
        fx, fy = sc.get("focus", [0.5, 0.5])
        cam.append({"start": sc["start"], "end": sc["end"], "zoom_from": round(zf, 3), "zoom_to": round(zt, 3),
                    "focus": [round(0.5 + (fx - 0.5) * 0.6, 3), round(0.5 + (fy - 0.5) * 0.6, 3)]})

    # transitions on every cut
    trans, sfx = [], []
    cuts = analysis["cuts"]
    biggest = max(cuts, key=lambda c: c["score"])["t"] if cuts else None
    cycle = ["zoom_blur", "whip", "glitch"]
    ci = 0
    for c in cuts:
        t = c["t"]
        before = next(s for s in scenes if abs(s["end"] - t) < 1e-3)
        after = next(s for s in scenes if abs(s["start"] - t) < 1e-3)
        short = min(before["end"] - before["start"], after["end"] - after["start"]) < 3.0
        if t == biggest:
            kind = "zoom_blur"
        elif short:
            kind = "punch"
        else:
            kind = cycle[ci % len(cycle)]
            ci += 1
        d = 0.22 if kind != "punch" else 0.2
        trans.append({"t": round(t, 3), "type": kind, "half": d})
        if kind == "zoom_blur":
            sfx += [{"name": "whoosh", "t": t, "align": "center", "gain_db": -9}, {"name": "impact", "t": t, "align": "start", "gain_db": -8}]
        elif kind == "whip":
            sfx.append({"name": "whoosh_down", "t": t, "align": "center", "gain_db": -9})
        elif kind == "glitch":
            sfx.append({"name": "glitch", "t": t - 0.08, "align": "start", "gain_db": -15})
            sfx.append({"name": "whoosh", "t": t, "align": "center", "gain_db": -14})
        else:
            sfx.append({"name": "impact", "t": t, "align": "start", "gain_db": -16})
        if t == biggest:
            sfx.append({"name": "riser", "t": t, "align": "end", "gain_db": -14})

    # captions
    cap_cfg = settings.get("captions", {})
    lines = []
    if cap_cfg.get("path"):
        lines = load_captions(cap_cfg["path"])
        log("Captions: %d lines from %s" % (len(lines), os.path.basename(cap_cfg["path"])))
    elif cap_cfg.get("auto_ocr", True) and analysis.get("text", {}).get("words"):
        ok = set(analysis["text"].get("caption_scenes", []))
        words = [w for w in analysis["text"]["words"] if w["scene"] in ok and w["conf"] >= 0.75]
        lines = captions_from_ocr(words)
        log("Captions: %d lines generated from on-screen text (OCR draft)" % len(lines))
    if lines and cap_cfg.get("snap_to_audio", True) and audio["hits"]:
        lines = snap_words_to_onsets(lines, audio["hits"])
    band_override = cap_cfg.get("band")
    cap_bands = []
    for sc in scenes:
        b = band_override or sc.get("text_band", "bottom")
        if b in ("top", "upper"):
            b = "upper" if b == "top" else b
        cap_bands.append({"start": sc["start"], "end": sc["end"], "y": BANDS.get(b, b) if isinstance(b, str) else b})
    for ln in lines:
        for w in ln["words"]:
            if w["emph"]:
                sfx.append({"name": "pop", "t": w["t"], "align": "start", "gain_db": -20})

    # hook title
    title = None
    tcfg = settings.get("title", {})
    ttext = tcfg.get("text") or (analysis.get("text") or {}).get("title")
    if ttext and tcfg.get("enabled", True):
        title = {"text": ttext, "start": tcfg.get("start", 0.15), "duration": tcfg.get("duration", 2.6),
                 "band_y": BANDS.get(tcfg.get("band", "upper"), 0.31)}
        sfx.append({"name": "impact", "t": title["start"] + 0.05, "align": "start", "gain_db": -7})
        sfx.append({"name": "whoosh", "t": title["start"] + title["duration"] + 0.15, "align": "center", "gain_db": -15})

    # zoom punches: emphasised caption words first, then downbeats; never near a transition
    punches = []

    def free(t, gap):
        return all(abs(t - p["t"]) >= gap for p in punches) and all(abs(t - tr["t"]) >= 0.5 for tr in trans)

    for ln in lines:
        for w in ln["words"]:
            if w["emph"] and free(w["t"], 0.9):
                punches.append({"t": w["t"], "amp": 0.05})
    for b in audio["downbeats"]:
        if free(b, 1.6) and not (title and title["start"] <= b <= title["start"] + title["duration"]):
            punches.append({"t": b, "amp": 0.03})
    punches.sort(key=lambda p: p["t"])

    shakes = [{"t": tr["t"], "amp": 0.010 if tr["type"] == "zoom_blur" else 0.005} for tr in trans if tr["type"] in ("zoom_blur", "punch")]
    if title:
        shakes.append({"t": title["start"] + 0.12, "amp": 0.008})

    plan = {
        "version": 1,
        "source": src["path"],
        "src_w": src["width"], "src_h": src["height"], "src_fps": src["fps"],
        "fps": fps, "duration": dur, "width": OW, "height": OH,
        "style": style,
        "grade": {"strength": settings.get("grade_strength", 1.0), "look": settings.get("look", {}),
                  "scenes": [{k: sc[k] for k in ("index", "start", "end", "mean_luma", "mean_sat")} for sc in scenes]},
        "camera": cam, "transitions": trans, "punches": punches, "shakes": shakes,
        "motion_blur": {"shutter_deg": settings.get("shutter_deg", 180), "max_samples": settings.get("mb_samples", 12)},
        "title": title,
        "captions": {"lines": lines, "bands": cap_bands},
        "progress_bar": settings.get("progress_bar", True),
        "sfx": sorted(sfx, key=lambda s: s["t"]),
        "music": settings.get("music"),
        "beats": audio["beats"], "bpm": audio.get("bpm"),
        "encode": {"crf": settings.get("crf", 16), "preset": settings.get("preset", "medium"),
                   "codec": settings.get("codec", "h264"), "audio_bitrate": "320k", "loudness_lufs": settings.get("lufs", -14)},
    }
    log("Plan: %d transitions, %d punches, %d caption lines, %d sfx, title=%r" % (len(trans), len(punches), len(lines), len(sfx), ttext))
    return plan


def write_srt(lines, path):
    def ts(t):
        t = max(0.0, t)
        h, m = int(t // 3600), int(t % 3600 // 60)
        return "%02d:%02d:%06.3f" % (h, m, t % 60)
    with open(path, "w", encoding="utf-8") as f:
        for i, ln in enumerate(lines, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, ts(ln["start"]).replace(".", ","), ts(ln["end"]).replace(".", ","),
                                              " ".join(w["text"] for w in ln["words"])))
