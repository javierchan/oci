from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional

from ..normalize.schema import NormalizedRecord
from ..normalize.transform import canonicalize_record, normalize_relationships


def _drop_empty_structs(value: object) -> object:
    if isinstance(value, dict):
        if not value:
            return None
        return {k: _drop_empty_structs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_drop_empty_structs(v) for v in value]
    return value


def _sanitize_parquet_row(record: NormalizedRecord) -> NormalizedRecord:
    return {k: _drop_empty_structs(v) for k, v in record.items()}


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


def write_parquet(
    records: Iterable[NormalizedRecord],
    path: Path,
    *,
    already_sorted: bool = False,
    batch_size: int = 1000,
) -> None:
    """
    Write Parquet file from normalized records. Uses pyarrow if available.
    Records are canonicalized to maintain column ordering deterministically.
    When already_sorted=True, records are streamed in batches without sorting in memory.
    """
    pa, pq = _require_pyarrow()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic ordering
    def _key(r: NormalizedRecord) -> tuple[str, str]:
        return (str(r.get("ocid") or ""), str(r.get("resourceType") or ""))

    if batch_size < 1:
        batch_size = 1000

    if already_sorted:
        iter_records: Iterable[NormalizedRecord] = records
    else:
        iter_records = sorted(records, key=_key)

    writer: Optional[Any] = None
    rows: List[NormalizedRecord] = []

    def _flush_rows() -> None:
        nonlocal writer, rows
        if not rows:
            return
        table = pa.Table.from_pylist(rows) if writer is None else pa.Table.from_pylist(rows, schema=writer.schema)
        if writer is None:
            writer = pq.ParquetWriter(path, table.schema)
        writer.write_table(table)
        rows = []

    for rec in iter_records:
        rows.append(_sanitize_parquet_row(canonicalize_record(normalize_relationships(dict(rec)))))
        if len(rows) >= batch_size:
            _flush_rows()

    if rows:
        _flush_rows()
    elif writer is None:
        table = pa.Table.from_pylist([])
        pq.write_table(table, path)

    if writer is not None:
        writer.close()
