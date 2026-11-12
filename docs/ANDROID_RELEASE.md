# Android release (Play Store)

Package name: `in.duxos.society`. The Play Store takes an **App Bundle (.aab)**, signed with an **upload key**.
Play App Signing then re-signs it with Google's own key; you only ever keep the upload key.

## 1. Create the upload key (once)

```bash
keytool -genkeypair -v -keystore upload-keystore.jks -alias upload \
  -keyalg RSA -keysize 2048 -validity 10000
```

Keep `upload-keystore.jks` and its passwords somewhere safe (a password manager). Never commit them -- `.gitignore`
already blocks `*.jks`, `*.keystore` and `mobile/android/key.properties`. Losing the upload key is recoverable
(Play Console -> App integrity -> request an upload key reset), but it takes days.

## 2. Build the bundle

**On GitHub (recommended):** add four repository secrets (Settings -> Secrets and variables -> Actions):

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | output of `base64 -w0 upload-keystore.jks` |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | `upload` (or the alias you chose) |
| `ANDROID_KEY_PASSWORD` | key password |

Then Actions -> **Build Android App Bundle (Play Store)** -> Run workflow. Download the `DUXOS Society AAB`
artifact. The version code is the workflow run number, so each upload is higher than the last.

**Locally:** create `mobile/android/key.properties` (not committed):

```properties
storeFile=/absolute/path/to/upload-keystore.jks
storePassword=...
keyAlias=upload
keyPassword=...
```

```bash
cd mobile
flutter build appbundle --release --build-number=2 \
  --dart-define=API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1 \
  --dart-define=APP_ENV=production --dart-define=APP_EDITION=field
```

Output: `mobile/build/app/outputs/bundle/release/app-release.aab`.

Without a keystore the release build falls back to the debug key (so the existing APK workflow keeps working).
A debug-signed bundle is rejected by Play.

## 3. Upload

Play Console -> create app `in.duxos.society` -> Testing -> Closed testing -> Create release -> upload the `.aab`.
Version name comes from `version:` in `mobile/pubspec.yaml`; bump it for user-visible releases.

## Before the first upload

- Register the Firebase Android app for `in.duxos.society` and update `androidAppId` in
  `mobile/lib/core/push/push_config.dart` (see `docs/PUSH_NOTIFICATIONS.md`).
- If you use Play App Signing, add the SHA-256 of Google's app-signing key to Firebase only if you adopt features that need it.
