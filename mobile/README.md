# ar_society_app

Flutter web app for AR Society.

## Run as a web app

Use the web flow instead of the APK path:

1. cd mobile
2. ./run_web.sh

This will build the web bundle and serve it at http://localhost:3000.

If you prefer a one-off browser launch during development:

flutter run -d chrome --web-port 3000

## Android APK: field edition

The APK is built from the same code as the web app but with `--dart-define=APP_EDITION=field`
(see `.github/workflows/build-apk.yml`). It is for residents, tenants, security, technical staff and gym trainers.
Accounts, finance, administration and the other operations screens stay on the web app: they are left out of the
menu, their addresses bounce to the person's own dashboard, and admin / committee / manager / platform-admin
accounts are told to use the web app when they sign in. The package id is unchanged, so it installs over the
earlier full-app APK. What the edition keeps is `AppEdition` in `lib/core/config/edition.dart`.
