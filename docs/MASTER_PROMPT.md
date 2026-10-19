# SKYSCOUT AI — MASTER BUILD PROMPT
## Build a Premium, Scalable, Production-Quality Flight Price Intelligence Platform

Act as a **principal software architect, senior full-stack engineer, AI engineer, database architect, UI/UX designer, DevOps engineer, and QA engineer** working together.

Your task is to design and build **SkyScout AI**, a polished, scalable, intelligent flight-price monitoring platform that helps users discover competitive fares, compare flights against their budgets and preferences, track prices over time, and receive timely alerts when fares meet their goals.

Do not merely generate a prototype, landing page, or collection of disconnected components. Build a coherent, functional application with a maintainable architecture, persistent storage, reliable background processing, a beautiful interface, comprehensive tests, and clear deployment instructions.

Work directly in the current repository.

---

# 1. START BY UNDERSTANDING THE PROJECT

Before writing code:

1. Inspect the existing repository, its files, dependencies, Git status, and current implementation.
2. Identify existing functionality worth preserving. Do not blindly overwrite files or replace working implementations.
3. Inspect all available design references in the repository, especially a `design-references/` directory, and any images or URLs I provide.
4. If browser access is available, inspect accessible reference websites and analyze their visual design. Never claim to have inspected a reference that you could not access.
5. Identify missing requirements, technical risks, dependencies, and implementation constraints.
6. Create these documents:
   - `docs/PRD.md` — product requirements and user journeys.
   - `docs/ARCHITECTURE.md` — system design, component boundaries, data flows, and scaling strategy.
   - `docs/IMPLEMENTATION_PLAN.md` — phased implementation plan with acceptance criteria.
   - `docs/DESIGN_BRIEF.md` — visual references and design principles.
   - `docs/DESIGN_DECISIONS.md` — design decisions and rationale.

Present a concise implementation plan, then begin implementation without waiting for approval unless an essential decision or genuine blocker requires my input.

Do not stop after producing documentation or scaffolding. Continue building the actual application.

# 2. PRODUCT VISION

SkyScout AI is a flight-price intelligence application, not merely a flight search form.

The central user journey is:

1. A user enters an origin, destination, travel dates, passenger configuration, cabin class, and budget.
2. The user specifies preferences such as airlines, maximum stops, baggage requirements, departure times, trip duration, and flexibility.
3. SkyScout searches available flight providers through approved integrations.
4. The platform normalizes, deduplicates, filters, and ranks available offers.
5. The user sees the cheapest qualifying flight, the best overall match, and other relevant alternatives.
6. The user saves a search or trip and optionally configures a target price.
7. Background jobs refresh monitored searches according to provider limits, cache freshness, and monitoring rules.
8. The application records fare observations and detects meaningful price changes.
9. The user receives notifications when configured conditions are met.

The product must clearly distinguish between live provider results, cached results, historical observations, and mock/demo data.

Never fabricate live prices, historical records, availability, or successful bookings.

# 3. REQUIRED TECHNOLOGY STACK

Use a modular monolith architecture with independently runnable application processes. Avoid premature microservices.

## Frontend

- Next.js with App Router.
- React and TypeScript with strict type checking.
- Tailwind CSS.
- shadcn/ui where appropriate.
- TanStack Query for server-state management.
- React Hook Form and Zod for forms and validation.
- Recharts for price-history charts and analytics.
- Accessible icon library such as Lucide.
- Server-Sent Events (SSE) or another justified mechanism for useful live status updates, where appropriate.

## Backend

- Python with FastAPI.
- Pydantic for request, response, and configuration validation.
- SQLAlchemy 2.x.
- Alembic database migrations.
- Clearly separated API, service, repository, provider, domain, and worker layers.

## Infrastructure

- PostgreSQL as the durable system of record.
- Redis for caching, coordination, rate limiting where appropriate, and queue infrastructure.
- Celery workers for asynchronous tasks.
- Celery Beat or an equivalent scheduler for recurring work.
- Docker and Docker Compose for local development.
- GitHub Actions for continuous integration.
- Structured application logs, health checks, metrics, and error reporting.

Pin or constrain compatible dependency versions and document the supported runtime versions.

Use separate processes or services for the frontend, backend API, background workers, and scheduler. They may share the same codebase.

