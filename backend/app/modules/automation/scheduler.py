"""Starts the loop that runs the automatic tasks.

A daemon thread wakes every few minutes and asks AutomationService to run whatever is
due. Several workers can run this at once: a task's run for a period is claimed by a
unique database row, so it still runs only once.
"""
import logging
import threading
import time

from app.core.config import settings
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)
_started = False
INTERVAL_SECONDS = 600


def _loop() -> None:
    from app.modules.automation.services.automation_service import AutomationService
    time.sleep(60)    # let the app finish starting
    while True:
        db = get_session_factory()()
        try:
            ran = AutomationService(db).run_due()
            if ran:
                logger.info("[automation] ran %s task(s)", ran)
        except Exception:  # noqa: BLE001
            logger.exception("[automation] pass failed")
        finally:
            db.close()
        time.sleep(INTERVAL_SECONDS)


def start() -> None:
    global _started
    if _started or not settings.SCHEDULER_ENABLED:
        return
    _started = True
    threading.Thread(target=_loop, name="automation", daemon=True).start()
    logger.info("[automation] scheduler started")
