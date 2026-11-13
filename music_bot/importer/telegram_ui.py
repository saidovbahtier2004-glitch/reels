"""Import uchun admin buyruqlari (Telegram).

  CSV hujjat yuborish               → yangi import (fayllar rejimi)
  CSV + izoh "provider <nom>"       → CSV treklari audiosi distributor API'sidan olinadi
  audio/MP3 yuborish                → ochiq import'dagi CSV qatoriga moslanadi va kanalga yuklanadi
  /import                           → yordam, providerlar va import'lar ro'yxati
  /import_status [ID]               → progress
  /import_sync <provider>           → distributor katalogini to'liq import qilish
  /import_pause ID | /import_resume ID | /import_cancel ID
  /import_finish ID                 → fayli kelmaganlarni o'tkazib yuborib yakunlash
  /import_failed ID | /import_retry ID
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .csv_import import parse_csv
from .vault import MAX_UPLOAD_BYTES, VaultError, safe_folder, scan_folder, scan_zip
from .providers import PROVIDERS, ProviderConfig, provider_status
from .runner import (ACTIVE, CANCELLED, COLLECTING, DONE, FAILED, FINISHED, PAUSED, PENDING, RUNNING,
                     SKIPPED, WAITING, ImportManager, counts)

log = logging.getLogger("music_bot.importer")

KIND_NAMES = {"files": "fayllar", "csv_provider": "CSV + provider", "provider": "katalog sinxroni",
              "vault": "DistroKid Vault"}
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024  # bot API orqali yuklab olish limiti
STATUS_NAMES = {COLLECTING: "📎 fayllar kutilmoqda", RUNNING: "▶️ ishlayapti", PAUSED: "⏸ pauza",
                FINISHED: "✅ tugadi", CANCELLED: "🚫 bekor qilindi"}


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def progress_text(job: dict, delay: float = 3.5) -> str:
    c = counts(job)
    vault = job["kind"] == "vault"
    total = c["total"] or 1
    processed = c[DONE] + c[SKIPPED] + c[FAILED]
    pct = processed * 100 // total if c["total"] else 0
    bar = "▓" * (pct // 10) + "░" * (10 - pct // 10)
    waiting_label = "🏷 Metadata yo'q" if vault else "📎 Fayl kutilmoqda"
    lines = [
        f"📦 <b>Import #{job['id']}</b> — {KIND_NAMES.get(job['kind'], job['kind'])}"
        + (f" ({esc(job['provider'])})" if job.get("provider") and not vault else ""),
        f"Holat: {STATUS_NAMES.get(job['status'], job['status'])}",
        f"{bar} {pct}%  ({processed}/{c['total']})",
        f"✅ Qo'shildi: {c[DONE]}   ⏭ Bazada bor: {c[SKIPPED]}   ❌ Xato: {c[FAILED]}",
        f"⏳ Navbatda: {c[PENDING]}   {waiting_label}: {c[WAITING]}",
    ]
    if vault:
        srcs = job.get("sources", [])
        kinds = {"tg_zip": 0, "tg_file": 0, "folder": 0}
        for src in srcs:
            kinds[src["type"]] = kinds.get(src["type"], 0) + 1
        by = {"csv": 0, "tags": 0, "filename": 0}
        for it in job["items"]:
            m = it.get("match") or ""
            if m:
                by["csv" if m.startswith("csv") else m] = by.get("csv" if m.startswith("csv") else m, 0) + 1
        lines.append(f"🗂 Manbalar: ZIP {kinds['tg_zip']} · fayl {kinds['tg_file']} · papka {kinds['folder']}"
                     f"   📄 CSV qatorlari: {len(job.get('csv', []))}")
        lines.append(f"🔗 Metadata manbasi: CSV {by['csv']} · teglar {by['tags']} · fayl nomi {by['filename']}")
        if job.get("default_artist"):
            lines.append(f"👤 Standart ijrochi: {esc(job['default_artist'])}")
    if c[PENDING] and job["status"] == RUNNING:
        lines.append(f"🕒 Taxminan {max(1, round(c[PENDING] * delay / 60))} daqiqa qoldi")
    if job["kind"] == "provider" and not job.get("catalog_done"):
        lines.append("📚 Katalog hali to'liq o'qilmagan")
    if vault and job["status"] == COLLECTING:
        lines.append("\nZIP, audio fayl yoki CSV yuboring, keyin ▶️ <b>Importni boshlash</b>.")
    elif job["status"] == COLLECTING and c[WAITING]:
        lines.append(f"\nAudio fayllarni yuboring yoki <code>/import_finish {job['id']}</code>")
    if job.get("log") and job["status"] in (PAUSED,):
        lines.append(f"\n⚠️ {esc(job['log'][-1])}")
    return "\n".join(lines)


def scan_report(name: str, files: list, skipped: list[str], res: dict) -> str:
    lines = [f"🗂 <b>{esc(name)}</b>",
             f"🎵 Audio topildi: {len(files)}   ➕ Qo'shildi: {res['added'] - res['in_library']}",
             f"⏭ Bazada bor: {res['in_library']}   ♻️ Takroriy: {res['dup_in_job']}",
             f"🚫 Audio bo'lmagan / o'tkazilgan: {len(skipped)}"]
    if skipped:
        lines += [f"  · {esc(x)}" for x in skipped[:5]]
        if len(skipped) > 5:
            lines.append(f"  · … va yana {len(skipped) - 5} ta")
    return "\n".join(lines)


def screen_kb(job: dict) -> InlineKeyboardMarkup:
    j = job["id"]

    def b(text, action):
        return InlineKeyboardButton(text=text, callback_data=f"imp:{action}:{j}")
    c = counts(job)
    rows = []
    st = job["status"]
    if st == COLLECTING and job["kind"] == "vault":
        rows.append([b("▶️ Importni boshlash", "start")])
    if st == RUNNING:
        rows.append([b("⏸ Pauza", "pause"), b("🔄 Yangilash", "refresh")])
    elif st == PAUSED:
        rows.append([b("▶️ Davom ettirish", "resume"), b("🔄 Yangilash", "refresh")])
    elif st == COLLECTING:
        rows.append([b("🔄 Yangilash", "refresh")])
    extra = []
    if c[FAILED]:
        extra.append(b(f"📋 Xatolar ({c[FAILED]})", "failed"))
    if c[WAITING]:
        extra.append(b(f"🏷 Mos kelmaganlar ({c[WAITING]})" if job["kind"] == "vault" else
                       f"📎 Kutilayotganlar ({c[WAITING]})", "unmatched"))
    if extra:
        rows.append(extra)
    if st in ACTIVE:
        rows.append([b("⏭ Yakunlash", "finish"), b("❌ Bekor qilish", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


HELP = (
    "📥 <b>Ommaviy import</b> (faqat litsenziyali musiqa)\n\n"
    "<b>1. CSV + fayllar</b>\n"
    "CSV jadvalni hujjat qilib yuboring. Majburiy ustunlar: <code>title, artist, license_id</code>.\n"
    "Ixtiyoriy: <code>file, isrc, album, duration, license_expires, external_id</code>.\n"
    "Keyin audio fayllarni yuboring. Ular <code>file</code> ustuni yoki «Ijrochi - Nomi» bo'yicha moslanadi.\n\n"
    "<b>2. CSV + distributor</b>\n"
    "CSV'ni <code>provider distributor</code> izohi bilan yuboring. Audio distributor API'sidan olinadi.\n\n"
    "<b>3. Distributor katalogi</b>\n"
    "<code>/import_sync distributor</code>\n\n"
    "<b>4. DistroKid Vault backup</b> (o'zingizning original yozuvlaringiz)\n"
    "<code>/vault</code>: sessiya ochiladi. Keyin ZIP (har biri ≤20 MB), audio fayllar va ixtiyoriy CSV yuboring.\n"
    "<code>/vault_artist Ism</code>: standart ijrochi, <code>/vault_folder yo'l</code>: serverdagi papka.\n\n"
    "<code>/imports</code>: barcha import'lar ekrani\n\n"
    "<b>Boshqaruv:</b> <code>/import_status</code>, <code>/import_pause ID</code>, <code>/import_resume ID</code>, "
    "<code>/import_cancel ID</code>, <code>/import_finish ID</code>, <code>/import_failed ID</code>, "
    "<code>/import_retry ID</code>"
)


def build_router(manager: ImportManager, is_admin: Callable[[int | None], bool]) -> Router:
    router = Router(name="importer")
    private = F.chat.type == "private"

    def admin_msg(m: Message) -> bool:
        return is_admin(m.from_user.id if m.from_user else None)

    async def send_progress(job: dict) -> None:
        if not job.get("progress_chat") or manager.bot is None:
            return
        try:
            await manager.bot.edit_message_text(progress_text(job, manager.delay), chat_id=job["progress_chat"],
                                                message_id=job["progress_msg"], reply_markup=screen_kb(job))
        except Exception as e:  # "message is not modified" va h.k.
            if "not modified" not in str(e):
                log.warning("Progress xabari yangilanmadi: %s", e)

    manager.on_progress = send_progress

    async def new_progress_message(message: Message, job: dict) -> None:
        msg = await message.answer(progress_text(job, manager.delay), reply_markup=screen_kb(job))
        job["progress_chat"], job["progress_msg"] = msg.chat.id, msg.message_id
        manager.save(job)

    # ---- DistroKid Vault ----
    def vault_open(m: Message) -> bool:
        return admin_msg(m) and manager.vault_job() is not None

    @router.message(Command("vault"), private)
    async def cmd_vault(message: Message) -> None:
        if not await need_admin(message):
            return
        job = manager.vault_job()
        if job:
            await new_progress_message(message, job)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlayman", callback_data="imp:attest:0")]])
        await message.answer(
            "🎙 <b>DistroKid Vault importi</b>\n\n"
            "DistroKid ommaviy katalog API'sini bermaydi, shuning uchun bot DistroKid saytiga ulanmaydi. "
            "Siz Vault'dan yuklab olgan backup'larni (ZIP yoki audio fayllar) shu yerga yuborasiz.\n\n"
            "Davom etish uchun tasdiqlang: <b>yuboriladigan fayllar sizga tegishli original yozuvlar va "
            "ularni shu botda tarqatish huquqingiz bor.</b>", reply_markup=kb)

    @router.message(Command("vault_artist"), private)
    async def cmd_vault_artist(message: Message) -> None:
        if not await need_admin(message):
            return
        job = manager.vault_job()
        name = (message.text or "").partition(" ")[2].strip()
        if not job or not name:
            await message.answer("Foydalanish: ochiq /vault sessiyasida <code>/vault_artist Ijrochi nomi</code>")
            return
        job["default_artist"] = name[:100]
        manager.rematch(job)
        await new_progress_message(message, job)

    @router.message(Command("vault_folder"), private)
    async def cmd_vault_folder(message: Message) -> None:
        if not await need_admin(message):
            return
        job = manager.vault_job()
        rel = (message.text or "").partition(" ")[2].strip()
        if not job or not rel:
            await message.answer("Foydalanish: ochiq /vault sessiyasida <code>/vault_folder papka/yo'li</code> "
                                 "(IMPORT_ROOT ichida)")
            return
        try:
            folder = safe_folder(rel)
            files, skipped = await asyncio.to_thread(scan_folder, folder)
        except VaultError as e:
            await message.answer(f"❌ {esc(e)}")
            return
        res = manager.add_vault_source(job, {"type": "folder", "name": rel}, files)
        await message.answer(scan_report(rel, files, skipped, res))
        await new_progress_message(message, job)

    @router.message(private, F.document, F.document.file_name.lower().endswith(".zip"), vault_open)
    async def on_vault_zip(message: Message) -> None:
        manager.bind(message.bot)
        job = manager.vault_job()
        doc = message.document
        if (doc.file_size or 0) > TG_DOWNLOAD_LIMIT:
            await message.reply("❌ ZIP 20 MB dan katta. Telegram bot faqat 20 MB gacha faylni yuklab oladi.\n"
                                "Backup'ni kichikroq ZIP'larga bo'ling (masalan, har bir albom alohida) "
                                "yoki audiolarni alohida fayl qilib yuboring.")
            return
        status = await message.reply("🔎 ZIP tekshirilmoqda...")
        idx = len(job["sources"])
        src = {"type": "tg_zip", "file_id": doc.file_id, "file_uid": doc.file_unique_id, "name": doc.file_name}
        if any(s_.get("file_uid") == doc.file_unique_id for s_ in job["sources"]):
            await status.edit_text("⏭ Bu ZIP allaqachon qo'shilgan.")
            return
        try:
            job["sources"].append(src)  # vaqtincha — kesh yo'li uchun
            path = await manager.cache.ensure(message.bot, job, idx)
            job["sources"].pop()
            files, skipped = await asyncio.to_thread(scan_zip, path)
        except VaultError as e:
            if job["sources"] and job["sources"][-1] is src:
                job["sources"].pop()
            await status.edit_text(f"❌ {esc(e)}")
            return
        except Exception:
            if job["sources"] and job["sources"][-1] is src:
                job["sources"].pop()
            log.exception("ZIP o'qishda xato")
            await status.edit_text("❌ ZIP'ni o'qib bo'lmadi.")
            return
        res = manager.add_vault_source(job, src, files)
        await status.edit_text(scan_report(doc.file_name, files, skipped, res))
        await new_progress_message(message, job)

    @router.message(private, F.document, F.document.file_name.lower().endswith(".csv"), vault_open)
    async def on_vault_csv(message: Message) -> None:
        manager.bind(message.bot)
        job = manager.vault_job()
        try:
            buf = await message.bot.download(message.document.file_id)
            result = parse_csv(buf.read(), provider="distrokid-vault", require_license=False)
        except Exception:
            log.exception("Vault CSV o'qishda xato")
            await message.answer("❌ CSV'ni o'qib bo'lmadi. UTF-8 formatida saqlang.")
            return
        manager.apply_csv(job, result.tracks)
        lines = [f"📄 CSV: {len(result.tracks)} ta qator qabul qilindi, {len(result.errors)} ta rad etildi."]
        lines += [f"• {esc(e)}" for e in result.errors[:10]]
        await message.answer("\n".join(lines))
        await new_progress_message(message, job)

    @router.message(private, F.audio | (F.document & F.document.mime_type.startswith("audio/")), vault_open)
    async def on_vault_audio(message: Message) -> None:
        manager.bind(message.bot)
        job = manager.vault_job()
        a = message.audio or message.document
        name = a.file_name or f"{getattr(a, 'performer', '') or ''} - {getattr(a, 'title', '') or 'audio'}.mp3"
        src = {"type": "tg_file", "file_id": a.file_id, "file_uid": a.file_unique_id, "name": name}
        if any(s_.get("file_uid") == a.file_unique_id for s_ in job["sources"]):
            await message.reply("⏭ Bu fayl allaqachon qo'shilgan.")
            return
        if (a.file_size or 0) > TG_DOWNLOAD_LIMIT:
            # yuklab ololmaymiz: faqat Telegram o'zi ijro etadigan va ≤49 MB fayllarni file_id bilan olamiz
            if not name.lower().endswith((".mp3", ".m4a")) or (a.file_size or 0) > MAX_UPLOAD_BYTES:
                await message.reply("❌ Fayl 20 MB dan katta va MP3/M4A emas. Bot uni yuklab, MP3 ga o'gira "
                                    "olmaydi. 20 MB dan kichik ZIP yoki MP3 qilib yuboring.")
                return
            from .vault import ScannedFile, parse_filename
            tags = {k: v for k, v in {"title": getattr(a, "title", None), "artist": getattr(a, "performer", None),
                                      "duration": getattr(a, "duration", None)}.items() if v}
            files = [ScannedFile(name, "", a.file_size or 0, "", tags, parse_filename(name))]
            src["direct"] = True
        else:
            try:
                job["sources"].append(src)
                path = await manager.cache.ensure(message.bot, job, len(job["sources"]) - 1)
                job["sources"].pop()
                import hashlib
                from .vault import ScannedFile, parse_filename, read_tags
                data = await asyncio.to_thread(path.read_bytes)
                tags = read_tags(data, name)
                for k, v in (("title", getattr(a, "title", None)), ("artist", getattr(a, "performer", None))):
                    if v and not tags.get(k):
                        tags[k] = v
                files = [ScannedFile(name, "", len(data), hashlib.sha256(data).hexdigest(), tags,
                                     parse_filename(name))]
            except Exception:
                if job["sources"] and job["sources"][-1] is src:
                    job["sources"].pop()
                log.exception("Vault audio o'qishda xato")
                await message.reply("❌ Faylni o'qib bo'lmadi.")
                return
        res = manager.add_vault_source(job, src, files)
        it = job["items"][-1] if res["added"] else None
        if res["dup_in_job"]:
            await message.reply("⏭ Bu audio sessiyada allaqachon bor.")
        elif it and it["status"] == SKIPPED:
            await message.reply(f"⏭ Bazada bor: #{it.get('lib_id')}")
        elif it and it["status"] == WAITING:
            await message.reply(f"🏷 Qo'shildi, lekin metadata yetarli emas: {esc(it.get('error'))}")
        elif it:
            tr = it["track"]
            await message.reply(f"📥 {esc(tr.get('artist'))} — {esc(tr.get('title'))} qo'shildi")

    # ---- CSV ----
    @router.message(private, F.document, F.document.file_name.lower().endswith(".csv"), admin_msg)
    async def on_csv(message: Message) -> None:
        manager.bind(message.bot)
        caption = (message.caption or "").strip().split()
        provider = ""
        if len(caption) >= 2 and caption[0].lower() == "provider":
            provider = caption[1].lower()
            if provider not in PROVIDERS:
                await message.answer(f"❌ Noma'lum provider: {esc(provider)}. Mavjud: {', '.join(PROVIDERS)}")
                return
            if not ProviderConfig.from_env(provider).configured:
                await message.answer(f"❌ <b>{esc(provider)}</b> sozlanmagan. Render → Environment'ga "
                                     f"<code>PROVIDER_{provider.upper()}_BASE_URL</code> va "
                                     f"<code>PROVIDER_{provider.upper()}_API_KEY</code> qo'shing.")
                return
        if (message.document.file_size or 0) > 20 * 1024 * 1024:
            await message.answer("❌ CSV 20 MB dan katta. Bir nechta faylga bo'ling.")
            return
        try:
            buf = await message.bot.download(message.document.file_id)
            result = parse_csv(buf.read(), provider=provider)
        except Exception:
            log.exception("CSV o'qishda xato")
            await message.answer("❌ CSV'ni o'qib bo'lmadi. UTF-8 formatida saqlang.")
            return
        lines = [f"📄 <b>{esc(message.document.file_name)}</b>",
                 f"✔️ Yaroqli treklar: <b>{len(result.tracks)}</b>",
                 f"⚠️ Rad etilgan qatorlar: <b>{len(result.errors)}</b>"]
        if result.errors:
            lines += ["", *[f"• {esc(e)}" for e in result.errors[:15]]]
            if len(result.errors) > 15:
                lines.append(f"… va yana {len(result.errors) - 15} ta")
        await message.answer("\n".join(lines))
        if not result.tracks:
            return
        kind = "csv_provider" if provider else "files"
        job = manager.create_job(kind, result.tracks, provider=provider, owner=message.from_user.id)
        await new_progress_message(message, job)
        if kind == "csv_provider":
            manager.start(job["id"])

    # ---- litsenziyali audio fayllar ----
    def has_files_job(m: Message) -> bool:
        return admin_msg(m) and bool(manager.files_jobs())

    audio_filter = F.audio | (F.document & F.document.mime_type.startswith("audio/"))

    @router.message(private, audio_filter, has_files_job)
    async def on_import_audio(message: Message) -> None:
        manager.bind(message.bot)
        a = message.audio or message.document
        found = manager.match_file(a.file_name or "", getattr(a, "title", "") or "",
                                   getattr(a, "performer", "") or "")
        if not found:
            await message.reply("⚠️ Bu fayl ochiq import'dagi CSV qatorlariga mos kelmadi. Litsenziyasi "
                                "noma'lum bo'lgani uchun qabul qilinmadi.\nFayl nomini CSV'dagi "
                                "<code>file</code> ustuniga yoki «Ijrochi - Nomi» ko'rinishiga moslang.")
            return
        job, item = found
        if (a.file_size or 0) > 50 * 1024 * 1024:
            item.update(status=FAILED, error="fayl 50 MB dan katta")
            manager.save(job)
            await message.reply("❌ Fayl 50 MB dan katta.")
            return
        manager.attach_file(job, item, a.file_id, a.file_unique_id)
        tr = item["track"]
        await message.reply(f"📥 #{job['id']}/{item['n']} {esc(tr.get('artist'))} — {esc(tr.get('title'))} "
                            f"navbatga qo'shildi")

    # ---- buyruqlar ----
    async def need_admin(message: Message) -> bool:
        if not admin_msg(message):
            await message.answer("⛔️ Bu buyruq faqat adminlar uchun.")
            return False
        manager.bind(message.bot)
        return True

    def job_arg(message: Message) -> dict | None:
        parts = (message.text or "").split()
        return manager.get(parts[1]) if len(parts) > 1 else None

    @router.message(Command("import"), private)
    async def cmd_import(message: Message) -> None:
        if not await need_admin(message):
            return
        provs = "\n".join(f"• <code>{n}</code> — {'✅ sozlangan' if ok else '⚙️ sozlanmagan'}"
                          for n, ok in provider_status())
        active = [j for j in manager.jobs.values() if j["status"] in ACTIVE]
        jobs = "\n".join(f"• #{j['id']} {KIND_NAMES.get(j['kind'])} — {STATUS_NAMES.get(j['status'])}"
                         for j in active) or "yo'q"
        await message.answer(f"{HELP}\n\n<b>Providerlar:</b>\n{provs}\n\n<b>Ochiq import'lar:</b>\n{jobs}")

    @router.message(Command("import_status"), private)
    async def cmd_status(message: Message) -> None:
        if not await need_admin(message):
            return
        job = job_arg(message)
        if job:
            await message.answer(progress_text(job))
            return
        recent = sorted(manager.jobs.values(), key=lambda j: int(j["id"]))[-5:]
        if not recent:
            await message.answer("Hali import bo'lmagan. Yordam: /import")
            return
        for j in recent:
            await message.answer(progress_text(j))

    @router.message(Command("import_sync"), private)
    async def cmd_sync(message: Message) -> None:
        if not await need_admin(message):
            return
        parts = (message.text or "").split()
        name = parts[1].lower() if len(parts) > 1 else ""
        if name not in PROVIDERS:
            await message.answer(f"Foydalanish: <code>/import_sync nom</code>. Mavjud: {', '.join(PROVIDERS)}")
            return
        if not ProviderConfig.from_env(name).configured:
            await message.answer(f"❌ <b>{esc(name)}</b> sozlanmagan: <code>PROVIDER_{name.upper()}_BASE_URL</code> "
                                 f"va <code>PROVIDER_{name.upper()}_API_KEY</code> kerak.")
            return
        if any(j["kind"] == "provider" and j["provider"] == name and j["status"] in ACTIVE
               for j in manager.jobs.values()):
            await message.answer("Bu provider uchun import allaqachon ochiq: /import_status")
            return
        job = manager.create_job("provider", [], provider=name, owner=message.from_user.id)
        await new_progress_message(message, job)
        manager.start(job["id"])

    async def control(message: Message, action: str) -> None:
        if not await need_admin(message):
            return
        job = job_arg(message)
        if not job:
            await message.answer(f"Foydalanish: <code>/import_{action} ID</code> (ID: /import_status)")
            return
        if action == "pause":
            manager.pause(job)
        elif action == "resume":
            manager.resume(job)
        elif action == "cancel":
            manager.cancel(job)
        elif action == "finish":
            n = manager.finish(job)
            await message.answer(f"⏭ {n} ta fayli kelmagan trek o'tkazib yuborildi.")
        elif action == "retry":
            n = manager.retry_failed(job)
            await message.answer(f"🔁 {n} ta trek qayta navbatga qo'yildi.")
            manager.start(job["id"])
        await message.answer(progress_text(job))

    for action in ("pause", "resume", "cancel", "finish", "retry"):
        async def handler(message: Message, _a: str = action) -> None:
            await control(message, _a)
        router.message.register(handler, Command(f"import_{action}"), private)

    @router.message(Command("import_failed"), private)
    async def cmd_failed(message: Message) -> None:
        if not await need_admin(message):
            return
        job = job_arg(message)
        if not job:
            await message.answer("Foydalanish: <code>/import_failed ID</code>")
            return
        failed = [it for it in job["items"] if it["status"] == FAILED]
        if not failed:
            await message.answer("Xato yo'q ✅")
            return
        lines = [f"❌ Import #{job['id']} xatolari: {len(failed)}\n"]
        lines += [f"#{it['n']} {esc(it['track'].get('artist'))} — {esc(it['track'].get('title'))}: "
                  f"<i>{esc(it.get('error'))}</i>" for it in failed[:30]]
        lines.append(f"\nQayta urinish: <code>/import_retry {job['id']}</code>")
        await message.answer("\n".join(lines))

    @router.message(Command("imports"), private)
    async def cmd_imports(message: Message) -> None:
        if not await need_admin(message):
            return
        jobs = sorted(manager.jobs.values(), key=lambda j: int(j["id"]))[-10:]
        if not jobs:
            await message.answer("Hali import yo'q. Boshlash: /vault yoki /import")
            return
        rows = []
        for j in reversed(jobs):
            c = counts(j)
            rows.append([InlineKeyboardButton(
                text=f"#{j['id']} {KIND_NAMES.get(j['kind'])} · {STATUS_NAMES.get(j['status'])} · "
                     f"{c[DONE]}/{c['total']}", callback_data=f"imp:open:{j['id']}")])
        await message.answer("📦 <b>Import'lar</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data.startswith("imp:"))
    async def on_screen(cb: CallbackQuery) -> None:
        if not is_admin(cb.from_user.id):
            await cb.answer("⛔️ Faqat adminlar uchun.", show_alert=True)
            return
        manager.bind(cb.bot)
        _, action, job_id = cb.data.split(":", 2)
        if action == "attest":
            job = manager.vault_job() or manager.create_vault_job(cb.from_user.id)
            await cb.answer("Tasdiqlandi")
            await new_progress_message(cb.message, job)
            return
        job = manager.get(job_id)
        if job is None:
            await cb.answer("Import topilmadi", show_alert=True)
            return
        note = ""
        if action == "start":
            note = "Boshlandi" if manager.start_vault(job) else "Navbatda yuklanadigan trek yo'q"
        elif action == "pause":
            manager.pause(job)
            note = "Pauza"
        elif action == "resume":
            manager.resume(job)
            note = "Davom etmoqda"
        elif action == "finish":
            note = f"{manager.finish(job)} ta o'tkazib yuborildi"
        elif action == "cancel":
            manager.cancel(job)
            note = "Bekor qilindi"
        elif action in ("failed", "unmatched"):
            want = FAILED if action == "failed" else WAITING
            items = [it for it in job["items"] if it["status"] == want]
            lines = [f"{'❌ Xatolar' if want == FAILED else '🏷 Mos kelmaganlar'} — import #{job['id']}: "
                     f"{len(items)}\n"]
            for it in items[:30]:
                name = it.get("scan", {}).get("name") or f"{it['track'].get('artist')} — {it['track'].get('title')}"
                lines.append(f"#{it['n']} {esc(name)}: <i>{esc(it.get('error'))}</i>")
            if want == WAITING and job["kind"] == "vault":
                lines.append("\nCSV yuboring yoki <code>/vault_artist Ism</code> bilan standart ijrochini bering.")
            await cb.answer()
            await cb.message.answer("\n".join(lines))
            return
        await cb.answer(note)
        if action == "open":
            await new_progress_message(cb.message, job)
            return
        job["progress_chat"], job["progress_msg"] = cb.message.chat.id, cb.message.message_id
        await send_progress(job)

    return router
