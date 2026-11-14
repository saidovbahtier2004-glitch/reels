"""Creative Commons litsenziyalarini aniqlash va tarqatish siyosati.

Har bir trek o'z litsenziyasi bo'yicha alohida tekshiriladi. Aniqlab bo'lmagan
litsenziya — rad etiladi (hech qachon "ruxsat bor" deb taxmin qilinmaydi).

Siyosat:
  * CC0, Public Domain Mark            — ruxsat
  * CC BY, CC BY-SA                    — ruxsat (muallif, manba, litsenziya ko'rsatiladi)
  * CC BY-ND                           — faqat fayl O'ZGARTIRILMASA (MP3 aynan o'zi yuboriladi)
  * NonCommercial (NC) variantlari     — bot tijoriy bo'lsa (BOT_COMMERCIAL=1, standart) rad
  * Sampling+, "All rights reserved", FMA-Limited va noma'lum — rad
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# CC port (yurisdiksiya) kodlari — faqat ishonchli bilganlarimiz; qolganlarida URL qo'yilmaydi
JURISDICTIONS = {
    "united states": "us", "us": "us", "germany": "de", "france": "fr", "spain": "es", "italy": "it",
    "netherlands": "nl", "canada": "ca", "australia": "au", "japan": "jp", "brazil": "br",
    "mexico": "mx", "argentina": "ar", "poland": "pl", "austria": "at", "switzerland": "ch",
    "belgium": "be", "portugal": "pt", "ireland": "ie", "new zealand": "nz",
}


@dataclass(frozen=True)
class LicenseInfo:
    code: str          # cc0, pdm, by, by-sa, by-nd, by-nc, by-nc-sa, by-nc-nd, unknown
    version: str       # "4.0", "3.0", ...
    title: str         # manbadagi asl nomi
    url: str           # kanonik litsenziya URL (aniq bo'lmasa bo'sh)

    @property
    def noncommercial(self) -> bool:
        return "-nc" in self.code

    @property
    def no_derivatives(self) -> bool:
        return self.code.endswith("-nd")

    @property
    def requires_attribution(self) -> bool:
        return self.code.startswith("by")

    @property
    def short(self) -> str:
        if self.code == "cc0":
            return "CC0 1.0"
        if self.code == "pdm":
            return "Public Domain Mark"
        if self.code == "unknown":
            return self.title or "noma'lum"
        return f"CC {self.code.upper()} {self.version}".strip()


def parse_license(title: str = "", url: str = "") -> LicenseInfo:
    """Litsenziyani nomi va/yoki URL'idan aniqlaydi."""
    t = (title or "").strip()
    low = t.lower()
    u = (url or "").strip()

    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/(\d\.\d)(?:/([a-z\-]+))?/?$",
                  u.lower())
    if m:
        kind, code, version, port = m.groups()
        if kind == "publicdomain":
            code = "cc0" if code == "zero" else "pdm" if code == "mark" else "unknown"
        elif code not in {"by", "by-sa", "by-nd", "by-nc", "by-nc-sa", "by-nc-nd"}:
            code = "unknown"
        # manba bergan URL'ni qayta qurmaymiz (masalan .../2.5/scotland/), faqat https va oxirgi "/"
        canon = ("https://" + u.split("://", 1)[-1].rstrip("/") + "/") if code != "unknown" else ""
        return LicenseInfo(code, version, t or code, canon)

    if not low:
        return LicenseInfo("unknown", "", t, "")
    if "sampling" in low or "all rights reserved" in low or "fma-limited" in low or "download only" in low:
        return LicenseInfo("unknown", "", t, "")
    if "cc0" in low or "public domain dedication" in low or "zero" in low and "public domain" in low:
        return LicenseInfo("cc0", "1.0", t, _canonical_url("cc0", "1.0", None))
    if "public domain mark" in low:
        return LicenseInfo("pdm", "1.0", t, _canonical_url("pdm", "1.0", None))
    if "attribution" not in low and not re.search(r"\bcc[\s-]*by\b", low):
        return LicenseInfo("unknown", "", t, "")

    parts = ["by"]
    if re.search(r"non[\s-]?commercial|\bnc\b", low):
        parts.append("nc")
    if re.search(r"no[\s-]?deriv|\bnd\b", low):
        parts.append("nd")
    elif re.search(r"share[\s-]?alike|\bsa\b", low):
        parts.append("sa")
    code = "-".join(parts)
    vm = re.search(r"(\d\.\d)", low)
    version = vm.group(1) if vm else ""
    port = None
    if version and "international" not in low and "unported" not in low and "generic" not in low:
        tail = low.split(version, 1)[1].strip(" -")
        port = JURISDICTIONS.get(tail) if tail else None
        if tail and port is None:
            return LicenseInfo(code, version, t, "")  # yurisdiksiya noma'lum: URL'ni taxmin qilmaymiz
    return LicenseInfo(code, version, t, _canonical_url(code, version, port) if version else "")


def _canonical_url(code: str, version: str, port: str | None) -> str:
    if code == "cc0":
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    if code == "pdm":
        return "https://creativecommons.org/publicdomain/mark/1.0/"
    return f"https://creativecommons.org/licenses/{code}/{version}/" + (f"{port}/" if port else "")


@dataclass(frozen=True)
class Policy:
    commercial: bool = True          # bot reklama bilan ishlaydi -> tijoriy deb hisoblaymiz
    allow_nd: bool = True            # faqat o'zgartirilmagan fayl yuborilsa

    def check(self, lic: LicenseInfo, *, will_modify: bool = False) -> str | None:
        """None — ruxsat; aks holda rad etish sababi."""
        if lic.code == "unknown":
            return f"litsenziya aniqlanmadi yoki tarqatishga ruxsat bermaydi: {lic.title or 'yo`q'}"
        if lic.noncommercial and self.commercial:
            return f"{lic.short}: NonCommercial — bot tijoriy"
        if lic.no_derivatives and (will_modify or not self.allow_nd):
            return f"{lic.short}: NoDerivatives — faqat o'zgartirilmagan holda"
        return None


def attribution(title: str, artist: str, lic: LicenseInfo, source: str, source_url: str = "") -> str:
    """Muallifni ko'rsatish matni (TASL: Title, Author, Source, License)."""
    lic_part = f"{lic.short} ({lic.url})" if lic.url else lic.short
    src = f"{source}: {source_url}" if source_url else source
    return f"«{title}» — {artist}. {src}. Litsenziya: {lic_part}"
