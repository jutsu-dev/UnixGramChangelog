import json
from pathlib import Path
from typing import ClassVar

import pytest

from unixgram_changelog.sources.web import NextDeploymentSource
from unixgram_changelog.storage import Repository


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def text(self) -> str:
        return self.body


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
    FakeSession.bodies = [page("first"), page("second")]
    monkeypatch.setattr("unixgram_changelog.sources.web.aiohttp.ClientSession", FakeSession)
    source = NextDeploymentSource(repository, "web", "Web", "https://example.test/")

    assert await source.collect() == []
    detections = await source.collect()

    assert len(detections) == 1
    assert detections[0].entry.external_id is not None
    assert "first.js" in detections[0].evidence
    assert "second.js" in detections[0].evidence
    assert "Добавлено: 1 · заменено: 1" in detections[0].evidence


@pytest.mark.asyncio
async def test_source_state_survives_repository_reopen(tmp_path: Path) -> None:
    path = tmp_path / "changelog.db"
    repository = Repository(path)
    await repository.initialize()
    await repository.set_source_state("web", "assets", json.dumps({"fingerprint": "abc"}))

    reopened = Repository(path)
    await reopened.initialize()

    assert await reopened.get_source_state("web", "assets") == '{"fingerprint": "abc"}'
