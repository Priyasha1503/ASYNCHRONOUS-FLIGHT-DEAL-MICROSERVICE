"""Builders for hand-crafted offers, so unit tests state exactly the scenario they check."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from app.domain.offers import Baggage, FareSource, Offer, Segment, Slice
from app.domain.query import CabinClass, UpstreamQuery

DAY = date(2026, 12, 10)
RETURN_DAY = date(2026, 12, 17)
FETCHED = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def query(**kw: object) -> UpstreamQuery:
    base: dict[str, object] = {"origin": "LHR", "destination": "JFK", "depart_date": DAY}
    return UpstreamQuery.model_validate(base | kw)


def make_slice(
    origin: str = "LHR",
    destination: str = "JFK",
    *,
    day: date = DAY,
    dep_hour: int = 9,
    stops: int = 0,
    leg_minutes: int = 420,
    layover_minutes: int = 90,
    carriers: tuple[str, ...] = ("Q7",),
    hubs: tuple[str, ...] = ("DUB", "BOS", "IAD"),
) -> Slice:
    path = [origin, *hubs[:stops], destination]
    t = datetime(day.year, day.month, day.day, dep_hour, tzinfo=UTC)
    segs = []
    for i, (a, b) in enumerate(pairwise(path)):
        arr = t + timedelta(minutes=leg_minutes)
        code = carriers[min(i, len(carriers) - 1)]
        segs.append(
            Segment(
                carrier_code=code,
                carrier_name=f"Carrier {code}",
                flight_number=str(100 + i),
                origin=a,
                destination=b,
                departure_at=t,
                arrival_at=arr,
            )
        )
        t = arr + timedelta(minutes=layover_minutes)
    return Slice(segments=tuple(segs))


def make_offer(
    price: str = "400.00",
    *,
    oid: str | None = None,
    currency: str = "USD",
    cabin: CabinClass = CabinClass.ECONOMY,
    bags: int | None = 1,
    source: FareSource = FareSource.DEMO,
    provider: str = "test",
    fetched_at: datetime = FETCHED,
    slices: tuple[Slice, ...] | None = None,
    **slice_kw: object,
) -> Offer:
    return Offer(
        provider=provider,
        provider_offer_id=oid
        or f"o-{price}-{slice_kw.get('stops', 0)}-{slice_kw.get('dep_hour', 9)}",
        source=source,
        slices=slices or (make_slice(**slice_kw),),  # type: ignore[arg-type]
        total_amount=Decimal(price),
        currency=currency,
        cabin=cabin,
        baggage=Baggage(checked_bags=bags),
        fetched_at=fetched_at,
    )
