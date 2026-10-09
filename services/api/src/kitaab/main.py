"""Application factory."""

from fastapi import FastAPI

from kitaab import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="KitaabOnDemand API", version=__version__)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
