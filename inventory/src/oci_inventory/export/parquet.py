from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Tuple

from ..logging import get_logger
from ..normalize.schema import NormalizedRecord
from ..normalize.transform import canonicalize_record, normalize_relationships

LOG = get_logger(__name__)


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


def _hash_ocid(ocid: str) -> str:
    if not ocid:
        return "unknown"
    return hashlib.sha1(ocid.encode("utf-8")).hexdigest()[:12]


def _record_debug_label(record: Mapping[str, Any]) -> str:
    resource_type = str(record.get("resourceType") or "Unknown")
    ocid = str(record.get("ocid") or "")
    return f"{resource_type} ocid_sha1={_hash_ocid(ocid)}"


def _make_nullable_type(pa, pa_type: Any) -> Any:
    if pa.types.is_struct(pa_type):
        fields = [pa.field(f.name, _make_nullable_type(pa, f.type), nullable=True, metadata=f.metadata) for f in pa_type]
        return pa.struct(fields)
    if pa.types.is_list(pa_type):
        value_field = pa.field(
            pa_type.value_field.name,
            _make_nullable_type(pa, pa_type.value_type),
            nullable=True,
            metadata=pa_type.value_field.metadata,
        )
        return pa.list_(value_field)
    if pa.types.is_large_list(pa_type):
        value_field = pa.field(
            pa_type.value_field.name,
            _make_nullable_type(pa, pa_type.value_type),
            nullable=True,
            metadata=pa_type.value_field.metadata,
        )
        return pa.large_list(value_field)
    if pa.types.is_map(pa_type):
        key_field = pa.field(
            pa_type.key_field.name,
            _make_nullable_type(pa, pa_type.key_type),
            nullable=False,
            metadata=pa_type.key_field.metadata,
        )
        item_field = pa.field(
            pa_type.item_field.name,
            _make_nullable_type(pa, pa_type.item_type),
            nullable=True,
            metadata=pa_type.item_field.metadata,
        )
        return pa.map_(key_field, item_field, keys_sorted=pa_type.keys_sorted)
    return pa_type


def _make_nullable_schema(pa, schema: Any) -> Any:
    return pa.schema(
        [pa.field(f.name, _make_nullable_type(pa, f.type), nullable=True, metadata=f.metadata) for f in schema]
    )


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
    row_meta: List[Tuple[int, str]] = []
    record_index = 0

    def _flush_rows() -> None:
        nonlocal writer, rows, row_meta
        if not rows:
            return
        try:
            if writer is None:
                table = pa.Table.from_pylist(rows)
                nullable_schema = _make_nullable_schema(pa, table.schema)
                if table.schema != nullable_schema:
                    table = table.cast(nullable_schema, safe=False)
            else:
                table = pa.Table.from_pylist(rows, schema=writer.schema)
        except Exception as exc:
            LOG.error(
                "Parquet batch write failed; attempting to isolate invalid record",
                extra={"step": "export", "phase": "error", "artifact": "parquet", "error": str(exc)},
            )
            schema = writer.schema if writer is not None else None
            for row, meta in zip(rows, row_meta):
                idx, label = meta
                try:
                    if schema is None:
                        pa.Table.from_pylist([row])
                    else:
                        pa.Table.from_pylist([row], schema=schema)
                except Exception as row_exc:
                    LOG.error(
                        "Parquet record failed schema coercion",
                        extra={
                            "step": "export",
                            "phase": "error",
                            "artifact": "parquet",
                            "record_index": idx,
                            "record_hint": label,
                            "error": str(row_exc),
                        },
                    )
                    raise
            LOG.error(
                "Parquet batch failed but no single record isolated",
                extra={"step": "export", "phase": "error", "artifact": "parquet"},
            )
            raise
        if writer is None:
            writer = pq.ParquetWriter(path, table.schema)
        writer.write_table(table)
        rows = []
        row_meta = []

    for rec in iter_records:
        record_index += 1
        sanitized = _sanitize_parquet_row(canonicalize_record(normalize_relationships(dict(rec))))
        rows.append(sanitized)
        row_meta.append((record_index, _record_debug_label(sanitized)))
        if len(rows) >= batch_size:
            _flush_rows()

    if rows:
        _flush_rows()
    elif writer is None:
        table = pa.Table.from_pylist([])
        pq.write_table(table, path)

    if writer is not None:
        writer.close()
