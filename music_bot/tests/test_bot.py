"""Bot testlari: haqiqiy aiogram routeriga soxta update'lar yuboriladi,
Telegram API o'rniga FakeSession javob beradi (internet kerak emas).

Ishga tushirish:  cd music_bot && python -m pytest -q tests
"""

from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery, EditMessageMedia, GetFile, PinChatMessage, SendAudio,
    SendDocument, SendMessage,
)
from aiogram.types import Chat, File, Message, Update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot as botmod  # noqa: E402

CHANNEL = -1003951552121
ADMIN = 111
USER = 222


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []
        self.next_id = 1000

    async def close(self) -> None:
        pass

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, GetFile):
            if method.file_id.startswith("BROKEN"):
                raise TelegramBadRequest(method=method, message="Bad Request: wrong file_id")
            if method.file_id.startswith("BIG"):
                raise TelegramBadRequest(method=method, message="Bad Request: file is too big")
            return File(file_id=method.file_id, file_unique_id="u")
        if isinstance(method, (PinChatMessage, AnswerCallbackQuery)):
            return True
        if hasattr(method, "chat_id"):
            self.next_id += 1
            chat_id = method.chat_id
            ctype = "channel" if isinstance(chat_id, int) and chat_id < 0 else "private"
            return Message(message_id=getattr(method, "message_id", None) or self.next_id,
                           date=dt.datetime.now(), chat=Chat(id=chat_id, type=ctype)).as_(bot)
        return True

    def of(self, kind):
        return [c for c in self.calls if isinstance(c, kind)]

    def texts(self) -> str:
        return "\n".join(c.text for c in self.of(SendMessage))


# --------------------------------------------------------------------------- #
@pytest.fixture
def env(monkeypatch):
    session = FakeSession()
    bot = Bot("123456:TEST", session=session,
              default=botmod.DefaultBotProperties(parse_mode=botmod.ParseMode.HTML))
    dp = Dispatcher()
    # router faqat bir marta ulanishi mumkin — har testda yangi Dispatcher'ga qayta bog'laymiz
    botmod.router._parent_router = None
    dp.include_router(botmod.router)

    lib = botmod.Library()
    lib.chat_id = CHANNEL
    monkeypatch.setattr(botmod, "library", lib)
    monkeypatch.setattr(botmod, "SAVE_DELAY", 0.01)
    monkeypatch.setattr(botmod, "ADMIN_IDS", {ADMIN})
    botmod.last_query.clear()

    async def no_deezer(query, index=0, limit=10):
        return [], 0
    monkeypatch.setattr(botmod, "deezer_search", no_deezer)
    return bot, dp, session, lib


_uid = [0]


def upd(**payload) -> Update:
    _uid[0] += 1
    return Update.model_validate({"update_id": _uid[0], **payload})


def channel_audio(msg_id, uid, title=None, performer=None, file_name=None, chat=CHANNEL,
                  duration=200, size=5_000_000, file_id=None):
    audio = {"file_id": file_id or f"FID_{uid}", "file_unique_id": uid, "duration": duration,
             "file_size": size}
    if title:
        audio["title"] = title
    if performer:
        audio["performer"] = performer
    if file_name:
        audio["file_name"] = file_name
    return upd(channel_post={"message_id": msg_id, "date": 1700000000,
                             "chat": {"id": chat, "type": "channel", "title": "Uzb music"},
                             "audio": audio})


def private_text(text, user=USER):
    return upd(message={"message_id": _uid[0] + 500, "date": 1700000000,
                        "chat": {"id": user, "type": "private"},
                        "from": {"id": user, "is_bot": False, "first_name": "T"},
                        "text": text})


def callback(data, user=USER):
    return upd(callback_query={
        "id": str(_uid[0]), "chat_instance": "x", "data": data,
        "from": {"id": user, "is_bot": False, "first_name": "T"},
        "message": {"message_id": 42, "date": 1700000000,
                    "chat": {"id": user, "type": "private"}, "text": "…"}})


def run(coro):
    return asyncio.run(coro)


async def feed(bot, dp, *updates, settle=0.05):
    for u in updates:
        await dp.feed_update(bot, u)
    await asyncio.sleep(settle)  # kechiktirilgan saqlash ishlashi uchun


