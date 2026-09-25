# Push notifications (Firebase Cloud Messaging)

Alerts that need someone *now* — a visitor at the gate for a resident, the
resident's approve/reject for the guard — are pushed to the user's phone and
browser, so they arrive even when the app is closed. Everything else stays an
in-app notification.

Push is **off until Firebase is configured**. Without the settings below the
app and API behave exactly as before (residents still see waiting visitors on
their dashboard, refreshed every 15 seconds).

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

## One-time setup

### 1. Create the Firebase project
1. <https://console.firebase.google.com> → **Add project** (Google Analytics
   not needed).
2. **Project settings → General → Your apps → Add app → Web** (nickname e.g.
   "DUX OS web"). Copy from the config it shows: `apiKey`, `projectId`,
   `messagingSenderId`, `appId`.
3. **Project settings → Cloud Messaging → Web configuration → Web Push
   certificates → Generate key pair.** Copy the key (the VAPID key).
4. **Project settings → Service accounts → Generate new private key.** This
   downloads a JSON file — keep it secret; it lets the server send pushes.

### 2. Backend (Railway service `AR_SOCIETY_APP`)
| Variable | Value |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | the whole contents of the service-account JSON file |
| `WEB_APP_URL` | `https://society.duxos.in` (default; change only if the web app moves) |

### 3. Web app (Railway service `superb-charm`)
These are build variables — Railway passes them to the Dockerfile's `ARG`s, so
**redeploy** after adding them.

| Variable | From step 1 |
|---|---|
| `FIREBASE_API_KEY` | `apiKey` |
| `FIREBASE_PROJECT_ID` | `projectId` |
| `FIREBASE_MESSAGING_SENDER_ID` | `messagingSenderId` |
| `FIREBASE_WEB_APP_ID` | `appId` (the web one, `1:…:web:…`) |
| `FIREBASE_VAPID_KEY` | the Web Push certificate key |

These web values are not secrets (they end up in the browser either way); the
service-account JSON is.

### 4. Android app
1. Firebase console → **Add app → Android**, package name `com.arsociety.app`.
   Copy its `appId` (`1:…:android:…`). No `google-services.json` is needed —
   the app is configured from build flags.
2. Build with:
   ```
   flutter build apk --release \
     --dart-define=API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1 \
     --dart-define=FIREBASE_API_KEY=… --dart-define=FIREBASE_PROJECT_ID=… \
     --dart-define=FIREBASE_MESSAGING_SENDER_ID=… \
     --dart-define=FIREBASE_ANDROID_APP_ID=1:…:android:…
   ```

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
