"""
Migration helper — runs 'alembic upgrade head' programmatically.
Called at app startup when RUN_MIGRATIONS=true env var is set.
Safe to call even if DB is unavailable (fails silently).
"""
import os
import logging

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run alembic upgrade head if RUN_MIGRATIONS env var is set."""
    if os.getenv("RUN_MIGRATIONS", "false").lower() != "true":
        return
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        logger.info("[migrate] Running alembic upgrade head...")
        command.upgrade(alembic_cfg, "head")
        logger.info("[migrate] Migrations complete.")
    except Exception as e:
        logger.warning(f"[migrate] Migration skipped — DB not ready: {e}")
