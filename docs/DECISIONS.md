# Decisions

Each entry gives the decision, the reason and the date. Entries marked
**conflict** record where the brief overrides or departs from another source.
Entries marked **proposed** are ideas that are written down but not built.

## D-001 · The brief is the specification while the PRD is missing · 2026-10-09

`docs/PRD.md` was not in the repository and could not be found elsewhere. The
build brief is detailed enough to build from, so work goes ahead on the brief
alone. Anything the PRD would normally settle is logged here as an assumption.
When the owner adds the PRD, each assumption must be checked against it (see
`OWNER_TODO.md`).

## D-002 · Android only for the first release · 2026-10-09

The owner asked to build for Android only at this stage. Not built yet: the
iOS platform folder, Sign in with Apple (mobile and backend), APNs, the iOS
CI workflow and the TestFlight steps. The backend keeps an `IdTokenVerifier`
interface so an Apple verifier can be added later.

Before an iOS release, App Store Review Guideline 4.8 requires Sign in with
Apple (or an equivalent privacy-focused login) because the app offers Google
sign-in.

## D-003 · Python dependencies managed with uv · 2026-10-09

`uv` gives a single lock file (`uv.lock`), fast installs in CI and Docker, and
pins the Python version. Plain `pip install -e .` still works from
`pyproject.toml`.

## D-004 · MinIO is built from pinned source · 2026-10-09

The brief specifies MinIO for local storage. MinIO no longer publishes
container images, and the `minio/minio` Docker Hub repository no longer
exists. `infra/docker/minio/Dockerfile` builds a pinned commit
(`v0.0.0-20260212201848-7aac2a2c5b7c`) from the Go module proxy. The first
build takes a few minutes, then Docker caches it. If this becomes a burden,
any S3-compatible server can replace it, because the app only uses the S3 API
through boto3.

## D-005 · Container registry is configurable · 2026-10-09

Docker Hub rate-limits anonymous pulls from the build sandbox. Every image and
base image reference starts with `${DOCKER_REGISTRY:-docker.io}` so a mirror
can be used (`DOCKER_REGISTRY=mirror.gcr.io`). CI uses Docker Hub.

## D-006 · Android builds and emulator tests run in CI · 2026-10-09

The build sandbox blocks `dl.google.com`, so it has no Android SDK. Flutter
analysis, unit tests and widget tests run everywhere. The release AAB build and
the `integration_test` run on an emulator happen in GitHub Actions, which has
the SDK. `make verify` builds the AAB when an Android SDK is present and
otherwise prints `SKIPPED`. With `STRICT=1` (set in CI) a missing SDK fails the
build. The integration test flows also run as widget tests against the mock API
so they are checked on every machine.

## D-007 · Optional CA certificate for Docker builds · 2026-10-09

Builds behind a TLS-intercepting proxy need the proxy's CA inside the build
container. Each Dockerfile accepts an optional BuildKit secret `build_ca`. If
it is absent nothing changes. Copy the CA to `infra/docker/.build-ca.crt` (git-ignored) and set
`BUILD_CA_FILE=./docker/.build-ca.crt`. The file must be inside the repository
because `docker buildx bake` only reads files under the working directory.

## D-008 · Typed web client from the OpenAPI file · 2026-10-09

`openapi-typescript` generates types from `packages/contracts/openapi.json` and
`openapi-fetch` provides a small typed client. Both are small, with no runtime
code generation. A check fails if the generated file is stale.

## D-009 · Hand-written Dart client with a contract test · 2026-10-09

Dart OpenAPI generators produce large, hard-to-read code. The mobile client is
hand-written. A test reads `openapi.json` and checks that every path and
method the client calls exists in the contract.

## D-010 · Synchronous SQLAlchemy · 2026-10-09

Large uploads go straight to S3 by presigned URL, so the API never streams file
bodies. Sync SQLAlchemy 2 with psycopg 3 is simpler to write, test and debug,
and the same code runs in Celery workers. FastAPI runs sync endpoints in a
thread pool.

## D-011 · `PENDING_PAYMENT` state before `PLACED` · 2026-10-09

