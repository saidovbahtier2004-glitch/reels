import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message, Update, User

from bot import handlers, texts
from bot.config import load_settings
from bot.search import SongResult

SETTINGS = load_settings({"BOT_TOKEN": "1:abc"})


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def close(self): ...
    async def stream_content(self, *a, **k): yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=len(self.calls) + 100, date=datetime.datetime.now(), chat=Chat(id=1, type="private"),
                           text=method.text).as_(bot)
        return True


def _update(text: str) -> Update:
    return Update(update_id=1, message=Message(message_id=1, date=datetime.datetime.now(), chat=Chat(id=1, type="private"),
                  from_user=User(id=1, is_bot=False, first_name="U"), text=text))


@pytest.fixture
def env():
    sess = FakeSession()
    bot = Bot("1:abc", session=sess)
    handlers.router._parent_router = None  # module-level router is reused across tests
    dp = Dispatcher(settings=SETTINGS, recognizer=None)
    dp.include_router(handlers.router)
    return bot, dp, sess


def _sent(sess):
    return [c for c in sess.calls if isinstance(c, SendMessage)]


async def test_start(env):
    bot, dp, sess = env
    await dp.feed_update(bot, _update("/start"))
    assert _sent(sess)[0].text == texts.START


async def test_url_shows_buttons(env):
    bot, dp, sess = env
    await dp.feed_update(bot, _update("https://8.8.8.8/video.mp4"))
    m = _sent(sess)[0]
    assert m.text == texts.CHOOSE_ACTION
    labels = [b.text for r in m.reply_markup.inline_keyboard for b in r]
    assert texts.BTN_VIDEO in labels and texts.BTN_RECOGNIZE not in labels  # recognition off


async def test_private_url_rejected(env):
    bot, dp, sess = env
    await dp.feed_update(bot, _update("http://127.0.0.1:8080/secret"))
    assert _sent(sess)[0].text == texts.ERR_BAD_URL


async def test_search(env, monkeypatch):
    async def fake(q, country="US"):
        return [SongResult("Song", "Artist", {"Apple Music": "https://a.example/1"})]
    monkeypatch.setattr(handlers, "search_songs", fake)
    bot, dp, sess = env
    await dp.feed_update(bot, _update("artist song"))
    edits = [c for c in sess.calls if c.__class__.__name__ == "EditMessageText"]
    assert edits and edits[-1].reply_markup.inline_keyboard[1][0].url == "https://a.example/1"