# --------------------------------------------------------------------------- #
# 1. Avtomatik yig'ish
# --------------------------------------------------------------------------- #
def test_channel_audio_saved_with_all_fields(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(10, "U1", title="Xiyonat", performer="Ummon")))
    it = lib.get(1)
    assert it["title"] == "Xiyonat" and it["artist"] == "Ummon"
    assert it["file_id"] == "FID_U1" and it["file_unique_id"] == "U1"
    assert it["duration"] == 200 and it["file_size"] == 5_000_000
    assert it["source_channel"] == CHANNEL and it["msg_id"] == 10
    assert dt.datetime.fromisoformat(it["date_added"]).tzinfo is not None


def test_filename_fallback(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(11, "U2", file_name="Konsta - Ko'nglim.mp3")))
    it = lib.get(1)
    assert (it["artist"], it["title"]) == ("Konsta", "Ko'nglim")


def test_duplicates_are_skipped(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(10, "U1", title="A", performer="B"),
             channel_audio(12, "U1", title="A", performer="B")))
    assert len(lib.active()) == 1


def test_other_channels_ignored(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(10, "U1", title="A", chat=-100999)))
    assert lib.active() == []


def test_bulk_upload_saves_index_once_then_edits(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, *[channel_audio(10 + i, f"U{i}", title=f"Song {i}") for i in range(5)]))
    assert len(s.of(SendDocument)) == 1 and len(s.of(PinChatMessage)) == 1
    run(feed(bot, dp, channel_audio(50, "U50", title="Yana")))
    assert len(s.of(SendDocument)) == 1 and len(s.of(EditMessageMedia)) == 1


def test_index_roundtrip_and_v1_migration(env):
    bot, dp, s, lib = env
    old = {"items": [{"file_id": "F", "uid": "U", "title": "T", "performer": "P",
                      "duration": 100, "msg": 7, "key": "p t"}]}
    lib.load_data(old)
    it = lib.get(1)
    assert it["artist"] == "P" and it["file_unique_id"] == "U" and it["msg_id"] == 7
    assert it["source_channel"] == CHANNEL and it["file_size"] == 0
    lib2 = botmod.Library()
    lib2.load_data(__import__("json").loads(lib.dump()))
    assert lib2.get(1)["title"] == "T" and "U" in lib2.by_uid


def test_channel_post_is_subscribed():
    dp = Dispatcher()
    botmod.router._parent_router = None
    dp.include_router(botmod.router)
    assert "channel_post" in dp.resolve_used_update_types()


# --------------------------------------------------------------------------- #
# 2. Qidiruv va yuborish
# --------------------------------------------------------------------------- #
def test_search_ranking(env):
    bot, dp, s, lib = env
    run(feed(bot, dp,
             channel_audio(1, "a", title="Xiyonat qilding", performer="Boshqa"),
             channel_audio(2, "b", title="Xiyonat", performer="Ummon"),
             channel_audio(3, "c", title="Dengiz", performer="Ummon")))
    assert [i["title"] for i in lib.search("xiyonat")] == ["Xiyonat", "Xiyonat qilding"]
    assert [i["title"] for i in lib.search("ummon")] == ["Xiyonat", "Dengiz"]
    assert lib.search("yoq narsa") == []


def test_user_search_shows_library_first(env, monkeypatch):
    bot, dp, s, lib = env

    async def dz(query, index=0, limit=10):
        return [{"id": 900 + i, "title": f"DZ{i}", "artist": {"name": "Ummon"}, "duration": 180}
                for i in range(limit)], 50
    monkeypatch.setattr(botmod, "deezer_search", dz)
    run(feed(bot, dp, channel_audio(1, "a", title="Xiyonat", performer="Ummon"),
             private_text("Ummon")))
    msg = s.of(SendMessage)[-1]
    assert "1.</b> 🎧 Ummon - Xiyonat" in msg.text
    datas = [b.callback_data for row in msg.reply_markup.inline_keyboard for b in row]
    assert datas[0] == "l:1" and "t:900" in datas and "p:10" in datas


