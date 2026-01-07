from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from ..normalize.transform import canonicalize_record, normalize_relationships
from ..normalize.schema import NormalizedRecord


class ParquetNotAvailable(RuntimeError):
    pass


def _require_pyarrow():
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ParquetNotAvailable(
            "pyarrow is required for Parquet export. Install with: pip install .[parquet]"
        ) from e
    return pa, pq


def write_parquet(records: Iterable[NormalizedRecord], path: Path) -> None:
    """
    Write Parquet file from normalized records. Uses pyarrow if available.
    Records are canonicalized to maintain column ordering deterministically.
    """
    pa, pq = _require_pyarrow()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic ordering
    def _key(r: NormalizedRecord) -> tuple[str, str]:
        return (str(r.get("ocid") or ""), str(r.get("resourceType") or ""))

    sorted_records: List[NormalizedRecord] = sorted(records, key=_key)
    # Canonicalize field order for stable schema
    rows = [canonicalize_record(normalize_relationships(dict(r))) for r in sorted_records]

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
