# ── Stage 1: Flutter web build ────────────────────────────────────────────────
FROM ghcr.io/cirruslabs/flutter:stable AS builder

WORKDIR /app

COPY pubspec.yaml ./
RUN flutter pub get --no-example

COPY . .

# .env is listed as a Flutter asset but not committed; create placeholder.
RUN touch .env

ARG API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1
ARG APP_ENV=production

# Push notifications (optional): the Firebase web app's settings, set as
# variables on this Railway service. See docs/PUSH_NOTIFICATIONS.md.
ARG FIREBASE_API_KEY=""
ARG FIREBASE_PROJECT_ID=""
ARG FIREBASE_MESSAGING_SENDER_ID=""
ARG FIREBASE_WEB_APP_ID=""
ARG FIREBASE_VAPID_KEY=""

RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=APP_ENV=${APP_ENV} \
    --dart-define=FIREBASE_API_KEY=${FIREBASE_API_KEY} \
    --dart-define=FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID} \
    --dart-define=FIREBASE_MESSAGING_SENDER_ID=${FIREBASE_MESSAGING_SENDER_ID} \
    --dart-define=FIREBASE_WEB_APP_ID=${FIREBASE_WEB_APP_ID} \
    --dart-define=FIREBASE_VAPID_KEY=${FIREBASE_VAPID_KEY} \
    --no-tree-shake-icons

# The push service worker can't read dart-defines; give it the same settings.
RUN if [ -n "$FIREBASE_API_KEY" ] && [ -n "$FIREBASE_WEB_APP_ID" ]; then \
      printf 'self.FIREBASE_CONFIG = {apiKey: "%s", authDomain: "%s.firebaseapp.com", projectId: "%s", messagingSenderId: "%s", appId: "%s"};\n' \
        "$FIREBASE_API_KEY" "$FIREBASE_PROJECT_ID" "$FIREBASE_PROJECT_ID" "$FIREBASE_MESSAGING_SENDER_ID" "$FIREBASE_WEB_APP_ID" \
        > build/web/firebase-config.js; \
    fi

# ── Stage 2: Caddy runtime ────────────────────────────────────────────────────
FROM caddy:2-alpine

# Caddy reads PORT from the environment via {$PORT} in the Caddyfile.
# No scripts, no entrypoint modifications needed.
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/build/web /srv

