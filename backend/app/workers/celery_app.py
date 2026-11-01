"""Celery application shared by the worker and beat processes."""

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

celery = Celery("skyscout", broker=settings.broker_url, backend=str(settings.redis_url))
celery.conf.update(
    task_acks_late=True,  # a crashed worker's task is redelivered…
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # …and one slow task doesn't hoard others
    task_time_limit=120,
    task_soft_time_limit=90,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    beat_schedule={
        # One shared scheduler tick; each due *query* (not each user) becomes one refresh task.
        "schedule-due-monitors": {
            "task": "app.workers.tasks.schedule_due_monitors",
            "schedule": 60.0,
        },
        "sweep-stale-refresh-runs": {
            "task": "app.workers.tasks.sweep_stale_runs",
            "schedule": 300.0,
        },
        "purge-expired-sessions": {
            "task": "app.workers.tasks.purge_expired_sessions",
            "schedule": 3600.0,
        },
    },
)
celery.conf.include = ["app.workers.tasks"]
