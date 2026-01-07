from __future__ import annotations

from typing import Any, Dict

from .base import Enricher, EnrichResult


class DefaultEnricher(Enricher):
    """
    Default enricher used for any resourceType without a specific enricher implementation.

    Requirements (Phase 1 MUST):
    - Never call any per-service API.
    - Never raise; always return an EnrichResult.
    - Returns:
        enrichStatus = "NOT_IMPLEMENTED"
        enrichError = None
        details = {"searchSummary": <the Search summary dict>}
        relationships = []
    """

    resource_type: str = "*"

    def enrich(self, record: Dict[str, Any]) -> EnrichResult:  # type: ignore[override]
        # Defensive copying of search summary if present
        search_summary = dict(record.get("searchSummary") or {})
        return EnrichResult(
            details={"searchSummary": search_summary},
            relationships=[],
            enrichStatus="NOT_IMPLEMENTED",
            enrichError=None,
        )