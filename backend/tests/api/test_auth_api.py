from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.security import hash_token
from app.models import User, UserSession
from tests.api.conftest import csrf_headers, register

PW = "correct-horse-battery"


def test_register_sets_session_and_returns_profile(client: TestClient) -> None:
    body = register(client, "Ada@Example.com")
    assert body["email"] == "ada@example.com"  # normalized
    assert body["preferences"]["currency"] == "USD"
    assert "password_hash" not in body
    assert client.cookies.get(get_settings().session_cookie_name)
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_password_and_session_token_are_not_stored_in_plaintext(client: TestClient) -> None:
    register(client)
    token = client.cookies.get(get_settings().session_cookie_name)
    assert token
    with get_sessionmaker()() as db:
        user = db.scalar(select(User))
        assert user and user.password_hash.startswith("$argon2id$")
        assert PW not in user.password_hash
        sess = db.scalar(select(UserSession))
        assert sess and sess.token_hash == hash_token(token) and sess.token_hash != token


def test_duplicate_email_conflict(client: TestClient) -> None:
    register(client)
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "ADA@example.com", "password": PW},
        headers=csrf_headers(client),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_register_validation_errors_use_envelope(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
        headers=csrf_headers(client),
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    fields = {d["loc"][-1] for d in err["details"]}
    assert {"email", "password"} <= fields
    assert "request_id" in err


def test_missing_or_wrong_csrf_rejected(client: TestClient) -> None:
    payload = {"email": "a@example.com", "password": PW}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 403
    client.get("/api/v1/auth/csrf")
    r = client.post("/api/v1/auth/register", json=payload, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_login_success_and_failure(client: TestClient) -> None:
    register(client)
    client.cookies.clear()
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
        headers=csrf_headers(client),
    )
    assert bad.status_code == 401
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": PW},
        headers=csrf_headers(client),
    )
    assert unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]  # no enumeration
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "ADA@example.com", "password": PW},
        headers=csrf_headers(client),
    )
    assert ok.status_code == 200
    assert client.get("/api/v1/me").status_code == 200


def test_logout_revokes_server_side_session(client: TestClient) -> None:
    register(client)
    token = client.cookies.get(get_settings().session_cookie_name)
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    # Replaying the old cookie must not work either.
    client.cookies.set(get_settings().session_cookie_name, token or "")
    assert client.get("/api/v1/me").status_code == 401


def test_session_probe_is_not_an_error_when_signed_out(client: TestClient) -> None:
    r = client.get("/api/v1/auth/session")
    assert r.status_code == 200 and r.json() == {"user": None}
    body = register(client)
    r = client.get("/api/v1/auth/session")
    assert r.status_code == 200 and r.json()["user"]["id"] == body["id"]
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert client.get("/api/v1/auth/session").json() == {"user": None}


def test_unauthenticated_and_garbage_session(client: TestClient) -> None:
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    client.cookies.set(get_settings().session_cookie_name, "garbage")
    assert client.get("/api/v1/me").status_code == 401


def test_update_preferences(client: TestClient) -> None:
    register(client)
    h = csrf_headers(client)
    r = client.patch(
        "/api/v1/me/preferences",
        json={"currency": "eur", "home_airport": "lhr", "timezone": "Europe/London"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    prefs = r.json()["preferences"]
    assert (prefs["currency"], prefs["home_airport"], prefs["timezone"]) == (
        "EUR",
        "LHR",
        "Europe/London",
    )
    assert (
        client.patch("/api/v1/me/preferences", json={"currency": "EURO"}, headers=h).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/me/preferences", json={"timezone": "Mars/Base"}, headers=h
        ).status_code
        == 400
    )
    assert (
        client.patch("/api/v1/me/preferences", json={"is_admin": True}, headers=h).status_code
        == 422
    )
    assert (
        client.patch("/api/v1/me/preferences", json={"currency": None}, headers=h).status_code
        == 400
    )


def test_sessions_are_isolated_between_users(client: TestClient) -> None:
    from app.main import create_app

    a = register(client, "a@example.com")
    with TestClient(create_app()) as other:
        b = register(other, "b@example.com")
        assert other.get("/api/v1/me").json()["id"] == b["id"]
    assert client.get("/api/v1/me").json()["id"] == a["id"]


def test_delete_account_requires_password_and_cascades(client: TestClient) -> None:
    register(client)
    h = csrf_headers(client)
    assert (
        client.request("DELETE", "/api/v1/me", json={"password": "nope"}, headers=h).status_code
        == 401
    )
    assert (
        client.request("DELETE", "/api/v1/me", json={"password": PW}, headers=h).status_code == 204
    )
    with get_sessionmaker()() as db:
        assert db.scalar(select(User)) is None
        assert db.scalar(select(UserSession)) is None


def test_login_rate_limited(client: TestClient, monkeypatch: object) -> None:
    get_settings().auth_rate_limit_per_minute = 3
    try:
        h = csrf_headers(client)
        codes = [
            client.post(
                "/api/v1/auth/login", json={"email": "x@example.com", "password": "x"}, headers=h
            ).status_code
            for _ in range(5)
        ]
    finally:
        get_settings().auth_rate_limit_per_minute = 1000
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]
