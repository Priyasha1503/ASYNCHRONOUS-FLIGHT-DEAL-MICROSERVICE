"""Saved searches, shared monitored queries, per-user rules, refresh runs, observations,
notifications and delivery attempts. Idempotency is enforced by unique constraints, not by hope:

* refresh_runs        UNIQUE(monitored_query_id, slot)     → a duplicate task finds the row
* price_observations  UNIQUE(monitored_query_id, provider, fingerprint, slot)
* rule_checks         UNIQUE(rule_id, refresh_run_id)       → a rule is evaluated once per run
* notifications       UNIQUE(rule_id, dedup_key)            → the same event alerts once
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk

Money = Numeric(12, 2)


class SavedSearch(UUIDPk, Timestamps, Base):
    __tablename__ = "saved_searches"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    # The full validated SearchRequest (route, dates, passengers, cabin, currency, preferences).
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    request_hash: Mapped[str] = mapped_column(CHAR(64))
    # Denormalized for listing/sorting without parsing JSON.
    origin: Mapped[str] = mapped_column(CHAR(3))
    destination: Mapped[str] = mapped_column(CHAR(3))
    depart_date: Mapped[date]
    return_date: Mapped[date | None]
    currency: Mapped[str] = mapped_column(CHAR(3))

    rule: Mapped["MonitoringRule | None"] = relationship(
        back_populates="saved_search", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "request_hash"),
        Index("ix_saved_searches_user_created", "user_id", "created_at"),
    )


class MonitoredQuery(UUIDPk, Timestamps, Base):
    """One row per distinct upstream query; shared by every user rule that needs it."""

    __tablename__ = "monitored_queries"

    query_key: Mapped[str] = mapped_column(String(64), unique=True)
    query: Mapped[dict[str, Any]] = mapped_column(JSONB)  # UpstreamQuery + include_nearby
    include_nearby: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer)
    next_run_at: Mapped[datetime | None]
    last_run_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    active_rules: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        Index(
            "ix_monitored_queries_due",
            "next_run_at",
            postgresql_where=text("active_rules > 0"),
        ),
        CheckConstraint("interval_minutes >= 1", name="interval_positive"),
    )


class MonitoringRule(UUIDPk, Timestamps, Base):
    __tablename__ = "monitoring_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    saved_search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("saved_searches.id", ondelete="CASCADE"), unique=True
    )
    monitored_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monitored_queries.id", ondelete="RESTRICT")
    )
    target_price: Mapped[Decimal | None] = mapped_column(Money)
    drop_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    notify_new_qualifying: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency_minutes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Evaluation state (updated once per refresh run).
    last_checked_at: Mapped[datetime | None]
    last_price: Mapped[Decimal | None] = mapped_column(Money)
    best_price: Mapped[Decimal | None] = mapped_column(Money)
    best_price_at: Mapped[datetime | None]
    last_qualifying: Mapped[int | None] = mapped_column(Integer)

    saved_search: Mapped[SavedSearch] = relationship(back_populates="rule", lazy="joined")
    monitored_query: Mapped[MonitoredQuery] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_monitoring_rules_user", "user_id"),
        Index("ix_monitoring_rules_query_active", "monitored_query_id", "is_active"),
        CheckConstraint("target_price IS NULL OR target_price > 0", name="target_positive"),
        CheckConstraint(
            "drop_threshold_pct IS NULL OR (drop_threshold_pct > 0 AND drop_threshold_pct <= 90)",
            name="drop_threshold_range",
        ),
    )


class RefreshRun(UUIDPk, Base):
    __tablename__ = "refresh_runs"

    monitored_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monitored_queries.id", ondelete="CASCADE")
    )
    slot: Mapped[datetime]  # scheduled bucket; (query, slot) identifies the job
    trigger: Mapped[str] = mapped_column(String(16), default="schedule")  # schedule | manual
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    offers_count: Mapped[int | None] = mapped_column(Integer)
    providers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("monitored_query_id", "slot"),
        Index("ix_refresh_runs_query_started", "monitored_query_id", "started_at"),
        CheckConstraint(
            "status IN ('running','succeeded','partial','failed')", name="status_valid"
        ),
    )


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    monitored_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monitored_queries.id", ondelete="CASCADE")
    )
    refresh_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refresh_runs.id", ondelete="CASCADE")
    )
    slot: Mapped[datetime]
    observed_at: Mapped[datetime]  # provider fetch time of the data, not insert time
    provider: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(16))
    offer_fingerprint: Mapped[str] = mapped_column(String(32))
    total_amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(CHAR(3))
    max_stops: Mapped[int] = mapped_column(Integer)
    total_duration_minutes: Mapped[int] = mapped_column(Integer)
    checked_bags: Mapped[int | None] = mapped_column(Integer)
    carriers: Mapped[str] = mapped_column(String(80))
    departure_at: Mapped[datetime]

    __table_args__ = (
        # Explicit name: the generated one exceeds Postgres's 63-char identifier limit.
        UniqueConstraint(
            "monitored_query_id",
            "provider",
            "offer_fingerprint",
            "slot",
            name="uq_price_obs_identity",
        ),
        Index("ix_price_observations_query_observed", "monitored_query_id", "observed_at"),
        CheckConstraint("total_amount > 0", name="amount_positive"),
    )


class RuleCheck(Base):
    """A rule's view of one refresh run: the cheapest offer meeting *its* requirements."""

    __tablename__ = "rule_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monitoring_rules.id", ondelete="CASCADE")
    )
    refresh_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refresh_runs.id", ondelete="CASCADE")
    )
    checked_at: Mapped[datetime]
    observed_at: Mapped[datetime | None]
    cheapest_amount: Mapped[Decimal | None] = mapped_column(Money)
    cheapest_fingerprint: Mapped[str | None] = mapped_column(String(32))
    qualifying: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        UniqueConstraint("rule_id", "refresh_run_id"),
        Index("ix_rule_checks_rule_checked", "rule_id", "checked_at"),
    )


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("monitoring_rules.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(32))
    dedup_key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    read_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("rule_id", "dedup_key"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )


class DeliveryAttempt(UUIDPk, Base):
    __tablename__ = "delivery_attempts"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE")
    )
    channel: Mapped[str] = mapped_column(String(16))  # email
    attempt: Mapped[int] = mapped_column(Integer)
    # queued → sent (accepted by the transport) | failed | simulated (console backend, dev only)
    status: Mapped[str] = mapped_column(String(16))
    backend: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("notification_id", "channel", "attempt"),
        CheckConstraint("status IN ('queued','sent','failed','simulated')", name="status_valid"),
    )


class JobFailure(Base):
    """Dead-letter record for tasks that exhausted their retries."""

    __tablename__ = "job_failures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(120))
    task_id: Mapped[str | None] = mapped_column(String(64))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text)
    failed_at: Mapped[datetime] = mapped_column(server_default=func.now())
