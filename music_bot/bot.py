"""Musiqa topuvchi Telegram bot.

Nima qiladi:
  * Qo'shiq nomi yoki ijrochi yozilsa — ro'yxat chiqaradi, tanlanganini yuboradi.
  * Video, reels, video-xabar (dumaloq), ovozli xabar yoki audio yuborilsa —
    ichidagi qo'shiqni aniqlaydi (Shazam) va uni yuboradi.

Audio sifatida Deezer'ning rasmiy 30 soniyalik preview'lari yuboriladi,
to'liq versiya uchun Spotify / YouTube / Apple Music / Deezer havolalari beriladi.

O'z kutubxonangiz: LIBRARY_CHANNEL_ID ko'rsatilgan maxfiy kanalga tashlangan
audio fayllar qidiruvda birinchi chiqadi va TO'LIQ yuboriladi. Kanalga faqat
tarqatishga huquqingiz bor qo'shiqlarni qo'ying.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import tempfile
import urllib.parse
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaDocument,
    Message,
)
from shazamio import Shazam

log = logging.getLogger("music_bot")

DEEZER_API = "https://api.deezer.com"
PAGE_SIZE = 10
MAX_TG_DOWNLOAD = 20 * 1024 * 1024  # Bot API fayl yuklab olish limiti
SAMPLE_SECONDS = 20
SAMPLE_OFFSETS = (0, 15, 35, 60)  # musiqa videoning o'rtasida boshlansa ham topish uchun

router = Router()
shazam = Shazam()
http: aiohttp.ClientSession | None = None

# chat_id -> oxirgi qidiruv so'rovi (sahifalash tugmalari uchun)
last_query: dict[int, str] = {}


# --------------------------------------------------------------------------- #
# O'z kutubxonangiz (maxfiy Telegram kanal)
# --------------------------------------------------------------------------- #
INDEX_NAME = "library.json"


def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[ʻʼ‘’`´']", "", text)
    return re.sub(r"[^\w]+", " ", text).strip()


class Library:
    """Kanaldagi audiolar ro'yxati. Indeks kanalda pin qilingan library.json
    faylida saqlanadi, shuning uchun server qayta ishga tushsa ham yo'qolmaydi."""

    def __init__(self) -> None:
        self.channel = os.getenv("LIBRARY_CHANNEL_ID", "").strip()
        self.chat_id: int | None = None
        self.index_msg_id: int | None = None
        self.items: list[dict] = []
        self.lock = asyncio.Lock()

    async def load(self, bot: Bot) -> None:
        if not self.channel:
            log.info("LIBRARY_CHANNEL_ID berilmagan — kutubxona o'chiq")
            return
        try:
            ref: int | str = int(self.channel) if self.channel.lstrip("-").isdigit() else self.channel
            chat = await bot.get_chat(ref)
            self.chat_id = chat.id
            pm = chat.pinned_message
            if pm and pm.document and pm.document.file_name == INDEX_NAME:
                buf = await bot.download(pm.document.file_id)
                self.items = json.loads(buf.read().decode()).get("items", [])
                self.index_msg_id = pm.message_id
            log.info("Kutubxona yuklandi: %s ta qo'shiq", len(self.active()))
        except Exception:
            log.exception("Kutubxona kanalini o'qib bo'lmadi (bot kanalda admin ekanini tekshiring)")

    def active(self) -> list[dict]:
        return [it for it in self.items if not it.get("deleted")]

    def search(self, query: str) -> list[tuple[int, dict]]:
        words = norm(query).split()
        if not words:
            return []
        return [(i, it) for i, it in enumerate(self.items)
                if not it.get("deleted") and all(w in it["key"] for w in words)]

    async def save(self, bot: Bot) -> None:
        data = json.dumps({"items": self.items}, ensure_ascii=False).encode()
        doc = BufferedInputFile(data, INDEX_NAME)
        if self.index_msg_id:
            try:
                await bot.edit_message_media(
                    chat_id=self.chat_id, message_id=self.index_msg_id,
                    media=InputMediaDocument(media=doc, caption="📚 Kutubxona indeksi — o'chirmang"),
                )
                return
            except Exception:
                log.exception("Indeksni yangilab bo'lmadi, yangisini yaratamiz")
        msg = await bot.send_document(
            self.chat_id, doc, caption="📚 Kutubxona indeksi — o'chirmang", disable_notification=True,
        )
        self.index_msg_id = msg.message_id
        await bot.pin_chat_message(self.chat_id, msg.message_id, disable_notification=True)

    async def add(self, bot: Bot, message: Message) -> dict | None:
        audio = message.audio or message.document
        title = getattr(audio, "title", None) or ""
        performer = getattr(audio, "performer", None) or ""
        if not title:
            stem = Path(audio.file_name or "Nomsiz").stem
            if " - " in stem and not performer:
                performer, title = (s.strip() for s in stem.split(" - ", 1))
            else:
                title = stem
        async with self.lock:
            if any(it["uid"] == audio.file_unique_id and not it.get("deleted") for it in self.items):
                return None
            item = {
                "file_id": audio.file_id,
                "uid": audio.file_unique_id,
                "title": title,
                "performer": performer,
                "duration": getattr(audio, "duration", None) or 0,
                "msg": message.message_id,
                "key": norm(f"{performer} {title} {audio.file_name or ''}"),
            }
            self.items.append(item)
            await self.save(bot)
            return item

    async def remove_by_msg(self, bot: Bot, msg_id: int) -> dict | None:
        async with self.lock:
            for it in self.items:
                if it.get("msg") == msg_id and not it.get("deleted"):
                    it["deleted"] = True
                    await self.save(bot)
                    return it
        return None


