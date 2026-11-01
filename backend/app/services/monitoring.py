"""Saved searches + monitoring: management (API), scheduling (beat) and refresh runs (worker).

Shared schedule: users who monitor the same upstream query share one `MonitoredQuery`, refreshed at
the fastest interval any of its active rules asks for (bounded by MONITOR_MIN_INTERVAL_MINUTES).
Each refresh calls providers once, stores observations once, then evaluates every rule against its
own hard requirements.

Idempotency (a duplicate or retried task must not double-count anything):
  refresh_runs UNIQUE(query, slot) · observations UNIQUE(query, provider, fingerprint, slot)
  rule_checks UNIQUE(rule, run) · notifications UNIQUE(rule, dedup_key)
External calls never happen inside a database transaction.
"""

import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.metrics import MONITOR_REFRESHES, NOTIFICATIONS_CREATED
from app.domain.monitoring import (
    FREQUENCIES,
    Check,
    Event,
    EventKind,
    RuleConfig,
    RuleState,
    evaluate_rule,
)
from app.domain.offers import FareSource, Offer
from app.domain.pipeline import evaluate
from app.domain.query import Preferences, SearchRequest, UpstreamQuery
from app.domain.ranking import fmt_money
from app.models import (
    MonitoredQuery,
    MonitoringRule,
    Notification,
    PriceObservation,
    RefreshRun,
    RuleCheck,
    SavedSearch,
    User,
)
from app.models.base import utcnow
from app.services.search import ProviderState, SearchService

log = logging.getLogger(__name__)


# ── identity helpers ─────────────────────────────────────────────────────────


def canonical_request(req: SearchRequest) -> dict[str, Any]:
    data = req.model_dump(mode="json")
    prefs = data["preferences"]
    for k in ("excluded_airlines", "preferred_airlines"):  # sets serialize in arbitrary order
        prefs[k] = sorted(prefs[k])
    return data


