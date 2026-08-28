from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from .formatting import KIND_META, is_valid_source_url, render_entry
from .models import ChangeEntry, ChangeKind, EntryStatus
from .notifications import AdminNotifier
from .publisher import Publisher
from .storage import Repository
from .ui import answer_card, icon, main_menu, review_menu


def review_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    return review_menu(entry_id)


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
        await message.answer("Доступ закрыт. Управление доступно только владельцу.")
        return False

    async def show_home(message: Message) -> None:
        await answer_card(
            message,
            f"{icon('home')} <b>UnixGram Changelog</b>\n"
            "<blockquote>закрытая редакционная панель</blockquote>\n\n"
            "Находки проходят проверку перед публикацией. "
            "Источник обязателен, повторы отсекаются автоматически.\n\n"
            f"{icon('lock')} доступ открыт только владельцу",
            reply_markup=main_menu(),
            disable_web_page_preview=True,
        )

    async def show_new_guide(message: Message) -> None:
        await answer_card(
            message,
            f"{icon('new')} <b>Новая запись</b>\n"
            "<blockquote>пять полей через вертикальную черту</blockquote>\n\n"
            "<code>/new тип | заголовок | описание | источник | ссылка</code>\n\n"
            f"{icon('link')} ссылка на подтверждающий источник обязательна. "
            "Типы доступны в /types.",
            reply_markup=main_menu(),
        )

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if not await require_admin(message):
            return
        await show_home(message)

    @router.message(Command("types"))
    async def show_types(message: Message) -> None:
        if not await require_admin(message):
            return
        rows = [
            f"{code} <code>{kind.value}</code>: {escape(label)}"
            for kind, (code, label, _) in KIND_META.items()
        ]
        await answer_card(
            message,
            f"{icon('types')} <b>Категории изменений</b>\n"
            "<blockquote>выберите код для команды /new</blockquote>\n\n" + "\n".join(rows),
            reply_markup=main_menu(),
        )

    @router.message(Command("new"))
    async def new_entry(message: Message) -> None:
        if not await require_admin(message):
            return
        raw = (message.text or "").partition(" ")[2].strip()
        if not raw:
            await show_new_guide(message)
            return
        parts = [part.strip() for part in raw.split("|", maxsplit=4)]
        if len(parts) < 5:
            await message.answer("Не хватает полей. Открой /new и проверь формат.")
            return
        try:
            kind = ChangeKind(parts[0].casefold())
        except ValueError:
            await message.answer("Неизвестная категория. Доступные значения есть в /types.")
            return
        if not is_valid_source_url(parts[4]):
            await message.answer("Нужна полная ссылка на источник с https:// или http://.")
            return
        entry = ChangeEntry(
            kind=kind,
            title=parts[1][:140],
            summary=parts[2][:2400],
            source_name=parts[3][:120],
            source_url=parts[4],
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
            await answer_card(
                message,
                f"{icon('queue')} <b>Очередь пуста</b>\n\nНовых записей на проверке нет.",
                reply_markup=main_menu(),
            )
            return
        await answer_card(
            message,
            f"{icon('queue')} <b>На проверке: {len(entries)}</b>\n"
            "<blockquote>проверьте формулировку и источник</blockquote>"
        )
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
            await answer_card(
                message,
                f"{icon('history')} <b>История пуста</b>\n\nПубликаций пока нет.",
                reply_markup=main_menu(),
            )
            return
        rows = [f"<code>#{item.id}</code> {escape(item.title)}" for item in entries]
        await answer_card(
            message,
            f"{icon('history')} <b>Последние публикации</b>\n"
            "<blockquote>10 последних записей</blockquote>\n\n" + "\n".join(rows),
            reply_markup=main_menu(),
        )

    @router.callback_query(F.data == "menu:home")
    async def menu_home(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await show_home(callback.message)

    @router.callback_query(F.data == "menu:new")
    async def menu_new(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await show_new_guide(callback.message)

    @router.callback_query(F.data == "menu:queue")
    async def menu_queue(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await queue(callback.message)

    @router.callback_query(F.data == "menu:history")
    async def menu_history(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await history(callback.message)

    @router.callback_query(F.data == "menu:types")
    async def menu_types(callback: CallbackQuery) -> None:
        await callback.answer()
        if isinstance(callback.message, Message):
            await show_types(callback.message)

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
