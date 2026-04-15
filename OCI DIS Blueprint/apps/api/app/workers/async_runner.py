"""Async execution helper for Celery worker processes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async(awaitable: Awaitable[T]) -> T:
    """Run async worker logic on a persistent event loop per Celery process."""

    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(awaitable)
