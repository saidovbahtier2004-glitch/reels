"""DistroKid Vault importi: ZIP/papka/fayl, CSV moslash, konvertatsiya, resume, takrorlar, progress ekrani."""

from __future__ import annotations

import asyncio
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from aiogram.methods import EditMessageText, SendAudio, SendMessage

import bot as botmod
from importer.models import TrackMeta
from importer.runner import DONE, FAILED, FINISHED, PAUSED, PENDING, RUNNING, SKIPPED, WAITING, counts
from importer.vault import (Matcher, ScannedFile, VaultError, parse_filename, read_tags, safe_folder,
                            scan_zip)
from test_bot import ADMIN, CHANNEL, USER, _uid, env, feed, private_text, run, upd  # noqa: F401
from test_importer import admin_audio, admin_document  # noqa: F401


def make_audio(fmt: str, seconds: float = 1.0, freq: int = 440, **meta) -> bytes:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={seconds}"]
    for k, v in meta.items():
        args += ["-metadata", f"{k}={v}"]
    codec = {"mp3": ["-c:a", "libmp3lame", "-b:a", "64k", "-id3v2_version", "3"],
             "wav": ["-c:a", "pcm_s16le"], "flac": ["-c:a", "flac"]}[fmt]
    return subprocess.run(args + codec + ["-f", fmt, "pipe:1"], capture_output=True, check=True).stdout


@pytest.fixture(scope="module")
def audio():
    return {
        "mp3_tagged": make_audio("mp3", title="Xiyonat", artist="Ummon", album="Birinchi", ISRC="UZA012400001"),
        "wav": make_audio("wav", freq=550),
        "flac": make_audio("flac", freq=660),
        "mp3_dup": None,
    }


