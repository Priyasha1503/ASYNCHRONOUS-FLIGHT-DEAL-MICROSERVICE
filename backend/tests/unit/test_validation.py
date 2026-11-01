from datetime import timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.offers import FareSource, Offer, Slice
from app.domain.query import CabinClass
from app.domain.validation import dedupe, normalize, validate_offer
from tests.unit.factories import FETCHED, RETURN_DAY, make_offer, make_slice, query


def test_valid_offer_has_no_issues() -> None:
    assert validate_offer(make_offer(), query()) == []
    assert validate_offer(make_offer(stops=2), query()) == []


@pytest.mark.parametrize(
    ("offer_kw", "issue"),
    [
        ({"currency": "EUR"}, "currency_mismatch"),
        ({"price": "0"}, "non_positive_price"),
        ({"price": "-5.00"}, "non_positive_price"),
        ({"price": "400.005"}, "price_precision"),
        ({"cabin": CabinClass.BUSINESS}, "cabin_mismatch"),
        ({"destination": "BOS"}, "route_mismatch"),
        ({"day": RETURN_DAY}, "wrong_departure_date"),
        ({"stops": 1, "layover_minutes": 20}, "connection_too_short"),
        ({"stops": 1, "layover_minutes": 26 * 60}, "connection_too_long"),
        ({"leg_minutes": 21 * 60}, "segment_too_long"),
    ],
)
def test_invalid_offers_are_flagged(offer_kw: dict[str, object], issue: str) -> None:
    assert issue in validate_offer(make_offer(**offer_kw), query())  # type: ignore[arg-type]


def test_disconnected_segments() -> None:
    a = make_slice(destination="DUB")
    b = make_slice(origin="BOS", destination="JFK", dep_hour=20)
    offer = make_offer(slices=(Slice(segments=a.segments + b.segments),))
    assert "disconnected_segments" in validate_offer(offer, query())


def test_round_trip_shape_and_order() -> None:
    q = query(return_date=RETURN_DAY)
    good = make_offer(slices=(make_slice(), make_slice("JFK", "LHR", day=RETURN_DAY)))
    assert validate_offer(good, q) == []
    assert validate_offer(make_offer(), q) == ["slice_count"]
    wrong_way = make_offer(slices=(make_slice(), make_slice("BOS", "LHR", day=RETURN_DAY)))
    assert "return_route_mismatch" in validate_offer(wrong_way, q)


def test_nearby_airports_only_when_allowed() -> None:
    offer = make_offer(destination="EWR")
    assert "route_mismatch" in validate_offer(offer, query())
    assert validate_offer(offer, query(), destinations=frozenset({"JFK", "EWR"})) == []


def test_booking_url_must_be_https() -> None:
    data = make_offer().model_dump()
    for bad in ("javascript:alert(1)", "http://example.com/book", "/relative"):
        with pytest.raises(ValidationError, match="https"):
            Offer.model_validate(data | {"booking_url": bad})
    assert Offer.model_validate(data | {"booking_url": "https://example.com/b"}).booking_url


def test_fingerprint_ignores_offset_notation_and_provider() -> None:
    a = make_offer(provider="p1")
    shifted = Slice(
        segments=tuple(
            s.model_copy(
                update={
                    "departure_at": s.departure_at.astimezone(timezone(timedelta(hours=-5))),
                    "arrival_at": s.arrival_at.astimezone(timezone(timedelta(hours=-5))),
                }
            )
            for s in a.outbound.segments
        )
    )
    b = make_offer(provider="p2", slices=(shifted,))
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != make_offer(dep_hour=10).fingerprint


def test_dedupe_keeps_cheapest_then_most_trustworthy_then_freshest() -> None:
    cheap = make_offer("380.00", oid="cheap")
    pricey = make_offer("420.00", oid="pricey")
    unique, dupes = dedupe([pricey, cheap])
    assert [o.id for o in unique] == ["test:cheap"] and dupes == 1

    demo = make_offer("400.00", oid="d", source=FareSource.DEMO)
    live = make_offer("400.00", oid="l", source=FareSource.LIVE)
    assert dedupe([demo, live])[0][0].id == "test:l"

    old = make_offer("400.00", oid="old", source=FareSource.LIVE)
    new = make_offer(
        "400.00", oid="new", source=FareSource.LIVE, fetched_at=FETCHED + timedelta(minutes=5)
    )
    assert dedupe([old, new])[0][0].id == "test:new"


def test_normalize_reports_dropped_with_reasons() -> None:
    result = normalize([make_offer(), make_offer(currency="EUR", oid="bad")], query())
    assert [o.id for o in result.offers] == [make_offer().id]
    assert result.dropped[0].offer_id == "test:bad"
    assert result.dropped[0].reasons == ("currency_mismatch",)
