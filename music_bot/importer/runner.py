"""Batch import: job'lar, progress va davom ettirish (resume).

Job holati kutubxona indeksi (library.json, kanalda pin qilingan) ichida saqlanadi —
server qayta ishga tushsa ham progress yo'qolmaydi va "running" job'lar o'zi davom etadi.

Job turlari:
  files         — CSV + admin botga yuborgan litsenziyali audio fayllar
  csv_provider  — CSV'dagi treklar audiosi distributor API'sidan olinadi
  provider      — distributor katalogi to'liq sinxronlanadi (sahifalab, cursor bilan)
  vault         — DistroKid Vault backup'lari (ZIP / papka / fayllar) + ixtiyoriy CSV
  fma           — Free Music Archive dataset'i: avval sanash (counting), keyin import

Trek holatlari: waiting_file → pending → done | skipped | failed
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import BufferedInputFile, Message

from .models import AudioFile, TrackMeta
from .providers import MusicProvider, ProviderError, SourceNotAllowed, create_provider
from .text import norm
from . import fma
from .licenses import Policy
from .vault import (ArchiveStorage, Matcher, ScannedFile, SourceCache, VaultError, build_track,
                    to_telegram_audio)

log = logging.getLogger("music_bot.importer")
TZ = timezone(timedelta(hours=5))

WAITING, PENDING, DONE, SKIPPED, FAILED = "waiting_file", "pending", "done", "skipped", "failed"
COLLECTING, RUNNING, PAUSED, FINISHED, CANCELLED = "collecting", "running", "paused", "done", "cancelled"
COUNTING = "counting"
ACTIVE = (COUNTING, COLLECTING, RUNNING, PAUSED)
LOG_LIMIT = 30


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def counts(job: dict) -> dict:
    c = {WAITING: 0, PENDING: 0, DONE: 0, SKIPPED: 0, FAILED: 0}
    for it in job["items"]:
        c[it["status"]] = c.get(it["status"], 0) + 1
    c["total"] = len(job["items"])
    return c


class ImportManager:
    def __init__(self, library_getter: Callable[[], object], *, batch_size: int = 20,
                 delay: float = 3.5, max_attempts: int = 3,
                 provider_factory: Callable[[str], MusicProvider] = create_provider) -> None:
        self._lib = library_getter
        self.bot: Bot | None = None
        self.batch_size = batch_size
        self.delay = delay  # kanalga ~20 xabar/daqiqa limiti
        self.max_attempts = max_attempts
        self.provider_factory = provider_factory
        self.on_progress: Callable[[dict], Awaitable[None]] | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self.cache = SourceCache()
        self.archive = ArchiveStorage()
        self._upload_lock = asyncio.Lock()  # bir vaqtda bitta job kanalga yozadi

    # ---- holat ----
    @property
    def library(self):
        return self._lib()

    @property
    def jobs(self) -> dict[str, dict]:
        return self.library.jobs

    def bind(self, bot: Bot) -> None:
        self.bot = bot

    def save(self, job: dict | None = None) -> None:
        if job is not None:
            job["updated"] = now_iso()
        if self.bot is not None:
            self.library.schedule_save(self.bot)

    def note(self, job: dict, text: str) -> None:
        job.setdefault("log", []).append(f"{datetime.now(TZ):%H:%M} {text}")
        del job["log"][:-LOG_LIMIT]
        log.warning("Import #%s: %s", job["id"], text)

    def get(self, job_id: str) -> dict | None:
        return self.jobs.get(str(job_id).lstrip("#"))

    def is_running(self, job_id: str) -> bool:
        t = self._tasks.get(job_id)
        return t is not None and not t.done()

    def create_job(self, kind: str, tracks: list[TrackMeta], *, provider: str = "",
                   owner: int | None = None) -> dict:
        job_id = str(max((int(k) for k in self.jobs if k.isdigit()), default=0) + 1)
        initial = WAITING if kind == "files" else PENDING
        job = {
            "id": job_id, "kind": kind, "provider": provider, "owner": owner,
            "status": COLLECTING if kind in ("files", "vault") else RUNNING,
            "created": now_iso(), "updated": now_iso(),
            "cursor": None, "catalog_done": kind != "provider",
            "items": [{"n": i + 1, "track": t.to_dict(), "status": initial, "attempts": 0}
                      for i, t in enumerate(tracks)],
            "log": [],
        }
        self.jobs[job_id] = job
        self.save(job)
        log.info("Import #%s yaratildi: %s, %s ta trek", job_id, kind, len(tracks))
        return job

    # ---- qo'lda yuklangan fayllar ----
    def files_jobs(self) -> list[dict]:
        return [j for j in self.jobs.values() if j["kind"] == "files" and j["status"] in ACTIVE
                and any(it["status"] == WAITING for it in j["items"])]

    def match_file(self, file_name: str, title: str, artist: str) -> tuple[dict, dict] | None:
        """Yuborilgan faylni CSV qatoriga moslaydi: avval fayl nomi, keyin teglar / 'Ijrochi - Nomi'."""
        stem = norm(file_name.rsplit(".", 1)[0]) if file_name else ""
        candidates = []
        if stem:
            candidates.append(stem)
        if title:
            candidates.append(norm(f"{artist} {title}"))
        if " - " in (file_name or ""):
            a, t = file_name.rsplit(".", 1)[0].split(" - ", 1)
            candidates.append(norm(f"{a} {t}"))
        for job in self.files_jobs():
            for it in job["items"]:
                if it["status"] != WAITING:
                    continue
                tr = it["track"]
                keys = {norm(f"{tr.get('artist', '')} {tr.get('title', '')}")}
                if tr.get("file"):
                    keys.add(norm(tr["file"].rsplit(".", 1)[0]))
                if keys & set(candidates):
                    return job, it
        return None

    def attach_file(self, job: dict, item: dict, file_id: str, file_uid: str) -> None:
        item.update(file_id=file_id, file_uid=file_uid, status=PENDING)
        if job["status"] == COLLECTING:
            job["status"] = RUNNING
        self.save(job)
        if job["status"] == RUNNING:
            self.start(job["id"])

    # ---- DistroKid Vault ----
    def vault_job(self) -> dict | None:
        """Hozir fayl qabul qilayotgan (boshlanmagan) Vault sessiyasi."""
        for j in sorted(self.jobs.values(), key=lambda j: int(j["id"]), reverse=True):
            if j["kind"] == "vault" and j["status"] == COLLECTING:
                return j
        return None

    def create_vault_job(self, owner: int) -> dict:
        job = self.create_job("vault", [], provider="distrokid-vault", owner=owner)
        job.update(sources=[], csv=[], default_artist="",
                   attestation={"by": owner, "at": now_iso(),
                                "text": "Admin fayllar o'ziga tegishli original yozuvlar ekanini tasdiqladi"})
        self.save(job)
        return job

    def add_vault_source(self, job: dict, source: dict, files: list[ScannedFile]) -> dict:
        """Manbadagi audiolarni job'ga qo'shadi. Natija: qo'shildi / takroriy / bazada bor."""
        job["sources"].append(source)
        idx = len(job["sources"]) - 1
        seen = {it["scan"].get("sha256") for it in job["items"] if it["scan"].get("sha256")}
        res = {"added": 0, "dup_in_job": 0, "in_library": 0}
        for f in files:
            if f.sha256 and f.sha256 in seen:
                res["dup_in_job"] += 1
                continue
            seen.add(f.sha256)
            item = {"n": len(job["items"]) + 1, "src": idx, "scan": f.to_dict(), "track": {},
                    "status": PENDING, "attempts": 0}
            if source["type"] == "tg_file" and source.get("direct"):
                item.update(direct_file_id=source["file_id"], file_uid=source.get("file_uid"))
            existing = self.library.by_sha.get(f.sha256) if f.sha256 else None
            if existing is None and item.get("file_uid"):
                existing = self.library.by_uid.get(item["file_uid"])
            if existing is not None:
                item.update(status=SKIPPED, error="bazada bor (bir xil fayl)", lib_id=existing["id"])
                res["in_library"] += 1
            job["items"].append(item)
            res["added"] += 1
        self.rematch(job)
        return res

    def apply_csv(self, job: dict, tracks: list[TrackMeta]) -> None:
        job["csv"] = [t.to_dict() for t in tracks]
        self.rematch(job)

    def rematch(self, job: dict) -> None:
        matcher = Matcher([TrackMeta.from_dict(d) for d in job.get("csv", [])])
        license_id = f"own-master:vault-job-{job['id']}"
        for it in job["items"]:
            if it["status"] not in (PENDING, WAITING):
                continue
            f = ScannedFile(**it["scan"])
            row, reason = matcher.match(f)
            track, problem = build_track(f, row, default_artist=job.get("default_artist", ""),
                                         license_id=license_id)
            if track is None:
                it.update(track={}, match="", status=WAITING, error=problem)
            else:
                it.update(track=track.to_dict(), match=reason or ("tags" if f.tags.get("title") else "filename"),
                          status=PENDING, error=None)
        self.save(job)

    # ---- Free Music Archive ----
    def fma_job(self) -> dict | None:
        for j in sorted(self.jobs.values(), key=lambda j: int(j["id"]), reverse=True):
            if j["kind"] == "fma" and j["status"] in ACTIVE:
                return j
        return None

    def create_fma_job(self, owner: int, settings: "fma.Settings") -> dict:
        job = self.create_job("fma", [], provider="fma", owner=owner)
        job.update(status=COUNTING, settings=settings.to_dict(), report=None, counted_rows=0)
        self.save(job)
        self._tasks[job["id"]] = asyncio.create_task(self._count(job))
        return job

    def create_fma_test_job(self, owner: int, ids: list[int], audio: str = fma.ARCHIVE_URL) -> dict:
        """Tasdiqlangan ro'yxatdan aniq treklar bilan test importi (sanashsiz, admin boshlaydi)."""
        settings = fma.Settings(metadata="", audio=audio, manifest="builtin", ids=tuple(ids), mode="test")
        job = self.create_job("fma", [], provider="fma", owner=owner)
        job.update(status=COLLECTING, settings=settings.to_dict(), counted_rows=len(ids),
                   items=[{"n": i + 1, "fma_id": tid, "status": PENDING} for i, tid in enumerate(ids)])
        self.save(job)
        return job

    async def _count(self, job: dict) -> None:
        """Katalogni sanaydi (alohida thread'da) va ekranni har bir necha soniyada yangilaydi."""
        settings = fma.Settings.from_dict(job["settings"])

        def on_progress(rep: "fma.CountReport") -> None:
            job["counted_rows"] = rep.rows

        task = asyncio.create_task(asyncio.to_thread(fma.count_catalog, settings, on_progress))
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=5)
                if not task.done():
                    await self._progress(job)
            rep = task.result()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            job["status"] = PAUSED
            self.note(job, f"sanashda xato: {e}")
            log.exception("FMA katalogini sanab bo'lmadi")
            self.save(job)
            await self._progress(job)
            return
        job["report"] = rep.to_dict()
        job["counted_rows"] = rep.rows
        job["items"] = [{"n": i + 1, "fma_id": tid, "status": PENDING} for i, tid in enumerate(rep.eligible_ids)]
        job["status"] = COLLECTING if job["status"] == COUNTING else job["status"]
        log.info("FMA sanaldi: %s qator, %s yaroqli", rep.rows, rep.eligible)
        self.save(job)
        await self._progress(job)

    def start_vault(self, job: dict) -> bool:
        if job["status"] != COLLECTING or not any(it["status"] == PENDING for it in job["items"]):
            return False
        job["status"] = RUNNING
        self.save(job)
        return self.start(job["id"])

    # ---- boshqaruv ----
    def start(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or self.bot is None or self.is_running(job["id"]):
            return False
        self._tasks[job["id"]] = asyncio.create_task(self._run(job))
        return True

    def pause(self, job: dict) -> None:
        if job["status"] in (RUNNING, COLLECTING):
            job["status"] = PAUSED
            self.save(job)

    def resume(self, job: dict) -> None:
        if job["status"] == PAUSED:
            job["status"] = RUNNING
            self.save(job)
        if job["status"] == RUNNING:
            self.start(job["id"])

    def cancel(self, job: dict) -> None:
        job["status"] = CANCELLED
        self.save(job)

    def finish(self, job: dict) -> int:
        """Fayli kelmagan treklarni o'tkazib yuborib, job'ni yakunlaydi."""
        n = 0
        for it in job["items"]:
            if it["status"] == WAITING:
                it.update(status=SKIPPED, error="fayl yuborilmadi")
                n += 1
        if not any(it["status"] == PENDING for it in job["items"]):
            job["status"] = FINISHED
        self.save(job)
        return n

    def retry_failed(self, job: dict) -> int:
        n = 0
        for it in job["items"]:
            if it["status"] == FAILED and not it.get("permanent"):
                it.update(status=PENDING, attempts=0, error=None)
                n += 1
        if n and job["status"] in (FINISHED, PAUSED):
            job["status"] = RUNNING
        self.save(job)
        return n

    async def resume_all(self) -> list[str]:
        """Server qayta ishga tushganda 'running' job'larni davom ettiradi."""
        for j in self.jobs.values():  # sanash yarim yo'lda qolgan bo'lsa — qaytadan sanaymiz
            if j["status"] == COUNTING and not self.is_running(j["id"]) and self.bot is not None:
                self._tasks[j["id"]] = asyncio.create_task(self._count(j))
        started = [j["id"] for j in self.jobs.values() if j["status"] == RUNNING and self.start(j["id"])]
        if started:
            log.info("Import job'lari davom ettirildi: %s", ", ".join(started))
        return started

    async def wait(self, job_id: str) -> None:
        t = self._tasks.get(job_id)
        if t:
            await t

    # ---- ishlash ----
    async def _progress(self, job: dict) -> None:
        if self.on_progress:
            try:
                await self.on_progress(job)
            except Exception:
                log.exception("Progress xabarini yangilab bo'lmadi")

    async def _run(self, job: dict) -> None:
        provider: MusicProvider | None = None
        try:
            if job["kind"] in ("provider", "csv_provider"):
                provider = self.provider_factory(job["provider"])
            if job["kind"] == "fma":
                await self._fma_open(job)
            while True:
                await self._loop(job, provider)
                # loop tugayotgan paytda yangi fayl kelgan bo'lsa — davom etamiz
                if job["status"] == COLLECTING and any(it["status"] == PENDING for it in job["items"]):
                    job["status"] = RUNNING
                    continue
                break
            self.save(job)
            await self.library.flush(self.bot)  # checkpoint
        except asyncio.CancelledError:
            self.save(job)
            raise
        except Exception as e:  # noqa: BLE001
            job["status"] = PAUSED
            self.note(job, f"kutilmagan xato, job pauza qilindi: {e}")
            log.exception("Import #%s yiqildi", job["id"])
            self.save(job)
        finally:
            if provider:
                await provider.close()
            if job["kind"] == "vault" and job["status"] in (FINISHED, CANCELLED):
                self.cache.drop(job["id"])
            if job["kind"] == "fma":
                self._fma_close(job)
            await self._progress(job)

    async def _loop(self, job: dict, provider: MusicProvider | None) -> None:
        catalog_errors = 0
        while job["status"] == RUNNING:
            pending = [it for it in job["items"] if it["status"] == PENDING]
            if job["kind"] == "provider" and not job["catalog_done"] and len(pending) < self.batch_size:
                try:
                    await self._fetch_catalog_page(job, provider)
                    catalog_errors = 0
                except Exception as e:  # noqa: BLE001
                    catalog_errors += 1
                    self.note(job, f"katalog xatosi: {e}")
                    if catalog_errors >= self.max_attempts:
                        job["status"] = PAUSED
                        self.note(job, "katalog 3 marta xato berdi — job pauza qilindi")
                        break
                    await asyncio.sleep(self.delay * 3)
                continue
            if not pending:
                if any(it["status"] == WAITING for it in job["items"]):
                    job["status"] = COLLECTING  # fayllar kutilmoqda
                else:
                    job["status"] = FINISHED
                break
            for item in pending[: self.batch_size]:
                if job["status"] != RUNNING:
                    break
                await self._process(job, item, provider)
                self.save(job)
            await self._progress(job)

    async def _fetch_catalog_page(self, job: dict, provider: MusicProvider) -> None:
        page = await provider.list_catalog(job.get("cursor"), self.batch_size * 2)
        known = {it["track"].get("external_id") for it in job["items"]}
        today = date.today()
        for t in page.tracks:
            if t.external_id and t.external_id in known:
                continue
            item = {"n": len(job["items"]) + 1, "track": t.to_dict(), "status": PENDING, "attempts": 0}
            problem = t.license_problem(today)
            if problem:
                item.update(status=FAILED, error=problem, permanent=True)
            job["items"].append(item)
        job["cursor"] = page.next_cursor
        job["catalog_done"] = page.next_cursor is None
        self.save(job)

    # ---- FMA import ----
    async def _fma_open(self, job: dict) -> None:
        settings = fma.Settings.from_dict(job["settings"])
        ids = {it["fma_id"] for it in job["items"] if it["status"] == PENDING}
        if settings.manifest:  # tasdiqlangan ro'yxat: faqat status=verified
            cands = await asyncio.to_thread(fma.load_manifest, fma.manifest_path(settings.manifest), ids)
        else:
            cands = await asyncio.to_thread(fma.load_candidates, settings, ids)
        audio = await asyncio.to_thread(fma.open_audio, settings.audio, ids)
        self._fma = getattr(self, "_fma", {})
        self._fma[job["id"]] = (cands, audio, Policy(commercial=settings.commercial))

    def _fma_close(self, job: dict) -> None:
        state = getattr(self, "_fma", {}).pop(job["id"], None)
        if state:
            state[1].close()

    URL_CHECK_HOSTS = {"creativecommons.org", "freemusicarchive.org"}

    async def _url_status(self, url: str) -> int:
        """Sahifa ochiladimi (HTTP holati). Faqat litsenziya va FMA hostlari; xato bo'lsa 0."""
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        if not url or host not in self.URL_CHECK_HOSTS:
            return -1  # tekshirilmadi
        import aiohttp
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
                async with s.head(url, allow_redirects=True) as r:
                    if r.status in (403, 405):
                        async with s.get(url, allow_redirects=True) as g:
                            return g.status
                    return r.status
        except Exception as e:  # noqa: BLE001
            log.warning("URL tekshiruvi xatosi %s: %s", url, e)
            return 0

    async def _roundtrip_sha1(self, msg: Message) -> str | None:
        """Telegram'ga yuklangan faylni qayta olib sha1'ini hisoblaydi (bot API: <= 20 MB)."""
        audio = msg.audio or msg.document
        if audio is None or (audio.file_size or 0) > 20 * 1024 * 1024:
            return None
        buf = await self.bot.download(audio.file_id)
        return hashlib.sha1(buf.read()).hexdigest()

    async def _recheck_existing(self, job: dict, item: dict, c, existing: dict) -> None:
        """Avvalroq import qilingan FMA trekini qayta tekshiradi: Telegram'dagi nusxa sha1, URL'lar,
        atribusiya maydonlari. Mos kelmasa — bazadan olib tashlanadi."""
        lib = self.library
        chk = {"source_sha1": bool(c.sha1), "existing": True}
        settings = fma.Settings.from_dict(job["settings"])
        if settings.mode == "test" or settings.verify_urls:
            chk["license_http"] = await self._url_status(c.license.url)
            chk["source_http"] = await self._url_status(c.source_url)
        tg = None
        if c.sha1 and existing.get("file_id") and (existing.get("file_size") or 0) <= 20 * 1024 * 1024:
            try:
                buf = await self.bot.download(existing["file_id"])
                tg = hashlib.sha1(buf.read()).hexdigest() == c.sha1
            except Exception as e:  # noqa: BLE001
                log.warning("FMA #%s qayta tekshiruvda yuklab bo'lmadi: %s", c.fma_id, e)
        chk["telegram_sha1"] = tg
        chk["caption"] = True  # foydalanuvchiga yuborishda atribusiya bazadan qo'shiladi
        item["chk"] = chk
        if tg is False:
            await lib.remove(self.bot, existing)
            item.update(status=FAILED, error="bazadagi nusxa asl fayldan farq qiladi — olib tashlandi",
                        permanent=True)
            return
        if chk.get("license_http") not in (None, 200, -1):
            self._fail(job, item, f"litsenziya sahifasi ochilmadi (HTTP {chk['license_http']})")
            return
        await lib.update_item(self.bot, existing, c.library_extra() | {
            "sha1": c.sha1, "unmodified": bool(tg), "import_job": existing.get("import_job")})
        item.update(status=SKIPPED, error="bazada bor — qayta tekshirildi", lib_id=existing["id"])

    async def _process_fma(self, job: dict, item: dict) -> None:
        cands, audio, policy = self._fma[job["id"]]
        lib = self.library
        c = cands.get(item["fma_id"])
        if c is None:
            item.update(status=FAILED, error="tasdiqlangan ro'yxatda yo'q (huquqi noaniq) — yuklanmadi",
                        permanent=True)
            return
        problem = policy.check(c.license, will_modify=False)  # siyosat o'zgargan bo'lsa ham qayta tekshiramiz
        if problem:
            item.update(status=FAILED, error=problem, permanent=True)
            return
        existing = lib.find_existing(provider="fma", external_id=str(c.fma_id), artist=c.artist,
                                     title=c.title, duration=c.duration)
        if existing is not None:
            if existing.get("provider") == "fma" and existing.get("external_id") == str(c.fma_id):
                await self._recheck_existing(job, item, c, existing)
            else:
                item.update(status=SKIPPED, error="bazada bor", lib_id=existing["id"])
            return
        if lib.chat_id is None:
            job["status"] = PAUSED
            self.note(job, "LIBRARY_CHANNEL_ID ulanmagan — job pauza qilindi")
            return
        try:
            data = await asyncio.to_thread(audio.read, c.fma_id)
            if c.sha1 and hashlib.sha1(data).hexdigest() != c.sha1:
                item.update(status=FAILED, error="rasmiy sha1 mos emas (fayl buzilgan)", permanent=True)
                return
            if len(data) > fma.MAX_UPLOAD:
                item.update(status=FAILED, error="audio > 49 MB", permanent=True)
                return
            sha = hashlib.sha256(data).hexdigest()
            dup = lib.by_sha.get(sha)
            if dup is not None:
                item.update(status=SKIPPED, error="bazada bor (bir xil fayl)", lib_id=dup["id"])
                return
            track = TrackMeta(title=c.title, artist=c.artist, license_id=c.license.short, duration=c.duration)
            chk = {"source_sha1": bool(c.sha1)}
            settings = fma.Settings.from_dict(job["settings"])
            if settings.mode == "test" or settings.verify_urls:
                chk["license_http"] = await self._url_status(c.license.url)
                chk["source_http"] = await self._url_status(c.source_url)
                if chk["license_http"] not in (200, -1):
                    item["chk"] = chk
                    self._fail(job, item, f"litsenziya sahifasi ochilmadi (HTTP {chk['license_http']})")
                    return
            name = f"{c.artist} - {c.title}.mp3".replace("/", "_")[:120]
            caption = html.escape(c.attribution(), quote=False)[:1000]
            async with self._upload_lock:
                # Fayl o'zgartirilmaydi (CC BY-ND talabi): aynan MP3 baytlari yuboriladi
                msg = await self._upload(track, file_id=None, audio=AudioFile(data, name), caption=caption)
                added = await lib.add(self.bot, msg, extra=c.library_extra() | {
                    "sha256": sha, "sha1": c.sha1, "unmodified": True, "import_job": job["id"]})
                await asyncio.sleep(self.delay)
            chk["caption"] = bool(caption)
            tg_sha1 = await self._roundtrip_sha1(msg)
            chk["telegram_sha1"] = None if tg_sha1 is None else tg_sha1 == hashlib.sha1(data).hexdigest()
            item["chk"] = chk
            if chk["telegram_sha1"] is False:
                # Telegram'dagi nusxa asl fayldan farq qiladi -> tarqatmaymiz
                if added is not None:
                    await lib.remove(self.bot, added)
                try:
                    await self.bot.delete_message(lib.chat_id, msg.message_id)
                except Exception:  # noqa: BLE001
                    pass
                item.update(status=FAILED, error="Telegram'dagi fayl asl nusxadan farq qiladi", permanent=True)
                return
            if added is None:
                item.update(status=SKIPPED, error="bazada bor (bir xil fayl)")
            else:
                item.update(status=DONE, lib_id=added["id"])
                item.pop("error", None)
        except FileNotFoundError:
            item.update(status=FAILED, error="audio fayl yo'q", permanent=True)
        except Exception as e:  # noqa: BLE001
            log.exception("FMA #%s import xatosi", item["fma_id"])
            self._fail(job, item, f"{type(e).__name__}: {e}")

    async def _process(self, job: dict, item: dict, provider: MusicProvider | None) -> None:
        if job["kind"] == "fma":
            await self._process_fma(job, item)
            return
        track = TrackMeta.from_dict(item["track"])
        lib = self.library
        problem = track.license_problem(date.today())
        if problem:
            item.update(status=FAILED, error=problem, permanent=True)
            return
        existing = lib.find_existing(isrc=track.isrc, provider=track.provider, external_id=track.external_id,
                                     artist=track.artist, title=track.title, duration=track.duration)
        if existing is None and item.get("file_uid"):
            existing = lib.by_uid.get(item["file_uid"])
        sha = (item.get("scan") or {}).get("sha256")
        if existing is None and sha:
            existing = lib.by_sha.get(sha)
        if existing is not None:
            item.update(status=SKIPPED, error="bazada bor", lib_id=existing["id"])
            return
        if lib.chat_id is None:
            item["attempts"] += 1
            item["error"] = "kutubxona kanali ulanmagan"
            job["status"] = PAUSED
            self.note(job, "LIBRARY_CHANNEL_ID ulanmagan — job pauza qilindi")
            return
        try:
            audio: AudioFile | None = None
            file_id = item.get("file_id")
            extra = track.library_extra() | {"import_job": job["id"]}
            if job["kind"] == "files":
                if not file_id:
                    item["status"] = WAITING
                    return
            elif job["kind"] == "vault":
                extra |= {"source_file": item["scan"]["member"] or item["scan"]["name"], "sha256": sha}
                if item.get("direct_file_id"):
                    file_id = item["direct_file_id"]  # >20 MB MP3/M4A: Telegram'da bor, file_id bilan
                else:
                    data = await self.cache.read(self.bot, job, item)
                    if sha and hashlib.sha256(data).hexdigest() != sha:
                        raise VaultError("manba fayli o'zgargan (sha256 mos emas)")
                    ext = Path(item["scan"]["name"]).suffix
                    stored = await asyncio.to_thread(self.archive.save, sha, ext, data) if sha else None
                    if stored:
                        extra["archive_path"] = stored
                    out, name = await to_telegram_audio(data, item["scan"]["name"], track)
                    audio = AudioFile(out, name)
            else:
                audio = await provider.fetch_audio(track)
            async with self._upload_lock:
                msg = await self._upload(track, file_id=file_id, audio=audio)
                added = await lib.add(self.bot, msg, extra=extra)
                await asyncio.sleep(self.delay)
            if added is None:
                item.update(status=SKIPPED, error="bazada bor (bir xil fayl)")
            else:
                item.update(status=DONE, lib_id=added["id"], error=None)
        except ProviderError as e:
            self._fail(job, item, str(e), permanent=isinstance(e, SourceNotAllowed))
        except VaultError as e:
            self._fail(job, item, str(e), permanent=True)
        except Exception as e:  # noqa: BLE001
            log.exception("Import #%s, trek %s xatosi", job["id"], item["n"])
            self._fail(job, item, f"{type(e).__name__}: {e}")

    def _fail(self, job: dict, item: dict, error: str, permanent: bool = False) -> None:
        item["attempts"] = item.get("attempts", 0) + 1
        item["error"] = error
        if permanent or item["attempts"] >= self.max_attempts:
            item["status"] = FAILED
            item["permanent"] = permanent
            tr = item.get("track") or {}
            label = f"{tr.get('artist')} — {tr.get('title')}" if tr else f"FMA #{item.get('fma_id')}"
            self.note(job, f"#{item['n']} {label}: {error}")

    async def _upload(self, track: TrackMeta, *, file_id: str | None, audio: AudioFile | None,
                      caption: str | None = None) -> Message:
        media = file_id or BufferedInputFile(audio.data, audio.filename)
        for attempt in range(5):
            try:
                # protect_content ishlatilmaydi: CC litsenziyalari qo'shimcha texnik cheklovlarni taqiqlaydi
                return await self.bot.send_audio(
                    self.library.chat_id, media, title=track.title, performer=track.artist,
                    duration=track.duration or None, disable_notification=True, caption=caption,
                    protect_content=False,
                )
            except TelegramRetryAfter as e:
                log.info("Telegram limiti: %s soniya kutamiz", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except TelegramNetworkError:
                await asyncio.sleep(2 ** attempt)
            if audio is not None:
                media = BufferedInputFile(audio.data, audio.filename)  # oqim qayta o'qilmaydi
        raise RuntimeError("Telegram'ga yuklab bo'lmadi (5 urinish)")