library = Library()


# --------------------------------------------------------------------------- #
# Yordamchi funksiyalar
# --------------------------------------------------------------------------- #
def esc(text: str | None) -> str:
    return html.escape(text or "")


def fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def links_keyboard(artist: str, title: str, deezer_link: str | None = None,
                   shazam_link: str | None = None) -> InlineKeyboardMarkup:
    q = urllib.parse.quote(f"{artist} {title}")
    rows = [
        [
            InlineKeyboardButton(text="🎧 Spotify", url=f"https://open.spotify.com/search/{q}"),
            InlineKeyboardButton(text="▶️ YouTube", url=f"https://www.youtube.com/results?search_query={q}"),
        ],
        [
            InlineKeyboardButton(text="🍎 Apple Music", url=f"https://music.apple.com/search?term={q}"),
            InlineKeyboardButton(text="🟣 Deezer", url=deezer_link or f"https://www.deezer.com/search/{q}"),
        ],
    ]
    if shazam_link:
        rows.append([InlineKeyboardButton(text="🔵 Shazam", url=shazam_link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def deezer_get(path: str, **params) -> dict:
    assert http is not None
    async with http.get(f"{DEEZER_API}{path}", params=params) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def deezer_search(query: str, index: int = 0, limit: int = PAGE_SIZE) -> tuple[list[dict], int]:
    data = await deezer_get("/search", q=query, index=index, limit=limit)
    return data.get("data", []), int(data.get("total", 0))


async def send_track(message: Message, track: dict, shazam_link: str | None = None) -> None:
    """Deezer track obyektini audio (preview) + havolalar bilan yuboradi."""
    title = track.get("title") or ""
    artist = (track.get("artist") or {}).get("name") or ""
    album = (track.get("album") or {}).get("title") or ""
    preview = track.get("preview")
    kb = links_keyboard(artist, title, track.get("link"), shazam_link)

    caption = f"🎵 <b>{esc(artist)} — {esc(title)}</b>"
    if album:
        caption += f"\n💿 {esc(album)}"
    if track.get("duration"):
        caption += f"\n⏱ {fmt_duration(track['duration'])}"
    caption += "\n\n<i>30 soniyalik parcha. To'liq versiya — pastdagi tugmalarda.</i>"

    if preview:
        try:
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            assert http is not None
            async with http.get(preview) as resp:
                resp.raise_for_status()
                audio_bytes = await resp.read()
            thumb = None
            cover = (track.get("album") or {}).get("cover_medium")
            if cover:
                async with http.get(cover) as resp:
                    if resp.status == 200:
                        thumb = BufferedInputFile(await resp.read(), "cover.jpg")
            await message.answer_audio(
                BufferedInputFile(audio_bytes, f"{artist} - {title}.mp3"),
                title=title,
                performer=artist,
                caption=caption,
                reply_markup=kb,
                thumbnail=thumb,
            )
            return
        except Exception:  # preview yuklanmasa — matn bilan yuboramiz
            log.exception("Preview yuborib bo'lmadi")

    await message.answer(caption, reply_markup=kb)


async def show_results(message: Message, query: str, index: int = 0, edit: bool = False) -> None:
    # 1-sahifada avval o'z kutubxonamizdagi to'liq qo'shiqlar chiqadi
    lib_hits = library.search(query)[:PAGE_SIZE] if index == 0 else []
    limit = PAGE_SIZE - len(lib_hits)

    tracks: list[dict] = []
    total = 0
    try:
        tracks, total = await deezer_search(query, index=index, limit=max(limit, 1))
        tracks = tracks[:limit]
    except Exception:
        log.exception("Deezer qidiruv xatosi")

    if not lib_hits and not tracks:
        text = f"😕 «{esc(query)}» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    lines = [f"🔍 <b>{esc(query)}</b>\n"]
    buttons = []
    n = 0
    for lib_idx, it in lib_hits:
        n += 1
        line = f"<b>{n}.</b> 🎧 {esc(it['performer'])} - {esc(it['title'])}"
        if it.get("duration"):
            line += f"  <b>{fmt_duration(it['duration'])}</b>"
        lines.append(line)
        buttons.append(InlineKeyboardButton(text=str(n), callback_data=f"l:{lib_idx}"))
    for t in tracks:
        n += 1
        artist = (t.get("artist") or {}).get("name", "")
        line = f"<b>{n}.</b> {esc(artist)} - {esc(t.get('title', ''))}"
        if t.get("duration"):
            line += f"  <b>{fmt_duration(t['duration'])}</b>"
        lines.append(line)
        buttons.append(InlineKeyboardButton(text=str(n), callback_data=f"t:{t['id']}"))
    if lib_hits:
        lines.append("\n🎧 — to'liq qo'shiq")

    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    next_index = index + len(tracks)
    has_prev = index > 0
    has_next = bool(tracks) and next_index < total
    rows.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"p:{max(0, index - PAGE_SIZE)}" if has_prev else "noop"),
        InlineKeyboardButton(text="❌", callback_data="close"),
        InlineKeyboardButton(text="➡️", callback_data=f"p:{next_index}" if has_next else "noop"),
    ])

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def run_ffmpeg(*args: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        log.warning("ffmpeg xatosi: %s", err.decode(errors="ignore")[:500])
    return proc.returncode == 0


async def recognize_file(src: Path, workdir: Path) -> dict | None:
    """Fayldan bir nechta joyni kesib, Shazam orqali aniqlashga urinadi."""
    for offset in SAMPLE_OFFSETS:
        sample = workdir / f"sample_{offset}.wav"
        ok = await run_ffmpeg(
            "-ss", str(offset), "-i", str(src), "-t", str(SAMPLE_SECONDS),
            "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(sample),
        )
        # 1 soniyadan qisqa bo'lsa — fayl tugadi
        if not ok or not sample.exists() or sample.stat().st_size < 16000 * 2:
            break
        try:
            result = await shazam.recognize(str(sample))
        except Exception:
            log.exception("Shazam xatosi")
            continue
        if result.get("track"):
            return result["track"]
    return None


# --------------------------------------------------------------------------- #
# Handlerlar
# --------------------------------------------------------------------------- #
WELCOME = (
    "🎧✨ <b>Baxtiyor Saidov</b> botiga xush kelibsiz! ✨🎧\n\n"
    "Bu botda siz qo'shig'ingizni oson topishingiz va yuklab olishingiz mumkin:\n\n"
    "🔤 <b>Muzika nomi orqali</b> — qo'shiq yoki ijrochi nomini yozing\n"
    "      masalan: <code>Ummon</code>\n"
    "🎬 <b>Video orqali</b> — reels, video yoki dumaloq video yuboring\n"
    "🎙 <b>Golosovoy orqali</b> — qo'shiqni telefonga yaqin qo'yib yozib yuboring\n"
    "🎵 <b>Audio fayl orqali</b> — nomini aniqlab beraman\n\n"
    "⚡️ Tez, oson va bepul!\n"
    "👇 Boshlash uchun hoziroq qo'shiq nomini yozing yoki video yuboring.\n\n"
    "━━━━━━━━━━━━━━━\n"
    "📢 Reklama va hamkorlik uchun: @Baxtiyor_Saidof"
)


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME)


