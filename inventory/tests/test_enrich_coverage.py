from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from oci_inventory.enrich import register_enricher
from oci_inventory.enrich.base import EnrichResult
from oci_inventory.enrich.coverage import compute_enrichment_coverage


class _UnitEnricher:
    resource_type = "UnitTypeA"

    def enrich(self, record: Dict[str, Any]) -> EnrichResult:  # type: ignore[override]
        return EnrichResult(details={}, relationships=[], enrichStatus="OK", enrichError=None)


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it))
            f.write("\n")


def test_compute_enrichment_coverage_counts_missing(tmp_path: Path) -> None:
    # Register one unit type; the other should be missing.
    register_enricher("UnitTypeA", _UnitEnricher)  # type: ignore[arg-type]

    p = tmp_path / "inventory.jsonl"
    _write_jsonl(
        p,
        [
            {"resourceType": "UnitTypeA"},
            {"resourceType": "UnitTypeA"},
            {"resourceType": "UnitTypeB"},
        ],
    )

    cov = compute_enrichment_coverage(p)
    assert cov.total_records == 3
    assert cov.total_resource_types == 2
    assert cov.missing_resource_types == 1
    assert cov.missing_by_count == {"UnitTypeB": 1}


def test_compute_enrichment_coverage_handles_missing_resource_type(tmp_path: Path) -> None:
    p = tmp_path / "inventory.jsonl"
    _write_jsonl(p, [{"ocid": "ocid1.test.oc1..aaaa"}])

    cov = compute_enrichment_coverage(p)
    assert cov.total_records == 1
    assert cov.missing_resource_types == 1
    assert cov.missing_by_count == {"(missing resourceType)": 1}
