"""Free Music Archive (FMA) dataset'idan nomzod treklar.

Manba: rasmiy FMA dataset (https://github.com/mdeff/fma):
  * fma_metadata.zip → tracks.csv  (106 574 trek, 2017 snapshot, metadata CC BY 4.0)
  * fma_full.zip     → <id[:3]>/<id:06d>.mp3  (kesilmagan MP3, har biri artist tanlagan litsenziyada)

FMA veb-saytiga yoki API'siga murojaat qilinmaydi. Fayllarni operator dataset'ning rasmiy
manzilidan yuklab, serverdagi IMPORT_ROOT ichiga qo'yadi (fma_full.zip'ni ochmasdan ham bo'ladi).

Har bir trek alohida tekshiriladi: litsenziya (licenses.Policy), audio fayl mavjudligi,
hajm (Telegram 49 MB) va format (faqat MP3, o'zgartirilmagan holda yuboriladi).
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from .licenses import LicenseInfo, Policy, attribution, parse_license
from .vault import VaultError, import_root

log = logging.getLogger("music_bot.importer")

DATASET_URL = "https://github.com/mdeff/fma"
MAX_UPLOAD = 49 * 1024 * 1024

# FMA top-level janrlari -> katalog janrlari
GENRE_MAP = {
    "Pop": "Pop", "Hip-Hop": "Hip-Hop/Rap", "Soul-RnB": "R&B", "Rock": "Rock",
    "Electronic": "Electronic/EDM", "Jazz": "Jazz", "Classical": "Classical", "Folk": "Folk",
    "International": "World Music",
}
# Bular standart filtrdan tashqarida (FMA_GENRES=all bilan qo'shiladi)
OTHER_GENRES = {"Experimental", "Instrumental", "Blues", "Country", "Easy Listening", "Old-Time / Historic",
                "Spoken"}

LANGUAGES = {"uz": "O'zbek", "ru": "Rus", "en": "Ingliz", "tr": "Turk", "ar": "Arab", "hi": "Hind",
             "ko": "Koreys", "es": "Ispan", "fr": "Fransuz"}


@dataclass
class Candidate:
    fma_id: int
    title: str
    artist: str
    album: str
    genre: str            # katalog janri
    fma_genre: str
    language: str         # ISO kod yoki ""
    duration: int
    license: LicenseInfo
    artist_url: str = ""

    @property
    def source_url(self) -> str:
        return ""  # tracks.csv'da trek URL'i yo'q — taxmin qilmaymiz

    def attribution(self) -> str:
        return attribution(self.title, self.artist, self.license,
                           f"Free Music Archive, trek #{self.fma_id} (FMA dataset, {DATASET_URL})")

    def library_extra(self) -> dict:
        return {
            "title": self.title, "artist": self.artist, "album": self.album, "duration": self.duration,
            "provider": "fma", "external_id": str(self.fma_id), "genre": self.genre,
            "language": self.language, "license_id": self.license.short, "license_code": self.license.code,
            "license_title": self.license.title, "license_url": self.license.url,
            "source": "Free Music Archive", "source_url": self.source_url, "dataset_url": DATASET_URL,
            "artist_url": self.artist_url, "attribution": self.attribution(),
        }


# --------------------------------------------------------------------------- #
# tracks.csv
# --------------------------------------------------------------------------- #
REQUIRED = [("track", "title"), ("artist", "name"), ("track", "license")]


def iter_tracks(path: Path) -> Iterator[dict]:
    """tracks.csv'ni qatorma-qator o'qiydi. Kalitlar: 'track.title', 'artist.name', ..."""
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        top = next(reader, [])
        sub = next(reader, [])
        keys, last = [], ""
        for t, s in zip(top, sub):
            last = t or last
            keys.append(f"{last}.{s}" if s else "")
        present = set(keys)
        missing = [f"{a}.{b}" for a, b in REQUIRED if f"{a}.{b}" not in present]
        if missing:
            raise VaultError("tracks.csv formati kutilganidek emas, ustunlar yo'q: " + ", ".join(missing))
        for row in reader:
            if not row or not row[0].strip().isdigit():
                continue  # "track_id,,," kabi indeks-nomi qatori
            rec = {"track_id": int(row[0])}
            for k, v in zip(keys[1:], row[1:]):
                if k:
                    rec[k] = v
            yield rec


def to_candidate(rec: dict) -> Candidate:
    fma_genre = (rec.get("track.genre_top") or "").strip()
    try:
        duration = int(float(rec.get("track.duration") or 0))
    except ValueError:
        duration = 0
    return Candidate(
        fma_id=rec["track_id"], title=(rec.get("track.title") or "").strip(),
        artist=(rec.get("artist.name") or "").strip(), album=(rec.get("album.title") or "").strip(),
        genre=GENRE_MAP.get(fma_genre, fma_genre or "—"), fma_genre=fma_genre,
        language=(rec.get("track.language_code") or "").strip().lower(), duration=duration,
        license=parse_license(rec.get("track.license") or ""),
        artist_url=(rec.get("artist.website") or "").strip(),
    )


# --------------------------------------------------------------------------- #
# Audio: ochilgan papka yoki fma_full.zip (ochmasdan)
# --------------------------------------------------------------------------- #
def audio_member(fma_id: int) -> str:
    tid = f"{fma_id:06d}"
    return f"{tid[:3]}/{tid}.mp3"


class AudioSource:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._zip: zipfile.ZipFile | None = None
        self._names: dict[str, zipfile.ZipInfo] = {}
        if path.is_file() and path.suffix.lower() == ".zip":
            self._zip = zipfile.ZipFile(path)
            for info in self._zip.infolist():
                p = PurePosixPath(info.filename)
                if p.suffix.lower() == ".mp3" and len(p.parts) >= 2:
                    self._names["/".join(p.parts[-2:])] = info
        elif not path.is_dir():
            raise VaultError(f"audio manbasi topilmadi: {path}")

    def stat(self, fma_id: int) -> int | None:
        """Fayl hajmi yoki None (yo'q)."""
        m = audio_member(fma_id)
        if self._zip is not None:
            info = self._names.get(m)
            return info.file_size if info else None
        p = self.path / m
        return p.stat().st_size if p.is_file() else None

    def read(self, fma_id: int) -> bytes:
        m = audio_member(fma_id)
        if self._zip is not None:
            return self._zip.read(self._names[m])
        return (self.path / m).read_bytes()

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()


def resolve(rel: str) -> Path:
    root = import_root()
    if root is None:
        raise VaultError("IMPORT_ROOT sozlanmagan")
    p = (root / rel.strip().lstrip("/")).resolve()
    if p != root and root not in p.parents:
        raise VaultError("ruxsat etilmagan yo'l")
    if not p.exists():
        raise VaultError(f"topilmadi: {rel}")
    return p


# --------------------------------------------------------------------------- #
# Hisoblash (import'dan oldin)
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    metadata: str                      # IMPORT_ROOT'ga nisbatan tracks.csv
    audio: str                         # IMPORT_ROOT'ga nisbatan fma_full/ yoki fma_full.zip
    commercial: bool = True
    genres: tuple[str, ...] = tuple(GENRE_MAP)   # FMA top-level nomlari; bo'sh = hammasi
    languages: tuple[str, ...] = ()              # bo'sh = filtrsiz
    target: int = 50_000

    @classmethod
    def from_env(cls) -> "Settings":
        g = os.getenv("FMA_GENRES", "").strip()
        langs = os.getenv("FMA_LANGUAGES", "").strip()
        return cls(
            metadata=os.getenv("FMA_METADATA", "fma_metadata/tracks.csv"),
            audio=os.getenv("FMA_AUDIO", "fma_full"),
            commercial=os.getenv("BOT_COMMERCIAL", "1").strip() not in ("0", "false", "no"),
            genres=() if g.lower() == "all" else tuple(x.strip() for x in g.split(",") if x.strip()) or tuple(GENRE_MAP),
            languages=tuple(x.strip().lower() for x in langs.split(",") if x.strip()),
            target=int(os.getenv("FMA_TARGET", "50000")),
        )

    def to_dict(self) -> dict:
        return {"metadata": self.metadata, "audio": self.audio, "commercial": self.commercial,
                "genres": list(self.genres), "languages": list(self.languages), "target": self.target}

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        return cls(d["metadata"], d["audio"], d["commercial"], tuple(d["genres"]), tuple(d["languages"]),
                   d["target"])


@dataclass
class CountReport:
    rows: int = 0
    eligible: int = 0
    reasons: Counter = field(default_factory=Counter)
    licenses: Counter = field(default_factory=Counter)        # yaroqlilar
    licenses_all: Counter = field(default_factory=Counter)    # hammasi
    genres: Counter = field(default_factory=Counter)
    languages: Counter = field(default_factory=Counter)
    eligible_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"rows": self.rows, "eligible": self.eligible, "reasons": dict(self.reasons.most_common()),
                "licenses": dict(self.licenses.most_common()),
                "licenses_all": dict(self.licenses_all.most_common(15)),
                "genres": dict(self.genres.most_common()), "languages": dict(self.languages.most_common())}


