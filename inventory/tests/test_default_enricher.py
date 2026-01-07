from __future__ import annotations

from typing import Any, Dict

from oci_inventory.enrich.default import DefaultEnricher


def test_default_enricher_returns_not_implemented_and_preserves_search_summary() -> None:
    enricher = DefaultEnricher()
    record: Dict[str, Any] = {
        "ocid": "ocid1.test.oc1..aaaa",
        "resourceType": "anything",
        "searchSummary": {"identifier": "ocid1.test.oc1..aaaa", "resource_type": "anything"},
    }

    res = enricher.enrich(dict(record))  # pass a copy

    assert res.enrichStatus == "NOT_IMPLEMENTED"
    assert res.enrichError is None
    assert isinstance(res.details, dict)
    assert "searchSummary" in res.details
    assert res.details["searchSummary"] == record["searchSummary"]
    assert res.relationships == []