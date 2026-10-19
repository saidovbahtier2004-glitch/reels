from __future__ import annotations

import asyncio
import logging
import secrets
import tempfile
from collections import OrderedDict
from html import escape
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from . import keyboards, texts
from .config import Settings
from .downloader import DownloadFailed, FileTooBig, download_audio, download_video
from .links import extract_url, is_safe_url
from .media import MediaError, extract_audio_clip
from .recognizer import Recognizer, RecognitionError
from .search import search_songs

log = logging.getLogger(__name__)
router = Router()

TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024  # Bot API getFile limit


class UrlCache:
    """Remembers URLs behind inline buttons (Telegram callback data is limited to 64 bytes)."""

    def __init__(self, size: int = 1000) -> None:
        self._d: OrderedDict[str, str] = OrderedDict()
        self._size = size

    def put(self, url: str) -> str:
        token = secrets.token_urlsafe(6)
        self._d[token] = url
        while len(self._d) > self._size:
            self._d.popitem(last=False)
        return token

    def get(self, token: str) -> str | None:
        return self._d.get(token)


urls = UrlCache()
_sem: asyncio.Semaphore | None = None


def _semaphore(settings: Settings) -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.max_parallel_jobs)
    return _sem


async def _edit(msg: Message, text: str, **kw) -> None:
    try:
        await msg.edit_text(text, **kw)
    except TelegramBadRequest:
        pass  # "message is not modified" etc.


# ---------- basic commands / menu ----------

@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(texts.START, reply_markup=keyboards.main_menu())


@router.message(Command("help"))
@router.message(F.text == texts.BTN_HELP)
async def help_(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=keyboards.main_menu())


@router.message(F.text == texts.BTN_SEARCH)
async def search_prompt(message: Message) -> None:
    await message.answer(texts.SEARCH_PROMPT)


@router.message(F.text == texts.BTN_IDENTIFY)
async def identify_prompt(message: Message) -> None:
    await message.answer(texts.IDENTIFY_PROMPT)


@router.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery) -> None:
    await cb.answer()
    if cb.message:
        await _edit(cb.message, texts.CANCELLED)


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery) -> None:
    await cb.answer()


# ---------- recognition ----------

async def _send_track(message: Message, track) -> None:
    await message.answer(
        texts.track_card(track.title, track.artist, track.album),
        reply_markup=keyboards.track_links(track),
    )


async def _recognize_file(src: Path, workdir: Path, recognizer: Recognizer, status: Message, reply_to: Message) -> None:
    await _edit(status, texts.IDENTIFYING)
    try:
        clip = await extract_audio_clip(src, workdir / "clip.mp3")
    except MediaError:
        await _edit(status, texts.ERR_NO_AUDIO)
        return
    try:
        track = await recognizer.recognize(clip)
    except RecognitionError as exc:
        log.warning("recognition failed: %s", exc)
        await _edit(status, texts.ERR_RECOGNITION_API)
        return
    if track is None:
        await _edit(status, texts.NOT_FOUND_SONG)
        return
    await status.delete()
    await _send_track(reply_to, track)


@router.message(F.voice | F.audio | F.video | F.video_note | F.document)
async def on_media(message: Message, bot: Bot, settings: Settings, recognizer: Recognizer | None) -> None:
    media = message.voice or message.audio or message.video or message.video_note or message.document
    if media is None:
        return
    if message.document and not (message.document.mime_type or "").startswith(("audio/", "video/")):
        return
    if recognizer is None:
        await message.answer(texts.ERR_RECOGNITION_OFF)
        return
    if (media.file_size or 0) > TG_DOWNLOAD_LIMIT:
        await message.answer(texts.ERR_INPUT_TOO_BIG)
        return
    status = await message.answer(texts.QUEUED)
    async with _semaphore(settings):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            src = workdir / "input"
            try:
                await _edit(status, texts.DOWNLOADING)
                await bot.download(media, destination=src)
                await _recognize_file(src, workdir, recognizer, status, message)
            except TelegramBadRequest:
                await _edit(status, texts.ERR_INPUT_TOO_BIG)
            except Exception:
                log.exception("on_media failed")
                await _edit(status, texts.ERR_GENERIC)


# ---------- links ----------

async def _do_download(cb: CallbackQuery, bot: Bot, settings: Settings, recognizer: Recognizer | None, kind: str, url: str) -> None:
    assert cb.message
    status = cb.message
    await _edit(status, texts.QUEUED)
    async with _semaphore(settings):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            try:
                await _edit(status, texts.DOWNLOADING)
                if kind == "v":
                    item = await download_video(url, workdir, settings.max_upload_bytes)
                    await _edit(status, texts.UPLOADING)
                    await bot.send_video(
                        status.chat.id, FSInputFile(item.path), supports_streaming=True,
                        caption=f"🎬 {escape(item.title[:200])}", duration=item.duration,
                    )
                    await status.delete()
                elif kind == "a":
                    item = await download_audio(url, workdir, settings.max_upload_bytes, to_mp3=True)
                    await _edit(status, texts.UPLOADING)
                    await bot.send_audio(
                        status.chat.id, FSInputFile(item.path), title=item.title[:100],
                        performer=item.uploader[:100] or None, duration=item.duration,
                    )
                    await status.delete()
                else:
                    if recognizer is None:
                        await _edit(status, texts.ERR_RECOGNITION_OFF)
                        return
                    item = await download_audio(url, workdir, settings.max_upload_bytes, to_mp3=False)
                    await _recognize_file(item.path, workdir, recognizer, status, status)
            except FileTooBig:
                await _edit(status, texts.ERR_TOO_BIG)
            except DownloadFailed:
                await _edit(status, texts.ERR_DOWNLOAD)
            except TelegramBadRequest as exc:
                log.warning("telegram rejected upload: %s", exc)
                await _edit(status, texts.ERR_TOO_BIG)
            except Exception:
                log.exception("download failed")
                await _edit(status, texts.ERR_GENERIC)


@router.callback_query(F.data.regexp(r"^dl:[var]:"))
async def on_download_button(cb: CallbackQuery, bot: Bot, settings: Settings, recognizer: Recognizer | None) -> None:
    await cb.answer()
    _, kind, token = (cb.data or "").split(":", 2)
    url = urls.get(token)
    if not url or not cb.message:
        if cb.message:
            await _edit(cb.message, texts.EXPIRED)
        return
    await _do_download(cb, bot, settings, recognizer, kind, url)


# ---------- text: URL or song search ----------

@router.message(F.text)
async def on_text(message: Message, settings: Settings, recognizer: Recognizer | None) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    url = extract_url(text)
    if url:
        if not await asyncio.to_thread(is_safe_url, url):
            await message.answer(texts.ERR_BAD_URL)
            return
        await message.answer(
            texts.CHOOSE_ACTION,
            reply_markup=keyboards.url_actions(urls.put(url), recognizer is not None),
            disable_web_page_preview=True,
        )
        return
    status = await message.answer(texts.SEARCHING)
    try:
        results = await search_songs(text[:150], settings.itunes_country)
    except Exception:
        log.exception("search failed")
        await _edit(status, texts.ERR_SEARCH)
        return
    if not results:
        await _edit(status, texts.NOT_FOUND_SEARCH)
        return
    await _edit(status, f"🔎 <b>Natijalar:</b> {escape(text[:80])}", reply_markup=keyboards.search_results(results))
