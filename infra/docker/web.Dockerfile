# syntax=docker/dockerfile:1.7
# Builds the React portal and serves it with Caddy as a non-root user.
# Caddy also proxies /api to the API so the portal is same-origin.
ARG DOCKER_REGISTRY=docker.io

FROM ${DOCKER_REGISTRY}/library/node:24-alpine AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN --mount=type=secret,id=build_ca \
    --mount=type=cache,target=/root/.npm \
    if [ -s /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM ${DOCKER_REGISTRY}/library/caddy:2-alpine AS runtime
RUN addgroup -S web && adduser -S -G web -u 10001 web \
 && mkdir -p /data /config && chown -R web:web /data /config
ENV XDG_DATA_HOME=/data XDG_CONFIG_HOME=/config
COPY infra/caddy/web.Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
USER web
EXPOSE 8080
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
