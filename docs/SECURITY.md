# Security

How the platform protects accounts, files and money, and what the Phase 6
review checked. Re-run the checks before each release (`docs/RUNBOOK.md`).

## Sign-in

| Who | How | Protections |
| --- | --- | --- |
| Customers | Phone OTP (6 digits) | Codes stored as peppered HMAC, valid 5 minutes, 5 attempts, a new code cancels the old one, 60 s resend cooldown, 10 codes per phone per day, 30 requests per IP per hour |
| Customers | Google Sign-In | ID token checked by the official `google-auth` library, audience and issuer verified; a phone must still be verified before ordering |
| Admins | Email, password and TOTP | Argon2 password hashes, TOTP mandatory, TOTP secrets encrypted at rest (`DATA_ENCRYPTION_KEY`), lockout after 5 failures for 15 minutes, 30 attempts per IP per 15 minutes, unknown email and wrong password look identical |
| Vendors | Email and password | Same as admins without TOTP; a login works only while linked to an active vendor |

Access tokens are JWTs that last 15 minutes. Refresh tokens are random and
stored hashed. They rotate on every use, and reusing an old one revokes the
whole session family (stolen-token detection). Disabling a staff member or
deleting an account revokes their sessions at once. The store-review demo
account needs explicit flags in production (D-020).

## Authorisation

Every route declares exactly one guard: public, any signed-in user, customer,
admin or vendor. `tests/test_authz_matrix.py` checks that:

- each of the 108 routes has the guard its area requires (50 admin, 25
  customer, 6 vendor, 3 any user, 12 public, 12 unguarded: health checks,
  static legal text, and development helpers that production never mounts);
- every protected route refuses a request without a token (401) and a request
  from each wrong role (403), and does not refuse the right role.

Inside a role, ownership is checked on every lookup. Another customer's order,
upload or address answers 404, so ids cannot be probed. Vendors see only the
orders assigned to them, and never the customer's price breakdown.

## Files

- Phones upload straight to S3 through presigned part URLs. The server checks
  each file: size at four points, the `%PDF-` header, a libmagic MIME sniff,
  ClamAV (required in production), pikepdf parsing, and refusal of encrypted
  files, scripts, launch actions and attachments. Rejected files are deleted
  at once.
- Admins and vendors download through 5-minute presigned links. Every link
  issued is written to the audit log.
- The bucket blocks public access and is encrypted (Terraform). Files are
  purged 7 days after delivery or cancellation, after 24 hours if never
  ordered, and at once for deleted accounts (D-016, D-019).

## Money

- Prices are always recomputed on the server. An order is refused if the
  total differs from what the customer saw.
- Payment and courier webhooks are verified by signature, refused if stale,
  and processed once per event id. A payment that arrives after an order
  closed is refunded (D-043).
- The ledger is append-only, enforced by a database trigger.

## Requests and responses

- JSON bodies are capped at 1 MB (413).
- Errors are RFC 7807 problems. Unexpected errors never return internals.
- API responses send `Content-Security-Policy: default-src 'none'`,
  `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer` and
  `Cache-Control: no-store`, plus HSTS in production. The portal has its own
  CSP (`infra/caddy/web.Caddyfile`).
- CORS allows only the configured portal origins.
- Production refuses to start with debug, development tools, mock providers,
  default or short secrets, wildcard origins, plain-HTTP URLs or ClamAV off
  (`kitaab/config.py`).

## Personal data in logs

Logs are JSON. Phone numbers and email addresses are masked by a filter on
every record. Request logs record the path only, because query strings can
carry phone numbers in admin search. Caddy keeps no access log.

Review (9 October 2026): after the end-to-end scenarios and load tests, all
62,000 lines from the API, worker, beat and portal containers were searched
for phone numbers, email addresses, JWTs, signed storage URLs and OTP messages.
None were found. The only phone-shaped matches were request ids.

## The Android app

Tokens are kept in `flutter_secure_storage` (Android Keystore-backed), and app
data is excluded from backups. Plain HTTP is allowed only in the dev flavor.
Card details never reach the app or the server: payment uses the gateway's
hosted page.

## Dependency audits (9 October 2026)

| Project | Check | Result |
| --- | --- | --- |
| API | `make api-audit` (pip-audit, runtime dependencies) | No known vulnerabilities |
| Portal | `make web-audit` (npm audit, production dependencies, high and above) | 0 vulnerabilities |
| Android app | `make mobile-audit` (pub outdated) | Every direct dependency at its latest version; none discontinued |

CI runs all three on every push.

## Before launch

- Turn on ClamAV (`CLAMAV_ENABLED=true`; production requires it).
- Real payment gateways and couriers must verify their webhooks with the
  signature scheme in the provider's documentation (`docs/INTEGRATIONS.md`).
- Generate fresh secrets (`docs/DEPLOY.md`) and keep them out of git.
- Leave Sentry's `send_default_pii` off (it is off in code).
