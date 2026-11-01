import base64
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import and_, func, or_, select, update

from app.api.deps import AppSettings, CurrentUser, DbSession, Limiter
from app.api.v1.schemas.monitoring import (
    AcceptedOut,
    HistoryPointOut,
    MonitorCreate,
    MonitorDetailOut,
    MonitorOut,
    MonitorUpdate,
    NotificationOut,
    NotificationPage,
    RefreshRunOut,
    SimulateIn,
    UnreadCountOut,
)
from app.core.errors import AppError, NotFound, RateLimited, ValidationFailed
from app.core.redis import get_redis
from app.domain.query import UpstreamQuery
from app.models import MonitoringRule, Notification, RefreshRun
from app.models.base import utcnow
from app.providers.demo_simulation import apply_price_change
from app.services.monitoring import MonitoringService, RuleSettings
from app.services.search import default_search_service

router = APIRouter(tags=["monitoring"])


def _detail(svc: MonitoringService, rule: MonitoringRule, demo: bool) -> MonitorDetailOut:
    base = MonitorOut.of(rule).model_dump()
    return MonitorDetailOut(
        **base,
        runs=[RefreshRunOut.of(r) for r in svc.recent_runs(rule)],
        history=[HistoryPointOut.of(c) for c in svc.history(rule)],
        demo_simulation_available=demo,
    )


@router.post("/monitors", response_model=MonitorOut, status_code=status.HTTP_201_CREATED)
def create_monitor(
    body: MonitorCreate, user: CurrentUser, db: DbSession, settings: AppSettings
) -> MonitorOut:
    """Save a search and start monitoring it. The first check runs within about a minute."""
    try:
        body.search.to_query().check_dates(datetime.now(UTC).date())
    except ValueError as exc:
        raise ValidationFailed(
            str(exc),
            details=[
                {"loc": ["body", "search", "depart_date"], "msg": str(exc), "type": "value_error"}
            ],
        ) from exc
    rule = MonitoringService(db, settings).create(
        user,
        body.search,
        body.name,
        RuleSettings(
            body.target_price,
            body.drop_threshold_pct,
            body.notify_new_qualifying,
            body.frequency_minutes,
        ),
    )
    return MonitorOut.of(rule)


@router.get("/monitors", response_model=list[MonitorOut])
def list_monitors(user: CurrentUser, db: DbSession, settings: AppSettings) -> list[MonitorOut]:
    return [MonitorOut.of(r) for r in MonitoringService(db, settings).list_for(user)]


