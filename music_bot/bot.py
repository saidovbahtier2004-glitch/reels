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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
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

from importer.runner import ImportManager
from importer.telegram_ui import build_router as build_import_router
from importer.text import norm

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
INDEX_CAPTION = "📚 Kutubxona indeksi — o'chirmang"
INDEX_VERSION = 2
TZ = timezone(timedelta(hours=5))  # Toshkent vaqti
SAVE_DELAY = 3.0  # bir nechta audio birdan tashlansa, indeks bir marta yoziladi


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def fmt_size(size: int | None) -> str:
    if not size:
        return "—"
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024:.0f} KB"


def parse_audio_meta(audio) -> tuple[str, str]:
    """Audio teglaridan yoki fayl nomidan (Ijrochi - Nomi.mp3) nom va ijrochini oladi."""
    title = (getattr(audio, "title", None) or "").strip()
    artist = (getattr(audio, "performer", None) or "").strip()
    if not title:
        stem = Path(getattr(audio, "file_name", None) or "Nomsiz").stem.replace("_", " ").strip()
        if " - " in stem:
            left, right = (s.strip() for s in stem.split(" - ", 1))
            if artist:
                title = right or left
            else:
                artist, title = left, right
        else:
            title = stem
    return title or "Nomsiz", artist


class Library:
    """Kanaldagi audiolar bazasi.

    Har bir yozuv: id, title, artist, file_id, file_unique_id, duration,
    file_size, date_added, source_channel, msg_id (+ deleted, key).
    Baza kanalda pin qilingan library.json faylida saqlanadi, shuning uchun
    server qayta ishga tushsa ham yo'qolmaydi. Audiolar serverga yuklanmaydi —
    foydalanuvchiga Telegram file_id orqali yuboriladi.
    """

    def __init__(self) -> None:
        self.channel = os.getenv("LIBRARY_CHANNEL_ID", "").strip()
        self.chat_id: int | None = None
        self.index_msg_id: int | None = None
        self.items: list[dict] = []
        self.by_uid: dict[str, dict] = {}
        self.by_sha: dict[str, dict] = {}  # import qilingan originallar (sha256)
        self.jobs: dict[str, dict] = {}  # import job'lari holati (importer paketi)
        self.lock = asyncio.Lock()
        self._dirty = False
        self._save_task: asyncio.Task | None = None

    # ---- yuklash / saqlash ----
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
                self.load_data(json.loads(buf.read().decode()))
                self.index_msg_id = pm.message_id
            log.info("Kutubxona yuklandi: %s ta qo'shiq", len(self.active()))
        except Exception:
            log.exception("Kutubxona kanalini o'qib bo'lmadi (bot kanalda admin ekanini tekshiring)")

    def load_data(self, data: dict) -> None:
        """JSON'dan yuklaydi va eski (v1) yozuvlarni yangi formatga o'tkazadi."""
        self.items = []
        self.jobs = dict(data.get("jobs", {}))
        for i, raw in enumerate(data.get("items", [])):
            it = dict(raw)
            it["id"] = i + 1  # id = ro'yxatdagi o'rni, o'chirilganlar ham joyida qoladi
            it.setdefault("file_unique_id", it.pop("uid", ""))
            it.setdefault("artist", it.pop("performer", ""))
            it.setdefault("msg_id", it.pop("msg", None))
            it.setdefault("title", "Nomsiz")
            it.setdefault("duration", 0)
            it.setdefault("file_size", 0)
            it.setdefault("date_added", "")
            it.setdefault("source_channel", self.chat_id)
            it["key"] = norm(f"{it['artist']} {it['title']} {it.get('file_name', '')}")
            self.items.append(it)
        self._reindex()

    def _reindex(self) -> None:
        self.by_uid = {it["file_unique_id"]: it for it in self.items
                       if not it.get("deleted") and it.get("file_unique_id")}
        self.by_sha = {it["sha256"]: it for it in self.items if not it.get("deleted") and it.get("sha256")}

    def dump(self) -> bytes:
        items = [{k: v for k, v in it.items() if k != "key"} for it in self.items]
        return json.dumps({"version": INDEX_VERSION, "items": items, "jobs": self.jobs},
                          ensure_ascii=False).encode()

    async def _write(self, bot: Bot) -> None:
        doc = BufferedInputFile(self.dump(), INDEX_NAME)
        if self.index_msg_id:
            try:
                await bot.edit_message_media(
                    chat_id=self.chat_id, message_id=self.index_msg_id,
                    media=InputMediaDocument(media=doc, caption=INDEX_CAPTION),
                )
                return
            except Exception:
                log.exception("Indeksni yangilab bo'lmadi, yangisini yaratamiz")
                doc = BufferedInputFile(self.dump(), INDEX_NAME)
        msg = await bot.send_document(self.chat_id, doc, caption=INDEX_CAPTION, disable_notification=True)
        self.index_msg_id = msg.message_id
        await bot.pin_chat_message(self.chat_id, msg.message_id, disable_notification=True)

    def schedule_save(self, bot: Bot) -> None:
        self._dirty = True
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._delayed_save(bot))

    async def _delayed_save(self, bot: Bot) -> None:
        await asyncio.sleep(SAVE_DELAY)
        await self.flush(bot)

    async def flush(self, bot: Bot) -> None:
        async with self.lock:
            if not self._dirty:
                return
            self._dirty = False
            try:
                await self._write(bot)
                log.info("Indeks saqlandi (%s ta qo'shiq)", len(self.active()))
            except Exception:
                self._dirty = True
                log.exception("Indeksni saqlab bo'lmadi")

    # ---- o'qish ----
    def active(self) -> list[dict]:
        return [it for it in self.items if not it.get("deleted")]

    def get(self, item_id: int) -> dict | None:
        if 1 <= item_id <= len(self.items) and not self.items[item_id - 1].get("deleted"):
            return self.items[item_id - 1]
        return None

    def search(self, query: str) -> list[dict]:
        """Barcha so'zlar mos kelganlar; aniqroq moslar oldinda."""
        q = norm(query)
        words = q.split()
        if not words:
            return []
        scored = []
        for it in self.items:
            if it.get("deleted"):
                continue
            key = it["key"]
            if not all(w in key for w in words):
                continue
            title = norm(it["title"])
            full = norm(f"{it['artist']} {it['title']}")
            if q in (title, full):
                score = 0
            elif title.startswith(q) or full.startswith(q) or norm(it["artist"]) == q:
                score = 1
            elif q in key:
                score = 2
            else:
                score = 3
            scored.append((score, it["id"], it))
        scored.sort(key=lambda s: (s[0], s[1]))
        return [s[2] for s in scored]

    def added_on(self, day: date) -> list[dict]:
        out = []
        for it in self.active():
            try:
                if datetime.fromisoformat(it["date_added"]).astimezone(TZ).date() == day:
                    out.append(it)
            except (ValueError, TypeError):
                pass
        return out

    def stats(self) -> dict:
        act = self.active()
        return {
            "total": len(act),
            "today": len(self.added_on(datetime.now(TZ).date())),
            "deleted": len(self.items) - len(act),
            "artists": len({norm(it["artist"]) for it in act if it["artist"]}),
            "size": sum(it.get("file_size") or 0 for it in act),
            "duration": sum(it.get("duration") or 0 for it in act),
        }

    def duplicates(self) -> list[list[dict]]:
        """Bir xil ijrochi + nomli (lekin boshqa fayl) qo'shiqlar guruhlari."""
        groups: dict[str, list[dict]] = {}
        for it in self.active():
            groups.setdefault(norm(f"{it['artist']} {it['title']}"), []).append(it)
        return [g for g in groups.values() if len(g) > 1]

    async def check(self, bot: Bot) -> dict:
        """Bazani tekshiradi: maydonlar, takroriy file_unique_id va file_id'lar ishlashi."""
        problems: list[str] = []
        broken: list[dict] = []
        seen: dict[str, int] = {}
        for it in self.active():
            for field in ("file_id", "file_unique_id", "title"):
                if not it.get(field):
                    problems.append(f"#{it['id']}: {field} yo'q")
            uid = it.get("file_unique_id")
            if uid in seen:
                problems.append(f"#{it['id']}: #{seen[uid]} bilan bir xil fayl")
            elif uid:
                seen[uid] = it["id"]
            try:
                await bot.get_file(it["file_id"])
            except TelegramBadRequest as e:
                if "too big" not in str(e).lower():  # 20 MB dan kattalar uchun bu normal
                    broken.append(it)
                    log.warning("Ishlamaydigan file_id #%s: %s", it["id"], e)
            except Exception:
                log.exception("file_id tekshiruvida xato #%s", it["id"])
            await asyncio.sleep(0.05)  # Telegram limitlariga urilmaslik uchun
        return {"checked": len(self.active()), "problems": problems, "broken": broken,
                "index_ok": bool(self.index_msg_id)}

    # ---- yozish ----
    def find_existing(self, *, isrc: str = "", provider: str = "", external_id: str = "",
                      artist: str = "", title: str = "", duration: int = 0) -> dict | None:
        """Import paytida takrorni aniqlash: ISRC, provider ID yoki ijrochi+nom+davomiylik."""
        name = norm(f"{artist} {title}") if title else ""
        for it in self.active():
            if isrc and it.get("isrc") and it["isrc"].upper() == isrc.upper():
                return it
            if external_id and it.get("external_id") == external_id and it.get("provider") == provider:
                return it
            if name and norm(f"{it['artist']} {it['title']}") == name and (
                    not duration or not it.get("duration") or abs(it["duration"] - duration) <= 2):
                return it
        return None

    async def add(self, bot: Bot, message: Message, extra: dict | None = None) -> dict | None:
        """Kanal postidagi audioni bazaga qo'shadi. Takroriy bo'lsa None qaytaradi.
        extra — import metadata'si (isrc, license_id, provider, ...), nom/ijrochini ham ustidan yozadi."""
        audio = message.audio or message.document
        title, artist = parse_audio_meta(audio)
        async with self.lock:
            if audio.file_unique_id in self.by_uid:
                log.info("Takroriy audio o'tkazib yuborildi: %s — %s", artist, title)
                return None
            item = {
                "id": len(self.items) + 1,
                "title": title,
                "artist": artist,
                "file_id": audio.file_id,
                "file_unique_id": audio.file_unique_id,
                "duration": getattr(audio, "duration", None) or 0,
                "file_size": getattr(audio, "file_size", None) or 0,
                "date_added": now_iso(),
                "source_channel": message.chat.id,
                "msg_id": message.message_id,
                "file_name": getattr(audio, "file_name", None) or "",
            }
            if extra:
                item.update({k: v for k, v in extra.items() if v not in (None, "")})
                title, artist = item["title"], item["artist"]
            item["key"] = norm(f"{artist} {title} {item['file_name']}")
            self.items.append(item)
            self.by_uid[item["file_unique_id"]] = item
            if item.get("sha256"):
                self.by_sha[item["sha256"]] = item
        log.info("Kutubxonaga qo'shildi #%s: %s — %s", item["id"], artist, title)
        self.schedule_save(bot)
        return item

    async def remove(self, bot: Bot, item: dict) -> None:
        async with self.lock:
            item["deleted"] = True
            self._reindex()
        log.info("Kutubxonadan o'chirildi #%s: %s — %s", item["id"], item["artist"], item["title"])
        self.schedule_save(bot)

    async def remove_by_msg(self, bot: Bot, msg_id: int) -> dict | None:
        for it in self.items:
            if it.get("msg_id") == msg_id and not it.get("deleted"):
                await self.remove(bot, it)
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
    """Natijalar: avval o'z bazamizdagi to'liq qo'shiqlar (🎧), keyin Deezer.
    index — umumiy ro'yxatdagi siljish (sahifalash uchun)."""
    lib_hits = library.search(query)
    lib_page = lib_hits[index:index + PAGE_SIZE]
    limit = PAGE_SIZE - len(lib_page)
    dz_index = max(0, index - len(lib_hits))

    tracks: list[dict] = []
    dz_total = 0
    if limit > 0:
        try:
            tracks, dz_total = await deezer_search(query, index=dz_index, limit=limit)
            tracks = tracks[:limit]
        except Exception:
            log.exception("Deezer qidiruv xatosi")
    else:
        dz_total = 1  # keyingi sahifada Deezer natijalari bo'lishi mumkin

    if not lib_page and not tracks:
        text = f"😕 «{esc(query)}» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    lines = [f"🔍 <b>{esc(query)}</b>\n"]
    buttons = []
    n = index
    for it in lib_page:
        n += 1
        line = f"<b>{n}.</b> 🎧 {esc(it['artist'])} - {esc(it['title'])}"
        if it.get("duration"):
            line += f"  <b>{fmt_duration(it['duration'])}</b>"
        lines.append(line)
        buttons.append(InlineKeyboardButton(text=str(n), callback_data=f"l:{it['id']}"))
    for t in tracks:
        n += 1
        artist = (t.get("artist") or {}).get("name", "")
        line = f"<b>{n}.</b> {esc(artist)} - {esc(t.get('title', ''))}"
        if t.get("duration"):
            line += f"  <b>{fmt_duration(t['duration'])}</b>"
        lines.append(line)
        buttons.append(InlineKeyboardButton(text=str(n), callback_data=f"t:{t['id']}"))
    if lib_page:
        lines.append("\n🎧 — to'liq qo'shiq")

    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    next_index = index + len(lib_page) + len(tracks)
    has_prev = index > 0
    has_next = next_index < len(lib_hits) + dz_total and (bool(tracks) or limit == 0)
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