# 4. VISUAL DESIGN — MAKE THIS EXCEPTIONAL

The UI must feel like a carefully designed premium travel-tech product that could credibly compete with polished commercial applications.

**Visual quality is a core product requirement, not a final styling task.**

## Design reference workflow

Use the reference images, screenshots, and websites I provide as the primary visual direction.

Study:

- Color palette and contrast.
- Typography and hierarchy.
- Spacing, alignment, and density.
- Navigation and information architecture.
- Cards, tables, borders, shadows, and corner radii.
- Image treatment and iconography.
- Interaction patterns, animation, and transitions.
- Desktop and mobile layouts.
- Chart styling and data visualization.

Combine compatible inspirations into one coherent design system. Do not copy unrelated styles into disconnected pages.

If references are unavailable, create an original, distinctive travel-tech visual identity. Avoid default-looking AI dashboards, generic gradients, excessive glassmorphism, unnecessary decoration, and repetitive card layouts unless the references justify them.

## Design system

Create reusable design tokens for:

- Brand and semantic colors.
- Background and surface colors.
- Text and border colors.
- Typography scale.
- Spacing scale.
- Radius and shadow.
- Animation timing and easing.
- Breakpoints and responsive behavior.

Centralize tokens using CSS variables and the Tailwind theme.

Use consistent, reusable components. Every page must belong to the same design system.

## Visual quality requirements

Implement:

- A polished, responsive navigation system.
- Thoughtful page transitions and restrained micro-interactions.
- Clear visual hierarchy.
- Elegant forms with helpful validation.
- Skeleton loaders rather than abrupt content jumps.
- Purposeful empty states and error states.
- Accessible contrast and keyboard navigation.
- Reduced-motion support.
- Responsive charts and tables.
- Mobile-friendly filters, dialogs, and navigation.
- Toasts and inline feedback for user actions.

Do not leave placeholder layouts, broken images, dead buttons, overflowing tables, or inconsistent styling.

## Browser verification

When browser automation or a local browser is available:

1. Run the actual application.
2. Inspect the rendered landing page, search experience, results, dashboard, monitoring center, and settings.
3. Test desktop and mobile viewports.
4. Compare the implementation with the supplied references.
5. Fix spacing, typography, responsiveness, alignment, contrast, and interaction problems.
6. Repeat until the actual rendered application meets the intended quality.

Use Playwright for browser verification and visual regression where practical.

If browser automation is unavailable, document what could not be visually verified rather than claiming successful verification.

# 5. APPLICATION PAGES AND FEATURES

Build the following experiences with real data flows and functional interactions.

## A. Landing page

Create a compelling landing page that communicates the product's value immediately.

Include:

- Clear product positioning.
- Prominent flight-search interface.
- Origin and destination selection.
- One-way and round-trip options.
- Departure and return dates.
- Passenger count and cabin class.
- Budget and preference controls.
- A preview of price intelligence.
- Explanation of monitoring and alert capabilities.
- Credible feature sections.
- Responsive navigation and footer.

Use only truthful product claims. Do not invent customer testimonials, statistics, or performance guarantees.

## B. Flight search

Support:

- Origin and destination.
- One-way and round-trip itineraries.
- Departure and return dates.
- Adult and other supported passenger configurations.
- Cabin class.
- Currency selection.
- Budget constraints.
- Maximum stops.
- Preferred or excluded airlines where supported.
- Departure and arrival time preferences.
- Maximum journey duration.
- Baggage requirements when provider data supports them.
- Flexible dates and nearby airports where supported.
- Sorting and filtering.

Validate all inputs on both frontend and backend.

Preserve search parameters when navigating between results, saved searches, and relevant detail views.

## C. Results and recommendations

Display normalized flight results with:

- Airline and flight details when available.
- Origin and destination airports.
- Departure and arrival times, including time zones where relevant.
- Journey duration.
- Stops and layover details.
- Cabin and fare information.
- Baggage inclusions when confirmed.
- Total displayed price and currency.
- Provider and source.
- Offer freshness or last-checked time.
- A link to the appropriate provider checkout or booking page when available.

Provide distinct recommendation categories:

1. **Cheapest qualifying flight** — the lowest-priced offer satisfying all hard constraints.
2. **Best overall match** — the offer with the strongest overall preference score.
3. **Best alternatives** — other relevant trade-offs such as shorter journeys or fewer stops.

