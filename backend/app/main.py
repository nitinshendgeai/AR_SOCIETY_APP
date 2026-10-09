import time
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.api import api_router
from app.utils.utc_response import UtcJSONResponse
from app.utils.exceptions import (
    validation_exception_handler,
    integrity_error_handler,
    generic_exception_handler,
    error_response,
)

# ── Register all models (must be before alembic/migrations) ──────────────────
import app.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Run Alembic migrations if RUN_MIGRATIONS=true ────────────────────────────
try:
    from app.db.migrate import run_migrations
    run_migrations()
except Exception as e:
    logger.warning(f"[startup] Migration runner error: {e}")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade Society ERP API — FastAPI + PostgreSQL",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    default_response_class=UtcJSONResponse,
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Middleware ────────────────────────────────────────────────────────────────
# Errors no route handled are turned into JSON here, inside CORS, so the reply
# carries the CORS headers. The Exception handler above runs outside every
# middleware, and a browser drops a cross-origin reply without them — the app
# then sees "could not reach the server" instead of the error.
@app.middleware("http")
async def unhandled_errors(request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001
        return error_response(exc)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ── System endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    from app.db.session import check_db_connection
    db_status = check_db_connection()
    return JSONResponse({
        "status":   "ok",
        "app":      settings.APP_NAME,
        "version":  settings.APP_VERSION,
        "env":      settings.APP_ENV,
        "time":     int(time.time()),
        "database": db_status,
        "migrations": migration_status(),
    })


def migration_status() -> dict:
    """The database's Alembic revision against the code's head — never raises."""
    try:
        import os
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text
        from app.db.session import get_engine

        backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend, "alembic"))
        heads = set(ScriptDirectory.from_config(cfg).get_heads())
        with get_engine().connect() as conn:
            current = {r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))}
        return {"current": sorted(current), "head": sorted(heads), "up_to_date": current == heads}
    except Exception as e:  # noqa: BLE001
        return {"status": "unknown", "error": str(e)[:120]}


@app.get("/", tags=["System"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}
