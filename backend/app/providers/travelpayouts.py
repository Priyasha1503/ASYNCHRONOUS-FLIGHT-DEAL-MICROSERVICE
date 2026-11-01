"""Travelpayouts / Aviasales Data API adapter (`/aviasales/v3/prices_for_dates`).

What this source is — and isn't (shown to users via the `observed` label):
* Cheapest fares *found by Aviasales users recently* (Travelpayouts: "in the last 48 hours"). A
  sighting, not a live quote: the price on the booking site can differ or be gone.
* Prices are for one adult in economy, so other passenger mixes/cabins are reported as
  unsupported rather than multiplied into guesses.
* Itineraries come as origin → destination with a stop *count*; connection airports, return
  flight numbers and baggage are not provided. They are left unknown (`detail="summary"`).
* Booking happens on Aviasales (→ airline or agency) via the item's `link`, with our partner
  `marker` attached for affiliate attribution.

Unverified against a live response at time of writing (the docs were not machine-readable here):
the exact marker parameter and the full field list. `scripts/travelpayouts_smoke.py` records a real
response so the contract test fixture can be replaced with ground truth.
"""

import hashlib
import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.domain.airports import AIRPORTS
from app.domain.money import SUPPORTED_CURRENCIES, quantize, to_decimal
from app.domain.offers import Baggage, FareSource, Offer, Segment, Slice
from app.domain.query import CabinClass, UpstreamQuery
from app.providers.base import FlightProvider, ProviderCapabilities, ProviderResult
from app.providers.errors import (
    ProviderAuthError,
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    ProviderUnsupportedQuery,
)

log = logging.getLogger(__name__)
PATH = "/aviasales/v3/prices_for_dates"


