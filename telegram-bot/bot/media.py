"""FFmpeg helpers."""
from __future__ import annotations

import asyncio
from pathlib import Path


class MediaError(RuntimeError):
    pass


async def extract_audio_clip(src: Path, dst: Path, seconds: int = 25) -> Path:
    """Convert any audio/video file to a short mono MP3 clip for recognition."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-t", str(seconds),
        "-ac", "1", "-ar", "44100", "-b:a", "128k", str(dst),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        raise MediaError("ffmpeg timeout")
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        raise MediaError(err.decode(errors="replace")[-300:] or "no audio")
    return dst
