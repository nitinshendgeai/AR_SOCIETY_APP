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

RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=APP_ENV=${APP_ENV} \
    --no-tree-shake-icons

# ── Stage 2: Caddy runtime ────────────────────────────────────────────────────
FROM caddy:2-alpine

# Caddy reads PORT from the environment via {$PORT} in the Caddyfile.
# No scripts, no entrypoint modifications needed.
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/build/web /srv