MEDIA_FILTER = (
    F.voice | F.audio | F.video | F.video_note | F.animation
    | (F.document & F.document.mime_type.regexp(r"^(audio|video)/"))
)


@router.message(MEDIA_FILTER)
async def on_media(message: Message) -> None:
    media = (message.voice or message.audio or message.video or message.video_note
             or message.animation or message.document)
    if media.file_size and media.file_size > MAX_TG_DOWNLOAD:
        await message.reply("⚠️ Fayl 20 MB dan katta. Qisqaroq parcha yuboring.")
        return

    status = await message.reply("🎧 Tinglayapman...")
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        src = workdir / "input"
        try:
            await message.bot.download(media.file_id, destination=src)
            track = await recognize_file(src, workdir)
        except Exception:
            log.exception("Aniqlashda xato")
            await status.edit_text("❌ Faylni o'qib bo'lmadi. Boshqa formatda yuborib ko'ring.")
            return

    if not track:
        await status.edit_text(
            "😕 Qo'shiqni aniqlay olmadim.\n"
            "Musiqa aniqroq eshitiladigan parcha yuboring yoki qo'shiq nomini yozing."
        )
        return

    title = track.get("title", "")
    artist = track.get("subtitle", "")
    shazam_link = track.get("url")
    found_text = f"✅ Topildi: <b>{esc(artist)} — {esc(title)}</b>"
    if shazam_link:
        found_text += f'\n<a href="{esc(shazam_link)}">Shazam\'da ochish</a>'
    await status.edit_text(found_text, disable_web_page_preview=True)

    # Topilgan qo'shiqning variantlari (original, remix, cover...) ro'yxati —
    # foydalanuvchi o'ziga yoqqanini tanlaydi.
    query = f"{artist} {title}"
    last_query[message.chat.id] = query
    try:
        await show_results(message, query)
    except Exception:
        log.exception("Deezer qidiruv xatosi")
        await message.answer(
            f"🎵 <b>{esc(artist)} — {esc(title)}</b>",
            reply_markup=links_keyboard(artist, title, shazam_link=shazam_link),
        )


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    query = message.text.strip()
    if query.startswith(("http://", "https://")):
        await message.answer(
            "🔗 Havola orqali emas — videoning o'zini yuboring (yoki qo'shiq nomini yozing)."
        )
        return
    last_query[message.chat.id] = query
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        await show_results(message, query)
    except Exception:
        log.exception("Qidiruv xatosi")
        await message.answer("❌ Qidiruvda xato bo'ldi, keyinroq urinib ko'ring.")


