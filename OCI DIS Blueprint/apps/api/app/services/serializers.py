"""Shared coercion and JSON-serialization helpers for API services."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


def sanitize_for_json(value: object) -> object:
    """Convert values into JSON-safe primitives."""

    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return value


def parse_bool(value: object) -> Optional[bool]:
    """Interpret workbook-style truthy values."""

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"si", "sí", "yes", "y", "true", "1"}:
        return True
    if normalized in {"no", "n", "false", "0"}:
        return False
    return None


def parse_float(value: object) -> Optional[float]:
    """Convert a workbook cell to float when possible."""

    if value in (None, ""):
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return None


def parse_int(value: object) -> Optional[int]:
    """Convert a workbook cell to int when possible."""

    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def parse_text(value: object) -> Optional[str]:
    """Convert a workbook cell to a stripped string or ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def split_csv(value: Optional[str]) -> list[str]:
    """Split a comma-separated string into clean values."""

    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
