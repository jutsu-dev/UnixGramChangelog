from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ChangeKind(StrEnum):
    FEATURE = "feature"
    INTERFACE = "interface"
    FIX = "fix"
    TECHNICAL = "technical"
    EXPERIMENT = "experiment"
    DISCOVERY = "discovery"
    API = "api"
    CLIENT = "client"
    IMPORTANT = "important"


class EntryStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    REJECTED = "rejected"


class SourceMode(StrEnum):
    REVIEW = "review"
    AUTO = "auto"


@dataclass(slots=True, frozen=True)
class SourceRecord:
    slug: str
    name: str
    url: str | None = None
    notes: str | None = None
    mode: SourceMode = SourceMode.REVIEW
    enabled: bool = True
    default_kind: ChangeKind | None = None
    confidence_threshold: float = 0.9
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True, frozen=True)
class ChangeEntry:
    title: str
    summary: str
    kind: ChangeKind
    source_name: str
    source_url: str | None = None
    archive_label: str | None = None
    archive_url: str | None = None
    changed_files: tuple[str, ...] = ()
    evidence: str | None = None
    version: str | None = None
    occurred_at: datetime | None = None
    external_id: str | None = None
    tags: tuple[str, ...] = ()
    source_slug: str | None = None
    id: int | None = None
    status: EntryStatus = EntryStatus.DRAFT
    published_message_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