async def send_library_item(message: Message, it: dict) -> None:
    """Bazadagi qo'shiqni serverga yuklamasdan, file_id orqali yuboradi."""
    caption = f"🎵 <b>{esc(it['artist'])} — {esc(it['title'])}</b>"
    try:
        await message.answer_audio(it["file_id"], caption=caption)
    except Exception:
        log.exception("Kutubxona audiosini yuborib bo'lmadi #%s", it.get("id"))
        await message.answer("❌ Qo'shiqni yuborib bo'lmadi.")


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
    "Bu botda siz qo'shig'ingizni oson topishingiz va yuklab olishingiz mumkin.\n\n"
    "📩 Menga <b>video parcha</b> 🎬, <b>ovozli xabar</b> 🎙, <b>musiqa parchasi</b> 🎵 "
    "yoki <b>qo'shiq nomini</b> 🔤 jo'nating.\n\n"
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
    it = library.get(int(cb.data[2:]))
    if not it:
        await cb.answer("Bu qo'shiq o'chirilgan.", show_alert=True)
        return
    await cb.answer("⏳ Yuborilmoqda...")
    await send_library_item(cb.message, it)


# --------------------------------------------------------------------------- #
# Admin panel (faqat ADMIN_IDS dagi foydalanuvchilar uchun)
# --------------------------------------------------------------------------- #
ADMIN_IDS = {int(x) for x in re.findall(r"-?\d+", os.getenv("ADMIN_IDS", ""))}
ADMIN_LIST_LIMIT = 30


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
         InlineKeyboardButton(text="📅 Bugun qo'shilgan", callback_data="adm:today")],
        [InlineKeyboardButton(text="♻️ Takroriylar", callback_data="adm:dups"),
         InlineKeyboardButton(text="🩺 Bazani tekshirish", callback_data="adm:check")],
        [InlineKeyboardButton(text="🔍 Qidirish", callback_data="adm:find")],
    ])


