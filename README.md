# KitaabOnDemand

Book sourcing and print-on-demand for Pakistan. Customers either ask us to find
a book (**SOURCE**) or upload a PDF to be printed and bound (**PRINT**). Admins
review, quote and dispatch orders. Print vendors receive their queue, download
files and print packing slips.

| Part | Path | Stack |
|---|---|---|
| Customer app (Android) | `apps/mobile` | Flutter, Riverpod, go_router, dio |
| Admin and vendor portal | `apps/web` | React, TypeScript, Vite, TanStack Query, Tailwind |
| API, worker, scheduler | `services/api` | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, Redis |
| Shared contracts | `packages/contracts` | OpenAPI export, pricing test vectors |
| Infrastructure | `infra` | Docker, Compose, Caddy, Terraform |
| Docs | `docs` | Architecture, decisions, runbooks |

## Quick start

Needs Docker, [uv](https://docs.astral.sh/uv/), Node 24 (npm 11) and Flutter
3.47.

```bash
make demo        # build and start the stack with mock providers, load demo data
open http://localhost:8080          # admin and vendor portal
open http://localhost:8000/docs     # API docs
make down
```

Everyday commands:

```bash
make help        # every target
make deps-up     # Postgres, Redis and MinIO only
make api-dev     # API on the host with auto-reload
make test        # all unit and integration tests
make verify      # lint, type checks, tests, contract checks and builds (what CI runs)
make e2e         # full-stack end-to-end scenarios with mock providers
```

Run the Android app against the local API on the emulator. The phone reaches
the host as `10.0.2.2`, so links the API hands out (upload URLs, the mock
checkout page) must use that address too:

```bash
printf 'PUBLIC_BASE_URL=http://10.0.2.2:8000\nS3_PUBLIC_ENDPOINT_URL=http://10.0.2.2:9000\n' > infra/.env
make up && make seed
cd apps/mobile
flutter run --flavor dev --dart-define-from-file=config/dev.json
```

Sign in with any 03XX number; the code is at
`http://localhost:8000/api/v1/_dev/sms-outbox`. For a real phone on the same
Wi-Fi, use the computer's LAN address in `infra/.env` and in
`apps/mobile/config/dev.json`. To click through the app without a server, add
`--dart-define=MOCK_API=true`. The customer flows also run on an emulator with
`make mobile-integration`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): components, data model, state machines, pricing, upload pipeline
- [Decisions](docs/DECISIONS.md): every decision and assumption, with reasons
- [Progress](docs/PROGRESS.md): what is done and what is next
- [Owner to-do](docs/OWNER_TODO.md): accounts, credentials and content only the owner can supply
- [Integrations](docs/INTEGRATIONS.md): provider adapters and their verification status
- [Screens](docs/design/screens.md): screen inventory and navigation for designers
- [Performance](docs/PERF.md), [Deploy](docs/DEPLOY.md), [Runbook](docs/RUNBOOK.md), [Mobile release](docs/RELEASE_MOBILE.md)

## Ground rules

- Money is integer paisa. Display as `Rs. 1,250`.
- Times are stored in UTC and shown in Pakistan time.
- No secrets in git. Copy `.env.example` files and fill them in.
- Tests never call real third-party services.
