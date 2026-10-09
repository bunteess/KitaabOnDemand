# Progress

Updated at the end of every phase. See `docs/DECISIONS.md` for the reasoning
behind each choice.

## Done

### Phase 0: Foundations (2026-10-09)

- Plan, assumptions and known owner inputs posted. Written up in
  `ARCHITECTURE.md` (components, ERD, both state machine tables, timeline
  mapping, pricing formula, upload pipeline, jobs, purge, assumptions),
  `DECISIONS.md` and `OWNER_TODO.md`.
- Monorepo scaffold: `services/api` (FastAPI, uv, ruff, mypy strict, pytest),
  `apps/web` (Vite, React 19, TypeScript 5.9, Tailwind 4, Vitest, ESLint,
  Prettier), `apps/mobile` (Flutter 3.47.7, Android only, dev, staging and prod
  flavors), `packages/contracts` (OpenAPI export with drift check).
- Compose stack: Postgres 16, Redis 7, MinIO (built from pinned source), an
  optional ClamAV profile, and API, worker, beat, migrate and web services.
- Multi-stage, non-root Dockerfiles for API, worker, beat, web and MinIO.
- `Makefile` with up, down, seed, lint, test, e2e, demo, verify.
- GitHub Actions CI running the same targets.

### Phase 1: Contracts and screens (2026-10-09)

- `docs/design/screens.md`: every app and portal screen with its fields,
  states, navigation map and the packing slip layout.
- OpenAPI contract: 87 paths with final request and response models
  (`packages/contracts/openapi.json`). Handlers return 501 until Phase 2
  (D-038). The typed web client is generated from it, and the Dart client is
  checked against it by test.
- `packages/contracts/pricing_vectors.json`: 17 hand-worked pricing cases, 9
  money-format cases and 11 phone cases. Python and Dart run them all and
  agree.
- Pricing engine in Python and Dart, phone normalisation and money formatting.
- Android app (Flutter): theme, 275 English strings in ARB with an Urdu stub,
  router with session redirects and deep-link paths, and every screen in
  `screens.md`. Also a typed API client with token refresh, a resumable
  multipart uploader and an in-memory fake API. Tests: 82 (vectors, contract,
  routing, OTP sign-in smoke flows).
- Web portal: Tailwind theme, role-gated admin and vendor areas with every
  screen in `screens.md`, a typed client with refresh, and an in-memory mock
  API. Tests: 51 (87% line coverage).

### Phase 2: Backend core (2026-10-09)

- Every contract endpoint implemented: phone OTP and Google sign-in, staff
  login with lockout and mandatory admin TOTP, rotating refresh tokens with
  reuse detection, profile, terms, addresses and devices.
- Uploads: presigned multipart uploads to object storage with resume, size
  enforced at four points, and a validation job (magic bytes, MIME sniff,
  optional ClamAV, pikepdf open, encryption, page count, scripts and
  attachments). Rejected files are deleted at once.
- Orders: the state machine table with side effects, both order types, server
  pricing with a price check against what the customer saw, COD limit, quotes
  with expiry, the mock hosted checkout and signed idempotent webhooks,
  refunds, dispatch through the mock courier or a typed CN, courier webhooks
  and polling, and the customer timeline.
- Admin and vendor APIs, packing slips (PDF), audit log, notifications (inbox,
  push, optional SMS fallback), the append-only ledger with daily revenue,
  COD reconciliation, vendor payouts and CSV exports.
- Purge job (delivered and exited orders after seven days, abandoned uploads
  after a day, deleted accounts' data once their orders finish), account
  deletion, and the operations CLI.
- Bugs found by the new tests and fixed: late gateway payments were ignored
  (D-043), history order was ambiguous within one transaction (D-044), tokens
  failed when the clock moved ahead (D-045), and chunked bodies over 1 MB got
  a 500 instead of 413.
- Tests: 326 backend tests against real Postgres, Redis and MinIO, with fakes
  for SMS, push, payments and couriers and a frozen clock. They cover every
  legal and illegal state transition, OTP, quotes, purge, ledger arithmetic,
  PDF fixtures generated in code, webhook signatures and idempotency, an
  authorisation matrix over every route and role, and Alembic upgrade,
  downgrade and drift. Coverage: 96% overall, 94% on domain modules.

## Next

- Phase 3: Integrations.
- Phase 4: Android app.
- Phase 5: Web portal.
- Phase 6: Hardening.
- Phase 7: Release readiness.

## Known limitations of the build environment

- No Android SDK in the build sandbox (`dl.google.com` is blocked), so the
  release AAB and emulator tests run only in CI (D-006).
- Docker Hub rate-limits the sandbox, so local builds use
  `DOCKER_REGISTRY=mirror.gcr.io` (D-005).
