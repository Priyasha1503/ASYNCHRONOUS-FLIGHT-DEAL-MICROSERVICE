"""Hard-constraint filtering with an explainable elimination report.

An offer qualifies only if it violates *no* hard constraint. Nothing is ever silently relaxed:
when offers are eliminated, the report says which constraint removed how many, and (for offers
blocked by exactly one constraint) what relaxing it would unlock, so the UI can offer deliberate
relaxations.
"""

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.domain.offers import Offer
from app.domain.query import Preferences


class Constraint(StrEnum):
    BUDGET = "budget"
    MAX_STOPS = "max_stops"
    CHECKED_BAG = "checked_bag"  # fare confirmed to exclude a checked bag
    BAG_UNCONFIRMED = "bag_unconfirmed"  # bag required but provider didn't confirm inclusion
    MAX_DURATION = "max_duration"
    EXCLUDED_AIRLINE = "excluded_airline"
    DEPARTURE_WINDOW = "departure_window"
    ARRIVAL_WINDOW = "arrival_window"


def violations(offer: Offer, prefs: Preferences) -> list[Constraint]:
    v: list[Constraint] = []
    if prefs.max_price is not None and offer.total_amount > prefs.max_price:
        v.append(Constraint.BUDGET)
    if prefs.max_stops is not None and offer.max_stops > prefs.max_stops:
        v.append(Constraint.MAX_STOPS)
    if prefs.require_checked_bag:
        bags = offer.baggage.checked_bags
        if bags is None:
            v.append(Constraint.BAG_UNCONFIRMED)
        elif bags < 1:
            v.append(Constraint.CHECKED_BAG)
    if prefs.max_duration_minutes is not None and any(
        s.duration_minutes > prefs.max_duration_minutes for s in offer.slices
    ):
        v.append(Constraint.MAX_DURATION)
    if prefs.excluded_airlines & offer.carriers:
        v.append(Constraint.EXCLUDED_AIRLINE)
    if prefs.time_windows_strict:
        out = offer.outbound
        if prefs.departure_window and not prefs.departure_window.contains(
            out.departure_at.hour, out.departure_at.minute
        ):
            v.append(Constraint.DEPARTURE_WINDOW)
        if prefs.arrival_window and not prefs.arrival_window.contains(
            out.arrival_at.hour, out.arrival_at.minute
        ):
            v.append(Constraint.ARRIVAL_WINDOW)
    return v


@dataclass(frozen=True, slots=True)
class Relaxation:
    """What relaxing one constraint (and only that one) would add.

    `unlocks`            offers added by removing the constraint entirely.
    `needed_value`       the smallest new limit that adds at least one offer (numeric limits only).
    `unlocks_at_needed`  offers added by moving the limit to exactly `needed_value` — the honest
                         count to show next to a "raise to X" suggestion.
    """

    constraint: Constraint
    unlocks: int
    needed_value: Decimal | int | None = None
    unlocks_at_needed: int = 0


@dataclass(slots=True)
class ConstraintReport:
    total: int
    qualifying: int
    failed_by: dict[Constraint, int] = field(default_factory=dict)
    relaxations: list[Relaxation] = field(default_factory=list)


@dataclass(slots=True)
class Filtered:
    qualifying: list[Offer]
    eliminated: list[tuple[Offer, list[Constraint]]]
    report: ConstraintReport


def apply_constraints(offers: list[Offer], prefs: Preferences) -> Filtered:
    qualifying: list[Offer] = []
    eliminated: list[tuple[Offer, list[Constraint]]] = []
    failed_by: Counter[Constraint] = Counter()
    only: dict[Constraint, list[Offer]] = {}

    for o in offers:
        v = violations(o, prefs)
        if not v:
            qualifying.append(o)
            continue
        eliminated.append((o, v))
        failed_by.update(v)
        if len(v) == 1:
            only.setdefault(v[0], []).append(o)

    relaxations = [_relaxation(c, blocked) for c, blocked in only.items()]
    relaxations.sort(key=lambda r: (-r.unlocks, r.constraint.value))
    report = ConstraintReport(
        total=len(offers),
        qualifying=len(qualifying),
        failed_by=dict(sorted(failed_by.items(), key=lambda kv: (-kv[1], kv[0].value))),
        relaxations=relaxations,
    )
    return Filtered(qualifying=qualifying, eliminated=eliminated, report=report)


def _measure(c: Constraint, o: Offer) -> Decimal | int | None:
    """The offer's value on the constraint's numeric axis, if it has one."""
    match c:
        case Constraint.BUDGET:
            return o.total_amount
        case Constraint.MAX_STOPS:
            return o.max_stops
        case Constraint.MAX_DURATION:
            return max(s.duration_minutes for s in o.slices)
        case _:
            return None


def _relaxation(c: Constraint, blocked: list[Offer]) -> Relaxation:
    values = [v for o in blocked if (v := _measure(c, o)) is not None]
    if not values:
        return Relaxation(c, len(blocked), None, len(blocked))
    needed = min(values)
    return Relaxation(c, len(blocked), needed, sum(v <= needed for v in values))
