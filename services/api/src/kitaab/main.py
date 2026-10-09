"""Application factory."""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from kitaab import __version__
from kitaab.api.v1 import router as v1_router
from kitaab.config import get_settings
from kitaab.problems import install_problem_handlers


def _operation_id(route: APIRoute) -> str:
    # Function names are unique across the app and read well in generated clients.
    return route.name


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
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
    )
    install_problem_handlers(app)
    app.include_router(v1_router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok"}

    return app


app = create_app()
