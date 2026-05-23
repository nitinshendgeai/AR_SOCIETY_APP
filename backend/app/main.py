from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.core.config import settings
from app.api import api_router
from app.db.base import Base
from app.db.session import engine

# ── Register all models ───────────────────────────────────────────────────────
import app.models  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Dev convenience: create tables directly (skipped if DB unavailable) ───────
# In production use: alembic upgrade head  (via RUN_MIGRATIONS=true)
try:
    Base.metadata.create_all(bind=engine)
    logger.info("[startup] Database tables verified/created.")
except Exception as e:
    logger.warning(f"[startup] DB not available yet, skipping table creation: {e}")

# ── Optional: run alembic migrations on boot ─────────────────────────────────
try:
    from app.db.migrate import run_migrations
    run_migrations()
except Exception as e:
    logger.warning(f"[startup] Migration runner skipped: {e}")

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade Society ERP API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    return JSONResponse({
        "status":  "ok",
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env":     settings.APP_ENV,
        "time":    int(time.time()),
    })


@app.get("/", tags=["Root"])
def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs"}
