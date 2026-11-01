"""Search use case: fan out to providers (cache-first, single-flight, guarded), then run the pure
domain pipeline. Partial failures are reported per provider — never silently dropped."""

import logging
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache

import redis

from app.cache.offers import CachedResult, CacheUnavailable, OfferCache
from app.core.config import Settings
from app.core.metrics import PROVIDER_CALLS, PROVIDER_LATENCY, SEARCHES
from app.domain.airports import nearby
from app.domain.offers import FareSource, Offer
from app.domain.pipeline import SearchOutcome, evaluate
from app.domain.query import Preferences, UpstreamQuery
from app.providers.base import FlightProvider
from app.providers.errors import ProviderError, ProviderRateLimited
from app.services.rate_limit import RateLimiter
from app.services.resilience import CircuitBreaker, call_with_retries

log = logging.getLogger(__name__)

# Shared by all requests in this process; bounded so a burst can't spawn unbounded threads.
_EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix="provider")


class ProviderState(StrEnum):
    OK = "ok"  # fresh provider call
    CACHED = "cached"  # served from shared cache
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


_SUCCESS = {ProviderState.OK, ProviderState.CACHED}


@dataclass(slots=True)
class ProviderStatus:
    provider: str
    display_name: str
    source: FareSource
    bookable: bool
    booking: str  # checkout | redirect | none
    state: ProviderState
    offers: int = 0
    latency_ms: int | None = None
    fetched_at: datetime | None = None  # oldest data contributing to this result
    message: str | None = None


@dataclass(slots=True)
class SearchResult:
    outcome: SearchOutcome
    providers: list[ProviderStatus]
    generated_at: datetime
    cache_available: bool
    upstream_queries: list[str] = field(default_factory=list)

    @property
    def is_demo(self) -> bool:
        return any(o.offer.source is FareSource.DEMO for o in self.outcome.ranked) or any(
            p.source is FareSource.DEMO and p.state in _SUCCESS for p in self.providers
        )


@dataclass(slots=True)
class _Ctx:
    """Per-search state (the service itself is shared across concurrent requests)."""

    deadline: float
    cache_ok: bool = True


@dataclass(slots=True)
class _Fetch:
    state: ProviderState
    result: CachedResult | None = None
    message: str | None = None


