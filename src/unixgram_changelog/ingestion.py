from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import ChangeEntry, EntryStatus, SourceMode
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
        review_required: bool = True,
    ) -> None:
        self.repository = repository
        self.sources = sources
        self.publisher = publisher
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
            try:
                detections = await source.collect()
            except Exception:
                logger.exception("Source collection failed: %s", source.name)
                source_failures.append(source.name)
                continue

            source_record = source_map.get(source.slug)
            for detection in detections:
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
                    detection.entry,
                    EntryStatus.REVIEW if status is EntryStatus.PUBLISHED else status,
                )
                if saved is None:
                    duplicates += 1
                    continue
                accepted.append(saved)
                if status is EntryStatus.PUBLISHED and self.publisher is not None:
                    await self.publisher.publish(saved)

        return CollectReport(
            accepted=tuple(accepted),
            duplicates=duplicates,
            source_failures=tuple(source_failures),
        )
