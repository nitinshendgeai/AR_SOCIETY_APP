# ── Stage 1: Flutter web build ────────────────────────────────────────────────
FROM ghcr.io/cirruslabs/flutter:stable AS builder

WORKDIR /app

# Copy dependency files first for layer caching
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --no-example

# Copy source
COPY . .

# Build arguments — override at build time for different environments
ARG API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1
ARG APP_ENV=production

# Build Flutter web in release mode
# --dart-define bakes the API URL into the compiled JS (no .env fetch needed)
RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=APP_ENV=${APP_ENV} \
    --no-tree-shake-icons

# ── Stage 2: Nginx runtime ────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy SPA nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built Flutter web output
COPY --from=builder /app/build/web /usr/share/nginx/html

# Railway sets PORT at runtime; nginx listens on 80 internally.
# Railway's networking maps its PORT → container:80.
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
