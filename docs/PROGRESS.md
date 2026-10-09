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

### Phase 3: Integrations (2026-10-09)

- `docs/INTEGRATIONS.md`: every provider's interface, status, mock behaviour,
  settings and the steps to add a real adapter. Real gateways, couriers and
  the SMS gateway stay skeletons that raise `NotConfigured` until the owner
  places official documentation in `docs/integrations/<provider>/` (README
  there). FCM and Google Sign-In are built on the official SDKs and marked
  UNVERIFIED until tried with the owner's projects.
- Mocks behave like real providers: hosted checkout page, consignment numbers,
  tracking page, HMAC-signed webhooks through the job queue, configurable
  failure rate and latency. Webhook signature checks and idempotency are
  covered by the Phase 2 tests; courier polling is tested with a polling-only
  courier.
- `.env.example` files for the API (every setting, kept in sync by a test),
  the compose stack and the portal. `make api-dev` reads `services/api/.env`,
  or the example when there is none.

### Phase 4: Android app (2026-10-09)

- Checked against the real server: every recorded response in
  `packages/contracts/examples` parses with the app's models (D-047).
- Push notifications: Firebase when configured, token registration and
  removal, refresh on arrival, open the order on tap (D-046). Android channel
  "Order updates".
- Deep links `kitaab://app/orders/{id}` and
  `kitaab://app/payment-result?order={id}` (the mock checkout's return link).
- Android manifest fixed for release builds: the main manifest lacked the
  INTERNET permission (only debug builds had it). Also added the notification
  permission, package visibility for checkout, phone and email links,
  cleartext HTTP only in the dev flavor, and no backups of the token store.
- An interrupted upload keeps the customer's paper, binding and copies, and
  resuming restores them.
- Layout fixes found by running tests at phone size (D-048).
- Tests: 100 (up from 82). New flow tests cover a COD print order from
  picking the PDF to tracking, a resumed upload, a book request whose quote
  arrives by push, opening an order from a notification, and sign-out
  unregistering the device. The same flows run on an Android emulator in CI
  (`make mobile-integration`, job "Android emulator").
- README: running the app on the emulator against the local stack.

### Phase 5: Web portal (2026-10-09)

- Playwright end-to-end tests against the full Docker stack with mock
  providers (`make demo && make web-e2e`, CI job "End-to-end"). A customer
  created through the API orders a print and requests a book. The admin signs
  in with password and TOTP, reviews the file, opens the signed PDF link and
  assigns the vendor. The vendor downloads the packing slip and prints. The
  admin books the mock courier, and delivery arrives by signed webhook. The
  COD remittance completes the order. The admin quotes the book request,
  every admin page loads without errors, and the vendor is kept out of the
  admin area.
- Bugs found by the first full-stack run and fixed: libmagic could not find
  its database in the image, so every upload stayed "checking" (D-033 update,
  plus an image smoke check); a validation job that failed left the upload
  waiting forever (D-049); portal search only looked in the open tab (D-050).

### Phase 6: Hardening (2026-10-09)

- `make e2e`: full-stack scenarios over HTTP with mock providers. A 20 MB PDF
  is uploaded in three parts, ordered with cash on delivery, reviewed,
  assigned, downloaded by the vendor (SHA-256 checked) and printed, then
  dispatched with the mock courier and delivered by webhook. Six days later
  the file is still there; seven days later the purge has deleted it and the
  order is intact. A book request is quoted, paid on the mock hosted checkout,
  sourced and completed. CI runs these with the Playwright suite.
- Load test (`make load`, docs/PERF.md). The first run collapsed at 300 users
  because requests held database connections while waiting for threads; fixed
  (D-051). Now: 179 requests/s at 300 users with p95 72 ms, and 242
  requests/s at 800 users with no errors.
- Security review (docs/SECURITY.md): authorisation matrix over all 108
  routes, sign-in protections, file and money controls, and a personal-data
  log review (none found in 62,000 lines). Dependency audits are clean for the
  API and portal, and every app dependency is current.
- The end-to-end and load test code is linted with the API's rules.

## Next

- Phase 7: Release readiness.

## Known limitations of the build environment

- No Android SDK in the build sandbox (`dl.google.com` is blocked), so the
  release AAB and emulator tests run only in CI (D-006).
- Docker Hub rate-limits the sandbox, so local builds use
  `DOCKER_REGISTRY=mirror.gcr.io` (D-005).
