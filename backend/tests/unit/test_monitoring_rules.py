from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.monitoring import (
    Check,
    EventKind,
    RuleConfig,
    RuleState,
    evaluate_rule,
    price_band,
)

SLOT = datetime(2026, 11, 1, 12, tzinfo=UTC)
D = Decimal


def check(price: str | None, qualifying: int = 5, hours: int = 0) -> Check:
    return Check(None if price is None else D(price), qualifying, SLOT + timedelta(hours=hours))


def kinds(events: list) -> list[EventKind]:  # type: ignore[type-arg]
    return [e.kind for e in events]


def test_below_target_fires_once_per_price_band() -> None:
    cfg = RuleConfig(target_price=D("500"), drop_threshold_pct=None, notify_new_qualifying=False)
    e1, s1 = evaluate_rule(cfg, RuleState(), check("498.40"))
    assert kinds(e1) == [EventKind.BELOW_TARGET]
    # Same band (step = 5 for a 500 target) → identical dedup key → DB constraint blocks a repeat.
    e2, _ = evaluate_rule(cfg, s1, check("497.10", hours=1))
    assert e2[0].dedup_key == e1[0].dedup_key
    # A meaningful further drop lands in a new band → new key → new alert.
    e3, _ = evaluate_rule(cfg, s1, check("470.00", hours=2))
    assert e3[0].dedup_key != e1[0].dedup_key
    # Above target → nothing.
    assert evaluate_rule(cfg, s1, check("500.01"))[0] == []


def test_changing_the_target_can_alert_again() -> None:
    a = RuleConfig(D("500"), None, False)
    b = RuleConfig(D("520"), None, False)
    ka = evaluate_rule(a, RuleState(), check("490"))[0][0].dedup_key
    kb = evaluate_rule(b, RuleState(), check("490"))[0][0].dedup_key
    assert ka != kb


def test_price_drop_threshold() -> None:
    cfg = RuleConfig(None, drop_threshold_pct=D("10"), notify_new_qualifying=False)
    state = RuleState(last_price=D("600"), best_price=D("600"), last_qualifying=3)
    assert evaluate_rule(cfg, state, check("545"))[0] == []  # 9.2% < 10%
    events, new = evaluate_rule(cfg, state, check("540"))  # exactly 10%
    assert kinds(events) == [EventKind.PRICE_DROP]
    assert events[0].previous == D("600") and events[0].price == D("540")
    assert new.last_price == D("540") and new.best_price == D("540")
    # No previous price (first check) → no drop event, whatever the price.
    assert evaluate_rule(cfg, RuleState(), check("1"))[0] == []


def test_now_available_only_on_transition() -> None:
    cfg = RuleConfig(None, None, notify_new_qualifying=True)
    # First ever check: unknown before → not a transition.
    assert evaluate_rule(cfg, RuleState(), check("400"))[0] == []
    none_before = RuleState(last_price=None, best_price=D("420"), last_qualifying=0)
    events, new = evaluate_rule(cfg, none_before, check("400"))
    assert kinds(events) == [EventKind.NOW_AVAILABLE]
    assert new.last_qualifying == 5
    # Still available on the next check → no repeat.
    assert evaluate_rule(cfg, new, check("390", hours=1))[0] == []


def test_nothing_qualifies_updates_state_without_events() -> None:
    cfg = RuleConfig(D("500"), D("5"), True)
    events, new = evaluate_rule(cfg, RuleState(D("480"), D("450"), 2), check(None, qualifying=0))
    assert events == []
    assert new == RuleState(last_price=None, best_price=D("450"), last_qualifying=0)


def test_price_band_has_a_minimum_step() -> None:
    assert price_band(D("99.99"), D("50")) == 99  # step clamps to 1 unit
    assert price_band(D("1234"), D("10000")) == 12  # step = 100
