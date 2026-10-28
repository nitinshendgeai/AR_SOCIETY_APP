"""Fixtures for the help-assistant tests: the shared two-society security world, plus a clean assistant state."""
import pytest

from app.core.config import settings
from app.modules.assistant import knowledge, service
from tests.security.world import world  # noqa: F401


@pytest.fixture(autouse=True)
def assistant_state(monkeypatch):
    """Default settings for every test (disabled provider, generous rate limit) and no leftover rate-limit hits."""
    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    monkeypatch.setattr(settings, "ASSISTANT_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "ASSISTANT_RATE_LIMIT_PER_MINUTE", 1000)
    service.reset_rate_limits()
    knowledge.reset_index_cache()
    yield
    service.reset_rate_limits()
    knowledge.reset_index_cache()
