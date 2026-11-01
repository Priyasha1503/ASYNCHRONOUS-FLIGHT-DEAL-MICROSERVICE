"""Pure search pipeline: offers from any providers → normalized, filtered, ranked, recommended.

No I/O. The search service (Phase 3) handles provider calls, caching and statuses, then calls
`evaluate`. Keeping this pure means the exact same logic serves interactive search, monitoring
refreshes and tests.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.airports import nearby
from app.domain.constraints import Constraint, ConstraintReport, apply_constraints
from app.domain.offers import Offer
from app.domain.query import Preferences, UpstreamQuery
from app.domain.ranking import (
    DEFAULT_WEIGHTS,
    RankingWeights,
    Recommendations,
    ScoredOffer,
    recommend,
    score_offers,
)
from app.domain.validation import DroppedOffer, normalize


@dataclass(slots=True)
class SearchOutcome:
    query: UpstreamQuery
    preferences: Preferences
    received: int
    dropped: list[DroppedOffer]
    duplicates_removed: int
    constraints: ConstraintReport
    ranked: list[ScoredOffer]  # qualifying offers, best score first
    eliminated: list[tuple[Offer, list[Constraint]]]
    recommendations: Recommendations

    @property
    def has_results(self) -> bool:
        return bool(self.ranked)


def allowed_airports(code: str, include_nearby: bool) -> frozenset[str]:
    return frozenset({code}) | (nearby(code) if include_nearby else frozenset())


def evaluate(
    query: UpstreamQuery,
    preferences: Preferences,
    offers: Iterable[Offer],
    *,
    include_nearby: bool = False,
    weights: RankingWeights = DEFAULT_WEIGHTS,
) -> SearchOutcome:
    offers = list(offers)
    norm = normalize(
        offers,
        query,
        origins=allowed_airports(query.origin, include_nearby),
        destinations=allowed_airports(query.destination, include_nearby),
    )
    filtered = apply_constraints(norm.offers, preferences)
    ranked = score_offers(filtered.qualifying, preferences, weights)
    return SearchOutcome(
        query=query,
        preferences=preferences,
        received=len(offers),
        dropped=norm.dropped,
        duplicates_removed=norm.duplicates_removed,
        constraints=filtered.report,
        ranked=ranked,
        eliminated=filtered.eliminated,
        recommendations=recommend(ranked),
    )
