from __future__ import annotations

import pytest

from oci_inventory.export import parquet as parquet_mod


def test_write_parquet_raises_when_pyarrow_missing(monkeypatch, tmp_path) -> None:
    def _raise():
        raise parquet_mod.ParquetNotAvailable("pyarrow is required for Parquet export.")

    monkeypatch.setattr(parquet_mod, "_require_pyarrow", _raise)

    with pytest.raises(parquet_mod.ParquetNotAvailable):
        parquet_mod.write_parquet(
            [{"ocid": "ocid1", "resourceType": "TestResource"}],
            tmp_path / "inventory.parquet",
        )


def test_parquet_sanitizes_empty_structs() -> None:
    record = {
        "ocid": "ocid1",
        "resourceType": "Test",
        "certificates": {},
        "details": {
            "foo": {},
            "bar": [{}, {"k": 1}],
        },
    }
    sanitized = parquet_mod._sanitize_parquet_row(record)
    assert sanitized["certificates"] is None
    assert sanitized["details"]["foo"] is None
    assert sanitized["details"]["bar"][0] is None
    assert sanitized["details"]["bar"][1]["k"] == 1


def test_parquet_record_debug_label_hashes_ocid() -> None:
    record = {"ocid": "ocid1.test.oc1..aaa", "resourceType": "Widget"}
    label = parquet_mod._record_debug_label(record)
    assert "Widget" in label
    assert "ocid1.test.oc1..aaa" not in label
    assert "ocid_sha1=" in label


def test_parquet_skips_rows_when_schema_coercion_fails(tmp_path, monkeypatch) -> None:
    class _FakeTable:
        def __init__(self, rows):
            self.rows = rows
            self.schema = "schema"

        def cast(self, schema, safe=False):
            return self

    class _FakePA:
        class Table:
            @staticmethod
            def from_pylist(rows, schema=None):
                if any(row.get("bad") for row in rows):
                    raise ValueError("Invalid null value")
                return _FakeTable(rows)

    class _FakePQ:
        last_writer = None

        class ParquetWriter:
            def __init__(self, path, schema):
                self.schema = schema
                self.tables = []
                _FakePQ.last_writer = self

            def write_table(self, table):
                self.tables.append(table)

            def close(self):
                return None

        @staticmethod
        def write_table(table, path):
            return None

    monkeypatch.setattr(parquet_mod, "_require_pyarrow", lambda: (_FakePA, _FakePQ))
    monkeypatch.setattr(parquet_mod, "_make_nullable_schema", lambda pa, schema: schema)

    parquet_mod.write_parquet(
        [{"ocid": "ok", "resourceType": "Ok"}, {"ocid": "bad", "resourceType": "Bad", "bad": True}],
        tmp_path / "inventory.parquet",
    )

    assert _FakePQ.last_writer is not None
    assert len(_FakePQ.last_writer.tables) == 1
