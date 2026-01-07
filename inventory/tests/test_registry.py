from __future__ import annotations

from typing import Any, Dict

from oci_inventory.enrich import get_enricher_for, register_enricher
from oci_inventory.enrich.base import EnrichResult


class _DummyEnricher:
    resource_type = "unit:Dummy"

    def enrich(self, record: Dict[str, Any]) -> EnrichResult:  # type: ignore[override]
        return EnrichResult(
            details={"dummy": True},
            relationships=[],
            enrichStatus="OK",
            enrichError=None,
        )


def test_registry_returns_default_when_not_registered() -> None:
    enricher = get_enricher_for("unit:NotRegistered")
    res = enricher.enrich({"searchSummary": {"x": 1}})
    assert res.enrichStatus == "NOT_IMPLEMENTED"
    assert res.enrichError is None
    assert "searchSummary" in res.details
    assert res.relationships == []


def test_registry_returns_specific_when_registered() -> None:
    register_enricher("unit:Dummy", _DummyEnricher)  # type: ignore[arg-type]
    enricher = get_enricher_for("unit:Dummy")
    res = enricher.enrich({})
    assert res.enrichStatus == "OK"
    assert res.details.get("dummy") is True
    assert res.relationships == []