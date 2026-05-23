"""
Entry point — Mega → GDrive Telegram Bot.
"""
import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

import config
from handlers import mega_handler, reupload_handler, start_handler, token_handler, workspace_handler


async def main() -> None:
    config.validate_config()

    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
    logger.add("data/bot.log", level="DEBUG", rotation="10 MB", retention="7 days")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers in priority order
    dp.include_router(start_handler.router)
    dp.include_router(token_handler.router)
    dp.include_router(workspace_handler.router)
    dp.include_router(reupload_handler.router)
    dp.include_router(mega_handler.router)

    logger.info("🤖 Bot starting — polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
