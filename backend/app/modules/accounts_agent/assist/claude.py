"""Claude (Anthropic API) for wording bye-law answers and reading free-text entry requests.

Boundaries, by construction:
* OFF unless the deployment sets ANTHROPIC_API_KEY *and* the society's admin chooses the "anthropic" provider in
  the agent's settings.
* The functions receive plain text and lists only (a question, the clauses the app itself found, ledger and vendor
  names). They get no database session, no user and no society id, so the model cannot read or change records.
* Output is structured (validated against a schema) and then checked again by the caller: an answer may cite only the
  clauses it was given; an entry may use only the ledgers and vendors it was given.
* Any failure (no key, network, refusal, invalid output) returns None and the caller falls back to the deterministic
  path. Questions and clause text are not logged.
"""
import logging
import os
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
MODEL = "claude-opus-5-5"
TIMEOUT_S = 60.0


def configured() -> bool:
    """The deployment has an API key and the SDK is installed."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def enabled(settings) -> bool:
    """Configured, and this society's admin switched it on."""
    return configured() and getattr(settings, "llm_provider", "disabled") == PROVIDER


def _client():
    import anthropic
    return anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=2)


def _parse(system: str, user: str, schema, max_tokens: int = 4000):
    """One structured call. Returns the validated object or None.

    Server-side fallbacks are on (a refused request is retried on another model inside the same call). If the API
    rejects the fallbacks option itself, the call is repeated once without it rather than silently losing the feature."""
    import anthropic
    kwargs = dict(model=MODEL, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user}], output_format=schema)
    client = _client()
    try:
        try:
            response = client.beta.messages.parse(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                                  **kwargs)
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(getattr(exc, "message", exc)).lower():
                raise
            response = client.messages.parse(**kwargs)
    except anthropic.APIStatusError as exc:
        logger.warning("[accounts-agent] Claude request failed: HTTP %s", exc.status_code)
        return None
    except anthropic.APIConnectionError:
        logger.warning("[accounts-agent] Claude request failed: connection error")
        return None
    except Exception:  # noqa: BLE001 — never let the optional AI path break the feature
        logger.exception("[accounts-agent] Claude request failed")
        return None
    if response.stop_reason == "refusal":
        logger.info("[accounts-agent] Claude declined the request")
        return None
    return getattr(response, "parsed_output", None)


# ── Bye-law answers ──────────────────────────────────────────────────────────────────────────────────────────────────

class BylawAnswer(BaseModel):
    answer: str = Field(description="Plain-English answer, 2-6 sentences, citing clauses as [C1], [C2] …")
    cited: List[str] = Field(description="IDs of the clauses the answer relies on, e.g. ['C1', 'C3']")
    answered_by_sources: bool = Field(description="False if the given clauses do not answer the question")
    needs_professional_review: bool = Field(description="True when the answer depends on interpretation or facts "
                                                        "not in the clauses")


BYLAW_SYSTEM = (
    "You answer questions from a Maharashtra co-operative housing society's committee or members, using ONLY the "
    "bye-law clauses provided (and the society facts, when given). Rules:\n"
    "- Cite every statement with the clause IDs given, like [C2]. Never cite a clause you were not given, and never "
    "quote a bye-law number, section or rule from memory.\n"
    "- If the clauses do not answer the question, say so plainly and set answered_by_sources to false.\n"
    "- Clauses marked 'model bye-laws' apply to this society only if its registered bye-laws adopted them unchanged; "
    "say so when you rely on one.\n"
    "- Extracted clause text is unverified (it may come from OCR); do not present the answer as legal advice.\n"
    "- Be brief and practical. Write in the language of the question (English or Marathi)."
)


def answer_bylaw_question(question: str, clauses: List[dict], facts: Optional[str] = None) -> Optional[BylawAnswer]:
    """clauses: [{"id": "C1", "source": "Model bye-laws", "ref": "157", "heading": …, "page": 12, "text": …}]"""
    parts = []
    for c in clauses:
        parts.append(f"<clause id=\"{c['id']}\" source=\"{c['source']}\" ref=\"{c['ref']}\" page=\"{c.get('page') or ''}\">\n"
                     f"{c.get('heading') or ''}\n{c['text'][:4000]}\n</clause>")
    user = "<clauses>\n" + "\n".join(parts) + "\n</clauses>\n"
    if facts:
        user += f"<society_facts>\n{facts[:3000]}\n</society_facts>\n"
    user += f"<question>\n{question[:1000]}\n</question>"
    out = _parse(BYLAW_SYSTEM, user, BylawAnswer)
    return out if isinstance(out, BylawAnswer) else None


# ── Free-text entry requests ─────────────────────────────────────────────────────────────────────────────────────

class EntryParse(BaseModel):
    voucher_type: Literal["payment", "receipt", "journal"]
    amount: Optional[str] = Field(None, description="Amount in rupees as digits, e.g. '12000.00'")
    voucher_date: Optional[str] = Field(None, description="YYYY-MM-DD, only if the request states a date")
    vendor_id: Optional[str] = Field(None, description="ID from the vendor list, only if the request names one")
    ledger_id: Optional[str] = Field(None, description="ID from the ledger list: the expense (payment) or income "
                                                       "(receipt) ledger this entry belongs to")
    money_account: Literal["bank", "cash"] = "bank"
    reference: Optional[str] = Field(None, description="Bill / invoice / cheque / UPI reference if stated")
    narration: str = Field(description="Short narration for the voucher")
    unclear: List[str] = Field(default_factory=list, description="What the request does not make clear")


ENTRY_SYSTEM = (
    "You turn a housing society accountant's request into the fields of ONE accounting voucher. Use only the ledger "
    "and vendor IDs listed. Do not invent amounts, dates, vendors or references: leave a field empty and list it in "
    "'unclear' when the request does not state it. Payments to suppliers are 'payment'; money received is 'receipt'."
)


def parse_entry_request(text: str, ledgers: List[dict], vendors: List[dict], today: str) -> Optional[EntryParse]:
    """ledgers / vendors: [{"id": …, "name": …}] — this society's own, active ones."""
    lines = ["<ledgers>"] + [f"{x['id']}\t{x['name']}" for x in ledgers[:300]] + ["</ledgers>", "<vendors>"]
    lines += [f"{x['id']}\t{x['name']}" for x in vendors[:300]] + ["</vendors>", f"<today>{today}</today>",
                                                                   f"<request>\n{text[:1000]}\n</request>"]
    out = _parse(ENTRY_SYSTEM, "\n".join(lines), EntryParse, max_tokens=2000)
    return out if isinstance(out, EntryParse) else None
