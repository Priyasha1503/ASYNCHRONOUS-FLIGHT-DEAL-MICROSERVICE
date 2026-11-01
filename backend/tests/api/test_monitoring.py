"""Monitoring lifecycle against real Postgres + Redis: scheduling, idempotent refreshes, rule
evaluation, deduplicated notifications, honest email status, and API authorization."""

import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.redis import get_redis
from app.domain.query import UpstreamQuery
from app.main import create_app
from app.models import (
    DeliveryAttempt,
    MonitoredQuery,
    MonitoringRule,
    Notification,
    PriceObservation,
    RefreshRun,
    RuleCheck,
)
from app.providers.demo_simulation import apply_price_change
from app.providers.registry import build_providers
from app.services.monitoring import run_refresh, schedule_due
from app.services.search import SearchService
from tests.api.conftest import csrf_headers, register

DEPART = (datetime.now(UTC).date() + timedelta(days=40)).isoformat()
RETURN = (datetime.now(UTC).date() + timedelta(days=47)).isoformat()
SEARCH = {"origin": "LHR", "destination": "JFK", "depart_date": DEPART, "return_date": RETURN}
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
# Monitor alerts only (excludes account emails like the welcome note).
ALERT = Notification.rule_id.is_not(None)


def create(client: TestClient, **kw: Any) -> Any:
    body = {"search": SEARCH, "frequency_minutes": 60} | kw
    return client.post("/api/v1/monitors", json=body, headers=csrf_headers(client))


def uncached_search() -> SearchService:
    # No shared cache, so each refresh sees the current (possibly simulated) demo prices.
    return SearchService(build_providers(get_settings()), get_settings(), redis_client=None)


def refresh(query_id: Any, slot: datetime) -> Any:
    return run_refresh(
        get_sessionmaker(), uncached_search(), get_settings(), query_id, slot, clock=lambda: slot
    )


def count(model: Any, *where: Any) -> int:
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def only_query_id() -> Any:
    with get_sessionmaker()() as db:
        return db.scalar(select(MonitoredQuery.id))


def query_keys() -> list[str]:
    with get_sessionmaker()() as db:
        mq = db.scalar(select(MonitoredQuery))
        assert mq is not None
        return [UpstreamQuery.model_validate(mq.query["query"]).cache_key()]


# ── scheduling & idempotency ─────────────────────────────────────────────────


def test_schedule_due_claims_each_query_once_per_interval(client: TestClient) -> None:
    register(client)
    assert create(client).status_code == 201
    now = datetime.now(UTC)
    with get_sessionmaker()() as db:
        first = schedule_due(db, get_settings(), now)
    with get_sessionmaker()() as db:
        again = schedule_due(db, get_settings(), now + timedelta(minutes=5))
    assert len(first) == 1 and again == []
    with get_sessionmaker()() as db:
        later = schedule_due(db, get_settings(), now + timedelta(minutes=61))
    assert len(later) == 1 and later[0][1] > first[0][1]


def test_two_users_share_one_monitored_query(client: TestClient) -> None:
    register(client, "a@example.com")
    create(client)
    refresh(only_query_id(), datetime.now(UTC) - timedelta(minutes=1))  # before B's rule exists
    with TestClient(create_app()) as other:
        register(other, "b@example.com")
        rid_b = create(other, frequency_minutes=1440).json()["id"]
        # B must not see the shared query's runs from before B started monitoring.
        assert other.get(f"/api/v1/monitors/{rid_b}").json()["runs"] == []
    with get_sessionmaker()() as db:
        mq = db.scalar(select(MonitoredQuery))
        assert mq is not None and mq.active_rules == 2
        assert mq.interval_minutes == 60  # fastest active rule wins
    assert count(MonitoredQuery) == 1


def test_duplicate_refresh_task_creates_nothing_twice(client: TestClient) -> None:
    register(client)
    create(client, target_price="100000")  # guaranteed below target → one notification
    qid = only_query_id()
    first = refresh(qid, T0)
    dup = refresh(qid, T0)
    assert first.status == "succeeded" and first.observations > 0
    assert dup.status == "duplicate"
    assert count(RefreshRun) == 1
    assert count(PriceObservation) == first.observations
    assert count(RuleCheck) == 1
    assert count(Notification, ALERT) == 1


def test_concurrent_duplicate_tasks_are_safe(client: TestClient) -> None:
    register(client)
    create(client, target_price="100000")
    qid = only_query_id()
    barrier = threading.Barrier(4)
    results: list[str] = []

    def go() -> None:
        barrier.wait()
        results.append(refresh(qid, T0).status)

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["duplicate", "duplicate", "duplicate", "succeeded"]
    assert count(RefreshRun) == 1 and count(RuleCheck) == 1 and count(Notification, ALERT) == 1


