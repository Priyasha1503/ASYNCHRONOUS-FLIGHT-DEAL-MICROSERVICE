# SkyScout AI — Progress Log

Evidence-based log: every "passed" below was produced by a command actually run on the date shown.

## Phase 1 — Foundation (2026-10-23)

**Environment:** Windows 11, Docker Desktop 29.2 (Compose v5.0.2), Python 3.12.14 via uv 0.12.15,
Node 22.23 (in `node:22-alpine` container — not installed on host), Postgres 16.15, Redis 7.

### Implemented
- **Backend skeleton** (`backend/app`): settings with production guards (`core/config.py`), sync
  SQLAlchemy engine w/ pooling + statement timeout (`core/db.py`), Redis client, JSON logging with
  request-id correlation and secret redaction, Prometheus metrics, consistent error envelope.
- **Schema** (Alembic `0001`): `users`, `user_preferences`, `sessions` with FK cascades, unique and
  check constraints (lower-case email, ISO-4217 currency, IATA home airport), UTC `timestamptz`.
- **Auth:** register / login / logout / me / preferences / delete-account. argon2id, opaque 256-bit
  session tokens (only SHA-256 stored), HttpOnly SameSite=Lax cookies, double-submit CSRF on every
  unsafe method, per-IP and per-email login rate limit (Redis), timing-equalised unknown-email login.
- **Health:** `/health/live`, `/health/ready` (PG required → 503; Redis down → `degraded`), `/metrics`.
- **Workers:** Celery app (acks_late, reject-on-lost, time limits) + beat schedule; hourly expired-
  session purge task.
- **Infra:** `docker-compose.yml` (postgres, redis, one-shot migrate, api, worker, beat, web) with
  healthchecks; test DB init script; backend + frontend Dockerfiles (non-root); `.env.example`;
  GitHub Actions CI (`.github/workflows/ci.yml`).
- **Frontend:** Next.js 16 / React 19 / Tailwind 4. Design tokens from `design-references/`
  (`src/styles/tokens.css`), light + dark themes, reduced-motion support. Components: Button, Field/
  Input/Switch, Card/Skeleton, SourceBadge, FormAlert, CSS sky backdrop, logo. Pages: landing,
  register, sign-in, account settings (profile, preferences, sign-out, delete account), 404.

### Phase 1 verification (all commands run 2026-10-23)
| Acceptance criterion | Command | Result |
|---|---|---|
| Migrations on empty DB | `uv run pytest` (drops schema → `alembic upgrade head`; also downgrade→upgrade round-trip + model/migration diff) | **Pass** |
| Migrations in Docker | `docker compose up` → `migrate` service | **Pass** (exit 0, `-> 0001`) |
| `/health/ready` 200 | `GET :8000/health/ready` | **Pass** `{"status":"ok"}`; degraded/503 paths covered by tests |
| Auth API tests | `uv run pytest` | **27 passed** (auth, CSRF, session revocation, rate limit, isolation, prefs validation, delete cascade, health, metrics, prod-config guards, log redaction) |
| Backend static checks | `ruff check`, `ruff format --check`, `mypy --strict app tests` | **Clean** |
| Frontend static checks | `prettier --check`, `eslint`, `tsc --noEmit`, `next build` | **Clean / build OK** |
| Services start | `docker compose up -d --build --wait` | **Pass**: postgres, redis, api (healthy), worker, beat, web |
| Worker executes tasks | `ping.delay().get()`, `purge_expired_sessions.delay().get()` | **Pass** (`pong`, `0`) |
| Web → API via rewrite | `scripts/smoke_stack.py create` | **Pass** (pages 200, register/prefs/me through :3000) |
| Durable across restart | `docker compose restart` (all incl. postgres) → `smoke_stack.py verify` | **Pass** (login + saved prefs intact) |
| Initial interface renders | `scripts/visual-smoke.mjs` (Playwright 1.64.1 in Docker) | **Pass**; see below |

**Visual / browser verification** (`mcr.microsoft.com/playwright:v1.64.1-noble`, Chromium):
- Viewports 1440×900 and 390×844; light + dark colour schemes for the landing page; light for
  register/account/sign-in; mobile menu open state.
- Flows driven through the real UI: client-side validation errors → registration → account page →
  save preferences → sign-out (desktop) / delete account (mobile) → server confirms session invalid.
- No horizontal overflow; no page errors; no 5xx. Only console errors are the script's own deliberate
  post-logout `GET /me` → 401 check.
