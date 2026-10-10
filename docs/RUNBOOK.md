# Runbook

Day-to-day operations on the production server (`docs/DEPLOY.md`). Commands
run from `/opt/kitaabondemand` with this alias:

```bash
alias dc='docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production'
```

Each procedure below was tried on the development stack on 10 October 2026,
except where a step needs real AWS or a real provider.

## Health and logs

- `https://API_DOMAIN/healthz` answers while the process is up.
  `https://API_DOMAIN/readyz` also checks the database and Redis, and answers
  503 when either is down.
- `dc ps` shows each service and its health.
- `dc logs -f --since 30m api worker beat` shows the application logs. Every
  line is JSON. Phone numbers and email addresses are masked, and request logs
  carry the path only.
- Every API response has an `X-Request-ID` header, which the browser's
  network panel shows. To follow one request, run
  `dc logs api | grep <request id>`.
- Docker keeps 10 files of 20 MB per container. With `SENTRY_DSN` set,
  unexpected errors also go to Sentry.

Scheduled work:

| What | When (Pakistan time) | Where |
| --- | --- | --- |
| Expire quotes past their validity | Every 5 minutes | beat → worker |
| Expire unpaid digital payments (`PENDING_PAYMENT_TTL_HOURS`) | Every 15 minutes | beat → worker |
| Poll couriers for shipment status | Every 30 minutes | beat → worker |
| Purge files (`PURGE_DAYS` after delivery or exit; unattached uploads after a day) | Hourly at :07 | beat → worker |
| Database dump | Daily at 02:00 | backup |
| Copy new dumps to S3 | Hourly | backup-ship |

## Backups and the restore drill

What exists:

- a custom-format `pg_dump` from every night in `infra/backups/`, kept for
  `BACKUP_KEEP_DAYS` (14);
- the same dumps in the backup bucket under `postgres/`, kept for 35 days. The
  server's credentials can add dumps there but cannot read or delete them.

Customer files are not in the dumps. They live in the versioned upload bucket
until the purge deletes them.

Check daily, or set up an alert:

```bash
ls -lh infra/backups | tail -3        # a dump from last night
dc logs --since 26h backup backup-ship
```

Use your own AWS credentials to check the bucket:
`aws s3 ls s3://<backup bucket>/postgres/ | tail -3`.

**Drill, once a month.** Restore the latest dump into a scratch database and
compare it with the live one. The `backup` container already has the
connection settings.

```bash
dc exec backup sh -c 'createdb kitaab_drill &&
  pg_restore --no-owner --exit-on-error -d kitaab_drill "$(ls /backups/kitaab-*.dump | tail -1)"'
for db in kitaab_drill kitaab; do
  dc exec backup psql -d $db -tAc "select '$db', (select count(*) from orders), (select count(*) from ledger_entries)"
done
dc exec backup dropdb kitaab_drill
```

The counts should match, give or take orders placed since 02:00. Then fetch
one dump back from S3 with your own credentials, to prove that copy works too.

**Restoring for real** (data was lost or corrupted):

1. Stop writes with `dc stop api worker beat`. The portal and app show errors
   until step 5.
2. Dump the current state, however broken, so nothing is lost for good:
   `dc exec backup sh /usr/local/bin/backup.sh --now`.
3. Pick the dump. For one from S3, download it with your own credentials:
   `aws s3 cp s3://<backup bucket>/postgres/<file> infra/backups/`.
4. Restore over the live database:

   ```bash
   dc exec backup pg_restore --clean --if-exists --no-owner --exit-on-error \
     -d kitaab /backups/<file>
   ```

5. Run `dc up -d`. The migrate step brings the schema up to the running
   release.
6. Anything paid or delivered after the dump is missing. Reconcile it from
   the gateway and courier dashboards, and tell affected customers.

## Rotating secrets

Edit `infra/.env.production`, then recreate the services that read the value.
Compose recreates a container when its settings change.

| Secret | What rotating it does | Steps |
| --- | --- | --- |
| `JWT_SECRET` | Access tokens (15 minutes) stop working. Apps and the portal renew them silently; refresh tokens are not signed with this secret | Edit, then `dc up -d api` |
| `OTP_PEPPER` | Sign-in codes sent in the last 5 minutes stop working; customers ask for a new one | Edit at a quiet hour, then `dc up -d api worker` |
| `DATA_ENCRYPTION_KEY` | Admins' authenticator secrets are encrypted with it, so they must be re-encrypted | See below |
| `MOCK_WEBHOOK_SECRET` | Nothing in production (mock providers are off) | Edit, then `dc up -d api` |
| `POSTGRES_PASSWORD` | The database login | See below |
| AWS access keys (API, backup) | Storage access | Create a second key in the IAM console, edit, `dc up -d api worker backup-ship`, check an upload and `ship.sh --now`, then deactivate and delete the old key |
| Firebase service account | Push notifications | Create a new key in the Firebase console, replace `infra/secrets/fcm-service-account.json`, `dc restart api worker`, then delete the old key |

**`DATA_ENCRYPTION_KEY`.** Admin sign-in fails for the minute between steps 3
and 4.

1. Generate the new key with `openssl rand -base64 48` and keep the old one.
2. Put the new key in `.env.production`.
3. Re-encrypt. `read -s` keeps the old key out of your shell history and the
   process list:

   ```bash
   read -rs OLD_DATA_ENCRYPTION_KEY && export OLD_DATA_ENCRYPTION_KEY
   dc run --rm -e OLD_DATA_ENCRYPTION_KEY api kitaab rotate-encryption-key
   unset OLD_DATA_ENCRYPTION_KEY
   ```

   It reports how many secrets it re-encrypted. It is safe to run twice. It
   changes nothing if a secret opens with neither key, or if you forgot step 2.
