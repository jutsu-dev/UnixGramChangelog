from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .formatting import KIND_META, render_entry
from .models import ChangeEntry, ChangeKind, EntryStatus
from .notifications import AdminNotifier
from .publisher import Publisher
from .storage import Repository


def review_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Опубликовать", callback_data=f"publish:{entry_id}"
                ),
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{entry_id}"),
            ]
        ]
    )


def create_router(
    repository: Repository,
    publisher: Publisher,
    notifier: AdminNotifier,
    admin_ids: frozenset[int],
) -> Router:
    router = Router(name="unixgram-changelog")

    def is_admin(user_id: int | None) -> bool:
        return user_id is not None and user_id in admin_ids

    async def require_admin(message: Message) -> bool:
        user_id = message.from_user.id if message.from_user else None
        if is_admin(user_id):
            return True
        await message.answer("Управление changelog доступно только редакции.")
        return False

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if not await require_admin(message):
            return
        await message.answer(
            "<b>UnixGram Changelog</b>\n\n"
            "Редакционная очередь изменений UnixGram.\n\n"
            "<b>Команды</b>\n"
            "/new: формат новой записи\n"
            "/queue: очередь проверки\n"
            "/history: последние публикации\n"
            "/types: категории изменений"
        )

    @router.message(Command("types"))
    async def show_types(message: Message) -> None:
        if not await require_admin(message):
            return
        rows = [
            f"{code} <code>{kind.value}</code>: {escape(label)}"
            for kind, (code, label, _) in KIND_META.items()
        ]
        await message.answer("<b>Категории</b>\n\n" + "\n".join(rows))

    @router.message(Command("new"))
    async def new_entry(message: Message) -> None:
        if not await require_admin(message):
            return
        raw = (message.text or "").partition(" ")[2].strip()
        if not raw:
            await message.answer(
                "<b>Новая запись</b>\n\n"
                "<code>/new тип | заголовок | описание | источник | ссылка</code>\n\n"
                "Ссылка необязательна. Типы доступны в /types."
            )
            return
        parts = [part.strip() for part in raw.split("|", maxsplit=4)]
        if len(parts) < 4:
            await message.answer("Не хватает полей. Открой /new и проверь формат.")
            return
        try:
            kind = ChangeKind(parts[0].casefold())
        except ValueError:
            await message.answer("Неизвестная категория. Доступные значения есть в /types.")
            return
        entry = ChangeEntry(
            kind=kind,
            title=parts[1][:140],
            summary=parts[2][:2400],
            source_name=parts[3][:120],
            source_url=parts[4] if len(parts) == 5 and parts[4] else None,
        )
        saved = await repository.add(entry)
        if saved is None:
            await message.answer("Такая запись уже есть в истории или очереди.")
            return
        await message.answer(
            "<b>Предпросмотр</b>\n\n" + render_entry(saved),
            reply_markup=review_keyboard(saved.id or 0),
            disable_web_page_preview=True,
        )
        await notifier.notify_review_entry(
            saved,
            reply_markup=review_keyboard(saved.id or 0),
            skip_chat_id=message.chat.id,
        )

    @router.message(Command("queue"))
    async def queue(message: Message) -> None:
        if not await require_admin(message):
            return
        entries = await repository.list_by_status(EntryStatus.REVIEW)
        if not entries:
            await message.answer("Очередь проверки пуста.")
            return
        await message.answer(f"<b>На проверке: {len(entries)}</b>")
        for entry in entries:
            await message.answer(
                render_entry(entry),
                reply_markup=review_keyboard(entry.id or 0),
                disable_web_page_preview=True,
            )

    @router.message(Command("history"))
    async def history(message: Message) -> None:
        if not await require_admin(message):
            return
        entries = await repository.list_by_status(EntryStatus.PUBLISHED, limit=10)
        if not entries:
            await message.answer("Публикаций пока нет.")
            return
        rows = [f"<code>#{item.id}</code> {escape(item.title)}" for item in entries]
        await message.answer("<b>Последние публикации</b>\n\n" + "\n".join(rows))

    @router.callback_query(F.data.startswith("publish:"))
    async def publish(callback: CallbackQuery) -> None:
        if not is_admin(callback.from_user.id):
            await callback.answer("Недостаточно прав", show_alert=True)
            return
        entry_id = int((callback.data or "").partition(":")[2])
        entry = await repository.get(entry_id)
        if entry is None or entry.status is not EntryStatus.REVIEW:
            await callback.answer("Запись уже обработана", show_alert=True)
            return
        await publisher.publish(entry)
        await callback.answer("Опубликовано")
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)

    @router.callback_query(F.data.startswith("reject:"))
    async def reject(callback: CallbackQuery) -> None:
        if not is_admin(callback.from_user.id):
            await callback.answer("Недостаточно прав", show_alert=True)
            return
        entry_id = int((callback.data or "").partition(":")[2])
        changed = await repository.mark(entry_id, EntryStatus.REJECTED)
        await callback.answer("Отклонено" if changed else "Запись не найдена")
        if changed and isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)

    return router
