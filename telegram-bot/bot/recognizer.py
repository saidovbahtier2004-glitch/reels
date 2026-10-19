"""Configurable music recognition (AudD or ACRCloud). Keys come from the environment."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import aiohttp

from .config import Settings

log = logging.getLogger(__name__)
_TIMEOUT = aiohttp.ClientTimeout(total=45)


class RecognitionError(RuntimeError):
    pass


@dataclass
class Track:
    title: str
    artist: str
    album: str | None = None
    links: dict[str, str] = field(default_factory=dict)  # label -> url


class Recognizer(Protocol):
    async def recognize(self, audio: Path) -> Track | None: ...


def parse_audd(data: dict[str, Any]) -> Track | None:
    if data.get("status") != "success":
        raise RecognitionError(str(data.get("error", {}).get("error_message", "audd error")))
    r = data.get("result")
    if not r:
        return None
    links: dict[str, str] = {}
    if r.get("song_link"):
        links["Tinglash"] = r["song_link"]
    sp = (r.get("spotify") or {}).get("external_urls", {}).get("spotify")
    if sp:
        links["Spotify"] = sp
    am = (r.get("apple_music") or {}).get("url")
    if am:
        links["Apple Music"] = am
    return Track(r.get("title", "?"), r.get("artist", "?"), r.get("album") or None, links)


def parse_acrcloud(data: dict[str, Any]) -> Track | None:
    code = data.get("status", {}).get("code")
    if code == 1001:  # no result
        return None
    if code != 0:
        raise RecognitionError(str(data.get("status", {}).get("msg", "acrcloud error")))
    music = (data.get("metadata", {}).get("music") or [])
    if not music:
        return None
    m = music[0]
    artists = ", ".join(a.get("name", "") for a in m.get("artists", []) if a.get("name")) or "?"
    ext = m.get("external_metadata", {})
    links: dict[str, str] = {}
    sp = (ext.get("spotify", {}).get("track", {}) or {}).get("id")
    if sp:
        links["Spotify"] = f"https://open.spotify.com/track/{sp}"
    yt = (ext.get("youtube", {}) or {}).get("vid")
    if yt:
        links["YouTube"] = f"https://www.youtube.com/watch?v={yt}"
    dz = (ext.get("deezer", {}).get("track", {}) or {}).get("id")
    if dz:
        links["Deezer"] = f"https://www.deezer.com/track/{dz}"
    return Track(m.get("title", "?"), artists, (m.get("album") or {}).get("name"), links)


def acrcloud_signature(access_key: str, access_secret: str, timestamp: str) -> str:
    to_sign = "\n".join(["POST", "/v1/identify", access_key, "audio", "1", timestamp])
    digest = hmac.new(access_secret.encode(), to_sign.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


class AuddRecognizer:
    def __init__(self, token: str) -> None:
        self._token = token

    async def recognize(self, audio: Path) -> Track | None:
        form = aiohttp.FormData()
        form.add_field("api_token", self._token)
        form.add_field("return", "spotify,apple_music")
        form.add_field("file", audio.read_bytes(), filename=audio.name, content_type="audio/mpeg")
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as s, s.post("https://api.audd.io/", data=form) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise RecognitionError(str(exc)) from exc
        return parse_audd(data)


class AcrCloudRecognizer:
    def __init__(self, host: str, key: str, secret: str) -> None:
        self._host, self._key, self._secret = host, key, secret

    async def recognize(self, audio: Path) -> Track | None:
        sample = audio.read_bytes()
        ts = str(int(time.time()))
        form = aiohttp.FormData()
        form.add_field("access_key", self._key)
        form.add_field("data_type", "audio")
        form.add_field("signature_version", "1")
        form.add_field("signature", acrcloud_signature(self._key, self._secret, ts))
        form.add_field("timestamp", ts)
        form.add_field("sample_bytes", str(len(sample)))
        form.add_field("sample", sample, filename=audio.name, content_type="audio/mpeg")
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as s, s.post(
                f"https://{self._host}/v1/identify", data=form
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise RecognitionError(str(exc)) from exc
        return parse_acrcloud(data)


def build_recognizer(settings: Settings) -> Recognizer | None:
    if not settings.recognition_ready:
        return None
    if settings.recognition_provider == "audd":
        return AuddRecognizer(settings.audd_api_token)
    return AcrCloudRecognizer(
        settings.acrcloud_host, settings.acrcloud_access_key, settings.acrcloud_access_secret
    )
