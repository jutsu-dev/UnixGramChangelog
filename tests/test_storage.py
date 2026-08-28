from pathlib import Path

import pytest

from unixgram_changelog.models import ChangeEntry, ChangeKind, EntryStatus
from unixgram_changelog.storage import Repository


@pytest.mark.asyncio
async def test_duplicate_entry_is_rejected(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    entry = ChangeEntry(
        title="One change", summary="Details", kind=ChangeKind.FEATURE,
        source_name="UnixGram", source_url="https://unixgram.com/change/1",
    )
    assert await repository.add(entry) is not None
    assert await repository.add(entry) is None


@pytest.mark.asyncio
async def test_review_can_be_published(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    saved = await repository.add(ChangeEntry(
        title="Fix", summary="Details", kind=ChangeKind.FIX, source_name="UnixGram",
    ))
    assert saved is not None and saved.id is not None
    assert await repository.mark(saved.id, EntryStatus.PUBLISHED, 42)
    published = await repository.get(saved.id)
    assert published is not None
    assert published.status is EntryStatus.PUBLISHED
    assert published.published_message_id == 42

