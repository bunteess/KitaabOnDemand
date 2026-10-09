# Owner to-do

Things only the owner can supply or do. Each item says what is needed and
where it goes. Items marked **before launch** block a production release.

## Product and business

- [ ] **Add the PRD** at `docs/PRD.md`, then review every assumption in
  `docs/DECISIONS.md` against it (D-001).
- [ ] **App name and logo** (before launch): final name, launcher icon (1024 ×
  1024 PNG) and a short tagline for the store.
- [ ] **Real pricing** (before launch): per-page rates for Local White and
  Imported Yellow paper, binding fees for Softcover Paperback and Premium
  Hardcover, maximum pages per binding, any volume brackets, delivery fee per
  zone and the COD fee. The seeded values are placeholders.
- [ ] Confirm what volume brackets are keyed on: printed pages (`pages × copies`,
  current) or pages per book (D-014).
- [ ] Decide whether SOURCE quotes add a margin on top of sourcing cost (D-023).
- [ ] **Real city and zone data** (before launch): the list of served cities
  and each city's courier zone code. The seeded zones are placeholders.
- [ ] Refund policy for failed deliveries (D-026) and for orders cancelled
  while printing.
- [ ] Whether to set `COD_MAX_ORDER_VALUE`, and to what amount.
- [ ] **Vendor onboarding** (before launch): each print vendor's name, contact,
  city, address and the email of each staff member who needs portal access.
- [ ] Support contact details shown in the app (phone, WhatsApp, email, hours).

## Legal

- [ ] **Terms of service** (before launch): replace the placeholder text.
- [ ] **Privacy policy** (before launch): replace the placeholder and publish it
  at a public URL (needed for Google Play).
- [ ] **Copyright declaration** wording shown on PDF upload.
- [ ] Public account deletion page URL (Google Play requires one in the
  data-safety form).

## Accounts and credentials

- [ ] **Google Play Console** developer account.
- [ ] **Firebase project** with an Android app for each flavor
  (`pk.kitaabondemand.app`, `.dev`, `.staging`). Enable Cloud Messaging. Supply
  the Android app config values (API key, app ID, sender ID, project ID) and a
  service account JSON for the server.
- [ ] **Google OAuth client** for Android sign-in: register the SHA-1 of the
  upload and app signing keys, and supply the web client ID used as the server
  audience.
- [ ] **AWS account**: region (default `ap-south-1`), an S3 bucket name, and an
  IAM user or role for the server (policy in `infra/terraform`).
- [ ] **SMS gateway**: choose one, open an account, place its official API docs
  in `docs/integrations/<provider>/` and supply sandbox credentials.
- [ ] **Payment gateways**: Easypaisa, JazzCash and one card gateway. Merchant
  accounts, official API docs in `docs/integrations/<provider>/`, sandbox
  credentials and webhook secrets.
- [ ] **Couriers**: Trax, Leopards and TCS (whichever you use). Accounts,
  official API docs in `docs/integrations/<provider>/` and API keys.
- [ ] **Domain and DNS**: a domain for the API and portal (for example
  `api.example.pk`, `portal.example.pk`) pointing to the server.
- [ ] Optional: a Sentry project and DSN.
- [ ] Once Firebase and the Google OAuth client exist, try push and Google
  sign-in on a real device so their status in `docs/INTEGRATIONS.md` can move
  from UNVERIFIED to Verified.

## Release steps only the owner can do

- [ ] Create the Android upload keystore and keep it safe, outside git
  (`docs/RELEASE_MOBILE.md`).
- [ ] Provision the server and run the deploy steps in `docs/DEPLOY.md`.
- [ ] Upload the first AAB to Play Console, fill in the data-safety form, add
  the reviewer demo account to the review notes, upload screenshots.

## Deferred with iOS (D-002)

- [ ] Apple Developer Program account.
- [ ] Sign in with Apple service ID and key.
- [ ] APNs key uploaded to Firebase.
- [ ] A Mac with Xcode, or a macOS CI runner, for iOS builds.
