"""Liveness/readiness. Readiness covers our own dependencies only — it is *not* a claim that any
external flight provider is healthy (provider health has its own endpoint in a later phase)."""

import logging
from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.db import ping_db
from app.core.redis import ping_redis

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    checks: dict[str, Any] = {}
    try:
        ping_db()
        checks["postgres"] = "ok"
    except Exception as exc:
        log.warning("readiness: postgres down", extra={"error_type": type(exc).__name__})
        checks["postgres"] = "down"
    try:
        ping_redis()
        checks["redis"] = "ok"
    except Exception as exc:
        log.warning("readiness: redis down", extra={"error_type": type(exc).__name__})
        checks["redis"] = "down"

    # Postgres is the system of record: without it we are not ready.
    # Redis loss degrades caching/rate-limits/queues but auth and reads keep working.
    if checks["postgres"] != "ok":
        status, code = "unavailable", 503
    elif checks["redis"] != "ok":
        status, code = "degraded", 200
    else:
        status, code = "ok", 200
    return JSONResponse({"status": status, "checks": checks}, status_code=code)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