def evaluate(c: Candidate, s: Settings, policy: Policy, audio: AudioSource | None) -> str | None:
    """None — yaroqli; aks holda sabab (hisobot uchun qisqa kalit)."""
    if not c.title or not c.artist:
        return "nom yoki ijrochi yo'q"
    if s.genres and c.fma_genre not in s.genres:
        return "janr filtrdan tashqarida"
    if s.languages and c.language not in s.languages:
        return "til filtrdan tashqarida"
    problem = policy.check(c.license, will_modify=False)
    if problem:
        if c.license.code == "unknown":
            return "litsenziya noma'lum / ruxsat yo'q"
        if c.license.noncommercial:
            return "NonCommercial (bot tijoriy)"
        return "litsenziya siyosati"
    if audio is not None:
        size = audio.stat(c.fma_id)
        if size is None:
            return "audio fayl yo'q"
        if size > MAX_UPLOAD:
            return "audio > 49 MB (o'zgartirmasdan yuborib bo'lmaydi)"
    return None


def count_catalog(s: Settings, progress: Callable[[CountReport], None] | None = None,
                  every: int = 5000) -> CountReport:
    """Butun katalogni o'qib, yaroqli treklarni sanaydi. Import qilinmaydi."""
    policy = Policy(commercial=s.commercial)
    audio = AudioSource(resolve(s.audio))
    rep = CountReport()
    try:
        for rec in iter_tracks(resolve(s.metadata)):
            rep.rows += 1
            c = to_candidate(rec)
            rep.licenses_all[c.license.short] += 1
            reason = evaluate(c, s, policy, audio)
            if reason:
                rep.reasons[reason] += 1
            else:
                rep.eligible += 1
                rep.eligible_ids.append(c.fma_id)
                rep.licenses[c.license.short] += 1
                rep.genres[c.genre] += 1
                rep.languages[c.language or "—"] += 1
            if progress and rep.rows % every == 0:
                progress(rep)
    finally:
        audio.close()
    return rep


def load_candidates(s: Settings, ids: set[int]) -> dict[int, Candidate]:
    """Import paytida faqat kerakli treklarning metadata'sini xotiraga oladi."""
    out = {}
    for rec in iter_tracks(resolve(s.metadata)):
        if rec["track_id"] in ids:
            out[rec["track_id"]] = to_candidate(rec)
    return out
