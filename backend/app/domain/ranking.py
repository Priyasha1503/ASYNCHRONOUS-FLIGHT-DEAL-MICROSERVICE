"""Explainable soft-preference ranking over offers that already passed every hard constraint.

score = Σ wᵢ · sᵢ over the *active* factors, with weights renormalized to sum to 1 and each factor
score sᵢ ∈ [0, 1] (1 = best). Price and duration are min-max normalized across the candidate set, so
scores are relative to what's actually available. Unconfirmed data earns no credit (an unknown
baggage allowance scores 0, with a note) — the ranking never rewards a fact it can't verify.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.domain.offers import Offer
from app.domain.query import Preferences


class Factor(StrEnum):
    PRICE = "price"
    DURATION = "duration"
    STOPS = "stops"
    BAGGAGE = "baggage"
    AIRLINE = "airline"  # active only when the user has preferred airlines
    SCHEDULE = "schedule"  # active only for soft (non-strict) time windows


@dataclass(frozen=True, slots=True)
class RankingWeights:
    price: float = 0.45
    duration: float = 0.20
    stops: float = 0.15
    baggage: float = 0.10
    airline: float = 0.05
    schedule: float = 0.05

    def __post_init__(self) -> None:
        values = [getattr(self, f.value) for f in Factor]
        if any(v < 0 for v in values) or sum(values) <= 0:
            raise ValueError("ranking weights must be non-negative and not all zero")

    def of(self, factor: Factor) -> float:
        return float(getattr(self, factor.value))


DEFAULT_WEIGHTS = RankingWeights()


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    factor: Factor
    weight: float  # effective (renormalized) weight
    score: float  # 0..1
    note: str

    @property
    def contribution(self) -> float:
        return self.weight * self.score


@dataclass(frozen=True, slots=True)
class ScoredOffer:
    offer: Offer
    score: float  # 0..100
    components: tuple[ScoreComponent, ...]


def fmt_minutes(m: int) -> str:
    h, mm = divmod(abs(m), 60)
    return f"{h}h {mm:02d}m" if h else f"{mm}m"


def fmt_money(amount: Decimal, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _minmax(value: float, lo: float, hi: float) -> float:
    return 1.0 if hi == lo else (hi - value) / (hi - lo)


def _active_factors(prefs: Preferences, weights: RankingWeights) -> dict[Factor, float]:
    active = [Factor.PRICE, Factor.DURATION, Factor.STOPS, Factor.BAGGAGE]
    if prefs.preferred_airlines:
        active.append(Factor.AIRLINE)
    if not prefs.time_windows_strict and (prefs.departure_window or prefs.arrival_window):
        active.append(Factor.SCHEDULE)
    raw = {f: weights.of(f) for f in active if weights.of(f) > 0}
    if not raw:  # e.g. only airline weight set but no preferred airlines
        raw = {Factor.PRICE: 1.0}
    total = sum(raw.values())
    return {f: w / total for f, w in raw.items()}


def score_offers(
    offers: Sequence[Offer], prefs: Preferences, weights: RankingWeights = DEFAULT_WEIGHTS
) -> list[ScoredOffer]:
    if not offers:
        return []
    active = _active_factors(prefs, weights)
    prices = [float(o.total_amount) for o in offers]
    durations = [o.total_duration_minutes for o in offers]
    p_lo, p_hi = min(prices), max(prices)
    d_lo, d_hi = min(durations), max(durations)
    cheapest = min(o.total_amount for o in offers)
    currency = offers[0].currency

    scored: list[ScoredOffer] = []
    for o in offers:
        comps: list[ScoreComponent] = []
        for f, w in active.items():
            s, note = _factor(f, o, prefs, p_lo, p_hi, d_lo, d_hi, cheapest, currency)
            comps.append(ScoreComponent(f, round(w, 4), round(s, 4), note))
        total = round(100 * sum(c.weight * c.score for c in comps), 1)
        scored.append(ScoredOffer(o, total, tuple(comps)))

    scored.sort(key=lambda s: (-s.score, s.offer.total_amount, s.offer.id))
    return scored


def _factor(
    f: Factor,
    o: Offer,
    prefs: Preferences,
    p_lo: float,
    p_hi: float,
    d_lo: int,
    d_hi: int,
    cheapest: Decimal,
    currency: str,
) -> tuple[float, str]:
    match f:
        case Factor.PRICE:
            diff = o.total_amount - cheapest
            note = (
                f"{fmt_money(o.total_amount, currency)} — lowest available"
                if diff == 0
                else f"{fmt_money(o.total_amount, currency)} (+{fmt_money(diff, currency)})"
            )
            return _minmax(float(o.total_amount), p_lo, p_hi), note
        case Factor.DURATION:
            d = o.total_duration_minutes
            extra = d - d_lo
            note = f"{fmt_minutes(d)} total" + (
                " — fastest" if extra == 0 else f" (+{fmt_minutes(extra)})"
            )
            return _minmax(d, d_lo, d_hi), note
        case Factor.STOPS:
            avg = sum(s.stops for s in o.slices) / len(o.slices)
            label = (
                "Nonstop"
                if o.max_stops == 0
                else f"Up to {o.max_stops} stop" + ("s" if o.max_stops > 1 else "")
            )
            return max(0.0, 1.0 - 0.5 * avg), label
        case Factor.BAGGAGE:
            bags = o.baggage.checked_bags
            if bags is None:
                return 0.0, "Checked bag not confirmed by provider — no credit given"
            if bags >= 1:
                return 1.0, f"{bags} checked bag{'s' if bags > 1 else ''} included"
            return 0.0, "No checked bag included"
        case Factor.AIRLINE:
            segs = [seg for s in o.slices for seg in s.segments]
            hits = sum(seg.carrier_code in prefs.preferred_airlines for seg in segs)
            return hits / len(segs), f"{hits} of {len(segs)} flights on preferred airlines"
        case Factor.SCHEDULE:
            checks: list[bool] = []
            out = o.outbound
            if prefs.departure_window:
                checks.append(
                    prefs.departure_window.contains(out.departure_at.hour, out.departure_at.minute)
                )
            if prefs.arrival_window:
                checks.append(
                    prefs.arrival_window.contains(out.arrival_at.hour, out.arrival_at.minute)
                )
            ok = sum(checks)
            return ok / len(checks), f"Matches {ok} of {len(checks)} preferred time window(s)"
    raise AssertionError(f"unhandled factor {f}")  # pragma: no cover


# ── Recommendation buckets ───────────────────────────────────────────────────


class PickKind(StrEnum):
    CHEAPEST = "cheapest"
    BEST_MATCH = "best_match"
    FASTEST = "fastest"
    FEWEST_STOPS = "fewest_stops"
    WITH_BAG = "with_checked_bag"


@dataclass(frozen=True, slots=True)
class Pick:
    kind: PickKind
    scored: ScoredOffer
    reasons: tuple[str, ...]


@dataclass(slots=True)
class Recommendations:
    cheapest: Pick | None = None
    best_match: Pick | None = None
    alternatives: list[Pick] = field(default_factory=list)


MAX_ALTERNATIVES = 3


def recommend(ranked: Sequence[ScoredOffer]) -> Recommendations:
    """Pick the cheapest qualifying offer, the best overall match, and up to three genuine
    trade-offs relative to them. `ranked` must contain only offers that passed hard constraints."""
    if not ranked:
        return Recommendations()

    n = len(ranked)
    cur = ranked[0].offer.currency
    cheapest = min(
        ranked, key=lambda s: (s.offer.total_amount, s.offer.total_duration_minutes, s.offer.id)
    )
    best = ranked[0]  # already sorted by score desc, then price, then id

    cheap_reasons = [
        f"Lowest price of the {n} offer{'s' if n > 1 else ''} that meet all your requirements"
    ]
    if best.offer.id == cheapest.offer.id:
        cheap_reasons.append("Also the best overall match for your preferences")

    top = sorted(best.components, key=lambda c: -c.contribution)[:2]
    best_reasons = [f"Highest overall score ({best.score:g}/100)"] + [
        f"{c.factor.value.capitalize()}: {c.note}" for c in top
    ]
    if best.offer.id != cheapest.offer.id:
        diff = best.offer.total_amount - cheapest.offer.total_amount
        best_reasons.append(f"{fmt_money(diff, cur)} more than the cheapest option")

    recs = Recommendations(
        cheapest=Pick(PickKind.CHEAPEST, cheapest, tuple(cheap_reasons)),
        best_match=Pick(PickKind.BEST_MATCH, best, tuple(best_reasons)),
    )
    chosen = {cheapest.offer.id, best.offer.id}
    anchors = [cheapest.offer, best.offer]

    def add(kind: PickKind, s: ScoredOffer, reasons: list[str]) -> None:
        if len(recs.alternatives) < MAX_ALTERNATIVES and s.offer.id not in chosen:
            recs.alternatives.append(Pick(kind, s, tuple(reasons)))
            chosen.add(s.offer.id)

    def premium(o: Offer) -> str:
        diff = o.total_amount - cheapest.offer.total_amount
        return (
            "same price as the cheapest"
            if diff == 0
            else f"+{fmt_money(diff, cur)} vs the cheapest"
        )

    # Fastest — only if genuinely faster than both picks.
    fastest = min(
        ranked, key=lambda s: (s.offer.total_duration_minutes, s.offer.total_amount, s.offer.id)
    )
    shortest_anchor = min(a.total_duration_minutes for a in anchors)
    if fastest.offer.total_duration_minutes < shortest_anchor:
        saved = shortest_anchor - fastest.offer.total_duration_minutes
        add(
            PickKind.FASTEST,
            fastest,
            [f"{fmt_minutes(saved)} faster than the recommended options", premium(fastest.offer)],
        )

    # Fewest stops — only if fewer than both picks.
    fewest = min(ranked, key=lambda s: (s.offer.max_stops, s.offer.total_amount, s.offer.id))
    if fewest.offer.max_stops < min(a.max_stops for a in anchors):
        label = (
            "Nonstop" if fewest.offer.max_stops == 0 else f"Only {fewest.offer.max_stops} stop(s)"
        )
        add(
            PickKind.FEWEST_STOPS,
            fewest,
            [f"{label} — the recommended options have more", premium(fewest.offer)],
        )

    # Confirmed checked bag — only if neither pick confirms one.
    if all((a.baggage.checked_bags or 0) < 1 for a in anchors):
        with_bag = [s for s in ranked if (s.offer.baggage.checked_bags or 0) >= 1]
        if with_bag:
            b = min(with_bag, key=lambda s: (s.offer.total_amount, s.offer.id))
            add(PickKind.WITH_BAG, b, ["Includes a confirmed checked bag", premium(b.offer)])

    return recs
