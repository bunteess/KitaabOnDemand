# syntax=docker/dockerfile:1.7
# Local S3-compatible storage. MinIO no longer publishes container images, so
# we build a pinned commit from the Go module proxy (docs/DECISIONS.md, D-004).
ARG DOCKER_REGISTRY=docker.io

FROM ${DOCKER_REGISTRY}/library/golang:1.25-alpine AS build
ARG MINIO_VERSION=v0.0.0-20260212201848-7aac2a2c5b7c
RUN --mount=type=secret,id=build_ca \
    --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    CGO_ENABLED=0 GOBIN=/out go install -trimpath -ldflags "-s -w" "github.com/minio/minio@${MINIO_VERSION}"

FROM ${DOCKER_REGISTRY}/library/alpine:3.22
RUN adduser -D -u 10001 minio && mkdir -p /data && chown minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
USER minio
EXPOSE 9000 9001
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD wget -q -O /dev/null http://127.0.0.1:9000/minio/health/live || exit 1
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
