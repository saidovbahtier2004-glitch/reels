"""Public-video downloading through yt-dlp.

No cookies, no logins, no DRM circumvention: if yt-dlp cannot fetch a URL as an
anonymous visitor, the download simply fails.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

log = logging.getLogger(__name__)


class DownloadFailed(RuntimeError):
    pass


class FileTooBig(DownloadFailed):
    pass


@dataclass
class Downloaded:
    path: Path
    title: str
    uploader: str
    duration: int | None


def _base_opts(outdir: Path, max_bytes: int) -> dict[str, Any]:
    return {
        "outtmpl": str(outdir / "%(id).60B.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreconfig": True,
        "socket_timeout": 20,
        "retries": 2,
        "max_filesize": max_bytes,
        "restrictfilenames": True,
        "cachedir": False,
    }


def _run(url: str, opts: dict[str, Any]) -> dict[str, Any]:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        msg = str(exc)
        log.info("yt-dlp failed: %s", msg[:300])
        if "larger than max-filesize" in msg:
            raise FileTooBig(msg) from exc
        raise DownloadFailed(msg) from exc
    if info is None:
        raise DownloadFailed("no info")
    if "entries" in info:  # playlist/carousel: take first entry only
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise DownloadFailed("empty playlist")
        info = entries[0]
    return info


def _pick_file(outdir: Path, info: dict[str, Any]) -> Path:
    files = [p for p in outdir.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
    if not files:
        # yt-dlp silently skips files above max_filesize, so an empty folder means "too big".
        raise FileTooBig("no output file (over size limit)")
    return max(files, key=lambda p: p.stat().st_size)


def _download_video_sync(url: str, outdir: Path, max_bytes: int) -> Downloaded:
    # Try best quality up to 720p, then fall back to smaller ones if the file is too large.
    last: Exception | None = None
    for height in (720, 480, 360):
        for p in outdir.iterdir():
            p.unlink()
        opts = _base_opts(outdir, max_bytes) | {
            "format": f"bv*[height<={height}]+ba/b[height<={height}]/b",
            "merge_output_format": "mp4",
        }
        try:
            info = _run(url, opts)
            path = _pick_file(outdir, info)
            if path.stat().st_size <= max_bytes:
                return Downloaded(path, info.get("title") or "video", info.get("uploader") or "", info.get("duration"))
            last = FileTooBig("too big")
        except FileTooBig as exc:
            last = exc
    raise last or DownloadFailed("failed")


def _download_audio_sync(url: str, outdir: Path, max_bytes: int, to_mp3: bool) -> Downloaded:
    opts = _base_opts(outdir, max_bytes) | {"format": "ba/b"}
    if to_mp3:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    info = _run(url, opts)
    path = _pick_file(outdir, info)
    if path.stat().st_size > max_bytes:
        raise FileTooBig("too big")
    return Downloaded(path, info.get("title") or "audio", info.get("uploader") or "", info.get("duration"))


async def download_video(url: str, outdir: Path, max_bytes: int) -> Downloaded:
    return await asyncio.to_thread(_download_video_sync, url, outdir, max_bytes)


async def download_audio(url: str, outdir: Path, max_bytes: int, to_mp3: bool = True) -> Downloaded:
    return await asyncio.to_thread(_download_audio_sync, url, outdir, max_bytes, to_mp3)
