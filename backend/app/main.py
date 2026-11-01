import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.deps import require_csrf
from app.api.v1 import auth, monitoring, search
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SkyScout AI API",
        version="0.1.0",
        docs_url="/api/docs" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", settings.csrf_header_name, "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.isprintable() else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            route = request.scope.get("route")
            label = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, label, str(status)).inc()
            HTTP_LATENCY.labels(request.method, label).observe(time.perf_counter() - start)
            request_id_var.reset(token)

    app.include_router(health.router)

    v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(require_csrf)])
    v1.include_router(auth.router)
    v1.include_router(search.router)
    v1.include_router(monitoring.router)
    app.include_router(v1)
    return app


app = create_app()
