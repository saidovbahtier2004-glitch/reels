"""FMA metadata tahlili: litsenziya, til va janr bo'yicha hisobot (audio yuklanmaydi).

Kirish (fma_metadata.zip ichidan):
  tracks.csv      — 106 574 trek, asosiy ro'yxat
  raw_tracks.csv  — FMA'ning o'zi bergan license_url va track_url (atribusiya uchun)
  genres.csv      — janr ierarxiyasi

Ishga tushirish:
  python -m importer.fma_report <papka> [--noncommercial] [--out hisobot]
Natija: hisobot.md (o'qish uchun) va hisobot.json (raqamlar + yaroqli treklar ro'yxati).
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .fma import iter_tracks
from .licenses import Policy, parse_license

TELEGRAM_LIMIT = 49 * 1024 * 1024

# 10 ta til toifasi (+ "belgilanmagan" alohida — u til emas)
LANG_CATEGORIES = [("uz", "O'zbek"), ("ru", "Rus"), ("en", "Ingliz"), ("tr", "Turk"), ("ar", "Arab"),
                   ("hi", "Hind"), ("ko", "Koreys"), ("es", "Ispan"), ("fr", "Fransuz"), ("other", "Boshqa tillar")]
LANG_CODES = {c for c, _ in LANG_CATEGORIES if c != "other"}

# So'ralgan janrlar -> FMA janr nomlari (genres.csv'dagi aniq nomlar)
GENRE_TARGETS = {
    "Pop": ["Pop"], "Rap": ["Rap"], "Hip-Hop": ["Hip-Hop"], "R&B": ["Soul-RnB"], "Rock": ["Rock"],
    "EDM": ["Dance", "Techno", "House", "Dubstep", "Drum & Bass", "Trance", "Breakbeat", "Jungle", "Bigbeat",
            "Hardcore"],
    "House": ["House"], "Jazz": ["Jazz"], "Classical": ["Classical"], "Folk": ["Folk"],
    "Electronic": ["Electronic"], "World Music": ["International"],
}


def lang_category(code: str) -> str:
    code = (code or "").strip().lower()
    if not code:
        return "unspecified"
    return code if code in LANG_CODES else "other"


def load_raw(path: Path) -> dict[int, dict]:
    """raw_tracks.csv: track_id -> {license_title, license_url, track_url, artist_url}."""
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            tid = (r.get("track_id") or "").strip()
            if tid.isdigit():
                tf = (r.get("track_file") or "").strip()
                out[int(tid)] = {"license_title": (r.get("license_title") or "").strip(),
                                 "license_url": (r.get("license_url") or "").strip(),
                                 "track_url": (r.get("track_url") or "").strip(),
                                 "album_url": (r.get("album_url") or "").strip(),
                                 "artist_url": (r.get("artist_url") or "").strip(),
                                 "curator": (tf.split("/") + ["", ""])[1] if tf.startswith("music/") else "",
                                 "context": " ".join((r.get(k) or "") for k in
                                                     ("track_information", "album_title", "artist_website"))[:3000]}
    return out


def load_genres(path: Path) -> tuple[dict[str, str], dict[str, set[str]]]:
    """genre_id -> nom, va so'ralgan janr -> FMA genre_id'lar to'plami."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    names = {r["genre_id"]: r["title"] for r in rows}
    by_title = {r["title"]: r["genre_id"] for r in rows}
    targets = {k: {by_title[t] for t in titles if t in by_title} for k, titles in GENRE_TARGETS.items()}
    return names, targets


def est_size(rec: dict) -> int:
    try:
        return int(float(rec.get("track.bit_rate") or 0) / 8 * float(rec.get("track.duration") or 0))
    except ValueError:
        return 0


@dataclass
class Report:
    commercial: bool
    total: int = 0
    licenses_all: Counter = field(default_factory=Counter)
    license_codes_all: Counter = field(default_factory=Counter)
    eligible: int = 0
    eligible_licenses: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)
    langs_all: Counter = field(default_factory=Counter)
    langs_eligible: Counter = field(default_factory=Counter)
    lang_codes_eligible_other: Counter = field(default_factory=Counter)
    genres_all: Counter = field(default_factory=Counter)
    genres_eligible: Counter = field(default_factory=Counter)
    genre_top_eligible: Counter = field(default_factory=Counter)
    lang_genre_eligible: dict = field(default_factory=lambda: defaultdict(Counter))
    nd_eligible: int = 0
    too_big_est: int = 0
    missing_raw: int = 0
    license_mismatch: int = 0
    no_license_url: int = 0
    rejected_titles: Counter = field(default_factory=Counter)
    eligible_rows: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "commercial": self.commercial, "total": self.total, "eligible": self.eligible,
            "licenses_all": dict(self.licenses_all.most_common()),
            "license_codes_all": dict(self.license_codes_all.most_common()),
            "eligible_licenses": dict(self.eligible_licenses.most_common()),
            "reasons": dict(self.reasons.most_common()),
            "languages_all": dict(self.langs_all), "languages_eligible": dict(self.langs_eligible),
            "other_language_codes_eligible": dict(self.lang_codes_eligible_other.most_common()),
            "genres_all": dict(self.genres_all), "genres_eligible": dict(self.genres_eligible),
            "genre_top_eligible": dict(self.genre_top_eligible.most_common()),
            "language_x_genre_eligible": {k: dict(v) for k, v in self.lang_genre_eligible.items()},
            "nd_eligible": self.nd_eligible, "eligible_over_49mb_estimated": self.too_big_est,
            "missing_in_raw_tracks": self.missing_raw, "license_title_mismatch_raw_vs_tracks": self.license_mismatch,
            "eligible_without_license_url": self.no_license_url,
            "rejected_non_cc_titles": dict(self.rejected_titles.most_common()),
        }


