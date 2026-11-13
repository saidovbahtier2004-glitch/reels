"""Importer testlari: CSV, provider adapteri, batch, progress, resume va Telegram oqimi."""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp import web
from aiogram.methods import EditMessageText, SendAudio, SendMessage

import bot as botmod
from importer import providers as prov
from importer.csv_import import parse_csv
from importer.models import AudioFile, TrackMeta
from importer.providers import (CatalogPage, HttpDistributorProvider, MusicProvider, ProviderConfig,
                                ProviderError, SourceNotAllowed)
from importer.runner import DONE, FAILED, FINISHED, PAUSED, PENDING, RUNNING, SKIPPED, ImportManager, counts
from test_bot import ADMIN, CHANNEL, USER, _uid, channel_audio, env, feed, private_text, run, upd  # noqa: F401

CSV_OK = (
    "Nomi;Ijrochi;License;File;ISRC;Duration;License_Expires\n"
    "Xiyonat;Ummon;LIC-1;ummon_xiyonat.mp3;UZA012400001;3:48;2099-01-01\n"
    "Dengiz;Ummon;LIC-2;;;4:25;\n"
    "Eski;Ummon;LIC-3;;;;2001-01-01\n"
    "Litsenziyasiz;Ummon;;;;;\n"
    "Xiyonat;Ummon;LIC-1;;;;\n"
)


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def test_csv_parsing_and_validation():
    r = parse_csv(CSV_OK.encode("utf-8-sig"))
    assert [t.title for t in r.tracks] == ["Xiyonat", "Dengiz"]
    t = r.tracks[0]
    assert (t.artist, t.license_id, t.file, t.isrc, t.duration) == ("Ummon", "LIC-1", "ummon_xiyonat.mp3",
                                                                    "UZA012400001", 228)
    errs = "\n".join(r.errors)
    assert "muddati tugagan" in errs and "license_id yo'q" in errs and "takroriy" in errs


def test_csv_requires_license_column():
    r = parse_csv("title,artist\nA,B\n")
    assert r.tracks == [] and "license_id" in r.errors[0]


def test_csv_bad_isrc_and_duration():
    r = parse_csv("title,artist,license_id,isrc,duration\nA,B,L,BAD,\nC,D,L,,abc\n")
    assert r.tracks == [] and "ISRC" in r.errors[0] and "duration" in r.errors[1]


# --------------------------------------------------------------------------- #
# Provider adapteri
# --------------------------------------------------------------------------- #
def test_provider_config_from_env_hides_key(monkeypatch):
    monkeypatch.setenv("PROVIDER_DISTRIBUTOR_BASE_URL", "https://api.dist.example/v1/")
    monkeypatch.setenv("PROVIDER_DISTRIBUTOR_API_KEY", "SECRET123")
    monkeypatch.setenv("PROVIDER_DISTRIBUTOR_ALLOWED_HOSTS", "cdn.dist.example")
    cfg = ProviderConfig.from_env("distributor")
    assert cfg.configured and cfg.base_url == "https://api.dist.example/v1"
    assert cfg.allowed_hosts == ("api.dist.example", "cdn.dist.example")
    assert "SECRET123" not in repr(cfg)


def test_unauthorized_sources_blocked():
    p = HttpDistributorProvider(ProviderConfig("d", "https://api.dist.example", "k", ("api.dist.example",)))
    for url in ("https://www.youtube.com/watch?v=x", "http://api.dist.example/a.mp3",
                "https://evil.example/api.dist.example/a.mp3"):
        with pytest.raises(SourceNotAllowed):
            p.check_source(url)
    p.check_source("https://api.dist.example/a.mp3")


def test_unknown_provider():
    with pytest.raises(ProviderError):
        prov.create_provider("youtube")


async def _with_server(handler_map, fn):
    app = web.Application()
    for path, h in handler_map.items():
        app.router.add_get(path, h)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        return await fn(f"http://127.0.0.1:{port}")
    finally:
        await runner.cleanup()


