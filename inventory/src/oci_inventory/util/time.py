from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso(seconds: bool = True) -> str:
    """
    Return current UTC time in ISO-8601 format.
    - If seconds is True, use seconds precision (stable strings).
    - Else, use milliseconds precision.
    """
    if seconds:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")