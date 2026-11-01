"""After `docker compose restart`: the Phase 4 journey's monitor, history and alerts must still exist.

    uv run --project backend python scripts/verify_monitoring_persistence.py shots/p4/creds.json
"""

import json
import sys

import httpx

WEB = "http://127.0.0.1:3000"


def main(path: str) -> int:
    creds = json.load(open(path))
    c = httpx.Client(base_url=WEB, timeout=30)
    token = c.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = c.post(
        "/api/v1/auth/login",
        json={"email": creds["email"], "password": creds["password"]},
        headers={"X-CSRF-Token": token},
    )
    ok = True

    def check(label: str, cond: bool, extra: object = "") -> None:
        nonlocal ok
        ok &= cond
        print(f"{'PASS' if cond else 'FAIL'}  {label} {extra}")

    check("login after restart", r.status_code == 200, r.status_code)
    monitor_id = creds["monitorUrl"].rsplit("/", 1)[-1]
    m = c.get(f"/api/v1/monitors/{monitor_id}").json()
    check("monitor persisted", m.get("id") == monitor_id, m.get("status"))
    check("target persisted", m.get("target_price") is not None, m.get("target_price"))
    check("price history persisted", len(m.get("history", [])) >= 2, f"{len(m.get('history', []))} checks")
    check("refresh runs persisted", len(m.get("runs", [])) >= 2, f"{len(m.get('runs', []))} runs")
    check("best price persisted", m.get("best_price") is not None, m.get("best_price"))
    notes = c.get("/api/v1/notifications").json()
    kinds = sorted(n["kind"] for n in notes["items"])
    check("alerts persisted", {"below_target", "price_drop"} <= set(kinds), kinds)
    check("scheduler still has it queued", m.get("next_check_at") is not None, m.get("next_check_at"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
