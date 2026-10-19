"""Song search through free, key-less public APIs (iTunes Search, Deezer)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=15)


@dataclass
class SongResult:
    title: str
    artist: str
    links: dict[str, str] = field(default_factory=dict)  # label -> url


def parse_itunes(data: dict[str, Any]) -> list[SongResult]:
    out = []
    for r in data.get("results", []):
        if r.get("wrapperType") != "track" or not r.get("trackViewUrl"):
            continue
        out.append(SongResult(r.get("trackName", "?"), r.get("artistName", "?"), {"Apple Music": r["trackViewUrl"]}))
    return out


def parse_deezer(data: dict[str, Any]) -> list[SongResult]:
    out = []
    for r in data.get("data", []):
        if not r.get("link"):
            continue
        out.append(SongResult(r.get("title", "?"), (r.get("artist") or {}).get("name", "?"), {"Deezer": r["link"]}))
    return out


def merge(primary: list[SongResult], secondary: list[SongResult], limit: int = 5) -> list[SongResult]:
    """Merge by (title, artist); add the extra platform link to an existing item."""
    out: list[SongResult] = []
    index: dict[tuple[str, str], SongResult] = {}
    for item in [*primary, *secondary]:
        key = (item.title.casefold().strip(), item.artist.casefold().strip())
        if key in index:
            index[key].links.update(item.links)
        elif len(out) < limit:
            index[key] = item
            out.append(item)
    for item in out:
        q = quote_plus(f"{item.artist} {item.title}")
        item.links["YouTube Music"] = f"https://music.youtube.com/search?q={q}"
    return out


async def _get(session: aiohttp.ClientSession, url: str, params: dict[str, str]) -> dict[str, Any]:
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def search_songs(query: str, country: str = "US") -> list[SongResult]:
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
        results = await asyncio.gather(
            _get(s, "https://itunes.apple.com/search",
                 {"term": query, "media": "music", "entity": "song", "limit": "5", "country": country}),
            _get(s, "https://api.deezer.com/search", {"q": query, "limit": "5"}),
            return_exceptions=True,
        )
    it, dz = results
    if isinstance(it, Exception) and isinstance(dz, Exception):
        raise it
    return merge(
        parse_itunes(it) if not isinstance(it, Exception) else [],
        parse_deezer(dz) if not isinstance(dz, Exception) else [],
    )