The brief requires digital payment to complete before a PRINT order becomes
`PLACED`. The order needs to exist while the customer is on the hosted
checkout page, so PRINT orders paid digitally start in `PENDING_PAYMENT`. A
paid webhook moves them to `PLACED`. Unpaid orders are cancelled after 24 hours
(`PENDING_PAYMENT_TTL_HOURS`). COD orders start in `PLACED`.

SOURCE orders choose payment when the quote is accepted. A digital payment then
stays `PENDING` while the order is `ACCEPTED`, and the admin cannot start
sourcing until it is `PAID`.

## D-012 · PRINT review actions · 2026-10-09

The brief says "approve (moves to VERIFYING then assignment)" and also
"REJECTED (admin, from VERIFYING)". So that both hold:
- **Start verification** moves `PLACED` to `VERIFYING`.
- **Approve and assign** picks the vendor and cost and moves `VERIFYING` to
  `ASSIGNED`.
- **Reject** is available in `VERIFYING`.

## D-013 · `DELIVERED` shows as "Completed" to the customer · 2026-10-09

The timeline's last step is "Completed". Internally `COMPLETED` waits for
payment settlement (COD cash remitted), which the customer neither knows nor
cares about. Both `DELIVERED` and `COMPLETED` show as the "Completed" step.

## D-014 · Volume brackets keyed on printed pages · 2026-10-09

The brief asks for optional volume brackets on the per-page rate without
saying what "volume" means. Brackets are keyed on printed pages
(`pages * copies`), so a 300-page book in 3 copies prices like 900 printed
pages. The owner should confirm (see `OWNER_TODO.md`).

## D-015 · Vendor cost accrued at "Ready for dispatch" · 2026-10-09

The agreed vendor cost is recorded on the order at assignment, as the brief
requires. The `VENDOR_COST_ACCRUED` ledger entry is written when the vendor
finishes (`READY_FOR_DISPATCH`), so an order cancelled before printing does
not create a payable. If the owner wants to pay vendors for cancelled work in
progress, an admin can add a manual accrual (proposed, not built).

## D-016 · Purging files of cancelled and rejected orders · 2026-10-09

As the brief asks, this is logged as an assumption: PDFs of `CANCELLED` and
`REJECTED` orders are purged `PURGE_DAYS` (default 7) after the order reached
that state. Unattached uploads are purged 24 hours after creation.

## D-017 · Revenue recognition · 2026-10-09

A `REVENUE` entry is written when a digital payment becomes `PAID`, and when
the courier collects COD on delivery, alongside `COD_COLLECTED`. Refunds are
`REFUND` entries when processed. The daily revenue panel shows gross revenue,
refunds and net by date and payment method.

## D-018 · Times shown at fixed UTC+05:00 · 2026-10-09

Times are stored in UTC. Pakistan Standard Time is UTC+05:00 and has had no
daylight saving since 2009. The app adds a fixed five-hour offset rather than
bundling a time zone database. The web portal uses `Intl` with
`Asia/Karachi`.

## D-019 · Account deletion with orders in progress · 2026-10-09

Deleting an account at once removes the profile, phone, Google link,
addresses, devices, notifications and every uploaded file not needed by an
in-flight order. Orders that can still be cancelled are cancelled, with refund
records created for paid ones. Orders past the cancellation point keep their
shipping details and file until they reach a terminal state. The hourly purge
job then removes the shipping details, and the file once its normal purge time
comes. Financial records are kept but no longer linked to any personal data.

## D-020 · Review mode in production (conflict) · 2026-10-09

Section 3.4 needs a reviewer demo account (`REVIEW_MODE_ENABLED=true`).
Section 10 says production must refuse to start with review mode on. Store
review runs against the production build, so both cannot hold literally.
Production refuses review mode unless `ALLOW_REVIEW_MODE_IN_PRODUCTION=true`
is also set. That second flag is turned on only for the store review window and
logged loudly at startup. Orders from the review account are flagged in the
admin panel so they are not fulfilled.

## D-021 · Rupee formatting · 2026-10-09

Amounts are shown as `Rs. 1,250` with Western digit grouping (`Rs. 1,250,000`),
which matches the brief's example and common English-language receipts in
Pakistan. Paisa are shown only when non-zero (`Rs. 12.50`). Python and Dart run
the same formatting test vectors.

