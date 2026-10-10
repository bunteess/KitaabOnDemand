# Deploy

The default deployment is one Linux server (EC2 or Lightsail) running Docker
Compose, in `ap-south-1` (Mumbai), the AWS region closest to Pakistan. Any
region works: set it in Terraform and in `S3_REGION`. Notes on moving to ECS
and RDS are at the end.

Nothing here has been run against a real AWS account. Terraform was validated,
and planned offline (21 resources). The production compose file was started
locally with the release images and stand-in certificates (10 October 2026).
That covered TLS on both names, HTTP to HTTPS redirects, security headers, the
portal's API proxy, migrations and seeding. The backup, S3 copy and restore
scripts were tested against the development database and MinIO.

## What runs

`infra/docker-compose.prod.yml`, with every container on one private network.
Only Caddy publishes ports.

| Service | Image | Job |
| --- | --- | --- |
| caddy | `caddy:2-alpine` | TLS certificates (automatic), HTTPS for both domains, HSTS |
| migrate | `kitaabondemand-api` | Runs database migrations, then exits; the API waits for it |
| api | `kitaabondemand-api` | The API (`WEB_CONCURRENCY` processes) |
| worker | `kitaabondemand-worker` | Background jobs: file checks, notifications, refunds |
| beat | `kitaabondemand-beat` | Schedules expiries, courier polling and the purge |
| web | `kitaabondemand-web` | The admin and vendor portal; proxies `/api` to the API |
| clamav | `clamav/clamav:stable` | Virus scanning of uploads (required in production) |
| postgres | `postgres:16-alpine` | Database, on the `pgdata` volume |
| redis | `redis:7-alpine` | Job queue, rate limits; append-only file on `redisdata` |
| backup | `postgres:16-alpine` | `pg_dump` every night at 02:00 Pakistan time into `infra/backups/` |
| backup-ship | `amazon/aws-cli:2.31.18` | Copies new dumps to the backup bucket every hour |

Customer files never touch the server. Phones upload straight to S3 through
presigned URLs, and staff download through 5-minute signed links.

## Before you start

You need the items under "Accounts and credentials" in `docs/OWNER_TODO.md`:
an AWS account, a domain, a Firebase service account, and the Google OAuth
client IDs. The SMS gateway adapter must also exist, or customers cannot
receive sign-in codes. Payment gateways and couriers are optional at launch:
without them the platform takes cash on delivery only, and admins type
consignment numbers by hand.

## 1. Storage and access keys (Terraform)

The owner runs these with their own AWS credentials. CI only formats and
validates; it never plans against AWS or applies.

```bash
cd infra/terraform
cp terraform.tfvars.example production.tfvars    # bucket names, portal origin
terraform init
terraform plan -var-file=production.tfvars       # read it: 21 resources to add
terraform apply -var-file=production.tfvars
terraform output
```

This creates:

- the upload bucket (private, encrypted, versioned, CORS for the portal), with
  lifecycle rules for abandoned multipart uploads and old versions;
- the backup bucket (private, encrypted, versioned), which deletes dumps after
  35 days;
- the IAM user `kitaabondemand-production-api`, which can read and write the
  upload bucket and nothing else;
- the IAM user `kitaabondemand-production-backup`, which can add dumps to the
  backup bucket but cannot read or delete them.

Terraform creates no access keys, so no secret lands in its state. In the IAM
console, create one access key for each user and keep both for step 4. On EC2
you can attach `api_policy_arn` to the instance role instead of using the API
user's key.

State is kept locally in `terraform.tfstate`. It holds no secrets, but keep it
safe, or set up an S3 backend before the first apply.

## 2. The server

- **Size**: 2 vCPU and 4 GB is enough for launch traffic (`docs/PERF.md`), with
  at least 40 GB of disk. On Lightsail, pick Ubuntu 24.04 LTS and attach a
  static IP. On EC2, pick a t3.medium with an Elastic IP.
- **Firewall**: SSH (22) from your own IP only; 80 and 443 (TCP) from
  anywhere; 443 UDP from anywhere for HTTP/3 (optional).
- **Docker**: install Docker Engine and the Compose plugin with Docker's
  official instructions for Ubuntu. Create a `deploy` user in the `docker`
  group.
- **Code**: the server needs the `infra/` folder and the release tags. Give it
  a read-only deploy key on GitHub and clone into `/opt/kitaabondemand`:

  ```bash
  sudo mkdir -p /opt/kitaabondemand && sudo chown deploy /opt/kitaabondemand
  git clone git@github.com:bunteess/KitaabOnDemand.git /opt/kitaabondemand
  ```

- **Images**: the release workflow pushes them to GitHub's container registry.
  Packages of a private repository are private, so log in once with a token
  that has only `read:packages`:

  ```bash
  echo "$TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
  ```

## 3. DNS

Point an A record for each name at the server's IP, for example
`api.example.pk` and `portal.example.pk`. Caddy requests certificates on first
start, so DNS must resolve before step 6.

## 4. Settings and secrets

```bash
cd /opt/kitaabondemand/infra
cp .env.production.example .env.production
chmod 600 .env.production
mkdir -p secrets && chmod 700 secrets
```

Fill in every value. The API checks them at startup and refuses to start if
debug, development tools or mock providers are on, if a secret is missing,
short or a development default, if CORS or the base URL are unsafe, or if
ClamAV is off. It also refuses an unknown provider name.

