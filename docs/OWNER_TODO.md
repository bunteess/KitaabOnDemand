# Owner to-do

Things only the owner can supply or do. Each item says what is needed and
where it goes. The code, tests, infrastructure and documents are done up to
the point where real accounts, content and approvals are needed.

## Launch blockers

Production cannot go live until each of these is done.

- [ ] **SMS gateway.** Choose one and open an account. Place its official API
  documentation in `docs/integrations/<provider>/` and supply sandbox
  credentials, so the adapter can be built and verified. Until then,
  customers cannot receive sign-in codes. Google sign-in alone is not enough,
  because a phone must be verified before ordering.
- [ ] **Firebase project** with an Android app for each flavor
  (`pk.kitaabondemand.app`, `.dev`, `.staging`), and Cloud Messaging on.
  - Put the Android app values in `apps/mobile/config/<flavor>.json`.
  - Put a service account JSON on the server at
    `infra/secrets/fcm-service-account.json`. The production API refuses to
    start without it.
- [ ] **AWS**. In your account, run `terraform plan` and then `terraform apply`
  in `infra/terraform` (`docs/DEPLOY.md` step 1). Then create one access key
  each for the `-api` and `-backup` IAM users.
- [ ] **Server, domain and DNS.** A 2 vCPU, 4 GB Lightsail or EC2 server in
  `ap-south-1`, and A records for the API and portal names
  (`docs/DEPLOY.md` steps 2–3).
- [ ] **Production settings.** Fill in `infra/.env.production` from the
  example, with freshly generated secrets (`docs/DEPLOY.md` step 4), and keep
  a copy in a password manager.
- [ ] **Real pricing**: per-page rates for Local White and Imported Yellow
  paper; binding fees for Softcover Paperback and Premium Hardcover; maximum
  pages per binding; any volume brackets; delivery fee per zone; and the COD
  fee. Enter them on the portal's Pricing page. The seeded values are
  placeholders.
- [ ] **Real cities and zones**: the served cities and each city's courier
  zone code (portal, Cities).
- [ ] **Vendors**: each print vendor's name, contact, city and address, and
  the email of each staff member who needs a login (portal, Vendors).
- [ ] **Support contact** shown in the app: phone, WhatsApp, email and hours
  (portal, Settings, and `SUPPORT_*` in `apps/mobile/config/prod.json`).
- [ ] **Legal text**: replace the placeholder terms of service and privacy
  policy, and the copyright declaration shown on PDF upload. Publish the
  privacy policy and an account deletion page at public URLs, which Google
  Play requires.
- [ ] **App name and logo**: the final name, a 1024 × 1024 launcher icon, and
  the store graphics (`docs/RELEASE_MOBILE.md`, store checklist).
- [ ] **Google Play Console** developer account, the upload key
  (`docs/RELEASE_MOBILE.md`), and the first internal test on a real phone
  against production.

## Optional at launch

- [ ] **Payment gateways**: Easypaisa, JazzCash and a card gateway. Each needs
  a merchant account, the official API docs in
  `docs/integrations/<provider>/`, sandbox credentials and webhook secrets.
  Without them the platform takes cash on delivery only.
- [ ] **Couriers**: Trax, Leopards and TCS, whichever you use. Each needs an
  account, the official API docs in `docs/integrations/<provider>/` and API
  keys. Without them, admins type consignment numbers and mark deliveries by
  hand.
- [ ] **Google sign-in**: an OAuth web client ID, and an Android client
  registered with the SHA-1 of both the upload key and Play's app signing
  key. Put the IDs in `GOOGLE_OAUTH_CLIENT_IDS` and `GOOGLE_SERVER_CLIENT_ID`.
  Phone sign-in works without it.
- [ ] **Sentry** project and DSN, for error reports.
- [ ] **Deploy workflow**: set it up only if you want deploys from GitHub
  (`docs/DEPLOY.md` step 8). `infra/deploy.sh` on the server does the same.

## Decisions waiting for you

- [ ] **Add the PRD** at `docs/PRD.md`, then review every assumption in
  `docs/DECISIONS.md` against it (D-001).
- [ ] What volume brackets are keyed on: printed pages (`pages × copies`,
  current) or pages per book (D-014).
- [ ] Whether SOURCE quotes add a margin on top of sourcing cost (D-023).
- [ ] The refund policy for failed deliveries (D-026) and for orders
  cancelled while printing.
- [ ] Whether to cap cash-on-delivery orders, and at what amount (portal,
  Settings, "Cash on delivery limit").
- [ ] Proposed, not built: re-dispatch after a failed delivery (D-027); a
  manual vendor-cost accrual for in-progress orders (D-015); and staff changing their own
  password in the portal (D-052). Say which, if any, to build.

## Release steps only the owner can do

- [ ] Run `terraform apply` and create the IAM access keys (above).
- [ ] On the server, log in to `ghcr.io` with a `read:packages` token
  (`docs/DEPLOY.md` step 2).
- [ ] Tag the first release (`v1.0.0`), then run `./infra/deploy.sh v1.0.0`,
  `kitaab seed` and `kitaab create-admin` on the server (`docs/DEPLOY.md`
  steps 5–6).
- [ ] Run the backup drill once (`docs/RUNBOOK.md`) and confirm that dumps
  arrive in the backup bucket.
- [ ] Add the Android upload key secrets to GitHub, and the store listing,
  data safety form and review notes to Play Console. Turn on review mode for
  the review window only (`docs/RELEASE_MOBILE.md`, `docs/RUNBOOK.md`).
- [ ] Once Firebase and the Google OAuth client exist, try push and Google
  sign-in on a real device, so their status in `docs/INTEGRATIONS.md` can
  move from UNVERIFIED to Verified. Do the same for each real provider
  adapter against its sandbox.

## Deferred with iOS (D-002)

- [ ] Apple Developer Program account.
- [ ] Sign in with Apple service ID and key (required because the app offers
  Google sign-in).
- [ ] APNs key uploaded to Firebase.
- [ ] A Mac with Xcode, or a macOS CI runner, for iOS builds
  (`docs/RELEASE_MOBILE.md`, iOS).
