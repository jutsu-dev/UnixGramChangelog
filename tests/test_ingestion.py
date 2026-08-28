from pathlib import Path
from typing import Any, cast

import pytest

from unixgram_changelog.ingestion import IngestionService
from unixgram_changelog.models import ChangeEntry, ChangeKind, SourceRecord
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


class CountingSource(WorkingSource):
    def __init__(self) -> None:
        self.collect_calls = 0

    async def collect(self) -> list[Detection]:
        self.collect_calls += 1
        return await super().collect()


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
    bot = DummyBot()
    notifier = AdminNotifier(bot=cast(Any, bot), admin_ids=frozenset({6089346880}))
    service = IngestionService(repository, [WorkingSource()], notifier=notifier)

    report = await service.collect()

    assert len(report.accepted) == 1
    assert bot.calls[0][0] == 6089346880
    assert "Источник Working source прислал новое изменение" in bot.calls[0][1]


@pytest.mark.asyncio
async def test_detection_evidence_is_persisted_when_entry_omits_it(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    service = IngestionService(repository, [WorkingSource()])

    report = await service.collect()

    assert len(report.accepted) == 1
    assert report.accepted[0].evidence == "fixture"


@pytest.mark.asyncio
async def test_disabled_source_is_skipped_before_collection(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    await repository.save_source(SourceRecord(slug="working", name="Working source", enabled=False))
    source = CountingSource()
    service = IngestionService(repository, [source])

    report = await service.collect()

    assert source.collect_calls == 0
    assert not report.accepted
