from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject


def is_owner_private(user_id: int | None, chat_type: ChatType | str | None, owner_id: int) -> bool:
    return user_id == owner_id and chat_type == ChatType.PRIVATE


class OwnerOnlyMiddleware(BaseMiddleware):
    """Silently discard every update outside the owner's private chat."""

    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            allowed = is_owner_private(
                event.from_user.id if event.from_user else None,
                event.chat.type,
                self.owner_id,
            )
        elif isinstance(event, CallbackQuery):
            chat_type = event.message.chat.type if isinstance(event.message, Message) else None
            allowed = is_owner_private(event.from_user.id, chat_type, self.owner_id)
        else:
            allowed = False
        if not allowed:
            return None
        return await handler(event, data)
