# ── Stage 1: Flutter web build ────────────────────────────────────────────────
FROM ghcr.io/cirruslabs/flutter:stable AS builder

WORKDIR /app

# Copy pubspec.yaml first for layer caching.
# pubspec.lock is in .gitignore (*.lock pattern) so it is never in the
# build context — flutter pub get regenerates it from pubspec.yaml constraints.
COPY pubspec.yaml ./
RUN flutter pub get --no-example

# Copy source
COPY . .

# .env is not committed (no secrets), but is listed as an asset in pubspec.yaml.
# Create an empty placeholder so Flutter's asset bundler doesn't abort.
RUN touch .env

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

# Copy SPA nginx config — nginx listens on port 80 (see internalPort in railway.json)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built Flutter web output
COPY --from=builder /app/build/web /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