def analyze(folder: Path, commercial: bool = True) -> Report:
    raw = load_raw(folder / "raw_tracks.csv")
    gnames, gtargets = load_genres(folder / "genres.csv")
    policy = Policy(commercial=commercial)
    rep = Report(commercial=commercial)
    for rec in iter_tracks(folder / "tracks.csv"):
        rep.total += 1
        tid = rec["track_id"]
        r = raw.get(tid)
        if r is None:
            rep.missing_raw += 1
        title_t = (rec.get("track.license") or "").strip()
        lic = parse_license(r["license_title"] if r else title_t, r["license_url"] if r else "")
        if r and title_t and r["license_title"] and title_t != r["license_title"]:
            rep.license_mismatch += 1
        rep.licenses_all[lic.title or "(bo'sh)"] += 1
        rep.license_codes_all[lic.short if lic.code != "unknown" else "ruxsat yo'q / noma'lum"] += 1

        lang = lang_category(rec.get("track.language_code", ""))
        rep.langs_all[lang] += 1
        try:
            gids = {str(g) for g in ast.literal_eval(rec.get("track.genres_all") or "[]")}
        except (ValueError, SyntaxError):
            gids = set()
        hit = [name for name, ids in gtargets.items() if gids & ids]
        for name in hit:
            rep.genres_all[name] += 1

        title, artist = (rec.get("track.title") or "").strip(), (rec.get("artist.name") or "").strip()
        problem = policy.check(lic, will_modify=False)
        if problem:
            if lic.noncommercial and commercial:
                rep.reasons["NonCommercial (bot tijoriy)"] += 1
            else:
                rep.reasons["litsenziya noma'lum / qayta tarqatishga ruxsat yo'q"] += 1
                rep.rejected_titles[lic.title or "(bo'sh)"] += 1
            continue
        if not title or not artist:
            rep.reasons["nom yoki ijrochi yo'q"] += 1
            continue
        rep.eligible += 1
        rep.eligible_licenses[lic.short] += 1
        rep.langs_eligible[lang] += 1
        if lang == "other":
            rep.lang_codes_eligible_other[rec.get("track.language_code", "").strip().lower()] += 1
        for name in hit:
            rep.genres_eligible[name] += 1
            rep.lang_genre_eligible[lang][name] += 1
        rep.genre_top_eligible[(rec.get("track.genre_top") or "").strip() or "(bir nechta / yo'q)"] += 1
        if lic.no_derivatives:
            rep.nd_eligible += 1
        size = est_size(rec)
        if size > TELEGRAM_LIMIT:
            rep.too_big_est += 1
        if not lic.url:
            rep.no_license_url += 1
        rep.eligible_rows.append({
            "fma_id": tid, "title": title, "artist": artist, "language": rec.get("track.language_code", ""),
            "genre_top": rec.get("track.genre_top", ""), "license": lic.short, "license_code": lic.code,
            "license_title": lic.title, "license_url": lic.url,
            "source_url": r["track_url"] if r else "", "artist_url": r["artist_url"] if r else "",
            "est_bytes": size,
        })
    return rep


