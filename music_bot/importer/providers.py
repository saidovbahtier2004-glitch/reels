"""Musiqa provider (distributor) adapterlari.

Yangi distributor ulash uchun MusicProvider'dan meros olib, ikkita metodni yozing:
  * list_catalog(cursor, limit) — litsenziyali treklar ro'yxati (sahifalab)
  * fetch_audio(track)           — trek audiosini distributor API'sidan olish
va PROVIDERS ro'yxatiga qo'shing.

Credential'lar faqat muhit o'zgaruvchilaridan olinadi (Render → Environment) va
hech qachon logga yozilmaydi:
  PROVIDER_<NOM>_BASE_URL       masalan https://api.distributor.example/v1
  PROVIDER_<NOM>_API_KEY        token (Authorization: Bearer ...)
  PROVIDER_<NOM>_ALLOWED_HOSTS  audio yuklanishi mumkin bo'lgan qo'shimcha hostlar (vergul bilan),
                                masalan distributor CDN'i. BASE_URL hosti doim ruxsat etilgan.

Audio faqat shu hostlardan yuklanadi — boshqa manbalar (YouTube, saytlar va h.k.) bloklanadi.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin, urlparse

import aiohttp

from .models import AudioFile, TrackMeta

log = logging.getLogger("music_bot.importer")

MAX_AUDIO_BYTES = 49 * 1024 * 1024  # Telegram bot API yuklash limiti 50 MB


class ProviderError(Exception):
    """Provider bilan bog'liq xato (xabarida credential bo'lmaydi)."""


class SourceNotAllowed(ProviderError):
    """Audio ruxsat etilmagan manbadan so'raldi."""


@dataclass
class ProviderConfig:
    name: str
    base_url: str = ""
    api_key: str = field(default="", repr=False)  # repr'da ko'rinmaydi
    allowed_hosts: tuple[str, ...] = ()
    timeout: int = 120

    @classmethod
    def from_env(cls, name: str) -> "ProviderConfig":
        prefix = f"PROVIDER_{name.upper()}_"
        base = os.getenv(prefix + "BASE_URL", "").strip().rstrip("/")
        extra = [h.strip().lower() for h in os.getenv(prefix + "ALLOWED_HOSTS", "").split(",") if h.strip()]
        hosts = tuple(filter(None, [urlparse(base).hostname or "", *extra]))
        return cls(name=name, base_url=base, api_key=os.getenv(prefix + "API_KEY", "").strip(),
                   allowed_hosts=hosts)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)


@dataclass
class CatalogPage:
    tracks: list[TrackMeta]
    next_cursor: str | None  # None = katalog tugadi


