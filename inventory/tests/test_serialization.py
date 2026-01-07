from __future__ import annotations

from datetime import datetime, timezone

from oci_inventory.util.serialization import REDACTED_VALUE, sanitize_for_json


def test_sanitize_for_json_redacts_sensitive_fields() -> None:
    payload = {
        "password": "secret",
        "tokenValue": "abc",
        "nested": {"ssh_key": "ssh-rsa AAA", "safe": 1},
    }

    sanitized = sanitize_for_json(payload)

    assert sanitized["password"] == REDACTED_VALUE
    assert sanitized["tokenValue"] == REDACTED_VALUE
    assert sanitized["nested"]["ssh_key"] == REDACTED_VALUE
    assert sanitized["nested"]["safe"] == 1


def test_sanitize_for_json_handles_datetime_and_bytes() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    payload = {"when": ts, "blob": b"bytes"}

    sanitized = sanitize_for_json(payload)

    assert sanitized["when"] == "2024-01-01T00:00:00+00:00"
    assert sanitized["blob"] == "bytes"
