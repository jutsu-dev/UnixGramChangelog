from pathlib import Path

import pytest

from unixgram_changelog.ingestion import IngestionService
from unixgram_changelog.models import ChangeEntry, ChangeKind
from unixgram_changelog.notifications import AdminNotifier
from unixgram_changelog.sources import Detection
from unixgram_changelog.storage import Repository


class WorkingSource:
    slug = "working"
    name = "Working source"

    async def collect(self) -> list[Detection]:
        return [Detection(
            entry=ChangeEntry(
                title="Detected change",
                summary="Evidence-backed description",
                kind=ChangeKind.DISCOVERY,
                source_name=self.name,
                external_id="change-1",
            ),
            confidence=0.9,
            evidence="fixture",
        )]


class FailingSource:
    slug = "failing"
    name = "Failing source"

    async def collect(self) -> list[Detection]:
        raise TimeoutError("source unavailable")


class DummyBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_: object) -> None:
        self.calls.append((chat_id, text))


@pytest.mark.asyncio
async def test_source_failure_does_not_stop_other_sources(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    service = IngestionService(repository, [FailingSource(), WorkingSource()])

    report = await service.collect()

    assert len(report.accepted) == 1
    assert report.accepted[0].title == "Detected change"
    assert report.source_failures == ("Failing source",)


@pytest.mark.asyncio
async def test_second_collection_is_deduplicated(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    service = IngestionService(repository, [WorkingSource()])

    first = await service.collect()
    second = await service.collect()

    assert len(first.accepted) == 1
    assert not second.accepted
    assert second.duplicates == 1


@pytest.mark.asyncio
async def test_new_detection_notifies_admins(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    notifier = AdminNotifier(bot=DummyBot(), admin_ids=frozenset({6089346880}))
    service = IngestionService(repository, [WorkingSource()], notifier=notifier)

    report = await service.collect()

    assert len(report.accepted) == 1
    assert notifier.bot.calls[0][0] == 6089346880
    assert "Источник Working source прислал новое изменение" in notifier.bot.calls[0][1]
