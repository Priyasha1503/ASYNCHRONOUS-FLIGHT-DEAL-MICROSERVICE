"""Contract tests for the Travelpayouts adapter over a mocked HTTP transport (no network)."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.domain.offers import FareSource
from app.domain.pipeline import evaluate
from app.domain.query import CabinClass, Preferences
from app.domain.validation import validate_offer
from app.providers.errors import (
    ProviderAuthError,
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    ProviderUnsupportedQuery,
)
from app.providers.travelpayouts import TravelpayoutsProvider
from tests.unit.factories import query

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "travelpayouts_prices_for_dates.json").read_text()
)
T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)
RT = {"return_date": date(2026, 12, 17)}


def provider(handler: Any) -> TravelpayoutsProvider:
    return TravelpayoutsProvider(
        token="test-token-not-real",
        marker="123456",
        transport=httpx.MockTransport(handler),
        clock=lambda: T0,
    )


def ok(body: Any = FIXTURE, status: int = 200, headers: dict[str, str] | None = None) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        handler.request = request  # type: ignore[attr-defined]
        return httpx.Response(status, json=body, headers=headers)

    return handler


def test_request_shape_and_token_in_header_not_url() -> None:
    h = ok()
    provider(h).search(query(**RT))
    req: httpx.Request = h.request
    assert req.url.path == "/aviasales/v3/prices_for_dates"
    params = parse_qs(req.url.query.decode())
    assert params["origin"] == ["LHR"] and params["destination"] == ["JFK"]
    assert params["departure_at"] == ["2026-12-10"] and params["return_at"] == ["2026-12-17"]
    assert params["one_way"] == ["false"] and params["currency"] == ["usd"]
    assert req.headers["X-Access-Token"] == "test-token-not-real"
    assert "token" not in params and "test-token" not in str(req.url)


def test_items_map_to_observed_summary_offers() -> None:
    res = provider(ok()).search(query(**RT))
    assert len(res.offers) == 2  # third item has no UTC offset → unmappable, not guessed
    assert len(res.unmappable) == 1 and "offset" in res.unmappable[0]
    ba = next(o for o in res.offers if o.carriers == {"BA"})
    assert ba.source is FareSource.OBSERVED and ba.cabin is CabinClass.ECONOMY
    assert ba.total_amount == Decimal("412.00") and ba.currency == "USD"
    assert ba.baggage.checked_bags is None  # unknown, never assumed
    out, back = ba.slices
    assert (out.detail, out.stops, out.layovers) == ("summary", 0, [])
    assert out.segments[0].designator == "BA117"
    assert out.duration_minutes == 470
    # Arrival shown in the destination's local time (JFK, UTC-5 in December).
    assert out.arrival_at.isoformat() == "2026-12-10T11:15:00-05:00"
    assert back.segments[0].flight_number is None  # return flight number isn't provided
    dy = next(o for o in res.offers if o.carriers == {"DY"})
    assert dy.slices[0].segments[0].flight_number == "7015"  # "DY7015" normalized
    assert dy.max_stops == 1


def test_booking_link_is_absolute_https_with_our_marker_only() -> None:
    res = provider(ok()).search(query(**RT))
    for o in res.offers:
        assert o.booking_url is not None
        url = urlsplit(o.booking_url)
        assert (url.scheme, url.netloc) == ("https", "www.aviasales.com")
        assert url.path.startswith("/search/")
        assert parse_qs(url.query)["marker"] == ["123456"]  # replaces any marker in the link


def test_offers_pass_domain_validation_and_rank() -> None:
    q = query(**RT)
    offers = provider(ok()).search(q).offers
    # LGW isn't LHR: dropped unless nearby airports are requested — never silently mixed in.
    issues = {o.carriers.__iter__().__next__(): validate_offer(o, q) for o in offers}
    assert issues["BA"] == []
    assert issues["DY"] == ["return_route_mismatch", "route_mismatch"]  # LGW both ways
    out = evaluate(q, Preferences(), offers, include_nearby=True)
    assert len(out.ranked) == 2 and out.recommendations.cheapest is not None
    assert out.recommendations.cheapest.scored.offer.total_amount == Decimal("365.00")
    # Stop constraints work on declared stop counts.
    nonstop = evaluate(q, Preferences(max_stops=0), offers, include_nearby=True)
    assert [s.offer.carriers for s in nonstop.ranked] == [frozenset({"BA"})]


def test_unsupported_queries_are_not_guessed() -> None:
    p = provider(ok())
    with pytest.raises(ProviderUnsupportedQuery, match="one adult"):
        p.search(query(passengers={"adults": 2}))
    with pytest.raises(ProviderUnsupportedQuery):
        p.search(query(cabin=CabinClass.BUSINESS))


@pytest.mark.parametrize(
    ("status", "headers", "exc", "retryable"),
    [
        (401, None, ProviderAuthError, False),
        (403, None, ProviderAuthError, False),
        (429, {"X-Rate-Limit-Reset": "42"}, ProviderRateLimited, True),
        (502, None, ProviderUnavailable, True),
        (400, None, ProviderUnsupportedQuery, False),
    ],
)
def test_http_errors_map_to_provider_errors(
    status: int, headers: dict[str, str] | None, exc: type[Exception], retryable: bool
) -> None:
    with pytest.raises(exc) as info:
        provider(ok({"success": False}, status=status, headers=headers)).search(query())
    assert info.value.retryable is retryable  # type: ignore[attr-defined]
    if status == 429:
        assert info.value.retry_after_s == 42  # type: ignore[attr-defined]


def test_transport_failures() -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderTimeout):
        provider(timeout).search(query())
    with pytest.raises(ProviderUnavailable):
        provider(refused).search(query())


@pytest.mark.parametrize(
    "body",
    [
        {"success": False, "error": "bad token"},
        {"success": True},  # no data list
        {"success": True, "data": [{"price": "x"}]},  # nothing usable
        ["not", "an", "object"],
    ],
)
def test_invalid_responses(body: Any) -> None:
    with pytest.raises(ProviderInvalidResponse):
        provider(ok(body)).search(query())


def test_empty_data_is_a_valid_empty_result() -> None:
    res = provider(ok({"success": True, "data": []})).search(query())
    assert res.offers == [] and res.unmappable == []


def test_observed_offers_serialize_through_the_api_schema() -> None:
    """Summary slices (no return flight number, no layovers) must survive the API response model."""
    from app.api.v1.schemas.search import SearchResponse
    from app.core.config import get_settings
    from app.services.search import SearchService

    svc = SearchService([provider(ok())], get_settings(), redis_client=None)
    body = SearchResponse.of(svc.search(query(**RT), Preferences(), include_nearby=True))
    data = body.model_dump(mode="json")
    assert data["providers"][0]["booking"] == "redirect" and data["is_demo"] is False
    o = data["offers"][0]
    assert o["source"] == "observed" and o["booking_url"].startswith("https://www.aviasales.com/")
    assert o["slices"][1]["segments"][0]["flight_number"] is None
    assert o["slices"][0]["detail"] == "summary" and o["slices"][0]["layovers"] == []


def test_requires_credentials() -> None:
    with pytest.raises(ValueError):
        TravelpayoutsProvider(token="", marker="1")
