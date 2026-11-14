"""FMA treklarini bittalab tekshirish va CSV manifest yaratish (audio yuklanmaydi).

Har bir trek uchun:
  1. Litsenziya NOMI va URL'i alohida tahlil qilinadi — kod va versiya mos kelishi shart
  2. tracks.csv va raw_tracks.csv'dagi litsenziya nomi bir xil bo'lishi shart
  3. Litsenziya URL'i creativecommons.org'da bo'lishi shart
  4. Siyosat (licenses.Policy): CC0/PDM/BY/BY-SA, o'zgartirilmagan BY-ND; tijoriy bo'lsa NC yo'q
  5. Nom va ijrochi bor
  6. Audio rasmiy fma_full.zip ichida bor, hajmi > 0 va ≤ 49 MB (Telegram), rasmiy sha1 bor

Holatlar:
  verified      — hammasi o'tdi, yuklab olish mumkin
  needs_review  — huquqlar noaniq (nom va URL mos emas va h.k.) — YUKLANMAYDI
  excluded      — huquq bor, lekin texnik sabab (audio yo'q, juda katta) — yuklanmaydi

  python -m importer.fma_verify <fma_metadata papka> <arxiv_index.json> <checksums.txt> --out <fayl.csv>
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from .fma import iter_tracks
from .fma_report import LANG_CATEGORIES, lang_category, load_genres, load_raw
from .licenses import Policy, attribution, parse_license

MAX_UPLOAD = 49 * 1024 * 1024
ARCHIVE_URL = "https://os.unil.cloud.switch.ch/fma/fma_full.zip"
DATASET_URL = "https://github.com/mdeff/fma"
LANG_NAMES = dict(LANG_CATEGORIES) | {"unspecified": "belgilanmagan"}

COLUMNS = ["fma_id", "status", "reason", "title", "artist", "album", "language_code", "language", "genre_top",
           "genres", "license", "license_code", "license_title", "license_url", "attribution", "source_url",
           "artist_url", "audio_member", "audio_bytes", "audio_sha1", "duration"]


def member_name(fma_id: int) -> str:
    tid = f"{fma_id:06d}"
    return f"{tid[:3]}/{tid}.mp3"


def load_checksums(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 40:
            out[parts[1]] = parts[0]
    return out


def load_index(path: Path) -> dict[str, int]:
    """{'000/000002.mp3': bayt} — fma_full.zip central directory'dan."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {"/".join(k.split("/")[-2:]): v[0] for k, v in raw.items() if k.endswith(".mp3")}