def item_line(it: dict) -> str:
    return (f"<code>#{it['id']}</code> {esc(it['artist'])} — {esc(it['title'])} "
            f"<i>({fmt_duration(it.get('duration')) or '—'}, {fmt_size(it.get('file_size'))})</i>")


def admin_stats_text() -> str:
    s = library.stats()
    if not library.chat_id:
        head = "⚠️ Kutubxona kanali ulanmagan (LIBRARY_CHANNEL_ID).\n\n"
    else:
        head = f"📡 Kanal: <code>{library.chat_id}</code>\n\n"
    hours, rem = divmod(s["duration"], 3600)
    return (head +
            f"🎵 Jami musiqalar: <b>{s['total']}</b>\n"
            f"📅 Bugun qo'shilgan: <b>{s['today']}</b>\n"
            f"👤 Ijrochilar: <b>{s['artists']}</b>\n"
            f"💾 Umumiy hajm: <b>{fmt_size(s['size'])}</b>\n"
            f"⏱ Umumiy davomiylik: <b>{hours} soat {rem // 60} daqiqa</b>\n"
            f"🗑 O'chirilganlar: {s['deleted']}")


def admin_today_text() -> str:
    items = library.added_on(datetime.now(TZ).date())
    if not items:
        return "📅 Bugun hali musiqa qo'shilmagan."
    lines = [f"📅 Bugun qo'shilgan: <b>{len(items)}</b>\n"]
    lines += [item_line(it) for it in items[-ADMIN_LIST_LIMIT:]]
    if len(items) > ADMIN_LIST_LIMIT:
        lines.append(f"\n… va yana {len(items) - ADMIN_LIST_LIMIT} ta")
    return "\n".join(lines)


