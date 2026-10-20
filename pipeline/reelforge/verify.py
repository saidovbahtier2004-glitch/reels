"""Stage 4: open the rendered MP4 and check it against the plan and the source."""
import json
import os
import re
import subprocess

import numpy as np

from .util import FFMPEG, FFPROBE, log, probe


def _ff(args):
    return subprocess.run([FFMPEG, "-hide_banner", "-nostats"] + args, capture_output=True, text=True).stderr


def verify(out_path, plan, workdir):
    rep = {"file": os.path.abspath(out_path), "size_mb": round(os.path.getsize(out_path) / 2 ** 20, 1), "checks": {}}
    info = probe(out_path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    subs = [s for s in info["streams"] if s["codec_type"] == "subtitle"]
    rep["video"] = {"codec": v["codec_name"], "profile": v.get("profile"), "width": info["width"], "height": info["height"],
                    "fps": info["fps"], "pix_fmt": v.get("pix_fmt"), "bitrate_mbps": round(int(v.get("bit_rate", 0)) / 1e6, 1),
                    "color": [v.get("color_space"), v.get("color_primaries"), v.get("color_transfer"), v.get("color_range")]}
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    rep["audio"] = {"codec": a["codec_name"], "sample_rate": a["sample_rate"], "channels": a["channels"],
                    "bitrate_kbps": round(int(a.get("bit_rate", 0)) / 1e3)} if a else None
    rep["subtitles"] = [{"codec": s["codec_name"], "lang": s.get("tags", {}).get("language")} for s in subs]
    cnt = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", out_path], capture_output=True, text=True).stdout.strip()
    rep["video"]["frames"] = int(cnt or 0)
    rep["duration"] = round(float(info["format"]["duration"]), 3)
    expected = int(round(plan["duration"] * plan["fps"]))
    c = rep["checks"]
    c["resolution_2160x3840"] = (info["width"], info["height"]) == (plan["width"], plan["height"])
    c["aspect_9_16"] = abs(info["width"] / info["height"] - 9 / 16) < 1e-3
    c["frame_count"] = abs(rep["video"]["frames"] - expected) <= 2
    c["duration_matches_source"] = abs(rep["duration"] - plan["duration"]) < 0.15
    c["has_audio"] = a is not None
    c["has_subtitle_track"] = bool(subs) or not plan["captions"]["lines"]
    c["bt709_tagged"] = v.get("color_space") == "bt709"

    # loudness / clipping
    e = _ff(["-i", out_path, "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"])
    m = re.search(r"I:\s+(-?[0-9.]+) LUFS", e.split("Summary:")[-1])
    p = re.search(r"Peak:\s+(-?[0-9.]+) dBFS", e.split("Summary:")[-1])
    rep["loudness_lufs"] = float(m.group(1)) if m else None
    rep["true_peak_dbfs"] = float(p.group(1)) if p else None
    c["loudness_ok"] = rep["loudness_lufs"] is not None and abs(rep["loudness_lufs"] - plan["encode"]["loudness_lufs"]) < 2.0
    c["no_clipping"] = rep["true_peak_dbfs"] is not None and rep["true_peak_dbfs"] <= -0.3

    # black / frozen frames
    e = _ff(["-i", out_path, "-vf", "scale=270:-2,blackdetect=d=0.5:pix_th=0.06", "-an", "-f", "null", "-"])
    rep["black_segments"] = re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", e)
    e = _ff(["-i", out_path, "-vf", "scale=270:-2,freezedetect=n=0.001:d=2", "-an", "-f", "null", "-"])
    rep["frozen_segments"] = re.findall(r"freeze_start: ([0-9.]+)", e)
    c["no_black_gaps"] = not rep["black_segments"]

    # colour stats vs source, and structural similarity to the source (camera moves lower it on purpose)
    def stats(path, w=270):
        r = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-vf", "fps=1,scale=%d:480,format=rgb24" % w, "-f", "rawvideo", "-"],
                           capture_output=True)
        f = np.frombuffer(r.stdout, np.uint8).reshape(-1, 480, w, 3).astype(np.float32) / 255
        lum = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        mx, mn = f.max(-1), f.min(-1)
        return f, {"mean_luma": round(float(lum.mean()), 3), "contrast_std": round(float(lum.std()), 3),
                   "saturation": round(float(((mx - mn) / (mx + 1e-6)).mean()), 3)}
    fs, rep["source_color"] = stats(plan["source"])
    fo, rep["output_color"] = stats(out_path)
    k = min(len(fs), len(fo))
    rep["mean_abs_diff_vs_source"] = round(float(np.abs(fs[:k] - fo[:k]).mean()), 3)

    # contact sheets: a timeline sheet and one at every transition
    sheet = os.path.join(workdir, "contact_sheet.jpg")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", out_path, "-vf",
                    "fps=1/3,scale=270:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    "text='%{pts\\:hms}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=8x4",
                    "-frames:v", "1", "-q:v", "3", sheet])
    rep["contact_sheet"] = sheet
    tsheets = []
    for tr in plan["transitions"][:8]:
        pth = os.path.join(workdir, "transition_%06.2f.jpg" % tr["t"])
        subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "%.3f" % max(0, tr["t"] - 0.25), "-i", out_path, "-vf",
                        "scale=216:-2,tile=8x2", "-frames:v", "1", "-q:v", "3", pth])
        tsheets.append(pth)
    rep["transition_sheets"] = tsheets
    rep["ok"] = all(c.values())
    json.dump(rep, open(os.path.join(workdir, "verify_report.json"), "w"), indent=1)
    for k2, v2 in c.items():
        log("  %-26s %s" % (k2, "OK" if v2 else "FAIL"))
    return rep