- Defects found **and fixed** in this pass: sign-out/delete raced the account page's auth redirect and
  landed on `/signin?next=/account`; hero paragraph/CTAs sat on the bright horizon band (contrast);
  account selects misaligned beside a field with a hint; plane overlapped headline on mobile;
  anonymous session probe logged a 401 on every page (added `GET /auth/session`).
- Observation (not fixed, environment-dependent): on a cold web container, hydration via
  `host.docker.internal` took ~7 s; not yet measured on a normal network path. Track in Phase 7 perf work.

## Phase 2 — Flight domain + demo provider (2026-10-29)

### Implemented
- `app/domain/` (pure, no I/O):
  - `query.py`: `UpstreamQuery` (only params that change provider output) with canonical
    serialization and versioned cache key; `Preferences` split into hard constraints and soft
    preferences.
  - `offers.py`: normalized `Offer → Slice → Segment` with tz-aware local times, `Baggage`
    (`None` = unconfirmed), `FareSource` label, https-only booking links, and a UTC-based itinerary
    fingerprint.
  - `validation.py`: drops offers that don't answer the query, with reason codes (currency, price
    precision, cabin, route, date, segment order, connection limits); dedupes by fingerprint.
  - `constraints.py`: hard filter + report (counts per constraint, single-constraint relaxations with
    the value needed).
  - `ranking.py`: weighted, min-max-normalized score with per-factor explanations; unconfirmed data
    earns no credit; picks for cheapest, best match and up to 3 genuine trade-offs (faster, fewer
    stops, confirmed bag).
  - `pipeline.py`: `evaluate()` = normalize → constrain → rank → recommend.
  - `airports.py`: 57 real airports (tz, coordinates, metro groups for "nearby").
- `app/providers/`: `FlightProvider` interface + capabilities, retryable/permanent error taxonomy,
  registry driven by `ENABLED_PROVIDERS`, and the **demo provider**: seeded from the query's cache
  key, fictional airlines, fixed illustrative FX, no booking links, failure injection for tests.
- `app/cli.py`: `uv run python -m app.cli search LHR JFK 2026-12-10 --return 2026-12-17 --budget 900`.
- Tests split into `tests/unit` (no infrastructure) and `tests/api` (Postgres + Redis).

### Phase 2 verification (2026-10-29)
| Acceptance criterion | Command | Result |
|---|---|---|
| Constraint / ranking / normalization unit tests | `uv run pytest tests/unit` | **81 passed** in 0.7 s |
| Same input → same demo output | `test_same_query_same_offers_regardless_of_clock`, `test_pipeline_end_to_end_on_demo_data_is_deterministic` | **Pass** |
| Demo offers always valid & labelled | 6 routes (incl. date-line, DST, long-haul) × one-way/round-trip | **Pass** |
| Budget never exceeded; reasons when nothing qualifies | constraint tests + CLI run with $150 budget | **Pass** |
| Whole suite + static checks | `pytest`, `ruff check`, `ruff format --check`, `mypy --strict` | **108 passed**, clean |

### Known gaps carried forward
- Arrival-day offset ("+1") must be shown in the UI (Phase 3).
- Demo prices are a simple model, not market data; real fares come in Phase 6.

## Phase 3 — Search API + UI (2026-10-29)

### Implemented
- **Shared offer cache** (`app/cache/offers.py`): cache-aside per provider × upstream query, TTL
  `SEARCH_CACHE_TTL_S` (600 s), single-flight via `SET NX PX` lock + compare-and-delete release,
  waiters poll; crashed winner's lock expires; failures are never cached.
- **Provider resilience** (`app/services/resilience.py`): Redis-shared circuit breaker
  (threshold/window/cooldown, half-open probe), retries only for retryable errors with exponential
  backoff + full jitter, bounded by the search deadline; per-provider request budget.
- **Search service** (`app/services/search.py`): parallel fan-out on a bounded thread pool, overall
  deadline, nearby-airport expansion (capped), per-provider status (`ok/cached/timeout/…`), cached
  live quotes relabelled `cached`.
- **Redis outage handling** (`app/core/redis.py`): redis-py 6's default retries made one call against
  a dead server take **5.6 s** (measured); now ≤1 quick retry, and a per-client "down" memo skips
  Redis for 5 s after a failure. Search degrades to direct, concurrency-capped provider calls.
- **API**: `POST /api/v1/searches` (anonymous allowed, CSRF, per-user/IP rate limit),
  `GET /api/v1/airports`, `GET /api/v1/providers`. Cross-field query rules surface as 422.
