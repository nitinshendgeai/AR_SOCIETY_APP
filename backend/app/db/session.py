import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Engine — created lazily so import never hard-crashes ─────────────────────
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=settings.DEBUG,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


# ── FastAPI dependency ────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


# ── Health-check helper ───────────────────────────────────────────────────────
def check_db_connection() -> dict:
    """Returns DB connectivity status — never raises."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "url": _safe_url()}
    except Exception as e:
        logger.warning(f"[db] Connection check failed: {e}")
        return {"status": "unavailable", "error": str(e)[:120]}


def _safe_url() -> str:
    """Return DATABASE_URL with password masked."""
    url = settings.DATABASE_URL
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.username}:***@{p.hostname}:{p.port}{p.path}"
    except Exception:
        return "postgresql://***"


# ── Module-level engine for Alembic + Base.metadata ──────────────────────────
# (kept for backward compat — session.engine is used in main.py)
engine = get_engine()
