"""Celery tasks: thin wrappers around services. Every task is safe to run twice."""

import logging
import random
import traceback
import uuid
from datetime import datetime
from typing import Any

from celery import Task
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.metrics import TASK_FAILURES
from app.models import JobFailure
from app.models.base import utcnow
from app.repositories.users import SessionRepository
from app.services.monitoring import mark_failed_runs_stale, run_refresh, schedule_due
from app.services.notifications import deliver_email, email_backend
from app.services.search import default_search_service
from app.workers.celery_app import celery

log = logging.getLogger(__name__)


class RecordedTask(Task):  # type: ignore[misc]
    """Dead-letter handling: a task that finally fails (no retries left) is persisted to
    `job_failures` so it can be inspected and replayed, instead of vanishing into the logs."""

    def on_failure(
        self, exc: BaseException, task_id: str, args: Any, kwargs: Any, einfo: Any
    ) -> None:
        TASK_FAILURES.labels(self.name).inc()
        log.error("task failed permanently", extra={"task": self.name, "task_id": task_id})
        try:
            with get_sessionmaker()() as db:
                db.add(
                    JobFailure(
                        task_name=self.name,
                        task_id=task_id,
                        args={
                            "args": [str(a) for a in args],
                            "kwargs": {k: str(v) for k, v in kwargs.items()},
                        },
                        error="".join(traceback.format_exception(exc))[-4000:],
                    )
                )
                db.commit()
        except Exception:
            log.exception("could not record job failure")


@celery.task(name="app.workers.tasks.ping")
def ping() -> str:
    return "pong"


@celery.task(name="app.workers.tasks.purge_expired_sessions", base=RecordedTask)
def purge_expired_sessions() -> int:
    with get_sessionmaker()() as db:
        removed = SessionRepository(db).delete_expired(utcnow())
        db.commit()
    log.info("expired sessions purged", extra={"count": removed})
    return removed


@celery.task(name="app.workers.tasks.schedule_due_monitors", base=RecordedTask)
def schedule_due_monitors() -> int:
    with get_sessionmaker()() as db:
        claimed = schedule_due(db, get_settings(), utcnow())
    for query_id, slot in claimed:
        refresh_monitored_query.delay(str(query_id), slot.isoformat(), "schedule")
    if claimed:
        log.info("scheduled monitor refreshes", extra={"count": len(claimed)})
    return len(claimed)


@celery.task(
    name="app.workers.tasks.refresh_monitored_query",
    base=RecordedTask,
    autoretry_for=(OperationalError,),  # database blip: retry; provider errors are handled inside
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def refresh_monitored_query(query_id: str, slot: str, trigger: str = "schedule") -> dict[str, Any]:
    out = run_refresh(
        get_sessionmaker(),
        default_search_service(),
        get_settings(),
        uuid.UUID(query_id),
        datetime.fromisoformat(slot),
        trigger,
    )
    for nid in out.notification_ids:
        send_notification_email.delay(str(nid))
    log.info(
        "monitor refresh finished",
        extra={
            "query_id": query_id,
            "status": out.status,
            "notifications": len(out.notification_ids),
        },
    )
    return {
        "status": out.status,
        "observations": out.observations,
        "notifications": len(out.notification_ids),
    }


@celery.task(
    name="app.workers.tasks.send_notification_email", base=RecordedTask, bind=True, max_retries=None
)
def send_notification_email(self: Task, notification_id: str) -> str:
    settings = get_settings()
    with get_sessionmaker()() as db:
        result = deliver_email(db, uuid.UUID(notification_id), email_backend(settings), settings)
    if result.retry:
        # Exponential backoff with jitter; deliver_email stops asking at the attempt cap.
        delay = min(3600, 30 * 2**self.request.retries) * random.uniform(0.5, 1.0)  # noqa: S311
        raise self.retry(countdown=delay)
    if result.status == "failed":
        raise RuntimeError(f"email delivery failed permanently for notification {notification_id}")
    return result.status


@celery.task(name="app.workers.tasks.sweep_stale_runs", base=RecordedTask)
def sweep_stale_runs() -> int:
    with get_sessionmaker()() as db:
        return mark_failed_runs_stale(db, get_settings(), utcnow())