def test_http_distributor_catalog_and_audio(monkeypatch):
    seen_auth = []

    async def catalog(req):
        seen_auth.append(req.headers.get("Authorization"))
        if req.query.get("cursor") == "p2":
            return web.json_response({"tracks": [{"id": "3", "title": "C", "artist": "Z", "license_id": "L3"}],
                                      "next_cursor": None})
        return web.json_response({"tracks": [
            {"id": "1", "title": "A", "artist": "X", "license_id": "L1", "isrc": "uza012400001", "duration": 200},
            {"id": "2", "title": "B", "artist": "Y", "license_id": "L2"}], "next_cursor": "p2"})

    async def audio(req):
        return web.Response(body=b"ID3fake", content_type="audio/mpeg")

    async def scenario(base):
        p = HttpDistributorProvider(ProviderConfig("distributor", base, "TOKEN", ("127.0.0.1",)))
        p.require_https = False
        page1 = await p.list_catalog(None, 10)
        page2 = await p.list_catalog(page1.next_cursor, 10)
        a = await p.fetch_audio(page1.tracks[0])
        await p.close()
        return page1, page2, a

    page1, page2, a = asyncio.run(_with_server({"/catalog": catalog, "/tracks/{id}/audio": audio}, scenario))
    assert [t.title for t in page1.tracks] == ["A", "B"] and page1.next_cursor == "p2"
    assert page1.tracks[0].isrc == "UZA012400001" and page1.tracks[0].provider == "distributor"
    assert page2.next_cursor is None
    assert a.data == b"ID3fake" and a.filename == "X - A.mp3"
    assert seen_auth[0] == "Bearer TOKEN"


def test_http_distributor_rejected_credentials():
    async def catalog(req):
        return web.Response(status=401)

    async def scenario(base):
        p = HttpDistributorProvider(ProviderConfig("distributor", base, "BAD", ("127.0.0.1",)))
        try:
            await p.list_catalog(None, 10)
        finally:
            await p.close()

    with pytest.raises(ProviderError, match="credential rad etildi"):
        asyncio.run(_with_server({"/catalog": catalog}, scenario))


def test_audio_rejects_non_audio_content():
    async def page(req):
        return web.Response(text="<html>", content_type="text/html")

    async def scenario(base):
        p = HttpDistributorProvider(ProviderConfig("distributor", base, "T", ("127.0.0.1",)))
        p.require_https = False
        try:
            await p.download(base + "/x", "x.mp3")
        finally:
            await p.close()

    with pytest.raises(ProviderError, match="audio emas"):
        asyncio.run(_with_server({"/x": page}, scenario))


# --------------------------------------------------------------------------- #
# Runner: batch, progress, resume
# --------------------------------------------------------------------------- #
class FakeProvider(MusicProvider):
    """2 sahifali katalog; 'flaky' trek birinchi urinishda xato beradi."""

    calls: list[str] = []

    def __init__(self, config=None):
        super().__init__(config or ProviderConfig("fake", "https://x", "k", ("x",)))
        self.flaky_failed = False

    async def list_catalog(self, cursor, limit):
        FakeProvider.calls.append(f"catalog:{cursor}")
        if cursor is None:
            return CatalogPage([TrackMeta("A", "X", "L1", external_id="1", provider="fake"),
                                TrackMeta("Old", "X", "L2", external_id="2", license_expires="2000-01-01",
                                          provider="fake"),
                                TrackMeta("Flaky", "X", "L3", external_id="3", provider="fake")], "p2")
        return CatalogPage([TrackMeta("B", "Y", "L4", external_id="4", provider="fake"),
                            TrackMeta("Blocked", "Y", "L5", external_id="5", provider="fake")], None)

    async def fetch_audio(self, track):
        FakeProvider.calls.append(f"audio:{track.external_id}")
        if track.title == "Flaky" and not self.flaky_failed:
            self.flaky_failed = True
            raise ProviderError("vaqtinchalik xato")
        if track.title == "Blocked":
            raise SourceNotAllowed("ruxsat etilmagan audio manbasi: evil.example")
        return AudioFile(b"mp3", f"{track.title}.mp3")


@pytest.fixture
def mgr(env):
    bot, dp, s, lib = env
    shared = FakeProvider()
    m = ImportManager(lambda: lib, batch_size=2, delay=0, provider_factory=lambda name: shared)
    m.bind(bot)
    FakeProvider.calls = []
    return m, bot, s, lib


def test_provider_catalog_import(mgr):
    m, bot, s, lib = mgr

    async def go():
        job = m.create_job("provider", [], provider="fake")
        m.start(job["id"])
        await m.wait(job["id"])
        return job
    job = run(go())
    c = counts(job)
    assert job["status"] == FINISHED and job["catalog_done"]
    assert (c[DONE], c[FAILED]) == (3, 2)  # A, Flaky (2-urinishda), B; Old=muddati o'tgan, Blocked
    titles = sorted(it["title"] for it in lib.active())
    assert titles == ["A", "B", "Flaky"]
    a = lib.find_existing(provider="fake", external_id="1")
    assert a["license_id"] == "L1" and a["provider"] == "fake" and a["import_job"] == job["id"]
    blocked = next(it for it in job["items"] if it["track"]["title"] == "Blocked")
    assert blocked["permanent"] and blocked["attempts"] == 1  # ruxsatsiz manbaga qayta urinilmaydi
    assert len(s.of(SendAudio)) == 3


