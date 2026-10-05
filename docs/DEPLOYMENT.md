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
- Timeout: 300s (`railway.json`). The migrations run *before* the app answers, and on a brand-new empty database
  that is ~60 of them over the network: well over the old 30s on a first start, which marked that first deploy
  failed even though the migrations had finished.

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

### Checking a deploy
`GET /health` shows `"migrations": {"current": [...], "head": [...], "up_to_date": true|false}`. After every
deploy that adds a migration, it must read `up_to_date: true`. If it doesn't, the new code is running against the
old schema: screens that read the new tables or columns get `503 SCHEMA_OUTDATED` ("The server's database hasn't
been updated for this version of the app"). Fix by running the migration:

```bash
# Either: Railway → service → Variables → RUN_MIGRATIONS=true, then Redeploy (start.sh runs alembic upgrade head;
# a failing migration stops the deploy — read the deploy log)
# Or, from a machine with the Railway CLI / public DB URL:
cd backend && DATABASE_URL="<public_proxy_url_from_railway>" python -m alembic upgrade head
```

Errors no route handles are returned as JSON from inside the CORS middleware, so the browser always receives
them (previously a 500 had no CORS headers and the web app showed "Could not reach the server").

---

## Starting with a blank database

Same schema, no data, one Platform Admin, and societies register themselves. Checked end to end on a copy of a
populated database: after the steps below the database has the same 107 tables as the models, at the latest migration,
and holds only the reference rows the migrations insert (`forms`, `permissions`). Everything else — roles, role
grants, societies, users, and the files people uploaded (stored in the database) — is gone or recreated by the app.

### What a blank database needs
1. **The schema** — `alembic upgrade head` (done on deploy when `RUN_MIGRATIONS=true`). Run on an empty database it builds
   exactly the schema the models describe.
2. **The first Platform Admin** — nothing can log in until one exists (§C below).
3. **Societies** — each registers itself in the app (**Register Your Society**), which creates the 16 roles and their
   permission and form grants, the society (30-day trial), its default logins, designations and shifts.

### A. A new empty database (recommended: nothing is deleted, and it is easy to undo)
1. Railway project → **+ New → Database → PostgreSQL** (call it e.g. `Postgres-live`).
2. Backend service → **Variables**: point `DATABASE_URL` at the new database (its internal URL, or the reference
   `${{Postgres-live.DATABASE_URL}}`) and keep `RUN_MIGRATIONS=true`. Change `SECRET_KEY` too if you want every old
   login session to stop working at once.
3. **Redeploy**. The deploy log lists each `Running upgrade …` ending at the latest revision. Open `/health`: the database
   is `connected` and `migrations` says `"up_to_date": true`.
4. Create the first Platform Admin (§C).
5. Open the app and register your society.

The old database is untouched. To go back, set `DATABASE_URL` back and redeploy; delete the old database once you are sure.

### B. Empty the existing database (same database, data removed)
1. **Back up first** (this cannot be undone), using the Postgres service's *public* URL from Railway → Connect:
   `pg_dump "<public url>" -Fc -f backup-$(date +%F).dump`
2. Pause the backend service so nobody registers or logs in while it runs.
3. From a machine with the repo and `pip install -r backend/requirements.txt`:
   ```bash
   cd backend
   DATABASE_URL="<public url>" python -m app.utils.reset_data                       # dry run: shows what it would clear
   DATABASE_URL="<public url>" python -m app.utils.reset_data --confirm-db railway --yes   # the database name shown, and yes
   ```
   It clears every table except `alembic_version`, `forms` and `permissions` in one transaction, and refuses unless the
   database name you give matches. If a migration ever starts seeding another table, add it to `KEEP_TABLES`
   in `backend/app/utils/reset_data.py`.
4. Resume the backend. Create the first Platform Admin (§C).

### C. Create the first Platform Admin
```bash
cd backend
DATABASE_URL="<public url>" PLATFORM_ADMIN_PASSWORD='a-strong-password-1' \
  python -m app.utils.create_platform_admin you@yourdomain.com "Your Name"
```
The password is read from `PLATFORM_ADMIN_PASSWORD` (or asked for), never put on the command line; at least 10
characters with letters and digits. It creates the `Platform Admin` role and the user (no society, no first-login
wizards) and is safe to run again (an existing user is promoted and keeps their password; `--reset-password` sets a
new one). Log in with it to see every society's trial status.

### D. After going live
- Register the real society in the app. The default logins it creates (`admin@<code>.com` and the other roles) share
  the standard onboarding password and **must change it at first login** — do that straight away.
- Registration is public: anyone with the link can register a society (that is the SaaS sign-up).
- Everyone logs in again; old sessions refer to users that no longer exist.
- Nothing lives outside the database (uploaded payment screenshots and bank statements are stored in it), so there are
  no files to clear.

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