Explain why an offer is recommended.

If no flights satisfy all hard constraints, explain the limiting conditions and allow users to relax selected filters. Never silently disregard a user's budget or essential requirements.

Clearly communicate when results are cached, stale, incomplete, or sourced from mock data.

## D. Price intelligence dashboard

Build an analytics dashboard with:

- Saved trips and searches.
- Active monitoring rules.
- Recent price changes.
- Historical price charts where actual observations exist.
- Target-price progress.
- Last successful refresh.
- Provider health and data freshness.
- Recent notifications.
- Summary statistics calculated from real stored data.

Historical charts must distinguish actual observations from missing data. Do not invent historical trends.

Any price prediction feature must be optional and supported by a documented methodology and adequate data. If reliable prediction is unavailable, provide descriptive historical analysis instead. Never present speculative predictions as guaranteed savings.

## E. Monitoring center

Users should be able to:

- Create a monitored search.
- Set a target price and optional conditions.
- Enable or pause monitoring.
- Edit or delete a monitoring rule.
- Select monitoring and notification preferences.
- View recent refresh attempts and outcomes.
- Inspect recent price changes.
- Understand when a price was last verified.
- Manage multiple trips independently.

Enforce sensible limits on active monitoring rules and refresh frequency. Make limits configurable rather than hardcoded throughout the application.

## F. Notifications

Support in-app notifications and an email notification interface.

Trigger alerts for configured conditions such as:

- Price falling below a target.
- A meaningful price decrease.
- A qualifying offer becoming available.
- A monitored offer changing beyond a configured threshold.

Implement notification preferences, delivery status, retries, and deduplication.

Use a development email backend or console output until an actual email provider is configured. Document the environment variables required for production delivery.

Never claim an email was delivered when it was merely queued.

## G. Authentication and user settings

Implement a secure authentication approach appropriate to the application, including:

- Registration and sign-in.
- Password hashing if using passwords.
- Session management.
- Logout.
- User profile and preferences.
- Notification settings.
- User-specific saved searches and monitoring rules.

Use secure cookie/session practices or a properly implemented token strategy. Do not store sensitive session credentials in browser local storage without a compelling, documented reason.

Enforce authorization on the backend for every user-owned resource. Hiding a frontend control is not authorization.

# 6. FLIGHT PROVIDER INTEGRATION

Create a provider abstraction that supports multiple data sources without coupling business logic to any single provider.

Define a consistent interface for:

- Searching flights.
- Retrieving supported offer details.
- Normalizing results.
- Handling provider errors.
- Exposing rate limits and relevant capabilities.
- Recording request metadata and freshness.

Start with a deterministic mock provider so the application can be developed and tested without API credentials.

The mock provider must use reproducible fixtures and visibly identify itself as demo data.

Then implement a real provider adapter using an officially supported flight API or a permitted affiliate integration. Evaluate providers such as Duffel or other suitable providers based on access, coverage, commercial terms, and current documentation.

Do not assume that a provider offers unrestricted access or that its search endpoint guarantees ticket availability or final checkout pricing.

Requirements:

- Load credentials from environment variables or a secret manager.
- Never commit API keys.
- Follow provider documentation, contractual restrictions, rate limits, and attribution requirements.
- Normalize provider-specific responses into a common domain model.
- Handle partial provider failures without failing the entire search.
- Validate currency, timestamps, fare totals, and itinerary fields.
- Preserve source attribution and relevant provider offer identifiers.
- Record provider response time, errors, and rate-limit events.
- Provide a clear configuration path for adding another provider.

Use browser automation only when explicitly permitted by the relevant source. Do not bypass CAPTCHAs, access controls, authentication restrictions, or anti-bot protections.

Do not implement uncontrolled scraping.

# 7. SCALABLE SEARCH, CACHING, AND RATE LIMITING

Design the platform for an initial target of approximately 100–1,000 active users, with a credible path toward 10,000 active users, subject to actual workload, provider limits, and available infrastructure.

Do not claim that the system supports a particular load until it has been tested.

## Shared caching

Use Redis to cache compatible search results across users.

Build deterministic cache keys from all parameters that materially affect upstream results, including:

