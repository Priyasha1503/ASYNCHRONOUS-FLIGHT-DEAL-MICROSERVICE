"""Search API contract. Domain objects are mapped explicitly so the wire format is stable even if
internals change. Money is serialized as a string."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.airports import Airport
from app.domain.constraints import ConstraintReport
from app.domain.money import Amount
from app.domain.offers import FareSource, Offer, Segment, Slice
from app.domain.query import CabinClass, SearchRequest, TripType
from app.domain.ranking import Pick, ScoredOffer
from app.services.search import ProviderState, ProviderStatus, SearchResult

__all__ = ["SearchRequest"]  # re-exported: the request contract is the domain model


# ── response ─────────────────────────────────────────────────────────────────


class SegmentOut(BaseModel):
    carrier_code: str
    carrier_name: str
    flight_number: str | None = Field(description="null = not provided by the source")
    operating_carrier_code: str | None
    origin: str
    destination: str
    departure_at: datetime  # ISO-8601 with the airport's local offset
    arrival_at: datetime
    duration_minutes: int
    aircraft: str | None

    @classmethod
    def of(cls, s: Segment) -> "SegmentOut":
        return cls(
            carrier_code=s.carrier_code,
            carrier_name=s.carrier_name,
            flight_number=s.flight_number,
            operating_carrier_code=s.operating_carrier_code,
            origin=s.origin,
            destination=s.destination,
            departure_at=s.departure_at,
            arrival_at=s.arrival_at,
            duration_minutes=s.duration_minutes,
            aircraft=s.aircraft,
        )


class LayoverOut(BaseModel):
    airport: str
    minutes: int


class SliceOut(BaseModel):
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    stops: int
    arrival_day_offset: int = Field(description="Calendar days between local departure and arrival")
    detail: str = Field(description="full: all segments known; summary: stop count only")
    layovers: list[LayoverOut]
    segments: list[SegmentOut]

    @classmethod
    def of(cls, s: Slice) -> "SliceOut":
        return cls(
            origin=s.origin,
            destination=s.destination,
            departure_at=s.departure_at,
            arrival_at=s.arrival_at,
            duration_minutes=s.duration_minutes,
            stops=s.stops,
            detail=s.detail,
            arrival_day_offset=(s.arrival_at.date() - s.departure_at.date()).days,
            layovers=[LayoverOut(airport=lay.airport, minutes=lay.minutes) for lay in s.layovers],
            segments=[SegmentOut.of(seg) for seg in s.segments],
        )


class ScoreComponentOut(BaseModel):
    factor: str
    weight: float
    score: float
    note: str


class BaggageOut(BaseModel):
    checked_bags: int | None = Field(description="null = not confirmed by the provider")
    cabin_bag: bool | None


class OfferOut(BaseModel):
    id: str
    fingerprint: str
    provider: str
    source: FareSource
    total_amount: Amount
    currency: str
    cabin: CabinClass
    fare_brand: str | None
    baggage: BaggageOut
    booking_url: str | None
    fetched_at: datetime
    expires_at: datetime | None
    total_duration_minutes: int
    max_stops: int
    score: float
    score_components: list[ScoreComponentOut]
    slices: list[SliceOut]

    @classmethod
    def of(cls, scored: ScoredOffer) -> "OfferOut":
        o: Offer = scored.offer
        return cls(
            id=o.id,
            fingerprint=o.fingerprint,
            provider=o.provider,
            source=o.source,
            total_amount=o.total_amount,
            currency=o.currency,
            cabin=o.cabin,
            fare_brand=o.fare_brand,
            baggage=BaggageOut(checked_bags=o.baggage.checked_bags, cabin_bag=o.baggage.cabin_bag),
            booking_url=o.booking_url,
            fetched_at=o.fetched_at,
            expires_at=o.expires_at,
            total_duration_minutes=o.total_duration_minutes,
            max_stops=o.max_stops,
            score=scored.score,
            score_components=[
                ScoreComponentOut(
                    factor=c.factor.value, weight=c.weight, score=c.score, note=c.note
                )
                for c in scored.components
            ],
            slices=[SliceOut.of(s) for s in o.slices],
        )


class PickOut(BaseModel):
    kind: str
    offer_id: str
    reasons: list[str]

    @classmethod
    def of(cls, p: Pick | None) -> "PickOut | None":
        if p is None:
            return None
        return cls(kind=p.kind.value, offer_id=p.scored.offer.id, reasons=list(p.reasons))


class RecommendationsOut(BaseModel):
    cheapest: PickOut | None
    best_match: PickOut | None
    alternatives: list[PickOut]


class RelaxationOut(BaseModel):
    constraint: str
    unlocks: int
    needed_value: str | None = Field(description="Smallest value that unlocks an offer, if numeric")
    unlocks_at_needed: int = Field(description="Offers added by moving the limit to needed_value")


class ConstraintReportOut(BaseModel):
    total: int
    qualifying: int
    failed_by: dict[str, int]
    relaxations: list[RelaxationOut]

    @classmethod
    def of(cls, r: ConstraintReport) -> "ConstraintReportOut":
        return cls(
            total=r.total,
            qualifying=r.qualifying,
            failed_by={c.value: n for c, n in r.failed_by.items()},
            relaxations=[
                RelaxationOut(
                    constraint=x.constraint.value,
                    unlocks=x.unlocks,
                    needed_value=None if x.needed_value is None else str(x.needed_value),
                    unlocks_at_needed=x.unlocks_at_needed,
                )
                for x in r.relaxations
            ],
        )


class ProviderStatusOut(BaseModel):
    provider: str
    display_name: str
    source: FareSource
    bookable: bool
    booking: str
    state: ProviderState
    offers: int
    latency_ms: int | None
    fetched_at: datetime | None
    message: str | None

    @classmethod
    def of(cls, p: ProviderStatus) -> "ProviderStatusOut":
        return cls(
            provider=p.provider,
            display_name=p.display_name,
            source=p.source,
            bookable=p.bookable,
            booking=p.booking,
            state=p.state,
            offers=p.offers,
            latency_ms=p.latency_ms,
            fetched_at=p.fetched_at,
            message=p.message,
        )


class SummaryOut(BaseModel):
    received: int
    invalid: int
    duplicates_removed: int
    qualifying: int
    eliminated: int


class SearchResponse(BaseModel):
    search_key: str = Field(description="Upstream cache key (same for equivalent searches)")
    trip_type: TripType
    currency: str
    is_demo: bool
    cache_available: bool
    generated_at: datetime
    providers: list[ProviderStatusOut]
    summary: SummaryOut
    constraints: ConstraintReportOut
    recommendations: RecommendationsOut
    offers: list[OfferOut] = Field(description="Qualifying offers, best overall match first")

    @classmethod
    def of(cls, r: SearchResult) -> "SearchResponse":
        out = r.outcome
        recs = out.recommendations
        return cls(
            search_key=out.query.cache_key(),
            trip_type=out.query.trip_type,
            currency=out.query.currency,
            is_demo=r.is_demo,
            cache_available=r.cache_available,
            generated_at=r.generated_at,
            providers=[ProviderStatusOut.of(p) for p in r.providers],
            summary=SummaryOut(
                received=out.received,
                invalid=len(out.dropped),
                duplicates_removed=out.duplicates_removed,
                qualifying=len(out.ranked),
                eliminated=len(out.eliminated),
            ),
            constraints=ConstraintReportOut.of(out.constraints),
            recommendations=RecommendationsOut(
                cheapest=PickOut.of(recs.cheapest),
                best_match=PickOut.of(recs.best_match),
                alternatives=[a for a in (PickOut.of(p) for p in recs.alternatives) if a],
            ),
            offers=[OfferOut.of(s) for s in out.ranked],
        )


class AirportOut(BaseModel):
    iata: str
    name: str
    city: str
    country: str
    tz: str
    nearby: list[str]

    @classmethod
    def of(cls, a: Airport, nearby: frozenset[str]) -> "AirportOut":
        return cls(
            iata=a.iata, name=a.name, city=a.city, country=a.country, tz=a.tz, nearby=sorted(nearby)
        )


class ProviderInfoOut(BaseModel):
    provider: str
    display_name: str
    source: FareSource
    bookable: bool
    booking: str
    circuit_open: bool
    currencies: list[str]
