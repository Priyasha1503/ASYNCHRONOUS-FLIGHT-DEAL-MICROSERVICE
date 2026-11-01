from decimal import Decimal

from app.domain.constraints import Constraint, apply_constraints, violations
from app.domain.query import Preferences, TimeWindow
from tests.unit.factories import make_offer


def test_budget_is_never_exceeded_and_boundary_is_inclusive() -> None:
    offers = [make_offer(p, oid=p) for p in ("299.99", "300.00", "300.01", "950.00")]
    res = apply_constraints(offers, Preferences(max_price=Decimal("300")))
    assert sorted(o.total_amount for o in res.qualifying) == [Decimal("299.99"), Decimal("300.00")]
    assert all(o.total_amount <= Decimal("300") for o in res.qualifying)
    assert res.report.failed_by == {Constraint.BUDGET: 2}


def test_required_bag_distinguishes_unknown_from_excluded() -> None:
    prefs = Preferences(require_checked_bag=True)
    assert violations(make_offer(bags=1), prefs) == []
    assert violations(make_offer(bags=0), prefs) == [Constraint.CHECKED_BAG]
    assert violations(make_offer(bags=None), prefs) == [Constraint.BAG_UNCONFIRMED]
    # Without the requirement, baggage never excludes anything.
    assert violations(make_offer(bags=None), Preferences()) == []


def test_excluded_airline_on_any_segment() -> None:
    offer = make_offer(stops=1, carriers=("Q7", "K5"))
    assert violations(offer, Preferences(excluded_airlines=frozenset({"K5"}))) == [
        Constraint.EXCLUDED_AIRLINE
    ]
    assert violations(offer, Preferences(excluded_airlines=frozenset({"T2"}))) == []


def test_stops_and_duration_are_per_direction() -> None:
    one_stop = make_offer(stops=1, leg_minutes=300, layover_minutes=60)  # 11h journey
    assert violations(one_stop, Preferences(max_stops=0)) == [Constraint.MAX_STOPS]
    assert violations(one_stop, Preferences(max_stops=1)) == []
    assert violations(one_stop, Preferences(max_duration_minutes=600)) == [Constraint.MAX_DURATION]
    assert violations(one_stop, Preferences(max_duration_minutes=660)) == []


def test_time_windows_only_exclude_when_strict() -> None:
    late = make_offer(dep_hour=22)
    window = TimeWindow(start_hour=6, end_hour=12)
    assert violations(late, Preferences(departure_window=window)) == []
    assert violations(late, Preferences(departure_window=window, time_windows_strict=True)) == [
        Constraint.DEPARTURE_WINDOW
    ]


def test_report_and_relaxations_when_nothing_qualifies() -> None:
    offers = [
        make_offer("520.00", oid="a"),  # budget only
        make_offer("480.00", oid="b"),  # budget only
        make_offer("350.00", oid="c", stops=1),  # stops only
        make_offer("900.00", oid="d", stops=2),  # budget + stops
    ]
    res = apply_constraints(offers, Preferences(max_price=Decimal("400"), max_stops=0))
    assert res.qualifying == []
    r = res.report
    assert (r.total, r.qualifying) == (4, 0)
    assert r.failed_by == {Constraint.BUDGET: 3, Constraint.MAX_STOPS: 2}
    relax = {x.constraint: x for x in r.relaxations}
    # Raising the budget to 480 unlocks the cheapest budget-only offer; 2 offers in total.
    assert relax[Constraint.BUDGET].unlocks == 2
    assert relax[Constraint.BUDGET].needed_value == Decimal("480.00")
    # Raising the budget only to 480 adds just the 480 offer, not the 520 one.
    assert relax[Constraint.BUDGET].unlocks_at_needed == 1
    assert relax[Constraint.MAX_STOPS].unlocks == 1
    assert relax[Constraint.MAX_STOPS].needed_value == 1
    assert relax[Constraint.MAX_STOPS].unlocks_at_needed == 1
    # The offer failing two constraints is never presented as a one-step relaxation.
    assert sum(x.unlocks for x in r.relaxations) == 3
