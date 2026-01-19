from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from oci_inventory.util.serialization import REDACTED_VALUE, sanitize_for_json
from oci_inventory.logging import JsonFormatter


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


def test_json_formatter_skips_non_serializable_extras() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="unit",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.good = {"a": 1, "b": [1, 2]}
    record.bad = {"obj": object()}

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "hello"
    assert payload["good"] == {"a": 1, "b": [1, 2]}
    assert "bad" not in payload
