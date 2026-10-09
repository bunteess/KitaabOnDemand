# KitaabOnDemand API

FastAPI application, Celery worker and Celery beat scheduler.
See `docs/ARCHITECTURE.md` at the repository root.

```bash
uv sync                      # install dependencies into .venv
uv run pytest                # unit tests (integration tests need `make deps-up`)
uv run kitaab --help         # CLI: migrate, seed, create-admin, ...
```
