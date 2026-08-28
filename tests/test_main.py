from pathlib import Path

import pytest

from unixgram_changelog.main import build_default_sources, sync_source_catalog
from unixgram_changelog.models import ChangeKind, SourceMode, SourceRecord
from unixgram_changelog.storage import Repository


@pytest.mark.asyncio
async def test_sync_source_catalog_bootstraps_default_sources(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()

    sources = build_default_sources(repository, 12.0)
    await sync_source_catalog(repository, sources)

    stored = await repository.list_sources()

    assert [source.slug for source in stored] == [
        "github-unixplace-snapshots",
        "github-web-snapshots",
        "unixplace-lots-contract",
    ]
    assert stored[0].default_kind is ChangeKind.TECHNICAL
    assert stored[1].default_kind is ChangeKind.TECHNICAL
    assert stored[2].default_kind is ChangeKind.API


@pytest.mark.asyncio
async def test_sync_source_catalog_preserves_owner_toggles(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    await repository.save_source(
        SourceRecord(
            slug="github-web-snapshots",
            name="Old name",
            url="https://old.example/",
            notes="old notes",
            mode=SourceMode.AUTO,
            enabled=False,
            default_kind=ChangeKind.IMPORTANT,
            confidence_threshold=0.42,
        )
    )

    sources = build_default_sources(repository, 12.0)
    await sync_source_catalog(repository, sources)

    stored = await repository.get_source("github-web-snapshots")

    assert stored is not None
    assert stored.name == "GitHub snapshots"
    assert stored.url == "https://unixgram.com/"
    assert stored.mode is SourceMode.AUTO
    assert stored.enabled is False
    assert stored.default_kind is ChangeKind.IMPORTANT
    assert stored.confidence_threshold == 0.42
