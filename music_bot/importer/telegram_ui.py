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

import html
import logging
from typing import Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from .csv_import import parse_csv
from .providers import PROVIDERS, ProviderConfig, provider_status
from .runner import (ACTIVE, CANCELLED, COLLECTING, DONE, FAILED, FINISHED, PAUSED, PENDING, RUNNING,
                     SKIPPED, WAITING, ImportManager, counts)

log = logging.getLogger("music_bot.importer")

KIND_NAMES = {"files": "fayllar", "csv_provider": "CSV + provider", "provider": "katalog sinxroni"}
STATUS_NAMES = {COLLECTING: "📎 fayllar kutilmoqda", RUNNING: "▶️ ishlayapti", PAUSED: "⏸ pauza",
                FINISHED: "✅ tugadi", CANCELLED: "🚫 bekor qilindi"}


def esc(t) -> str:
    return html.escape(str(t or ""))


def progress_text(job: dict) -> str:
    c = counts(job)
    total = c["total"] or 1
    processed = c[DONE] + c[SKIPPED] + c[FAILED]
    pct = processed * 100 // total if c["total"] else 0
    bar = "▓" * (pct // 10) + "░" * (10 - pct // 10)
    lines = [
        f"📦 <b>Import #{job['id']}</b> — {KIND_NAMES.get(job['kind'], job['kind'])}"
        + (f" ({esc(job['provider'])})" if job.get("provider") else ""),
        f"Holat: {STATUS_NAMES.get(job['status'], job['status'])}",
        f"{bar} {pct}%  ({processed}/{c['total']})",
        f"✅ Qo'shildi: {c[DONE]}   ⏭ Bazada bor: {c[SKIPPED]}   ❌ Xato: {c[FAILED]}",
        f"⏳ Navbatda: {c[PENDING]}   📎 Fayl kutilmoqda: {c[WAITING]}",
    ]
    if job["kind"] == "provider" and not job.get("catalog_done"):
        lines.append("📚 Katalog hali to'liq o'qilmagan")
    if job["status"] == COLLECTING and c[WAITING]:
        lines.append(f"\nAudio fayllarni yuboring yoki <code>/import_finish {job['id']}</code>")
    elif job["status"] == RUNNING:
        lines.append(f"\n<code>/import_pause {job['id']}</code>")
    elif job["status"] == PAUSED:
        lines.append(f"\n<code>/import_resume {job['id']}</code>")
    if c[FAILED]:
        lines.append(f"Xatolar: <code>/import_failed {job['id']}</code>")
    return "\n".join(lines)


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
            await manager.bot.edit_message_text(progress_text(job), chat_id=job["progress_chat"],
                                                message_id=job["progress_msg"])
        except Exception as e:  # "message is not modified" va h.k.
            if "not modified" not in str(e):
                log.warning("Progress xabari yangilanmadi: %s", e)

    manager.on_progress = send_progress

    async def new_progress_message(message: Message, job: dict) -> None:
        msg = await message.answer(progress_text(job))
        job["progress_chat"], job["progress_msg"] = msg.chat.id, msg.message_id
        manager.save(job)

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

    return router
