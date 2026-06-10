# Deployment — AR Society ERP

Last updated: 2026-06-10

---

## Architecture

```
Railway Project: AR Society App
├── Service 1 — Backend (FastAPI)
│   ├── Root directory: /  (repo root)
│   ├── Builder: Nixpacks (nixpacks.toml)
│   ├── URL: https://arsocietyapp-production.up.railway.app
│   └── Database: Railway PostgreSQL (internal network)
│
└── Service 2 — Frontend (Flutter Web)
    ├── Root directory: /mobile
    ├── Builder: Docker (mobile/Dockerfile)
    ├── URL: https://<frontend-service>.up.railway.app
    └── Serves: Nginx + Flutter web build/web
```

---

## Service 1 — Backend (FastAPI)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | `postgresql://user:pass@postgres.railway.internal:5432/railway` |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars, random) |
| `RUN_MIGRATIONS` | ✅ | Set `true` to auto-run `alembic upgrade head` on deploy |
| `APP_ENV` | optional | `production` |
| `PORT` | auto | Set by Railway |

### Build Config (`nixpacks.toml`)
```toml
[phases.setup]
nixPkgs = ["python312", "gcc"]

[phases.install]
cmds = [
  "python3 -m venv /opt/venv",
  "/opt/venv/bin/pip install -r backend/requirements.txt --quiet"
]

[start]
cmd = "bash /app/start.sh"
```

### Start Sequence (`start.sh`)
1. Activate `/opt/venv`
2. `cd /app/backend`
3. If `RUN_MIGRATIONS=true`: `alembic upgrade head`
4. `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Health Check
- Path: `/health`
- Timeout: 30s

---

## Service 2 — Frontend (Flutter Web)

### Files

| File | Purpose |
|------|---------|
| `mobile/Dockerfile` | Multi-stage build: Flutter → Nginx |
| `mobile/nginx.conf` | Nginx SPA config with proper Flutter web routing |
| `mobile/railway.json` | Railway frontend service config |
| `mobile/.env` | Development API URL (committed, loaded at runtime) |
| `mobile/.env.production` | Production API URL (committed, loaded at runtime) |

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `API_BASE_URL` | optional | Backend API URL (build arg) | `https://arsocietyapp-production.up.railway.app/api/v1` |
| `APP_ENV` | optional | Environment name (build arg) | `production` |

> **Note:** These are Docker **build arguments** (passed via `--build-arg`), not runtime env vars. The API URL is baked into the compiled Flutter JavaScript at build time via `--dart-define`. Runtime Railway environment variables are not available inside Flutter web JavaScript.

### API URL Priority Order

The Flutter app resolves `API_BASE_URL` in this order:

1. **`--dart-define=API_BASE_URL=…`** — baked in at Docker build time (highest priority)
2. **`.env` bundled asset** — fetched at app startup from `Env.apiBaseUrl`
3. **Hard-coded fallback** — `https://arsocietyapp-production.up.railway.app/api/v1`

For Railway deployment, priority 1 is used (baked via Dockerfile `ARG`).

### Dockerfile Build Process

```dockerfile
# Stage 1: Build
FROM ghcr.io/cirruslabs/flutter:stable AS builder
WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --no-example
COPY . .
ARG API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1
ARG APP_ENV=production
RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=APP_ENV=${APP_ENV}

# Stage 2: Serve
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/build/web /usr/share/nginx/html
EXPOSE 80
```

### Nginx Config (`mobile/nginx.conf`)

- Serves static files with long cache headers (content-hashed by Flutter)
- All unmatched routes → `index.html` (required for GoRouter hash navigation)
- `.env` asset served with 5-min cache and `no-store` headers
- Gzip enabled for JS/CSS/WASM

### Build Status

```
✓ flutter build web --release  (verified 2026-06-10, Flutter 3.41.7)
✓ flutter build web --release --dart-define=API_BASE_URL=... (verified 2026-06-10)

Warnings (non-blocking):
- flutter_secure_storage_web: dart:html / dart:js_util incompatible with WASM
  → JavaScript build is unaffected; WASM not used
- cupertino_icons font not tree-shaken (informational only)
```

---

## Setting Up the Frontend Service on Railway

### Step-by-step

