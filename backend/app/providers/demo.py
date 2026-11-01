"""Deterministic demo provider — synthetic, clearly-labelled fares for development and tests.

Everything about the output (flights, times, prices, baggage) is a pure function of the query: the
RNG is seeded from `query.cache_key()`, and nothing depends on the wall clock except `fetched_at`.
So the same query always yields the same offers, on every machine.

Honesty rules:
* Airlines are **fictional** (names and the codes chosen for them), so a demo fare can't be mistaken
  for a real airline's price. Airports, distances and timezones are real, so itineraries look right.
* Offers carry `source=demo` and no booking link — the UI labels them "Demo data".
* Prices come from a simple distance/cabin/stops model in USD converted at fixed illustrative rates
  (`DEMO_FX`). They are not market prices.
"""

import hashlib
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Literal

from app.domain.airports import AIRPORTS, Airport, distance_km, nearby
from app.domain.money import SUPPORTED_CURRENCIES, quantize
from app.domain.offers import Baggage, FareSource, Offer, Segment, Slice
from app.domain.query import CabinClass, UpstreamQuery
from app.providers.base import FlightProvider, ProviderCapabilities, ProviderResult
from app.providers.errors import (
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    ProviderUnsupportedQuery,
)


@dataclass(frozen=True, slots=True)
class DemoAirline:
    code: str
    name: str
    price_factor: float


# Fictional carriers. Codes contain a digit to reduce resemblance to real two-letter codes.
DEMO_AIRLINES: tuple[DemoAirline, ...] = (
    DemoAirline("Q7", "Aurora Atlantic", 1.08),
    DemoAirline("V3", "Vesper Air", 0.95),
    DemoAirline("N8", "Nimbus Airways", 1.00),
    DemoAirline("K5", "Kestrel Air", 0.88),
    DemoAirline("H9", "Halcyon Airlines", 1.15),
    DemoAirline("D4", "Dusk Pacific", 1.04),
    DemoAirline("M6", "Meridian Wings", 0.92),
    DemoAirline("T2", "Tern Airways", 0.85),
)

# Fixed, illustrative conversion from USD. NOT live exchange rates.
DEMO_FX: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "INR": Decimal("83.5"),
    "AUD": Decimal("1.52"),
    "CAD": Decimal("1.37"),
    "SGD": Decimal("1.35"),
    "AED": Decimal("3.67"),
    "JPY": Decimal("150"),
    "CHF": Decimal("0.89"),
}
assert set(DEMO_FX) == SUPPORTED_CURRENCIES

CABIN_FACTOR = {
    CabinClass.ECONOMY: 1.0,
    CabinClass.PREMIUM_ECONOMY: 1.7,
    CabinClass.BUSINESS: 3.6,
    CabinClass.FIRST: 6.0,
}
# (brand, price factor, checked bags or None if unconfirmed, cabin bag)
FARE_BRANDS: tuple[tuple[str, float, int | None, bool | None], ...] = (
    ("Basic", 1.00, 0, True),
    ("Standard", 1.12, 1, True),
    ("Flex", 1.35, 1, True),
    ("Saver", 0.97, None, None),  # provider "doesn't say" — exercises the unknown-baggage path
)
CRUISE_KMH = 820
MAX_NONSTOP_KM = 13_500

FailureMode = Literal["timeout", "rate_limited", "unavailable", "invalid_response"]


@dataclass(frozen=True, slots=True)
class _Leg:
    airline: DemoAirline
    flight_number: str
    origin: Airport
    destination: Airport
    departure: datetime  # UTC
    arrival: datetime  # UTC


