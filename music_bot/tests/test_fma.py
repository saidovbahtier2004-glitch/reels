"""Free Music Archive: litsenziya siyosati, tracks.csv o'qish, sanash, import, resume va takrorlar."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from aiogram.methods import EditMessageText, SendAudio, SendMessage

import bot as botmod
from importer import fma
from importer.licenses import Policy, attribution, parse_license
from importer.runner import DONE, FAILED, FINISHED, PENDING, RUNNING, SKIPPED, ImportManager, counts
from importer.vault import VaultError
from test_bot import ADMIN, CHANNEL, USER, _uid, env, feed, private_text, run, upd  # noqa: F401


# --------------------------------------------------------------------------- #
# Litsenziyalar
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title,code,url", [
    ("Attribution 4.0 International", "by", "https://creativecommons.org/licenses/by/4.0/"),
    ("Attribution-ShareAlike 3.0 United States", "by-sa", "https://creativecommons.org/licenses/by-sa/3.0/us/"),
    ("Attribution-NoDerivatives 4.0 International", "by-nd", "https://creativecommons.org/licenses/by-nd/4.0/"),
    ("Attribution-NonCommercial-ShareAlike 3.0 International", "by-nc-sa",
     "https://creativecommons.org/licenses/by-nc-sa/3.0/"),
    ("Attribution-Noncommercial-No Derivative Works 3.0 United States", "by-nc-nd",
     "https://creativecommons.org/licenses/by-nc-nd/3.0/us/"),
    ("Attribution 3.0 Hungary", "by", ""),          # port noma'lum: URL taxmin qilinmaydi
    ("CC0 1.0 Universal", "cc0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ("Public Domain Mark 1.0", "pdm", "https://creativecommons.org/publicdomain/mark/1.0/"),
    ("Creative Commons Sampling+ 1.0", "unknown", ""),
    ("FMA-Limited: Download Only", "unknown", ""),
    ("", "unknown", ""),
])
def test_parse_license_titles(title, code, url):
    lic = parse_license(title)
    assert (lic.code, lic.url) == (code, url)


def test_parse_license_url():
    lic = parse_license(url="https://creativecommons.org/licenses/by-nc-nd/4.0/")
    assert lic.code == "by-nc-nd" and lic.noncommercial and lic.no_derivatives


def test_policy():
    commercial, free = Policy(commercial=True), Policy(commercial=False)
    by, nc, nd, unk = (parse_license(t) for t in ("Attribution 4.0 International",
                                                   "Attribution-NonCommercial 4.0 International",
                                                   "Attribution-NoDerivatives 4.0 International", "All rights reserved"))
    assert commercial.check(by) is None
    assert "NonCommercial" in commercial.check(nc) and free.check(nc) is None
    assert commercial.check(nd) is None and "NoDerivatives" in commercial.check(nd, will_modify=True)
    assert commercial.check(unk) and free.check(unk)


def test_attribution_text():
    lic = parse_license("Attribution-ShareAlike 4.0 International")
    t = attribution("Song", "Artist", lic, "Free Music Archive, trek #5")
    assert t == ("«Song» — Artist. Free Music Archive, trek #5. Litsenziya: CC BY-SA 4.0 "
                 "(https://creativecommons.org/licenses/by-sa/4.0/)")


# --------------------------------------------------------------------------- #
# Sintetik dataset (FMA formati)
# --------------------------------------------------------------------------- #
COLUMNS = [("album", "title"), ("artist", "name"), ("artist", "website"), ("set", "subset"),
           ("track", "duration"), ("track", "genre_top"), ("track", "language_code"),
           ("track", "license"), ("track", "title")]

ROWS = [  # id, album, artist, website, subset, dur, genre, lang, license, title
    (2, "Al, bum", "AWOL", "http://awol.example", "small", "168", "Hip-Hop", "en",
     "Attribution-NonCommercial-ShareAlike 3.0 International", "Food"),
    (3, "A", "Ozoda", "", "large", "200", "Pop", "uz", "Attribution 4.0 International", "Bahor"),
    (5, "B", "Ivan", "", "large", "210", "Rock", "ru", "Attribution-NoDerivatives 4.0 International",
     "Pesnya \"1\""),
    (10, "C", "Kim", "", "large", "190", "International", "ko", "CC0 1.0 Universal", "Haneul"),
    (11, "C", "Kim", "", "large", "190", "Experimental", "", "Attribution 4.0 International", "Noise"),
    (12, "D", "Sam", "", "large", "180", "Jazz", "", "Attribution-ShareAlike 4.0 International", "Blue"),
    (13, "D", "Sam", "", "large", "180", "Jazz", "", "Creative Commons Sampling+ 1.0", "Sample"),
    (14, "E", "Ana", "", "large", "180", "Folk", "es", "Attribution 4.0 International", "Sin audio"),
    (15, "E", "Ana", "", "large", "180", "Folk", "es", "Attribution-ShareAlike 3.0 United States", "Copia"),
]


def tracks_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([""] + [a for a, _ in COLUMNS])
    w.writerow([""] + [b for _, b in COLUMNS])
    w.writerow(["track_id"] + [""] * len(COLUMNS))  # pandas yozadigan indeks-nomi qatori
    for r in ROWS:
        tid, album, artist, web, subset, dur, genre, lang, lic, title = r
        rec = {("album", "title"): album, ("artist", "name"): artist, ("artist", "website"): web,
               ("set", "subset"): subset, ("track", "duration"): dur, ("track", "genre_top"): genre,
               ("track", "language_code"): lang, ("track", "license"): lic, ("track", "title"): title}
        w.writerow([tid] + [rec[c] for c in COLUMNS])
    return buf.getvalue()


def mp3(freq: int) -> bytes:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                           f"sine=frequency={freq}:duration=1", "-c:a", "libmp3lame", "-b:a", "32k", "-f", "mp3",
                           "pipe:1"], capture_output=True, check=True).stdout


@pytest.fixture(scope="module")
def audio_bytes():
    out = {tid: mp3(200 + tid * 10) for tid, *_ in ROWS if tid != 14}  # 14 — audio yo'q
    out[15] = out[3]  # 15 — 3 bilan bir xil fayl (takror)
    return out


@pytest.fixture
def dataset(tmp_path, monkeypatch, audio_bytes):
    root = tmp_path / "imports"
    (root / "fma_metadata").mkdir(parents=True)
    (root / "fma_metadata" / "tracks.csv").write_text(tracks_csv(), encoding="utf-8")
    for tid, data in audio_bytes.items():
        p = root / "fma_full" / fma.audio_member(tid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    with zipfile.ZipFile(root / "fma_full.zip", "w") as z:
        for tid, data in audio_bytes.items():
            z.writestr("fma_full/" + fma.audio_member(tid), data)
    monkeypatch.setenv("IMPORT_ROOT", str(root))
    monkeypatch.setenv("FMA_METADATA", "fma_metadata/tracks.csv")
    monkeypatch.setenv("FMA_AUDIO", "fma_full")
    monkeypatch.delenv("BOT_COMMERCIAL", raising=False)
    monkeypatch.delenv("FMA_GENRES", raising=False)
    monkeypatch.delenv("FMA_LANGUAGES", raising=False)
    return root


def test_iter_tracks_reads_multiheader(dataset):
    recs = list(fma.iter_tracks(dataset / "fma_metadata" / "tracks.csv"))
    assert [r["track_id"] for r in recs] == [r[0] for r in ROWS]
    assert recs[0]["album.title"] == "Al, bum" and recs[2]["track.title"] == 'Pesnya "1"'


def test_iter_tracks_rejects_unexpected_format(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("title,artist\nA,B\n")
    with pytest.raises(VaultError, match="ustunlar yo'q"):
        list(fma.iter_tracks(p))


@pytest.mark.parametrize("audio", ["fma_full", "fma_full.zip"])
def test_count_catalog(dataset, audio):
    s = fma.Settings.from_env()
    s.audio = audio
    rep = fma.count_catalog(s)
    assert rep.rows == 9
    # yaroqli: 3 (BY), 5 (BY-ND), 10 (CC0), 12 (BY-SA), 15 (BY-SA 3.0 US; fayl 3 bilan bir xil —
    # takror import paytida sha256 bo'yicha aniqlanadi)
    assert sorted(rep.eligible_ids) == [3, 5, 10, 12, 15]
    assert rep.reasons == {"NonCommercial (bot tijoriy)": 1, "janr filtrdan tashqarida": 1,
                           "litsenziya noma'lum / ruxsat yo'q": 1, "audio fayl yo'q": 1}
    assert rep.languages["uz"] == 1 and rep.languages["—"] == 1
    assert rep.genres["Pop"] == 1 and rep.genres["World Music"] == 1


def test_count_noncommercial_mode_and_language_filter(dataset, monkeypatch):
    monkeypatch.setenv("BOT_COMMERCIAL", "0")
    monkeypatch.setenv("FMA_LANGUAGES", "en,uz")
    rep = fma.count_catalog(fma.Settings.from_env())
    assert sorted(rep.eligible_ids) == [2, 3]  # NC ruxsat, lekin faqat en/uz


def test_count_rejects_oversized(dataset, monkeypatch):
    monkeypatch.setattr(fma, "MAX_UPLOAD", 10)
    rep = fma.count_catalog(fma.Settings.from_env())
    assert rep.eligible == 0 and rep.reasons["audio > 49 MB (o'zgartirmasdan yuborib bo'lmaydi)"] == 5


def test_resolve_blocks_traversal(dataset):
    with pytest.raises(VaultError):
        fma.resolve("../../etc/passwd")


# --------------------------------------------------------------------------- #
# Bot oqimi
# --------------------------------------------------------------------------- #
@pytest.fixture
def tg(env, monkeypatch, dataset):
    bot, dp, s, lib = env
    m = botmod.import_manager
    monkeypatch.setattr(m, "delay", 0)
    monkeypatch.setattr(m, "_tasks", {})
    m.bind(bot)
    return bot, dp, s, lib, m


def cb(data, user=ADMIN):
    return upd(callback_query={
        "id": str(_uid[0]), "chat_instance": "x", "data": data,
        "from": {"id": user, "is_bot": False, "first_name": "A"},
        "message": {"message_id": 4343, "date": 1700000000, "chat": {"id": user, "type": "private"}, "text": "…"}})


def count_job(bot, dp, m):
    async def go():
        await feed(bot, dp, private_text("/fma", user=ADMIN), cb("imp:fmacount:0"))
        job = m.fma_job()
        await m.wait(job["id"])
        return job
    return run(go())


def test_fma_count_then_import(tg, audio_bytes):
    bot, dp, s, lib, m = tg
    job = count_job(bot, dp, m)
    out = "\n".join(c.text for c in s.calls if isinstance(c, (SendMessage, EditMessageText)))
    assert "✅ Metadata" in out and "✅ Audio" in out
    assert job["status"] == "collecting" and counts(job)[PENDING] == 5
    assert "Yaroqli: <b>5</b>" in out and "yetmaydi</b> — yana 49 995" in out
    assert "O'zbek 1" in out and s.of(SendAudio) == []  # sanash hech narsa yuklamaydi

    async def start():
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        await m.wait(job["id"])
    run(start())
    c = counts(job)
    assert job["status"] == FINISHED and (c[DONE], c[SKIPPED]) == (4, 1)  # 15 = 3 ning takrori
    ups = s.of(SendAudio)
    assert len(ups) == 4 and all(u.chat_id == CHANNEL for u in ups)
    by_title = {u.title: u for u in ups}
    assert by_title["Bahor"].audio.data == audio_bytes[3]  # fayl o'zgartirilmagan (ND talabi)
    nd = lib.find_existing(provider="fma", external_id="5")
    assert nd["license_code"] == "by-nd" and nd["license_url"] == "https://creativecommons.org/licenses/by-nd/4.0/"
    assert "Ivan" in nd["attribution"] and "CC BY-ND 4.0" in nd["attribution"]
    assert nd["source"] == "Free Music Archive" and nd["dataset_url"] == fma.DATASET_URL
    assert nd["language"] == "ru" and nd["genre"] == "Rock"
    # foydalanuvchiga muallif va litsenziya bilan yetkaziladi
    run(feed(bot, dp, cb(f"l:{nd['id']}", user=USER)))
    sent = s.of(SendAudio)[-1]
    assert sent.audio == nd["file_id"] and "CC BY-ND 4.0" in sent.caption and "Ivan" in sent.caption
    assert lib.search("bahor")[0]["artist"] == "Ozoda"


def test_fma_reimport_skips_everything(tg):
    bot, dp, s, lib, m = tg

    def full():
        job = count_job(bot, dp, m)

        async def start():
            await feed(bot, dp, cb(f"imp:start:{job['id']}"))
            await m.wait(job["id"])
        run(start())
        return job
    full()
    n = len(s.of(SendAudio))
    job2 = full()
    assert len(s.of(SendAudio)) == n == 4 and counts(job2)[SKIPPED] == 5


def test_fma_resume_after_restart(tg):
    bot, dp, s, lib, m = tg
    job = count_job(bot, dp, m)

    async def crash():
        orig = m._process_fma

        async def stop_after_two(job, item):
            await orig(job, item)
            if counts(job)[DONE] == 2:
                raise asyncio.CancelledError
        m._process_fma = stop_after_two
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        with pytest.raises(asyncio.CancelledError):
            await m.wait(job["id"])
        del m._process_fma
        m._fma_close(job)
    run(crash())
    assert job["status"] == RUNNING and counts(job)[DONE] == 2

    saved = json.loads(lib.dump())
    lib2 = botmod.Library()
    lib2.chat_id = CHANNEL
    lib2.load_data(saved)
    m2 = ImportManager(lambda: lib2, delay=0)
    m2.bind(bot)

    async def resume():
        await m2.resume_all()
        await m2.wait(job["id"])
    run(resume())
    j2 = lib2.jobs[job["id"]]
    assert j2["status"] == FINISHED and counts(j2)[DONE] == 4 and len(s.of(SendAudio)) == 4


def test_fma_admin_only_and_unconfigured(tg, monkeypatch):
    bot, dp, s, lib, m = tg
    run(feed(bot, dp, private_text("/fma", user=USER), cb("imp:fmacount:0", user=USER)))
    assert "faqat adminlar" in s.texts() and lib.jobs == {}
    monkeypatch.setenv("FMA_METADATA", "yoq/tracks.csv")
    run(feed(bot, dp, private_text("/fma", user=ADMIN), cb("imp:fmacount:0")))
    assert "❌ Metadata" in s.texts() and lib.jobs == {}


def test_fma_job_items_are_compact(tg):
    bot, dp, s, lib, m = tg
    job = count_job(bot, dp, m)
    assert set(job["items"][0]) == {"n", "fma_id", "status"}
    assert len(json.dumps(job["items"][0])) < 60  # 50 000 trek ~ 3 MB
