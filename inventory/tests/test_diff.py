from __future__ import annotations

from typing import Any, Dict, List

from oci_inventory.diff.diff import compute_diff


def test_compute_diff_added_removed_changed_unchanged() -> None:
    prev: List[Dict[str, Any]] = [
        {"ocid": "ocid1", "resourceType": "X", "collectedAt": "2024-01-01T00:00:00Z", "details": {"a": 1}},
        {"ocid": "ocid2", "resourceType": "Y", "collectedAt": "2024-01-01T00:00:00Z", "details": {"b": 2}},
    ]
    curr: List[Dict[str, Any]] = [
        # ocid1 changed details
        {"ocid": "ocid1", "resourceType": "X", "collectedAt": "2025-01-01T00:00:00Z", "details": {"a": 2}},
        # ocid2 unchanged (collectedAt excluded from hash)
        {"ocid": "ocid2", "resourceType": "Y", "collectedAt": "2025-01-01T00:00:00Z", "details": {"b": 2}},
        # ocid3 added
        {"ocid": "ocid3", "resourceType": "Z", "collectedAt": "2025-01-01T00:00:00Z", "details": {"c": 3}},
    ]

    d = compute_diff(prev, curr)
    assert d["added"] == ["ocid3"]
    assert d["removed"] == []
    assert d["changed"] == ["ocid1"]
    assert d["unchanged"] == ["ocid2"]

    summary = d["summary"]
    assert summary["added"] == 1
    assert summary["removed"] == 0
    assert summary["changed"] == 1
    assert summary["unchanged"] == 1
    assert summary["prev_total"] == 2
    assert summary["curr_total"] == 3