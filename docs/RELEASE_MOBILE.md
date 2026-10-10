# Mobile release

The first stage is Android only (D-002). iOS is described at the end so the
work is known, but there is no iOS project yet.

## Flavors

| Flavor | Application ID | App name | Settings file | Notes |
| --- | --- | --- | --- | --- |
| dev | `pk.kitaabondemand.app.dev` | Kitaab Dev | `config/dev.json` | Talks to a local API over plain HTTP (the emulator reaches the host at `10.0.2.2`) |
| staging | `pk.kitaabondemand.app.staging` | Kitaab Staging | `config/staging.json` | HTTPS only |
| prod | `pk.kitaabondemand.app` | KitaabOnDemand | `config/prod.json` | HTTPS only; the one that goes to Google Play |

All three install side by side. Minimum Android version: API 24 (Android 7.0).

Each settings file is passed with `--dart-define-from-file` and holds:

| Key | Value |
| --- | --- |
| `API_BASE_URL` | `https://API_DOMAIN` |
| `FIREBASE_API_KEY`, `FIREBASE_APP_ID`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_PROJECT_ID` | From the Firebase console, from the Android app registered for that flavor's application ID |
| `GOOGLE_SERVER_CLIENT_ID` | The Google OAuth web client ID, the same one listed first in the server's `GOOGLE_OAUTH_CLIENT_IDS` |
| `SUPPORT_PHONE`, `SUPPORT_EMAIL` | Shown on the help screen |

These are not secrets: they ship inside every copy of the app. Commit them.
Firebase is set up from these values, so no `google-services.json` is needed
(D-024). Without the Firebase values, push notifications are off and
everything else works.

## Version numbers

`apps/mobile/pubspec.yaml` has `version: 1.0.0+1`. The part before `+` is the
version customers see. The number after it is the version code, which Google
Play requires to go up with every upload. Before each release, raise both and
commit. The release tag must match the version: `v1.0.0` for `1.0.0+N`. The
Release workflow checks this.

## The upload key

Google Play App Signing holds the key that signs the app on customers' phones.
You keep an upload key, which proves to Google that an upload came from you.
If the upload key is lost, Google can reset it through Play Console support.
Without it, nobody can ship an update until then.

Create it once, on your own computer:

```bash
keytool -genkeypair -v -keystore ~/kitaab-upload.jks -alias upload \
  -keyalg RSA -keysize 2048 -validity 10000
```

- Never commit it: `.gitignore` refuses `*.jks`, `*.keystore` and
  `key.properties`.
- Keep the file and its passwords in a password manager, plus one offline
  copy.
- For Google sign-in, read the key's SHA-1 with
  `keytool -list -v -keystore ~/kitaab-upload.jks -alias upload`. After the
  first upload, also copy the app signing key's SHA-1 from Play Console (Test
  and release, App integrity). Add both to the Android OAuth client in Google
  Cloud (`docs/OWNER_TODO.md`).

## Building the release bundle

**On your computer.** Create `apps/mobile/android/key.properties`:

```properties
storeFile=/home/you/kitaab-upload.jks
storePassword=...
keyAlias=upload
keyPassword=...
```

Then build:

```bash
cd apps/mobile
flutter build appbundle --release --flavor prod --dart-define-from-file=config/prod.json
# or, from the repository root: make mobile-build FLAVOR=prod
```

The bundle is at `build/app/outputs/bundle/prodRelease/app-prod-release.aab`.
Without `key.properties`, the build is signed with the debug key and Google
Play refuses it. CI builds it that way on every push.

**In CI.** Add four repository secrets:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 ~/kitaab-upload.jks` |
| `ANDROID_KEYSTORE_PASSWORD` | The keystore password |
| `ANDROID_KEY_ALIAS` | `upload` |
| `ANDROID_KEY_PASSWORD` | The key password |

Pushing a tag `vX.Y.Z` runs the Release workflow. It checks that the tag
matches `pubspec.yaml` and that `config/prod.json` has no placeholder values.
It then builds the signed bundle and keeps it for 90 days as the artifact
`kitaabondemand-vX.Y.Z-aab`. The key exists only for the length of the job.

## Size

Measured in CI on 10 October 2026 (prod flavor, release mode):