| Setting | Value |
| --- | --- |
| `VERSION` | The release tag, for example `v1.0.0` (`deploy.sh` sets it) |
| `API_DOMAIN`, `PORTAL_DOMAIN`, `ACME_EMAIL` | Your names, and an email for certificate notices |
| `PUBLIC_BASE_URL`, `WEB_ORIGINS` | `https://` + the API name, and `https://` + the portal name |
| `POSTGRES_PASSWORD` | `openssl rand -hex 32` (hex, because it also goes in a URL) |
| `DATABASE_URL` | Replace `REPLACE_WITH_POSTGRES_PASSWORD` with the same password |
| `JWT_SECRET`, `OTP_PEPPER`, `DATA_ENCRYPTION_KEY`, `MOCK_WEBHOOK_SECRET` | `openssl rand -base64 48`, a different value each |
| `S3_BUCKET`, `S3_REGION` | Terraform outputs `bucket_name` and `region` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | The API user's access key |
| `BACKUP_S3_BUCKET` | Terraform output `backup_bucket_name` |
| `BACKUP_AWS_ACCESS_KEY_ID`, `BACKUP_AWS_SECRET_ACCESS_KEY` | The backup user's access key |
| `GOOGLE_OAUTH_CLIENT_IDS` | The web client ID first, then the Android client IDs |
| `SMS_PROVIDER` | The SMS gateway's adapter name, once it is built (`docs/INTEGRATIONS.md`) |
| `PAYMENT_PROVIDERS`, `COURIER_PROVIDERS` | Empty for cash on delivery and typed CNs; adapter names once built |
| `SENTRY_DSN` | Optional |

Store the Firebase service account JSON as
`infra/secrets/fcm-service-account.json` (`chmod 600`). Production requires
push through Firebase, and the API refuses to start if that file is missing or
is not a service account key.

Keep a copy of `.env.production` and the service account file in a password
manager. Losing `DATA_ENCRYPTION_KEY` locks every admin out until you reset
their logins (`docs/RUNBOOK.md`).

## 5. A release

Tag a commit on the main branch whose CI is green. The tag must match the
version in `apps/mobile/pubspec.yaml`:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

The Release workflow pushes
`ghcr.io/bunteess/kitaabondemand-{api,worker,beat,web}:v1.0.0` and builds the
Android App Bundle (`docs/RELEASE_MOBILE.md`).

## 6. First start

```bash
cd /opt/kitaabondemand
./infra/deploy.sh v1.0.0
```

`deploy.sh` checks out the tag, backs up the database if it is running, sets
`VERSION`, pulls the images, runs migrations, starts everything, and waits for
`https://API_DOMAIN/readyz`. Then, once only:

```bash
alias dc='docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production'
dc run --rm api kitaab seed                                    # cities, placeholder pricing, settings
dc run --rm api kitaab create-admin you@example.pk "Your Name" # temporary password and TOTP secret
```

Add the TOTP secret to an authenticator app, sign in at
`https://PORTAL_DOMAIN`, then:

1. Replace the placeholder pricing, cities and zones, and the support contact
   (Settings, Pricing, Cities).
2. Add each vendor and their logins (Vendors).
3. Check backups end to end:
   `dc exec backup sh /usr/local/bin/backup.sh --now`, then
   `dc exec backup-ship sh /usr/local/bin/ship.sh --now`.
4. Place a test order from the app on a real phone, then cancel it.

## 7. Updates

Tag a new version, wait for the Release workflow, then run
`./infra/deploy.sh vX.Y.Z` on the server (or start the Deploy workflow, below).

Migrations only move forward. To roll back a release that added none, deploy
the previous tag. If it did add migrations, restore the backup `deploy.sh` took
just before (`docs/RUNBOOK.md`), then deploy the previous tag.

## 8. The Deploy workflow (disabled)

`.github/workflows/deploy.yml` runs `infra/deploy.sh` over SSH. It only runs
when started by hand, and only after the owner sets it up:

1. Add the repository variable `DEPLOY_ENABLED` = `true`.
2. Create the environment `production` with required reviewers.
3. Add these secrets to that environment:

   | Secret | Value |
   | --- | --- |
   | `DEPLOY_HOST` | The server's address |
   | `DEPLOY_USER` | `deploy` |
   | `DEPLOY_SSH_KEY` | A private key used only for deploys; its public key goes in the server's `authorized_keys` |
   | `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan <host>`, checked against the server |
   | `DEPLOY_PATH` | Optional, defaults to `/opt/kitaabondemand` |

Then use Actions, Deploy, Run workflow, and give the version.

## Moving to ECS and RDS

The images and settings carry over unchanged. Only where things run changes.

- **Database**: RDS for PostgreSQL 16 in the same region, Multi-AZ when
  traffic justifies it. Set `DATABASE_URL` to the RDS endpoint with
  `?sslmode=require`. RDS backups and snapshots replace the `backup` and
  `backup-ship` services; leave `BACKUP_S3_BUCKET` empty. Keep
  `WEB_CONCURRENCY × THREADPOOL_SIZE` per task, summed over tasks plus 20,
  below the instance's `max_connections` (`docs/PERF.md`).
- **Redis**: ElastiCache for Redis, or keep one Redis task.
- **Compute**: ECS on Fargate, one service each for api, worker and web, and
  exactly one beat task, because two would schedule every job twice. Run
  migrate as a one-off task before each deploy and wait for it to succeed.
  ClamAV runs as its own service, reached at `CLAMAV_HOST`.
- **Traffic**: an Application Load Balancer with an ACM certificate replaces
  Caddy. Route the API name to the api service (health check `/readyz`) and
  the portal name to web (health check `/`).
- **Secrets**: keep settings in Systems Manager Parameter Store or Secrets
  Manager and pass them as task environment variables. Give the tasks a task
  role with the Terraform storage policy instead of access keys. Mount the
  Firebase file from Secrets Manager.
- **Logs**: the JSON logs go to CloudWatch through the `awslogs` driver.
