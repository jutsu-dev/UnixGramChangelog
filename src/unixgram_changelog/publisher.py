from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from .formatting import plain_entry, render_entry
from .models import ChangeEntry, EntryStatus
from .storage import Repository

logger = logging.getLogger(__name__)


class Publisher:
    def __init__(self, bot: Bot, repository: Repository, channel_id: str) -> None:
        self.bot = bot
        self.repository = repository
        self.channel_id = channel_id

    async def publish(self, entry: ChangeEntry) -> Message:
        if entry.id is None:
            raise ValueError("Entry must be stored before publication")
        try:
            if entry.published_message_id is not None:
                message = await self.bot.edit_message_text(
                    render_entry(entry),
                    self.channel_id,
                    entry.published_message_id,
                    disable_web_page_preview=True,
                )
            else:
                message = await self.bot.send_message(
                    self.channel_id,
                    render_entry(entry),
                    disable_web_page_preview=True,
                )
        except TelegramBadRequest as error:
            logger.warning("HTML publication failed; retrying as plain text: %s", error)
            if entry.published_message_id is not None:
                message = await self.bot.edit_message_text(
                    plain_entry(entry),
                    self.channel_id,
                    entry.published_message_id,
                    parse_mode=None,
                    disable_web_page_preview=True,
                )
            else:
                message = await self.bot.send_message(
                    self.channel_id,
                    plain_entry(entry),
                    parse_mode=None,
                    disable_web_page_preview=True,
                )
        if not isinstance(message, Message):
            raise RuntimeError("Telegram returned no message after publication")
        await self.repository.mark(entry.id, EntryStatus.PUBLISHED, message.message_id)
        return message
