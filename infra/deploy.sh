#!/usr/bin/env bash
# Deploys a released version on the production server (docs/DEPLOY.md):
#
#   ./infra/deploy.sh v1.2.3
#
# Run from the server's clone of the repository. It checks out the release tag,
# takes a database backup, pulls the release images, runs migrations and
# restarts the services, then checks the API answers through Caddy.
set -euo pipefail

# Everything runs inside main, so bash has read the whole script before the
# checkout below replaces it with the release's copy.
main() {
  local version="${1:-}"
  if ! [[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "usage: $0 vX.Y.Z" >&2
    exit 2
  fi

  cd "$(dirname "$0")/.."
  env_file=infra/.env.production
  if [ ! -f "$env_file" ]; then
    echo "$env_file is missing (copy infra/.env.production.example)" >&2
    exit 1
  fi
  compose=(docker compose -f infra/docker-compose.prod.yml --env-file "$env_file")

  echo "==> Checking out $version"
  git fetch --quiet --tags origin
  git checkout --quiet "refs/tags/$version"

  if [ -n "$("${compose[@]}" ps --quiet backup 2>/dev/null)" ]; then
    echo "==> Backing up the database"
    "${compose[@]}" exec -T backup sh /usr/local/bin/backup.sh --now
  fi

  echo "==> Pulling images"
  sed -i "s/^VERSION=.*/VERSION=$version/" "$env_file"
  "${compose[@]}" pull --quiet

  echo "==> Migrating and restarting"
  "${compose[@]}" up -d --wait --remove-orphans

  api_domain=$(sed -n 's/^API_DOMAIN=//p' "$env_file")
  echo "==> Checking https://$api_domain/readyz"
  for _ in $(seq 1 30); do
    if curl -fsS "https://$api_domain/readyz" > /dev/null; then
      echo "Deployed $version"
      exit 0
    fi
    sleep 2
  done
  echo "The API is not ready after a minute. Check: ${compose[*]} logs api" >&2
  exit 1
}

main "$@"
