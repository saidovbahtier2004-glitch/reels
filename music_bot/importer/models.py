"""Import uchun ma'lumot modellari."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date


@dataclass
class TrackMeta:
    """Bitta litsenziyali trek metadata'si (CSV qatori yoki provider katalogidan)."""

    title: str
    artist: str
    license_id: str
    external_id: str = ""       # provider/distributor'dagi trek ID
    album: str = ""
    isrc: str = ""
    duration: int = 0           # soniya
    license_expires: str = ""   # YYYY-MM-DD, bo'sh = muddatsiz
    file: str = ""              # qo'lda yuklashda fayl nomi
    audio_url: str = ""         # provider bergan yuklab olish havolasi (faqat ruxsat etilgan host)
    provider: str = ""

    def license_problem(self, today: date) -> str | None:
        """Litsenziya bilan muammo bo'lsa sababini qaytaradi."""
        if not self.license_id.strip():
            return "license_id yo'q"
        if self.license_expires:
            try:
                if date.fromisoformat(self.license_expires) < today:
                    return f"litsenziya muddati tugagan ({self.license_expires})"
            except ValueError:
                return f"license_expires noto'g'ri sana: {self.license_expires}"
        return None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in ("", 0)}

    @classmethod
    def from_dict(cls, d: dict) -> "TrackMeta":
        names = {f.name for f in fields(cls)}
        data = {"title": "", "artist": "", "license_id": ""}
        data.update({k: v for k, v in d.items() if k in names})
        return cls(**data)

    def library_extra(self) -> dict:
        """Bazaga yoziladigan qo'shimcha maydonlar."""
        return {
            "title": self.title, "artist": self.artist, "album": self.album, "isrc": self.isrc,
            "license_id": self.license_id, "license_expires": self.license_expires,
            "provider": self.provider, "external_id": self.external_id,
        }


@dataclass
class AudioFile:
    """Provider'dan olingan audio (Telegram'ga yuklash uchun)."""

    data: bytes
    filename: str
    mime: str = "audio/mpeg"