def test_library_pagination_beyond_first_page(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, *[channel_audio(i, f"u{i}", title=f"Qoshiq {i}", performer="Ummon")
                        for i in range(1, 15)]))
    run(feed(bot, dp, private_text("Ummon")))
    first = s.of(SendMessage)[-1]
    assert first.text.count("🎧") == 11  # 10 qator + izoh
    run(feed(bot, dp, callback("p:10")))
    page2 = [c for c in s.calls if type(c).__name__ == "EditMessageText"][-1]
    assert "11.</b> 🎧" in page2.text and "14.</b> 🎧" in page2.text


def test_send_uses_file_id_without_download(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(1, "a", title="Xiyonat", performer="Ummon"), callback("l:1")))
    audio = s.of(SendAudio)[-1]
    assert audio.audio == "FID_a"
    assert not any(type(c).__name__ == "GetFile" for c in s.calls)


def test_deleted_track_not_sent(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(1, "a", title="X"), private_text("/delete 1", user=ADMIN),
             callback("l:1")))
    assert s.of(SendAudio) == []
    assert lib.search("x") == []


# --------------------------------------------------------------------------- #
# 3. Admin panel
# --------------------------------------------------------------------------- #
def test_admin_only(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, private_text("/stats", user=USER), callback("adm:stats", user=USER)))
    assert "faqat adminlar" in s.texts()
    assert "Jami musiqalar" not in s.texts()


def test_admin_stats_and_today(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(1, "a", title="X", performer="Ummon", size=3 * 1024 * 1024),
             channel_audio(2, "b", title="Y", performer="Konsta")))
    lib.items[1]["date_added"] = "2020-01-01T10:00:00+05:00"  # eski qo'shiq
    run(feed(bot, dp, private_text("/admin", user=ADMIN), private_text("/today", user=ADMIN)))
    out = s.texts()
    assert "Jami musiqalar: <b>2</b>" in out
    assert "Bugun qo'shilgan: <b>1</b>" in out
    assert "Ijrochilar: <b>2</b>" in out
    assert "#1</code> Ummon — X" in out and "Konsta — Y" not in out.split("📅 Bugun qo'shilgan: <b>1</b>\n")[-1]


def test_admin_find_and_dups(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(1, "a", title="Xiyonat", performer="Ummon"),
             channel_audio(2, "b", title="Xiyonat", performer="Ummon"),  # boshqa fayl, bir xil nom
             channel_audio(3, "c", title="Dengiz", performer="Ummon"),
             private_text("/dups", user=ADMIN), private_text("/find dengiz", user=ADMIN)))
    out = s.texts()
    assert "1</b> guruh" in out and "#1</code>" in out and "#2</code>" in out
    find = s.of(SendMessage)[-1]
    assert "bazada <b>1</b> ta" in find.text and find.reply_markup.inline_keyboard[0][0].callback_data == "l:3"


def test_admin_check_reports_broken(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(1, "a", title="OK"),
             channel_audio(2, "b", title="Buzuq", file_id="BROKEN_1"),
             channel_audio(3, "c", title="Katta", file_id="BIG_1"),
             private_text("/check", user=ADMIN)))
    report = [c for c in s.calls if type(c).__name__ == "EditMessageText"][-1].text
    assert "Ishlamaydigan fayllar: 1" in report and "Buzuq" in report and "Katta" not in report


def test_channel_count_and_del(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, channel_audio(5, "a", title="X")))
    reply = upd(channel_post={"message_id": 6, "date": 1700000000,
                              "chat": {"id": CHANNEL, "type": "channel", "title": "U"},
                              "text": "/del",
                              "reply_to_message": {"message_id": 5, "date": 1700000000,
                                                   "chat": {"id": CHANNEL, "type": "channel"}}})
    count = upd(channel_post={"message_id": 7, "date": 1700000000,
                              "chat": {"id": CHANNEL, "type": "channel", "title": "U"},
                              "text": "/count"})
    run(feed(bot, dp, reply, count))
    out = s.texts()
    assert "O'chirildi: #1" in out and "0 ta qo'shiq" in out


# --------------------------------------------------------------------------- #
# 4. Avvalgi funksiyalar buzilmagan
# --------------------------------------------------------------------------- #
def test_start_and_myid(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, private_text("/start"), private_text("/myid")))
    out = s.texts()
    assert "Baxtiyor Saidov" in out and f"<code>{USER}</code>" in out


def test_text_search_without_library(env):
    bot, dp, s, lib = env
    run(feed(bot, dp, private_text("hech narsa")))
    assert "topilmadi" in s.texts()
