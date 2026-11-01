"""Normalized flight offer model shared by every provider.

Times are timezone-aware (local offset of the airport); durations are computed from the instants,
so they stay correct across timezones and DST. Unknown facts stay `None` — never guessed.
"""

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.domain.money import Amount, Currency
from app.domain.query import AirlineCode, CabinClass, Iata


class FareSource(StrEnum):
    """Data-honesty label shown next to every price (docs/PRD.md §4)."""

    LIVE = "live"  # real-time provider search for this request
    CACHED = "cached"  # live result reused from the shared cache
    OBSERVED = "observed"  # provider-reported recently-seen fare; not a bookable quote
    HISTORICAL = "historical"  # stored SkyScout observation (history views only)
    DEMO = "demo"  # deterministic demo provider — never a real fare


def _safe_url(v: str | None) -> str | None:
    # Booking links are rendered as <a href>; only plain https links are allowed (no javascript:).
    if v is None:
        return None
    parsed = urlparse(v)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("booking_url must be an absolute https URL")
    return v


FlightNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,4}[A-Z]?$")]


class Segment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    carrier_code: AirlineCode  # marketing carrier
    carrier_name: str = Field(min_length=1, max_length=80)
    flight_number: FlightNumber | None = None  # None = not provided by the source
    operating_carrier_code: AirlineCode | None = None
    origin: Iata
    destination: Iata
    departure_at: AwareDatetime
    arrival_at: AwareDatetime
    aircraft: str | None = Field(default=None, max_length=80)

    @property
    def duration_minutes(self) -> int:
        return int((self.arrival_at - self.departure_at).total_seconds() // 60)

    @property
    def designator(self) -> str:
        return f"{self.carrier_code}{self.flight_number or '?'}"


class Layover(BaseModel):
    model_config = ConfigDict(frozen=True)

    airport: str
    minutes: int


class Slice(BaseModel):
    """One direction of travel (outbound or return).

    `detail="full"`: every flight segment is known (live/demo providers).
    `detail="summary"`: the source only gives origin → destination times, the first carrier and a
    stop *count* (e.g. Aviasales observed fares). The slice then holds one segment spanning the
    whole journey and `declared_stops`; connection airports/times are unknown and never invented.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    segments: tuple[Segment, ...] = Field(min_length=1, max_length=4)
    detail: Literal["full", "summary"] = "full"
    declared_stops: int | None = Field(default=None, ge=0, le=4)

    @model_validator(mode="after")
    def _summary_shape(self) -> Self:
        if self.detail == "summary" and (len(self.segments) != 1 or self.declared_stops is None):
            raise ValueError("summary slices have exactly one journey segment and declared_stops")
        if self.detail == "full" and self.declared_stops is not None:
            raise ValueError("declared_stops is only for summary slices")
        return self

    @property
    def origin(self) -> str:
        return self.segments[0].origin

    @property
    def destination(self) -> str:
        return self.segments[-1].destination

    @property
    def departure_at(self) -> datetime:
        return self.segments[0].departure_at

    @property
    def arrival_at(self) -> datetime:
        return self.segments[-1].arrival_at

    @property
    def duration_minutes(self) -> int:
        """Door-to-door for this direction, including layovers."""
        return int((self.arrival_at - self.departure_at).total_seconds() // 60)

    @property
    def stops(self) -> int:
        if self.declared_stops is not None:
            return self.declared_stops
        return len(self.segments) - 1

    @property
    def layovers(self) -> list[Layover]:
        if self.detail == "summary":
            return []  # unknown — the UI says so instead of guessing
        return [
            Layover(
                airport=a.destination,
                minutes=int((b.departure_at - a.arrival_at).total_seconds() // 60),
            )
            for a, b in pairwise(self.segments)
        ]


class Baggage(BaseModel):
    """What the fare includes, per passenger. `None` means the provider didn't confirm it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checked_bags: int | None = Field(default=None, ge=0, le=4)
    cabin_bag: bool | None = None


class Offer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1, max_length=40)
    provider_offer_id: str = Field(min_length=1, max_length=200)
    source: FareSource
    slices: tuple[Slice, ...] = Field(min_length=1, max_length=2)
    total_amount: Amount  # all passengers, taxes included
    currency: Currency
    cabin: CabinClass
    fare_brand: str | None = Field(default=None, max_length=60)
    baggage: Baggage = Baggage()
    booking_url: Annotated[str | None, AfterValidator(_safe_url)] = None
    fetched_at: AwareDatetime
    expires_at: AwareDatetime | None = None

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.provider_offer_id}"

    @property
    def outbound(self) -> Slice:
        return self.slices[0]

    @property
    def inbound(self) -> Slice | None:
        return self.slices[1] if len(self.slices) > 1 else None

    @property
    def total_duration_minutes(self) -> int:
        return sum(s.duration_minutes for s in self.slices)

    @property
    def max_stops(self) -> int:
        return max(s.stops for s in self.slices)

    @property
    def carriers(self) -> frozenset[str]:
        return frozenset(seg.carrier_code for s in self.slices for seg in s.segments)

    @property
    def fingerprint(self) -> str:
        """Identity of the *itinerary* (not the provider's offer), used to dedupe across providers
        and to key price observations: same flights + same departure instants + same cabin."""
        parts = [self.cabin.value]
        for s in self.slices:
            for seg in s.segments:
                # UTC so the fingerprint is independent of offset notation and server timezone.
                parts.append(f"{seg.designator}@{seg.departure_at.astimezone(UTC).isoformat()}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