def test_resume_after_restart_without_duplicates(mgr):
    m, bot, s, lib = mgr
    tracks = [TrackMeta(f"T{i}", "X", f"L{i}", external_id=str(i), provider="fake") for i in range(5)]

    async def first_run():
        job = m.create_job("csv_provider", tracks, provider="fake")
        m.on_progress = None
        orig = m._process

        async def stop_after_two(job, item, provider):
            await orig(job, item, provider)
            if counts(job)[DONE] == 2:
                raise asyncio.CancelledError  # server o'chib qoldi
        m._process = stop_after_two
        m.start(job["id"])
        with pytest.raises(asyncio.CancelledError):
            await m.wait(job["id"])
        return job
    job = run(first_run())
    assert job["status"] == RUNNING and counts(job)[DONE] == 2

    # "server qayta ishga tushdi": indeks JSON'dan qayta yuklanadi
    saved = json.loads(lib.dump())
    lib2 = botmod.Library()
    lib2.chat_id = CHANNEL
    lib2.load_data(saved)
    m2 = ImportManager(lambda: lib2, batch_size=2, delay=0, provider_factory=lambda n: FakeProvider())
    m2.bind(bot)

    async def resume():
        started = await m2.resume_all()
        await m2.wait(job["id"])
        return started
    assert run(resume()) == [job["id"]]
    job2 = lib2.jobs[job["id"]]
    assert job2["status"] == FINISHED and counts(job2)[DONE] == 5
    assert sorted(it["title"] for it in lib2.active()) == ["T0", "T1", "T2", "T3", "T4"]
    assert len(s.of(SendAudio)) == 5  # hech biri ikki marta yuklanmadi


def test_existing_tracks_skipped_and_pause(mgr):
    m, bot, s, lib = mgr
    lib.items.append({"id": 1, "title": "Xiyonat", "artist": "Ummon", "file_id": "F", "file_unique_id": "U",
                      "duration": 228, "key": "ummon xiyonat"})
    lib._reindex()

    async def go():
        job = m.create_job("csv_provider", [TrackMeta("Xiyonat", "Ummon", "L", duration=229, provider="fake"),
                                            TrackMeta("Yangi", "Ummon", "L", provider="fake")], provider="fake")
        m.pause(job)
        m.start(job["id"])
        await m.wait(job["id"])
        assert counts(job)[PENDING] == 2 and job["status"] == PAUSED  # pauzada hech narsa qilinmadi
        m.resume(job)
        await m.wait(job["id"])
        return job
    job = run(go())
    assert [it["status"] for it in job["items"]] == [SKIPPED, DONE]
    assert job["items"][0]["lib_id"] == 1


def test_channel_not_connected_pauses(mgr):
    m, bot, s, lib = mgr
    lib.chat_id = None

    async def go():
        job = m.create_job("csv_provider", [TrackMeta("A", "X", "L", provider="fake")], provider="fake")
        m.start(job["id"])
        await m.wait(job["id"])
        return job
    job = run(go())
    assert job["status"] == PAUSED and s.of(SendAudio) == []


# --------------------------------------------------------------------------- #
# Telegram oqimi: CSV hujjat + litsenziyali fayllar
# --------------------------------------------------------------------------- #
def admin_document(file_id, name, mime="text/csv", caption=None, user=ADMIN):
    _uid[0] += 1
    msg = {"message_id": 700 + _uid[0], "date": 1700000000, "chat": {"id": user, "type": "private"},
           "from": {"id": user, "is_bot": False, "first_name": "A"},
           "document": {"file_id": file_id, "file_unique_id": "uq" + file_id, "file_name": name,
                        "mime_type": mime, "file_size": 100}}
    if caption:
        msg["caption"] = caption
    return upd(message=msg)


def admin_audio(file_id, name, title=None, performer=None, user=ADMIN):
    _uid[0] += 1
    audio = {"file_id": file_id, "file_unique_id": "uq" + file_id, "duration": 200, "file_name": name,
             "file_size": 4_000_000}
    if title:
        audio["title"], audio["performer"] = title, performer
    return upd(message={"message_id": 800 + _uid[0], "date": 1700000000, "chat": {"id": user, "type": "private"},
                        "from": {"id": user, "is_bot": False, "first_name": "A"}, "audio": audio})


