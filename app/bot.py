"""Точка входа бота."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app import config, db, seeds
from app.handlers import build_root_router
from app.middlewares import AccessMiddleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("my-codes-bot")


async def main() -> None:
    config.validate()

    await db.init_db()
    await seeds.ensure_seeds()
    log.info("DB initialized at %s", config.DB_PATH)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # access middleware на уровне Update — отрезает левых пользователей
    dp.update.middleware(AccessMiddleware())

    dp.include_router(build_root_router())

    # сбросить вебхук на всякий случай (если когда-то ставился)
    await bot.delete_webhook(drop_pending_updates=False)

    me = await bot.get_me()
    log.info("Bot @%s started", me.username)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bye")
