"""Reusable wire-level schema primitives."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, TypeAlias

from pydantic import BeforeValidator


def _parse_iso_datetime(value: object) -> object:
    """Accept the ISO-8601 representation returned by this API in strict models."""

    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


ApiTimestamp: TypeAlias = Annotated[datetime, BeforeValidator(_parse_iso_datetime)]
