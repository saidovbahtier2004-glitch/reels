# ReelForge — server-side video montage pipeline

The browser editor in the repo root (`index.html`, `app.js`) is unchanged. This folder is a separate
pipeline that renders real MP4 files with FFmpeg + Python, at up to 2160×3840 (9:16).

```
python3 -m pip install -r requirements.txt        # needs ffmpeg/ffprobe with libx264 on PATH
cd pipeline
python3 -m reelforge run --project projects/opus55/edit.json -o ../output/reel_2160x3840.mp4
python3 -m reelforge run INPUT.mp4 -o OUT.mp4 [--captions c.json|c.srt] [--music track.mp3] [--preview 6]
```

## Stages

| Stage | Module | What it does |
|---|---|---|
| Analyse | `analyze.py` | ffprobe; scene cuts (`scdet`); audio tempo, beat grid, downbeats, onsets, silences; per-scene subject box, focus point, luma/saturation and the quietest band for text; OCR of on-screen text (title + timed words). Cached as `analysis.json`. |
| Plan | `plan.py` | Edit decision list: camera push-ins, beat/emphasis zoom punches, shakes, transition per cut (zoom-blur, whip, glitch, punch), captions (word-level, snapped to audio onsets), hook title, SFX cues, music, encode settings. Written to `plan.json` (editable; `reelforge render plan.json` re-renders it). |
| Render | `render.py`, `text.py`, `grade.py` | Decode once → per-scene colour grade at source resolution → virtual camera sampled across a 180° shutter (real motion blur on zooms/whips) → one Lanczos resample to output size → flash / RGB-split glitch → kinetic typography (Pillow, motion-blurred) → progress bar. Multiprocess; frames piped to one x264 encode (BT.709 tagged). |
| Audio | `mixer.py`, `sfx.py` | Original track + procedurally synthesised whoosh/impact/riser/glitch/pop (no samples) placed on the plan's cues; optional music looped, faded and side-chain ducked under the source; soft limiter; `loudnorm` to −14 LUFS; AAC 320k. Captions are also muxed as a soft `mov_text` track. |
| Verify | `verify.py` | Re-opens the MP4: resolution, frame count, duration, audio, subtitle track, BT.709 tags, loudness/true peak, black and frozen segments, colour stats vs. source, contact sheets of the timeline and every transition → `verify_report.json`. |

## Project file (`projects/*/edit.json`)

`width/height`, `crf`, `preset`, `codec` (`h264`/`hevc`), `lufs`, `accent` colour, `caption_size`,
`title_size`, `max_zoom`, `shutter_deg`, `look` (contrast, saturation, red boost, split tone, vignette),
`title` (`text`, `start`, `duration`, `band`), `captions` (`path` to .json/.srt, `snap_to_audio`, `band`),
`music` (`path`, `gain_db`, `duck`, `offset`). Paths are relative to the project file.

Captions JSON: `{"lines": [{"end": 3.3, "words": [[1.0, "NO"], [2.0, "*WAY."]]}]}` — `*` = emphasised
(accent colour, zoom punch, pop SFX).

## Limits

* Speech recognition: no ASR model ships with the pipeline (Whisper/Vosk model downloads were blocked
  in the environment it was built in). Captions come from a .json/.srt file, or as an OCR draft of
  on-screen text when the project gives none.
* Upscaling a 720p source to 2160×3840 makes a clean 4K file but cannot add detail that was never recorded.
