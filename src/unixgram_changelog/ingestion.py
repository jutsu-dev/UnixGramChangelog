from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from .archive import GitHubArchive
from .models import ChangeEntry, EntryStatus, SourceMode
from .notifications import AdminNotifier
from .publisher import Publisher
from .sources import ChangeSource
from .storage import Repository

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class CollectReport:
    accepted: tuple[ChangeEntry, ...]
    duplicates: int
    source_failures: tuple[str, ...]


class IngestionService:
    def __init__(
        self,
        repository: Repository,
        sources: list[ChangeSource],
        publisher: Publisher | None = None,
        notifier: AdminNotifier | None = None,
        archiver: GitHubArchive | None = None,
        review_required: bool = True,
    ) -> None:
        self.repository = repository
        self.sources = sources
        self.publisher = publisher
        self.notifier = notifier
        self.archiver = archiver
        self.review_required = review_required

    async def collect(self) -> CollectReport:
        accepted: list[ChangeEntry] = []
        duplicates = 0
        source_failures: list[str] = []
        source_map = {
            source.slug: source
            for source in await self.repository.list_sources()
        }

        for source in self.sources:
            source_record = source_map.get(source.slug)
            if source_record is not None and not source_record.enabled:
                logger.info("Skipping disabled source: %s", source.slug)
                continue
            try:
                detections = await source.collect()
            except Exception:
                logger.exception("Source collection failed: %s", source.name)
                source_failures.append(source.name)
                continue

            for detection in detections:
                entry = detection.entry
                if entry.evidence is None and detection.evidence:
                    entry = replace(entry, evidence=detection.evidence)
                status = EntryStatus.REVIEW
                if (
                    not self.review_required
                    and self.publisher is not None
                    and source_record is not None
                    and source_record.enabled
                    and source_record.mode is SourceMode.AUTO
                    and detection.confidence >= source_record.confidence_threshold
                ):
                    status = EntryStatus.PUBLISHED

                saved = await self.repository.add(
                    entry,
                    EntryStatus.REVIEW if status is EntryStatus.PUBLISHED else status,
                )
                if saved is None:
                    duplicates += 1
                    continue
                if self.archiver is not None:
                    try:
                        saved = await self.archiver.archive(saved)
                        saved = await self.repository.update_render_fields(saved)
                    except Exception:
                        logger.exception(
                            "Archive update failed for source %s entry %s",
                            source.slug,
                            saved.id,
                        )
                accepted.append(saved)
                if status is EntryStatus.PUBLISHED and self.publisher is not None:
                    try:
                        await self.publisher.publish(saved)
                    except Exception:
                        logger.exception(
                            "Auto publish failed for source %s entry %s",
                            source.slug,
                            saved.id,
                        )
                        if self.notifier is not None:
                            await self.notifier.notify_review_entry(
                                saved,
                                heading=(
                                    f"Автопубликация не удалась, проверь вручную: {source.name}"
                                ),
                            )
                elif self.notifier is not None:
                    await self.notifier.notify_review_entry(
                        saved,
                        heading=f"Источник {source.name} прислал новое изменение",
                    )

        return CollectReport(
            accepted=tuple(accepted),
            duplicates=duplicates,
            source_failures=tuple(source_failures),
        )