def test_stale_running_job_is_taken_over(client: TestClient) -> None:
    register(client)
    create(client)
    qid = only_query_id()
    with get_sessionmaker()() as db:
        db.add(
            RefreshRun(
                monitored_query_id=qid,
                slot=T0,
                status="running",
                started_at=T0 - timedelta(hours=2),
            )
        )
        db.commit()
    out = refresh(qid, T0)
    assert out.status == "succeeded" and count(RefreshRun) == 1


def test_failed_providers_do_not_count_as_a_check(client: TestClient, monkeypatch: Any) -> None:
    from app.providers.demo import DemoProvider

    register(client)
    create(client)
    qid = only_query_id()
    svc = SearchService(
        [DemoProvider(failure="unavailable")],
        get_settings().model_copy(update={"provider_max_attempts": 1}),
        redis_client=None,
    )
    out = run_refresh(get_sessionmaker(), svc, get_settings(), qid, T0, clock=lambda: T0)
    assert out.status == "failed"
    assert count(RuleCheck) == 0 and count(PriceObservation) == 0
    with get_sessionmaker()() as db:
        run = db.scalar(select(RefreshRun))
        rule = db.scalar(select(MonitoringRule))
        assert run is not None and run.status == "failed" and "unavailable" in (run.error or "")
        assert rule is not None and rule.last_checked_at is None


def test_alert_lifecycle_with_simulated_price_changes(client: TestClient) -> None:
    register(client)
    qid_resp = create(client, drop_threshold_pct="15")
    assert qid_resp.status_code == 201
    qid = only_query_id()

    base = refresh(qid, T0)
    assert base.notification_ids == []  # first check: no previous price, no target
    with get_sessionmaker()() as db:
        rule = db.scalar(select(MonitoringRule))
        assert rule is not None and rule.last_price is not None
        start = rule.last_price
    # Set a target just under today's price, then simulate a 20% drop.
    rid = qid_resp.json()["id"]
    target = (start * Decimal("0.9")).quantize(Decimal("1"))
    client.patch(
        f"/api/v1/monitors/{rid}", json={"target_price": str(target)}, headers=csrf_headers(client)
    )
    apply_price_change(get_redis(), query_keys(), Decimal("-20"))

    drop = refresh(qid, T0 + timedelta(hours=1))
    with get_sessionmaker()() as db:
        kinds = sorted(db.scalars(select(Notification.kind).where(ALERT)).all())
    assert kinds == ["below_target", "price_drop"]
    assert len(drop.notification_ids) == 2

    # Same price next hour → nothing new (same band, no drop).
    same = refresh(qid, T0 + timedelta(hours=2))
    assert same.notification_ids == [] and count(Notification, ALERT) == 2

    # A further 10% drop → a new below-target band (drop < 15% threshold → no drop alert).
    apply_price_change(get_redis(), query_keys(), Decimal("-10"))
    further = refresh(qid, T0 + timedelta(hours=3))
    assert len(further.notification_ids) == 1 and count(Notification, ALERT) == 3

    detail = client.get(f"/api/v1/monitors/{rid}").json()
    prices = [Decimal(p["cheapest_amount"]) for p in detail["history"]]
    assert len(prices) == 4 and prices[1] < prices[0] and prices[3] < prices[2]
    assert Decimal(detail["best_price"]) == prices[3]


def test_email_status_is_never_overstated(client: TestClient) -> None:
    from app.services.notifications import deliver_email, email_backend

    register(client)
    create(client, target_price="100000")
    out = refresh(only_query_id(), T0)
    nid = out.notification_ids[0]
    with get_sessionmaker()() as db:
        first = deliver_email(db, nid, email_backend(get_settings()), get_settings())
        again = deliver_email(db, nid, email_backend(get_settings()), get_settings())
        statuses = db.scalars(
            select(DeliveryAttempt.status).where(DeliveryAttempt.notification_id == nid)
        ).all()
    assert first.status == "simulated"  # console backend: logged, not sent
    assert again.status == "skipped"  # idempotent: no second email
    assert statuses == ["simulated"]