- **UI**: hero search form (airport combobox per WAI-ARIA, passengers popover, advanced options),
  `/search` results: demo banner, provider coverage/freshness, cheapest + best-match + trade-offs with
  reasons, sortable list, airport-local times with "+1", unknown baggage labelled, expandable
  details + score breakdown, filters (sidebar / mobile sheet) that re-run the search (cache hit),
  no-results explanation with honest one-click relaxations, skeletons, error state with request id.
  URL is the source of truth (shareable searches); controls update optimistically.

### Phase 3 verification (2026-10-29)
| Acceptance criterion | Evidence | Result |
|---|---|---|
| Repeat search is a cache hit | `test_repeat_search_is_a_cache_hit`; live stack: miss 360 ms → hit 42 ms → new budget still hit 26 ms | **Pass** |
| Stampede coalesced | `test_stampede_is_coalesced_into_one_provider_call` (12 concurrent → 1 provider call) | **Pass** |
| Failure handling | tests: crashed-winner lock, Redis down (<1.5 s), partial failure, deadline timeout, retry once, no retry on permanent, circuit opens, cache TTL | **Pass** |
| API contract & validation | `tests/api/test_search_api.py` (labels, money as string, 422s, CSRF, 429, relaxation counts) | **Pass** |
| Whole backend suite + static checks | `pytest`, `ruff`, `mypy --strict` | **129 passed**, clean |
| Frontend static checks | prettier, eslint, tsc | **Clean** |
| Search via the actual UI with "Demo data" label | `scripts/visual-search.mjs` (Playwright, 1440×900 + 390×844): hero → combobox → results → details → sort → filter → impossible budget → relax → invalid link | **Pass, no console/5xx/overflow** |

Defects found by the browser pass and fixed: filter controls snapped back until navigation finished
(now `useOptimistic`); duplicate ids / merged radio group when sidebar and mobile sheet were both
mounted; relaxation button overstated how many flights it adds; long button overflowed on mobile.

### Not yet done (by design, later phases)
- Flexible-date search (Addendum §I.1) — nearby airports are done; flexible dates deferred.
- Save / monitor buttons → Phase 4.

## Phase 4 — Saved searches, monitoring, alerts (2026-10-29)

### Implemented
- **Schema** (Alembic `0002`): `saved_searches`, `monitored_queries` (shared per upstream query),
  `monitoring_rules`, `refresh_runs`, `price_observations`, `rule_checks`, `notifications`,
  `delivery_attempts`, `job_failures`, with the idempotency constraints in
  `app/models/monitoring.py`.
- **Domain** (`app/domain/monitoring.py`): pure rule evaluation → `below_target` (1% price bands),
  `price_drop` (≥ threshold vs last check), `now_available` (transition only).
- **Services** (`app/services/monitoring.py`): create/update/pause/delete with per-user limits and
  ownership; scheduler (`FOR UPDATE SKIP LOCKED`, epoch-aligned slots, past departures stop);
  refresh runs (provider calls outside transactions, stale-run takeover, failed runs don't count as
  checks); per-rule atomic evaluation.
- **Notifications** (`app/services/notifications.py`): in-app rows + email channel with honest
  statuses; console (simulated) and SMTP backends; retries with backoff; dead-letter `job_failures`.
- **Workers**: beat every 60 s → `schedule_due_monitors`; `refresh_monitored_query`;
  `send_notification_email`; stale-run sweep.
- **API**: `/monitors` CRUD, `/monitors/{id}/refresh` (cooldown), `/monitors/{id}/simulate-price-change`
  (demo + non-production only), `/notifications` (keyset pagination, unread count, mark read/all).
- **UI**: **Monitor this trip** dialog on results (target price prefilled 10% below the current
  cheapest qualifying fare, drop %, frequency, "now available"); Monitoring centre with target
  progress; monitor page with validated price-history chart (gaps for "nothing qualified", target
  line, table view), recent checks, alert settings, pause/resume/check now/delete, labelled demo
  simulator; Alerts inbox; header bell with unread count.

### Phase 4 verification (2026-10-29)
| Acceptance criterion | Evidence | Result |
|---|---|---|
| Duplicate task ⇒ no duplicate observation/notification | `test_duplicate_refresh_task_creates_nothing_twice`, `test_concurrent_duplicate_tasks_are_safe` (4 concurrent tasks → 1 run, 1 check, 1 alert) | **Pass** |
| Alerts once per event; further drop re-alerts | `test_alert_lifecycle_with_simulated_price_changes`; live stack: scheduled check at the same price 9 s after a simulated drop created 0 alerts | **Pass** |
| Failure handling | stale-run takeover, failed provider not counted, email failure recorded + retry cap, simulation 404 in production | **Pass** |
| Authorization / isolation | `test_cross_user_access_is_404` (+ notifications), browser: second user sees "doesn't exist or isn't yours"; shared-query runs before a user's monitor are hidden | **Pass** |
| Whole backend suite + static checks | `pytest`, `ruff`, `mypy --strict` | **151 passed**, clean |
| Save + monitor + observe persisted changes via the UI | `scripts/visual-monitoring.mjs` against the real worker: register → search → Monitor this trip → check → simulate −25% → 2 alerts → table view → 2nd user blocked | **Pass, no console/5xx/overflow** |
| Data survives restart | `docker compose restart` (all services) → `scripts/verify_monitoring_persistence.py`: monitor, target, history, runs, best price, alerts, next check | **Pass** |

