from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, runtime_checkable

EnrichDetails = Dict[str, Any]
Relationship = Dict[str, str]


@dataclass(frozen=True)
class EnrichResult:
    details: EnrichDetails
    relationships: List[Relationship]
    enrichStatus: str
    enrichError: str | None


@runtime_checkable
class Enricher(Protocol):
    """
    Enricher contract for a specific resourceType.
    Implementations must not mutate input record in-place.
    """

    resource_type: str

    def enrich(self, record: Dict[str, Any]) -> EnrichResult:
        ...