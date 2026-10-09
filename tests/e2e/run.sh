#!/usr/bin/env bash
# Full-stack end-to-end scenarios with mock providers (make e2e).
# Starts the stack with demo data unless E2E_SKIP_STACK=1, then runs the
# scenarios over HTTP through the portal's proxy, with the API's tooling.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ "${E2E_SKIP_STACK:-0}" != "1" ]; then
  make demo
fi
cd services/api
exec uv run pytest -c ../../tests/e2e/pytest.ini ../../tests/e2e "$@"
