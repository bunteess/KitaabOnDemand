#!/usr/bin/env bash
# Load test against a running stack (make demo first). Results: tests/load/results/.
#   USERS=50 SPAWN_RATE=10 DURATION=2m make load
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p tests/load/results
cd services/api
exec uv run --group load locust \
  -f ../../tests/load/locustfile.py \
  --host "${LOAD_HOST:-http://localhost:8080}" \
  --headless \
  --users "${USERS:-50}" \
  --spawn-rate "${SPAWN_RATE:-10}" \
  --run-time "${DURATION:-2m}" \
  --csv ../../tests/load/results/run \
  --only-summary
