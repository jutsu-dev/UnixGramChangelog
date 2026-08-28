from __future__ import annotations

import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

CUSTOM_EMOJI: dict[str, tuple[str, str]] = {
    "home": ("📰", "5895519358871932592"),
    "new": ("➕", "6032924188828767321"),
    "queue": ("📥", "6041730074376410123"),
    "history": ("📖", "6037286673010660132"),
    "types": ("🏷", "5888620056551625531"),
    "publish": ("✅", "5774022692642492953"),
    "reject": ("❌", "6030757850274336631"),
    "lock": ("🔒", "6037249452824072506"),
    "link": ("🔗", "6028171274939797252"),
}


def icon(name: str) -> str:
    fallback, custom_emoji_id = CUSTOM_EMOJI[name]
    return f'<tg-emoji emoji-id="{custom_emoji_id}">{fallback}</tg-emoji>'


_CUSTOM_EMOJI_TAG = re.compile(r"</?tg-emoji(?:\s+emoji-id=\"\d+\")?>")


async def answer_card(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> Message:
    """Send premium emoji when available, then retry with normal emoji."""

    try:
        return await message.answer(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramBadRequest:
        return await message.answer(
            _CUSTOM_EMOJI_TAG.sub("", text),
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Новая запись", callback_data="menu:new"),
                InlineKeyboardButton(text="📥 Очередь", callback_data="menu:queue"),
            ],
            [
                InlineKeyboardButton(text="📖 История", callback_data="menu:history"),
                InlineKeyboardButton(text="🏷 Категории", callback_data="menu:types"),
            ],
            [InlineKeyboardButton(text="📢 Канал", url="https://t.me/UnixGramChangelog")],
        ]
    )


def review_menu(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish:{entry_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{entry_id}"),
            ],
            [InlineKeyboardButton(text="↩️ В меню", callback_data="menu:home")],
        ]
    )
