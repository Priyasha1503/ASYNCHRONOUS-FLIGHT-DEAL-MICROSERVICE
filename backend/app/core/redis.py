"""Redis client + fast-fail outage handling.

Redis is an accelerator (cache, locks, rate limits, breaker), never the system of record, so an
outage must degrade features *quickly* rather than stall requests. Two measures:

1. The client retries at most once with a tiny backoff (redis-py 6's default retry policy turned a
   single call against a dead server into ~5.6 s, measured 2026-10-29).
2. After a failure, callers consult `is_down()` and skip Redis for `DOWN_BACKOFF_S` instead of
   paying the connect timeout on every call. Tracked per client object, so a test client pointing
   at a dead port doesn't affect the real one.
"""

import time
import weakref
from functools import lru_cache

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import get_settings

DOWN_BACKOFF_S = 5.0
_down_until: "weakref.WeakKeyDictionary[redis.Redis, float]" = weakref.WeakKeyDictionary()


def make_redis(url: str, timeout_s: float) -> "redis.Redis":
    return redis.Redis.from_url(
        url,
        socket_timeout=timeout_s,
        socket_connect_timeout=timeout_s,
        retry=Retry(ExponentialBackoff(cap=0.1, base=0.02), retries=1),
        decode_responses=True,
    )


@lru_cache
def get_redis() -> "redis.Redis":
    s = get_settings()
    return make_redis(str(s.redis_url), s.redis_socket_timeout_s)


def is_down(client: "redis.Redis") -> bool:
    until = _down_until.get(client)
    return until is not None and time.monotonic() < until


def mark_down(client: "redis.Redis") -> None:
    _down_until[client] = time.monotonic() + DOWN_BACKOFF_S


def mark_up(client: "redis.Redis") -> None:
    _down_until.pop(client, None)


def ping_redis() -> None:
    """Readiness probe: always really pings (so recovery is noticed), and updates the memo."""
    client = get_redis()
    try:
        client.ping()
    except redis.RedisError:
        mark_down(client)
        raise
    mark_up(client)
