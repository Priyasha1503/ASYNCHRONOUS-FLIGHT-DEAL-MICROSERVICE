"""Application settings, loaded from environment variables (prefix-free, see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-change-me"  # noqa: S105 — rejected in production by the guard below


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = _DEV_SECRET

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://skyscout:skyscout@127.0.0.1:5432/skyscout"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_s: float = Field(default=5.0, gt=0)
    db_statement_timeout_ms: int = Field(default=10_000, ge=100)

    redis_url: RedisDsn = RedisDsn("redis://127.0.0.1:6379/0")
    redis_socket_timeout_s: float = Field(default=2.0, gt=0)
    celery_broker_url: str | None = None  # defaults to redis_url

    cors_origins: list[str] = ["http://localhost:3000"]

    session_cookie_name: str = "skyscout_session"
    csrf_cookie_name: str = "skyscout_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_ttl_hours: int = Field(default=24 * 14, ge=1)
    cookie_secure: bool = False

    auth_rate_limit_per_minute: int = Field(default=10, ge=1)

    # Flight providers. "demo" works without credentials; real ones arrive in Phase 6.
    enabled_providers: list[str] = ["demo"]
    demo_provider_latency_ms: int = Field(default=0, ge=0, le=10_000)

    # Travelpayouts / Aviasales Data API (recently observed fares + affiliate booking links).
    travelpayouts_token: SecretStr | None = None
    travelpayouts_marker: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    travelpayouts_base_url: str = "https://api.travelpayouts.com"
    travelpayouts_link_host: str = "https://www.aviasales.com"
    travelpayouts_requests_per_minute: int = Field(default=60, ge=1)
    # Data is a recent sighting by nature; Travelpayouts recommends caching on our side.
    travelpayouts_cache_ttl_s: int = Field(default=3 * 3600, ge=60, le=86_400)

    # Search: shared cache, single-flight, resilience. See docs/ARCHITECTURE.md §3.1 and §4.
    search_cache_ttl_s: int = Field(default=600, ge=10, le=86_400)
    provider_timeout_s: float = Field(default=12.0, gt=0, le=60)
    provider_max_attempts: int = Field(default=2, ge=1, le=5)  # interactive: keep retries short
    search_deadline_s: float = Field(default=15.0, gt=0, le=90)  # whole fan-out, all providers
    circuit_failure_threshold: int = Field(default=5, ge=1)
    circuit_window_s: int = Field(default=60, ge=1)
    circuit_cooldown_s: int = Field(default=30, ge=1)
    search_rate_limit_per_minute: int = Field(default=30, ge=1)
    max_nearby_combinations: int = Field(default=4, ge=1, le=9)
    no_cache_max_concurrency: int = Field(default=4, ge=1)  # provider calls while Redis is down

    # Monitoring
    max_active_monitors_per_user: int = Field(default=10, ge=1, le=1000)
    monitor_min_interval_minutes: int = Field(default=60, ge=1)  # floor for every rule's frequency
    monitor_schedule_batch: int = Field(default=200, ge=1)
    refresh_stale_after_s: int = Field(
        default=900, ge=60
    )  # a "running" run older than this is dead
    manual_refresh_cooldown_s: int = Field(default=120, ge=0)
    observations_per_run_cap: int = Field(default=200, ge=1)

    # Notifications. "console" logs emails and records them as *simulated*, never as sent.
    email_backend: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "SkyScout <alerts@example.invalid>"
    smtp_starttls: bool = True
    smtp_timeout_s: float = Field(default=10.0, gt=0)
    email_max_attempts: int = Field(default=4, ge=1, le=10)
    app_base_url: str = "http://localhost:3000"

    celery_task_always_eager: bool = False  # tests only

    @property
    def demo_simulation_enabled(self) -> bool:
        """The "simulate price change" tool exists only for demo data outside production."""
        return self.environment != "production" and "demo" in self.enabled_providers

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or str(self.redis_url)

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.environment == "production":
            problems = []
            if self.secret_key == _DEV_SECRET or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be set to a random value of 32+ chars")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true")
            if "skyscout:skyscout@" in str(self.database_url):
                problems.append("DATABASE_URL uses development credentials")
            if any(o == "*" for o in self.cors_origins):
                problems.append("CORS_ORIGINS must not contain '*'")
            if self.email_backend == "smtp" and not self.smtp_host:
                problems.append("EMAIL_BACKEND=smtp requires SMTP_HOST")
            if self.celery_task_always_eager:
                problems.append("CELERY_TASK_ALWAYS_EAGER is for tests only")
            if "travelpayouts" in self.enabled_providers and not (
                self.travelpayouts_token and self.travelpayouts_marker
            ):
                problems.append(
                    "travelpayouts requires TRAVELPAYOUTS_TOKEN and TRAVELPAYOUTS_MARKER"
                )
            if problems:
                raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
