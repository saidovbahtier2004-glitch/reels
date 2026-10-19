from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import ConfigError, load_settings
from .handlers import router
from .recognizer import build_recognizer


async def run() -> None:
    settings = load_settings()
    recognizer = build_recognizer(settings)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(settings=settings, recognizer=recognizer)
    dp.include_router(router)
    me = await bot.get_me()
    logging.info("Started as @%s | recognition: %s", me.username, settings.recognition_provider if recognizer else "off")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Never log full request URLs that could contain the token.
    logging.getLogger("aiogram").setLevel(logging.INFO)
    try:
        asyncio.run(run())
    except ConfigError as exc:
        logging.error("%s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
