from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

from ..normalize.schema import NormalizedRecord
from ..normalize.transform import report_rows


def write_csv(records: Iterable[NormalizedRecord], path: Path) -> None:
    """
    Write a CSV file with report fields only. Deterministic row order by ocid, then resourceType.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic ordering
    def _key(r: NormalizedRecord) -> tuple[str, str]:
        return (str(r.get("ocid") or ""), str(r.get("resourceType") or ""))

    sorted_records: List[NormalizedRecord] = sorted(records, key=_key)
    rows = report_rows(sorted_records)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)