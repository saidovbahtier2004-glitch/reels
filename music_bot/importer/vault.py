"""DistroKid Vault backup'laridan (o'zingizning original audiolaringiz) import.

DistroKid ommaviy katalog API'sini bermaydi, shuning uchun bu modul hech qanday
DistroKid endpoint'iga murojaat qilmaydi va saytni o'qimaydi. Manbalar faqat:
  * siz botga yuborgan ZIP backup'lar (Telegram file_id orqali saqlanadi)
  * siz botga yuborgan alohida audio fayllar
  * serverdagi IMPORT_ROOT ichidagi papka (doimiy disk bo'lsa)

Vault arxivining aniq tuzilishiga bog'lanmaymiz: audio fayllar istalgan papkada
bo'lishi mumkin, metadata CSV, audio teglari va fayl nomidan olinadi.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import io
import logging
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from .models import TrackMeta
from .text import norm

log = logging.getLogger("music_bot.importer")

AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".aif", ".aiff"}
TELEGRAM_NATIVE = {".mp3", ".m4a"}  # Telegram pleyerida o'zi ijro bo'ladi
MAX_MEMBERS = 5000
MAX_TOTAL_BYTES = 4 * 1024 ** 3     # ZIP ichidagi umumiy hajm (zip-bomb himoyasi)
MAX_FILE_BYTES = 700 * 1024 ** 2    # bitta audio (WAV uzun bo'lishi mumkin)
MAX_UPLOAD_BYTES = 49 * 1024 ** 2   # Telegram bot yuklash limiti
ISRC_RE = re.compile(r"\b([A-Z]{2}-?[A-Z0-9]{3}-?\d{2}-?\d{5})\b", re.I)


class VaultError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Fayl tahlili
# --------------------------------------------------------------------------- #
@dataclass
class ScannedFile:
    name: str                      # fayl nomi
    member: str                    # ZIP ichidagi yo'l yoki papkaga nisbiy yo'l
    size: int
    sha256: str
    tags: dict = field(default_factory=dict)
    fname: dict = field(default_factory=dict)  # fayl nomidan olingan maydonlar

    def to_dict(self) -> dict:
        return asdict(self)


def clean_isrc(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def parse_filename(name: str) -> dict:
    """'01 - Ijrochi - Nomi.wav', 'Ijrochi - Nomi (USRC12345678).mp3', '03 Nomi.flac' ..."""
    stem = Path(name).stem.replace("_", " ").strip()
    out: dict = {}
    m = ISRC_RE.search(stem)
    if m:
        out["isrc"] = clean_isrc(m.group(1))
        stem = (stem[:m.start()] + stem[m.end():])
        stem = re.sub(r"[\(\[]\s*[\)\]]", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -._")
    m = re.match(r"^(\d{1,3})[\s.\-)]+(.+)$", stem)
    if m:
        out["track"] = int(m.group(1))
        stem = m.group(2).strip()
    parts = [p.strip() for p in re.split(r"\s+-\s+", stem) if p.strip()]
    if len(parts) >= 2:
        out["artist"], out["title"] = parts[0], " - ".join(parts[1:])
    elif parts:
        out["title"] = parts[0]
    return out


def read_tags(data: bytes, filename: str) -> dict:
    """Audio ichidagi teglar (ID3, FLAC, MP4, WAV ID3) va davomiylik."""
    try:
        import mutagen
    except ImportError:  # pragma: no cover
        return {}
    out: dict = {}
    try:
        f = mutagen.File(io.BytesIO(data), easy=True)
    except Exception:
        f = None
    if f is None:
        return out
    length = getattr(getattr(f, "info", None), "length", None)
    if length and 0 < length < 6 * 3600:  # buzilgan sarlavhalardagi bema'ni qiymatlarni o'tkazamiz
        out["duration"] = int(round(length))
    tags = f.tags
    if not tags:
        return out

    def first(*keys):
        for k in keys:
            try:
                v = tags.get(k)
            except Exception:
                v = None
            if v:
                v = v[0] if isinstance(v, list) else v
                v = str(getattr(v, "text", [v])[0] if hasattr(v, "text") else v).strip()
                if v:
                    return v
        return ""

    out["title"] = first("title", "TIT2", "\xa9nam")
    out["artist"] = first("artist", "TPE1", "\xa9ART", "albumartist", "TPE2")
    out["album"] = first("album", "TALB", "\xa9alb")
    out["isrc"] = clean_isrc(first("isrc", "TSRC") or _raw_isrc(data))
    track = first("tracknumber", "TRCK")
    if track:
        m = re.match(r"\d+", track)
        if m:
            out["track"] = int(m.group())
    return {k: v for k, v in out.items() if v}


def _raw_isrc(data: bytes) -> str:
    """ISRC ba'zan TXXX:ISRC yoki iTunes '----' tegida bo'ladi (easy rejim ko'rmaydi)."""
    import mutagen
    try:
        f = mutagen.File(io.BytesIO(data))
    except Exception:
        return ""
    if not f or not f.tags:
        return ""
    for key in ("TSRC", "TXXX:ISRC", "TXXX:isrc", "----:com.apple.iTunes:ISRC", "ISRC", "isrc"):
        try:
            v = f.tags.get(key)
        except Exception:
            v = None
        if v:
            v = getattr(v, "text", v)
            v = v[0] if isinstance(v, list) else v
            return v.decode() if isinstance(v, bytes) else str(v)
    return ""


def _is_audio_member(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part.startswith(".") or part == "__MACOSX" for part in p.parts):
        return False
    return p.suffix.lower() in AUDIO_EXTS


def scan_zip(path: str | Path) -> tuple[list[ScannedFile], list[str]]:
    """ZIP ichidagi audiolarni xavfsiz o'qiydi (fayllar diskka chiqarilmaydi)."""
    files, skipped = [], []
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise VaultError("ZIP fayl buzilgan yoki ZIP emas") from e
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_MEMBERS:
            raise VaultError(f"ZIP'da {len(infos)} ta fayl — limit {MAX_MEMBERS}")
        total = sum(i.file_size for i in infos)
        if total > MAX_TOTAL_BYTES:
            raise VaultError("ZIP ochilgandagi hajmi juda katta")
        for info in infos:
            if not _is_audio_member(info.filename):
                skipped.append(info.filename)
                continue
            if info.file_size > MAX_FILE_BYTES:
                skipped.append(f"{info.filename} (juda katta)")
                continue
            if info.flag_bits & 0x1:
                skipped.append(f"{info.filename} (parol bilan himoyalangan)")
                continue
            data = _read_limited(zf, info)
            name = PurePosixPath(info.filename).name
            files.append(ScannedFile(name, info.filename, len(data), hashlib.sha256(data).hexdigest(),
                                     read_tags(data, name), parse_filename(name)))
    return files, skipped


def _read_limited(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    buf = bytearray()
    with zf.open(info) as fh:
        while chunk := fh.read(1024 * 1024):
            buf += chunk
            if len(buf) > MAX_FILE_BYTES:  # sarlavhadagi hajm yolg'on bo'lsa ham
                raise VaultError(f"{info.filename}: e'lon qilingan hajmdan katta")
    return bytes(buf)


def read_zip_member(path: str | Path, member: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        return _read_limited(zf, zf.getinfo(member))


def import_root() -> Path | None:
    root = os.getenv("IMPORT_ROOT", "").strip()
    return Path(root).resolve() if root else None


def safe_folder(rel: str) -> Path:
    """IMPORT_ROOT ichidagi papka; tashqariga chiqish (../, symlink) taqiqlanadi."""
    root = import_root()
    if root is None:
        raise VaultError("IMPORT_ROOT sozlanmagan — papka importi o'chiq")
    target = (root / rel.strip().lstrip("/")).resolve()
    if target != root and root not in target.parents:
        raise VaultError("ruxsat etilmagan yo'l")
    if not target.is_dir():
        raise VaultError(f"papka topilmadi: {rel}")
    return target


def scan_folder(folder: Path) -> tuple[list[ScannedFile], list[str]]:
    root = import_root()
    files, skipped = [], []
    paths = sorted(p for p in folder.rglob("*") if p.is_file())
    if len(paths) > MAX_MEMBERS:
        raise VaultError(f"papkada {len(paths)} ta fayl — limit {MAX_MEMBERS}")
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if p.is_symlink() or not _is_audio_member(p.relative_to(folder).as_posix()):
            skipped.append(rel)
            continue
        if p.stat().st_size > MAX_FILE_BYTES:
            skipped.append(f"{rel} (juda katta)")
            continue
        data = p.read_bytes()
        files.append(ScannedFile(p.name, rel, len(data), hashlib.sha256(data).hexdigest(),
                                 read_tags(data, p.name), parse_filename(p.name)))
    return files, skipped


def read_folder_member(rel: str) -> bytes:
    root = import_root()
    if root is None:
        raise VaultError("IMPORT_ROOT sozlanmagan")
    p = (root / rel).resolve()
    if root not in p.parents:
        raise VaultError("ruxsat etilmagan yo'l")
    return p.read_bytes()


# --------------------------------------------------------------------------- #
# Metadata bilan moslash
# --------------------------------------------------------------------------- #
class Matcher:
    """Faylni CSV qatoriga moslaydi. Ustuvorlik: ISRC → file ustuni → ijrochi+nom → nom (yagona)
    → o'xshash nom (faqat bitta aniq nomzod bo'lsa)."""

    def __init__(self, rows: list[TrackMeta]) -> None:
        self.rows = rows
        self.by_isrc = {clean_isrc(r.isrc): r for r in rows if r.isrc}
        self.by_file = {norm(Path(r.file).stem): r for r in rows if r.file}
        self.by_name: dict[str, list[TrackMeta]] = {}
        self.by_title: dict[str, list[TrackMeta]] = {}
        for r in rows:
            self.by_name.setdefault(norm(f"{r.artist} {r.title}"), []).append(r)
            self.by_title.setdefault(norm(r.title), []).append(r)

    def match(self, f: ScannedFile) -> tuple[TrackMeta | None, str]:
        if not self.rows:
            return None, ""
        for isrc in (f.tags.get("isrc"), f.fname.get("isrc")):
            if isrc and clean_isrc(isrc) in self.by_isrc:
                return self.by_isrc[clean_isrc(isrc)], "csv:isrc"
        stem = norm(Path(f.name).stem)
        if stem in self.by_file:
            return self.by_file[stem], "csv:file"
        for src in (f.tags, f.fname):
            if src.get("title"):
                hits = self.by_name.get(norm(f"{src.get('artist', '')} {src['title']}"), [])
                if len(hits) == 1:
                    return hits[0], "csv:name"
        for src in (f.tags, f.fname):
            if src.get("title"):
                hits = self.by_title.get(norm(src["title"]), [])
                if len(hits) == 1:
                    return hits[0], "csv:title"
        title = norm(f.tags.get("title") or f.fname.get("title") or "")
        if title:
            scored = sorted(((difflib.SequenceMatcher(None, title, t).ratio(), t) for t in self.by_title),
                            reverse=True)
            if scored and scored[0][0] >= 0.9 and (len(scored) == 1 or scored[1][0] < 0.8) \
                    and len(self.by_title[scored[0][1]]) == 1:
                return self.by_title[scored[0][1]][0], "csv:fuzzy"
        return None, ""


def build_track(f: ScannedFile, row: TrackMeta | None, *, default_artist: str,
                license_id: str) -> tuple[TrackMeta | None, str]:
    """CSV > teglar > fayl nomi. Nom yoki ijrochi topilmasa (None, sabab)."""
    def pick(key):
        if row is not None and getattr(row, key, ""):
            return getattr(row, key)
        return f.tags.get(key) or f.fname.get(key) or ""

    title, artist = pick("title"), pick("artist") or default_artist
    if not title:
        return None, "nom topilmadi"
    if not artist:
        return None, "ijrochi topilmadi (/vault_artist bilan standart ijrochini kiriting)"
    return TrackMeta(
        title=title, artist=artist, album=pick("album"), isrc=clean_isrc(pick("isrc")),
        duration=(row.duration if row and row.duration else f.tags.get("duration", 0)),
        license_id=(row.license_id if row and row.license_id else license_id),
        license_expires=(row.license_expires if row else ""),
        external_id=(row.external_id if row else ""), file=f.name, provider="distrokid-vault",
    ), ""


# --------------------------------------------------------------------------- #
# Konvertatsiya va saqlash
# --------------------------------------------------------------------------- #
async def to_telegram_audio(data: bytes, filename: str, track: TrackMeta) -> tuple[bytes, str]:
    """MP3/M4A — o'zgarishsiz; WAV/FLAC/AIFF/OGG — MP3 320k ga (ffmpeg)."""
    ext = Path(filename).suffix.lower()
    out_name = f"{track.artist} - {track.title}"
    out_name = re.sub(r'[\\/:*?"<>|]+', "_", out_name)[:120]
    if ext in TELEGRAM_NATIVE:
        result, name = data, out_name + ext
    else:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-vn",
            "-codec:a", "libmp3lame", "-b:a", "320k",
            "-metadata", f"title={track.title}", "-metadata", f"artist={track.artist}",
            "-metadata", f"album={track.album}", "-f", "mp3", "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        result, err = await proc.communicate(data)
        if proc.returncode != 0 or not result:
            raise VaultError(f"MP3 ga o'girib bo'lmadi: {err.decode(errors='ignore')[:200]}")
        name = out_name + ".mp3"
    if len(result) > MAX_UPLOAD_BYTES:
        raise VaultError(f"fayl {len(result) // 1024 // 1024} MB — Telegram limiti 49 MB")
    return result, name


class ArchiveStorage:
    """Ixtiyoriy: originallarni ARCHIVE_DIR'ga sha256 nomi bilan saqlaydi (doimiy disk bo'lsa)."""

    def __init__(self) -> None:
        d = os.getenv("ARCHIVE_DIR", "").strip()
        self.dir = Path(d) if d else None

    @property
    def enabled(self) -> bool:
        return self.dir is not None

    def save(self, sha256: str, ext: str, data: bytes) -> str | None:
        if not self.dir:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{sha256}{ext.lower()}"
        if not path.exists():
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        return str(path)


class SourceCache:
    """Telegram'dagi ZIP/fayllarni vaqtinchalik diskka yuklaydi; server qayta yonsa,
    file_id orqali qayta yuklab oladi (resume)."""

    def __init__(self, base: str | None = None) -> None:
        self.base = Path(base or os.getenv("IMPORT_CACHE_DIR") or Path(tempfile.gettempdir()) / "bahti_import")

    def path(self, job_id: str, idx: int, ext: str) -> Path:
        return self.base / f"job{job_id}" / f"src{idx}{ext}"

    async def ensure(self, bot, job: dict, idx: int) -> Path:
        src = job["sources"][idx]
        p = self.path(job["id"], idx, Path(src["name"]).suffix.lower() or ".bin")
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(p.suffix + ".part")
            await bot.download(src["file_id"], destination=tmp)
            tmp.replace(p)
        return p

    def drop(self, job_id: str) -> None:
        d = self.base / f"job{job_id}"
        if d.exists():
            for f in d.iterdir():
                f.unlink(missing_ok=True)
            d.rmdir()

    async def read(self, bot, job: dict, item: dict) -> bytes:
        src = job["sources"][item["src"]]
        if src["type"] == "folder":
            return await asyncio.to_thread(read_folder_member, item["scan"]["member"])
        path = await self.ensure(bot, job, item["src"])
        if src["type"] == "tg_zip":
            return await asyncio.to_thread(read_zip_member, path, item["scan"]["member"])
        return await asyncio.to_thread(path.read_bytes)