- Origin and destination.
- Travel dates and trip type.
- Passenger configuration.
- Cabin class.
- Currency where relevant.
- Other upstream-relevant search parameters.

Normalize equivalent inputs before generating keys.

Use cache-aside behavior, configurable TTLs, bounded memory usage, and explicit cache invalidation rules.

Prevent cache stampedes using safe locks or single-flight request coalescing. Handle lock expiry, worker crashes, and failed refreshes correctly.

Do not create one independent upstream search per user when multiple users request equivalent data.

Do not poll providers every two to five seconds by default. Refresh frequency must reflect provider quotas, user-selected monitoring policies, fare freshness, and actual product needs.

## Background processing

Use Celery and Redis for work that should not block API responses.

Implement:

- Scheduled monitoring.
- Search refresh tasks.
- Price observation persistence.
- Price-change evaluation.
- Notification dispatch.
- Retryable provider requests.
- Job status tracking.
- Dead-letter or equivalent handling for exhausted tasks.
- Idempotent job execution.
- Bounded concurrency and provider-specific throttling.

Ensure duplicate jobs do not create duplicate price observations or repeated alerts.

Use appropriate scheduling strategies and avoid a separate periodic polling loop for every user if a shared monitoring schedule can serve compatible searches.

## Reliability

Implement:

- Connection and request timeouts.
- Exponential backoff with jitter.
- Circuit breakers or equivalent provider failure isolation.
- Controlled retries for transient errors.
- No retries for permanent validation errors.
- Queue monitoring and stale-job detection.
- Graceful degradation when a provider is unavailable.
- Explicit handling of Redis and database outages.

Never allow retries to create unbounded work.

# 8. POSTGRESQL DATA MODEL AND PERSISTENCE

PostgreSQL is the authoritative source of durable application data. Redis must not be the only place where important user or historical data exists.

Design normalized, maintainable models for at least:

- Users and authentication/session records as appropriate.
- User preferences.
- Saved searches and trips.
- Monitoring rules.
- Provider configurations and execution metadata.
- Normalized flight offers and itinerary details as appropriate.
- Price observations and historical records.
- Notifications.
- Notification delivery attempts.
- Background job metadata where required.
- Audit or operational events where justified.

Use appropriate foreign keys, unique constraints, indexes, and transactional boundaries.

Requirements:

- Use Alembic for all schema changes.
- Store monetary values with appropriate decimal precision and explicit currencies.
- Store timestamps consistently in UTC.
- Enforce ownership and data isolation.
- Prevent duplicate observations and notifications with database constraints and idempotency keys where appropriate.
- Design efficient pagination and filtering.
- Avoid N+1 queries and unnecessary database round trips.
- Define retention and cleanup policies for old observations and operational records.
- Use connection pooling and configurable database settings.
- Include seed/demo data for development, clearly marked as such.
- Document backup, restore, and migration procedures.

Persist user preferences, monitoring configurations, notification history, and price observations across restarts.

Test persistence by restarting the application and confirming that stored records remain available.

Do not use in-memory dictionaries or browser local storage as substitutes for the real database.

# 9. BACKEND API AND DOMAIN DESIGN

Use versioned API routes, such as `/api/v1/`.

Organize code by clear responsibilities rather than putting all business logic in route handlers.

Implement documented endpoints for:

- Authentication and profile.
- Flight search.
- Flight offer details where supported.
- Saved searches and trips.
- Monitoring rules.
- Price history.
- Notifications and notification preferences.
- Provider status and relevant operational health.
- User settings.

For each endpoint:

- Define request and response schemas.
- Validate input.
- Enforce authentication and authorization.
- Return consistent error responses.
- Use appropriate HTTP status codes.
- Implement pagination where needed.
- Document the contract using OpenAPI.
- Avoid leaking credentials, internal exceptions, or sensitive data.

Keep domain services independent of FastAPI where practical so they can be tested directly.

Use database transactions for operations that must remain consistent.

# 10. AI-POWERED INTELLIGENCE

AI should provide meaningful value rather than being added as decoration.

Implement deterministic, testable recommendation logic first.

Separate:

**Hard constraints:** route, dates, passenger requirements, cabin class, budget ceiling, and other explicitly mandatory criteria.

**Soft preferences:** price, duration, stop count, preferred airlines, departure times, baggage convenience, and fare flexibility.

