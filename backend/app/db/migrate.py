"""
Migration helper — runs 'alembic upgrade head' programmatically.
Resolves alembic.ini path absolutely so it works from any working directory.
Activated by setting RUN_MIGRATIONS=true environment variable.
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# What happened when the app tried to migrate at start-up, for /health/ready. `ok` is None until a run was attempted.
startup_result = {"attempted": False, "ok": None, "error": None}

_URL_CREDENTIALS = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/@\s]*@")


def redact(text) -> str:
    """Hide the user and password of any connection URL in an error message before it is logged or reported."""
    return _URL_CREDENTIALS.sub(r"\1***@", str(text))

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

    startup_result.update(attempted=True, ok=None, error=None)

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
        startup_result.update(ok=True)
        return True

    except Exception as e:
        # Never silent: the failure is logged at CRITICAL (credentials removed) and remembered, so /health/ready
        # reports "not ready" instead of the app looking healthy on a half-migrated database.
        message = redact(e)[:300]
        startup_result.update(ok=False, error=message)
        logger.critical(f"[migrate] ❌ Migration FAILED — the database may be behind this version of the code: {message}")
        return False
