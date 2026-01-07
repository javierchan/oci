from __future__ import annotations

import types

import pytest

from oci_inventory.auth import providers as auth_providers
from oci_inventory.util.errors import OCIClientError


class DummyOciError(Exception):
    __module__ = "oci.exceptions"


def test_resolve_auth_maps_oci_errors(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise DummyOciError("boom")

    dummy_oci = types.SimpleNamespace(config=types.SimpleNamespace(from_file=_raise))
    monkeypatch.setattr(auth_providers, "oci", dummy_oci)

    with pytest.raises(OCIClientError):
        auth_providers.resolve_auth("config", profile=None, tenancy_ocid=None)
