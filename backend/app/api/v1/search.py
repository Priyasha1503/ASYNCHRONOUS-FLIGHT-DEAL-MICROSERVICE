from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import AppSettings, Limiter, OptionalUser
from app.api.v1.schemas.search import (
    AirportOut,
    ProviderInfoOut,
    SearchRequest,
    SearchResponse,
)
from app.core.errors import ValidationFailed
from app.domain.airports import AIRPORTS, nearby
from app.services.search import SearchService, default_search_service

router = APIRouter(tags=["search"])


def get_search_service() -> SearchService:
    return default_search_service()


Search = Annotated[SearchService, Depends(get_search_service)]


@router.post("/searches", response_model=SearchResponse)
def create_search(
    body: SearchRequest,
    request: Request,
    service: Search,
    settings: AppSettings,
    limiter: Limiter,
    user: OptionalUser,
) -> SearchResponse:
    """Run a flight search. Anonymous use is allowed (saving and monitoring need an account).

    Results include per-provider status, so partial failures are visible rather than silent.
    """
    who = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else '-'}"
    limiter.hit(f"search:{who}", settings.search_rate_limit_per_minute)
    query = body.to_query()
    try:
        query.check_dates(datetime.now(UTC).date())
    except ValueError as exc:
        raise ValidationFailed(
            str(exc),
            details=[{"loc": ["body", "depart_date"], "msg": str(exc), "type": "value_error"}],
        ) from exc
    result = service.search(query, body.preferences, include_nearby=body.include_nearby)
    return SearchResponse.of(result)


@router.get("/airports", response_model=list[AirportOut])
def list_airports() -> list[AirportOut]:
    """Airports SkyScout knows about (for autocomplete). Small and static, so returned in full."""
    return [
        AirportOut.of(a, nearby(a.iata)) for a in sorted(AIRPORTS.values(), key=lambda a: a.city)
    ]


@router.get("/providers", response_model=list[ProviderInfoOut])
def list_providers(service: Search) -> list[ProviderInfoOut]:
    """Configured providers and whether their circuit breaker is open. This reflects SkyScout's view
    of recent calls — not a guarantee the provider is up right now."""
    return [
        ProviderInfoOut(
            provider=p.name,
            display_name=p.display_name,
            source=p.capabilities.source,
            bookable=p.capabilities.bookable,
            booking=p.capabilities.booking,
            circuit_open=service.breaker.is_open(p.name),
            currencies=sorted(p.capabilities.currencies),
        )
        for p in service.providers
    ]
