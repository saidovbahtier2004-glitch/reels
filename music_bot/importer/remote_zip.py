"""Masofadagi katta ZIP'dan (FMA fma_full.zip, 879 GiB) alohida fayllarni HTTP Range orqali o'qish.

Butun arxiv yuklanmaydi: avval oxiridagi fayl ro'yxati (central directory) o'qiladi,
keyin faqat kerakli treklarning baytlari olinadi. Faqat ALLOWED_HOSTS'dagi rasmiy manba.
"""

from __future__ import annotations

import io
import logging
import urllib.request
from urllib.parse import urlparse

log = logging.getLogger("music_bot.importer")

# FMA dataset'ining rasmiy tarqatish manzili (github.com/mdeff/fma README)
ALLOWED_HOSTS = {"os.unil.cloud.switch.ch"}


class RemoteSourceError(Exception):
    pass


def check_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https" or (p.hostname or "").lower() not in ALLOWED_HOSTS:
        raise RemoteSourceError(f"ruxsat etilmagan manba: {p.hostname or url[:40]}")


class HttpRangeFile(io.RawIOBase):
    """Faqat o'qish uchun, seek qilinadigan HTTP fayl (Range so'rovlari bilan)."""

    def __init__(self, url: str, block: int = 1 << 20, timeout: int = 120) -> None:
        check_url(url)
        self.url, self.block, self.timeout = url, block, timeout
        self.pos = 0
        self.requests = 0
        self.bytes_fetched = 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise RemoteSourceError("server Range so'rovlarini qo'llamaydi")
            self.size = int(r.headers["Content-Length"])
            self.etag = r.headers.get("ETag", "")
        self._buf_start, self._buf = -1, b""

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def _fetch(self, start: int, end: int) -> bytes:
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end - 1}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status != 206:
                raise RemoteSourceError(f"Range javobi kutilmagan: HTTP {r.status}")
            if self.etag and r.headers.get("ETag") and r.headers["ETag"] != self.etag:
                raise RemoteSourceError("arxiv serverda o'zgargan (ETag mos emas)")
            data = r.read()
        self.requests += 1
        self.bytes_fetched += len(data)
        return data

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        start, end = self.pos, self.pos + n
        b0 = self._buf_start
        if b0 <= start and end <= b0 + len(self._buf):
            out = self._buf[start - b0:end - b0]
        elif n >= self.block:
            out = self._fetch(start, end)
        else:  # kichik o'qishlar (ZIP sarlavhalari) uchun blok bilan oldindan o'qiymiz
            fend = min(self.size, start + self.block)
            self._buf_start, self._buf = start, self._fetch(start, fend)
            out = self._buf[:n]
        self.pos = end
        return out

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)