| What | Size |
| --- | --- |
| App Bundle uploaded to Play (all CPU types) | 57.2 MB (57,160,626 bytes) |
| Download on an arm64 phone (most phones sold today) | 9.5 MB (9,463,661–9,488,114 bytes) |
| Download on an older 32-bit ARM phone | 9.1 MB (9,052,250–9,076,703 bytes) |
| Download on an x86_64 device (emulators, a few tablets) | 9.7 MB (9,652,869–9,677,322 bytes) |

Google Play sends each phone only the parts for its CPU type, screen density
and language, so customers download about 9.5 MB. The bundle holds three CPU
types, and the PDF preview library adds a native PDF engine to each. CI
reports the per-device size on every push (job "Android app", step "Download
size per device").

## First release on Google Play

1. In Play Console, create the app: default language English, app (not
   game), free.
2. **Internal testing** first. Upload the signed bundle, add testers by email,
   and install from the opt-in link on a real phone. Run the whole flow
   against production: sign in by SMS, upload a PDF, order with cash on
   delivery, then cancel.
3. Fill in the store listing, then go to the production track.

### Store checklist

- [ ] **App name, short description (80 characters), full description**,
  in English (an Urdu listing can follow).
- [ ] **Graphics**: 512 × 512 icon, 1024 × 500 feature graphic, and at least
  2 phone screenshots. The dev flavor with demo data makes clean screenshots
  without real customer data.
- [ ] **Privacy policy URL**: a public page with the final policy
  (`docs/OWNER_TODO.md`).
- [ ] **Account deletion**: customers delete their account in the app under
  Profile, Delete account (D-019). Play also needs a public web page that
  explains how to request deletion, and its URL.
- [ ] **Data safety form**, from what the app actually does:

  | Data | Collected | Why | Notes |
  | --- | --- | --- | --- |
  | Phone number | Yes | Sign-in, delivery, order updates | Required |
  | Name, delivery address | Yes | Delivery | Removed when the account is deleted, once open orders finish |
  | Email address | Only with Google sign-in | Sign-in | |
  | Files (PDFs) | Yes, when printing | Printing the order | Deleted 7 days after delivery or cancellation |
  | Purchase history | Yes | Orders and receipts | Card details never reach the app or the server; payment uses the gateway's hosted page |
  | Device or other IDs | Push token | Order notifications | |
  | Location, contacts, photos, analytics, crash logs | No | | The app has no analytics or crash-reporting SDK |

  All data is encrypted in transit, and none is shared with third parties for
  advertising. Delivery partners receive the name, phone and address needed
  to deliver. Customers can ask for deletion.
- [ ] **App access**: reviewers outside Pakistan cannot receive our SMS.
  Turn on review mode for the review window (`docs/RUNBOOK.md`, D-020). Put
  the review phone and code in the "App access" instructions, then turn it off
  after approval.
- [ ] **Content rating** questionnaire, **target audience** (not children),
  **ads**: none.
- [ ] **Permissions** declared in the app: internet, network state and
  notifications. Nothing needs a special declaration.

## iOS (deferred, D-002)

Not built in this stage. The owner asked for Android only. The Flutter code
has no iOS-only parts, so adding iOS means:

1. **Accounts and tools**: the Apple Developer Program, a Mac with Xcode (or
   a macOS CI runner), and an APNs key uploaded to Firebase for push.
2. **Project**: `flutter create --platforms=ios .` in `apps/mobile`, a bundle
   ID per flavor (Xcode schemes matching dev, staging and prod), and the
   iOS Firebase app values in each settings file.
3. **Sign in with Apple**: required by App Store Review Guideline 4.8 because
   the app offers Google sign-in. The server needs an Apple ID token
   verifier alongside Google's.
4. **Signing**: a distribution certificate and an App Store provisioning
   profile per bundle ID. Xcode's automatic signing can manage both.
5. **Build and ship**: `flutter build ipa --flavor prod
   --dart-define-from-file=config/prod.json`, upload with Xcode Organizer or
   Transporter, test through TestFlight, then submit for review with the same
   demo account notes.
6. **CI**: a workflow on a `macos` runner that builds the IPA, disabled until
   the signing certificate, profile and App Store Connect API key are stored
   as secrets. It is not added yet because there is no iOS project for it to
   build.

The store checklist above applies to the App Store too, with Apple's privacy
"nutrition label" in place of Play's data safety form.