Create a configurable ranking function that:

- Filters hard constraints before ranking.
- Normalizes comparable scoring factors.
- Handles missing attributes safely.
- Makes weights configurable.
- Produces an explainable score or ranked rationale.
- Avoids ranking offers using unverified data.
- Distinguishes price from overall suitability.

Add tests for ranking behavior and edge cases.

If an LLM-based assistant is introduced, use it for interpreting natural-language preferences or explaining structured recommendations, not as the source of truth for prices, availability, or flight facts.

Keep provider data and user input untrusted. Do not allow either to override system instructions or trigger arbitrary tool execution.

Make any external AI integration optional, configurable, and safe when credentials are unavailable.

# 11. SECURITY AND PRIVACY

Implement security throughout the system.

Include:

- Input validation and output encoding.
- Password hashing using an established secure algorithm.
- Authentication and resource-level authorization.
- Cross-user data isolation.
- Rate limiting on sensitive and expensive endpoints.
- CORS configured for intended origins.
- Secure cookies and session protections where applicable.
- CSRF protection when relevant to the chosen authentication model.
- Protection against SQL injection and unsafe query construction.
- Protection against SSRF if URLs can be supplied to server-side fetches.
- Safe error messages and structured logging.
- Secret management through environment variables or a secret manager.
- Dependency and container security checks.
- Appropriate handling of personal data.
- Data deletion and retention behavior where applicable.

Never log passwords, authentication tokens, API secrets, or unnecessary personal information.

Provide `.env.example` with placeholders only. Do not create fake credentials that could be mistaken for real ones.

Include appropriate development-versus-production configuration checks.

# 12. OBSERVABILITY AND OPERATIONS

Implement useful operational visibility, including:

- Liveness and readiness endpoints.
- Structured JSON logs.
- Request IDs or trace correlation.
- Request latency and error metrics.
- Provider latency and error metrics.
- Cache hit/miss metrics.
- Queue depth and task failure metrics.
- Monitoring refresh success and failure rates.
- Notification delivery outcomes.
- Database connection and health checks.

Provide a lightweight operational dashboard or documented metrics endpoints where appropriate.

Distinguish between an application health check and proof that every external provider is healthy.

Document common failure modes and troubleshooting procedures.

# 13. TESTING — REQUIRED, NOT OPTIONAL

Write tests as the implementation progresses.

## Unit tests

Cover:

- Input validation.
- Hard-constraint filtering.
- Recommendation ranking.
- Currency and price handling.
- Cache key normalization.
- Cache expiration behavior.
- Provider response normalization.
- Price-change detection.
- Notification thresholds and deduplication.
- Idempotency behavior.
- Authorization rules.

## Integration tests

Test:

- PostgreSQL persistence and migrations.
- Redis cache behavior.
- Queue submission and worker execution.
- Provider adapters using fixtures or mocks.
- Monitoring rule lifecycle.
- Price observation persistence.
- Notification creation and delivery handling.
- Failure recovery and retries.

Use isolated test resources or disposable test containers where practical. Do not accidentally modify production or personal data.

## API tests

Cover:

- Valid and invalid requests.
- Authentication and authorization.
- Missing or malformed parameters.
- Pagination and filtering.
- Consistent error responses.
- Cross-user access attempts.
- Rate limiting where implemented.

## End-to-end tests

Use Playwright to exercise critical user journeys:

1. Open the application.
2. Search for flights using demo data.
3. Apply filters and inspect recommendations.
4. Save a search.
5. Create a monitoring rule.
6. Configure a target price.
7. Trigger a simulated price change.
8. Verify notification creation.
9. Restart relevant services and verify durable data remains.
10. Verify that a different user cannot access the first user's private resources.

## Failure and resilience tests

Test:

- Provider timeouts.
- Provider rate limits.
- Partial provider outages.
- Invalid provider responses.
- Redis cache misses and expiration.
- Redis restarts.
- Worker restarts.
- Duplicate task execution.
- Database connection failures.
- Notification delivery failures.
- Stale data and incomplete results.

## Performance tests

Create repeatable load-test scenarios for representative search, read, write, and monitoring workloads.

Report actual:

