from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from .models import ChangeEntry, ChangeKind, EntryStatus, SourceMode, SourceRecord


def entry_fingerprint(entry: ChangeEntry) -> str:
    normalized = "\x1f".join(
        (
            entry.kind.value,
            entry.title.strip().casefold(),
            entry.summary.strip().casefold(),
            (entry.source_url or entry.source_name).strip().casefold(),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    external_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT,
                    source_slug TEXT,
                    evidence TEXT,
                    version TEXT,
                    occurred_at TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    published_message_id INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT,
                    notes TEXT,
                    mode TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    default_kind TEXT,
                    confidence_threshold REAL NOT NULL DEFAULT 0.9,
                    created_at TEXT NOT NULL
                );
                """
            )
            await self._migrate_entries_table(db)
            await db.commit()

    async def _migrate_entries_table(self, db: aiosqlite.Connection) -> None:
        rows = await db.execute_fetchall("PRAGMA table_info(entries)")
        columns = {row[1] for row in rows}
        migrations = {
            "source_slug": "ALTER TABLE entries ADD COLUMN source_slug TEXT",
            "evidence": "ALTER TABLE entries ADD COLUMN evidence TEXT",
            "tags_json": "ALTER TABLE entries ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'",
        }
        for column, statement in migrations.items():
            if column not in columns:
                await db.execute(statement)

    async def add(
        self,
        entry: ChangeEntry,
        status: EntryStatus = EntryStatus.REVIEW,
    ) -> ChangeEntry | None:
        fingerprint = entry_fingerprint(entry)
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO entries
                (
                    fingerprint,
                    external_id,
                    title,
                    summary,
                    kind,
                    source_name,
                    source_url,
                    source_slug,
                    evidence,
                    version,
                    occurred_at,
                    tags_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    entry.external_id,
                    entry.title,
                    entry.summary,
                    entry.kind.value,
                    entry.source_name,
                    entry.source_url,
                    entry.source_slug,
                    entry.evidence,
                    entry.version,
                    entry.occurred_at.isoformat() if entry.occurred_at else None,
                    json.dumps(list(entry.tags), ensure_ascii=True),
                    status.value,
                    entry.created_at.astimezone(UTC).isoformat(),
                ),
            )
            await db.commit()
            if cursor.rowcount == 0:
                return None
            return replace(entry, id=cursor.lastrowid, status=status)

    async def get(self, entry_id: int) -> ChangeEntry | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = list(
                await db.execute_fetchall("SELECT * FROM entries WHERE id = ?", (entry_id,))
            )
        return self._entry_from_row(rows[0]) if rows else None

    async def list_by_status(self, status: EntryStatus, limit: int = 20) -> list[ChangeEntry]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM entries WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status.value, limit),
            )
        return [self._entry_from_row(row) for row in rows]

    async def mark(
        self,
        entry_id: int,
        status: EntryStatus,
        message_id: int | None = None,
    ) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "UPDATE entries SET status = ?, published_message_id = ? WHERE id = ?",
                (status.value, message_id, entry_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def save_source(self, source: SourceRecord) -> SourceRecord:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO sources
                (
                    slug, name, url, notes, mode, enabled,
                    default_kind, confidence_threshold, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    notes = excluded.notes,
                    mode = excluded.mode,
                    enabled = excluded.enabled,
                    default_kind = excluded.default_kind,
                    confidence_threshold = excluded.confidence_threshold
                """,
                (
                    source.slug,
                    source.name,
                    source.url,
                    source.notes,
                    source.mode.value,
                    1 if source.enabled else 0,
                    source.default_kind.value if source.default_kind else None,
                    source.confidence_threshold,
                    source.created_at.astimezone(UTC).isoformat(),
                ),
            )
            await db.commit()
        return source

    async def list_sources(self, enabled_only: bool = False) -> list[SourceRecord]:
        query = "SELECT * FROM sources"
        params: tuple[object, ...] = ()
        if enabled_only:
            query += " WHERE enabled = ?"
            params = (1,)
        query += " ORDER BY slug ASC"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(query, params)
        return [self._source_from_row(row) for row in rows]

    async def get_source(self, slug: str) -> SourceRecord | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            rows = list(
                await db.execute_fetchall("SELECT * FROM sources WHERE slug = ?", (slug,))
            )
        return self._source_from_row(rows[0]) if rows else None

    @staticmethod
    def _entry_from_row(row: aiosqlite.Row) -> ChangeEntry:
        tags_raw = row["tags_json"] if "tags_json" in row.keys() else "[]"
        return ChangeEntry(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            kind=ChangeKind(row["kind"]),
            source_name=row["source_name"],
            source_url=row["source_url"],
            source_slug=row["source_slug"] if "source_slug" in row.keys() else None,
            evidence=row["evidence"] if "evidence" in row.keys() else None,
            version=row["version"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]) if row["occurred_at"] else None,
            external_id=row["external_id"],
            tags=tuple(json.loads(tags_raw)),
            status=EntryStatus(row["status"]),
            published_message_id=row["published_message_id"],
            created_at=datetime.fromisoformat(row["created_at"]).astimezone(UTC),
        )

    @staticmethod
    def _source_from_row(row: aiosqlite.Row) -> SourceRecord:
        default_kind = row["default_kind"]
        return SourceRecord(
            slug=row["slug"],
            name=row["name"],
            url=row["url"],
            notes=row["notes"],
            mode=SourceMode(row["mode"]),
            enabled=bool(row["enabled"]),
            default_kind=ChangeKind(default_kind) if default_kind else None,
            confidence_threshold=float(row["confidence_threshold"]),
            created_at=datetime.fromisoformat(row["created_at"]).astimezone(UTC),
        )
