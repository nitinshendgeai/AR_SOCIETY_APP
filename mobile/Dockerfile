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

RUN rm /etc/nginx/conf.d/default.conf

# Store config as a template — CMD substitutes only $PORT at startup
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

COPY --from=builder /app/build/web /usr/share/nginx/html

# Substitute ONLY $PORT (leaves nginx vars like $uri untouched), then start nginx.
# envsubst '$PORT' limits substitution to that one variable.
CMD ["/bin/sh", "-c", "envsubst '$PORT' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
