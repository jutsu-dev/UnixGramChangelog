from unixgram_changelog.config import Settings


def test_single_admin_id_from_environment() -> None:
    settings = Settings(
        bot_token="1234567890:test_token_for_configuration",
        admin_ids=6089346880,
    )
    assert settings.admin_ids == frozenset((6089346880,))


def test_multiple_admin_ids_from_environment() -> None:
    settings = Settings(
        bot_token="1234567890:test_token_for_configuration",
        admin_ids="1, 2,3",
    )
    assert settings.admin_ids == frozenset((1, 2, 3))
