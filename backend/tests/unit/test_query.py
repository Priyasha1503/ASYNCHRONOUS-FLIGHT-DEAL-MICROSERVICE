from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.money import quantize, to_decimal
from app.domain.query import Passengers, Preferences, TimeWindow, TripType, UpstreamQuery
from tests.unit.factories import DAY, RETURN_DAY, query


def test_cache_key_normalizes_equivalent_inputs() -> None:
    a = query()
    b = UpstreamQuery.model_validate(
        {
            "origin": " lhr ",
            "destination": "jfk",
            "depart_date": "2026-12-10",
            "passengers": {"adults": 1},
            "cabin": "economy",
            "currency": "usd",
        }
    )
    assert a.cache_key() == b.cache_key()
    assert a.cache_key().startswith("q1:")


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "EUR"},
        {"cabin": "business"},
        {"passengers": {"adults": 2}},
        {"return_date": RETURN_DAY},
        {"destination": "EWR"},
    ],
)
def test_cache_key_changes_with_upstream_params(change: dict[str, object]) -> None:
    assert query().cache_key() != query(**change).cache_key()


def test_trip_type() -> None:
    assert query().trip_type is TripType.ONE_WAY
    assert query(return_date=RETURN_DAY).trip_type is TripType.ROUND_TRIP


@pytest.mark.parametrize(
    ("kw", "msg"),
    [
        ({"destination": "LHR"}, "must differ"),
        ({"return_date": DAY - timedelta(days=1)}, "on or after"),
        ({"origin": "LONDON"}, "pattern"),
        ({"currency": "XXX"}, "unsupported currency"),
        ({"passengers": {"adults": 1, "infants": 2}}, "infant"),
        ({"passengers": {"adults": 5, "children": 5}}, "at most 9"),
        ({"passengers": {"adults": 0}}, "greater than or equal"),
        ({"unknown": 1}, "Extra inputs"),
    ],
)
def test_query_validation(kw: dict[str, object], msg: str) -> None:
    with pytest.raises(ValidationError, match=msg):
        query(**kw)


def test_check_dates() -> None:
    q = query()
    q.check_dates(today=DAY)  # same day is fine
    with pytest.raises(ValueError, match="past"):
        q.check_dates(today=DAY + timedelta(days=1))
    with pytest.raises(ValueError, match="within"):
        q.check_dates(today=DAY - timedelta(days=400))


def test_passenger_total() -> None:
    assert Passengers(adults=2, children=1, infants=1).total == 4


def test_preferences_reject_contradictions() -> None:
    with pytest.raises(ValidationError, match="both preferred and excluded"):
        Preferences(preferred_airlines=frozenset({"Q7"}), excluded_airlines=frozenset({"q7"}))
    with pytest.raises(ValidationError):
        Preferences(max_price=Decimal("0"))


def test_time_window() -> None:
    w = TimeWindow(start_hour=6, end_hour=12)
    assert w.contains(6) and w.contains(11, 59)
    assert not w.contains(12) and not w.contains(5, 59)
    with pytest.raises(ValidationError):
        TimeWindow(start_hour=12, end_hour=12)


def test_money_helpers() -> None:
    assert quantize(Decimal("10.005"), "USD") == Decimal("10.01")  # half-up, not banker's
    assert quantize(Decimal("1234.5"), "JPY") == Decimal("1235")
    assert to_decimal("19.99") == Decimal("19.99")
    with pytest.raises(ValueError, match="float"):
        to_decimal(19.99)
    with pytest.raises(ValueError):
        to_decimal("NaN")


def test_date_type_is_strict_date() -> None:
    assert isinstance(query().depart_date, date)