def admin_dups_text() -> str:
    groups = library.duplicates()
    if not groups:
        return "♻️ Takroriy musiqalar topilmadi ✅\n\n<i>Bir xil fayllar baza qo'shayotganda avtomatik o'tkazib yuboriladi.</i>"
    lines = [f"♻️ Bir xil nomli musiqalar: <b>{len(groups)}</b> guruh\n"]
    for g in groups[:15]:
        lines += [item_line(it) for it in g]
        lines.append("")
    lines.append("O'chirish: <code>/delete ID</code>")
    return "\n".join(lines)


async def admin_find(message: Message, query: str) -> None:
    hits = library.search(query)
    if not hits:
        await message.answer(f"🔍 «{esc(query)}» — bazada topilmadi.")
        return
    shown = hits[:ADMIN_LIST_LIMIT]
    lines = [f"🔍 «{esc(query)}» — bazada <b>{len(hits)}</b> ta\n"] + [item_line(it) for it in shown]
    if len(hits) > len(shown):
        lines.append(f"\n… va yana {len(hits) - len(shown)} ta")
    buttons = [InlineKeyboardButton(text=f"#{it['id']}", callback_data=f"l:{it['id']}") for it in shown[:10]]
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + 5] for i in range(0, len(buttons), 5)])
    await message.answer("\n".join(lines), reply_markup=kb)


