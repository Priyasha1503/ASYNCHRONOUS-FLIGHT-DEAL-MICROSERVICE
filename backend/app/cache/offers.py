"""Shared, cross-user cache of provider results with single-flight request coalescing.

Key:   offers:{provider}:{query.cache_key()}    value: JSON ProviderResult, TTL = search_cache_ttl_s
Lock:  lock:offers:{provider}:{query hash}       SET NX PX, value = random token

Single-flight: the first caller to take the lock calls the provider and fills the cache; concurrent
callers wait (polling the value key) for at most the lock TTL. The lock is released with an atomic
compare-and-delete, so a slow winner can't delete a lock that already expired and was re-taken.
A crashed winner simply lets the lock expire; the next waiter then takes it and calls the provider.

Every method raises `CacheUnavailable` on Redis errors so the caller can degrade explicitly.
"""

import logging
import secrets
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import redis
from pydantic import BaseModel, TypeAdapter

from app.core.metrics import CACHE_EVENTS
from app.core.redis import is_down, mark_down
from app.domain.offers import Offer

log = logging.getLogger(__name__)

_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end
"""


class CacheUnavailable(Exception):
    pass


class CachedResult(BaseModel):
    provider: str
    offers: list[Offer]
    fetched_at: datetime
    latency_ms: int


_OFFERS = TypeAdapter(CachedResult)


class OfferCache:
    def __init__(
        self,
        client: "redis.Redis",
        *,
        ttl_s: int,
        lock_ttl_ms: int,
        poll_interval_s: float = 0.05,
    ) -> None:
        self.r = client
        self.ttl_s = ttl_s
        self.lock_ttl_ms = lock_ttl_ms
        self.poll_interval_s = poll_interval_s
        self._release = self.r.register_script(_RELEASE)

    @staticmethod
    def key(provider: str, query_key: str) -> str:
        return f"offers:{provider}:{query_key}"

    def get(self, provider: str, query_key: str) -> CachedResult | None:
        raw = self._call(self.r.get, self.key(provider, query_key))
        if raw is None:
            return None
        try:
            return _OFFERS.validate_json(raw)
        except ValueError:
            # Corrupt/old-format entry: treat as a miss and remove it.
            log.warning("discarding unreadable cache entry", extra={"provider": provider})
            self._call(self.r.delete, self.key(provider, query_key))
            return None

    def put(self, result: CachedResult, query_key: str, ttl_s: int | None = None) -> None:
        self._call(
            self.r.set,
            self.key(result.provider, query_key),
            _OFFERS.dump_json(result),
            ex=ttl_s or self.ttl_s,
        )

    def invalidate(self, provider: str, query_key: str) -> None:
        self._call(self.r.delete, self.key(provider, query_key))

    def get_or_fetch(
        self,
        provider: str,
        query_key: str,
        fetch: Callable[[], CachedResult],
        ttl_s: int | None = None,
    ) -> tuple[CachedResult, bool]:
        """Return (result, from_cache). `fetch` runs at most once across all concurrent callers
        sharing this key (per lock period). Provider errors from `fetch` propagate and are *not*
        cached; waiters then compete for the lock and one of them retries."""
        if hit := self.get(provider, query_key):
            CACHE_EVENTS.labels(provider, "hit").inc()
            return hit, True

        lock_key = f"lock:{self.key(provider, query_key)}"
        deadline = time.monotonic() + self.lock_ttl_ms / 1000 + 1.0
        while True:
            token = secrets.token_hex(16)
            if self._call(self.r.set, lock_key, token, nx=True, px=self.lock_ttl_ms):
                try:
                    # Double-check: another winner may have filled it between our GET and SET NX.
                    if hit := self.get(provider, query_key):
                        CACHE_EVENTS.labels(provider, "hit").inc()
                        return hit, True
                    CACHE_EVENTS.labels(provider, "miss").inc()
                    result = fetch()
                    self.put(result, query_key, ttl_s)
                    return result, False
                finally:
                    try:
                        self._release(keys=[lock_key], args=[token])
                    except redis.RedisError:
                        log.warning(
                            "lock release failed; it will expire", extra={"provider": provider}
                        )

            # Someone else is fetching: wait for their result (or for their lock to vanish).
            CACHE_EVENTS.labels(provider, "coalesced").inc()
            while time.monotonic() < deadline:
                time.sleep(self.poll_interval_s)
                if hit := self.get(provider, query_key):
                    return hit, True
                if not self._call(self.r.exists, lock_key):
                    break  # winner failed or crashed → try to become the winner
            else:
                raise TimeoutError("timed out waiting for a concurrent provider call")

    def _call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if is_down(self.r):
            raise CacheUnavailable("redis marked down")
        try:
            return fn(*args, **kwargs)
        except redis.RedisError as exc:
            mark_down(self.r)
            CACHE_EVENTS.labels("-", "unavailable").inc()
            raise CacheUnavailable(str(exc)) from exc