@router.callback_query(F.data.startswith("p:"))
async def on_page(cb: CallbackQuery) -> None:
    query = last_query.get(cb.message.chat.id)
    if not query:
        await cb.answer("Qidiruv eskirgan, qaytadan yozing.", show_alert=True)
        return
    await cb.answer()
    await show_results(cb.message, query, index=int(cb.data[2:]), edit=True)


@router.callback_query(F.data == "close")
async def on_close(cb: CallbackQuery) -> None:
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(F.data.startswith("t:"))
async def on_track(cb: CallbackQuery) -> None:
    await cb.answer("⏳ Yuklanmoqda...")
    try:
        track = await deezer_get(f"/track/{int(cb.data[2:])}")
    except Exception:
        log.exception("Track olishda xato")
        await cb.message.answer("❌ Qo'shiqni olib bo'lmadi.")
        return
    await send_track(cb.message, track)


@router.callback_query(F.data.startswith("l:"))
async def on_library_track(cb: CallbackQuery) -> None:
    idx = int(cb.data[2:])
    if idx >= len(library.items) or library.items[idx].get("deleted"):
        await cb.answer("Bu qo'shiq o'chirilgan.", show_alert=True)
        return
    await cb.answer("⏳ Yuborilmoqda...")
    it = library.items[idx]
    caption = f"🎵 <b>{esc(it['performer'])} — {esc(it['title'])}</b>"
    try:
        await cb.message.answer_audio(it["file_id"], caption=caption)
    except Exception:
        log.exception("Kutubxona audiosini yuborib bo'lmadi")
        await cb.message.answer("❌ Qo'shiqni yuborib bo'lmadi.")