class DemoProvider(FlightProvider):
    name = "demo"
    display_name = "SkyScout demo data"
    capabilities = ProviderCapabilities(
        source=FareSource.DEMO,
        bookable=False,
        currencies=SUPPORTED_CURRENCIES,
    )

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        latency_ms: int = 0,
        failure: FailureMode | None = None,
        adjustment: Callable[[str], Decimal | None] = lambda _key: None,
    ) -> None:
        self._clock = clock
        self._latency_ms = latency_ms
        self._failure = failure
        # Explicit, user-triggered price simulation (see `simulate_price_change`). Without it the
        # output is a pure function of the query.
        self._adjustment = adjustment

    # ── public API ────────────────────────────────────────────────────────

    def search(self, query: UpstreamQuery) -> ProviderResult:
        start = time.perf_counter()
        self.check_supported(query)
        origin, dest = AIRPORTS.get(query.origin), AIRPORTS.get(query.destination)
        if origin is None or dest is None:
            raise ProviderUnsupportedQuery(self.name, "airport not in demo dataset")
        if self._latency_ms:
            time.sleep(self._latency_ms / 1000)
        self._maybe_fail()

        rng = random.Random(int(query.cache_key()[3:19], 16))
        fetched_at = self._clock()
        factor = self._adjustment(query.cache_key()) or Decimal(1)
        outbound = self._slices(rng, origin, dest, query.depart_date, query.cabin)
        if query.return_date:
            inbound = self._slices(rng, dest, origin, query.return_date, query.cabin)
            pairs = self._pair(rng, outbound, inbound)
        else:
            pairs = [(o, None) for o in outbound]

        offers = [
            self._offer(query, i, out, back, fetched_at, rng, factor)
            for i, (out, back) in enumerate(pairs)
        ]
        return ProviderResult(
            provider=self.name,
            offers=offers,
            fetched_at=fetched_at,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    # ── generation ───────────────────────────────────────────────────────

    def _maybe_fail(self) -> None:
        match self._failure:
            case "timeout":
                raise ProviderTimeout(self.name, "simulated timeout")
            case "rate_limited":
                raise ProviderRateLimited(self.name, "simulated rate limit", retry_after_s=30)
            case "unavailable":
                raise ProviderUnavailable(self.name, "simulated 503")
            case "invalid_response":
                raise ProviderInvalidResponse(self.name, "simulated malformed payload")

    def _hubs(self, a: Airport, b: Airport) -> list[Airport]:
        direct = distance_km(a, b)
        excluded = {a.iata, b.iata} | nearby(a.iata) | nearby(b.iata)
        cands = [
            (distance_km(a, h) + distance_km(h, b), h)
            for h in AIRPORTS.values()
            if h.iata not in excluded
        ]
        good = [(d, h) for d, h in cands if d <= direct * 1.35 and distance_km(a, h) > 250]
        good.sort(key=lambda t: (t[0], t[1].iata))
        return [h for _, h in good[:6]]

    def _legs(
        self, rng: random.Random, path: list[Airport], day: date, airline: DemoAirline
    ) -> list[_Leg]:
        local = datetime(
            day.year, day.month, day.day, rng.randint(5, 22), rng.choice(range(0, 60, 5))
        )
        t = local.replace(tzinfo=path[0].zone).astimezone(UTC)
        legs: list[_Leg] = []
        for a, b in pairwise(path):
            minutes = int(distance_km(a, b) / CRUISE_KMH * 60) + 35 + rng.randint(-10, 15)
            arr = t + timedelta(minutes=max(minutes, 45))
            legs.append(_Leg(airline, str(rng.randint(100, 9899)), a, b, t, arr))
            t = arr + timedelta(minutes=rng.randint(55, 240))  # connection
        return legs

    def _slices(
        self, rng: random.Random, a: Airport, b: Airport, day: date, cabin: CabinClass
    ) -> list[tuple[list[_Leg], float]]:
        """Return (legs, usd_price_per_adult) options for one direction."""
        km = distance_km(a, b)
        hubs = self._hubs(a, b)
        plans: list[list[Airport]] = []
        if km <= MAX_NONSTOP_KM:
            plans += [[a, b]] * rng.randint(2, 4)
        if hubs:
            plans += [[a, rng.choice(hubs), b] for _ in range(rng.randint(5, 8))]
        if len(hubs) >= 2 and km > 3000:
            for _ in range(rng.randint(1, 3)):
                h1, h2 = rng.sample(hubs, 2)
                if distance_km(a, h1) > distance_km(a, h2):
                    h1, h2 = h2, h1
                plans.append([a, h1, h2, b])
        if not plans:  # very short hop with no sensible hub
            plans = [[a, b]] * 2

        out: list[tuple[list[_Leg], float]] = []
        for path in plans:
            airline = rng.choice(DEMO_AIRLINES)
            legs = self._legs(rng, path, day, airline)
            stops = len(path) - 2
            dep_hour = legs[0].departure.astimezone(a.zone).hour
            usd = (40 + 0.09 * km**0.97) * CABIN_FACTOR[cabin]
            usd *= (1.15, 0.92, 0.82)[min(stops, 2)]
            usd *= 0.9 if dep_hour < 7 or dep_hour >= 21 else 1.0
            usd *= airline.price_factor * rng.uniform(0.88, 1.18)
            out.append((legs, usd))
        return out

    @staticmethod
    def _pair(
        rng: random.Random,
        outbound: list[tuple[list[_Leg], float]],
        inbound: list[tuple[list[_Leg], float]],
    ) -> list[tuple[tuple[list[_Leg], float], tuple[list[_Leg], float] | None]]:
        pairs: list[tuple[tuple[list[_Leg], float], tuple[list[_Leg], float] | None]] = []
        for o in outbound:
            for i in rng.sample(range(len(inbound)), k=min(2, len(inbound))):
                pairs.append((o, inbound[i]))
        return pairs

    def _offer(
        self,
        query: UpstreamQuery,
        index: int,
        out: tuple[list[_Leg], float],
        back: tuple[list[_Leg], float] | None,
        fetched_at: datetime,
        rng: random.Random,
        factor: Decimal = Decimal(1),
    ) -> Offer:
        brand, brand_factor, bags, cabin_bag = rng.choice(FARE_BRANDS)
        pax = query.passengers
        pax_factor = pax.adults + 0.75 * pax.children + 0.1 * pax.infants
        usd = out[1] + (back[1] * 0.95 if back else 0.0)
        usd *= brand_factor * pax_factor
        amount = quantize(
            Decimal(str(round(usd, 4))) * DEMO_FX[query.currency] * factor, query.currency
        )

        slices = [self._slice(out[0])] + ([self._slice(back[0])] if back else [])
        oid = hashlib.sha256(f"{query.cache_key()}:{index}".encode()).hexdigest()[:16]
        return Offer(
            provider=self.name,
            provider_offer_id=oid,
            source=FareSource.DEMO,
            slices=tuple(slices),
            total_amount=amount,
            currency=query.currency,
            cabin=query.cabin,
            fare_brand=brand,
            baggage=Baggage(checked_bags=bags, cabin_bag=cabin_bag),
            booking_url=None,  # demo fares are not bookable
            fetched_at=fetched_at,
            expires_at=fetched_at + timedelta(minutes=30),
        )

    @staticmethod
    def _slice(legs: list[_Leg]) -> Slice:
        return Slice(
            segments=tuple(
                Segment(
                    carrier_code=leg.airline.code,
                    carrier_name=leg.airline.name,
                    flight_number=leg.flight_number,
                    origin=leg.origin.iata,
                    destination=leg.destination.iata,
                    departure_at=leg.departure.astimezone(leg.origin.zone),
                    arrival_at=leg.arrival.astimezone(leg.destination.zone),
                    aircraft=None,
                )
                for leg in legs
            )
        )
