import json
from pathlib import Path
from typing import ClassVar, cast

import pytest

from unixgram_changelog.archive import ArchiveSettings, GitHubArchive
from unixgram_changelog.ingestion import IngestionService
from unixgram_changelog.notifications import AdminNotifier
from unixgram_changelog.sources import Detection
from unixgram_changelog.sources.web import GitHubSnapshotSource, NextDeploymentSource
from unixgram_changelog.storage import Repository


class FakeResponse:
    def __init__(self, body: str, *, content_type: str = "text/html") -> None:
        self.body = body
        self.headers = {"Content-Type": content_type}
        self.status = 200

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self.body

    async def json(self) -> object:
        return json.loads(self.body)


class FakeSession:
    bodies: ClassVar[list[str]] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def get(self, *_: object, **__: object) -> FakeResponse:
        return FakeResponse(self.bodies.pop(0))


class FakeJsonResponse(FakeResponse):
    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def json(self) -> object:
        return self.payload


class FakeJsonSession(FakeSession):
    payloads: ClassVar[list[object]] = []

    def get(self, *_: object, **__: object) -> FakeJsonResponse:
        return FakeJsonResponse(self.payloads.pop(0))


class DummyBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_: object) -> None:
        self.calls.append((chat_id, text))


def page(*assets: str) -> str:
    tags = "".join(f'<script src="/_next/static/chunks/{asset}.js"></script>' for asset in assets)
    return f"<html><body>{tags}{'x' * 1100}</body></html>"


@pytest.mark.asyncio
async def test_deployment_source_baselines_then_detects_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    FakeSession.bodies = [
        page("layout-aaaabbbb", "webpack-11112222"),
        page("layout-ccccdddd", "app-eeeeffff"),
    ]
    monkeypatch.setattr("unixgram_changelog.sources.web.aiohttp.ClientSession", FakeSession)
    source = NextDeploymentSource(repository, "web", "Web", "https://example.test/")

    assert await source.collect() == []
    detections = await source.collect()

    assert len(detections) == 1
    assert detections[0].entry.external_id is not None
    assert detections[0].entry.title == "Web: новая сборка"
    assert detections[0].entry.changed_files == ("app.js", "layout.js", "webpack.js")
    assert "build " in detections[0].evidence
    assert "files: app.js, layout.js, webpack.js" in detections[0].evidence


@pytest.mark.asyncio
async def test_source_state_survives_repository_reopen(tmp_path: Path) -> None:
    path = tmp_path / "changelog.db"
    repository = Repository(path)
    await repository.initialize()
    await repository.set_source_state("web", "assets", json.dumps({"fingerprint": "abc"}))

    reopened = Repository(path)
    await reopened.initialize()

    assert await reopened.get_source_state("web", "assets") == '{"fingerprint": "abc"}'


@pytest.mark.asyncio
async def test_github_snapshot_source_links_new_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    first = {"sha": "a" * 40, "html_url": "https://github.com/example/repo/commit/aaa"}
    second = {"sha": "b" * 40, "html_url": "https://github.com/example/repo/commit/bbb"}
    FakeJsonSession.payloads = [
        [first],
        [second],
        {"files": [{"filename": "data/snapshots/unixgram/chunks/app/layout.json"}]},
    ]
    monkeypatch.setattr("unixgram_changelog.sources.web.aiohttp.ClientSession", FakeJsonSession)
    source = GitHubSnapshotSource(repository, repository_name="example/repo")

    assert await source.collect() == []
    detections = await source.collect()

    assert len(detections) == 1
    assert detections[0].entry.source_url == second["html_url"]
    assert detections[0].entry.source_name.endswith("@bbbbbbb")
    assert "unixgram/chunks/app/layout.json" in detections[0].evidence


class StaticSource:
    slug = "web"
    name = "Web"

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    async def collect(self) -> list[Detection]:
        source = NextDeploymentSource(self.repository, "web", "Web", "https://example.test/")
        return await source.collect()


@pytest.mark.asyncio
async def test_archiver_fallback_adds_github_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Repository(tmp_path / "changelog.db")
    await repository.initialize()
    FakeSession.bodies = [page("first"), page("second")]
    monkeypatch.setattr("unixgram_changelog.sources.web.aiohttp.ClientSession", FakeSession)

    source = StaticSource(repository)
    await source.collect()

    bot = DummyBot()
    notifier = AdminNotifier(bot=cast(object, bot), admin_ids=frozenset({6089346880}))  # type: ignore[arg-type]
    service = IngestionService(
        repository,
        [source],
        notifier=notifier,
        archiver=GitHubArchive(
            ArchiveSettings(
                repository="jutsu-dev/UnixGramChangelog",
                branch="main",
                directory="archive",
                token=None,
            )
        ),
    )

    report = await service.collect()

    assert len(report.accepted) == 1
    assert report.accepted[0].archive_url == "https://github.com/jutsu-dev/UnixGramChangelog"
    assert "https://github.com/jutsu-dev/UnixGramChangelog" in bot.calls[0][1]