# ---- Kutubxona kanali ----
CHANNEL_AUDIO = F.audio | (F.document & F.document.mime_type.startswith("audio/"))


@router.channel_post(F.text.startswith("/id"))
async def channel_id(message: Message) -> None:
    await message.answer(f"Kanal ID: <code>{message.chat.id}</code>")


@router.channel_post(F.text.startswith("/del") & F.reply_to_message)
async def channel_del(message: Message) -> None:
    if message.chat.id != library.chat_id:
        return
    it = await library.remove_by_msg(message.bot, message.reply_to_message.message_id)
    await message.answer(f"🗑 O'chirildi: {esc(it['performer'])} — {esc(it['title'])}" if it
                         else "Bu xabar kutubxonada yo'q.")


@router.channel_post(F.text.startswith("/count"))
async def channel_count(message: Message) -> None:
    if message.chat.id == library.chat_id:
        await message.answer(f"📚 Kutubxonada {len(library.active())} ta qo'shiq bor.")


@router.channel_post(CHANNEL_AUDIO)
async def channel_audio(message: Message) -> None:
    if message.chat.id != library.chat_id:
        return
    try:
        await library.add(message.bot, message)
    except Exception:
        log.exception("Kutubxonaga qo'shib bo'lmadi")


# --------------------------------------------------------------------------- #
async def main() -> None:
    global http
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv("BOT_TOKEN")
    if not token:
        env = Path(__file__).with_name(".env")
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    if not token:
        raise SystemExit("BOT_TOKEN topilmadi. .env fayliga yoki muhit o'zgaruvchisiga yozing.")

    http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await library.load(bot)

    # Serverda (Render va h.k.) webhook rejimi: Telegram o'zi xabarlarni yuboradi,
    # shuning uchun bepul server "uxlab qolsa" ham birinchi xabarda uyg'onadi.
    base_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
    try:
        if base_url:
            await run_webhook(bot, dp, token, base_url.rstrip("/"))
        else:
            log.info("Bot ishga tushdi (polling)")
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)
    finally:
        await http.close()
        await bot.session.close()


async def run_webhook(bot: Bot, dp: Dispatcher, token: str, base_url: str) -> None:
    import hashlib

    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    secret = hashlib.sha256(token.encode()).hexdigest()[:32]
    path = f"/tg/{secret}"

    app = web.Application()
    app.router.add_get("/", lambda _: web.Response(text="Music bot ishlayapti ✅"))
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(app, path=path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    await bot.set_webhook(
        f"{base_url}{path}", secret_token=secret, drop_pending_updates=False,
        allowed_updates=dp.resolve_used_update_types(),
    )
    log.info("Bot ishga tushdi (webhook, port %s)", port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
