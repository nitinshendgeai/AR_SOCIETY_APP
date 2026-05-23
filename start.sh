#!/bin/bash
set -e

echo "============================================"
echo "  AR Society ERP — Starting up"
echo "============================================"
echo "[start] Time: $(date)"
echo "[start] Python: $(/opt/venv/bin/python --version 2>&1)"
echo "[start] Working dir: $(pwd)"
echo "[start] PORT: $PORT"
echo "[start] APP_ENV: $APP_ENV"
echo "[start] RUN_MIGRATIONS: $RUN_MIGRATIONS"

# Mask DB URL for logging
if [ -n "$DATABASE_URL" ]; then
    echo "[start] DATABASE_URL: set ✅"
else
    echo "[start] DATABASE_URL: NOT SET ❌"
fi

cd /app/backend
echo "[start] Changed to: $(pwd)"

# Run Alembic migrations if enabled
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[start] Running database migrations..."
    /opt/venv/bin/python -m alembic upgrade head
    echo "[start] ✅ Migrations complete"
else
    echo "[start] Skipping migrations (RUN_MIGRATIONS != true)"
fi

echo "[start] Starting uvicorn..."
exec /opt/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info \
    --access-log