def request_hash(req: SearchRequest) -> str:
    raw = json.dumps(canonical_request(req), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def monitored_key(query: UpstreamQuery, include_nearby: bool) -> str:
    raw = f"{query.cache_key()}|nearby={int(include_nearby)}"
    return "m1:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def slot_for(now: datetime, interval_minutes: int) -> datetime:
    """Epoch-aligned bucket: every worker computes the same slot for the same moment."""
    step = interval_minutes * 60
    return datetime.fromtimestamp(int(now.timestamp()) // step * step, UTC)


def route_label(ss: SavedSearch) -> str:
    return f"{ss.origin} → {ss.destination}"


# ── management (API) ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RuleSettings:
    target_price: Decimal | None
    drop_threshold_pct: Decimal | None
    notify_new_qualifying: bool
    frequency_minutes: int


class MonitoringService:
    def __init__(self, db: Session, settings: Settings, clock: Callable[[], datetime] = utcnow):
        self.db = db
        self.s = settings
        self.clock = clock

    def _check_frequency(self, minutes: int) -> None:
        if minutes not in FREQUENCIES:
            raise ValidationFailed(
                "Unsupported check frequency",
                details=[
                    {
                        "loc": ["body", "frequency_minutes"],
                        "msg": f"one of {sorted(FREQUENCIES)}",
                        "type": "value_error",
                    }
                ],
            )

    def create(
        self, user: User, req: SearchRequest, name: str | None, rs: RuleSettings
    ) -> MonitoringRule:
        self._check_frequency(rs.frequency_minutes)
        active = self.db.scalar(
            select(func.count())
            .select_from(MonitoringRule)
            .where(MonitoringRule.user_id == user.id, MonitoringRule.is_active.is_(True))
        )
        if (active or 0) >= self.s.max_active_monitors_per_user:
            raise Conflict(
                f"You can monitor up to {self.s.max_active_monitors_per_user} trips at once. "
                "Pause or delete one first.",
                details={"reason": "limit_reached"},
            )
        query = req.to_query()
        h = request_hash(req)
        ss = self.db.scalar(
            select(SavedSearch).where(SavedSearch.user_id == user.id, SavedSearch.request_hash == h)
        )
        if ss is not None and ss.rule is not None:
            raise Conflict(
                "You're already monitoring this exact search.", details={"rule_id": str(ss.rule.id)}
            )
        if ss is None:
            ss = SavedSearch(
                user_id=user.id,
                name=(name or f"{query.origin} → {query.destination}")[:120],
                request=canonical_request(req),
                request_hash=h,
                origin=query.origin,
                destination=query.destination,
                depart_date=query.depart_date,
                return_date=query.return_date,
                currency=query.currency,
            )
            self.db.add(ss)
            self.db.flush()

        mq = self._get_or_create_query(query, req.include_nearby, rs.frequency_minutes)
        rule = MonitoringRule(
            user_id=user.id,
            saved_search_id=ss.id,
            monitored_query_id=mq.id,
            target_price=rs.target_price,
            drop_threshold_pct=rs.drop_threshold_pct,
            notify_new_qualifying=rs.notify_new_qualifying,
            frequency_minutes=rs.frequency_minutes,
            is_active=True,
        )
        self.db.add(rule)
        self.db.flush()
        self._recompute(mq, first_check_now=True)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def _get_or_create_query(
        self, query: UpstreamQuery, nearby: bool, minutes: int
    ) -> MonitoredQuery:
        key = monitored_key(query, nearby)
        self.db.execute(
            insert(MonitoredQuery)
            .values(
                id=uuid.uuid4(),
                query_key=key,
                query={"query": json.loads(query.model_dump_json()), "include_nearby": nearby},
                include_nearby=nearby,
                interval_minutes=max(minutes, self.s.monitor_min_interval_minutes),
                active_rules=0,
            )
            .on_conflict_do_nothing(index_elements=["query_key"])
        )
        mq = self.db.scalar(
            select(MonitoredQuery).where(MonitoredQuery.query_key == key).with_for_update()
        )
        assert mq is not None
        return mq

    def _recompute(self, mq: MonitoredQuery, *, first_check_now: bool = False) -> None:
        freqs = self.db.scalars(
            select(MonitoringRule.frequency_minutes).where(
                MonitoringRule.monitored_query_id == mq.id, MonitoringRule.is_active.is_(True)
            )
        ).all()
        mq.active_rules = len(freqs)
        if not freqs:
            mq.next_run_at = None
            return
        mq.interval_minutes = max(min(freqs), self.s.monitor_min_interval_minutes)
        now = self.clock()
        if first_check_now or mq.next_run_at is None:
            mq.next_run_at = now
        else:  # a faster rule shouldn't wait for the old, slower schedule
            mq.next_run_at = min(
                mq.next_run_at, (mq.last_run_at or now) + timedelta(minutes=mq.interval_minutes)
            )

    def get(self, user: User, rule_id: uuid.UUID) -> MonitoringRule:
        rule = self.db.scalar(
            select(MonitoringRule).where(
                MonitoringRule.id == rule_id, MonitoringRule.user_id == user.id
            )
        )
        if rule is None:  # same answer for "missing" and "someone else's"
            raise NotFound("Monitor not found")
        return rule

    def list_for(self, user: User) -> list[MonitoringRule]:
        return list(
            self.db.scalars(
                select(MonitoringRule)
                .where(MonitoringRule.user_id == user.id)
                .order_by(MonitoringRule.is_active.desc(), MonitoringRule.created_at.desc())
            ).all()
        )

    def update(self, user: User, rule_id: uuid.UUID, changes: dict[str, Any]) -> MonitoringRule:
        rule = self.get(user, rule_id)
        if "frequency_minutes" in changes:
            self._check_frequency(changes["frequency_minutes"])
        if changes.get("is_active") and not rule.is_active:
            active = self.db.scalar(
                select(func.count())
                .select_from(MonitoringRule)
                .where(MonitoringRule.user_id == user.id, MonitoringRule.is_active.is_(True))
            )
            if (active or 0) >= self.s.max_active_monitors_per_user:
                raise Conflict("Active monitor limit reached.", details={"reason": "limit_reached"})
        if "name" in changes:
            rule.saved_search.name = changes.pop("name")
        for k, v in changes.items():
            setattr(rule, k, v)
        mq = self.db.scalar(
            select(MonitoredQuery)
            .where(MonitoredQuery.id == rule.monitored_query_id)
            .with_for_update()
        )
        assert mq is not None
        self.db.flush()
        self._recompute(mq)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete(self, user: User, rule_id: uuid.UUID) -> None:
        rule = self.get(user, rule_id)
        mq = self.db.scalar(
            select(MonitoredQuery)
            .where(MonitoredQuery.id == rule.monitored_query_id)
            .with_for_update()
        )
        self.db.delete(rule.saved_search)  # cascades to the rule; notifications keep rule_id NULL
        self.db.flush()
        if mq is not None:
            self._recompute(mq)
        self.db.commit()

    def recent_runs(self, rule: MonitoringRule, limit: int = 20) -> list[RefreshRun]:
        # Runs belong to the *shared* query; only show those since this user's rule existed, so a
        # user never sees activity from before they started monitoring (or hints of other users).
        return list(
            self.db.scalars(
                select(RefreshRun)
                .where(
                    RefreshRun.monitored_query_id == rule.monitored_query_id,
                    RefreshRun.started_at >= rule.created_at,
                )
                .order_by(RefreshRun.started_at.desc())
                .limit(limit)
            ).all()
        )

    def history(self, rule: MonitoringRule, limit: int = 500) -> list[RuleCheck]:
        rows = self.db.scalars(
            select(RuleCheck)
            .where(RuleCheck.rule_id == rule.id)
            .order_by(RuleCheck.checked_at.desc())
            .limit(limit)
        ).all()
        return list(reversed(rows))


# ── scheduling (beat) ────────────────────────────────────────────────────────


def schedule_due(
    db: Session, settings: Settings, now: datetime
) -> list[tuple[uuid.UUID, datetime]]:
    """Claim due queries and advance their schedule in one transaction. SKIP LOCKED lets several
    schedulers run without double-claiming; past-departure queries stop being scheduled."""
    rows = db.scalars(
        select(MonitoredQuery)
        .where(MonitoredQuery.active_rules > 0, MonitoredQuery.next_run_at <= now)
        .order_by(MonitoredQuery.next_run_at)
        .limit(settings.monitor_schedule_batch)
        .with_for_update(skip_locked=True)
    ).all()
    claimed: list[tuple[uuid.UUID, datetime]] = []
    for mq in rows:
        depart = date.fromisoformat(mq.query["query"]["depart_date"])
        if depart < now.date():
            mq.next_run_at = None  # nothing left to monitor
            continue
        slot = slot_for(now, mq.interval_minutes)
        mq.next_run_at = slot + timedelta(minutes=mq.interval_minutes)
        claimed.append((mq.id, slot))
    db.commit()
    return claimed


# ── refresh runs (worker) ────────────────────────────────────────────────────


@dataclass(slots=True)
class RefreshOutcome:
    status: str  # succeeded | partial | failed | duplicate | gone
    run_id: uuid.UUID | None = None
    observations: int = 0
    notification_ids: list[uuid.UUID] = field(default_factory=list)


def _claim_run(
    db: Session,
    settings: Settings,
    query_id: uuid.UUID,
    slot: datetime,
    trigger: str,
    now: datetime,
) -> RefreshRun | None:
    """Insert the (query, slot) run, or take over a stale one. None = someone else owns it."""
    run_id = db.scalar(
        insert(RefreshRun)
        .values(
            id=uuid.uuid4(),
            monitored_query_id=query_id,
            slot=slot,
            trigger=trigger,
            status="running",
            started_at=now,
        )
        .on_conflict_do_nothing(index_elements=["monitored_query_id", "slot"])
        .returning(RefreshRun.id)
    )
    if run_id is not None:
        db.commit()
        return db.get(RefreshRun, run_id)
    existing = db.scalar(
        select(RefreshRun)
        .where(RefreshRun.monitored_query_id == query_id, RefreshRun.slot == slot)
        .with_for_update()
    )
    stale = now - timedelta(seconds=settings.refresh_stale_after_s)
    if existing is not None and existing.status == "running" and existing.started_at < stale:
        log.warning("taking over stale refresh run", extra={"run_id": str(existing.id)})
        existing.started_at = now
        db.commit()
        return existing
    db.rollback()
    return None


def run_refresh(
    session_factory: Callable[[], Session],
    search: SearchService,
    settings: Settings,
    query_id: uuid.UUID,
    slot: datetime,
    trigger: str = "schedule",
    clock: Callable[[], datetime] = utcnow,
) -> RefreshOutcome:
    with session_factory() as db:
        mq = db.get(MonitoredQuery, query_id)
        if mq is None:
            return RefreshOutcome("gone")
        run = _claim_run(db, settings, query_id, slot, trigger, clock())
        if run is None:
            MONITOR_REFRESHES.labels("duplicate").inc()
            return RefreshOutcome("duplicate")
        run_id = run.id
        query = UpstreamQuery.model_validate(mq.query["query"])
        include_nearby = bool(mq.include_nearby)

    # Provider calls: outside any transaction.
    result = search.search(query, Preferences(), include_nearby=include_nearby)
    offers = [s.offer for s in result.outcome.ranked]
    ok = [p for p in result.providers if p.state in (ProviderState.OK, ProviderState.CACHED)]
    status = (
        "failed" if not ok else ("succeeded" if len(ok) == len(result.providers) else "partial")
    )
    now = clock()

    with session_factory() as db:
        observed = _store_observations(db, settings, query_id, run_id, slot, offers)
        run = db.get(RefreshRun, run_id)
        assert run is not None
        run.status, run.finished_at, run.offers_count = status, now, len(offers)
        run.providers = [
            {
                "provider": p.provider,
                "state": p.state.value,
                "offers": p.offers,
                "message": p.message,
            }
            for p in result.providers
        ]
        run.error = (
            None if ok else "; ".join(f"{p.provider}: {p.state.value}" for p in result.providers)
        )
        mq = db.get(MonitoredQuery, query_id)
        if mq is not None:
            mq.last_run_at = now
            if ok:
                mq.last_success_at = now
        db.commit()
    MONITOR_REFRESHES.labels(status).inc()

    outcome = RefreshOutcome(status, run_id, observed)
    if status == "failed":
        return outcome  # no data → rules are not evaluated (and not marked as checked)

    with session_factory() as db:
        rule_ids = db.scalars(
            select(MonitoringRule.id).where(
                MonitoringRule.monitored_query_id == query_id, MonitoringRule.is_active.is_(True)
            )
        ).all()
    for rid in rule_ids:
        with session_factory() as db:
            outcome.notification_ids += _evaluate_rule(
                db, rid, run_id, slot, query, include_nearby, offers, now
            )
    return outcome


def _store_observations(
    db: Session,
    settings: Settings,
    query_id: uuid.UUID,
    run_id: uuid.UUID,
    slot: datetime,
    offers: list[Offer],
) -> int:
    cheapest_first = sorted(offers, key=lambda o: (o.total_amount, o.id))[
        : settings.observations_per_run_cap
    ]
    if not cheapest_first:
        return 0
    rows = [
        {
            "monitored_query_id": query_id,
            "refresh_run_id": run_id,
            "slot": slot,
            "observed_at": o.fetched_at,
            "provider": o.provider,
            "source": o.source.value,
            "offer_fingerprint": o.fingerprint,
            "total_amount": o.total_amount,
            "currency": o.currency,
            "max_stops": o.max_stops,
            "total_duration_minutes": o.total_duration_minutes,
            "checked_bags": o.baggage.checked_bags,
            "carriers": ",".join(sorted(o.carriers))[:80],
            "departure_at": o.outbound.departure_at,
        }
        for o in cheapest_first
    ]
    inserted = db.scalars(
        insert(PriceObservation)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_price_obs_identity")
        .returning(PriceObservation.id)
    ).all()
    return len(inserted)


def _evaluate_rule(
    db: Session,
    rule_id: uuid.UUID,
    run_id: uuid.UUID,
    slot: datetime,
    query: UpstreamQuery,
    include_nearby: bool,
    offers: list[Offer],
    now: datetime,
) -> list[uuid.UUID]:
    """One transaction per rule: the check row, its notifications and the new rule state commit
    together, so a crash can't leave a half-evaluated rule — and a re-run is a no-op."""
    # Lock only the rule row: its eager-loaded relationships are outer joins, which Postgres
    # refuses to lock.
    rule = db.scalar(
        select(MonitoringRule)
        .where(MonitoringRule.id == rule_id)
        .with_for_update(of=MonitoringRule)
    )
    if rule is None or not rule.is_active:
        db.rollback()
        return []
    req = SearchRequest.model_validate(rule.saved_search.request)
    out = evaluate(query, req.preferences, offers, include_nearby=include_nearby)
    cheapest = out.recommendations.cheapest.scored.offer if out.recommendations.cheapest else None

    check_id = db.scalar(
        insert(RuleCheck)
        .values(
            rule_id=rule.id,
            refresh_run_id=run_id,
            checked_at=now,
            observed_at=cheapest.fetched_at if cheapest else None,
            cheapest_amount=cheapest.total_amount if cheapest else None,
            cheapest_fingerprint=cheapest.fingerprint if cheapest else None,
            qualifying=len(out.ranked),
            total=out.constraints.total,
            source=cheapest.source.value if cheapest else None,
        )
        .on_conflict_do_nothing(index_elements=["rule_id", "refresh_run_id"])
        .returning(RuleCheck.id)
    )
    if check_id is None:  # already evaluated for this run
        db.rollback()
        return []

    events, state = evaluate_rule(
        RuleConfig(rule.target_price, rule.drop_threshold_pct, rule.notify_new_qualifying),
        RuleState(rule.last_price, rule.best_price, rule.last_qualifying),
        Check(cheapest.total_amount if cheapest else None, len(out.ranked), slot),
    )
    created: list[uuid.UUID] = []
    for e in events:
        title, body = _message(e, rule.saved_search, cheapest)
        # Email only the FIRST time this target is reached; later, lower prices for the same
        # target are in-app only. Changing the target re-arms the email.
        email = True
        if e.kind is EventKind.BELOW_TARGET:
            email = (
                db.scalar(
                    select(Notification.id)
                    .where(
                        Notification.rule_id == rule.id,
                        Notification.kind == EventKind.BELOW_TARGET.value,
                        Notification.data["target"].astext == str(e.target),
                    )
                    .limit(1)
                )
                is None
            )
        nid = db.scalar(
            insert(Notification)
            .values(
                id=uuid.uuid4(),
                user_id=rule.user_id,
                rule_id=rule.id,
                kind=e.kind.value,
                dedup_key=e.dedup_key,
                title=title,
                body=body,
                data={
                    "price": str(e.price),
                    "previous": None if e.previous is None else str(e.previous),
                    "target": None if e.target is None else str(e.target),
                    "currency": rule.saved_search.currency,
                    "route": route_label(rule.saved_search),
                    "saved_search_id": str(rule.saved_search_id),
                    "observed_at": cheapest.fetched_at.isoformat() if cheapest else None,
                    "source": cheapest.source.value if cheapest else None,
                    "email": email,
                },
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["rule_id", "dedup_key"])
            .returning(Notification.id)
        )
        if nid is not None:
            created.append(nid)
            NOTIFICATIONS_CREATED.labels(e.kind.value).inc()

    rule.last_checked_at = now
    rule.last_price, rule.last_qualifying = state.last_price, state.last_qualifying
    if state.best_price is not None and state.best_price != rule.best_price:
        rule.best_price, rule.best_price_at = state.best_price, now
    db.commit()
    return created


def _message(e: Event, ss: SavedSearch, cheapest: Offer | None) -> tuple[str, str]:
    route, cur = route_label(ss), ss.currency
    price = fmt_money(e.price, cur)
    demo = (
        " (demo data — not a real fare)" if cheapest and cheapest.source is FareSource.DEMO else ""
    )
    when = cheapest.fetched_at.astimezone(UTC).strftime("%d %b %H:%M UTC") if cheapest else "now"
    match e.kind:
        case EventKind.BELOW_TARGET:
            assert e.target is not None
            return (
                f"{route} is at or below your target",
                f"The cheapest flight meeting your requirements is {price}{demo}, at or under your "
                f"{fmt_money(e.target, cur)} target. Observed {when}.",
            )
        case EventKind.PRICE_DROP:
            assert e.previous is not None
            return (
                f"Price drop on {route}",
                f"The cheapest flight meeting your requirements fell from "
                f"{fmt_money(e.previous, cur)} to {price}{demo}. Observed {when}.",
            )
        case EventKind.NOW_AVAILABLE:
            return (
                f"Flights now meet your requirements on {route}",
                f"After a check with no matching flights, the cheapest match is now {price}{demo}. "
                f"Observed {when}.",
            )
    raise AssertionError(e.kind)  # pragma: no cover


def mark_failed_runs_stale(db: Session, settings: Settings, now: datetime) -> int:
    """Stale-job sweep: 'running' runs older than the threshold are marked failed for visibility."""
    cutoff = now - timedelta(seconds=settings.refresh_stale_after_s)
    res = db.execute(
        update(RefreshRun)
        .where(RefreshRun.status == "running", RefreshRun.started_at < cutoff)
        .values(status="failed", finished_at=now, error="stale: worker did not finish")
    )
    db.commit()
    return res.rowcount or 0  # type: ignore[attr-defined]