@pytest.fixture
def tg(env, monkeypatch):
    bot, dp, s, lib = env
    m = botmod.import_manager
    monkeypatch.setattr(m, "delay", 0)
    monkeypatch.setattr(m, "_tasks", {})
    m.bind(bot)

    async def no_recognize(src, workdir):
        return None
    monkeypatch.setattr(botmod, "recognize_file", no_recognize)
    return bot, dp, s, lib, m


def test_files_import_via_bot(tg):
    bot, dp, s, lib, m = tg
    s.files["CSV1"] = CSV_OK.encode()

    async def go():
        await feed(bot, dp, admin_document("CSV1", "tracks.csv"))
        job = next(iter(lib.jobs.values()))
        await feed(bot, dp,
                   admin_audio("A3", "Begona - Qoshiq.mp3"),                # CSV'da yo'q -> rad etiladi
                   admin_audio("A1", "ummon_xiyonat.mp3"),                  # file ustuni bo'yicha
                   admin_audio("A2", "track.mp3", title="Dengiz", performer="Ummon"))  # teglar bo'yicha
        await m.wait(job["id"])
        await asyncio.sleep(0.05)
        return job
    job = run(go())
    out = s.texts()
    assert "Yaroqli treklar: <b>2</b>" in out and "Rad etilgan qatorlar: <b>3</b>" in out
    assert out.count("navbatga qo'shildi") == 2 and "mos kelmadi" in out
    assert job["status"] == FINISHED and counts(job)[DONE] == 2
    uploads = s.of(SendAudio)
    assert [u.audio for u in uploads] == ["A1", "A2"]  # file_id bilan, qayta yuklab olinmagan
    assert all(u.chat_id == CHANNEL for u in uploads)
    x = lib.search("xiyonat")[0]
    assert (x["isrc"], x["license_id"], x["title"]) == ("UZA012400001", "LIC-1", "Xiyonat")
    edits = [c for c in s.calls if isinstance(c, EditMessageText) and "Import #" in c.text]
    assert edits and "100%" in edits[-1].text


def test_files_finish_and_status_commands(tg):
    bot, dp, s, lib, m = tg
    s.files["CSV2"] = CSV_OK.encode()

    async def go():
        await feed(bot, dp, admin_document("CSV2", "t.csv"))
        job = next(iter(lib.jobs.values()))
        await feed(bot, dp, private_text(f"/import_status {job['id']}", user=ADMIN),
                   private_text(f"/import_finish {job['id']}", user=ADMIN),
                   private_text("/import", user=ADMIN))
        return job
    job = run(go())
    assert job["status"] == FINISHED and counts(job)[SKIPPED] == 2
    out = s.texts()
    assert "Fayl kutilmoqda: 2" in out and "2 ta fayli kelmagan" in out and "Providerlar" in out


def test_import_admin_only_and_audio_falls_through(tg):
    bot, dp, s, lib, m = tg
    s.files["CSV3"] = CSV_OK.encode()
    run(feed(bot, dp, admin_document("CSV3", "t.csv", user=USER), private_text("/import", user=USER)))
    assert lib.jobs == {}
    assert "faqat adminlar" in s.texts()
    # admin'ning ochiq import'i bo'lsa ham, oddiy foydalanuvchi audiosi Shazam'ga boradi
    run(feed(bot, dp, admin_document("CSV3", "t.csv"), admin_audio("Z1", "ummon_xiyonat.mp3", user=USER)))
    edits = "\n".join(c.text for c in s.calls if isinstance(c, EditMessageText))
    assert "navbatga" not in s.texts() and "aniqlay olmadim" in edits


def test_csv_provider_requires_configuration(tg, monkeypatch):
    bot, dp, s, lib, m = tg
    monkeypatch.delenv("PROVIDER_DISTRIBUTOR_BASE_URL", raising=False)
    s.files["CSV4"] = CSV_OK.encode()
    run(feed(bot, dp, admin_document("CSV4", "t.csv", caption="provider distributor"),
             private_text("/import_sync distributor", user=ADMIN)))
    assert "sozlanmagan" in s.texts() and lib.jobs == {}


def test_jobs_persist_in_index(tg):
    bot, dp, s, lib, m = tg
    s.files["CSV5"] = CSV_OK.encode()
    run(feed(bot, dp, admin_document("CSV5", "t.csv")))
    data = json.loads(lib.dump())
    assert list(data["jobs"]) == ["1"] and len(data["jobs"]["1"]["items"]) == 2
