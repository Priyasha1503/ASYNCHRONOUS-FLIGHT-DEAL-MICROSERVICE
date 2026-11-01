import pytest

from app.domain.query import Preferences, TimeWindow
from app.domain.ranking import (
    Factor,
    PickKind,
    RankingWeights,
    recommend,
    score_offers,
)
from tests.unit.factories import make_offer

CHEAP_SLOW = make_offer("300.00", oid="cheap", stops=2, leg_minutes=300, bags=0)
MID = make_offer("420.00", oid="mid", stops=1, leg_minutes=330, bags=1)
FAST = make_offer("610.00", oid="fast", stops=0, leg_minutes=420, bags=None)
OFFERS = [CHEAP_SLOW, MID, FAST]


def test_price_only_weights_make_best_match_the_cheapest() -> None:
    w = RankingWeights(price=1, duration=0, stops=0, baggage=0, airline=0, schedule=0)
    ranked = score_offers(OFFERS, Preferences(), w)
    assert ranked[0].offer.id == "test:cheap"
    assert ranked[0].score == 100.0 and ranked[-1].score == 0.0


def test_duration_heavy_weights_prefer_the_fastest() -> None:
    w = RankingWeights(price=0.1, duration=0.9, stops=0, baggage=0, airline=0, schedule=0)
    assert score_offers(OFFERS, Preferences(), w)[0].offer.id == "test:fast"


def test_components_explain_the_score() -> None:
    for s in score_offers(OFFERS, Preferences()):
        assert sum(c.weight for c in s.components) == pytest.approx(1.0, abs=1e-3)
        assert s.score == pytest.approx(100 * sum(c.contribution for c in s.components), abs=0.11)
        assert all(0.0 <= c.score <= 1.0 and c.note for c in s.components)


def test_unconfirmed_baggage_earns_no_credit() -> None:
    fast = next(s for s in score_offers(OFFERS, Preferences()) if s.offer.id == "test:fast")
    bag = next(c for c in fast.components if c.factor is Factor.BAGGAGE)
    assert bag.score == 0.0 and "not confirmed" in bag.note


def test_optional_factors_only_active_when_requested() -> None:
    plain = {c.factor for c in score_offers(OFFERS, Preferences())[0].components}
    assert Factor.AIRLINE not in plain and Factor.SCHEDULE not in plain
    prefs = Preferences(
        preferred_airlines=frozenset({"Q7"}), departure_window=TimeWindow(start_hour=6, end_hour=12)
    )
    factors = {c.factor for c in score_offers(OFFERS, prefs)[0].components}
    assert {Factor.AIRLINE, Factor.SCHEDULE} <= factors
    # Strict windows are hard constraints, so they no longer influence ranking.
    strict = prefs.model_copy(update={"time_windows_strict": True})
    assert Factor.SCHEDULE not in {c.factor for c in score_offers(OFFERS, strict)[0].components}


def test_ranking_is_deterministic_with_ties() -> None:
    twins = [make_offer("400.00", oid=x) for x in ("b", "a", "c")]
    ids = [s.offer.id for s in score_offers(twins, Preferences())]
    assert ids == ["test:a", "test:b", "test:c"]


def test_invalid_weights_rejected() -> None:
    with pytest.raises(ValueError):
        RankingWeights(price=-1)
    with pytest.raises(ValueError):
        RankingWeights(0, 0, 0, 0, 0, 0)


def test_recommend_buckets() -> None:
    recs = recommend(score_offers(OFFERS, Preferences()))
    assert recs.cheapest and recs.cheapest.scored.offer.id == "test:cheap"
    assert recs.best_match is not None
    assert all(r for r in recs.cheapest.reasons)
    kinds = {p.kind: p.scored.offer.id for p in recs.alternatives}
    # Nonstop "fast" is faster and has fewer stops than both picks → offered as a trade-off once.
    assert "test:fast" in kinds.values()
    assert len(recs.alternatives) <= 3
    # Alternatives are distinct from each other and from the two headline picks.
    alt_ids = list(kinds.values())
    assert len(alt_ids) == len(set(alt_ids))
    assert not set(alt_ids) & {recs.cheapest.scored.offer.id, recs.best_match.scored.offer.id}
    assert all(p.reasons for p in recs.alternatives)


def test_bag_alternative_only_when_picks_lack_a_confirmed_bag() -> None:
    no_bag = make_offer("300.00", oid="nobag", bags=0)
    with_bag = make_offer("340.00", oid="bag", bags=1, dep_hour=11)
    recs = recommend(score_offers([no_bag, with_bag], Preferences()))
    picks = {recs.cheapest.scored.offer.id, recs.best_match.scored.offer.id}  # type: ignore[union-attr]
    if "test:bag" not in picks:
        assert any(p.kind is PickKind.WITH_BAG for p in recs.alternatives)


def test_single_and_empty_inputs() -> None:
    assert recommend([]).cheapest is None
    recs = recommend(score_offers([MID], Preferences()))
    assert recs.cheapest and recs.best_match
    assert recs.cheapest.scored.offer.id == recs.best_match.scored.offer.id == "test:mid"
    assert "Also the best overall match" in " ".join(recs.cheapest.reasons)
    assert recs.alternatives == []
