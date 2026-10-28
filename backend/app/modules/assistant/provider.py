"""Provider abstraction for the help assistant.

A provider turns (question, retrieved excerpts) into answer text. It is given NOTHING else: no user identity, no role,
no society, no conversation history, no diagnostics and no database record. Its output is untrusted: the service
validates and bounds it, and sources / steps / configuration gaps never come from it.

Only "disabled" and "mock" exist. No live provider is implemented and no credential is read anywhere in this module;
choosing one is an open decision (docs/HELP_ASSISTANT.md, "Provider decision").
"""
import concurrent.futures
import logging
from dataclasses import dataclass
from typing import List, Optional, Protocol

from app.modules.assistant.knowledge import lead_text

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Any provider failure. The message is for our logs only and is never shown to the user."""


@dataclass(frozen=True)
class ProviderRequest:
    question: str
    excerpts: List[str]            # retrieved manual text, to be treated as reference data, never as instructions


class AssistantProvider(Protocol):
    name: str
    def generate(self, request: ProviderRequest, timeout: float) -> str: ...


class MockProvider:
    """Deterministic, offline. Answers with a short summary of the best excerpt. Used by tests and local runs."""
    name = "mock"

    def generate(self, request: ProviderRequest, timeout: float) -> str:
        if not request.excerpts:
            raise ProviderError("no excerpts")
        return "According to the approved manual: " + lead_text(request.excerpts[0], 400)


def get_provider(name: str, app_env: str = "development") -> Optional[AssistantProvider]:
    """The configured provider, or None when disabled / unknown / not allowed in this environment."""
    if name == "mock" and app_env != "production":
        return MockProvider()
    return None


def provider_mode(name: str, app_env: str = "development") -> str:
    if name == "disabled":
        return "disabled"
    if name == "mock" and app_env != "production":
        return "mock"
    return "misconfigured"          # an unknown name, or the mock in production: behaves exactly like disabled


_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="assistant-provider")


def call_with_timeout(provider: AssistantProvider, request: ProviderRequest, timeout: float) -> str:
    """Runs provider.generate with a hard wall-clock limit that every provider gets, whatever its own timeout does.
    Raises ProviderError("timeout" | ...) — never anything provider-specific."""
    future = _pool.submit(provider.generate, request, timeout)
    try:
        out = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise ProviderError("timeout")
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 — a provider bug must not become a 500 or leak its message
        logger.warning("assistant provider failed: %s", type(exc).__name__)
        raise ProviderError("error")
    if not isinstance(out, str) or not out.strip():
        raise ProviderError("malformed")
    return out