def test_email_failures_are_recorded_and_retried_until_the_cap(client: TestClient) -> None:
    from app.services.notifications import EmailError, deliver_email

    class Down:
        name, delivered_status = "smtp", "sent"

        def send(self, email: Any) -> None:
            raise EmailError("connection refused", retryable=True)

    register(client)
    create(client, target_price="100000")
    nid = refresh(only_query_id(), T0).notification_ids[0]
    s = get_settings().model_copy(update={"email_max_attempts": 2})
    with get_sessionmaker()() as db:
        r1 = deliver_email(db, nid, Down(), s)
        r2 = deliver_email(db, nid, Down(), s)
        rows = db.scalars(
            select(DeliveryAttempt)
            .where(DeliveryAttempt.notification_id == nid)  # not the welcome email
            .order_by(DeliveryAttempt.attempt)
        ).all()
    assert (r1.status, r1.retry) == ("failed", True)
    assert (r2.status, r2.retry) == ("failed", False)  # cap reached → task dead-letters
    assert [(a.attempt, a.status) for a in rows] == [(1, "failed"), (2, "failed")]
    assert all("connection refused" in (a.error or "") for a in rows)


def _emailed_kinds() -> list[str]:
    with get_sessionmaker()() as db:
        return sorted(
            db.scalars(
                select(Notification.kind)
                .join(DeliveryAttempt, DeliveryAttempt.notification_id == Notification.id)
                .where(DeliveryAttempt.status.in_(("sent", "simulated")))
            ).all()
        )


def test_welcome_and_sign_in_emails(client: TestClient) -> None:
    register(client, "new@example.com")
    assert _emailed_kinds() == ["welcome"]
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "new@example.com", "password": "correct-horse-battery"},
        headers=csrf_headers(client),
    )
    assert r.status_code == 200
    assert _emailed_kinds() == ["sign_in", "welcome"]
    # The sign-in notice is emailed but doesn't light up the bell.
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 1}


def test_target_price_is_emailed_only_the_first_time(client: TestClient) -> None:
    register(client)
    rid = create(client, target_price="2000").json()["id"]
    qid = only_query_id()
    refresh(qid, T0)  # first time under target → in-app + email
    apply_price_change(get_redis(), query_keys(), Decimal("-20"))
    refresh(qid, T0 + timedelta(hours=1))  # lower band → in-app only
    with get_sessionmaker()() as db:
        flags = [
            n.data["email"]
            for n in db.scalars(
                select(Notification)
                .where(Notification.kind == "below_target")
                .order_by(Notification.created_at)
            ).all()
        ]
    assert flags == [True, False]
    # Deliver everything that was created: only the first target hit becomes an email.
    from app.services.notifications import deliver_email, email_backend

    with get_sessionmaker()() as db:
        for nid in db.scalars(select(Notification.id)).all():
            deliver_email(db, nid, email_backend(get_settings()), get_settings())
    assert _emailed_kinds() == ["below_target", "welcome"]
    # A new target re-arms the email.
    client.patch(
        f"/api/v1/monitors/{rid}", json={"target_price": "1500"}, headers=csrf_headers(client)
    )
    apply_price_change(get_redis(), query_keys(), Decimal("-10"))
    refresh(qid, T0 + timedelta(hours=2))
    with get_sessionmaker()() as db:
        latest = db.scalars(
            select(Notification)
            .where(Notification.kind == "below_target")
            .order_by(Notification.created_at.desc())
        ).first()
    assert (
        latest is not None and latest.data["target"] == "1500.00" and latest.data["email"] is True
    )


# ── API ──────────────────────────────────────────────────────────────────────


def test_monitors_require_auth(client: TestClient) -> None:
    assert create(client).status_code == 401
    assert client.get("/api/v1/monitors").status_code == 401
    assert client.get("/api/v1/notifications").status_code == 401


def test_create_validation_duplicates_and_limits(client: TestClient) -> None:
    register(client)
    assert create(client, frequency_minutes=5).status_code == 422
    assert create(client, target_price="-1").status_code == 422
    assert create(client, drop_threshold_pct="95").status_code == 422
    ok = create(client, target_price="450.50", name="NYC trip")
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert (body["name"], body["target_price"], body["status"]) == ("NYC trip", "450.50", "active")
    assert body["next_check_at"] is not None
    dup = create(client)
    assert dup.status_code == 409 and "already monitoring" in dup.json()["error"]["message"]
    s = get_settings()
    old, s.max_active_monitors_per_user = s.max_active_monitors_per_user, 1
    try:
        other = create(client, search=SEARCH | {"destination": "BOS"})
    finally:
        s.max_active_monitors_per_user = old
    assert (
        other.status_code == 409 and other.json()["error"]["details"]["reason"] == "limit_reached"
    )


