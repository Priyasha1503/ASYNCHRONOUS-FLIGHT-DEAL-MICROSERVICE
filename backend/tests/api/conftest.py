"""Fixtures for tests that need Postgres + Redis: schema via Alembic, per-test cleanup, client."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.redis import get_redis
from tests.conftest import TEST_DB

BACKEND = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["database_url"] = TEST_DB
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    yield
    try:
        with get_engine().begin() as conn:
            # The app's 10 s statement timeout is too tight for TRUNCATE on a loaded machine; and a
            # lock wait should fail with a *lock* error, not look like a slow statement.
            conn.execute(
                text("SET LOCAL statement_timeout = '60s'; SET LOCAL lock_timeout = '30s'")
            )
            tables = conn.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename <> 'alembic_version'"
                )
            ).all()
            if tables:
                conn.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    except Exception:
        # Diagnose instead of guessing: show who else is connected and what they're doing.
        with get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT pid, state, now() - xact_start AS xact_age, left(query, 120) "
                    "FROM pg_stat_activity WHERE datname = current_database() "
                    "AND pid <> pg_backend_pid()"
                )
            ).all()
        print("\n[test cleanup failed] other sessions:", *rows, sep="\n  ")
        raise
    get_redis().flushdb()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {get_settings().csrf_header_name: token}


def register(
    client: TestClient, email: str = "ada@example.com", password: str = "correct-horse-battery"
) -> dict[str, Any]:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Ada"},
        headers=csrf_headers(client),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]
