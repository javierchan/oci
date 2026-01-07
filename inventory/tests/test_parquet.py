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
