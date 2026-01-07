from __future__ import annotations

from oci_inventory.diff.hash import stable_record_hash


def test_hash_excludes_collected_at() -> None:
    base = {
        "ocid": "ocid1.test.oc1..aaaa",
        "resourceType": "TestResource",
        "displayName": "name",
        "collectedAt": "2024-01-01T00:00:00Z",
        "details": {"k": "v"},
    }
    a = dict(base)
    b = dict(base)
    b["collectedAt"] = "2025-01-01T00:00:00Z"  # only difference

    ha = stable_record_hash(a)
    hb = stable_record_hash(b)
    assert ha == hb, "Hash must be stable when only collectedAt changes"


def test_hash_changes_when_other_fields_change() -> None:
    rec1 = {
        "ocid": "ocid1.test.oc1..aaaa",
        "resourceType": "TestResource",
        "displayName": "name",
        "collectedAt": "2024-01-01T00:00:00Z",
        "details": {"k": "v"},
    }
    rec2 = dict(rec1)
    rec2["details"] = {"k": "changed"}

    h1 = stable_record_hash(rec1)
    h2 = stable_record_hash(rec2)
    assert h1 != h2, "Hash must change when material fields change"