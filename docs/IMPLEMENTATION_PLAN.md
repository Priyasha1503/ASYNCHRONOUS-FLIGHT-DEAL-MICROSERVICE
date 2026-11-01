# SkyScout AI — Implementation Plan

Each phase ends only when its acceptance criteria are verified by commands actually run; results are
logged in `docs/PROGRESS.md`.

| Phase | Scope | Acceptance criteria |
|---|---|---|
| 1 Foundation | Docs; backend skeleton (settings, DB, Alembic, logging, health, metrics); auth (register/login/logout/me, sessions, CSRF); compose files; Next.js scaffold | `alembic upgrade head` on empty DB; `/health/ready` 200; auth API tests pass; web renders |
| 2 Domain + demo provider | Domain models, provider interface, deterministic demo fixtures, normalization, constraints, ranking + explanations | Unit tests for constraints/ranking/normalization pass; same input → same demo output |
| 3 Search | `/searches` endpoint, cache + single-flight, provider status, search form + results UI with sort/filter | Search end-to-end via UI with "Demo data" label; cache hit on repeat; stampede test passes |
| 4 Monitoring | Saved searches, monitoring rules, shared monitored queries, beat scheduler, refresh runs, observations, rule evaluation, notifications + delivery | Duplicate task ⇒ no duplicate observation/notification (tested); data survives restart |
| 5 Dashboard | Dashboard, monitoring center, history charts with gaps, provider health, notifications UI | All dashboard numbers traced to DB queries; empty states verified |
| 6 Real providers | Travelpayouts (observed fares) + Duffel (live) adapters, contract tests on recorded fixtures, env config | Adapters pass contract tests; live calls only when keys present; otherwise documented blocker |
| 7 Hardening | Security review, rate limits, Playwright E2E + screenshots (desktop/mobile), load tests, release verification | `docs/RELEASE_VERIFICATION.md` with real outcomes |

Design work (`DESIGN_BRIEF.md`) is gated on the user's references; backend phases do not wait on it.

## Risks
1. **Provider access** — free real-time APIs are scarce (Amadeus Self-Service closed July 2026).
   Mitigation: abstraction + demo provider; Travelpayouts for observed fares; Duffel for live.
2. **Provider cost** — Duffel charges for high search-to-book ratios. Mitigation: shared query cache,
   monitoring cadence budgets per provider.
3. **Local toolchain** — development now happens on the user's Windows machine with Docker Desktop.
   Node 22 is not installed natively yet; frontend commands run in a `node:22-alpine` container
   (see README) until it is. Python 3.15 is the system default, so the backend pins 3.12 via uv.
