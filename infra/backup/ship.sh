#!/bin/sh
# Copies the daily database dumps to S3 (infra/docker-compose.prod.yml,
# docs/RUNBOOK.md). Runs every hour and uploads only dumps not yet in the
# bucket. Its credentials can add files but not read or delete them; the
# bucket's lifecycle rule removes old dumps (infra/terraform/backups.tf).
# Run once by hand with: ship.sh --now
set -eu

ship() {
  if [ -z "${BACKUP_S3_BUCKET:-}" ]; then
    echo "BACKUP_S3_BUCKET is not set: dumps stay on this server only" >&2
    return 0
  fi
  aws s3 sync /backups "s3://${BACKUP_S3_BUCKET}/postgres/" \
    --exclude "*" --include "kitaab-*.dump" --no-progress --only-show-errors
  echo "backups shipped to s3://${BACKUP_S3_BUCKET}/postgres/"
}

if [ "${1:-}" = "--now" ]; then
  ship
  exit 0
fi

while true; do
  ship || echo "shipping backups failed" >&2
  sleep 3600
done
