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
