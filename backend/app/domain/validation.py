"""Semantic validation and de-duplication of normalized offers.

Pydantic guarantees *shape* (types, tz-aware times, https links). This module checks that an offer
is actually an answer to the query and internally consistent. Invalid offers are dropped *with a
reason* so provider data-quality problems are visible, never silently absorbed.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import pairwise

from app.domain.money import MINOR_UNITS
from app.domain.offers import FareSource, Offer
from app.domain.query import UpstreamQuery

MIN_CONNECTION = timedelta(minutes=30)
MAX_CONNECTION = timedelta(hours=24)
MAX_SEGMENT = timedelta(hours=20)
MAX_JOURNEY = timedelta(hours=72)


@dataclass(frozen=True, slots=True)
class DroppedOffer:
    offer_id: str
    provider: str
    reasons: tuple[str, ...]


@dataclass(slots=True)
class Normalized:
    offers: list[Offer]
    dropped: list[DroppedOffer] = field(default_factory=list)
    duplicates_removed: int = 0


def validate_offer(
    offer: Offer,
    query: UpstreamQuery,
    *,
    origins: frozenset[str] | None = None,
    destinations: frozenset[str] | None = None,
) -> list[str]:
    """Return machine-readable issue codes; empty list means valid."""
    origins = origins or frozenset({query.origin})
    destinations = destinations or frozenset({query.destination})
    issues: list[str] = []

    if offer.currency != query.currency:
        issues.append("currency_mismatch")
    if offer.total_amount <= 0:
        issues.append("non_positive_price")
    exp = offer.total_amount.as_tuple().exponent
    if isinstance(exp, int) and -exp > MINOR_UNITS.get(offer.currency, 2):
        issues.append("price_precision")
    if offer.cabin != query.cabin:
        issues.append("cabin_mismatch")

    expected_slices = 2 if query.return_date else 1
    if len(offer.slices) != expected_slices:
        issues.append("slice_count")
        return issues  # the remaining checks assume the right shape

    out = offer.outbound
    if out.origin not in origins or out.destination not in destinations:
        issues.append("route_mismatch")
    if out.departure_at.date() != query.depart_date:  # local date at the origin airport
        issues.append("wrong_departure_date")
    if (back := offer.inbound) is not None:
        if back.origin not in destinations or back.destination not in origins:
            issues.append("return_route_mismatch")
        if back.departure_at.date() != query.return_date:
            issues.append("wrong_return_date")
        if back.departure_at <= out.arrival_at:
            issues.append("return_before_arrival")

    for s in offer.slices:
        # A summary slice's single "segment" is the whole journey (connections included).
        limit = MAX_JOURNEY if s.detail == "summary" else MAX_SEGMENT
        for seg in s.segments:
            if seg.arrival_at <= seg.departure_at:
                issues.append("segment_time_order")
            elif seg.arrival_at - seg.departure_at > limit:
                issues.append("segment_too_long")
        for a, b in pairwise(s.segments):
            if a.destination != b.origin:
                issues.append("disconnected_segments")
            gap = b.departure_at - a.arrival_at
            if gap < MIN_CONNECTION:
                issues.append("connection_too_short")
            elif gap > MAX_CONNECTION:
                issues.append("connection_too_long")

    return sorted(set(issues))


_SOURCE_PREFERENCE = {
    FareSource.LIVE: 0,
    FareSource.CACHED: 1,
    FareSource.OBSERVED: 2,
    FareSource.DEMO: 3,
    FareSource.HISTORICAL: 4,
}


def dedupe(offers: Iterable[Offer]) -> tuple[list[Offer], int]:
    """Collapse offers for the same itinerary (by fingerprint). Keeps the cheapest; on equal price
    prefers the more trustworthy source, then the freshest, then a stable id order."""
    best: dict[str, Offer] = {}
    total = 0
    for o in offers:
        total += 1
        cur = best.get(o.fingerprint)
        if cur is None or _rank(o) < _rank(cur):
            best[o.fingerprint] = o
    unique = sorted(best.values(), key=lambda o: (o.total_amount, o.id))
    return unique, total - len(unique)


def _rank(o: Offer) -> tuple[object, ...]:
    return (o.total_amount, _SOURCE_PREFERENCE[o.source], -o.fetched_at.timestamp(), o.id)


def normalize(
    offers: Iterable[Offer],
    query: UpstreamQuery,
    *,
    origins: frozenset[str] | None = None,
    destinations: frozenset[str] | None = None,
) -> Normalized:
    valid: list[Offer] = []
    dropped: list[DroppedOffer] = []
    for o in offers:
        if issues := validate_offer(o, query, origins=origins, destinations=destinations):
            dropped.append(DroppedOffer(o.id, o.provider, tuple(issues)))
        else:
            valid.append(o)
    unique, dupes = dedupe(valid)
    return Normalized(offers=unique, dropped=dropped, duplicates_removed=dupes)