async def admin_check(message: Message) -> None:
    status = await message.answer(f"🩺 Tekshirilmoqda... ({len(library.active())} ta musiqa)")
    try:
        r = await library.check(message.bot)
    except Exception:
        log.exception("Bazani tekshirishda xato")
        await status.edit_text("❌ Tekshiruvda xato bo'ldi, logni ko'ring.")
        return
    lines = [
        "🩺 <b>Baza tekshiruvi</b>\n",
        f"✔️ Tekshirildi: {r['checked']}",
        f"📌 Indeks fayli: {'bor ✅' if r['index_ok'] else 'hali yaratilmagan ⚠️'}",
        f"❌ Ishlamaydigan fayllar: {len(r['broken'])}",
        f"⚠️ Boshqa muammolar: {len(r['problems'])}",
    ]
    if r["broken"]:
        lines.append("\n<b>Ishlamaydigan fayllar:</b>")
        lines += [item_line(it) for it in r["broken"][:20]]
        lines.append("O'chirish: <code>/delete ID</code>")
    if r["problems"]:
        lines.append("\n<b>Muammolar:</b>")
        lines += [esc(p) for p in r["problems"][:20]]
    if not r["broken"] and not r["problems"]:
        lines.append("\nHammasi joyida ✅")
    await status.edit_text("\n".join(lines))


PRIVATE = F.chat.type == "private"


@router.message(Command("myid"), PRIVATE)
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Sizning ID: <code>{message.from_user.id}</code>")