1. Open your Railway project at [railway.app](https://railway.app)

2. Click **+ New Service** → **GitHub Repo**

3. Select the `AR_SOCIETY_APP` repository

4. In service settings:
   - **Root Directory**: `/mobile`
   - **Builder**: Docker (auto-detected from `mobile/Dockerfile`)
   - Leave start command blank (Dockerfile CMD handles it)

5. Under **Build Arguments** (optional — default is already correct):
   ```
   API_BASE_URL = https://arsocietyapp-production.up.railway.app/api/v1
   APP_ENV = production
   ```

6. Click **Deploy**

7. Once deployed, Railway assigns a URL like `https://ar-society-frontend.up.railway.app`

8. Optionally set a custom domain in Railway service settings

### Verify after deploy

Open the Railway service URL. You should see:
- Flutter web app loads
- Login screen appears
- Network tab shows API calls to `https://arsocietyapp-production.up.railway.app/api/v1/...`

---

## Local Development

### Backend

```bash
cd backend

# Install deps
pip install -r requirements.txt

# Copy env
cp .env.example .env
# Edit .env with:
# DATABASE_URL=postgresql://...
# SECRET_KEY=any-32-char-string

# Run server
uvicorn app.main:app --reload --port 8000
```

### Frontend (web)

```bash
cd mobile

# Install deps
flutter pub get

# Start dev server (uses .env which points to production backend)
flutter run -d chrome

# Or build and serve locally
flutter build web --release
python3 -m http.server 3000 --directory build/web
# → http://localhost:3000
```

### Override API URL locally

To point the Flutter app at a local backend during development:

```bash
flutter run -d chrome \
  --dart-define=API_BASE_URL=http://localhost:8000/api/v1 \
  --dart-define=APP_ENV=development
```

Or edit `mobile/.env`:
```
API_BASE_URL=http://localhost:8000/api/v1
APP_ENV=development
```

---

## Migration Workflow

```bash
# 1. Create revision (locally)
cd backend
DATABASE_URL="..." python -m alembic revision -m "description"

# 2. Fill upgrade()/downgrade()

# 3. Test locally
DATABASE_URL="sqlite:///test.db" python -m alembic upgrade head

# 4. Push to main — Railway auto-deploys and runs alembic upgrade head
git push origin main
```

**Never use `--autogenerate` with PostgreSQL enums in production.**
**One head at all times: verify with `python -m alembic heads`.**

---

## Deployment Checklist

### Backend
```
□ python -c "from app.main import app" exits cleanly
□ python -m alembic heads shows exactly ONE head
□ requirements.txt has no test-only deps
□ DATABASE_URL set in Railway (internal URL)
□ SECRET_KEY set in Railway (32+ chars)
□ RUN_MIGRATIONS=true set in Railway
```

### Frontend
```
□ flutter build web --release succeeds locally
□ mobile/Dockerfile exists
□ mobile/nginx.conf exists
□ mobile/railway.json exists
□ Railway service root directory = /mobile
□ API_BASE_URL build arg set (or use default)
```

---

## Database: Internal vs External URL

| Context | URL format |
|---------|-----------|
| Railway services (internal) | `postgresql://...@postgres.railway.internal:5432/railway` |
| External / local dev | `postgresql://...@monorail.proxy.rlwy.net:PORT/railway` |

Always use the **internal URL** in `DATABASE_URL` for Railway deployments.

---

## Troubleshooting

### Frontend shows blank page
- Check browser console for JavaScript errors
- Verify Nginx is running: Railway service logs should show `nginx: [notice] start worker process`
- Verify build succeeded: look for `✓ Built build/web` in deploy logs

### 403 on API calls
- Confirm the logged-in user's role is in `EXTENDED_DEFAULT_ROLES`
- All module guards now use canonical role names (see `backend/app/core/dependencies.py`)
- Society Admin has full access to all modules within their society

### API calls going to wrong URL
- Check Network tab → XHR requests → Request URL
- Should be `https://arsocietyapp-production.up.railway.app/api/v1/...`
- If wrong: verify `API_BASE_URL` build arg in Railway frontend service settings

### CORS errors
- Backend has CORS configured to allow all origins (`*`) in development
- For production, update `ALLOWED_ORIGINS` in backend if needed
