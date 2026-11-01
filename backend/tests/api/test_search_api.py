from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.money import SUPPORTED_CURRENCIES
from tests.api.conftest import csrf_headers

DEPART = (datetime.now(UTC).date() + timedelta(days=40)).isoformat()
RETURN = (datetime.now(UTC).date() + timedelta(days=47)).isoformat()


def body(**kw: Any) -> dict[str, Any]:
    return {"origin": "LHR", "destination": "JFK", "depart_date": DEPART} | kw


def search(client: TestClient, **kw: Any) -> Any:
    return client.post("/api/v1/searches", json=body(**kw), headers=csrf_headers(client))


def test_anonymous_search_returns_labelled_ranked_results(client: TestClient) -> None:
    r = search(client, return_date=RETURN, preferences={"max_stops": 1})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_demo"] is True
    assert data["providers"][0] | {"latency_ms": 0, "fetched_at": None} == {
        "provider": "demo",
        "display_name": "SkyScout demo data",
        "source": "demo",
        "bookable": False,
        "booking": "none",
        "state": "ok",
        "offers": data["providers"][0]["offers"],
        "latency_ms": 0,
        "fetched_at": None,
        "message": None,
    }
    offers = data["offers"]
    assert offers and all(o["source"] == "demo" and o["booking_url"] is None for o in offers)
    assert all(o["max_stops"] <= 1 for o in offers)
    assert isinstance(offers[0]["total_amount"], str)  # money never as float
    scores = [o["score"] for o in offers]
    assert scores == sorted(scores, reverse=True)
    ids = {o["id"] for o in offers}
    recs = data["recommendations"]
    assert recs["cheapest"]["offer_id"] in ids and recs["best_match"]["offer_id"] in ids
    cheapest = min(Decimal(o["total_amount"]) for o in offers)
    assert (
        next(Decimal(o["total_amount"]) for o in offers if o["id"] == recs["cheapest"]["offer_id"])
        == cheapest
    )
    sl = offers[0]["slices"][0]
    assert (
        sl["departure_at"].endswith(("+00:00", "Z"))
        or "+" in sl["departure_at"]
        or "-" in sl["departure_at"][-6:]
    )
    assert "arrival_day_offset" in sl and len(offers[0]["slices"]) == 2


def test_repeat_search_reports_cache(client: TestClient) -> None:
    first = search(client).json()
    second = search(client, preferences={"max_price": "5000"}).json()
    assert first["search_key"] == second["search_key"]
    assert second["providers"][0]["state"] == "cached"


def test_nothing_qualifies_explains_why(client: TestClient) -> None:
    data = search(client, preferences={"max_price": "1"}).json()
    assert data["offers"] == [] and data["recommendations"]["cheapest"] is None
    assert data["constraints"]["failed_by"]["budget"] == data["summary"]["eliminated"]
    relax = data["constraints"]["relaxations"][0]
    assert relax["constraint"] == "budget" and Decimal(relax["needed_value"]) > 1
    # Raising the budget to the suggested value adds only the offers at or under it.
    prices = sorted(Decimal(p) for p in _all_prices(client))
    assert relax["unlocks"] == len(prices)
    assert relax["unlocks_at_needed"] == sum(p <= Decimal(relax["needed_value"]) for p in prices)
    assert 1 <= relax["unlocks_at_needed"] < relax["unlocks"]


def _all_prices(client: TestClient) -> list[str]:
    return [o["total_amount"] for o in search(client).json()["offers"]]


def test_unknown_airport_is_reported_not_failed(client: TestClient) -> None:
    data = search(client, origin="XYZ").json()
    assert data["offers"] == [] and data["providers"][0]["state"] == "unsupported"


def test_validation_errors(client: TestClient) -> None:
    cases: list[tuple[dict[str, Any], str | None]] = [
        ({"destination": "LHR"}, None),
        ({"origin": "London"}, "origin"),
        ({"depart_date": "2020-01-01"}, "depart_date"),
        ({"passengers": {"adults": 1, "infants": 3}}, None),
        ({"currency": "BTC"}, "currency"),
        ({"preferences": {"max_price": "-5"}}, "max_price"),
        ({"preferences": {"surprise": True}}, "surprise"),
    ]
    for kw, field in cases:
        r = search(client, **kw)
        assert r.status_code == 422, (kw, r.text)
        err = r.json()["error"]
        assert err["code"] == "validation_error"
        if field:
            assert any(field in map(str, d["loc"]) for d in err["details"]), (kw, err)


def test_search_requires_csrf(client: TestClient) -> None:
    assert client.post("/api/v1/searches", json=body()).status_code == 403


def test_search_rate_limited(client: TestClient) -> None:
    s = get_settings()
    old, s.search_rate_limit_per_minute = s.search_rate_limit_per_minute, 2
    try:
        codes = [search(client).status_code for _ in range(3)]
    finally:
        s.search_rate_limit_per_minute = old
    assert codes == [200, 200, 429]


def test_airports_and_providers(client: TestClient) -> None:
    airports = {a["iata"]: a for a in client.get("/api/v1/airports").json()}
    assert airports["LHR"]["nearby"] == ["LGW"] and airports["LHR"]["tz"] == "Europe/London"
    providers = client.get("/api/v1/providers").json()
    assert providers == [
        {
            "provider": "demo",
            "display_name": "SkyScout demo data",
            "source": "demo",
            "bookable": False,
            "booking": "none",
            "circuit_open": False,
            "currencies": sorted(SUPPORTED_CURRENCIES),
        }
    ]
