# Uses the Dockerfile frontend built into Docker 23+ (no "syntax" line), so a
# build pulls nothing from Docker Hub beyond DOCKER_REGISTRY (D-005).
# One Dockerfile, three runtime targets: api, worker, beat.
#   docker build -f infra/docker/api.Dockerfile --target api .
ARG DOCKER_REGISTRY=docker.io
ARG PYTHON_IMAGE=library/python:3.12-slim-trixie

# libmagic is copied from the full Debian image of the same release instead of
# installed with apt, so the build needs no Debian mirror access (D-033).
FROM ${DOCKER_REGISTRY}/library/python:3.12-trixie AS libmagic
RUN mkdir -p /out/lib /out/file \
 && cp -a /usr/lib/$(uname -m)-linux-gnu/libmagic.so.1* /out/lib/ \
 && cp /usr/lib/file/magic.mgc /out/file/

FROM ${DOCKER_REGISTRY}/${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY --from=libmagic /out/lib/ /usr/local/lib/
COPY --from=libmagic /out/file/ /usr/lib/file/
# libmagic looks for its database at /usr/share/misc/magic.mgc, a symlink the
# slim image lacks; MAGIC makes the path explicit as well.
ENV MAGIC=/usr/lib/file/magic.mgc
RUN mkdir -p /usr/share/misc \
 && ln -sf /usr/lib/file/magic.mgc /usr/share/misc/magic.mgc \
 && ldconfig

FROM base AS build
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir uv==0.11.32
WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock services/api/README.md ./
RUN --mount=type=secret,id=build_ca \
    --mount=type=cache,target=/root/.cache/uv \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY services/api/src ./src
COPY services/api/alembic.ini ./
COPY services/api/migrations ./migrations
RUN --mount=type=secret,id=build_ca \
    --mount=type=cache,target=/root/.cache/uv \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --frozen --no-dev --no-editable

FROM base AS runtime
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build --chown=app:app /app /app
ENV PATH=/app/.venv/bin:$PATH
WORKDIR /app
USER app

FROM runtime AS api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)" || exit 1
CMD ["uvicorn", "kitaab.main:create_production_app", "--host", "0.0.0.0", "--port", "8000", "--factory", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]

FROM runtime AS worker
CMD ["celery", "-A", "kitaab.workers.celery_app", "worker", "--loglevel=INFO", "--concurrency=2", "--without-gossip", "--without-mingle"]

FROM runtime AS beat
CMD ["celery", "-A", "kitaab.workers.celery_app", "beat", "--loglevel=INFO", "--schedule=/tmp/celerybeat-schedule"]