4. Run `dc up -d api`.

If the old key is lost, give every admin a new authenticator with
`reset-staff-login` (below).

**`POSTGRES_PASSWORD`.** The variable is only read when the database is first
created, so change the password inside Postgres too:

```bash
dc exec postgres psql -U kitaab -c "ALTER USER kitaab PASSWORD '<new hex password>'"
# then set POSTGRES_PASSWORD and the password inside DATABASE_URL, and
dc up -d
```

After any suspected leak, rotate everything the leak could reach, then review
the portal's Audit log.

## Staff sign-in problems

- **Locked out** after 5 wrong passwords: the lock lifts after 15 minutes, or
  another admin presses Unlock on the Admins page.
- **Lost phone or password**:
  `dc run --rm api kitaab reset-staff-login person@example.pk`. It prints a
  new temporary password, plus a new authenticator secret for an admin. It
  also clears the lock and signs out every session. Share the output over a
  secure channel, never by plain email. The reset is written to the audit log.
- **Someone leaves**: press Deactivate on the Admins page, or for vendor
  staff in the vendor's Logins on the Vendors page. Their sessions end at once.

## Stuck uploads

An upload moves through these statuses:

| Status | Meaning | Normal duration |
| --- | --- | --- |
| `AWAITING_PARTS` | The app is still sending the file. It can resume for 24 hours | Minutes; abandoned ones are purged after a day |
| `VALIDATING` | Checks queued or running: size, PDF header, file type, virus scan, PDF structure | Seconds. A failing check is retried 5 times over about 8 minutes, then the upload is rejected as "could not be checked" |
| `VALID` / `REJECTED` | Done | |

An upload still `VALIDATING` after 15 minutes means its job was lost, for
example if the worker was down. Find such uploads:

```bash
dc exec postgres psql -U kitaab -d kitaab -c "select id, completed_at from uploads
  where status = 'VALIDATING' and completed_at < now() - interval '15 minutes'"
```

Then:

1. Check the worker with `dc ps worker` and `dc logs --since 1h worker`, and
   start it if needed.
2. Check ClamAV with `dc logs --since 1h clamav`. On first start it downloads
   its signature database, which takes several minutes. Uploads checked in
   that window are retried, then rejected as "could not be checked".
3. Queue the check again for each id. This is safe: the check does nothing to
   an upload that is no longer `VALIDATING`.

   ```bash
   dc exec worker celery -A kitaab.workers.celery_app call validate_upload --args='["<upload id>"]'
   ```

A rejected upload's file is deleted at once, so the customer uploads again.
The app shows them the reason.

## Purge failures

The purge runs hourly at :07. It deletes every stored version of each file
that is due, and removes the shipping details of deleted accounts once their
orders finish (D-016, D-019).

- Each run writes a `purge.run` entry to the Audit log with its counts and an
  `errors` count. Each failure is also logged as `purge failed for upload`
  with the upload id (`dc logs worker | grep "purge failed"`).
- A file that failed keeps its place and is tried again the next hour. One
  failed run is not urgent; the same ids failing for a day are.
- The usual cause is S3 refusing a request. Check that the API user still has
  the Terraform policy, which needs `s3:ListBucketVersions` and
  `s3:DeleteObjectVersion`, and that its access key is active.
- To see what is due without deleting anything, run
  `dc run --rm api kitaab purge --dry-run`. To run the purge now, run
  `dc run --rm api kitaab purge`.
- `PURGE_DRY_RUN=true` pauses deletion while you investigate. The privacy
  policy promises deletion after 7 days, so turn it back off soon.

## Webhooks

Payment and courier providers post to:

- `https://API_DOMAIN/api/v1/webhooks/payments/<provider>`
- `https://API_DOMAIN/api/v1/webhooks/couriers/<provider>`

Each event is verified by signature and applied in one transaction. Its event
id is recorded in the same transaction.

- **200** means it was applied. A repeat answers `{"status": "duplicate"}` and
  changes nothing, so replaying is always safe.
- **401 `invalid-signature`** means the secret in our settings does not match
  the provider's. It is logged as `payment webhook rejected` or `courier
  webhook rejected`, with the provider name.
- **404** means the provider is not in `PAYMENT_PROVIDERS` or
  `COURIER_PROVIDERS`.
- **5xx** means nothing was recorded. The provider's retry, or a replay,
  applies it later.

**Replaying.** Use the provider's own dashboard or API to resend an event, as
its documentation describes (`docs/INTEGRATIONS.md`; the real adapters are
built only from that documentation). Never forge one by hand, because
signatures are checked.

**Missed events.**

- Courier statuses are also polled every 30 minutes for open shipments with
  couriers that support it. With manual consignment numbers, admins mark
  orders delivered or failed in the portal.
- An unpaid digital payment expires after `PENDING_PAYMENT_TTL_HOURS`. If the
  gateway confirms it later, the order is placed, or the money is refunded if
  the order has closed (D-043).

## Store review mode

For the Google Play review window only (D-020):

1. In `.env.production`, set `REVIEW_MODE_ENABLED=true` and
   `ALLOW_REVIEW_MODE_IN_PRODUCTION=true`, plus a `REVIEW_PHONE` and a
   `REVIEW_OTP` other than `000000`. Then run `dc up -d api`.
2. The API logs a warning at startup. Orders from the review account are
   flagged in the portal so nobody fulfils them.
3. Put the phone and code in the Play Console review notes.
4. Once the review is approved, set both flags back to `false` and run
   `dc up -d api`.

## Before each release

- CI is green on the commit you tag: tests, end-to-end, audits, image builds.
- Re-run the dependency audits in `docs/SECURITY.md` if the last one is more
  than a month old.
- `deploy.sh` takes a backup before it changes anything. Keep the dump name in
  case you must roll back.
