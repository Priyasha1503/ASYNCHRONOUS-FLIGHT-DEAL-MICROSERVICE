from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.airports import AIRPORTS
from app.domain.offers import FareSource
from app.domain.pipeline import evaluate
from app.domain.query import CabinClass, Preferences
from app.domain.validation import validate_offer
from app.providers.demo import DEMO_AIRLINES, DemoProvider
from app.providers.errors import (
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    ProviderUnsupportedQuery,
)
from tests.unit.factories import RETURN_DAY, query

T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)
CONTENT = {"fetched_at", "expires_at"}


def content(offers: list) -> list[dict]:  # type: ignore[type-arg]
    return [o.model_dump(mode="json", exclude=CONTENT) for o in offers]


def test_same_query_same_offers_regardless_of_clock() -> None:
    a = DemoProvider(clock=lambda: T0).search(query())
    b = DemoProvider(clock=lambda: T0 + timedelta(days=3)).search(query())
    assert content(a.offers) == content(b.offers)
    assert a.fetched_at != b.fetched_at  # only metadata reflects the clock


def test_different_queries_differ() -> None:
    p = DemoProvider()
    assert content(p.search(query()).offers) != content(p.search(query(destination="BOS")).offers)


ROUTES = [
    ("LHR", "JFK"),  # transatlantic
    ("DEL", "BLR"),  # domestic India
    ("SIN", "SYD"),  # southern hemisphere, DST at destination
    ("LAX", "NRT"),  # crosses the date line
    ("CDG", "AMS"),  # short hop
    ("JNB", "SEA"),  # very long → connections only
]


@pytest.mark.parametrize(("origin", "destination"), ROUTES)
@pytest.mark.parametrize("round_trip", [False, True])
def test_every_demo_offer_is_valid_and_labelled(
    origin: str, destination: str, round_trip: bool
) -> None:
    q = query(
        origin=origin, destination=destination, return_date=RETURN_DAY if round_trip else None
    )
    result = DemoProvider().search(q)
    assert result.offers, "demo provider should always return something for known airports"
    demo_codes = {a.code for a in DEMO_AIRLINES}
    for o in result.offers:
        issues = validate_offer(o, q)
        # Same-day/short round trips can legitimately produce returns that leave before arrival.
        assert set(issues) <= {"return_before_arrival"}, (o.id, issues)
        assert o.source is FareSource.DEMO and o.booking_url is None
        assert o.carriers <= demo_codes  # fictional airlines only
        out = o.outbound
        assert (
            out.departure_at.utcoffset()
            == out.departure_at.astimezone(AIRPORTS[origin].zone).utcoffset()
        )  # times are local to the airport


def test_long_haul_has_no_impossible_nonstops() -> None:
    offers = DemoProvider().search(query(origin="JNB", destination="SEA")).offers
    assert all(o.max_stops >= 1 for o in offers)


@pytest.mark.parametrize(("currency", "places"), [("USD", 2), ("INR", 2), ("JPY", 0)])
def test_currency_and_precision(currency: str, places: int) -> None:
    for o in DemoProvider().search(query(currency=currency)).offers:
        assert o.currency == currency
        assert -o.total_amount.as_tuple().exponent <= places  # type: ignore[operator]


def test_cabin_costs_more() -> None:
    eco = DemoProvider().search(query()).offers
    biz = DemoProvider().search(query(cabin=CabinClass.BUSINESS)).offers
    assert min(o.total_amount for o in biz) > min(o.total_amount for o in eco) * 2


def test_unknown_airport_is_unsupported_not_an_error() -> None:
    with pytest.raises(ProviderUnsupportedQuery) as exc:
        DemoProvider().search(query(origin="XYZ"))
    assert exc.value.retryable is False


@pytest.mark.parametrize(
    ("mode", "exc", "retryable"),
    [
        ("timeout", ProviderTimeout, True),
        ("rate_limited", ProviderRateLimited, True),
        ("unavailable", ProviderUnavailable, True),
        ("invalid_response", ProviderInvalidResponse, False),
    ],
)
def test_failure_injection(mode: str, exc: type[Exception], retryable: bool) -> None:
    with pytest.raises(exc) as info:
        DemoProvider(failure=mode).search(query())  # type: ignore[arg-type]
    assert info.value.retryable is retryable  # type: ignore[attr-defined]


def test_pipeline_end_to_end_on_demo_data_is_deterministic() -> None:
    prefs = Preferences(max_price=Decimal("700"), max_stops=1)
    q = query(return_date=RETURN_DAY)

    def run() -> list[str]:
        out = evaluate(q, prefs, DemoProvider(clock=lambda: T0).search(q).offers)
        assert out.recommendations.cheapest is not None
        assert all(s.offer.total_amount <= Decimal("700") for s in out.ranked)
        assert all(s.offer.max_stops <= 1 for s in out.ranked)
        cheapest = out.recommendations.cheapest.scored.offer.total_amount
        assert cheapest == min(s.offer.total_amount for s in out.ranked)
        assert out.received == out.constraints.total + len(out.dropped) + out.duplicates_removed
        return [s.offer.id for s in out.ranked]

    assert run() == run()


def test_pipeline_reports_why_nothing_qualifies() -> None:
    out = evaluate(
        query(), Preferences(max_price=Decimal("50")), DemoProvider().search(query()).offers
    )
    assert not out.has_results
    assert out.recommendations.cheapest is None
    relax = out.constraints.relaxations[0]
    assert relax.constraint.value == "budget" and relax.needed_value > Decimal("50")  # type: ignore[operator]