class MusicProvider(ABC):
    """Barcha distributor adapterlari uchun umumiy interfeys."""

    require_https = True  # audio faqat HTTPS orqali (testlarda o'chiriladi)

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        return self.config.name

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.timeout))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def check_source(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if (self.require_https and parsed.scheme != "https") or host not in self.config.allowed_hosts:
            raise SourceNotAllowed(f"ruxsat etilmagan audio manbasi: {host or url[:40]}")

    async def download(self, url: str, filename: str) -> AudioFile:
        """Faqat ruxsat etilgan hostdan, hajm limiti bilan yuklaydi."""
        self.check_source(url)
        s = await self.session()
        async with s.get(url) as resp:
            if resp.status != 200:
                raise ProviderError(f"audio yuklab bo'lmadi: HTTP {resp.status}")
            if resp.url.host and resp.url.host.lower() not in self.config.allowed_hosts:
                raise SourceNotAllowed(f"redirect ruxsat etilmagan hostga: {resp.url.host}")
            ctype = resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
            if not (ctype.startswith("audio/") or ctype == "application/octet-stream"):
                raise ProviderError(f"audio emas: {ctype}")
            size = int(resp.headers.get("Content-Length") or 0)
            if size > MAX_AUDIO_BYTES:
                raise ProviderError(f"fayl juda katta ({size // 1024 // 1024} MB > 49 MB)")
            data = bytearray()
            async for chunk in resp.content.iter_chunked(256 * 1024):
                data += chunk
                if len(data) > MAX_AUDIO_BYTES:
                    raise ProviderError("fayl juda katta (> 49 MB)")
        return AudioFile(bytes(data), filename, ctype if ctype.startswith("audio/") else "audio/mpeg")

    @abstractmethod
    async def list_catalog(self, cursor: str | None, limit: int) -> CatalogPage:
        """Litsenziyali treklar katalogining bitta sahifasi."""

    @abstractmethod
    async def fetch_audio(self, track: TrackMeta) -> AudioFile:
        """Trek audiosini distributor API'si orqali oladi."""


class HttpDistributorProvider(MusicProvider):
    """Umumiy REST distributor adapteri (shablon).

    Kutilayotgan API (distributor hujjatlari kelgach endpoint va maydon nomlarini moslang):
      GET {base}/catalog?cursor=<c>&limit=<n>
          -> {"tracks": [{"id", "title", "artist", "isrc", "duration", "album",
                          "license_id", "license_expires", "audio_url"}], "next_cursor": "..."|null}
      GET {base}/tracks/{id}/audio   (agar trekda audio_url bo'lmasa)
    """

    CATALOG_PATH = "catalog"
    AUDIO_PATH = "tracks/{id}/audio"

    async def list_catalog(self, cursor: str | None, limit: int) -> CatalogPage:
        if not self.config.configured:
            raise ProviderError(f"{self.name}: BASE_URL yoki API_KEY sozlanmagan")
        s = await self.session()
        params = {"limit": str(limit)}
        if cursor:
            params["cursor"] = cursor
        async with s.get(urljoin(self.config.base_url + "/", self.CATALOG_PATH), params=params) as resp:
            if resp.status == 401 or resp.status == 403:
                raise ProviderError(f"{self.name}: credential rad etildi (HTTP {resp.status})")
            if resp.status != 200:
                raise ProviderError(f"{self.name}: katalog xatosi HTTP {resp.status}")
            data = await resp.json(content_type=None)
        tracks = []
        for raw in data.get("tracks", []):
            tracks.append(TrackMeta(
                title=str(raw.get("title", "")), artist=str(raw.get("artist", "")),
                license_id=str(raw.get("license_id", "")), external_id=str(raw.get("id", "")),
                album=str(raw.get("album", "")), isrc=str(raw.get("isrc", "")).upper(),
                duration=int(raw.get("duration") or 0),
                license_expires=str(raw.get("license_expires", "") or ""),
                audio_url=str(raw.get("audio_url", "") or ""), provider=self.name,
            ))
        return CatalogPage(tracks, data.get("next_cursor"))

    async def fetch_audio(self, track: TrackMeta) -> AudioFile:
        if not self.config.configured:
            raise ProviderError(f"{self.name}: BASE_URL yoki API_KEY sozlanmagan")
        url = track.audio_url
        if not url:
            if not track.external_id:
                raise ProviderError("trekda audio_url ham, external_id ham yo'q")
            path = self.AUDIO_PATH.format(id=quote(track.external_id, safe=""))
            url = urljoin(self.config.base_url + "/", path)
        filename = f"{track.artist} - {track.title}.mp3"
        return await self.download(url, filename)


# Ro'yxatga yangi distributorlarni qo'shing: {"nom": AdapterKlassi}
PROVIDERS: dict[str, type[MusicProvider]] = {
    "distributor": HttpDistributorProvider,
}


def create_provider(name: str) -> MusicProvider:
    name = name.strip().lower()
    if name not in PROVIDERS:
        raise ProviderError(f"noma'lum provider: {name}. Mavjud: {', '.join(PROVIDERS)}")
    return PROVIDERS[name](ProviderConfig.from_env(name))


def provider_status() -> list[tuple[str, bool]]:
    return [(n, ProviderConfig.from_env(n).configured) for n in PROVIDERS]
