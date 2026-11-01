"""Prometheus metrics. Later phases add provider, cache, queue and notification metrics here."""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "skyscout_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "skyscout_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15),
)
AUTH_EVENTS = Counter("skyscout_auth_events_total", "Auth outcomes", ["event", "outcome"])

CACHE_EVENTS = Counter(
    "skyscout_offer_cache_events_total",
    "Offer cache events (hit, miss, coalesced, unavailable)",
    ["provider", "event"],
)
PROVIDER_CALLS = Counter(
    "skyscout_provider_calls_total",
    "Upstream provider calls by outcome",
    ["provider", "outcome"],
)
PROVIDER_LATENCY = Histogram(
    "skyscout_provider_call_duration_seconds",
    "Upstream provider call latency",
    ["provider"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 12, 20),
)
SEARCHES = Counter("skyscout_searches_total", "Searches by result", ["result"])

MONITOR_REFRESHES = Counter(
    "skyscout_monitor_refreshes_total",
    "Monitored-query refresh runs by outcome",
    ["outcome"],  # succeeded | partial | failed | duplicate
)
NOTIFICATIONS_CREATED = Counter(
    "skyscout_notifications_created_total", "Notifications created", ["kind"]
)
NOTIFICATION_DELIVERIES = Counter(
    "skyscout_notification_deliveries_total",
    "Notification delivery attempts by channel and status",
    ["channel", "status"],
)
TASK_FAILURES = Counter("skyscout_task_failures_total", "Exhausted background tasks", ["task"])
