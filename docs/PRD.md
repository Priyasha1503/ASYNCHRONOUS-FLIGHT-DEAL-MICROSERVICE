# SkyScout AI — Product Requirements

## 1. Problem
Fares move constantly, and comparing offers against a budget plus personal constraints (stops, bags,
times, airlines) is tedious. Existing tools either show a wall of equal-looking results or send
noisy, unexplained alerts. SkyScout AI finds the cheapest flight that *actually meets your
requirements*, explains its recommendations, and watches the route for you.

## 2. Target users
- **Budget-bound leisure traveller** — fixed dates, hard budget ceiling, wants to know when to buy.
- **Flexible explorer** — dates ±3 days, open to nearby airports, wants the best trade-off.
- **Frequent route watcher** — monitors the same few routes, cares about alert quality not volume.

## 3. Core journey
1. Enter origin, destination, dates, passengers, cabin, currency, budget.
2. Add preferences: max stops, preferred/excluded airlines, departure/arrival windows, max duration,
   checked bag required, flexible dates, nearby airports.
3. SkyScout queries enabled providers (shared cache first), normalizes, dedupes, filters hard
   constraints, ranks soft preferences.
4. Results show: **cheapest qualifying**, **best overall match**, **notable alternatives**, then the
   ranked list — each with a "why" explanation and data-freshness label.
5. User saves the search, sets a target price → becomes a monitored trip.
6. Scheduler refreshes monitored searches (shared across users with identical upstream params),
   stores observations, evaluates rules.
7. Alerts (in-app + email) fire once per qualifying event, deduplicated.

## 4. Data honesty rules (non-negotiable)
Every price shown carries a **source label**:

| Label | Meaning |
|---|---|
| `live` | Returned by a provider's real-time search in this request |
| `cached` | Live result reused from shared cache; shows age |
| `observed` | Provider-reported recently-seen fare (e.g. Aviasales Data API); not a bookable quote |
| `historical` | Stored SkyScout observation, used only in charts/history |
| `demo` | Deterministic mock provider; never shown without a "Demo data" banner |

No fabricated prices, history, availability, testimonials, statistics or bookings. A search price is
never presented as a guaranteed checkout price.

## 5. Functional requirements
- **Search**: one-way/round-trip; adults/children/infants; cabin; currency; budget ceiling; max stops;
  airline include/exclude; time windows; max duration; checked bag; flexible dates (±N days, bounded);
  nearby airports (bounded list). Validated client- and server-side.
- **Results**: airline, flight numbers, airports, local times + tz, duration, stops & layovers,
  cabin/fare brand, baggage (only if confirmed, else "unknown"), total price + currency, provider,
  freshness, booking/redirect link if available. Sort + filter client-side over the result set.
- **Recommendations**: hard filters first; explainable weighted score; when nothing qualifies, list
  which constraint eliminated how many offers and offer one-click relaxations.
- **Saved trips & monitoring**: create/edit/pause/delete; target price; drop-threshold (% or amount);
  frequency tier (bounded by config); per-user active-rule limit.
- **Notifications**: below-target, meaningful drop, qualifying offer appears, monitored offer changed
  beyond threshold. In-app + email; preferences; delivery attempts with status; dedup.
- **Dashboard**: saved trips, active rules, recent changes, history charts (observations only, gaps
  shown), target progress, last refresh, provider health, recent notifications, stats from DB.
- **Auth**: email + password, server-side sessions in HttpOnly cookies, CSRF protection, logout,
  profile, preferences, account deletion.

## 6. Non-functional
- 100–1,000 active users initially; documented path to 10,000. Claims only from measured load tests.
- p95 search latency: cached < 300 ms server-side; uncached bounded by provider timeout (default 12 s).
- WCAG 2.2 AA contrast and keyboard access; reduced-motion respected.
- All timestamps stored UTC; money as `NUMERIC(12,2)` + ISO-4217 currency.

## 7. Out of scope (v1)
In-app ticket purchase/payment (we redirect to the provider), multi-city itineraries, loyalty-point
pricing, guaranteed price predictions.

## 8. Success metrics (instrumented, not claimed)
Search success rate, cache hit rate, alert precision (user "useful?" feedback), monitored-trip
retention, provider error rate.
