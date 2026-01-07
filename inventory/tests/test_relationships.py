from __future__ import annotations

import json

from oci_inventory.export.jsonl import write_jsonl


def test_write_jsonl_sorts_relationships(tmp_path) -> None:
    rel_a = {"source_ocid": "ocid1", "relation_type": "USES", "target_ocid": "ocid3"}
    rel_b = {"source_ocid": "ocid1", "relation_type": "DEPENDS_ON", "target_ocid": "ocid2"}
    records = [
        {
            "ocid": "ocid1",
            "resourceType": "TestResource",
            "relationships": [rel_a, rel_b],
        }
    ]

    path = tmp_path / "inventory.jsonl"
    write_jsonl(records, path)

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["relationships"] == [rel_b, rel_a]
