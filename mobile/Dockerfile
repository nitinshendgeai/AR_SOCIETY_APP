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

# ── Stage 2: Nginx runtime ────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove the nginx default config and IPv6-by-default entrypoint script.
# Our start.sh generates the config from $PORT at container startup.
RUN rm /etc/nginx/conf.d/default.conf \
 && rm /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh

COPY --from=builder /app/build/web /usr/share/nginx/html

# Startup script: generates nginx.conf with Railway's $PORT then starts nginx.
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
