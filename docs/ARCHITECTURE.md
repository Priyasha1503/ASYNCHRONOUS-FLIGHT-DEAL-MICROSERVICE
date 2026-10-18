# SkyScout AI — Architecture

## 1. Shape: modular monolith, four processes

```
            ┌──────────────┐  same-origin /api/* rewrite   ┌──────────────────┐
 browser ──▶│ web (Next.js)│──────────────────────────────▶│ api (FastAPI)    │
            └──────────────┘                               │  /api/v1/*       │
                                                           └───┬────────┬─────┘
                                                               │        │
                                       ┌───────────────────────┘        │
                                       ▼                                ▼
                              ┌────────────────┐               ┌───────────────┐
                              │ PostgreSQL     │◀──────────────│ Redis         │
                              │ system of record│              │ cache, locks, │
                              └────────────────┘               │ broker, limits│
                                       ▲                       └───────┬───────┘
                                       │                               │
                              ┌────────┴───────┐   enqueue    ┌────────┴──────┐
                              │ worker (Celery)│◀─────────────│ beat (Celery) │
                              └────────────────┘              └───────────────┘
```

One Python package (`backend/app`) is shared by `api`, `worker` and `beat`; each runs as its own
process/container. The frontend is a separate Next.js app.

## 2. Backend layers (`backend/app`)

| Layer | Package | Rule |
|---|---|---|
| API | `api/v1/*` | HTTP only: parse, auth, call a service, map errors. No SQL, no provider calls. |
| Services | `services/*` | Use cases & transactions. Framework-free; tested directly. |
| Domain | `domain/*` | Pure models + logic: search params, offers, constraints, ranking, price-change rules. No I/O. |
| Repositories | `repositories/*` | SQLAlchemy queries; return ORM or domain objects. |
| Providers | `providers/*` | `FlightProvider` adapters (demo, travelpayouts, duffel) → normalized `Offer`. |
| Infra | `core/*`, `cache/*` | Settings, DB engine, Redis, logging, metrics, security. |
| Workers | `workers/*` | Celery tasks — thin wrappers that call services. |

## 3. Key flows

### 3.1 Search
1. `POST /api/v1/searches` with validated `SearchRequest`.
2. `SearchService` derives the **upstream query** (route, dates, pax, cabin, currency — the params that
   change provider output) and a canonical hash. User-only preferences (budget, stops, airlines, times,
   bags) are applied *after* retrieval so one upstream query serves many users.
3. For each enabled provider: cache-aside on `offers:{provider}:{hash}`.
   - hit → `cached` label with age.
   - miss → **single-flight**: `SET lock:{key} <token> NX PX <ttl>`. Winner calls provider (timeout,
     retries w/ jittered backoff, circuit breaker), writes cache, releases lock via compare-and-delete
     Lua script. Losers wait on the result key up to a bounded time, else return a "pending/partial"
     provider status. A crashed winner's lock expires by TTL.
4. Merge, dedupe (offer fingerprint = carrier+flight numbers+departure times+cabin), apply hard
   constraints, rank, build recommendation buckets + "why" explanations + elimination report.
5. Response includes per-provider status (`ok | cached | timeout | error | rate_limited | circuit_open
   | disabled`) so partial failure is visible, never silent.

### 3.2 Monitoring (shared schedule)
- A `MonitoredQuery` row exists per distinct upstream hash; `MonitoringRule`s (per user) point at it.
- Beat runs `schedule_due` every minute: selects queries whose `next_run_at <= now` (respecting the
  *fastest* active member rule, bounded by config min interval and per-provider budgets), and enqueues
  `refresh_query(query_id, slot)` where `slot` = scheduled timestamp bucket.
- Idempotency: `refresh_runs` has `UNIQUE(query_id, slot)`; a duplicate task sees the row and exits.
- Observations: `UNIQUE(query_id, provider, offer_fingerprint, slot)` — re-runs cannot duplicate.
- After persisting, `evaluate_rules(query_id, slot)` checks each active rule against its own hard
  constraints and emits `Notification` rows with `UNIQUE(rule_id, dedup_key)`; dedup_key encodes the
  event kind + price band so the same event can't alert twice, but a *further* drop can.
- `dispatch_notification(id)` sends via channel adapters, recording each `DeliveryAttempt`. Email
  status is `queued → sent | failed`; "sent" means the SMTP/API accepted it, nothing more.

### 3.3 Auth
Email + password (argon2id). Server-side sessions: random 256-bit token in an HttpOnly, Secure (prod),
SameSite=Lax cookie; only its SHA-256 is stored in `sessions`. CSRF: double-submit token (readable
`csrf` cookie echoed in `X-CSRF-Token`) required on all unsafe methods. Every repository query for
user-owned data filters by `user_id`; access to another user's id returns 404.

## 4. Reliability
- httpx timeouts (connect 3 s / total configurable), retry only on network/5xx/429 with exponential
  backoff + full jitter and a max attempt cap; 4xx validation → no retry.
- Circuit breaker per provider in Redis (failure count window → open for cooldown → half-open probe).
- Provider rate limiting: Redis token bucket per provider, shared by api and workers.
- Redis down: search degrades to direct provider calls with a concurrency cap and no caching; sessions
  and all durable data live in Postgres, so auth keeps working. Health `/ready` reports degraded.
- Postgres down: `/ready` fails; API returns 503 with a stable error body.
- Celery: `acks_late`, `task_reject_on_worker_lost`, bounded retries, failures land in
  `job_failures` (dead-letter table) for inspection.

## 5. Data model (summary — see migrations for truth)
`users, user_preferences, sessions, saved_searches, monitored_queries, monitoring_rules,
refresh_runs, price_observations, notifications, delivery_attempts, provider_calls, job_failures`.
Money `NUMERIC(12,2)` + `CHAR(3)` currency. All timestamps `timestamptz` UTC.

## 6. Scaling path
| Stage | Users | Change |
|---|---|---|
| 1 | ≤1k | 1 api (2–4 uvicorn workers), 1 worker, 1 beat, managed PG + Redis |
| 2 | ≤10k | horizontal api replicas; worker autoscaling on queue depth; PG read replica for dashboards; partition `price_observations` by month |
| 3 | beyond | dedicated provider-gateway service if quotas need central brokering |

The dominant cost driver is **upstream provider calls**, not CPU — shared query hashing + cache is the
main scaling lever. Numbers will be filled from measured load tests only.

## 7. Observability
JSON logs with request id; Prometheus `/metrics` (request latency/errors, provider latency/errors,
cache hit/miss, task outcomes, notification outcomes); `/health/live`, `/health/ready`
(PG + Redis checks — explicitly *not* a claim that providers are healthy; provider health has its own
endpoint derived from recent `provider_calls`).