class TravelpayoutsProvider(FlightProvider):
    name = "travelpayouts"
    display_name = "Aviasales (recent prices)"

    def __init__(
        self,
        *,
        token: str,
        marker: str,
        base_url: str = "https://api.travelpayouts.com",
        link_host: str = "https://www.aviasales.com",
        timeout_s: float = 12.0,
        requests_per_minute: int = 60,
        cache_ttl_s: int = 3 * 3600,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not token or not marker:
            raise ValueError("Travelpayouts needs both a token and a partner marker")
        self.marker = marker
        self.link_host = link_host.rstrip("/")
        self.clock = clock
        self.capabilities = ProviderCapabilities(
            source=FareSource.OBSERVED,
            bookable=False,  # price not guaranteed at checkout…
            booking="redirect",  # …but there is a booking path
            cabins=frozenset({CabinClass.ECONOMY}),
            currencies=SUPPORTED_CURRENCIES,
            max_passengers=1,
            requests_per_minute=requests_per_minute,
            cache_ttl_s=cache_ttl_s,
        )
        # Token in a header (not the query string) so it never lands in URL logs.
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s, connect=3.0),
            headers={"X-Access-Token": token, "Accept": "application/json"},
            transport=transport,
        )

    def check_supported(self, query: UpstreamQuery) -> None:
        p = query.passengers
        if (p.adults, p.children, p.infants) != (1, 0, 0):
            raise ProviderUnsupportedQuery(self.name, "prices are for one adult only")
        super().check_supported(query)

    def search(self, query: UpstreamQuery) -> ProviderResult:
        self.check_supported(query)
        params: dict[str, str | int] = {
            "origin": query.origin,
            "destination": query.destination,
            "departure_at": query.depart_date.isoformat(),
            "one_way": "false" if query.return_date else "true",
            "currency": query.currency.lower(),
            "sorting": "price",
            "direct": "false",
            "unique": "false",
            "limit": 100,
            "page": 1,
        }
        if query.return_date:
            params["return_at"] = query.return_date.isoformat()

        started = time.perf_counter()
        body = self._get(params)
        fetched_at = self.clock()
        items = body.get("data")
        if not isinstance(items, list):
            raise ProviderInvalidResponse(self.name, "response has no data list")

        offers: list[Offer] = []
        unmappable: list[str] = []
        for i, item in enumerate(items):
            try:
                offers.append(self._to_offer(item, query, fetched_at))
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                unmappable.append(f"item {i}: {type(exc).__name__}: {str(exc)[:120]}")
        if items and not offers:
            raise ProviderInvalidResponse(self.name, f"no usable items ({unmappable[0]})")
        if unmappable:
            log.warning(
                "travelpayouts items could not be mapped",
                extra={"count": len(unmappable), "first": unmappable[0]},
            )
        return ProviderResult(
            provider=self.name,
            offers=offers,
            fetched_at=fetched_at,
            latency_ms=int((time.perf_counter() - started) * 1000),
            unmappable=unmappable,
        )

    # ── transport ────────────────────────────────────────────────────────────

    def _get(self, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            r = self._client.get(PATH, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(self.name, "request timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderUnavailable(self.name, f"network error: {type(exc).__name__}") from exc

        if r.status_code in (401, 403):
            raise ProviderAuthError(self.name, f"HTTP {r.status_code}: check TRAVELPAYOUTS_TOKEN")
        if r.status_code == 429:
            reset = r.headers.get("X-Rate-Limit-Reset") or r.headers.get("Retry-After")
            raise ProviderRateLimited(
                self.name,
                "HTTP 429",
                retry_after_s=float(reset) if reset and reset.isdigit() else None,
            )
        if r.status_code >= 500:
            raise ProviderUnavailable(self.name, f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise ProviderUnsupportedQuery(self.name, f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            body = r.json()
        except ValueError as exc:
            raise ProviderInvalidResponse(self.name, "response is not JSON") from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            err = body.get("error") if isinstance(body, dict) else None
            raise ProviderInvalidResponse(self.name, f"unsuccessful response: {err!r}"[:200])
        return body

    # ── mapping ──────────────────────────────────────────────────────────────

    def booking_link(self, link: str) -> str:
        """Absolute https Aviasales URL with our partner marker added (replacing any existing)."""
        url = link if link.startswith("https://") else f"{self.link_host}/{link.lstrip('/')}"
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise ValueError("booking link is not https")
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "marker"]
        query.append(("marker", self.marker))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    @staticmethod
    def _local(dt: datetime, airport: str) -> datetime:
        ap = AIRPORTS.get(airport)
        return dt.astimezone(ap.zone) if ap else dt.astimezone(UTC)

    def _slice(
        self,
        *,
        airline: str,
        flight_number: str | None,
        origin: str,
        destination: str,
        departure: str,
        duration_min: int,
        stops: int,
    ) -> Slice:
        dep = datetime.fromisoformat(departure)
        if dep.tzinfo is None:
            raise ValueError("departure time has no UTC offset")
        if duration_min <= 0:
            raise ValueError("non-positive duration")
        arr = self._local(dep + timedelta(minutes=duration_min), destination)
        # Accept "7701" or "UX7701"; anything else is recorded as unknown rather than rejected.
        fn = None
        if flight_number:
            digits = flight_number.upper().removeprefix(airline)
            fn = digits if re.fullmatch(r"[0-9]{1,4}[A-Z]?", digits) else None
        seg = Segment(
            carrier_code=airline,
            carrier_name=airline,  # the API gives codes only; names are not invented
            flight_number=fn,
            origin=origin,
            destination=destination,
            departure_at=dep,
            arrival_at=arr,
        )
        return Slice(segments=(seg,), detail="summary", declared_stops=stops)

    def _to_offer(self, item: dict[str, Any], query: UpstreamQuery, fetched_at: datetime) -> Offer:
        price = quantize(to_decimal(str(item["price"])), query.currency)
        origin = str(item.get("origin_airport") or item["origin"]).upper()
        dest = str(item.get("destination_airport") or item["destination"]).upper()
        airline = str(item["airline"]).upper()
        one_way = query.return_date is None
        out_minutes = int(item.get("duration_to") or (item["duration"] if one_way else 0))
        slices = [
            self._slice(
                airline=airline,
                flight_number=str(item["flight_number"]) if item.get("flight_number") else None,
                origin=origin,
                destination=dest,
                departure=str(item["departure_at"]),
                duration_min=out_minutes,
                stops=int(item.get("transfers", 0)),
            )
        ]
        if not one_way:
            slices.append(
                self._slice(
                    airline=airline,
                    flight_number=None,  # not provided for the return leg
                    origin=dest,
                    destination=origin,
                    departure=str(item["return_at"]),
                    duration_min=int(item["duration_back"]),
                    stops=int(item.get("return_transfers", 0)),
                )
            )
        link = str(item["link"])
        return Offer(
            provider=self.name,
            provider_offer_id=hashlib.sha256(link.encode()).hexdigest()[:24],
            source=FareSource.OBSERVED,
            slices=tuple(slices),
            total_amount=price,
            currency=query.currency,
            cabin=CabinClass.ECONOMY,
            baggage=Baggage(),  # not provided → unknown
            booking_url=self.booking_link(link),
            fetched_at=fetched_at,
        )
