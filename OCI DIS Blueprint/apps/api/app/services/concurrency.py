"""Shared optimistic-concurrency checks for collaborative App resources."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException


def _as_utc(value: datetime) -> datetime:
    """Normalize database and request timestamps before exact comparison."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assert_current_version(
    *,
    current_updated_at: datetime,
    expected_updated_at: datetime,
    entity_type: str,
    entity_id: str,
) -> None:
    """Reject a stale mutation instead of silently overwriting another writer."""

    current = _as_utc(current_updated_at)
    expected = _as_utc(expected_updated_at)
    if current == expected:
        return
    raise HTTPException(
        status_code=409,
        detail={
            "detail": (
                f"The {entity_type} changed after this view was loaded. "
                "Reload the latest version and review the conflicting changes before saving again."
            ),
            "error_code": "STALE_WRITE_CONFLICT",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "expected_updated_at": expected.isoformat(),
            "current_updated_at": current.isoformat(),
        },
    )
