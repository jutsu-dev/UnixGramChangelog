from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .bot import create_router
from .config import Settings
from .notifications import AdminNotifier
from .publisher import Publisher
from .storage import Repository


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    repository = Repository(settings.database_path)
    await repository.initialize()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    publisher = Publisher(bot, repository, settings.channel_id)
    notifier = AdminNotifier(bot, settings.admin_ids)
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(repository, publisher, notifier, settings.admin_ids))
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
