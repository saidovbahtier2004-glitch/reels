"""Musiqa topuvchi Telegram bot.

Nima qiladi:
  * Qo'shiq nomi yoki ijrochi yozilsa — ro'yxat chiqaradi, tanlanganini yuboradi.
  * Video, reels, video-xabar (dumaloq), ovozli xabar yoki audio yuborilsa —
    ichidagi qo'shiqni aniqlaydi (Shazam) va uni yuboradi.

Audio sifatida Deezer'ning rasmiy 30 soniyalik preview'lari yuboriladi,
to'liq versiya uchun Spotify / YouTube / Apple Music / Deezer havolalari beriladi.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
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
    Message,
)
from shazamio import Shazam

log = logging.getLogger("music_bot")

DEEZER_API = "https://api.deezer.com"
PAGE_SIZE = 8
MAX_TG_DOWNLOAD = 20 * 1024 * 1024  # Bot API fayl yuklab olish limiti
SAMPLE_SECONDS = 20
SAMPLE_OFFSETS = (0, 15, 35, 60)  # musiqa videoning o'rtasida boshlansa ham topish uchun

router = Router()
shazam = Shazam()
http: aiohttp.ClientSession | None = None

# chat_id -> oxirgi qidiruv so'rovi (sahifalash tugmalari uchun)
last_query: dict[int, str] = {}


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
    tracks, total = await deezer_search(query, index=index)
    if not tracks:
        text = f"😕 «{esc(query)}» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    rows = []
    for i, t in enumerate(tracks, start=index + 1):
        artist = (t.get("artist") or {}).get("name", "")
        label = f"{i}. {artist} — {t.get('title', '')}"
        if t.get("duration"):
            label += f" ({fmt_duration(t['duration'])})"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"t:{t['id']}")])

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"p:{max(0, index - PAGE_SIZE)}"))
    if index + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"p:{index + PAGE_SIZE}"))
    if nav:
        rows.append(nav)

    text = f"🔎 <b>{esc(query)}</b> — {total} ta natija. Tanlang:"
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
    "👋 Salom! Men musiqa topuvchi botman.\n\n"
    "Menga yuboring:\n"
    "🔤 <b>Qo'shiq nomi yoki ijrochi</b> — masalan: <code>Konsta</code>\n"
    "🎬 <b>Video / reels / dumaloq video</b> — ichidagi qo'shiqni topaman\n"
    "🎙 <b>Ovozli xabar</b> — qo'shiqni telefonga yaqin qo'yib yozib yuboring\n"
    "🎵 <b>Audio fayl</b> — nomini aniqlab beraman"
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
    await status.edit_text(f"✅ Topildi: <b>{esc(artist)} — {esc(title)}</b>")

    # Shazam natijasini Deezer'dan qidirib, audio bilan yuboramiz
    try:
        found, _ = await deezer_search(f'artist:"{artist}" track:"{title}"', limit=1)
        if not found:
            found, _ = await deezer_search(f"{artist} {title}", limit=1)
    except Exception:
        log.exception("Deezer qidiruv xatosi")
        found = []

    if found:
        await send_track(message, found[0], shazam_link=shazam_link)
    else:
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
    try:
        log.info("Bot ishga tushdi")
        await dp.start_polling(bot)
    finally:
        await http.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
