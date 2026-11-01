# SkyScout AI — Design Decisions

Log of design decisions, newest first. Visual-identity decisions are deferred until references arrive.

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-29 | **User decision:** real-world booking = redirect to airline/OTA via affiliate links (Travelpayouts/Aviasales). In-app checkout (Duffel) not pursued now | No payments, passenger data or ticketing liability; fastest path to real use. Duffel stays the upgrade path if in-app booking is wanted later |
| 2026-10-29 | Observed fares modelled as `detail="summary"` slices with `declared_stops`; unknown flight numbers/baggage stay null | The source gives stop counts, not connections; inventing segments would misstate itineraries |
| 2026-10-29 | Travelpayouts accepted only for 1 adult / economy; other searches report "doesn't cover this search" | Prices are per adult; multiplying would be a guess presented as a fare |
| 2026-10-29 | Booking links: absolute https Aviasales URL, our `marker` replaces any other, `rel="sponsored noopener noreferrer"`, commission disclosed at the button and in the footer | Correct attribution, safe outbound link, honest disclosure |
| 2026-10-29 | API token sent as `X-Access-Token` header, never in the URL | Keeps the secret out of request logs |
| 2026-10-29 | Per-provider cache TTL; Travelpayouts 3 h (configurable) | Data is a recent sighting anyway; Travelpayouts asks partners to cache, and quotas are per minute |
| 2026-10-29 | One `MonitoredQuery` per distinct upstream query, shared by all users' rules; refreshed at the fastest active rule's frequency (floor `MONITOR_MIN_INTERVAL_MINUTES`, default 60) | Provider calls scale with distinct routes, not users |
| 2026-10-29 | Idempotency via unique constraints (run per slot, observation per fingerprint+slot, rule check per run, notification per dedup key) + `ON CONFLICT DO NOTHING` | Duplicate/retried/concurrent tasks are harmless by construction, proven by tests |
| 2026-10-29 | Below-target dedup key = target + 1%-of-target price band | Jitter doesn't re-alert; a meaningful further drop or a changed target does |
| 2026-10-29 | Each rule evaluated in its own transaction (check row + notifications + state) | No half-evaluated rule after a crash; re-evaluation is a no-op |
| 2026-10-29 | A failed refresh (no provider data) does not count as a check | "Last checked" must mean "we actually saw prices" |
| 2026-10-29 | Demo prices are only changed by an explicit, labelled *Simulate price change* tool (non-production, demo provider only) | Deterministic demo data would never move; inventing drift would be fabricating history. **Caveat:** the factor applies to the shared demo query, so on one dev instance every user searching that route/dates sees the simulated demo prices (7-day TTL) |
| 2026-10-29 | Email delivery statuses `queued / sent / failed / simulated`; console backend records `simulated`, never `sent` | Master prompt: never claim delivery that didn't happen |
| 2026-10-29 | "Recent checks" shows only runs since the user's monitor was created | Runs belong to the shared query; earlier runs would confuse and hint at other users' activity |
| 2026-10-29 | Chart colours validated with the dataviz validator; dark-mode chart steps `#8a64e6` / `#e5673f` | The light-mode tones failed the dark-surface lightness band |
| 2026-10-29 | Results filters are *hard constraints* that re-run the search (served from cache), not client-side hiding | One rule set (backend) for what "qualifies"; recommendations stay consistent with filters |
| 2026-10-29 | URL is the source of truth for search, filters and sort; controls use `useOptimistic` | Shareable/bookmarkable searches; instant control feedback without diverging from the URL |
| 2026-10-29 | Relaxation buttons show the count *that exact change* adds; "remove limit" offered separately | Showing the remove-limit count on a "raise to X" button overstated the effect |
| 2026-10-29 | Times shown in each airport's local time with a "+1" day marker; never converted to viewer tz | Matches tickets and boarding passes |
| 2026-10-29 | Search allowed anonymously; saving/monitoring require an account | Low-friction first use; persistence needs ownership |
| 2026-10-29 | Demo provider uses **fictional airlines** + real airports | Fake fares under real airline names could be mistaken for real prices; real airports keep itineraries realistic |
| 2026-10-29 | Upstream query (route/dates/pax/cabin/currency) is separate from user preferences | One cached provider result serves every user with the same upstream params; preferences applied after retrieval |
| 2026-10-29 | Unconfirmed baggage scores 0 in ranking and fails a "bag required" constraint as `bag_unconfirmed` | Master prompt: never rank using unverified data; distinct code lets UI say "not confirmed" vs "not included" |
| 2026-10-29 | Default weights price .45 / duration .20 / stops .15 / baggage .10 / airline .05 / schedule .05, renormalized over active factors | Price dominates but trade-offs matter; optional factors don't dilute scores when unused |
| 2026-10-29 | Alternatives shown only if strictly better on their axis than *both* headline picks | Avoids "alternatives" that aren't real trade-offs |
| 2026-10-29 | Sync provider interface (`search()` blocks) | Matches the sync stack; Phase 3 fans out providers on a bounded thread pool |
| 2026-10-23 | Visual identity v1 from `design-references/` (twilight violet + coral); see DESIGN_BRIEF | References are the source of truth (Addendum §A) |
| 2026-10-23 | Hero sky drawn in CSS + original SVG aircraft; reference images not shipped | ref2/3 are watermarked/unknown-licence stock; CSS avoids payload and layout shift |
| 2026-10-23 | Fraunces (display) + Inter (UI, tabular numerals) | Warm dusk mood for headings; Inter's tabular figures keep prices aligned |
| 2026-10-23 | Coral reserved for one accent role; magenta only in charts/sky | Mirrors the references' cool-dominant / warm-highlight ratio; avoids a garish UI |
| 2026-10-23 | Landing shows no search form until Phase 3 | Addendum §F: no decorative controls that imply unsupported functionality |
| 2026-10-23 | Tailwind v4 `@theme inline` maps CSS variables → utilities; dark mode via `prefers-color-scheme` + `data-theme` override | One token source; theming without duplicate class names |
| 2026-10-23 | Sync SQLAlchemy + psycopg 3 everywhere (API, workers, scripts) | One data-access style; FastAPI runs sync deps in a threadpool; revisit if API I/O-bound under load tests |
| 2026-10-23 | CSRF double-submit applies to login/register too | Prevents login-CSRF; frontend fetches a token from `GET /auth/csrf` |
| 2026-10-23 | Auth rate limiter fails **open** on Redis outage (logged) | Sessions live in Postgres; a cache outage must not lock users out. Revisit in Phase 7 review |
| 2026-10-18 | **Provider plan approved by user:** demo provider (dev/tests) → Travelpayouts/Aviasales Data API (launch; `observed` fares, affiliate redirect) → Duffel (live quotes, test mode first) → Aviasales Search API / Skyscanner when traffic qualifies | Amadeus Self-Service closed Jul 2026; Kiwi invite-only; Duffel's search-to-book fees punish monitoring-heavy usage; affiliate model avoids handling payments |
| 2026-10-18 | Defer palette/typography until user references are inspected | Addendum §A: references are the source of truth; don't invent preferences |
| 2026-10-18 | Tokens live in `frontend/src/styles/tokens.css` as CSS variables, mapped into Tailwind theme | Single source for all screens; swappable once references land |
| 2026-10-18 | Fare source shown as icon + text badge | Addendum §B: never communicate status by colour alone |
