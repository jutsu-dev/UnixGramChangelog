from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import ChangeEntry


@dataclass(slots=True, frozen=True)
class Detection:
    entry: ChangeEntry
    confidence: float
    evidence: str


class ChangeSource(Protocol):
    slug: str
    name: str

    async def collect(self) -> list[Detection]: ...
