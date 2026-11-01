import json
import logging

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import health
from app.core.config import Settings
from app.core.db import get_engine
from app.core.logging import JsonFormatter
from app.core.security import hash_password, verify_password
from app.models import Base
from tests.api.conftest import alembic_config


def test_live(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["X-Request-ID"]


def test_ready_all_ok(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_ready_degraded_without_redis(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(health, "ping_redis", boom)
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "degraded"


def test_ready_unavailable_without_postgres(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise OperationalError("SELECT 1", {}, Exception("pg down"))

    monkeypatch.setattr(health, "ping_db", boom)
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "unavailable"


def test_metrics_exposed(client: TestClient) -> None:
    client.get("/health/live")
    body = client.get("/metrics").text
    assert 'skyscout_http_requests_total{method="GET",route="/health/live",status="200"}' in body


def test_request_id_propagated(client: TestClient) -> None:
    assert (
        client.get("/health/live", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"]
        == "abc123"
    )


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_migrations_roundtrip_and_match_models() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations diverge: {diff}"


def test_password_hashing() -> None:
    h = hash_password("correct-horse-battery")
    assert verify_password(h, "correct-horse-battery")
    assert not verify_password(h, "wrong")
    assert not verify_password(None, "timing-equaliser-not-a-real-password")
    assert not verify_password("not-a-hash", "x")


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # dev secret
        {"secret_key": "x" * 40},  # cookie_secure false
        {"secret_key": "x" * 40, "cookie_secure": True},  # dev DB credentials
    ],
)
def test_production_rejects_unsafe_config(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(environment="production", _env_file=None, **overrides)  # type: ignore[arg-type]


def test_production_accepts_safe_config() -> None:
    s = Settings(
        _env_file=None,
        environment="production",
        secret_key="x" * 40,
        cookie_secure=True,
        celery_task_always_eager=False,  # the test env enables it; production must not
        database_url="postgresql+psycopg://app:s3cret@db:5432/skyscout",
    )
    assert s.environment == "production"


def test_log_formatter_redacts_sensitive_extras() -> None:
    record = logging.makeLogRecord(
        {"msg": "hi", "levelname": "INFO", "password": "p", "session_token": "t", "user_id": "u"}
    )
    out = json.loads(JsonFormatter().format(record))
    assert out["password"] == "[redacted]" and out["session_token"] == "[redacted]"
    assert out["user_id"] == "u"
