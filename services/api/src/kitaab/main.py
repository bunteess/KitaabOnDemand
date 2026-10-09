"""Application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import text

from kitaab import __version__
from kitaab.api import dev, mock_pages
from kitaab.api.v1 import router as v1_router
from kitaab.config import Settings, get_settings
from kitaab.container import Services, build_services
from kitaab.logging import configure_logging
from kitaab.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from kitaab.problems import install_problem_handlers

log = logging.getLogger(__name__)


def _operation_id(route: APIRoute) -> str:
    # Function names are unique across the app and read well in generated clients.
    return route.name


def create_app(services: Services | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or (services.settings if services else get_settings())
    threads = settings.threadpool_size

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Sync endpoints run here; the database pool is sized to match (kitaab/db.py).
        anyio.to_thread.current_default_thread_limiter().total_tokens = threads
        yield

    app = FastAPI(
        lifespan=lifespan,
        title="KitaabOnDemand API",
        version=__version__,
        description=(
            "REST API for the KitaabOnDemand app and portal. Errors use RFC 7807 "
            "(application/problem+json) with a machine-readable `code`. Money is integer "
            "paisa. Times are UTC."
        ),
        generate_unique_id_function=_operation_id,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    # Building providers needs Redis and storage; the OpenAPI export does not.
    app.state.services = services
    app.state.settings = settings

    install_problem_handlers(app)
    app.include_router(v1_router)
    if settings.dev_tools_enabled:
        app.include_router(dev.router)
    if "mock" in settings.payment_providers or "mock" in settings.courier_providers:
        app.include_router(mock_pages.router)

    # Order matters: the outermost middleware is added last.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition"],
        max_age=600,
    )
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"], response_model=None)
    def readyz() -> dict[str, str] | JSONResponse:
        """Readiness: the database and Redis answer."""
        current: Services = app.state.services
        checks: dict[str, str] = {}
        try:
            with current.session() as session:
                session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"
        try:
            current.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
        if all(v == "ok" for v in checks.values()):
            return {"status": "ok", **checks}
        return JSONResponse({"status": "error", **checks}, status_code=503)

    return app


def create_production_app() -> FastAPI:
    """ASGI entry point used by uvicorn: validates settings, builds services."""
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=False,
            traces_sample_rate=0.0,
            environment=settings.environment.value,
        )
    if settings.review_mode_enabled and settings.is_production:
        log.warning(
            "REVIEW MODE IS ON IN PRODUCTION: the store reviewer account accepts a fixed code"
        )
    return create_app(build_services(settings), settings)
