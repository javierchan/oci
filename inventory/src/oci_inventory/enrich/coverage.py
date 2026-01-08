from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

from . import is_enricher_registered


@dataclass(frozen=True)
class EnrichCoverage:
    total_records: int
    total_resource_types: int
    registered_resource_types: int
    missing_resource_types: int
    missing_by_count: Dict[str, int]


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def compute_enrichment_coverage(inventory_jsonl: Path) -> EnrichCoverage:
    by_type = Counter()
    total = 0
    for rec in _iter_jsonl(inventory_jsonl):
        total += 1
        rtype = str(rec.get("resourceType") or "").strip()
        if not rtype:
            rtype = "(missing resourceType)"
        by_type[rtype] += 1

    missing: Dict[str, int] = {}
    registered = 0
    for rtype, count in by_type.items():
        if rtype == "(missing resourceType)":
            missing[rtype] = count
            continue
        if is_enricher_registered(rtype):
            registered += 1
        else:
            missing[rtype] = count

    missing_sorted = dict(sorted(missing.items(), key=lambda kv: (-kv[1], kv[0])))
    return EnrichCoverage(
        total_records=total,
        total_resource_types=len(by_type),
        registered_resource_types=registered,
        missing_resource_types=len(missing),
        missing_by_count=missing_sorted,
    )


def top_missing_types(coverage: EnrichCoverage, limit: int = 20) -> list[Tuple[str, int]]:
    if limit <= 0:
        return []
    items = list(coverage.missing_by_count.items())
    return items[:limit]
