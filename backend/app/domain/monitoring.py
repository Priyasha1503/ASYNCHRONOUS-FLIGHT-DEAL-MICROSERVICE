"""Pure monitoring-rule evaluation: (rule config, previous state, fresh check) → events + new state.

Dedup keys are deterministic so that re-evaluating the same situation can never alert twice
(enforced by UNIQUE(rule_id, dedup_key)), while a genuinely new situation — a further drop into a
lower price band, a changed target — produces a new key and therefore a new alert.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum

# Allowed check frequencies (minutes → label). The effective schedule is also bounded below by
# MONITOR_MIN_INTERVAL_MINUTES so provider quotas are respected.
FREQUENCIES: dict[int, str] = {
    60: "Hourly",
    360: "Every 6 hours",
    720: "Every 12 hours",
    1440: "Daily",
}


class EventKind(StrEnum):
    BELOW_TARGET = "below_target"
    PRICE_DROP = "price_drop"
    NOW_AVAILABLE = "now_available"


@dataclass(frozen=True, slots=True)
class RuleConfig:
    target_price: Decimal | None
    drop_threshold_pct: Decimal | None
    notify_new_qualifying: bool


@dataclass(frozen=True, slots=True)
class RuleState:
    last_price: Decimal | None = None
    best_price: Decimal | None = None
    last_qualifying: int | None = None  # None = never checked


@dataclass(frozen=True, slots=True)
class Check:
    """The cheapest offer meeting the rule's hard requirements in one refresh run."""

    cheapest: Decimal | None
    qualifying: int
    run_slot: datetime


@dataclass(frozen=True, slots=True)
class Event:
    kind: EventKind
    dedup_key: str
    price: Decimal
    previous: Decimal | None = None
    target: Decimal | None = None


def price_band(price: Decimal, reference: Decimal) -> int:
    """Bucket prices into ~1% steps of the reference (min 1 currency unit), so small jitter around a
    level doesn't re-alert but a meaningful further drop does."""
    step = max(Decimal(1), (reference / 100).quantize(Decimal(1), rounding=ROUND_FLOOR))
    return int((price / step).to_integral_value(rounding=ROUND_FLOOR))


def evaluate_rule(
    config: RuleConfig, state: RuleState, check: Check
) -> tuple[list[Event], RuleState]:
    events: list[Event] = []
    p = check.cheapest

    if p is not None:
        if config.target_price is not None and p <= config.target_price:
            band = price_band(p, config.target_price)
            events.append(
                Event(
                    EventKind.BELOW_TARGET,
                    f"below_target:{config.target_price}:{band}",
                    price=p,
                    previous=state.last_price,
                    target=config.target_price,
                )
            )
        if (
            config.drop_threshold_pct is not None
            and state.last_price is not None
            and p < state.last_price
        ):
            drop_pct = (state.last_price - p) / state.last_price * 100
            if drop_pct >= config.drop_threshold_pct:
                events.append(
                    Event(
                        EventKind.PRICE_DROP,
                        f"price_drop:{state.last_price}->{p}",
                        price=p,
                        previous=state.last_price,
                    )
                )
        # Only a *transition* from "nothing qualifies" (on a previous check) to "something does".
        if config.notify_new_qualifying and state.last_qualifying == 0 and check.qualifying > 0:
            events.append(
                Event(
                    EventKind.NOW_AVAILABLE,
                    f"now_available:{check.run_slot.isoformat()}",
                    price=p,
                )
            )

    best = state.best_price
    if p is not None and (best is None or p < best):
        best = p
    new_state = RuleState(last_price=p, best_price=best, last_qualifying=check.qualifying)
    return events, new_state
