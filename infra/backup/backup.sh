#!/bin/sh
# Daily database backup (infra/docker-compose.prod.yml, docs/RUNBOOK.md).
# Runs `pg_dump --format=custom` around 02:00 local time and deletes dumps older
# than BACKUP_KEEP_DAYS. Run once by hand with: backup.sh --now
set -eu

dump() {
  name="kitaab-$(date +%Y-%m-%dT%H%M).dump"
  pg_dump --format=custom --no-owner --file="/backups/${name}.partial"
  mv "/backups/${name}.partial" "/backups/${name}"
  find /backups -name 'kitaab-*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
  echo "backup written: ${name} ($(du -h "/backups/${name}" | cut -f1))"
}

if [ "${1:-}" = "--now" ]; then
  dump
  exit 0
fi

while true; do
  # Sleep until the next 02:00.
  now=$(date +%s)
  next=$(date -d "$(date +%Y-%m-%d) 02:00" +%s 2>/dev/null || echo 0)
  if [ "$next" -le "$now" ]; then
    next=$((next + 86400))
  fi
  if [ "$next" -le 86400 ]; then
    next=$((now + 86400))
  fi
  sleep $((next - now))
  dump || echo "backup failed" >&2
done
