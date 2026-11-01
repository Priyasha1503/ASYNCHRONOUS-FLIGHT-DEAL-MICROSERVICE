<div align="center">

# ✈️ SkyScout AI

**Flight price intelligence — find the cheapest flight that actually meets your requirements,
see *why* it was recommended, and get alerted when the fare hits your target.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/backend%20tests-169%20passing-brightgreen)

</div>

---

## 📖 Table of contents

1. [What is SkyScout?](#-what-is-skyscout)
2. [Key features](#-key-features)
3. [Architecture](#-architecture)
4. [Tech stack](#-tech-stack)
5. [Project structure](#-project-structure)
6. [Quick start (Docker)](#-quick-start-docker)
7. [Local development](#-local-development-hot-reload)
8. [Configuration](#-configuration)
9. [Real fares & booking](#-real-fares--booking-travelpayouts--aviasales)
10. [Price monitoring & alerts](#-price-monitoring--alerts)
11. [API overview](#-api-overview)
12. [Testing & quality](#-testing--quality)
13. [Security](#-security)
14. [Roadmap](#-roadmap--project-status)
15. [Troubleshooting](#-troubleshooting)
16. [Documentation](#-documentation)
17. [Author & contact](#-author--contact)

---

## 🧭 What is SkyScout?

Most flight search sites show you the cheapest number on the page — even when that flight has three
stops, a 14-hour layover, or no checked bag. **SkyScout** works the other way round:

1. You say what you **need** (hard constraints: max stops, max duration, baggage, budget, cabin…)
   and what you'd **prefer** (soft preferences).
2. SkyScout fans out to flight providers **in parallel**, normalizes every offer into one model,
   **drops anything that doesn't qualify**, and **ranks** the rest with a transparent, weighted score.
3. You get the **cheapest qualifying flight**, the **best overall match**, and up to three genuine
   **trade-offs** (faster, fewer stops, bag included) — each with a plain-English explanation.
4. Like a trip but not the price? Click **Monitor this trip**, set a target, and background workers
   keep checking. When the fare hits your target you get an **in-app alert and an email**.

**Data honesty is a core rule:** SkyScout never guesses. Unconfirmed baggage is shown as unknown,
demo data is labelled as demo, "seen recently" fares are not presented as live quotes, and if no
flight meets your constraints it tells you *which* constraint to relax and how many flights that
would unlock.

---

## ✨ Key features

### 🔎 Smart search
- Parallel provider fan-out with an overall **deadline**, per-provider status (`ok` / `cached` / `timeout` / …)
- **Nearby-airport expansion** (metro groups, e.g. all London airports) across 57 real airports
- Normalized `Offer → Slice → Segment` model with timezone-aware local times and "+1 day" arrivals
- **Hard-constraint filtering** with a report of why offers were excluded
- **Explainable ranking** — min-max-normalized weighted score with per-factor breakdown
- **One-click relaxations** when nothing qualifies ("allow 1 stop → +12 flights")
- Shareable searches — the URL is the source of truth

### ⚡ Performance & resilience
- **Redis cache-aside** per provider × query with **single-flight locking** — 12 concurrent identical
  searches result in exactly **1** provider call (repeat search: ~360 ms → ~40 ms)
- **Circuit breaker** shared through Redis (closed → open → half-open probe)
- **Retries with exponential backoff + full jitter**, only for retryable errors, bounded by the deadline
- **Graceful degradation** — if Redis is down, search still works (direct, concurrency-capped calls)

### 📈 Price monitoring
- **Monitor this trip** with target price, price-drop %, check frequency and "now available" alerts
- Users watching the same route **share one refresh** (deduplicated monitored queries)
- Scheduler uses `FOR UPDATE SKIP LOCKED` — safe with many workers, no double processing
- **Idempotent** tasks — duplicate jobs never create duplicate observations or alerts
- Price-history chart with target line, gaps for "nothing qualified", and an accessible table view

### 🔔 Notifications
- In-app **Alerts inbox** with unread badge, keyset pagination, mark read / mark all
- Emails for welcome, sign-in security notice, target reached and price drops
- Honest delivery statuses (`sent` / `failed` / `simulated`), retries with backoff, dead-letter table
- Local **Mailpit** inbox in Docker so you can see every email without spamming real inboxes

### ✈️ Real fares & affiliate booking
- **Travelpayouts / Aviasales** provider adapter with full error mapping and rate-limit handling
- **Check price & book** button opens Aviasales with your affiliate marker (commission disclosed)
- Deterministic **demo provider** so the whole app works with zero credentials

### 🎨 Polished UI
- Next.js 16 App Router, React 19, Tailwind CSS 4, light + dark themes, reduced-motion support
- WAI-ARIA airport combobox, passengers popover, filters (sidebar on desktop / sheet on mobile)
- Skeleton loading states, optimistic controls, error states with request IDs
- Verified at 1440×900 and 390×844 with Playwright — no horizontal overflow, no console errors

---

## 🏗️ Architecture

```
                         ┌──────────────────────────────┐
   Browser  ───────────► │  web  (Next.js 16, :3000)    │
                         │  same-origin /api/* rewrite  │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐        ┌───────────────────┐
                         │  api  (FastAPI, :8000)       │──────► │  Flight providers │
                         │  auth · search · monitors    │        │  demo │ Travelpay- │
                         │  notifications · /metrics    │        │       │ outs       │
                         └───────┬───────────────┬──────┘        └─────────▲─────────┘
                                 │               │                         │
                    ┌────────────▼───┐   ┌───────▼────────┐                │
                    │ PostgreSQL 16  │   │   Redis 7      │                │
                    │ system of      │   │ cache · locks  │                │
                    │ record         │   │ broker · rate  │                │
                    └────────▲───────┘   │ limits · CB    │                │
                             │           └───────▲────────┘                │
                             │                   │                         │
                    ┌────────┴───────────────────┴────────┐                │
                    │  beat (Celery, ticks every 60 s)     │                │
                    │  worker (Celery) — refresh monitors, ├────────────────┘
                    │  evaluate rules, send emails         │──────► SMTP (Mailpit / real)
                    └──────────────────────────────────────┘
```

**Backend layering** (`backend/app/`):

| Layer | Responsibility |
|---|---|
| `api/` | HTTP routes, request/response schemas, dependencies (auth, CSRF) |
| `services/` | Use cases: search orchestration, auth, monitoring, notifications, rate limiting, resilience |
| `domain/` | **Pure logic, no I/O**: query model, offers, validation, constraints, ranking, monitoring rules |
| `providers/` | `FlightProvider` interface, registry, demo + Travelpayouts adapters, error taxonomy |
| `cache/` | Shared offer cache with single-flight locking |
| `models/` · `repositories/` | SQLAlchemy 2 models and data access |
| `workers/` | Celery app, beat schedule and tasks |
| `core/` | Settings (with production guards), DB, Redis, JSON logging, metrics, security, errors |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for flows and the scaling path.

---

## 🧰 Tech stack

| Area | Technologies |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind CSS 4, TanStack Query, React Hook Form + Zod, Radix UI, Recharts, Motion, Lucide, Sonner |
| **Backend API** | FastAPI, Pydantic 2, SQLAlchemy 2 (psycopg 3), Alembic, httpx, argon2-cffi |
| **Background jobs** | Celery 5 (worker + beat) on Redis |
| **Data** | PostgreSQL 16 (system of record), Redis 7 (cache, locks, broker, rate limits, circuit breaker) |
| **Observability** | Structured JSON logs with request-id correlation & secret redaction, Prometheus `/metrics`, health probes |
| **Tooling** | uv, Ruff, mypy (strict), pytest, ESLint, Prettier, Playwright, Docker Compose, GitHub Actions |

### Supported runtimes

| Tool | Version |
|---|---|
| Python | 3.12 (3.13 allowed) — managed by [uv](https://docs.astral.sh/uv/) |
| Node.js | 22 LTS |
| Docker Engine / Compose | 24+ / v2.24+ |
| PostgreSQL / Redis | 16 / 7 |

---

## 📁 Project structure

```
skyscout/
├── backend/                     # FastAPI API + Celery workers
│   ├── app/
│   │   ├── api/                 # routes: health, v1/auth, v1/search, v1/monitoring (+ schemas)
│   │   ├── cache/               # offer cache with single-flight locks
│   │   ├── core/                # config, db, redis, logging, metrics, security, errors
│   │   ├── domain/              # pure logic: query, offers, constraints, ranking, monitoring
│   │   ├── models/              # SQLAlchemy models
│   │   ├── providers/           # demo + Travelpayouts adapters, registry
│   │   ├── repositories/        # data access
│   │   ├── services/            # search, auth, monitoring, notifications, resilience
│   │   ├── workers/             # Celery app + tasks
│   │   └── main.py              # FastAPI app factory
│   ├── alembic/                 # database migrations
│   ├── tests/                   # unit + API tests (169 passing)
│   ├── Dockerfile
│   └── pyproject.toml / uv.lock
├── frontend/                    # Next.js web app
│   ├── src/app/                 # pages: landing, search, monitors, notifications, account, auth
│   ├── src/components/          # ui, site, search, results, monitoring
│   ├── src/lib/                 # API client, auth, formatting, query helpers
│   └── src/styles/tokens.css    # design tokens (light + dark)
├── infra/postgres/init/         # creates the isolated test database
├── scripts/                     # stack smoke tests + Playwright visual checks
├── docs/                        # PRD, architecture, plan, design, progress log
├── design-references/           # visual references for the design system
├── .github/workflows/ci.yml     # CI: backend, frontend, compose validation
├── docker-compose.yml           # full local stack
└── .env.example                 # every setting, with safe placeholders
```

---

## 🚀 Quick start (Docker)

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2) and Git.

```bash
git clone https://github.com/Priyasha1503/ASYNCHRONOUS-FLIGHT-DEAL-MICROSERVICE.git
cd ASYNCHRONOUS-FLIGHT-DEAL-MICROSERVICE

cp .env.example .env            # optional — defaults work for local dev
docker compose up -d --build    # mailpit, postgres, redis, migrate, api, worker, beat, web
```

| Service | URL |
|---|---|
| 🌐 Web app | http://localhost:3000 |
| 📚 API docs (Swagger, dev only) | http://localhost:8000/api/docs |
| ❤️ Health | http://localhost:8000/health/ready |
| 📊 Metrics | http://localhost:8000/metrics |
| 📬 Mailpit inbox | http://localhost:8025 |

Out of the box SkyScout uses the **demo provider** (synthetic, clearly labelled data) — no API keys needed.

```bash
docker compose ps                       # status
docker compose logs -f api worker beat  # follow logs
docker compose down                     # stop (data kept in named volumes)
docker compose down -v                  # stop AND wipe local data (destructive)
```

---

## 🛠️ Local development (hot reload)

Run infrastructure in Docker and the apps on your machine:

```bash
docker compose up -d postgres redis mailpit

# ── backend ──────────────────────────────────────────────
cd backend
uv sync                                  # creates .venv with Python 3.12
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run celery -A app.workers.celery_app:celery worker --loglevel=INFO --pool=solo   # --pool=solo on Windows
uv run celery -A app.workers.celery_app:celery beat --loglevel=INFO

# ── frontend (Node 22) ───────────────────────────────────
cd frontend
npm ci
npm run dev                              # http://localhost:3000
```

> **🪟 Windows note:** use `127.0.0.1`, not `localhost`, in `DATABASE_URL` / `REDIS_URL`. Docker
> Desktop publishes on IPv4 only, and `localhost` may resolve to `::1` first and stall.

<details>
<summary><b>No Node installed? Run frontend commands in a container</b></summary>

Dependencies live in a Docker volume, so Linux binaries never mix with a Windows checkout:

```bash
cd frontend
docker run --rm -v "$PWD:/app" -v skyscout_web_node_modules:/app/node_modules -w /app node:22-alpine npm ci
docker run --rm -v "$PWD:/app" -v skyscout_web_node_modules:/app/node_modules -w /app node:22-alpine npm run lint
```
</details>

### Database migrations

```bash
cd backend
uv run alembic upgrade head                                   # apply
uv run alembic current                                        # show applied revision
uv run alembic check                                          # fail if models and migrations diverge
uv run alembic revision --autogenerate -m "describe change"   # then review the file!
uv run alembic downgrade -1                                   # roll back one
```

In Docker, the one-shot `migrate` service runs `alembic upgrade head` before api/worker/beat start.

---

## ⚙️ Configuration

All settings come from environment variables — see [`.env.example`](.env.example) for the full list.

| Variable | Purpose | Default |
|---|---|---|
| `ENVIRONMENT` | `development` / `production` | `development` |
| `SECRET_KEY` | Session signing secret (generate a random one!) | placeholder |
| `DATABASE_URL` / `REDIS_URL` | Postgres / Redis connection | local `127.0.0.1` |
| `CORS_ORIGINS` | Allowed browser origins | `["http://localhost:3000"]` |
| `COOKIE_SECURE` | `true` in production (HTTPS) | `false` |
| `ENABLED_PROVIDERS` | `["demo"]` or `["travelpayouts"]` | `["demo"]` |
| `TRAVELPAYOUTS_TOKEN` / `_MARKER` | Real fares + affiliate links | empty |
| `EMAIL_BACKEND` | `console` (log only) or `smtp` | `smtp` → Mailpit in Docker |
| `MAX_ACTIVE_MONITORS_PER_USER` | Monitoring limit per user | `10` |
| `MONITOR_MIN_INTERVAL_MINUTES` | Fastest allowed check frequency | `60` |

> 🔒 In `ENVIRONMENT=production` the API **refuses to start** with the dev secret, insecure cookies,
> development DB credentials or wildcard CORS.

---

## 💸 Real fares & booking (Travelpayouts / Aviasales)

SkyScout doesn't sell tickets. With real data enabled, each fare has a **Check price & book** button
that opens Aviasales (which hands off to the airline or agency) with your affiliate marker — bookings
can earn commission, while payments and passenger data stay with them.

1. Create a [Travelpayouts](https://www.travelpayouts.com/) account, join the **Aviasales** programme,
   and copy your **API token** and **partner ID (marker)**.
2. Add them to `.env` (never commit it):
   ```env
   ENABLED_PROVIDERS=["travelpayouts"]
   TRAVELPAYOUTS_TOKEN=...
   TRAVELPAYOUTS_MARKER=...
   ```
3. `docker compose up -d`, then verify the live integration:
   ```bash
   uv run --project backend python scripts/travelpayouts_smoke.py LHR JFK 2026-12-10 2026-12-17
   ```

**What this data is:** fares *seen by Aviasales users recently* ("observed"), not live quotes — the
booking site shows the current price. Prices are for one adult in economy; connection airports and
baggage aren't provided, and SkyScout says so in the UI instead of guessing.

---

## 🔔 Price monitoring & alerts

1. Search, click **Monitor this trip**, and set a target price (prefilled 10% below the current
   cheapest qualifying fare), plus optional drop-% alert and check frequency.
2. `beat` ticks every minute; due monitored queries are claimed and refreshed by `worker`.
3. Each check stores price observations and evaluates every rule against its own requirements.
4. Alerts appear in **Alerts** (🔔 bell icon) and are emailed if enabled — **once per event**.
5. With demo data, use **Simulate a price change** on the monitor page to watch alerts fire
   (dev/demo only; disabled in production).

```bash
docker compose logs -f worker beat
docker compose exec postgres psql -U skyscout -c \
  "select trigger,status,started_at from refresh_runs order by started_at desc limit 5"
```

### 📧 Emails

| Event | Email |
|---|---|
| Register | Welcome |
| Sign in | Security notice |
| Monitored trip **first** reaches target | Target reached (changing the target re-arms it) |
| Price drop ≥ your threshold | Price-drop alert (if enabled) |

Locally every email goes to **Mailpit** at http://localhost:8025. To send to real inboxes, set SMTP
details in `.env` (Brevo, Mailgun, SendGrid, Amazon SES, or Gmail with an app password):

```env
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM=SkyScout <you@gmail.com>
APP_BASE_URL=http://localhost:3000
```

---

## 🔌 API overview

Base path: `/api/v1` · Interactive docs at `/api/docs` (development only).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/auth/csrf` | Get a CSRF token (echo it in `X-CSRF-Token`) |
| `POST` | `/auth/register` · `/auth/login` · `/auth/logout` | Account & session |
| `GET` | `/auth/session` | Anonymous-safe session probe |
| `GET` `DELETE` | `/me` | Current user / delete account |
| `PATCH` | `/me/preferences` | Update currency, home airport, email settings |
| `POST` | `/searches` | Run a flight search (anonymous allowed, rate-limited) |
| `GET` | `/airports` · `/providers` | Airport list, provider capabilities |
| `GET` `POST` | `/monitors` | List / create monitors |
| `GET` `PATCH` `DELETE` | `/monitors/{id}` | Detail with price history / update (incl. pause) / delete |
| `POST` | `/monitors/{id}/refresh` | Check now (with cooldown) |
| `GET` | `/notifications` · `/notifications/unread-count` | Alerts inbox (keyset pagination) |
| `POST` | `/notifications/{id}/read` · `/notifications/read-all` | Mark alerts as read |
| `GET` | `/health/live` · `/health/ready` · `/metrics` | Probes and Prometheus metrics (root path) |

Errors use one consistent envelope with a `request_id` for tracing. Money is always serialized as a
string to avoid floating-point surprises.

---

## 🧪 Testing & quality

Backend tests use a **separate** database (`skyscout_test`) and Redis DB 15 — the suite refuses to
run against any database whose name doesn't end in `_test`.

```bash
# backend — needs postgres + redis running
cd backend
uv run pytest                                   # 169 unit + API + migration tests
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests                           # strict mode

# frontend
cd frontend
npm run lint && npm run typecheck && npm run format:check && npm run build
```

**What's covered:** auth & CSRF, session revocation, rate limits, user isolation, migrations
(upgrade/downgrade round-trip + model/migration drift), constraints, ranking, cache hits, stampede
coalescing, Redis-down behaviour, circuit breaker, retries, deadlines, monitor idempotency under
concurrency, alert lifecycle, provider contract tests, production config guards and log redaction.

**Stack-level and browser checks** (against a running `docker compose` stack):

```bash
uv run --project backend python scripts/smoke_stack.py create /tmp/email.txt
docker compose restart && uv run --project backend python scripts/smoke_stack.py verify /tmp/email.txt

# Playwright in Docker — desktop + mobile screenshots, real UI flows, no local Node needed
mkdir -p shots && docker run --rm --ipc=host -v "$PWD/scripts:/work" -v "$PWD/shots:/out" -w /work \
  mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm i --no-save playwright@1.64.1 && node visual-smoke.mjs"
```

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push and PR:
backend (ruff, mypy, pytest with real Postgres + Redis services), frontend (prettier, eslint,
tsc, next build) and `docker compose config` validation.

---

## 🔐 Security

- Passwords hashed with **argon2id**
- Opaque 256-bit session tokens — only a **SHA-256 hash** is stored server-side
- **HttpOnly, SameSite=Lax** cookies; `Secure` enforced in production
- **Double-submit CSRF** protection on every unsafe method
- Per-IP and per-email **login rate limiting**; timing-equalised responses for unknown emails
- Strict ownership checks — other users' monitors return 404, never 403
- Secrets redacted from logs; production refuses to boot with insecure settings
- Containers run as **non-root**; services publish on `127.0.0.1` only

---

## 🗺️ Roadmap / project status

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation — auth, design system, health, infra, CI | ✅ Done |
| 2 | Flight domain + demo provider (constraints, ranking) | ✅ Done |
| 3 | Search API + UI (cache, resilience, results) | ✅ Done |
| 4 | Saved searches, monitoring, alerts, emails | ✅ Done |
| 5 | Dashboard summary & insights | ⏳ Planned |
| 6 | Real providers — Travelpayouts/Aviasales (part 1 done) | 🚧 In progress |
| 7 | Hardening — performance, JSON access logs, ops | ⏳ Planned |

Every "passed" claim is backed by commands logged in [`docs/PROGRESS.md`](docs/PROGRESS.md).

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| API/alembic hangs connecting to DB on Windows | Use `127.0.0.1` instead of `localhost` |
| `/health/ready` → `degraded` | Redis is down; auth & reads still work, caching/rate limits don't |
| `/health/ready` → 503 | Postgres is down or unreachable |
| `403 Missing or invalid CSRF token` | `GET /api/v1/auth/csrf` first and echo the cookie in `X-CSRF-Token` |
| Test DB missing | `docker compose exec postgres createdb -U skyscout skyscout_test` |
| Port already in use | Stop the other process or change the host port in `docker-compose.yml` |

---

## 📚 Documentation

| Doc | What's in it |
|---|---|
| [PRD](docs/PRD.md) | Product requirements and data-honesty rules |
| [Architecture](docs/ARCHITECTURE.md) | Processes, layers, flows, scaling path |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Phases + acceptance criteria |
| [Design brief](docs/DESIGN_BRIEF.md) · [Decisions](docs/DESIGN_DECISIONS.md) | Visual identity, tokens, trade-offs |
| [Progress log](docs/PROGRESS.md) | What's done per phase, with test evidence |
| [Release verification](docs/RELEASE_VERIFICATION.md) | Pre-release checklist |

---

## 👩‍💻 Author & contact

**Priyasha Sabbavarapu**

- 💼 LinkedIn: [linkedin.com/in/priyasha1503](https://www.linkedin.com/in/priyasha1503/)
- 📧 Email: [priyashasabbav@gmail.com](mailto:priyashasabbav@gmail.com)
- 🐙 GitHub: [@Priyasha1503](https://github.com/Priyasha1503)

If you found this project useful or interesting, a ⭐ on the repo is much appreciated!
Questions, ideas or feedback — feel free to reach out on LinkedIn or by email.
