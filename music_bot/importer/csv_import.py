"""CSV metadata importi.

Majburiy ustunlar: title, artist, license_id.
Ixtiyoriy: file, external_id, album, isrc, duration, license_expires, audio_url.
Ustun nomlari o'zbekcha/ruscha/inglizcha sinonimlar bilan ham qabul qilinadi.
Ajratkich avtomatik aniqlanadi (, ; yoki TAB). UTF-8 (BOM bilan ham) kutiladi.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date

from .models import TrackMeta
from .text import norm

MAX_ROWS = 20_000
REQUIRED = ("title", "artist", "license_id")

ALIASES = {
    "title": "title", "name": "title", "song": "title", "track": "title", "nomi": "title",
    "qoshiq": "title", "название": "title",
    "artist": "artist", "performer": "artist", "ijrochi": "artist", "исполнитель": "artist",
    "license_id": "license_id", "license": "license_id", "licence": "license_id",
    "litsenziya": "license_id", "лицензия": "license_id",
    "license_expires": "license_expires", "expires": "license_expires", "license_end": "license_expires",
    "file": "file", "filename": "file", "file_name": "file", "fayl": "file", "файл": "file",
    "external_id": "external_id", "id": "external_id", "track_id": "external_id",
    "album": "album", "albom": "album", "альбом": "album",
    "isrc": "isrc",
    "duration": "duration", "length": "duration", "davomiylik": "duration",
    "audio_url": "audio_url", "url": "audio_url",
}

ISRC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")


@dataclass
class CsvResult:
    tracks: list[TrackMeta] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


def _key(header: str) -> str:
    h = re.sub(r"[\s\-]+", "_", header.strip().lower().replace("'", "").replace("ʻ", ""))
    return ALIASES.get(h, h)


def parse_duration(value: str) -> int:
    value = (value or "").strip()
    if not value:
        return 0
    if ":" in value:
        parts = [int(p) for p in value.split(":")]
        total = 0
        for p in parts:
            total = total * 60 + p
        return total
    return int(float(value))


def parse_csv(data: bytes | str, provider: str = "") -> CsvResult:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.lstrip("﻿")
    res = CsvResult()
    if not text.strip():
        res.errors.append("CSV bo'sh")
        return res
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, [])
    keys = [_key(h) for h in header]
    res.columns = keys
    missing = [c for c in REQUIRED if c not in keys]
    if missing:
        res.errors.append("Majburiy ustun(lar) yo'q: " + ", ".join(missing)
                          + ". Faqat litsenziyali treklar import qilinadi, license_id shart.")
        return res

    today = date.today()
    seen: set[str] = set()
    for line_no, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue
        if len(res.tracks) >= MAX_ROWS:
            res.errors.append(f"{MAX_ROWS} qatordan ko'pi o'tkazib yuborildi")
            break
        rec = {k: (row[i].strip() if i < len(row) else "") for i, k in enumerate(keys)}
        try:
            duration = parse_duration(rec.get("duration", ""))
        except ValueError:
            res.errors.append(f"{line_no}-qator: duration noto'g'ri: {rec.get('duration')}")
            continue
        track = TrackMeta(
            title=rec.get("title", ""), artist=rec.get("artist", ""),
            license_id=rec.get("license_id", ""), external_id=rec.get("external_id", ""),
            album=rec.get("album", ""), isrc=rec.get("isrc", "").upper().replace("-", ""),
            duration=duration, license_expires=rec.get("license_expires", ""),
            file=rec.get("file", ""), audio_url=rec.get("audio_url", ""), provider=provider,
        )
        if not track.title or not track.artist:
            res.errors.append(f"{line_no}-qator: title yoki artist bo'sh")
            continue
        problem = track.license_problem(today)
        if problem:
            res.errors.append(f"{line_no}-qator ({track.artist} — {track.title}): {problem}")
            continue
        if track.isrc and not ISRC_RE.match(track.isrc):
            res.errors.append(f"{line_no}-qator: ISRC formati noto'g'ri: {track.isrc}")
            continue
        ids = {f"name:{norm(track.artist)}|{norm(track.title)}"}
        if track.isrc:
            ids.add(f"isrc:{track.isrc}")
        if track.external_id:
            ids.add(f"ext:{track.external_id}")
        if ids & seen:
            res.errors.append(f"{line_no}-qator: CSV ichida takroriy ({track.artist} — {track.title})")
            continue
        seen |= ids
        res.tracks.append(track)
    return res
