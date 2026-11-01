"""Provider failure isolation: a Redis-shared circuit breaker and bounded retries with jitter."""

import logging
import random
import time
from collections.abc import Callable

import redis

from app.core.redis import is_down, mark_down
from app.providers.errors import ProviderError, ProviderRateLimited

log = logging.getLogger(__name__)


class CircuitBreaker:
    """Per-provider breaker shared by every API replica and worker.

    closed → `threshold` failures within `window_s` → open for `cooldown_s` (calls short-circuit)
    → half-open: the next call goes through; failure re-opens immediately, success closes.
    Redis problems never block calls (the breaker fails open — it's an optimisation, not a gate).
    """

    def __init__(
        self, client: "redis.Redis | None", *, threshold: int, window_s: int, cooldown_s: int
    ) -> None:
        self.r = client
        self.threshold = threshold
        self.window_s = window_s
        self.cooldown_s = cooldown_s

    def _keys(self, provider: str) -> tuple[str, str, str]:
        return f"cb:{provider}:failures", f"cb:{provider}:open", f"cb:{provider}:tripped"

    def _usable(self) -> bool:
        return self.r is not None and not is_down(self.r)

    def _failed(self, provider: str) -> None:
        assert self.r is not None
        mark_down(self.r)
        log.warning("circuit breaker unavailable", extra={"provider": provider})

    def is_open(self, provider: str) -> bool:
        if not self._usable():
            return False
        assert self.r is not None
        try:
            return bool(self.r.exists(self._keys(provider)[1]))
        except redis.RedisError:
            self._failed(provider)
            return False

    def record_success(self, provider: str) -> None:
        if not self._usable():
            return
        assert self.r is not None
        failures, _, tripped = self._keys(provider)
        try:
            self.r.delete(failures, tripped)
        except redis.RedisError:
            self._failed(provider)

    def record_failure(self, provider: str) -> None:
        if not self._usable():
            return
        assert self.r is not None
        failures, _, tripped = self._keys(provider)
        try:
            if self.r.exists(tripped):  # half-open probe failed → straight back to open
                self._open(provider)
                return
            pipe = self.r.pipeline()
            pipe.incr(failures)
            pipe.expire(failures, self.window_s, nx=True)
            count, _ = pipe.execute()
            if int(count) >= self.threshold:
                self._open(provider)
        except redis.RedisError:
            self._failed(provider)

    def _open(self, provider: str) -> None:
        assert self.r is not None
        failures, open_, tripped = self._keys(provider)
        pipe = self.r.pipeline()
        pipe.set(open_, "1", ex=self.cooldown_s)
        pipe.set(tripped, "1", ex=self.cooldown_s * 4)
        pipe.delete(failures)
        pipe.execute()
        log.warning("circuit opened", extra={"provider": provider, "cooldown_s": self.cooldown_s})


def call_with_retries[T](
    fn: Callable[[], T],
    *,
    attempts: int,
    deadline: float,
    base_delay_s: float = 0.2,
    max_delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    """Retry only `retryable` ProviderErrors, with exponential backoff and full jitter, never past
    `deadline` (a time.monotonic() value). Permanent errors are raised immediately."""
    rng = rng or random.Random()  # noqa: S311 — jitter, not security
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except ProviderError as exc:
            if not exc.retryable or attempt == attempts:
                raise
            delay = rng.uniform(0, min(max_delay_s, base_delay_s * 2 ** (attempt - 1)))
            if isinstance(exc, ProviderRateLimited) and exc.retry_after_s:
                delay = max(delay, exc.retry_after_s)
            if time.monotonic() + delay >= deadline:
                raise  # not enough time left to retry meaningfully
            log.info(
                "retrying provider call",
                extra={"provider": exc.provider, "attempt": attempt, "error_code": exc.code},
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
