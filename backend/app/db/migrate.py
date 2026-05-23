"""
Migration helper — runs 'alembic upgrade head' programmatically.
Resolves alembic.ini path absolutely so it works from any working directory.
Activated by setting RUN_MIGRATIONS=true environment variable.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Absolute path to backend/ directory (where alembic.ini lives)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_migrations() -> bool:
    """
    Run alembic upgrade head.
    Returns True on success, False on failure.
    Always safe to call — never raises.
    """
    if os.getenv("RUN_MIGRATIONS", "false").lower() != "true":
        logger.info("[migrate] RUN_MIGRATIONS not set — skipping.")
        return False

    try:
        from alembic.config import Config
        from alembic import command

        ini_path = os.path.join(BACKEND_DIR, "alembic.ini")
        logger.info(f"[migrate] Loading alembic config from: {ini_path}")

        alembic_cfg = Config(ini_path)
        # Ensure script_location is absolute
        alembic_cfg.set_main_option(
            "script_location",
            os.path.join(BACKEND_DIR, "alembic")
        )

        logger.info("[migrate] Running: alembic upgrade head")
        command.upgrade(alembic_cfg, "head")
        logger.info("[migrate] ✅ Migrations complete.")
        return True

    except Exception as e:
        logger.error(f"[migrate] ❌ Migration failed: {e}")
        return False