- Throughput.
- p50, p95, and p99 latency.
- Error rate.
- Cache hit rate.
- Queue wait time and backlog.
- Resource utilization.
- Database behavior under load.

State the test environment, test duration, concurrency, workload assumptions, and known limitations.

Never fabricate test results or claim that a test passed without executing it.

# 14. DEVELOPER EXPERIENCE AND DEPLOYMENT

Provide:

- Clean repository organization.
- Clear naming and type annotations.
- Linting and formatting.
- Frontend type checking.
- Backend static checks where appropriate.
- Dependency management and lockfiles.
- Dockerfiles and Docker Compose configuration.
- Database migrations.
- Environment configuration.
- Seed data and deterministic mock-provider fixtures.
- CI workflows.
- Test commands.
- A comprehensive root `README.md`.

A developer should be able to clone the repository, configure the environment, start the application, migrate the database, run tests, and understand the architecture by following the documentation.

Include practical commands for:

- Starting and stopping services.
- Applying and checking migrations.
- Running backend and frontend tests.
- Running linting and type checking.
- Running end-to-end tests.
- Inspecting worker and scheduler logs.
- Resetting local demo data safely.

Provide a deployment guide for a realistic initial production setup, including TLS, secrets, persistent storage, database backups, monitoring, migrations, and rollback considerations.

Do not claim production deployment has occurred unless it actually has.

# 15. IMPLEMENTATION STRATEGY

Build the application in deliberate, verifiable phases.

## Phase 1 — Foundation

- Inspect the repository.
- Finalize architecture and requirements.
- Set up frontend and backend.
- Configure PostgreSQL, Redis, Docker Compose, and environment variables.
- Establish migrations and basic health checks.
- Implement authentication foundations.
- Create the design system and shared frontend components.

**Acceptance criteria:** The services start correctly, database migrations work, and the initial interface renders.

## Phase 2 — Flight domain and mock provider

- Define domain models and provider interfaces.
- Implement deterministic mock data.
- Build normalization and filtering.
- Implement recommendation ranking.
- Add unit and integration tests.

**Acceptance criteria:** Flight search works end to end with clearly labeled demo data.

## Phase 3 — Search API and frontend

- Implement search endpoints.
- Integrate shared caching.
- Build the search interface and results page.
- Add sorting, filtering, loading states, and error handling.
- Implement recommendation explanations.

**Acceptance criteria:** Users can search, compare, filter, and inspect results through the actual UI.

## Phase 4 — Persistence and monitoring

- Implement saved searches and trips.
- Add monitoring rules and scheduling.
- Record price observations.
- Implement target-price evaluation.
- Add notification records and deduplication.
- Test restart persistence and background processing.

**Acceptance criteria:** Users can save a search, monitor it, and observe persisted price changes.

## Phase 5 — Price intelligence and dashboard

- Build the dashboard and monitoring center.
- Add historical charts based on stored observations.
- Add meaningful summary statistics.
- Display freshness, provider health, and notification status.

**Acceptance criteria:** Dashboard information is derived from real persisted records and accurately represents data availability.

## Phase 6 — Real provider integration

- Review official provider documentation.
- Implement a permitted real provider adapter.
- Configure credentials through environment variables.
- Add contract tests and failure handling.
- Preserve the working mock provider for development and testing.

**Acceptance criteria:** Real integration works when valid credentials and provider access are available. Otherwise, document the exact blocker and keep the mock workflow functional.

## Phase 7 — Hardening and visual refinement

- Review security and authorization.
- Optimize database access and caching.
- Verify retries, queue behavior, and idempotency.
- Improve responsive layouts and accessibility.
- Run automated browser tests.
- Run performance tests.
- Fix high-priority defects.

**Acceptance criteria:** The documented test suite runs, failures are addressed or disclosed, and the application is ready for an informed deployment decision.

Do not skip a phase's acceptance criteria simply to move faster.

# 16. ENGINEERING RULES

Follow these rules throughout implementation:

