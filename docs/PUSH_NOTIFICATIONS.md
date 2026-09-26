# Push notifications (Firebase Cloud Messaging)

Alerts that need someone *now* — a visitor at the gate for a resident, the
resident's approve/reject for the guard — are pushed to the user's phone and
browser, so they arrive even when the app is closed. Everything else stays an
in-app notification.

Firebase project: **`society-app-186ff`** (project number 666567205264).
Its web settings — API key, web app id, sender id, Web Push key — are built
into the app (`mobile/lib/core/push/push_config.dart` and
`mobile/web/firebase-config.js`); they aren't secret. The one secret, the
service-account key the backend sends with, is set only on Railway.

| Where | Status |
|---|---|
| Web app (society.duxos.in) | built in |
| Backend | needs `FIREBASE_SERVICE_ACCOUNT_JSON` on Railway |
| Android app | needs a Firebase Android app for package `com.arsociety.app` |

Until the backend has the service-account key, nothing is pushed and the app
behaves as before (residents still see waiting visitors on their dashboard,
refreshed every 15 seconds).

## How it works

1. After sign-in the app asks for notification permission, gets the device's
   FCM token and registers it: `POST /api/v1/notifications/devices`
   (`device_tokens` table; one user can have several devices).
2. `NotificationService.send(..., push=True, action_url="/visitors/pending")`
   stores the in-app notification and hands it to `PushService`, which sends
   it through the FCM HTTP v1 API on a background thread.
3. Tapping the notification opens the app on `action_url`
   (web: `WEB_APP_URL/#/visitors/pending`).
4. Tokens FCM reports as unregistered (app uninstalled, browser data cleared)
   are switched off. Signing out unregisters the device.

## Setup

### 1. Backend (Railway service `AR_SOCIETY_APP`) — required
1. Firebase console → project `society-app-186ff` → **Project settings →
   Service accounts → Generate new private key**. This downloads a JSON file;
   keep it secret (it lets anyone send pushes as the app) and never commit it.
2. Railway → `AR_SOCIETY_APP` → **Variables** → add
   `FIREBASE_SERVICE_ACCOUNT_JSON` with the whole file contents as its value.
3. Optional: `WEB_APP_URL` (default `https://society.duxos.in`) — where a
   clicked web notification opens.

### 2. Android app
The app's package is `com.arsociety.app` (`android/app/build.gradle`).
Firebase console → **Add app → Android** with exactly that package name, then
put its App ID (`1:666567205264:android:…`) in `androidAppId` in
`push_config.dart` (or build with
`--dart-define=FIREBASE_ANDROID_APP_ID=…`). No `google-services.json` is
needed. (An Android app registered under a different package name, such as
`com.arsociety.ar_society_app`, won't receive pushes — remove it.)

### Pointing a build at another Firebase project
Override the built-in values with `--dart-define=FIREBASE_API_KEY=…`,
`FIREBASE_PROJECT_ID`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_WEB_APP_ID`,
`FIREBASE_VAPID_KEY` — for the web Docker build, as variables on the Railway
web service (the Dockerfile then also rewrites `firebase-config.js`).

## Checking it works
1. Sign in on the web app as a resident and click **Allow** when the browser
   asks about notifications.
2. As the guard, log a visitor for that resident's flat.
3. The resident gets "Visitor at Gate — … is at the gate for Wing A-102",
   even with the tab closed; clicking it opens Pending Approvals.

If nothing arrives: check the backend logs for `[push]` lines, and in the
browser that notifications are allowed for the site.

## Limits
- **iPhone/iPad (Safari):** web push only works after the resident adds the
  site to the Home Screen (Share → Add to Home Screen) and opens it from
  there. There's no native iOS app yet.
- Browsers or networks that block `gstatic.com` / `googleapis.com` (some ad
  blockers, office firewalls) get no push; the app still works and polls.