@router.message(Command("admin", "stats", "today", "dups", "check", "find", "delete"), PRIVATE)
async def admin_commands(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("⛔️ Bu buyruq faqat adminlar uchun.")
        return
    cmd, _, arg = (message.text or "").partition(" ")
    cmd = cmd.lstrip("/").split("@")[0].lower()
    arg = arg.strip()
    try:
        if cmd == "admin":
            await message.answer("🛠 <b>Admin panel</b>\n\n" + admin_stats_text(), reply_markup=admin_keyboard())
        elif cmd == "stats":
            await message.answer(admin_stats_text())
        elif cmd == "today":
            await message.answer(admin_today_text())
        elif cmd == "dups":
            await message.answer(admin_dups_text())
        elif cmd == "check":
            await admin_check(message)
        elif cmd == "find":
            if not arg:
                await message.answer("Foydalanish: <code>/find qo'shiq nomi</code>")
            else:
                await admin_find(message, arg)
        elif cmd == "delete":
            it = library.get(int(arg)) if arg.isdigit() else None
            if not it:
                await message.answer("Foydalanish: <code>/delete ID</code> (ID bazada bo'lishi kerak)")
            else:
                await library.remove(message.bot, it)
                await message.answer(f"🗑 O'chirildi: {item_line(it)}")
    except Exception:
        log.exception("Admin buyrug'ida xato: %s", message.text)
        await message.answer("❌ Xato bo'ldi, logni ko'ring.")


@router.callback_query(F.data.startswith("adm:"))
async def admin_buttons(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔️ Faqat adminlar uchun.", show_alert=True)
        return
    action = cb.data[4:]
    await cb.answer()
    try:
        if action == "stats":
            await cb.message.answer(admin_stats_text())
        elif action == "today":
            await cb.message.answer(admin_today_text())
        elif action == "dups":
            await cb.message.answer(admin_dups_text())
        elif action == "check":
            await admin_check(cb.message)
        elif action == "find":
            await cb.message.answer("🔍 Bazadan qidirish: <code>/find qo'shiq nomi</code>")
    except Exception:
        log.exception("Admin tugmasida xato: %s", cb.data)
        await cb.message.answer("❌ Xato bo'ldi, logni ko'ring.")


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
    await message.answer(f"🗑 O'chirildi: #{it['id']} {esc(it['artist'])} — {esc(it['title'])}" if it
                         else "Bu xabar kutubxonada yo'q.")


@router.channel_post(F.text.startswith("/count"))
async def channel_count(message: Message) -> None:
    if message.chat.id == library.chat_id:
        s = library.stats()
        await message.answer(f"📚 Kutubxonada {s['total']} ta qo'shiq bor (bugun +{s['today']}).")


@router.channel_post(CHANNEL_AUDIO)
async def channel_audio(message: Message) -> None:
    if message.chat.id != library.chat_id:
        return
    try:
        await library.add(message.bot, message)
    except Exception:
        log.exception("Kutubxonaga qo'shib bo'lmadi (post %s)", message.message_id)


@router.message(Command("version"))
async def cmd_version(message: Message) -> None:
    commit = (os.getenv("RENDER_GIT_COMMIT") or "")[:7] or "noma'lum"
    await message.answer(f"🤖 Bot versiyasi: <code>{commit}</code>")


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    """Noma'lum buyruqqa jim qolmaymiz (eng oxirgi handler bo'lishi kerak)."""
    cmd = esc(message.text.split()[0])
    await message.answer(f"🤷 <code>{cmd}</code> degan buyruq yo'q.\n"
                         "Qo'shiq nomini yozing yoki video yuboring. Yordam: /start")


# --------------------------------------------------------------------------- #
# Ommaviy import (importer paketi). Import router'i birinchi turadi, chunki u
# ochiq import bo'lganda admin yuborgan audiolarni Shazam'dan oldin ushlaydi.
# --------------------------------------------------------------------------- #
import_manager = ImportManager(lambda: library)
root_router = Router(name="root")
root_router.include_routers(build_import_router(import_manager, is_admin), router)


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
    dp.include_router(root_router)
    await library.load(bot)
    import_manager.bind(bot)
    await import_manager.resume_all()  # server qayta ishga tushsa, importlar davom etadi

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
        await library.flush(bot)  # saqlanmagan o'zgarishlarni yozib qo'yamiz
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