@router.get("/monitors/{rule_id}", response_model=MonitorDetailOut)
def get_monitor(
    rule_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> MonitorDetailOut:
    svc = MonitoringService(db, settings)
    return _detail(svc, svc.get(user, rule_id), settings.demo_simulation_enabled)


@router.patch("/monitors/{rule_id}", response_model=MonitorOut)
def update_monitor(
    rule_id: uuid.UUID, body: MonitorUpdate, user: CurrentUser, db: DbSession, settings: AppSettings
) -> MonitorOut:
    changes = body.model_dump(exclude_unset=True)
    for k in ("name", "notify_new_qualifying", "frequency_minutes", "is_active"):
        if k in changes and changes[k] is None:
            raise AppError(f"{k} cannot be null")
    return MonitorOut.of(MonitoringService(db, settings).update(user, rule_id, changes))


@router.delete("/monitors/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitor(
    rule_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> Response:
    MonitoringService(db, settings).delete(user, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _queue_manual_refresh(rule: MonitoringRule, *, fresh: bool) -> None:
    from app.workers.tasks import refresh_monitored_query  # avoid importing Celery at module load

    mq = rule.monitored_query
    if fresh:  # "check now" means now: drop shared cached results for this query
        svc = default_search_service()
        query = UpstreamQuery.model_validate(mq.query["query"])
        if svc.cache is not None:
            for q in svc.upstream_queries(query, mq.include_nearby):
                for p in svc.providers:
                    try:
                        svc.cache.invalidate(p.name, q.cache_key())
                    except Exception:  # cache down → the provider gets called anyway
                        break
    slot = utcnow().replace(microsecond=0)
    refresh_monitored_query.delay(str(mq.id), slot.isoformat(), "manual")


@router.post(
    "/monitors/{rule_id}/refresh", response_model=AcceptedOut, status_code=status.HTTP_202_ACCEPTED
)
def refresh_monitor(
    rule_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> AcceptedOut:
    rule = MonitoringService(db, settings).get(user, rule_id)
    recent = db.scalar(
        select(RefreshRun.started_at)
        .where(
            RefreshRun.monitored_query_id == rule.monitored_query_id,
            RefreshRun.trigger == "manual",
            RefreshRun.started_at
            > utcnow() - timedelta(seconds=settings.manual_refresh_cooldown_s),
        )
        .limit(1)
    )
    if recent is not None:
        raise RateLimited(
            "This trip was checked moments ago. Try again in a couple of minutes.",
            details={"retry_after_s": settings.manual_refresh_cooldown_s},
        )
    _queue_manual_refresh(rule, fresh=True)
    return AcceptedOut(status="queued", message="Check queued — results appear in a few seconds.")


@router.post(
    "/monitors/{rule_id}/simulate-price-change",
    response_model=AcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def simulate_price_change(
    rule_id: uuid.UUID,
    body: SimulateIn,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
) -> AcceptedOut:
    """Demo only: shift this trip's *demo* fares by a percentage, then check immediately. Lets you
    see alerts fire without real price movement. Not available in production or for real data."""
    if not settings.demo_simulation_enabled:
        raise NotFound("Not found")
    if body.percent == 0:
        raise AppError("percent must not be 0")
    limiter.hit(f"simulate:{user.id}", 10)
    rule = MonitoringService(db, settings).get(user, rule_id)
    mq = rule.monitored_query
    query = UpstreamQuery.model_validate(mq.query["query"])
    keys = [
        q.cache_key() for q in default_search_service().upstream_queries(query, mq.include_nearby)
    ]
    factor = apply_price_change(get_redis(), keys, body.percent)
    _queue_manual_refresh(rule, fresh=True)
    return AcceptedOut(
        status="queued",
        message=f"Demo fares for this trip are now at {factor * 100:.0f}% of their base price; "
        "checking now.",
    )


# ── notifications ────────────────────────────────────────────────────────────


def _cursor(n: Notification) -> str:
    return base64.urlsafe_b64encode(f"{n.created_at.isoformat()}|{n.id}".encode()).decode()


def _parse_cursor(c: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, nid = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(nid)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("invalid cursor") from exc


def _unread(db: DbSession, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    unread: bool = False,
) -> NotificationPage:
    """Newest first, keyset-paginated (stable under concurrent inserts)."""
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    if cursor:
        ts, nid = _parse_cursor(cursor)
        stmt = stmt.where(
            or_(
                Notification.created_at < ts,
                and_(Notification.created_at == ts, Notification.id < nid),
            )
        )
    rows = db.scalars(
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
    ).all()
    page = list(rows[:limit])
    return NotificationPage(
        items=[NotificationOut.of(n) for n in page],
        next_cursor=_cursor(page[-1]) if len(rows) > limit else None,
        unread_count=_unread(db, user.id),
    )


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def unread_count(user: CurrentUser, db: DbSession) -> UnreadCountOut:
    return UnreadCountOut(unread_count=_unread(db, user.id))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DbSession) -> NotificationOut:
    n = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if n is None:
        raise NotFound("Notification not found")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return NotificationOut.of(n)


@router.post("/notifications/read-all", response_model=UnreadCountOut)
def mark_all_read(user: CurrentUser, db: DbSession) -> UnreadCountOut:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
    return UnreadCountOut(unread_count=0)
