"""Optional explanation provider (OFF by default — Version 1 needs no AI service or API key).

A provider receives ONE already-computed finding as plain text/numbers and returns prose. By construction it gets no
database session, no user, no society id and no tool access, so it cannot run SQL, change records, bypass
authorisation, approve proposals or see another society's data. Its output is advisory text shown beside the
deterministic explanation; it never feeds back into a finding, a proposal or an approval. No provider is implemented
here and no credential is read anywhere.
"""
from typing import Optional, Protocol


class ExplanationProvider(Protocol):
    name: str

    def explain(self, finding: dict, timeout: float) -> str: ...


_PROVIDERS: dict = {}          # name -> provider instance; empty until a deployment registers one explicitly


def register_provider(provider: ExplanationProvider) -> None:
    _PROVIDERS[provider.name] = provider


def provider_status(name: str) -> str:
    return "disabled" if name == "disabled" else ("enabled" if name in _PROVIDERS else "misconfigured")


def explain_finding(provider_name: str, finding: dict) -> Optional[str]:
    """Advisory natural-language explanation, or None when the provider is disabled/unknown/failing."""
    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        return None
    safe = {k: finding.get(k) for k in ("title", "explanation", "expected_behaviour", "actual_behaviour", "severity",
                                         "finding_class", "category", "rule_code")}
    try:
        return str(provider.explain(safe, 10.0))[:2000]
    except Exception:  # noqa: BLE001 — a provider failure never affects the audit result
        return None
