# Testing on your laptop

How to run the whole platform on your own computer before deploying: the API,
worker, database, file storage and the admin and vendor portal, plus the
Android app on an emulator. Everything runs with **mock providers**. No SMS is
sent, no money moves and no courier is booked: the mocks behave like the real
services and let you read what they would have sent.

Allow about an hour the first time: most of it is installing tools and the
first build.

## 1. What you need

| Tool | Needed for | How to get it |
| --- | --- | --- |
| Docker Desktop (Windows, macOS) or Docker Engine (Linux) | Everything | docker.com. In Settings, Resources, give it at least 6 GB of memory and 20 GB of disk |
| `make`, `git`, `curl`, `unzip` | Running the commands below | Linux and WSL: `sudo apt install make git curl unzip`. macOS: `brew install make` (then type `gmake` wherever this guide says `make`; Apple's own `make` is too old) |
| uv | Automated tests (it installs Python 3.12 by itself) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 24 | Portal tests | nodejs.org, or `nvm install 24` |
| Flutter 3.47.7 and Android Studio | The Android app only (step 6) | flutter.dev and developer.android.com/studio. Android Studio brings the Android SDK and the emulator. `flutter doctor` must show no errors for Android |

**On Windows**, the commands need a Linux shell:

1. Install WSL 2 with Ubuntu (`wsl --install` in an administrator PowerShell)
   and restart.
2. In Docker Desktop, Settings, Resources, WSL integration, turn on Ubuntu.
3. Run every `make` command in the Ubuntu terminal. Run the Flutter commands
   in step 6 in PowerShell, on the same folder.

Steps 2–5 need only Docker, `make`, uv and Node.

## 2. Get the code

Unzip the project, for example to `~/KitaabOnDemand`. On Windows, unzip it to
`C:\KitaabOnDemand`; in the Ubuntu terminal that folder is
`/mnt/c/KitaabOnDemand`.

```bash
cd ~/KitaabOnDemand          # Windows (Ubuntu terminal): cd /mnt/c/KitaabOnDemand
```

Or clone it: `git clone https://github.com/bunteess/KitaabOnDemand.git`.

All commands below run from this folder.

## 3. Start the platform

```bash
make demo
```

This builds the images, starts every service, creates the database, seeds 20
cities, placeholder pricing and two demo logins, and prints them. The first
run takes 5–15 minutes; later runs take seconds.

When it finishes, open these:

| What | Address | Sign in with |
| --- | --- | --- |
| Admin and vendor portal | http://localhost:8080 | Below |
| API reference (try requests in the browser) | http://localhost:8000/docs | |
| API health | http://localhost:8000/readyz | Should show `"status":"ok"` |
| File storage console (MinIO) | http://localhost:9001 | `kitaab-minio` / `kitaab-minio-secret` |
| Text messages the API "sent" | http://localhost:8000/api/v1/_dev/sms-outbox | |
| Push notifications the API "sent" | http://localhost:8000/api/v1/_dev/push-outbox | |

Demo logins:

| Role | Email | Password | Extra |
| --- | --- | --- | --- |
| Admin | `admin@example.com` | `demo-admin-password` | Authenticator code, below |
| Vendor (Demo Print House) | `vendor@example.com` | `demo-vendor-password` | |

Admins need a 6-digit authenticator code. Either add the key
`JBSWY3DPEHPK3PXP` to an authenticator app on your phone (Google Authenticator:
+, Enter a setup key, time based), or print the current code:

```bash
docker compose -f infra/docker-compose.yml exec api python -c "import pyotp; print(pyotp.TOTP('JBSWY3DPEHPK3PXP').now())"
```

A code is valid for about 30 seconds.

## 4. Run the automated tests

These check the same flows a person would, in a few minutes. Run them first:
if they pass, the platform works on your machine.

```bash
E2E_SKIP_STACK=1 make e2e
```

This runs two scenarios against the running platform, about a minute:

- **Print order**: a customer signs in with an SMS code and uploads a 20 MB PDF
  in parts. They order with cash on delivery. The admin reviews and assigns
  the order, and the vendor downloads the exact file, prints the packing slip
  and prints. The mock courier delivers by signed webhook. Six days later the
  file is still stored; seven days later the purge has deleted it.
- **Book request**: a customer asks for a book, the admin quotes, the customer
  pays on the mock checkout page, and the order is sourced and completed.

Then the portal in a real browser (7 tests, under a minute):

```bash
make web-install
(cd apps/web && npx playwright install --with-deps chromium)   # once; on macOS drop --with-deps
make web-e2e
```

And the unit and integration tests, about 5 minutes:

```bash
make api-test web-test     # 339 API tests with coverage gates, 53 portal tests
make mobile-test           # 100 app tests; needs Flutter
```

`make verify` runs everything CI runs, about 25 minutes. Without an Android
SDK it skips the Android bundle build and says so.

## 5. Test the portal by hand

Create fresh orders to work through:

```bash
make sample-orders
```

It prints a customer phone number, a print order code (waiting in **To
verify**) and a book request code (waiting in **To quote**). Run it again
whenever you want more.

**As the admin** (http://localhost:8080, demo admin login):

1. **Orders**, tab **To verify**: open the print order, then press **Start
   verification**.
2. Press **Open PDF** to see the customer's file. It downloads through a link
   that expires after 5 minutes.
3. Choose the **Vendor** (Demo Print House), enter the **Agreed vendor cost
   (Rs.)**, then press **Approve and assign**. The status becomes Assigned.

**As the vendor**: use a private browser window, so both people can be signed
in at once.

4. Sign in with the demo vendor login. Open the order in the **Print queue**.
   The vendor sees the order and the file, but not the customer's price.
5. Press **Packing slip** (a PDF to stick on the parcel), then **Start
   printing**, then **Ready for dispatch**.

**As the admin again:**

6. Open the order (tab **Ready to dispatch**). Choose **Courier: Mock
   Courier**, then press **Book courier and dispatch**. A consignment number
   like `MOCK-123456` appears.
7. Play the courier: tell the mock courier the parcel was delivered, using
   your consignment number:

   ```bash
   curl -X POST http://localhost:8000/api/v1/_dev/mock-courier/MOCK-123456/events \
     -H 'Content-Type: application/json' -d '{"state":"DELIVERED"}'
   ```

   Other states you can send first: `PICKED_UP`, `IN_TRANSIT`,
   `OUT_FOR_DELIVERY`. You can also send `FAILED` instead of `DELIVERED`.
   Reload the order: it shows Delivered, with each step in its history.
8. **COD pending**: tick the order, enter a **Remittance reference** (any
   text), and press **Mark Rs. … remitted**. The order becomes Completed, and
   the money appears under **Revenue**.
9. **To quote**: open the book request. Enter **Pages** and **Sourcing cost
   (Rs.)**, press **Preview price**, then **Send quote**. Without the app,
   step 6 below shows the customer's side.

Also look at **Pricing**, **Cities**, **Vendors** (add one, and give it a
login), **Admins**, **Customers**, **Refunds**, **Vendor payouts** and **Audit
log**: every action above is recorded there. Then sign in as the vendor and
try to open http://localhost:8080/admin; it should refuse.

## 6. Test the Android app on the emulator

1. In Android Studio, open **Device Manager**, create a phone (for example a
   Pixel with Android 14, API 34) and start it.
2. Point the API's links at the emulator. Inside the emulator, your laptop is
   `10.0.2.2`. In the project folder (Ubuntu terminal on Windows):

   ```bash
   printf 'PUBLIC_BASE_URL=http://10.0.2.2:8000\nS3_PUBLIC_ENDPOINT_URL=http://10.0.2.2:9000\n' > infra/.env
   make up
   ```

   While this is set, **Open PDF** in the portal and the automated tests in
   step 4 cannot fetch files. When you finish with the app, delete
   `infra/.env` and run `make up` again.
3. Run the app (PowerShell on Windows, a terminal elsewhere):

   ```bash
   cd apps/mobile
   flutter pub get
   flutter run --flavor dev --dart-define-from-file=config/dev.json
   ```

   The first build takes several minutes. The app appears as "Kitaab Dev".
4. **Sign in** with any number like `03001234567`. Read the code at
   http://localhost:8000/api/v1/_dev/sms-outbox, then accept the terms. Add a
   delivery address under Profile, Addresses, or when the app asks for one at
   your first order.
5. **Print a PDF.** Drag any PDF from your laptop onto the emulator window;
   it lands in the emulator's Downloads. In the app, choose it, then pick
   paper, binding and copies. The price updates as you choose. Order with
   cash on delivery.
6. Work the order through the portal (step 5) and watch the app's order
   screen and inbox update at each step.
7. **Request a book**, quote it in the portal, then pay in the app. The mock
   checkout page opens in the emulator's browser: press **Pay**, then
   **Return to the app**.
8. Also try: turning on airplane mode in the middle of an upload and back off
   (the upload resumes), the inbox, the profile and delete account.

To click through the screens without any server, run the app with mock data:
`flutter run --flavor dev --dart-define-from-file=config/dev.json --dart-define=MOCK_API=true`.

The same customer flows run automatically on an emulator with
`make mobile-integration`.

## 7. Time-based features

Quotes expire, unpaid payments expire, and files are purged 7 days after
delivery. Rather than wait, move the platform's clock forward, then run the
job now instead of on its schedule:

```bash
# 8 days ahead
curl -X POST http://localhost:8000/api/v1/_dev/clock -H 'Content-Type: application/json' \
  -d '{"offset_seconds": 691200}'
# run the purge (also: expire_quotes, expire_pending_payments, poll_courier_status)
curl -X POST http://localhost:8000/api/v1/_dev/jobs/purge_files
# back to the real time
curl -X POST http://localhost:8000/api/v1/_dev/clock -H 'Content-Type: application/json' \
  -d '{"offset_seconds": 0}'
```

After the purge, a delivered order's file is gone from the MinIO console, but
the order and its history remain. The **Audit log** shows a `purge.run`
entry with the counts.

## 8. Stop, restart and reset

```bash
make down                    # stop; your data is kept
make up                      # start again
docker compose -f infra/docker-compose.yml --profile app down -v   # stop and erase all local data
make demo                    # then start fresh with demo data
```

`make logs` follows the API, worker and scheduler logs (Ctrl+C to stop
following).

## 9. Before you deploy: sign-off

| Check | How | Expected |
| --- | --- | --- |
| Platform starts | `make demo`, then http://localhost:8000/readyz | `"status":"ok"` |
| End-to-end scenarios | `E2E_SKIP_STACK=1 make e2e` | 2 passed |
| Portal in a browser | `make web-e2e` | 7 passed |
| Unit and integration tests | `make api-test web-test mobile-test` | All passed, coverage gates met |
| Admin and vendor flow by hand | Step 5 | Order reaches Completed |
| Customer app by hand | Step 6 | Sign-in, upload, order, quote and payment work |
| Purge by hand | Step 7 | File gone, order kept |

The production configuration itself is checked by `make infra-check` and by
CI. `docs/DEPLOY.md` has the first-start checks for the real server.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `port is already allocated` | Something else uses the port, often a local Postgres on 5432. Create `infra/.env` with other ports, for example `POSTGRES_PORT=5433`, `API_PORT=8001`, `WEB_PORT=8081`. If you move Postgres, Redis or MinIO, also set `TEST_DATABASE_URL`, `TEST_REDIS_URL` or `TEST_S3_ENDPOINT_URL` (see the top of the `Makefile`) before running the tests |
| `toomanyrequests` or `429` while building | Docker Hub is rate-limiting you. Run `export DOCKER_REGISTRY=mirror.gcr.io` and try again |
| Builds fail with certificate errors on an office network | The network inspects HTTPS. Copy its CA certificate to `infra/docker/.build-ca.crt` and run `export BUILD_CA_FILE=./docker/.build-ca.crt` (D-005) |
| A service keeps restarting | `docker compose -f infra/docker-compose.yml --profile app logs api` (or `worker`, `web`) shows why. Also check Docker has 6 GB of memory |
| `make: command not found` on macOS, or odd errors | Use `gmake` from `brew install make` |
| `bad interpreter` or `\r` errors on Windows | The files got Windows line endings. Unzip again, or clone with `git config --global core.autocrlf false` |
| Admin sign-in says the code is wrong | Codes change every 30 seconds; print a fresh one. Check your laptop's clock is correct |
| Sign-in is refused as too many attempts | The platform limits sign-ins per address (30 SMS codes an hour, 30 staff attempts per 15 minutes), and repeated test runs reach that. Wait, or clear the limits by emptying Redis (it also forgets queued jobs and the SMS outbox): `docker compose -f infra/docker-compose.yml exec redis redis-cli FLUSHALL` |
| The app cannot reach the API | Check step 6.2 was done before `make up`, and that http://localhost:8000/readyz works on the laptop |
