from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from ..normalize.schema import NormalizedRecord
from ..normalize.transform import canonicalize_record, normalize_relationships, stable_json_dumps


def write_jsonl(records: Iterable[NormalizedRecord], path: Path) -> None:
    """
    Write records to a JSONL file with stable key ordering and deterministic line order.
    Ordering: sort by ocid, then resourceType.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic ordering
    def _key(r: NormalizedRecord) -> tuple[str, str]:
        return (str(r.get("ocid") or ""), str(r.get("resourceType") or ""))

    sorted_records: List[NormalizedRecord] = sorted(records, key=_key)

    with path.open("w", encoding="utf-8") as f:
        for rec in sorted_records:
            obj = canonicalize_record(normalize_relationships(dict(rec)))
            f.write(stable_json_dumps(obj))
            f.write("\n")