class SearchService:
    def __init__(
        self,
        providers: Sequence[FlightProvider],
        settings: Settings,
        *,
        redis_client: "redis.Redis | None",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        executor: ThreadPoolExecutor = _EXECUTOR,
    ) -> None:
        self.providers = list(providers)
        self.s = settings
        self.clock = clock
        self.executor = executor
        lock_ttl_ms = int((settings.provider_timeout_s * settings.provider_max_attempts + 2) * 1000)
        self.cache = (
            OfferCache(redis_client, ttl_s=settings.search_cache_ttl_s, lock_ttl_ms=lock_ttl_ms)
            if redis_client is not None
            else None
        )
        self.breaker = CircuitBreaker(
            redis_client,
            threshold=settings.circuit_failure_threshold,
            window_s=settings.circuit_window_s,
            cooldown_s=settings.circuit_cooldown_s,
        )
        self.limiter = RateLimiter(redis_client) if redis_client is not None else None
        # Process-wide cap on direct provider calls while Redis is unavailable.
        self._no_cache_slots = threading.BoundedSemaphore(settings.no_cache_max_concurrency)

    # ── public ───────────────────────────────────────────────────────────────

    def search(
        self, query: UpstreamQuery, prefs: Preferences, *, include_nearby: bool = False
    ) -> SearchResult:
        ctx = _Ctx(deadline=time.monotonic() + self.s.search_deadline_s)
        upstream = self.upstream_queries(query, include_nearby)

        futures: dict[Future[_Fetch], tuple[FlightProvider, UpstreamQuery]] = {
            self.executor.submit(self._fetch, p, q, ctx): (p, q)
            for p in self.providers
            for q in upstream
        }
        results: dict[str, list[_Fetch]] = {p.name: [] for p in self.providers}
        pending = set(futures)
        while pending:
            remaining = ctx.deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            for f in done:
                provider, _ = futures[f]
                try:
                    results[provider.name].append(f.result())
                except Exception:  # _fetch maps expected errors; this is a bug
                    log.exception("provider task crashed", extra={"provider": provider.name})
                    results[provider.name].append(_Fetch(ProviderState.ERROR, message="internal"))
        for f in pending:  # still running at the deadline; they'll fill the cache when done
            provider, _ = futures[f]
            results[provider.name].append(_Fetch(ProviderState.TIMEOUT, message="search deadline"))

        offers: list[Offer] = []
        statuses: list[ProviderStatus] = []
        for p in self.providers:
            status, provider_offers = self._summarize(p, results[p.name])
            statuses.append(status)
            offers += provider_offers

        outcome = evaluate(query, prefs, offers, include_nearby=include_nearby)
        SEARCHES.labels("results" if outcome.has_results else "empty").inc()
        return SearchResult(
            outcome=outcome,
            providers=statuses,
            generated_at=self.clock(),
            cache_available=ctx.cache_ok and self.cache is not None,
            upstream_queries=[q.cache_key() for q in upstream],
        )

    def upstream_queries(self, query: UpstreamQuery, include_nearby: bool) -> list[UpstreamQuery]:
        if not include_nearby:
            return [query]
        origins = [query.origin, *sorted(nearby(query.origin))]
        dests = [query.destination, *sorted(nearby(query.destination))]
        combos = [(o, d) for o in origins for d in dests][: self.s.max_nearby_combinations]
        return [query.model_copy(update={"origin": o, "destination": d}) for o, d in combos]

    # ── per provider x upstream query ────────────────────────────────────────

    def _fetch(self, provider: FlightProvider, query: UpstreamQuery, ctx: _Ctx) -> _Fetch:
        name = provider.name
        if self.breaker.is_open(name):
            PROVIDER_CALLS.labels(name, "circuit_open").inc()
            return _Fetch(ProviderState.CIRCUIT_OPEN, message="temporarily paused after errors")

        def call() -> CachedResult:
            rpm = provider.capabilities.requests_per_minute
            if rpm and self.limiter and not self.limiter.try_hit(f"provider:{name}", rpm):
                raise ProviderRateLimited(name, "SkyScout's request budget for this provider")
            started = time.perf_counter()
            try:
                res = call_with_retries(
                    lambda: provider.search(query),
                    attempts=self.s.provider_max_attempts,
                    deadline=ctx.deadline,
                )
            except ProviderError as exc:
                PROVIDER_CALLS.labels(name, exc.code).inc()
                if exc.code in {"timeout", "unavailable", "invalid_response", "auth"}:
                    self.breaker.record_failure(name)
                raise
            finally:
                PROVIDER_LATENCY.labels(name).observe(time.perf_counter() - started)
            PROVIDER_CALLS.labels(name, "ok").inc()
            self.breaker.record_success(name)
            return CachedResult(
                provider=name,
                offers=res.offers,
                fetched_at=res.fetched_at,
                latency_ms=res.latency_ms,
            )

        try:
            if self.cache is not None and ctx.cache_ok:
                try:
                    result, cached = self.cache.get_or_fetch(
                        name, query.cache_key(), call, provider.capabilities.cache_ttl_s
                    )
                    return _Fetch(ProviderState.CACHED if cached else ProviderState.OK, result)
                except CacheUnavailable:
                    ctx.cache_ok = False
                    log.warning("offer cache unavailable; calling provider directly")
            return self._fetch_uncached(call, ctx.deadline)
        except ProviderError as exc:
            return _Fetch(_STATE.get(exc.code, ProviderState.ERROR), message=str(exc))
        except TimeoutError:
            return _Fetch(ProviderState.TIMEOUT, message="waited too long for a shared request")
        except Exception:
            log.exception("unexpected provider failure", extra={"provider": name})
            self.breaker.record_failure(name)
            return _Fetch(ProviderState.ERROR, message="unexpected provider error")

    def _fetch_uncached(self, call: Callable[[], CachedResult], deadline: float) -> _Fetch:
        """Redis is down: no cache, no coalescing — so cap concurrent upstream calls instead."""
        if not self._no_cache_slots.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return _Fetch(ProviderState.UNAVAILABLE, message="busy; try again shortly")
        try:
            return _Fetch(ProviderState.OK, call())
        finally:
            self._no_cache_slots.release()

    def _summarize(
        self, provider: FlightProvider, fetches: list[_Fetch]
    ) -> tuple[ProviderStatus, list[Offer]]:
        caps = provider.capabilities
        ok = [f for f in fetches if f.state in _SUCCESS and f.result is not None]
        offers: list[Offer] = []
        for f in ok:
            assert f.result is not None
            if f.state is ProviderState.CACHED:
                # A reused live quote is labelled "cached"; other sources keep their label.
                offers += [
                    o.model_copy(update={"source": FareSource.CACHED})
                    if o.source is FareSource.LIVE
                    else o
                    for o in f.result.offers
                ]
            else:
                offers += f.result.offers

        if ok:
            state = (
                ProviderState.CACHED
                if all(f.state is ProviderState.CACHED for f in ok)
                else ProviderState.OK
            )
            failed = [f for f in fetches if f.state not in _SUCCESS]
            message = f"{len(failed)} of {len(fetches)} route variants failed" if failed else None
            fetched_at = min(f.result.fetched_at for f in ok if f.result)
            latency = max(f.result.latency_ms for f in ok if f.result)
        else:
            first = fetches[0] if fetches else _Fetch(ProviderState.ERROR, message="no result")
            state, message, fetched_at, latency = first.state, first.message, None, None

        return (
            ProviderStatus(
                provider=provider.name,
                display_name=provider.display_name,
                source=caps.source,
                bookable=caps.bookable,
                booking=caps.booking,
                state=state,
                offers=len(offers),
                latency_ms=latency,
                fetched_at=fetched_at,
                message=message,
            ),
            offers,
        )


_STATE = {
    "timeout": ProviderState.TIMEOUT,
    "rate_limited": ProviderState.RATE_LIMITED,
    "unavailable": ProviderState.UNAVAILABLE,
    "invalid_response": ProviderState.INVALID_RESPONSE,
    "unsupported": ProviderState.UNSUPPORTED,
    "auth": ProviderState.ERROR,
}


@lru_cache
def default_search_service() -> SearchService:
    """One per process (API worker or Celery worker): shares providers and the concurrency cap."""
    from app.core.config import get_settings
    from app.core.redis import get_redis
    from app.providers.registry import build_providers

    settings = get_settings()
    return SearchService(build_providers(settings), settings, redis_client=get_redis())