1. Build functional features, not static mockups disguised as working software.
2. Keep modules cohesive and interfaces explicit.
3. Prefer the simplest architecture that satisfies current requirements and credible future growth.
4. Avoid duplicated business logic across frontend, API, and workers.
5. Validate important invariants in the backend and database.
6. Never trust frontend validation alone.
7. Never fabricate provider data, historical prices, test results, or deployment status.
8. Avoid hardcoded secrets, production credentials, and environment-specific assumptions.
9. Do not silently swallow exceptions.
10. Use retries only where safe and appropriate.
11. Keep external API calls out of long-running database transactions.
12. Avoid unnecessary dependencies and overengineering.
13. Add tests for every important business rule.
14. Document significant design trade-offs.
15. Preserve a working application as features are added.
16. Do not leave core buttons, forms, or navigation elements nonfunctional.
17. Use feature flags or configuration for optional integrations when appropriate.
18. Keep local development possible without paid third-party API access.
19. Do not claim scalability based on architecture alone; measure it.
20. Do not stop after generating code. Run it, test it, inspect it, and fix defects.

# 17. WORKING WITH THE CODING AGENT

Operate as an autonomous engineering agent with explicit checkpoints.

At the start of each phase:

- Review the relevant implementation plan.
- Identify dependencies and acceptance criteria.
- Inspect existing code before changing it.
- Make a focused implementation plan.

During each phase:

- Implement working code.
- Run relevant tests and checks.
- Inspect failures and fix root causes.
- Update documentation and configuration examples.
- Keep changes focused and maintainable.

At the end of each phase, summarize:

- What was implemented.
- Important files created or changed.
- Architectural decisions.
- Tests actually executed and their results.
- Known defects and incomplete work.
- Exact commands to run the application and tests.
- What remains before the next acceptance gate.

Then continue to the next phase unless a genuine blocker requires input.

If a command fails, investigate the cause instead of repeatedly executing it without changes.

If a required API key or service is unavailable, implement and test the permitted fallback and document the integration steps. Do not fabricate a successful connection.

If the repository is too large to safely modify at once, work incrementally and preserve functioning features.

# 18. FINAL RELEASE VERIFICATION GATE

Before declaring SkyScout AI complete, perform a final, evidence-based verification process.

1. Start the application using the documented configuration.
2. Apply migrations to a clean PostgreSQL database.
3. Verify that durable records survive application and service restarts.
4. Verify Redis cache hits, misses, expiration, and recovery after restart.
5. Run all available unit, integration, API, and end-to-end tests.
6. Run frontend linting, TypeScript checks, and a production build.
7. Test authentication, authorization, and cross-user data isolation.
8. Test provider timeouts, partial failures, retries, and rate limits.
9. Verify job idempotency and duplicate-alert prevention.
10. Run representative load tests and record actual results.
11. Verify that secrets are not committed and production configuration does not rely on development defaults.
12. Check that database backups and restoration procedures are documented.
13. Inspect the UI at desktop and mobile sizes and fix major visual defects.
14. Document all failures, unresolved issues, and checks that could not be run.

Create `docs/RELEASE_VERIFICATION.md` containing:

- Environment and commands used.
- Tests executed and their actual outcomes.
- Database persistence checks.
- Cache and worker recovery checks.
- Security and authorization checks.
- Load-test methodology and measured results.
- Visual verification status.
- Known limitations.
- Unresolved blockers.
- Recommended next steps.

Distinguish clearly between:

- Implemented but not tested.
- Tested locally.
- Validated under a specified load.
- Deployed and verified in a real environment.

Do not label the application production-ready solely because it builds or its unit tests pass.

# 19. DEFINITION OF DONE

SkyScout AI is considered complete only when the following are true:

- The application has a cohesive, polished, responsive interface.
- Users can perform the primary flight-search journey.
- Search and recommendation logic obey hard constraints.
- Provider integrations use permitted sources and honest data labeling.
- User data and monitoring configurations persist in PostgreSQL.
- Redis caching and background jobs behave reliably.
- Price observations and notifications are deduplicated.
- Users can manage saved searches and monitoring rules.
- Authentication and authorization are enforced server-side.
- Critical automated tests exist and have been executed.
- Failure handling and performance have been evaluated.
- Documentation covers setup, architecture, testing, and deployment.
- Visual checks and release verification are documented.
- Remaining limitations are disclosed rather than hidden.

**Final instruction:** Start by inspecting the existing repository and producing the five planning documents. Then implement Phase 1 and proceed sequentially through the remaining phases. Maintain the visual quality, engineering discipline, and product vision throughout. Deliver a real, tested, maintainable application—not just a demonstration of what could be built.