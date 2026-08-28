from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from .formatting import plain_review_card, render_review_card
from .models import ChangeEntry

logger = logging.getLogger(__name__)


class AdminNotifier:
    def __init__(self, bot: Bot, admin_ids: frozenset[int]) -> None:
        self.bot = bot
        self.admin_ids = admin_ids

    async def notify_review_entry(
        self,
        entry: ChangeEntry,
        reply_markup: InlineKeyboardMarkup | None = None,
        skip_chat_id: int | None = None,
        heading: str = "Новое изменение ждёт проверки",
    ) -> None:
        html_text = f"<b>{heading}</b>\n\n{render_review_card(entry)}"
        plain_text = f"{heading}\n\n{plain_review_card(entry)}"
        for admin_id in self.admin_ids:
            if skip_chat_id is not None and admin_id == skip_chat_id:
                continue
            try:
                await self.bot.send_message(
                    admin_id,
                    html_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
            except TelegramBadRequest as error:
                logger.warning("Admin HTML notification failed; retrying as plain text: %s", error)
                try:
                    await self.bot.send_message(
                        admin_id,
                        plain_text,
                        parse_mode=None,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True,
                    )
                except TelegramAPIError:
                    logger.exception("Admin plain-text notification failed for %s", admin_id)
            except TelegramAPIError:
                logger.exception("Admin notification failed for %s", admin_id)
