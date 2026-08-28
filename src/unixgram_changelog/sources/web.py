from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp

from ..models import ChangeEntry, ChangeKind
from ..storage import Repository
from .base import Detection

_ASSET_PATTERN = re.compile(
    r'(?:src|href)=["\']([^"\']+_next/static/[^"\']+\.(?:js|css)(?:\?[^"\']*)?)["\']'
)
_HASHED_ASSET_PATTERN = re.compile(r"^(?P<name>.+)-[0-9a-f]{8,}(?P<ext>\.(?:js|css))$")


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _shape(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _shape(child) for key, child in sorted(value.items())}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_shape(value[0])] if value else []
    if value is None:
        return "null"
    return type(value).__name__


def _display_asset_name(filename: str) -> str:
    match = _HASHED_ASSET_PATTERN.match(filename)
    if not match:
        return filename
    return f"{match.group('name')}{match.group('ext')}"


def _pick_changed_files(added: list[str], removed: list[str]) -> tuple[str, ...]:
    unique: list[str] = []
    for item in (*added[:2], *removed[:2]):
        normalized = _display_asset_name(item)
        if normalized not in unique:
            unique.append(normalized)
    return tuple(unique)


@dataclass(slots=True)
class NextDeploymentSource:
    repository: Repository
    slug: str
    name: str
    base_url: str
    timeout_seconds: float = 12.0

    async def collect(self) -> list[Detection]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.base_url, allow_redirects=True) as response:
                response.raise_for_status()
                html = await response.text()
        if len(html) < 1000 or "_next/static" not in html:
            raise ValueError(f"{self.name} returned an unexpected HTML document")
        assets = sorted({urljoin(self.base_url, match) for match in _ASSET_PATTERN.findall(html)})
        if not assets:
            raise ValueError(f"{self.name} did not expose build assets")
        fingerprint = _digest(assets)
        previous_raw = await self.repository.get_source_state(self.slug, "assets")
        await self.repository.set_source_state(
            self.slug,
            "assets",
            json.dumps({"fingerprint": fingerprint, "assets": assets}, ensure_ascii=True),
        )
        if previous_raw is None:
            return []
        previous = json.loads(previous_raw)
        old_assets = set(previous.get("assets", []))
        if previous.get("fingerprint") == fingerprint:
            return []

        new_assets = set(assets)
        added = [item.rsplit("/", 1)[-1] for item in assets if item not in old_assets]
        removed = [item.rsplit("/", 1)[-1] for item in old_assets if item not in new_assets]
        changed_files = _pick_changed_files(added, removed)
        evidence_lines = [
            f"build {str(previous.get('fingerprint', ''))[:12]} -> {fingerprint[:12]}",
            f"added: {len(added)}",
            f"removed: {len(removed)}",
        ]
        if changed_files:
            evidence_lines.append("files: " + ", ".join(changed_files))
        evidence = "\n".join(evidence_lines)
        entry = ChangeEntry(
            title=f"{self.name}: новая сборка",
            summary=(
                "Обновился набор клиентских ресурсов. Проверяем интерфейс и функции "
                "перед публикацией подробного описания."
            ),
            kind=ChangeKind.TECHNICAL,
            source_name=self.name,
            source_url=self.base_url,
            source_slug=self.slug,
            external_id=f"{self.slug}:{fingerprint}",
            changed_files=changed_files,
            evidence=evidence,
            tags=("deploy", "web"),
        )
        return [Detection(entry=entry, confidence=0.98, evidence=evidence)]


@dataclass(slots=True)
class JsonContractSource:
    repository: Repository
    slug: str
    name: str
    url: str
    timeout_seconds: float = 12.0

    async def collect(self) -> list[Detection]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.url, allow_redirects=True) as response:
                response.raise_for_status()
                if "json" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError(f"{self.name} returned a non-JSON response")
                payload = await response.json()
        shape = _shape(payload)
        fingerprint = _digest(shape)
        previous = await self.repository.get_source_state(self.slug, "contract")
        await self.repository.set_source_state(self.slug, "contract", fingerprint)
        if previous is None or previous == fingerprint:
            return []
        evidence = f"contract {previous[:12]} -> {fingerprint[:12]}"
        entry = ChangeEntry(
            title=f"{self.name}: изменился API-контракт",
            summary="Структура публичного ответа изменилась. Требуется проверить совместимость.",
            kind=ChangeKind.API,
            source_name=self.name,
            source_url=self.url,
            source_slug=self.slug,
            external_id=f"{self.slug}:{fingerprint}",
            evidence=evidence,
            tags=("api", "contract"),
        )
        return [Detection(entry=entry, confidence=0.99, evidence=evidence)]
