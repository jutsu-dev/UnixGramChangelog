from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from .access import OwnerOnlyMiddleware
from .archive import ArchiveSettings, GitHubArchive
from .bot import create_router
from .config import Settings
from .ingestion import IngestionService
from .models import ChangeKind, SourceRecord
from .notifications import AdminNotifier
from .publisher import Publisher
from .sources import ChangeSource, GitHubSnapshotSource, JsonContractSource, NextDeploymentSource
from .storage import Repository

logger = logging.getLogger(__name__)


async def run_ingestion_loop(service: IngestionService, interval_seconds: int) -> None:
    while True:
        try:
            report = await service.collect()
            logger.info(
                "Source scan finished: accepted=%d duplicates=%d failures=%s",
                len(report.accepted),
                report.duplicates,
                list(report.source_failures),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected ingestion cycle failure")
        await asyncio.sleep(interval_seconds)


def build_default_sources(
    repository: Repository,
    timeout_seconds: float,
) -> list[ChangeSource]:
    return [
        GitHubSnapshotSource(repository=repository, timeout_seconds=timeout_seconds),
        GitHubSnapshotSource(
            repository=repository,
            site_slug="unixplace",
            subject="UnixPlace",
            base_url="https://place.unixgram.com/",
            slug="github-unixplace-snapshots",
            name="GitHub UnixPlace snapshots",
            timeout_seconds=timeout_seconds,
        ),
        JsonContractSource(
            repository,
            "unixplace-lots-contract",
            "UnixPlace lots API",
            "https://place.unixgram.com/api/lots?filter=sold&sort=recent&page=1",
            timeout_seconds,
        ),
    ]


async def sync_source_catalog(
    repository: Repository,
    sources: list[ChangeSource],
) -> None:
    for source in sources:
        source_url = getattr(source, "base_url", None) or getattr(source, "url", None)
        notes = (
            "Tracks Next.js build asset changes and creates a review entry when the public "
            "bundle fingerprint changes."
            if isinstance(source, NextDeploymentSource)
            else (
                "Tracks crawler commits under data/snapshots and links review entries to GitHub."
                if isinstance(source, GitHubSnapshotSource)
                else "Tracks public JSON response structure and creates a review entry when "
                "the contract shape changes."
            )
        )
        default_kind = (
            ChangeKind.API if isinstance(source, JsonContractSource) else ChangeKind.TECHNICAL
        )
        current = await repository.get_source(source.slug)
        source_record = SourceRecord(
            slug=source.slug,
            name=source.name,
            url=source_url,
            notes=notes,
            default_kind=default_kind,
        )
        if current is not None:
            source_record = replace(
                current,
                name=source.name,
                url=source_url,
                notes=notes,
            )
        await repository.save_source(source_record)


async def configure_bot(bot: Bot, owner_id: int) -> None:
    try:
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
    except TelegramAPIError as error:
        logger.warning("Bot command configuration skipped: %s", error)


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    repository = Repository(settings.database_path)
    await repository.initialize()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if settings.configure_bot_on_startup:
        await configure_bot(bot, settings.owner_id)
    publisher = Publisher(bot, repository, settings.channel_id)
    notifier = AdminNotifier(bot, settings.admin_ids)
    archiver = GitHubArchive(
        ArchiveSettings(
            repository=settings.github_repository,
            branch=settings.github_branch,
            directory=settings.github_archive_directory,
            token=settings.github_token,
        )
    )
    sources = build_default_sources(repository, settings.source_timeout_seconds)
    await sync_source_catalog(repository, sources)
    ingestion = IngestionService(
        repository,
        sources,
        publisher=publisher,
        notifier=notifier,
        archiver=archiver,
        review_required=settings.review_required,
    )
    dispatcher = Dispatcher()
    dispatcher.message.outer_middleware(OwnerOnlyMiddleware(settings.owner_id))
    dispatcher.callback_query.outer_middleware(OwnerOnlyMiddleware(settings.owner_id))
    dispatcher.include_router(create_router(repository, publisher, notifier, settings.admin_ids))
    ingestion_task = (
        asyncio.create_task(run_ingestion_loop(ingestion, settings.ingestion_interval_seconds))
        if settings.ingestion_enabled
        else None
    )
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if ingestion_task is not None:
            ingestion_task.cancel()
            await asyncio.gather(ingestion_task, return_exceptions=True)
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
