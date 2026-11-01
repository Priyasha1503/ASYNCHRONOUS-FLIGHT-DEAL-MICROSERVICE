"""Phase 1 smoke test against the running compose stack via the web origin (port 3000)."""

import sys
import time
import uuid

import httpx

WEB = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"
phase = sys.argv[1] if len(sys.argv) > 1 else "all"
email_file = sys.argv[2] if len(sys.argv) > 2 else None


def check(label: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {label} {extra}")
    if not cond:
        sys.exit(1)


if phase in ("all", "create"):
    for path in ["/", "/signin", "/register", "/account"]:
        r = httpx.get(WEB + path, timeout=20)
        check(f"GET {path}", r.status_code == 200, f"[{r.status_code}, {len(r.text)} bytes]")
    home = httpx.get(WEB + "/").text
    check("landing contains hero copy", "Find the fare that fits" in home)
    check("security header set", httpx.get(WEB + "/").headers.get("x-frame-options") == "DENY")
    r = httpx.get(API + "/health/ready")
    check("api ready", r.status_code == 200 and r.json()["status"] == "ok", r.text)

    c = httpx.Client(base_url=WEB, timeout=20)
    t0 = time.perf_counter()
    token = c.get("/api/v1/auth/csrf").json()["csrf_token"]
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery", "display_name": "Smoke"},
        headers={"X-CSRF-Token": token},
    )
    check("register via web rewrite", r.status_code == 201, f"[{r.status_code}]")
    token = c.cookies.get("skyscout_csrf")
    r = c.patch(
        "/api/v1/me/preferences", json={"currency": "eur"}, headers={"X-CSRF-Token": token}
    )
    check("update prefs", r.status_code == 200 and r.json()["preferences"]["currency"] == "EUR")
    check("/me with session cookie", c.get("/api/v1/me").json()["email"] == email)
    print(f"      auth round-trips took {time.perf_counter() - t0:.2f}s")
    if email_file:
        open(email_file, "w").write(email)

if phase == "verify":
    email = open(email_file).read().strip()
    c = httpx.Client(base_url=WEB, timeout=20)
    token = c.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-battery"},
        headers={"X-CSRF-Token": token},
    )
    check("login after restart", r.status_code == 200, f"[{r.status_code}]")
    check(
        "preferences persisted across restart", r.json()["preferences"]["currency"] == "EUR"
    )