def verify(folder: Path, index: dict[str, int], checksums: dict[str, str], commercial: bool = True):
    raw = load_raw(folder / "raw_tracks.csv")
    gnames, _ = load_genres(folder / "genres.csv")
    policy = Policy(commercial=commercial)
    rows, considered = [], 0
    for rec in iter_tracks(folder / "tracks.csv"):
        tid = rec["track_id"]
        r = raw.get(tid) or {}
        lic = parse_license(r.get("license_title", ""), r.get("license_url", ""))
        # faqat litsenziyasi siyosatdan o'tadiganlar (11 953) batafsil tekshiriladi
        if policy.check(lic, will_modify=False) is not None:
            continue
        considered += 1
        by_title = parse_license(r.get("license_title", ""))
        by_url = parse_license("", r.get("license_url", ""))
        problems, tech = [], []
        if by_title.code != by_url.code:
            problems.append(f"litsenziya nomi ({by_title.code}) va URL ({by_url.code}) mos emas")
        elif by_title.version and by_url.version and by_title.version != by_url.version:
            problems.append(f"versiya mos emas: nomi {by_title.version}, URL {by_url.version}")
        t_title = (rec.get("track.license") or "").strip()
        if t_title != r.get("license_title", ""):
            problems.append("tracks.csv va raw_tracks.csv litsenziyasi farq qiladi")
        if "creativecommons.org/" not in (r.get("license_url") or ""):
            problems.append("litsenziya URL'i creativecommons.org emas")
        title, artist = (rec.get("track.title") or "").strip(), (rec.get("artist.name") or "").strip()
        if not title or not artist:
            problems.append("nom yoki ijrochi yo'q")
        member = member_name(tid)
        size = index.get(member)
        sha1 = checksums.get(member, "")
        if size is None:
            tech.append("audio arxivda yo'q")
        elif size == 0:
            tech.append("audio fayl bo'sh")
        elif size > MAX_UPLOAD:
            tech.append("audio > 49 MB (o'zgartirmasdan yuborib bo'lmaydi)")
        else:
            try:
                dur = float(rec.get("track.duration") or 0)
            except ValueError:
                dur = 0
            if dur >= 5 and size < dur * 4000:  # < 32 kbps — fayl kesilgan yoki buzilgan bo'lishi mumkin
                tech.append("audio hajmi davomiyligiga mos emas (buzilgan bo'lishi mumkin)")
        if not sha1:
            tech.append("rasmiy sha1 yo'q")
        status = "needs_review" if problems else "excluded" if tech else "verified"
        try:
            gids = ast.literal_eval(rec.get("track.genres_all") or "[]")
        except (ValueError, SyntaxError):
            gids = []
        lang_code = (rec.get("track.language_code") or "").strip().lower()
        source_url = r.get("track_url", "")
        rows.append({
            "fma_id": tid, "status": status, "reason": "; ".join(problems + tech),
            "title": title, "artist": artist, "album": (rec.get("album.title") or "").strip(),
            "language_code": lang_code, "language": LANG_NAMES.get(lang_category(lang_code), lang_code),
            "genre_top": (rec.get("track.genre_top") or "").strip(),
            "genres": ", ".join(gnames.get(str(g), str(g)) for g in gids),
            "license": lic.short, "license_code": lic.code, "license_title": lic.title, "license_url": lic.url,
            "attribution": attribution(title, artist, lic, "Free Music Archive", source_url),
            "source_url": source_url, "artist_url": r.get("artist_url", ""),
            "audio_member": member if size else "", "audio_bytes": size or 0, "audio_sha1": sha1,
            "duration": rec.get("track.duration", ""),
        })
    return rows, considered


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM: Excel'da UTF-8 to'g'ri ochiladi
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def summary(rows: list[dict]) -> dict:
    st = Counter(r["status"] for r in rows)
    return {
        "total": len(rows), "status": dict(st),
        "by_license": {s: dict(Counter(r["license"] for r in rows if r["status"] == s).most_common())
                       for s in st},
        "license_all": dict(Counter(r["license"] for r in rows).most_common()),
        "reasons": dict(Counter(x for r in rows for x in r["reason"].split("; ") if x).most_common()),
        "verified_bytes": sum(r["audio_bytes"] for r in rows if r["status"] == "verified"),
        "verified_by_language": dict(Counter(r["language"] for r in rows if r["status"] == "verified")),
    }


def _dur(r: dict) -> float:
    try:
        return float(r.get("duration") or 0)
    except ValueError:
        return 0


def pick_test_batch(rows: list[dict], n: int = 20) -> list[dict]:
    """Test uchun xilma-xil 20 ta 'verified' trek: har litsenziya, ingliz bo'lmagan tillar, turli janrlar.
    Faqat odatiy qo'shiqlar (1–7 daqiqa, 1–15 MB). Natija har safar bir xil (deterministik)."""
    pool = sorted((r for r in rows if r["status"] == "verified" and 60 <= _dur(r) <= 420
                   and 1_000_000 <= r["audio_bytes"] <= 15_000_000),
                  key=lambda r: (r["audio_bytes"], r["fma_id"]))
    chosen: list[dict] = []
    ids: set[int] = set()

    def take(pred):
        for r in pool:
            if r["fma_id"] not in ids and pred(r):
                chosen.append(r)
                ids.add(r["fma_id"])
                return

    for lic in sorted({r["license"] for r in pool}):
        take(lambda r, lic=lic: r["license"] == lic)
    for code, _ in LANG_CATEGORIES:
        if code not in ("en", "other"):
            take(lambda r, code=code: r["language_code"] == code)
    for genre in sorted({r["genre_top"] for r in pool if r["genre_top"]}):
        if len(chosen) >= n:
            break
        take(lambda r, g=genre: r["genre_top"] == g)
    for r in pool:
        if len(chosen) >= n:
            break
        if r["fma_id"] not in ids:
            chosen.append(r)
            ids.add(r["fma_id"])
    return chosen[:n]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FMA treklarini bittalab tekshirish (audio yuklanmaydi)")
    ap.add_argument("folder", type=Path)
    ap.add_argument("index", type=Path, help="fma_full.zip central directory JSON")
    ap.add_argument("checksums", type=Path, help="fma_full/checksums")
    ap.add_argument("--out", type=Path, default=Path("fma_verified_tracks.csv"))
    ap.add_argument("--noncommercial", action="store_true")
    a = ap.parse_args(argv)
    rows, considered = verify(a.folder, load_index(a.index), load_checksums(a.checksums),
                              commercial=not a.noncommercial)
    write_csv(rows, a.out)
    s = summary(rows)
    test = pick_test_batch(rows)
    a.out.with_name("fma_test_batch.json").write_text(
        json.dumps([r["fma_id"] for r in test]), encoding="utf-8")
    json.dump(s, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
