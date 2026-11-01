import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.money import Amount
from app.domain.query import SearchRequest
from app.models import MonitoringRule, Notification, RefreshRun, RuleCheck

Price = Annotated[Decimal, Field(gt=0, le=1_000_000, decimal_places=2)]
DropPct = Annotated[Decimal, Field(gt=0, le=90, decimal_places=2)]


class MonitorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: SearchRequest
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    target_price: Price | None = Field(default=None, description="In the search currency")
    drop_threshold_pct: DropPct | None = Field(
        default=None, description="Alert when the price falls by at least this % since last check"
    )
    notify_new_qualifying: bool = True
    frequency_minutes: int = 360


class MonitorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    target_price: Price | None = None
    drop_threshold_pct: DropPct | None = None
    notify_new_qualifying: bool | None = None
    frequency_minutes: int | None = None
    is_active: bool | None = None


class MonitorOut(BaseModel):
    id: uuid.UUID
    name: str
    status: Literal["active", "paused", "departed"]
    search: dict[str, Any]
    origin: str
    destination: str
    depart_date: date
    return_date: date | None
    currency: str
    target_price: Amount | None
    drop_threshold_pct: Amount | None
    notify_new_qualifying: bool
    frequency_minutes: int
    effective_interval_minutes: int = Field(description="Shared schedule actually used")
    created_at: datetime
    last_checked_at: datetime | None
    next_check_at: datetime | None
    last_price: Amount | None = Field(description="Cheapest qualifying price at the last check")
    last_qualifying: int | None
    best_price: Amount | None
    best_price_at: datetime | None

    @classmethod
    def of(cls, r: MonitoringRule) -> "MonitorOut":
        ss, mq = r.saved_search, r.monitored_query
        today = datetime.now(UTC).date()
        status: Literal["active", "paused", "departed"] = (
            "paused" if not r.is_active else "departed" if ss.depart_date < today else "active"
        )
        return cls(
            id=r.id,
            name=ss.name,
            status=status,
            search=ss.request,
            origin=ss.origin,
            destination=ss.destination,
            depart_date=ss.depart_date,
            return_date=ss.return_date,
            currency=ss.currency,
            target_price=r.target_price,
            drop_threshold_pct=r.drop_threshold_pct,
            notify_new_qualifying=r.notify_new_qualifying,
            frequency_minutes=r.frequency_minutes,
            effective_interval_minutes=mq.interval_minutes,
            created_at=r.created_at,
            last_checked_at=r.last_checked_at,
            next_check_at=mq.next_run_at if status == "active" else None,
            last_price=r.last_price,
            last_qualifying=r.last_qualifying,
            best_price=r.best_price,
            best_price_at=r.best_price_at,
        )


class RefreshRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slot: datetime
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    offers_count: int | None
    providers: list[dict[str, Any]] | None
    error: str | None

    @classmethod
    def of(cls, r: RefreshRun) -> "RefreshRunOut":
        return cls.model_validate(r)


class HistoryPointOut(BaseModel):
    checked_at: datetime
    observed_at: datetime | None
    cheapest_amount: Amount | None = Field(description="null = nothing met your requirements")
    qualifying: int
    total: int
    source: str | None

    @classmethod
    def of(cls, c: RuleCheck) -> "HistoryPointOut":
        return cls(
            checked_at=c.checked_at,
            observed_at=c.observed_at,
            cheapest_amount=c.cheapest_amount,
            qualifying=c.qualifying,
            total=c.total,
            source=c.source,
        )


class MonitorDetailOut(MonitorOut):
    runs: list[RefreshRunOut]
    history: list[HistoryPointOut]
    demo_simulation_available: bool


class SimulateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: Annotated[Decimal, Field(ge=-60, le=60, decimal_places=1)]


class AcceptedOut(BaseModel):
    status: Literal["queued"]
    message: str


class NotificationOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID | None
    kind: str
    title: str
    body: str
    data: dict[str, Any]
    created_at: datetime
    read_at: datetime | None

    @classmethod
    def of(cls, n: Notification) -> "NotificationOut":
        return cls(
            id=n.id,
            rule_id=n.rule_id,
            kind=n.kind,
            title=n.title,
            body=n.body,
            data=n.data,
            created_at=n.created_at,
            read_at=n.read_at,
        )


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int
