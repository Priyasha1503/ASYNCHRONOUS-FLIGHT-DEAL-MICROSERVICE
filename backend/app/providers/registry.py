"""Builds the enabled providers from configuration. Real providers (Phase 6) register here and are
only enabled when their credentials are configured."""

from collections.abc import Callable

from app.core.config import Settings
from app.core.redis import get_redis
from app.providers.base import FlightProvider
from app.providers.demo import DemoProvider
from app.providers.demo_simulation import read_adjustment


def _demo(s: Settings) -> FlightProvider:
    return DemoProvider(
        latency_ms=s.demo_provider_latency_ms,
        adjustment=(lambda key: read_adjustment(get_redis(), key))
        if s.demo_simulation_enabled
        else (lambda _key: None),
    )


def _travelpayouts(s: Settings) -> FlightProvider:
    from app.providers.travelpayouts import TravelpayoutsProvider

    if not (s.travelpayouts_token and s.travelpayouts_marker):
        raise ValueError(
            "ENABLED_PROVIDERS includes travelpayouts, but TRAVELPAYOUTS_TOKEN and "
            "TRAVELPAYOUTS_MARKER are not both set (see .env.example)"
        )
    return TravelpayoutsProvider(
        token=s.travelpayouts_token.get_secret_value(),
        marker=s.travelpayouts_marker,
        base_url=s.travelpayouts_base_url,
        link_host=s.travelpayouts_link_host,
        timeout_s=s.provider_timeout_s,
        requests_per_minute=s.travelpayouts_requests_per_minute,
        cache_ttl_s=s.travelpayouts_cache_ttl_s,
    )


_FACTORIES: dict[str, Callable[[Settings], FlightProvider]] = {
    "demo": _demo,
    "travelpayouts": _travelpayouts,
}


def available_providers() -> list[str]:
    return sorted(_FACTORIES)


def build_providers(settings: Settings) -> list[FlightProvider]:
    unknown = set(settings.enabled_providers) - set(_FACTORIES)
    if unknown:
        raise ValueError(f"unknown providers in ENABLED_PROVIDERS: {sorted(unknown)}")
    return [_FACTORIES[name](settings) for name in settings.enabled_providers]
