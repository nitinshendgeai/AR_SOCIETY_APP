import time
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, settings
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

# ── Unsafe configuration is said loudly (never printing the value) ───────────
def _warn_insecure_config() -> None:
    if settings.SECRET_KEY == Settings.model_fields["SECRET_KEY"].default or len(settings.SECRET_KEY) < 32:
        logger.critical("[security] SECRET_KEY is the built-in default or shorter than 32 characters: anyone can "
                        "forge login tokens. Set a long random SECRET_KEY in the environment.")
    if "*" in settings.ALLOWED_ORIGINS and settings.APP_ENV == "production":
        logger.warning("[security] ALLOWED_ORIGINS allows every origin in production; list the app's origin instead.")


_warn_insecure_config()

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

# ── Automatic tasks ──────────────────────────────────────────────────────────
from app.modules.automation import scheduler  # noqa: E402
scheduler.start()

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
    """Liveness: the process is up. Always HTTP 200 (the deploy's health check relies on that). It says whether the
    database answers and the schema is current, but never where the database is: use /health/ready to refuse traffic
    on a database that is down or behind."""
    from app.db.session import check_db_connection
    db_status = check_db_connection()
    return JSONResponse({
        "status":   "ok",
        "app":      settings.APP_NAME,
        "version":  settings.APP_VERSION,
        "env":      settings.APP_ENV,
        "time":     int(time.time()),
        "database": {"status": db_status["status"]},
        "migrations": _public_migration_status(),
    })


def _public_migration_status() -> dict:
    status_ = migration_status()
    if "error" in status_:                     # the detail is for the log, not for whoever asks
        return {"status": "unknown"}
    return status_


@app.get("/health/ready", tags=["System"])
def ready():
    """Readiness: 200 only when the database answers, the schema is at the code's head and this start-up's own
    migration run (if one was asked for) did not fail. Otherwise 503, so a half-migrated release is not served."""
    from app.db.migrate import startup_result
    from app.db.session import check_db_connection
    db_ok = check_db_connection()["status"] == "connected"
    migrations = _public_migration_status()
    schema_ok = migrations.get("up_to_date") is True
    startup_ok = startup_result["ok"] is not False
    is_ready = db_ok and schema_ok and startup_ok
    body = {
        "status": "ready" if is_ready else "not_ready",
        "database": "connected" if db_ok else "unavailable",
        "migrations": migrations,
        "startup_migration": {"attempted": startup_result["attempted"], "ok": startup_result["ok"]},
    }
    return JSONResponse(body, status_code=200 if is_ready else 503)


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
        from app.db.migrate import redact
        logger.warning(f"[health] could not read the migration status: {redact(e)[:200]}")
        return {"status": "unknown", "error": redact(e)[:120]}


@app.get("/", tags=["System"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}