def test_update_pause_delete(client: TestClient) -> None:
    register(client)
    rid = create(client).json()["id"]
    h = csrf_headers(client)
    r = client.patch(
        f"/api/v1/monitors/{rid}", json={"is_active": False, "target_price": "399"}, headers=h
    )
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["target_price"], r.json()["next_check_at"]) == (
        "paused",
        "399.00",
        None,
    )
    with get_sessionmaker()() as db:
        mq = db.scalar(select(MonitoredQuery))
        assert mq is not None and mq.active_rules == 0 and mq.next_run_at is None
    assert (
        client.patch(
            f"/api/v1/monitors/{rid}", json={"frequency_minutes": 7}, headers=h
        ).status_code
        == 422
    )
    assert client.delete(f"/api/v1/monitors/{rid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/monitors/{rid}").status_code == 404


def test_cross_user_access_is_404(client: TestClient) -> None:
    register(client, "owner@example.com")
    rid = create(client, target_price="100000").json()["id"]
    refresh(only_query_id(), T0)
    with TestClient(create_app()) as intruder:
        register(intruder, "intruder@example.com")
        h = csrf_headers(intruder)
        assert intruder.get(f"/api/v1/monitors/{rid}").status_code == 404
        assert (
            intruder.patch(
                f"/api/v1/monitors/{rid}", json={"is_active": False}, headers=h
            ).status_code
            == 404
        )
        assert intruder.delete(f"/api/v1/monitors/{rid}", headers=h).status_code == 404
        assert intruder.post(f"/api/v1/monitors/{rid}/refresh", headers=h).status_code == 404
        assert intruder.get("/api/v1/monitors").json() == []
        notes = intruder.get("/api/v1/notifications").json()
        # The intruder only sees their own welcome note — nothing from the owner's monitor.
        assert [n["kind"] for n in notes["items"]] == ["welcome"]
        assert all(n["rule_id"] is None for n in notes["items"])
        owner_note = next(
            n["id"]
            for n in client.get("/api/v1/notifications").json()["items"]
            if n["kind"] == "below_target"
        )
        assert (
            intruder.post(f"/api/v1/notifications/{owner_note}/read", headers=h).status_code == 404
        )
    assert client.get(f"/api/v1/monitors/{rid}").status_code == 200


def test_simulate_endpoint_runs_check_and_notifies(client: TestClient) -> None:
    register(client)
    rid = create(client, target_price="100000").json()["id"]
    h = csrf_headers(client)
    r = client.post(
        f"/api/v1/monitors/{rid}/simulate-price-change", json={"percent": "-10"}, headers=h
    )
    assert r.status_code == 202, r.text
    # Celery runs eagerly in tests: the check, notification and (console) email already happened.
    detail = client.get(f"/api/v1/monitors/{rid}").json()
    assert detail["demo_simulation_available"] is True
    assert len(detail["history"]) == 1 and detail["runs"][0]["trigger"] == "manual"
    notes = client.get("/api/v1/notifications").json()
    kinds = [n["kind"] for n in notes["items"]]
    assert kinds == ["below_target", "welcome"] and notes["unread_count"] == 2
    target = notes["items"][0]
    assert "demo data" in target["body"]
    # Welcome + first target hit both emailed (console backend in tests → "simulated").
    assert count(DeliveryAttempt, DeliveryAttempt.status == "simulated") == 2
    assert client.post(f"/api/v1/notifications/{target['id']}/read", headers=h).json()["read_at"]
    assert client.get("/api/v1/notifications/unread-count").json() == {"unread_count": 1}
    # Manual "check now" has a cooldown.
    assert client.post(f"/api/v1/monitors/{rid}/refresh", headers=h).status_code == 429


def test_simulation_is_unavailable_in_production(client: TestClient) -> None:
    register(client)
    rid = create(client).json()["id"]
    s = get_settings()
    old, s.environment = s.environment, "production"
    try:
        r = client.post(
            f"/api/v1/monitors/{rid}/simulate-price-change",
            json={"percent": "-10"},
            headers=csrf_headers(client),
        )
    finally:
        s.environment = old
    assert r.status_code == 404


def test_notifications_keyset_pagination(client: TestClient) -> None:
    register(client)
    # Bands are 1% of the target: with a 2000 target (20-unit bands), each 10% drop of a ~600
    # fare lands in a new band. (With a huge target every fare shares one band → one alert.)
    create(client, target_price="2000")
    qid = only_query_id()
    refresh(qid, T0)
    for i in range(1, 5):
        apply_price_change(get_redis(), query_keys(), Decimal("-10"))
        refresh(qid, T0 + timedelta(hours=i))
    total = count(Notification)
    assert total >= 5
    seen: list[str] = []
    cursor = None
    while True:
        page = client.get(
            "/api/v1/notifications", params={"limit": 2} | ({"cursor": cursor} if cursor else {})
        ).json()
        seen += [n["id"] for n in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == total == len(set(seen))
    assert client.get("/api/v1/notifications", params={"cursor": "garbage"}).status_code == 400
