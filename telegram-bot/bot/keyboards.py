from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from . import texts
from .recognizer import Track
from .search import SongResult


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_SEARCH), KeyboardButton(text=texts.BTN_IDENTIFY)],
            [KeyboardButton(text=texts.BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def url_actions(token: str, recognition_enabled: bool = True) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=texts.BTN_VIDEO, callback_data=f"dl:v:{token}"),
        InlineKeyboardButton(text=texts.BTN_MP3, callback_data=f"dl:a:{token}"),
    ]]
    if recognition_enabled:
        rows.append([InlineKeyboardButton(text=texts.BTN_RECOGNIZE, callback_data=f"dl:r:{token}")])
    rows.append([InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def link_rows(links: dict[str, str]) -> list[list[InlineKeyboardButton]]:
    buttons = [InlineKeyboardButton(text=f"▶️ {label}", url=url) for label, url in links.items()]
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def track_links(track: Track) -> InlineKeyboardMarkup:
    from urllib.parse import quote_plus

    links = dict(track.links)
    links.setdefault("YouTube Music", f"https://music.youtube.com/search?q={quote_plus(track.artist + ' ' + track.title)}")
    return InlineKeyboardMarkup(inline_keyboard=link_rows(links))


def search_results(results: list[SongResult]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for r in results:
        rows.append([InlineKeyboardButton(text=f"🎶 {r.artist} — {r.title}"[:60], callback_data="noop")])
        rows.extend(link_rows(r.links))
    return InlineKeyboardMarkup(inline_keyboard=rows)
