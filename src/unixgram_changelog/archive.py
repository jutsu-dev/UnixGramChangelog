from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import UTC
from html import escape

import aiohttp

from .models import ChangeEntry


@dataclass(slots=True, frozen=True)
class ArchiveSettings:
    repository: str
    branch: str
    directory: str
    token: str | None = None

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repository}"


class GitHubArchive:
    def __init__(self, settings: ArchiveSettings) -> None:
        self.settings = settings

    async def archive(self, entry: ChangeEntry) -> ChangeEntry:
        if entry.external_id is None:
            return self._fallback(entry)
        if not self.settings.token:
            return self._fallback(entry)

        path = self._entry_path(entry)
        payload = {
            "message": f"archive: {entry.source_slug or 'change'} {entry.external_id[:12]}",
            "content": base64.b64encode(self._entry_body(entry).encode("utf-8")).decode("ascii"),
            "branch": self.settings.branch,
        }
        api_url = (
            f"https://api.github.com/repos/{self.settings.repository}/contents/{path}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.settings.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20.0),
            headers=headers,
        ) as session:
            async with session.get(
                api_url,
                params={"ref": self.settings.branch},
            ) as response:
                if response.status == 200:
                    existing = await response.json()
                    payload["sha"] = str(existing["sha"])
                elif response.status != 404:
                    response.raise_for_status()

            async with session.put(api_url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()

        commit_sha = str(result["commit"]["sha"])
        return replace(
            entry,
            archive_label=f"{self.settings.repository}@{commit_sha[:7]}",
            archive_url=str(result["content"]["html_url"]),
        )

    def _fallback(self, entry: ChangeEntry) -> ChangeEntry:
        return replace(
            entry,
            archive_label=self.settings.repository,
            archive_url=self.settings.repo_url,
        )

    def _entry_path(self, entry: ChangeEntry) -> str:
        moment = (entry.occurred_at or entry.created_at).astimezone(UTC)
        slug = entry.source_slug or "change"
        digest = (entry.external_id or "manual").split(":", maxsplit=1)[-1][:12]
        return (
            f"{self.settings.directory}/{moment:%Y/%m/%d}/"
            f"{slug}-{digest}.md"
        )

    def _entry_body(self, entry: ChangeEntry) -> str:
        moment = (entry.occurred_at or entry.created_at).astimezone(UTC)
        lines = [
            f"# {entry.title}",
            "",
            f"- Kind: {entry.kind.value}",
            f"- Source: {entry.source_name}",
            f"- Source URL: {entry.source_url or 'n/a'}",
            f"- External ID: {entry.external_id or 'n/a'}",
            f"- Detected at: {moment.isoformat()}",
        ]
        if entry.version:
            lines.append(f"- Version: {entry.version}")
        if entry.tags:
            lines.append(f"- Tags: {', '.join(entry.tags)}")
        lines.extend(("", "## Summary", "", entry.summary))
        if entry.changed_files:
            lines.extend(("", "## Changed files", ""))
            lines.extend(f"- {item}" for item in entry.changed_files)
        if entry.evidence:
            lines.extend(("", "## Evidence", "", entry.evidence))
        return "\n".join(lines) + "\n"


def render_archive_label(label: str | None) -> str | None:
    if not label:
        return None
    return escape(label)