def vault_zip(audio, extra: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Vault/Album 1/01 - Ummon - Xiyonat.mp3", audio["mp3_tagged"])
        z.writestr("Vault/Album 1/02 Dengiz (UZA012400002).wav", audio["wav"])
        z.writestr("Vault/Album 1/03 - Tola.flac", audio["flac"])
        z.writestr("Vault/Album 1/cover.jpg", b"\xff\xd8jpg")
        z.writestr("__MACOSX/Vault/._01 - Ummon - Xiyonat.mp3", b"junk")
        z.writestr("Vault/copy/Xiyonat-copy.mp3", audio["mp3_tagged"])  # ZIP ichidagi takror
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Tahlil va moslash
# --------------------------------------------------------------------------- #
def test_parse_filename_patterns():
    assert parse_filename("01 - Ummon - Xiyonat.wav") == {"track": 1, "artist": "Ummon", "title": "Xiyonat"}
    assert parse_filename("Ummon - Tola (UZ-A01-24-00003).mp3") == {
        "isrc": "UZA012400003", "artist": "Ummon", "title": "Tola"}
    assert parse_filename("03 Dengiz.flac") == {"track": 3, "title": "Dengiz"}


def test_read_tags_from_real_files(audio):
    t = read_tags(audio["mp3_tagged"], "a.mp3")
    assert (t["title"], t["artist"], t["album"], t["isrc"]) == ("Xiyonat", "Ummon", "Birinchi", "UZA012400001")
    assert t["duration"] == 1
    assert "duration" not in read_tags(audio["wav"], "a.wav") or read_tags(audio["wav"], "a.wav")["duration"] == 1
    assert read_tags(make_wav_file(), "b.wav")["duration"] == 2  # to'g'ri sarlavhali WAV


def make_wav_file() -> bytes:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=2", str(out)], check=True)
        return out.read_bytes()


def test_scan_zip_skips_non_audio_and_reads_tags(audio, tmp_path):
    p = tmp_path / "v.zip"
    p.write_bytes(vault_zip(audio))
    files, skipped = scan_zip(p)
    assert sorted(f.name for f in files) == ["01 - Ummon - Xiyonat.mp3", "02 Dengiz (UZA012400002).wav",
                                             "03 - Tola.flac", "Xiyonat-copy.mp3"]
    assert any("cover.jpg" in s for s in skipped) and any("__MACOSX" in s for s in skipped)
    wav = next(f for f in files if f.name.endswith(".wav"))
    assert wav.fname["isrc"] == "UZA012400002" and len(wav.sha256) == 64


def test_scan_zip_limits(audio, tmp_path, monkeypatch):
    import importer.vault as v
    p = tmp_path / "v.zip"
    p.write_bytes(vault_zip(audio))
    monkeypatch.setattr(v, "MAX_MEMBERS", 2)
    with pytest.raises(VaultError, match="limit"):
        scan_zip(p)
    (tmp_path / "bad.zip").write_bytes(b"not a zip")
    with pytest.raises(VaultError, match="buzilgan"):
        scan_zip(tmp_path / "bad.zip")


def test_matcher_priorities():
    rows = [TrackMeta("Xiyonat", "Ummon", "", isrc="UZA012400001", album="A1"),
            TrackMeta("Dengiz", "Ummon", "", file="02 Dengiz.wav"),
            TrackMeta("Tola", "Ummon", ""),
            TrackMeta("Sevgi", "Ummon", ""), TrackMeta("Sevgi", "Boshqa", "")]
    m = Matcher(rows)

    def sf(name, tags=None):
        return ScannedFile(name, name, 1, "x", tags or {}, parse_filename(name))
    assert m.match(sf("whatever.mp3", {"isrc": "UZA012400001"})) == (rows[0], "csv:isrc")
    assert m.match(sf("02 Dengiz.wav")) == (rows[1], "csv:file")
    assert m.match(sf("Ummon - Tola.mp3")) == (rows[2], "csv:name")
    assert m.match(sf("Tolla.mp3"))[1] in ("", "csv:fuzzy")
    assert m.match(sf("Sevgi.mp3")) == (None, "")  # ikki nomzod — taxmin qilinmaydi
    assert m.match(sf("Ummon - Sevgi.mp3")) == (rows[3], "csv:name")


def test_safe_folder_blocks_traversal(tmp_path, monkeypatch):
    (tmp_path / "root" / "vault").mkdir(parents=True)
    monkeypatch.setenv("IMPORT_ROOT", str(tmp_path / "root"))
    assert safe_folder("vault") == (tmp_path / "root" / "vault").resolve()
    for bad in ("../", "../../etc", "/etc/../.."):
        with pytest.raises(VaultError):
            safe_folder(bad)
    monkeypatch.delenv("IMPORT_ROOT")
    with pytest.raises(VaultError, match="IMPORT_ROOT"):
        safe_folder("vault")


# --------------------------------------------------------------------------- #
# Bot oqimi
# --------------------------------------------------------------------------- #
@pytest.fixture
def tg(env, monkeypatch, tmp_path):
    bot, dp, s, lib = env
    m = botmod.import_manager
    monkeypatch.setattr(m, "delay", 0)
    monkeypatch.setattr(m, "_tasks", {})
    monkeypatch.setattr(m, "_license_ok", set())
    monkeypatch.setattr(m.cache, "base", tmp_path / "cache")
    monkeypatch.setattr(m.archive, "dir", tmp_path / "archive")
    m.bind(bot)

    async def no_recognize(src, workdir):
        return None
    monkeypatch.setattr(botmod, "recognize_file", no_recognize)
    return bot, dp, s, lib, m


def cb(data, user=ADMIN):
    return upd(callback_query={
        "id": str(_uid[0]), "chat_instance": "x", "data": data,
        "from": {"id": user, "is_bot": False, "first_name": "A"},
        "message": {"message_id": 4242, "date": 1700000000, "chat": {"id": user, "type": "private"}, "text": "…"}})


def zip_doc(file_id, name="vault.zip", size=1000):
    _uid[0] += 1
    return upd(message={"message_id": 900 + _uid[0], "date": 1700000000,
                        "chat": {"id": ADMIN, "type": "private"},
                        "from": {"id": ADMIN, "is_bot": False, "first_name": "A"},
                        "document": {"file_id": file_id, "file_unique_id": "uq" + file_id, "file_name": name,
                                     "mime_type": "application/zip", "file_size": size}})


def open_session(bot, dp):
    return feed(bot, dp, private_text("/vault", user=ADMIN), cb("imp:attest:0"))


def test_vault_requires_attestation_and_admin(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z0"] = vault_zip(audio)
    run(feed(bot, dp, private_text("/vault", user=USER), zip_doc("Z0")))
    assert "faqat adminlar" in s.texts() and lib.jobs == {}  # tasdiqsiz ZIP qabul qilinmaydi
    run(feed(bot, dp, private_text("/vault", user=ADMIN)))
    assert "Tasdiqlayman" in str(s.of(SendMessage)[-1].reply_markup) and lib.jobs == {}
    run(feed(bot, dp, cb("imp:attest:0", user=USER)))
    assert lib.jobs == {}


def test_vault_zip_csv_full_import(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z1"] = vault_zip(audio)
    s.files["C1"] = ("Song Title,Artist Name,ISRC,Album\n"
                     "Dengiz,Ummon,UZA012400002,Birinchi\n").encode()

    async def go():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, zip_doc("Z1"))
        before = {it["scan"]["name"]: it["status"] for it in job["items"]}
        await feed(bot, dp, admin_document("C1", "meta.csv"))
        await feed(bot, dp, private_text("/vault_artist Ummon", user=ADMIN))
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        await m.wait(job["id"])
        await asyncio.sleep(0.05)
        return job, before
    job, before = run(go())
    out = "\n".join(c.text for c in s.calls if isinstance(c, (SendMessage, EditMessageText)))
    assert "Audio topildi: 4" in out and "Takroriy: 1" in out
    assert before["03 - Tola.flac"] == WAITING  # nom fayl nomidan bor, ijrochi yo'q -> /vault_artist kutadi
    c = counts(job)
    assert job["status"] == FINISHED and c[DONE] == 3 and c[FAILED] == 0
    assert job["attestation"]["by"] == ADMIN

    uploads = s.of(SendAudio)
    assert len(uploads) == 3 and all(u.chat_id == CHANNEL for u in uploads)
    names = sorted(u.audio.filename for u in uploads)
    assert names == ["Ummon - Dengiz.mp3", "Ummon - Tola.mp3", "Ummon - Xiyonat.mp3"]  # WAV/FLAC -> MP3
    wav_up = next(u for u in uploads if u.title == "Dengiz")
    assert wav_up.audio.data[:3] == b"ID3" or wav_up.audio.data[:2] == b"\xff\xfb"
    assert read_tags(wav_up.audio.data, "x.mp3")["title"] == "Dengiz"

    d = lib.search("dengiz")[0]
    assert (d["isrc"], d["album"], d["provider"]) == ("UZA012400002", "Birinchi", "distrokid-vault")
    assert d["license_id"].startswith("own-master:vault-job-") and len(d["sha256"]) == 64
    assert d["source_file"].endswith("02 Dengiz (UZA012400002).wav")
    x = lib.search("xiyonat")[0]
    assert x["isrc"] == "UZA012400001"  # teglardan
    # arxiv: originallar sha256 nomi bilan saqlandi
    assert sorted(p.suffix for p in m.archive.dir.iterdir()) == [".flac", ".mp3", ".wav"]
    # kesh tozalandi
    assert not (m.cache.base / f"job{job['id']}").exists()
    # progress ekrani yangilandi va tugmalari bor
    screens = [c for c in s.calls if isinstance(c, EditMessageText) and "DistroKid Vault" in c.text]
    assert screens and "100%" in screens[-1].text
    # foydalanuvchi qidiruvi va file_id orqali yetkazish ishlaydi
    run(feed(bot, dp, private_text("dengiz"), cb(f"l:{d['id']}", user=USER)))
    assert s.of(SendAudio)[-1].audio == d["file_id"]


def test_flac_without_artist_waits_until_default_artist(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z2"] = vault_zip(audio)

    async def go():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, zip_doc("Z2"))
        return job
    job = run(go())
    flac = next(it for it in job["items"] if it["scan"]["name"].endswith(".flac"))
    assert flac["status"] == WAITING and "ijrochi" in flac["error"]
    run(feed(bot, dp, cb(f"imp:unmatched:{job['id']}")))
    assert "03 - Tola.flac" in s.texts()
    run(feed(bot, dp, private_text("/vault_artist Ummon", user=ADMIN)))
    assert flac["status"] == PENDING and flac["track"]["artist"] == "Ummon"


def test_reimport_same_backup_is_all_duplicates(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z3"] = vault_zip(audio)

    async def import_once(fid):
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, private_text("/vault_artist Ummon", user=ADMIN), zip_doc(fid))
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        await m.wait(job["id"])
        return job
    run(import_once("Z3"))
    first = len(s.of(SendAudio))
    s.files["Z3b"] = s.files["Z3"]
    job2 = run(import_once("Z3b"))
    assert len(s.of(SendAudio)) == first == 3
    assert counts(job2)[SKIPPED] == 3 and "Bazada bor: 3" in s.texts()


def test_resume_after_restart_redownloads_zip(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z4"] = vault_zip(audio)

    async def first():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, private_text("/vault_artist Ummon", user=ADMIN), zip_doc("Z4"))
        orig = m._process

        async def crash_after_one(job, item, provider):
            await orig(job, item, provider)
            if counts(job)[DONE] == 1:
                raise asyncio.CancelledError
        m._process = crash_after_one
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        with pytest.raises(asyncio.CancelledError):
            await m.wait(job["id"])
        del m._process
        return job
    job = run(first())
    assert job["status"] == RUNNING and counts(job)[DONE] == 1
    m.cache.drop(job["id"])  # yangi server: vaqtinchalik disk bo'sh

    saved = json.loads(lib.dump())
    lib2 = botmod.Library()
    lib2.chat_id = CHANNEL
    lib2.load_data(saved)
    from importer.runner import ImportManager
    m2 = ImportManager(lambda: lib2, delay=0)
    m2.cache.base, m2.archive.dir = m.cache.base, None
    m2.bind(bot)

    async def resume():
        await m2.resume_all()
        await m2.wait(job["id"])
    run(resume())
    j2 = lib2.jobs[job["id"]]
    assert j2["status"] == FINISHED and counts(j2)[DONE] == 3
    assert len(s.of(SendAudio)) == 3  # birinchisi qayta yuklanmadi
    assert len(lib2.by_sha) == 3


def test_progress_screen_pause_resume(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["Z5"] = vault_zip(audio)

    async def go():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, private_text("/vault_artist Ummon", user=ADMIN), zip_doc("Z5"))
        m.delay = 0.05
        await feed(bot, dp, cb(f"imp:start:{job['id']}"), settle=0.01)
        await feed(bot, dp, cb(f"imp:pause:{job['id']}"))
        await m.wait(job["id"])
        paused_done = counts(job)[DONE]
        status = job["status"]
        await feed(bot, dp, cb(f"imp:resume:{job['id']}"))
        await m.wait(job["id"])
        return job, paused_done, status
    job, paused_done, status = run(go())
    assert status == PAUSED and paused_done < 3
    assert job["status"] == FINISHED and counts(job)[DONE] == 3
    kb_texts = [str(c.reply_markup) for c in s.calls if isinstance(c, EditMessageText) and c.reply_markup]
    assert any("Davom ettirish" in t for t in kb_texts) and any("Pauza" in t for t in kb_texts)
    run(feed(bot, dp, private_text("/imports", user=ADMIN)))
    assert "imp:open:" in str(s.of(SendMessage)[-1].reply_markup)


def test_single_audio_files_and_large_zip(tg, audio):
    bot, dp, s, lib, m = tg
    s.files["F1"] = audio["mp3_tagged"]

    async def go():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, admin_audio("F1", "track.mp3"), admin_audio("F1", "track.mp3"),
                   zip_doc("ZBIG", size=25 * 1024 * 1024))
        return job
    job = run(go())
    out = s.texts()
    assert len(job["items"]) == 1 and job["items"][0]["track"]["title"] == "Xiyonat"
    replies = "\n".join(c.text for c in s.calls if isinstance(c, (SendMessage, EditMessageText)))
    assert "Ummon — Xiyonat qo'shildi" in replies and "allaqachon qo'shilgan" in replies
    assert "20 MB dan katta" in replies


def test_folder_import(tg, audio, tmp_path, monkeypatch):
    bot, dp, s, lib, m = tg
    root = tmp_path / "imports"
    (root / "vault" / "a").mkdir(parents=True)
    (root / "vault" / "a" / "Ummon - Xiyonat.mp3").write_bytes(audio["mp3_tagged"])
    (root / "vault" / "a" / "notes.txt").write_text("x")
    monkeypatch.setenv("IMPORT_ROOT", str(root))

    async def go():
        await open_session(bot, dp)
        job = m.vault_job()
        await feed(bot, dp, private_text("/vault_folder ../..", user=ADMIN),
                   private_text("/vault_folder vault", user=ADMIN))
        await feed(bot, dp, cb(f"imp:start:{job['id']}"))
        await m.wait(job["id"])
        return job
    job = run(go())
    assert "ruxsat etilmagan yo'l" in s.texts()
    assert counts(job)[DONE] == 1 and lib.search("xiyonat")[0]["source_file"] == "vault/a/Ummon - Xiyonat.mp3"
