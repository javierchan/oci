from __future__ import annotations

from datetime import datetime
from typing import Any

REDACTED_VALUE = "<redacted>"
SENSITIVE_KEY_SUBSTRINGS = (
    "private_key",
    "passphrase",
    "password",
    "secret",
    "token",
    "ssh",
    "content",
)


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_KEY_SUBSTRINGS)


def sanitize_for_json(value: Any) -> Any:
    """
    Convert common non-JSON types to serializable forms and redact sensitive fields.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                out[k] = REDACTED_VALUE
            else:
                out[k] = sanitize_for_json(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return sanitize_for_json(to_dict())
        except Exception:
            return str(value)
    attribute_map = getattr(value, "attribute_map", None)
    swagger_types = getattr(value, "swagger_types", None)
    if isinstance(attribute_map, dict):
        out = {}
        for attr, json_key in attribute_map.items():
            if _is_sensitive_key(json_key):
                out[json_key] = REDACTED_VALUE
                continue
            out[json_key] = sanitize_for_json(getattr(value, attr, None))
        return out
    if isinstance(swagger_types, dict):
        out = {}
        for attr in swagger_types.keys():
            if _is_sensitive_key(attr):
                out[attr] = REDACTED_VALUE
                continue
            out[attr] = sanitize_for_json(getattr(value, attr, None))
        return out
    if hasattr(value, "__dict__"):
        return sanitize_for_json(vars(value))
    return value
