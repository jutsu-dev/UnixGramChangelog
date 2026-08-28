from aiogram.enums import ChatType

from unixgram_changelog.access import is_owner_private


def test_owner_private_chat_is_allowed() -> None:
    assert is_owner_private(6089346880, ChatType.PRIVATE, 6089346880)


def test_other_user_is_rejected() -> None:
    assert not is_owner_private(123, ChatType.PRIVATE, 6089346880)


def test_owner_group_chat_is_rejected() -> None:
    assert not is_owner_private(6089346880, ChatType.GROUP, 6089346880)
