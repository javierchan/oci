"""Redis-backed leases for horizontally scaled scheduled task consumers."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from collections.abc import Iterator

import redis


_RELEASE_IF_OWNER = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


@contextmanager
def scheduled_task_lease(redis_url: str, key: str, ttl_seconds: int) -> Iterator[bool]:
    """Yield whether this worker owns the bounded lease and release only its token."""

    token = str(uuid.uuid4())
    client = redis.from_url(redis_url, decode_responses=True)
    acquired = bool(client.set(key, token, nx=True, ex=ttl_seconds))
    try:
        yield acquired
    finally:
        if acquired:
            client.eval(_RELEASE_IF_OWNER, 1, key, token)
        client.close()
