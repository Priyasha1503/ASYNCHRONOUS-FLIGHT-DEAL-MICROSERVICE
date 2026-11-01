"""Search service against real Redis: cache, single-flight, degradation and provider failures."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import redis

from app.cache.offers import CachedResult, OfferCache
from app.core.config import Settings, get_settings
from app.core.redis import get_redis, make_redis
from app.domain.offers import FareSource
from app.domain.query import Preferences, UpstreamQuery
from app.providers.base import ProviderCapabilities, ProviderResult
from app.providers.demo import DemoProvider
from app.providers.errors import ProviderError, ProviderUnavailable
from app.services.search import ProviderState, SearchService
from tests.unit.factories import query


class Counting(DemoProvider):
    """Demo provider that counts calls and can fail the first `fail_times` calls."""

    def __init__(
        self,
        name: str = "demo",
        *,
        latency_ms: int = 0,
        fail_with: type[ProviderError] | None = None,
        fail_times: int = 0,
        source: FareSource = FareSource.DEMO,
    ) -> None:
        super().__init__(latency_ms=latency_ms)
        self.name = name
        self.display_name = name
        self.capabilities = ProviderCapabilities(
            source=source,
            bookable=source is FareSource.LIVE,
            currencies=DemoProvider.capabilities.currencies,
        )
        self.calls = 0
        self._lock = threading.Lock()
        self._fail_with = fail_with
        self._fail_times = fail_times

    def search(self, q: UpstreamQuery) -> ProviderResult:
        with self._lock:
            self.calls += 1
            n = self.calls
        if self._fail_with and n <= self._fail_times:
            raise self._fail_with(self.name, "injected")
        res = super().search(q)
        if self.capabilities.source is not FareSource.DEMO:
            src = self.capabilities.source
            res.offers = [
                o.model_copy(update={"source": src, "provider": self.name}) for o in res.offers
            ]
        return res


def settings(**kw: Any) -> Settings:
    return get_settings().model_copy(update=kw)


def service(*providers: Counting, client: "redis.Redis | None" = None, **kw: Any) -> SearchService:
    return SearchService(list(providers), settings(**kw), redis_client=client or get_redis())


def test_repeat_search_is_a_cache_hit() -> None:
    p = Counting()
    svc = service(p)
    first = svc.search(query(), Preferences())
    second = svc.search(query(), Preferences())
    assert p.calls == 1
    assert first.providers[0].state is ProviderState.OK
    assert second.providers[0].state is ProviderState.CACHED
    assert [s.offer.id for s in first.outcome.ranked] == [s.offer.id for s in second.outcome.ranked]
    # Preferences are applied after retrieval: a different budget still reuses the upstream result.
    svc.search(query(), Preferences(max_stops=0))
    assert p.calls == 1


def test_stampede_is_coalesced_into_one_provider_call() -> None:
    p = Counting(latency_ms=400)
    svc = service(p)
    barrier = threading.Barrier(12)

    def run() -> list[str]:
        barrier.wait()
        return [s.offer.id for s in svc.search(query(), Preferences()).outcome.ranked]

    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda _: run(), range(12)))
    assert p.calls == 1
    assert all(r == results[0] and r for r in results)


def test_cache_entries_expire() -> None:
    cache = OfferCache(get_redis(), ttl_s=2, lock_ttl_ms=2000)
    res = Counting().search(query())
    cache.put(
        CachedResult(provider="demo", offers=res.offers, fetched_at=res.fetched_at, latency_ms=1),
        "k",
    )
    assert cache.get("demo", "k") is not None
    # Milliseconds, not TTL's rounded-down seconds: robust when the machine is busy.
    pttl: int = get_redis().pttl(OfferCache.key("demo", "k"))  # type: ignore[assignment]
    assert 0 < pttl <= 2000
    time.sleep(2.2)
    assert cache.get("demo", "k") is None


def test_failed_fetch_releases_lock_and_is_not_cached() -> None:
    p = Counting(fail_with=ProviderUnavailable, fail_times=99)
    svc = service(p, provider_max_attempts=1)
    r = svc.search(query(), Preferences())
    assert r.providers[0].state is ProviderState.UNAVAILABLE
    assert not get_redis().keys("lock:*") and not get_redis().keys("offers:*")


def test_crashed_winner_lock_expires_and_a_waiter_takes_over() -> None:
    cache = OfferCache(get_redis(), ttl_s=60, lock_ttl_ms=300)
    lock = "lock:" + OfferCache.key("demo", "crash")
    get_redis().set(lock, "dead-worker", px=300)  # simulate a winner that died mid-fetch
    calls = 0

    def fetch() -> CachedResult:
        nonlocal calls
        calls += 1
        res = Counting().search(query())
        return CachedResult(
            provider="demo", offers=res.offers, fetched_at=res.fetched_at, latency_ms=1
        )

    started = time.monotonic()
    result, cached = cache.get_or_fetch("demo", "crash", fetch)
    assert calls == 1 and not cached and result.offers
    assert time.monotonic() - started >= 0.25  # it waited for the stale lock first


def test_redis_down_degrades_to_direct_calls() -> None:
    dead = make_redis("redis://127.0.0.1:6399/0", timeout_s=0.2)
    p = Counting()
    t0 = time.monotonic()
    r = service(p, client=dead).search(query(), Preferences())
    elapsed = time.monotonic() - t0
    assert r.providers[0].state is ProviderState.OK
    assert r.outcome.ranked and r.cache_available is False
    # One failed Redis attempt (+1 quick retry), then Redis is skipped: no multi-second stall.
    assert elapsed < 1.5, elapsed


def test_partial_provider_failure_keeps_other_results() -> None:
    good, bad = Counting("good"), Counting("bad", fail_with=ProviderUnavailable, fail_times=99)
    r = service(good, bad, provider_max_attempts=1).search(query(), Preferences())
    states = {p.provider: p.state for p in r.providers}
    assert states == {"good": ProviderState.OK, "bad": ProviderState.UNAVAILABLE}
    assert r.outcome.ranked
    assert {s.offer.provider for s in r.outcome.ranked} == {"good"}  # only the healthy provider


def test_slow_provider_hits_the_search_deadline() -> None:
    fast, slow = Counting("fast"), Counting("slow", latency_ms=1500)
    t0 = time.monotonic()
    r = service(fast, slow, search_deadline_s=0.5).search(query(), Preferences())
    assert time.monotonic() - t0 < 1.2
    states = {p.provider: p.state for p in r.providers}
    assert states == {"fast": ProviderState.OK, "slow": ProviderState.TIMEOUT}


def test_transient_error_is_retried_once() -> None:
    p = Counting(fail_with=ProviderUnavailable, fail_times=1)
    r = service(p, provider_max_attempts=2).search(query(), Preferences())
    assert p.calls == 2 and r.providers[0].state is ProviderState.OK


def test_permanent_error_is_not_retried() -> None:
    from app.providers.errors import ProviderInvalidResponse

    p = Counting(fail_with=ProviderInvalidResponse, fail_times=99)
    r = service(p, provider_max_attempts=3).search(query(), Preferences())
    assert p.calls == 1 and r.providers[0].state is ProviderState.INVALID_RESPONSE


def test_circuit_opens_after_repeated_failures_and_stops_calling() -> None:
    p = Counting(fail_with=ProviderUnavailable, fail_times=99)
    svc = service(p, provider_max_attempts=1, circuit_failure_threshold=2)
    for d in ("2026-12-10", "2026-12-11"):  # different queries → no cache involvement
        svc.search(query(depart_date=d), Preferences())
    r = svc.search(query(depart_date="2026-12-12"), Preferences())
    assert r.providers[0].state is ProviderState.CIRCUIT_OPEN
    assert p.calls == 2


def test_cached_live_quotes_are_relabelled_cached() -> None:
    p = Counting("live", source=FareSource.LIVE)
    svc = service(p)
    first = svc.search(query(), Preferences())
    second = svc.search(query(), Preferences())
    assert {s.offer.source for s in first.outcome.ranked} == {FareSource.LIVE}
    assert {s.offer.source for s in second.outcome.ranked} == {FareSource.CACHED}


def test_nearby_airports_expand_upstream_queries() -> None:
    svc = service(Counting())
    qs = svc.upstream_queries(query(), include_nearby=True)
    assert {(q.origin, q.destination) for q in qs} == {
        ("LHR", "JFK"),
        ("LHR", "EWR"),
        ("LGW", "JFK"),
        ("LGW", "EWR"),
    }
    r = svc.search(query(), Preferences(), include_nearby=True)
    assert {s.offer.outbound.destination for s in r.outcome.ranked} <= {"JFK", "EWR"}
    assert len(r.upstream_queries) == 4
