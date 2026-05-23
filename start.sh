#!/bin/bash
set -e

echo "[start] Working directory: $(pwd)"
echo "[start] Python: $(/opt/venv/bin/python --version)"

cd /app/backend

# Run migrations if enabled
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[start] Running alembic upgrade head..."
    /opt/venv/bin/python -m alembic upgrade head
    echo "[start] Migrations complete."
fi

echo "[start] Starting uvicorn on port $PORT..."
exec /opt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --log-level info