## D-022 · SOURCE requests include the delivery address · 2026-10-09

A quote must show the full price, and the delivery fee depends on the city's
zone. So the customer chooses a delivery address when requesting a book. The
payment method (and so any COD fee) is chosen when the quote is accepted.

## D-023 · SOURCE quote pricing · 2026-10-09

The proposed goods price for a SOURCE quote is
`ceil_to_rupee((pages * rate + binding) * copies + sourcing_cost)`. The admin
may override the goods price with a reason. Delivery and COD fees always come
from the pricing config. Whether to add a margin on sourcing cost is for the
owner to decide (see `OWNER_TODO.md`).

## D-024 · Firebase set up from build-time values · 2026-10-09

The app calls `Firebase.initializeApp` with options passed through
`--dart-define-from-file`, so no `google-services.json` is committed or needed
to build. If the values are missing (development), push is disabled and the
app falls back to polling.

## D-025 · Local PDF page count with `pdfx` · 2026-10-09

`pdfx` (MIT licence) uses Android's built-in `PdfRenderer`, so it adds no
PDFium binary and keeps the app small. `pdfrx` (MIT) was rejected because it
bundles PDFium for every ABI, which would threaten the 25 MB budget. If the
file is encrypted or cannot be opened, the app shows a manual page count field
and relies on the server's count.

## D-026 · Delivery failures are not refunded automatically · 2026-10-09

`DELIVERY_FAILED` does not create a refund record, because whether to refund,
re-deliver or charge for returns is a business policy. Admins can create a
manual refund. Recorded in `OWNER_TODO.md`.

## D-027 · Proposed: re-dispatch after a failed delivery · 2026-10-09

**Proposed, not built.** `DELIVERY_FAILED` is terminal in the MVP. A
`DELIVERY_FAILED → READY_FOR_DISPATCH` transition for re-delivery would be
useful.

## D-028 · Ledger immutability enforced in the database · 2026-10-09

A trigger on `ledger_entries` rejects `UPDATE` and `DELETE`, so no code path,
admin script or bug can rewrite financial history. Corrections are new
entries.

## D-029 · Google ID tokens verified with the official library · 2026-10-09

The backend verifies Google ID tokens with the `google-auth` library's
`id_token.verify_oauth2_token`, checking the audience against
`GOOGLE_OAUTH_CLIENT_IDS`. It is marked `UNVERIFIED` until tested with the
owner's OAuth client.

## D-030 · COD payments are recorded as payments · 2026-10-09

Every order that has a price gets a `payments` row. COD payments stay `PENDING`
until the admin marks the courier's cash as remitted, then become `PAID`. This
makes "payment settled" the same check for every method.

## D-031 · E2E and load tests live in `/tests` · 2026-10-09

The full-stack scenarios touch the API, worker, storage and mock providers, so
they live in `tests/e2e` (pytest over HTTP) rather than inside one app. Load
scripts live in `tests/load` (Locust). Playwright tests for the portal stay in
`apps/web/e2e`.

## D-032 · Locust for load tests · 2026-10-09

The brief allows k6 or Locust. Locust is Python, installs from PyPI like the
rest of the backend tooling, and can reuse the e2e helpers.

## D-033 · libmagic copied into the API image · 2026-10-09

`python-magic` needs the `libmagic` C library, which the slim Python image
lacks. Instead of installing it with `apt`, the API Dockerfile copies
`libmagic.so.1` and `magic.mgc` from the full `python:3.12-trixie` image of the
same Debian release. This keeps the build working where Debian mirrors are not
reachable (as in the build sandbox) and keeps the runtime image slim.

## D-034 · Node 24 and npm 11 for the web portal · 2026-10-09

npm 10 crashes while resolving some peer dependencies of the test tooling.
npm 11, bundled with Node 24 LTS, does not. The web Dockerfile and CI use Node
24. `package.json` requires npm 11 or later.

## D-035 · TypeScript 5.9 · 2026-10-09

TypeScript 7 (the native compiler) is current, but `typescript-eslint` supports
only versions below 6.1 and `openapi-typescript` requires 5.x. The portal uses
TypeScript 5.9 until the tooling catches up.
