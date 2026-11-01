"""The upstream search query: every parameter that changes what a provider returns.

User-only preferences (budget, stops, airlines, time windows, bags) are deliberately *not* part of
it — they're applied after retrieval — so one cached upstream result serves every user who searches
the same route/dates/passengers/cabin/currency.
"""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.domain.money import Currency

MAX_PASSENGERS = 9
MAX_BOOKING_HORIZON_DAYS = 330  # typical airline schedule horizon
MAX_TRIP_LENGTH_DAYS = 330


def _upper(v: object) -> object:
    return v.strip().upper() if isinstance(v, str) else v


Iata = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{3}$")]
AirlineCode = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z0-9]{2}$")]


class CabinClass(StrEnum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class TripType(StrEnum):
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class Passengers(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adults: int = Field(default=1, ge=1, le=MAX_PASSENGERS)
    children: int = Field(default=0, ge=0, le=MAX_PASSENGERS - 1)  # ages 2 to 11
    infants: int = Field(default=0, ge=0, le=MAX_PASSENGERS - 1)  # under 2, on lap

    @model_validator(mode="after")
    def _limits(self) -> Self:
        if self.infants > self.adults:
            raise ValueError("each infant must travel with an adult")
        if self.total > MAX_PASSENGERS:
            raise ValueError(f"at most {MAX_PASSENGERS} passengers per search")
        return self

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


class UpstreamQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    origin: Iata
    destination: Iata
    depart_date: date
    return_date: date | None = None
    passengers: Passengers = Passengers()
    cabin: CabinClass = CabinClass.ECONOMY
    currency: Currency = "USD"

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        if self.return_date is not None:
            if self.return_date < self.depart_date:
                raise ValueError("return date must be on or after the departure date")
            if (self.return_date - self.depart_date).days > MAX_TRIP_LENGTH_DAYS:
                raise ValueError(f"trips longer than {MAX_TRIP_LENGTH_DAYS} days aren't supported")
        return self

    @property
    def trip_type(self) -> TripType:
        return TripType.ROUND_TRIP if self.return_date else TripType.ONE_WAY

    def check_dates(self, today: date) -> None:
        """Clock-dependent validation, kept separate so the model itself stays pure."""
        if self.depart_date < today:
            raise ValueError("departure date is in the past")
        if self.depart_date > today + timedelta(days=MAX_BOOKING_HORIZON_DAYS):
            raise ValueError(f"departure must be within {MAX_BOOKING_HORIZON_DAYS} days")

    def canonical(self) -> str:
        """Stable serialization: equivalent inputs (case, whitespace, defaults) → identical text."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def cache_key(self) -> str:
        """Versioned hash used for the shared cache and for monitored-query identity."""
        return "q1:" + hashlib.sha256(self.canonical().encode()).hexdigest()[:32]


class TimeWindow(BaseModel):
    """Local-time window [start_hour, end_hour) at the relevant airport."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be after start_hour")
        return self

    def contains(self, hour: int, minute: int = 0) -> bool:
        t = hour * 60 + minute
        return self.start_hour * 60 <= t < self.end_hour * 60


class Preferences(BaseModel):
    """What the user wants.

    Hard constraints exclude offers; soft preferences only affect ranking.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # ── Hard constraints ────────────────────────────────────────────────
    max_price: Decimal | None = Field(default=None, gt=0, description="Total, in query currency")
    max_stops: int | None = Field(default=None, ge=0, le=3, description="Per direction")
    require_checked_bag: bool = False
    max_duration_minutes: int | None = Field(
        default=None, ge=60, le=72 * 60, description="Per direction"
    )
    excluded_airlines: frozenset[AirlineCode] = frozenset()
    # Time windows are soft unless `time_windows_strict` is set.
    time_windows_strict: bool = False

    # ── Soft preferences ────────────────────────────────────────────────
    preferred_airlines: frozenset[AirlineCode] = frozenset()
    departure_window: TimeWindow | None = None  # outbound departure, origin local time
    arrival_window: TimeWindow | None = None  # outbound arrival, destination local time

    @model_validator(mode="after")
    def _no_overlap(self) -> Self:
        if both := self.preferred_airlines & self.excluded_airlines:
            raise ValueError(f"airlines both preferred and excluded: {sorted(both)}")
        return self


class SearchRequest(BaseModel):
    """A complete search: the upstream query plus the user's preferences and options."""

    model_config = ConfigDict(extra="forbid")

    origin: Iata
    destination: Iata
    depart_date: date
    return_date: date | None = None
    passengers: Passengers = Passengers()
    cabin: CabinClass = CabinClass.ECONOMY
    currency: Currency = "USD"
    preferences: Preferences = Preferences()
    include_nearby: bool = False

    _query: UpstreamQuery = PrivateAttr()

    @model_validator(mode="after")
    def _build_query(self) -> Self:
        # Cross-field rules live in the domain model; building it here turns any violation into a
        # normal 422 instead of an error deep inside the handler.
        try:
            self._query = UpstreamQuery(
                origin=self.origin,
                destination=self.destination,
                depart_date=self.depart_date,
                return_date=self.return_date,
                passengers=self.passengers,
                cabin=self.cabin,
                currency=self.currency,
            )
        except ValidationError as exc:
            raise ValueError(
                "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())
            ) from None
        return self

    def to_query(self) -> UpstreamQuery:
        return self._query
