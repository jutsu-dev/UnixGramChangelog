from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from .access import OwnerOnlyMiddleware
from .bot import create_router
from .config import Settings
from .notifications import AdminNotifier
from .publisher import Publisher
from .storage import Repository


async def configure_bot(bot: Bot, owner_id: int) -> None:
    await bot.set_my_name("UnixGram Changelog")
    await bot.set_my_short_description("Проверяемая история изменений UnixGram")
    await bot.set_my_description(
        "Закрытая редакционная панель канала UnixGram Changelog. "
        "Находки, источники, проверка и публикация без дублей."
    )
    await bot.delete_my_commands(scope=BotCommandScopeDefault())
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="открыть редакционную панель"),
            BotCommand(command="new", description="создать запись"),
            BotCommand(command="queue", description="открыть очередь"),
            BotCommand(command="history", description="последние публикации"),
            BotCommand(command="types", description="категории изменений"),
        ],
        scope=BotCommandScopeChat(chat_id=owner_id),
    )


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    repository = Repository(settings.database_path)
    await repository.initialize()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await configure_bot(bot, settings.owner_id)
    publisher = Publisher(bot, repository, settings.channel_id)
    notifier = AdminNotifier(bot, settings.admin_ids)
    dispatcher = Dispatcher()
    dispatcher.message.outer_middleware(OwnerOnlyMiddleware(settings.owner_id))
    dispatcher.callback_query.outer_middleware(OwnerOnlyMiddleware(settings.owner_id))
    dispatcher.include_router(create_router(repository, publisher, notifier, settings.admin_ids))
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