Defects found and fixed in this phase: `FOR UPDATE` across eager-loaded outer joins (now
`FOR UPDATE OF monitoring_rules`); `list` method shadowing the builtin in class annotations;
service importing an API schema (moved `SearchRequest` into the domain); 81-char constraint name
over Postgres's limit; chart dark-mode colours failing the validator; "Recent checks" leaking
pre-existing shared runs; time-axis showing duplicate dates; flaky TTL test (now uses PTTL).

### Known limitations
- Simulated demo price changes apply to the shared demo query on that instance (documented).
- Email via SMTP is implemented but not exercised against a real server here (console backend used).
- Dashboard summary (Phase 5) not built yet; the monitor page covers per-trip intelligence.

## Phase 6 (part 1) — Real fares + affiliate booking via Travelpayouts (2026-10-29)

**User decision:** booking = redirect to airline/agency via affiliate links; no in-app checkout.

### Implemented
- `app/providers/travelpayouts.py`: `/aviasales/v3/prices_for_dates` adapter. Token in header,
  timeouts, full error mapping (401/403 auth, 429 rate-limited w/ reset, 5xx/network unavailable,
  4xx unsupported, malformed/`success:false` invalid), per-item mapping with unmappable items
  reported (e.g. timestamps without UTC offset are rejected, not guessed), booking links made
  absolute with our `marker`. 1 adult / economy only.
- Domain: `Slice.detail="summary"` + `declared_stops`; optional flight numbers; journey-level
  duration limit for summary slices.
- Per-provider cache TTL (Travelpayouts 3 h); provider `booking` mode (`redirect`/`checkout`/`none`)
  in the API.
- UI: **Check price & book** (new tab, `rel="sponsored noopener noreferrer"`), honest copy and
  commission disclosure at the button and in the footer; "seen recently" instead of a fetch time
  for observed fares; summary itineraries say connection details aren't provided.
- `scripts/travelpayouts_smoke.py`: live check + records a real response for the contract fixture.

### Verification (2026-10-29)
| Check | Evidence | Result |
|---|---|---|
| Adapter contract (mocked HTTP) | `tests/unit/test_travelpayouts.py` (request shape, header token, mapping, links, errors, invalid bodies, API serialization) | **Pass** |
| Whole backend suite + static checks | `pytest`, `ruff`, `mypy --strict` | **169 passed**, clean |
| End-to-end through the running stack | Stack pointed at a local mock serving the documented response shape (dummy token): search → observed offers → booking URLs with our marker (foreign marker replaced) → dedupe across nearby queries | **Pass** |
| Browser | `scripts/visual-booking.mjs` desktop + mobile: no demo banner, Observed label, link `https://www.aviasales.com/…marker=…`, `target=_blank`, `rel` sponsored/noopener, disclosure visible, summary details text, no overflow | **Pass** |

Defect found by the mock E2E and fixed: API `SegmentOut.flight_number` was required, so summary
offers (no return flight number) returned 500.

### NOT verified (blocked on credentials)
- A real Travelpayouts response: field list, the exact marker parameter for attribution, rate-limit
  headers. The fixture is **documented shape, not recorded data**. Run
  `scripts/travelpayouts_smoke.py` once `TRAVELPAYOUTS_TOKEN`/`TRAVELPAYOUTS_MARKER` are set, then
  replace the fixture with the recorded file and re-run the contract tests.
- That an Aviasales click with our marker is attributed in the Travelpayouts dashboard.

---

### Phase 1 known gaps / deferred
- Uvicorn's own access/startup logs are not JSON yet (app logs are). → Phase 7.
- Email notification transport not present yet (preference only). → Phase 4.
- Rate limiter fails open if Redis is down (documented decision). → re-review Phase 7.
- No search UI yet by design; landing deliberately shows no non-functional search form. → Phase 3.
- Celery worker on native Windows needs `--pool=solo`; Docker is the supported path.
