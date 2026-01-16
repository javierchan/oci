from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

from ..normalize.schema import CSV_REPORT_FIELDS, NormalizedRecord


def write_csv(records: Iterable[NormalizedRecord], path: Path, *, already_sorted: bool = False) -> None:
    """
    Write a CSV file with report fields only. Deterministic row order by ocid, then resourceType.
    When already_sorted=True, records are streamed without additional sorting.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic ordering
    def _key(r: NormalizedRecord) -> tuple[str, str]:
        return (str(r.get("ocid") or ""), str(r.get("resourceType") or ""))

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_REPORT_FIELDS)
        if already_sorted:
            iter_records: Iterable[NormalizedRecord] = records
        else:
            iter_records = sorted(records, key=_key)
        for rec in iter_records:
            row: List[str] = []
            for field in CSV_REPORT_FIELDS:
                val = rec.get(field)
                if val is None:
                    row.append("unknown")
                    continue
                text = str(val)
                row.append("unknown" if not text.strip() else text)
            writer.writerow(row)
