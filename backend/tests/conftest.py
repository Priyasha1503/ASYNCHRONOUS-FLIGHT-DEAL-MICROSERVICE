"""Shared test setup. Points the app at disposable resources *before* anything imports settings.

* tests/unit — pure domain/provider tests; no database or Redis needed.
* tests/api  — HTTP + persistence tests; need Postgres (`skyscout_test`) and Redis DB 15
  (fixtures in tests/api/conftest.py).
"""

import os

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://skyscout:skyscout@127.0.0.1:5432/skyscout_test"
)
TEST_REDIS = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")

if not TEST_DB.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against non-test database: {TEST_DB}")

# Must be set before the app (and its cached settings) is imported.
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=TEST_DB,
    REDIS_URL=TEST_REDIS,
    AUTH_RATE_LIMIT_PER_MINUTE="1000",
    LOG_LEVEL="WARNING",
    ENABLED_PROVIDERS='["demo"]',
    CELERY_TASK_ALWAYS_EAGER="true",  # tasks run inline in tests
    MONITOR_MIN_INTERVAL_MINUTES="60",
)
