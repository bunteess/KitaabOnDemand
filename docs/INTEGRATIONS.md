# Integrations

Every third-party service sits behind a small interface in
`services/api/src/kitaab/providers/`. Development and tests use mocks that
behave like the real thing: hosted pages, signed webhooks, delays and failures.

A real adapter is written only from official documentation that the owner
places in `docs/integrations/<provider>/` (see the README there). Until then
the adapter is a skeleton that raises `NotConfigured`, so nothing guesses at an
endpoint, field or error code. Production refuses to start with any mock
provider enabled (`kitaab/config.py`).

## Status

| Service | Interface | Status | Development | Production setting |
| --- | --- | --- | --- | --- |
| SMS (OTP, fallback alerts) | `SmsProvider.send` | Skeleton until a gateway is chosen | `mock`: outbox in Redis, `GET /api/v1/_dev/sms-outbox` | `SMS_PROVIDER=<code>` |
| Easypaisa | `PaymentProvider` | Skeleton | `mock` hosted checkout | `PAYMENT_PROVIDERS=easypaisa,...` |
| JazzCash | `PaymentProvider` | Skeleton | `mock` hosted checkout | `PAYMENT_PROVIDERS=jazzcash,...` |
| Card gateway | `PaymentProvider` | Skeleton (gateway not chosen) | `mock` hosted checkout | `PAYMENT_PROVIDERS=card,...` |
| Trax, Leopards, TCS | `CourierProvider` | Skeleton | `mock` courier with tracking page and webhooks | `COURIER_PROVIDERS=trax,leopards,tcs` |
| Any other courier | `ManualCourier` | Works now: the admin types the CN | same | always available |
| Push (FCM) | `PushProvider` | **UNVERIFIED**: built on the official `firebase-admin` SDK, not yet tried with a real project | `fake`: outbox in Redis, `GET /api/v1/_dev/push-outbox` | `PUSH_PROVIDER=fcm`, `FCM_CREDENTIALS_FILE` |
| Google Sign-In | `IdTokenVerifier` | **UNVERIFIED**: built on the official `google-auth` library, not yet tried with real client IDs | fake tokens `fake-google-<id>` | `GOOGLE_OAUTH_CLIENT_IDS` |
| Object storage | `ObjectStore` | Verified against MinIO; AWS S3 bucket settings come from Terraform | MinIO in compose | `S3_BUCKET`, `S3_REGION`, IAM role |
| Virus scanning | `VirusScanner` | Speaks clamd's documented INSTREAM protocol; tested against a protocol fake | off, or `docker compose --profile clamav up` | `CLAMAV_ENABLED=true`, `CLAMAV_HOST` |
| Error reporting | Sentry SDK | Optional | off | `SENTRY_DSN` |

Sign in with Apple and APNs are deferred with iOS (D-002).

## How the mocks behave

- **Payments.** `create_checkout` returns a URL on our own server,
  `/mock/payments/{ref}`, with Pay and Decline buttons. Pressing one makes the
  mock post an HMAC-signed webhook to `/api/v1/webhooks/payments/mock`, through
  the same job queue a real gateway's retry would use. Refunds succeed with a
  `mockrefund_` reference.
- **Couriers.** Booking returns a `MOCK-NNNNNN` consignment number and a
  tracking page at `/mock/couriers/track/{cn}`. Move a parcel with
  `POST /api/v1/_dev/mock-courier/{cn}/events` and a body such as
  `{"state": "DELIVERED"}`. The mock then posts a signed webhook to
  `/api/v1/webhooks/couriers/mock`.
- **Failures and delays.** `MOCK_PROVIDER_FAILURE_RATE` (0 to 1) makes that
  share of checkout, refund and booking calls fail. `MOCK_PROVIDER_LATENCY_MS`
  adds a random delay around that value. Compose sets 150 ms by default.
- **Signatures.** Mock webhooks carry `x-mock-signature` (HMAC-SHA256 of
  `timestamp.body` with `MOCK_WEBHOOK_SECRET`) and `x-mock-timestamp`, and are
  refused more than five minutes out. A real adapter must verify its
  gateway's own documented signature instead.

## Webhooks

| Path | Used by |
| --- | --- |
| `POST /api/v1/webhooks/payments/{provider}` | Payment gateways |
| `POST /api/v1/webhooks/couriers/{provider}` | Couriers that push status updates |

Both are public, verify the signature first (`401 invalid-signature`
otherwise), and are idempotent: each event id is recorded in `webhook_events`,
and repeats return 200 without changing anything. A payment that arrives after
we closed the attempt is placed or refunded, never ignored (D-043). Couriers
without webhooks are polled every 30 minutes by `poll_courier_status`.

## Adding a real adapter

1. The owner places the provider's official API documentation (PDF, HTML
   export or a link file with the version and date) and sandbox credentials in
   `docs/integrations/<provider>/`. Credentials go in the environment, never in
   git.
2. Implement the interface in the matching module (`payment.py`, `courier.py`
   or `sms.py`), using only endpoints, fields, signatures and error codes the
   documentation shows. Cite the document and section in the docstring.
3. Register it in `build_payments`, `build_couriers` or `build_sms` in place of
   the skeleton.
4. Add tests that replay the documented request and response examples,
   including the signature check, through a fake HTTP transport. Tests never
   call the real service.
5. Try it against the provider's sandbox, then change its status here from
   Skeleton to Verified, with the date.

## Configuration

Every setting is listed with its development default in
`services/api/.env.example`. The compose stack's own knobs are in
`infra/.env.example`, and the portal's in `apps/web/.env.example`. The Android
app reads its settings at build time from `apps/mobile/config/<flavor>.json`
(passed with `--dart-define-from-file`). Those files hold only public values,
such as the API URL and the Firebase Android app identifiers, which the owner
fills in (D-024).
