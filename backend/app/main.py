import time
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.api import api_router
from app.utils.exceptions import (
    validation_exception_handler,
    integrity_error_handler,
    generic_exception_handler,
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
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Middleware ────────────────────────────────────────────────────────────────
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
    })


@app.get("/", tags=["System"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}