def sp(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def to_markdown(rep: Report, other: Report | None = None, target: int = 50_000) -> str:
    L = []
    mode = "tijoriy — NC chiqarib tashlangan" if rep.commercial else "notijoriy — NC ham kiritilgan"
    L.append("# FMA katalogi: litsenziya hisoboti\n")
    L.append(f"Manba: FMA dataset `fma_metadata.zip` (sha1 tekshirilgan), 2017 snapshot. Audio yuklanmagan.\n")
    L.append(f"- Jami treklar: **{sp(rep.total)}**")
    L.append(f"- Qayta tarqatish mumkin ({mode}): **{sp(rep.eligible)}** "
             f"({rep.eligible * 100 / max(rep.total, 1):.1f}%)")
    verdict = "**YETADI**" if rep.eligible >= target else f"**YETMAYDI** — {sp(target - rep.eligible)} ta kam"
    L.append(f"- Maqsad {sp(target)}: {verdict}")
    if other is not None:
        L.append(f"- Taqqoslash uchun, agar bot notijoriy bo'lsa: {sp(other.eligible)} ta yaroqli")
    L.append("")
    L.append("## Til toifalari bo'yicha (10 toifa)\n")
    L.append("| Til | Jami treklar | Yaroqli |" + (" Notijoriy bo'lsa |" if other else ""))
    L.append("|---|---:|---:|" + ("---:|" if other else ""))
    for code, name in LANG_CATEGORIES:
        row = f"| {name} | {sp(rep.langs_all.get(code, 0))} | **{sp(rep.langs_eligible.get(code, 0))}** |"
        if other:
            row += f" {sp(other.langs_eligible.get(code, 0))} |"
        L.append(row)
    row = f"| *Til belgilanmagan* | {sp(rep.langs_all.get('unspecified', 0))} | " \
          f"{sp(rep.langs_eligible.get('unspecified', 0))} |"
    if other:
        row += f" {sp(other.langs_eligible.get('unspecified', 0))} |"
    L.append(row)
    if rep.lang_codes_eligible_other:
        L.append("\n«Boshqa tillar» ichida (yaroqli): " + ", ".join(
            f"{k} {sp(v)}" for k, v in rep.lang_codes_eligible_other.most_common(15)))
    L.append("\n## Litsenziyalar (barcha treklar)\n")
    L.append("| Litsenziya | Treklar |\n|---|---:|")
    for k, v in rep.license_codes_all.most_common():
        L.append(f"| {k} | {sp(v)} |")
    L.append("\n## Yaroqli treklar litsenziyasi\n")
    L.append("| Litsenziya | Treklar |\n|---|---:|")
    for k, v in rep.eligible_licenses.most_common():
        L.append(f"| {k} | {sp(v)} |")
    L.append(f"\nShundan CC BY-ND: {sp(rep.nd_eligible)} — faqat o'zgartirilmagan holda yuboriladi.")
    L.append("\n## Rad etilganlar\n")
    for k, v in rep.reasons.most_common():
        L.append(f"- {k}: {sp(v)}")
    if rep.rejected_titles:
        L.append("\nRuxsat etilgan ro'yxatda bo'lmagan litsenziyalar (qo'lda ko'rib chiqish mumkin, hozir rad etilgan):\n")
        L.append("| Litsenziya | Treklar |\n|---|---:|")
        for k, v in rep.rejected_titles.most_common():
            L.append(f"| {k} | {sp(v)} |")
    L.append("\n## Janrlar\n")
    L.append("Bitta trek bir nechta janrga tushishi mumkin (FMA `genres_all`), shuning uchun yig'indi jamidan katta.\n")
    L.append("| Janr | Jami | Yaroqli |\n|---|---:|---:|")
    for name in GENRE_TARGETS:
        L.append(f"| {name} | {sp(rep.genres_all.get(name, 0))} | **{sp(rep.genres_eligible.get(name, 0))}** |")
    L.append("\n## Ma'lumot sifati\n")
    L.append(f"- raw_tracks.csv'da topilmagan: {sp(rep.missing_raw)}")
    L.append(f"- tracks.csv va raw_tracks.csv litsenziya nomi farqi: {sp(rep.license_mismatch)}")
    L.append(f"- Yaroqli, lekin litsenziya URL'i yo'q: {sp(rep.no_license_url)}")
    L.append(f"- Yaroqli, lekin taxminan 49 MB dan katta (Telegram limiti): {sp(rep.too_big_est)}")
    L.append("\nEslatma: audio fayllar mavjudligi va haqiqiy hajmi audio bosqichida tekshiriladi. "
             "Dataset 2017 yilniki; CC litsenziyalari qaytarib olinmaydi, lekin muhim treklarni joriy "
             "FMA sahifasida tekshirish tavsiya etiladi.")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FMA metadata litsenziya hisoboti (audio yuklanmaydi)")
    ap.add_argument("folder", type=Path, help="tracks.csv, raw_tracks.csv, genres.csv joylashgan papka")
    ap.add_argument("--noncommercial", action="store_true", help="bot notijoriy (NC treklar ham ruxsat)")
    ap.add_argument("--target", type=int, default=50_000)
    ap.add_argument("--out", type=Path, default=Path("fma_report"))
    a = ap.parse_args(argv)
    main_rep = analyze(a.folder, commercial=not a.noncommercial)
    other = analyze(a.folder, commercial=a.noncommercial) if not a.noncommercial else None
    md = to_markdown(main_rep, other, a.target)
    a.out.with_suffix(".md").write_text(md, encoding="utf-8")
    data = main_rep.to_dict() | {"eligible_tracks": main_rep.eligible_rows}
    if other:
        data["noncommercial_comparison"] = other.to_dict()
    a.out.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
