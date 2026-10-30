"""Help assistant orchestration: scope → retrieval → (optional) provider → structured, bounded answer.

Security decisions (details in docs/HELP_ASSISTANT.md):
  * The caller's identity, permissions and society come from the authenticated User row, never from the request.
    `target_society_id` is only honoured for platform admins; anyone else naming another society is refused.
  * The assistant has no path to resident / financial / vendor records. Its only data access is diagnostics.py
    (counts and booleans). Diagnostics never reach the provider.
  * The provider sees the question and manual excerpts only. Sources, steps and gaps are built here.
"""
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import _user_has_permission
from app.core.services_catalog import effective_services
from app.core.tenant_scope import assert_society_access
from app.models.society import Society
from app.models.user import User
from app.modules.assistant import diagnostics, knowledge, provider as prov
from app.modules.assistant.schemas import (
    AskRequest, AskResponse, DiagnosticsRequest, DiagnosticsResponse, Finding, ProviderInfo, Source, StatusResponse,
)

logger = logging.getLogger(__name__)

_MANAGEMENT_QUESTIONS = [
    "How do I set up maintenance elements and link them to expense ledgers?",
    "What should I check before generating this month's maintenance bills?",
    "How do I add a vendor and set up TDS for them?",
    "How do I record an expense and get it approved?",
    "Why is the month-end checklist showing pending vouchers?",
    "How does the chart of accounts get set up for a new society?",
]
# Suggestions follow the person's audience, so a resident is not offered accounting set-up. Every one of them is checked
# in the tests to find a manual section.
SUGGESTED_BY_AUDIENCE = {
    "resident": [
        "How do I approve or reject a visitor?",
        "How do I raise a complaint?",
        "How do I book an amenity?",
        "How do I register my vehicle?",
    ],
    "security": [
        "How do I log a visitor at the gate?",
        "How do I check a vehicle at the gate?",
        "How do I log a parcel?",
    ],
    "staff": ["How do I see my duties for today?"],
}


def suggested_questions(audience: str) -> List[str]:
    return SUGGESTED_BY_AUDIENCE.get(audience, _MANAGEMENT_QUESTIONS)


ESCALATION = "Please ask your society manager or administrator, or contact DuxOS support."

# ── Rate limit (per user, in this process) ───────────────────────────────────

_hits: Dict[str, Deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()


def check_rate_limit(user_id) -> None:
    limit = settings.ASSISTANT_RATE_LIMIT_PER_MINUTE
    now = time.monotonic()
    with _hits_lock:
        q = _hits[str(user_id)]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= max(limit, 1):
            raise HTTPException(status_code=429, detail="You are asking too quickly. Please wait a minute and try again.",
                                headers={"Retry-After": str(int(60 - (now - q[0])) + 1)})
        q.append(now)


def reset_rate_limits() -> None:
    with _hits_lock:
        _hits.clear()


# ── Who is asking ────────────────────────────────────────────────────────────

_AUDIENCE_ROLES = {
    "platform_admin": ("committee",), "admin": ("committee", "manager"), "committee": ("committee", "manager"),
    "manager": ("manager",), "supervisor": ("manager",), "security": ("guard",), "staff": ("staff",),
    "resident": ("resident",),
}


def audience_of(user: User) -> str:
    """A label for the guidance to show, derived from the server-side permission grants (never from the client and
    never from the Flutter role mapping). It only steers which manual sections rank first; it grants nothing."""
    if getattr(user, "is_superadmin", False) and user.society_id is None:
        return "platform_admin"
    for code, label in (("admin", "admin"), ("admin_committee", "committee"), ("manager_above", "manager"),
                        ("supervisor_above", "supervisor"), ("security", "security"), ("any_staff", "staff")):
        if _user_has_permission(user, code):
            return label
    return "resident"


class Scope:
    def __init__(self, society_id: Optional[UUID], audience: str, can_diagnose: bool, needs_target: bool):
        self.society_id, self.audience, self.can_diagnose, self.needs_target = society_id, audience, can_diagnose, needs_target


def resolve_scope(db: Session, user: User, target_society_id: Optional[UUID]) -> Scope:
    audience = audience_of(user)
    if user.society_id is not None:
        if target_society_id is not None:
            assert_society_access(user, target_society_id)       # 403 when it is not the caller's own society
        return Scope(user.society_id, audience, _user_has_permission(user, "manager_above"), False)
    if getattr(user, "is_superadmin", False):
        if target_society_id is None:
            return Scope(None, audience, False, True)
        # Platform access in this codebase is all-or-nothing (the Platform Admin role / is_superadmin flag; there are no
        # per-society platform grants), so authorisation is the flag itself plus the society having to exist.
        if db.query(Society.id).filter(Society.id == target_society_id).first() is None:
            raise HTTPException(status_code=404, detail="Society not found")
        return Scope(target_society_id, audience, True, False)
    if target_society_id is not None:
        raise HTTPException(status_code=403, detail="Access denied to this society")
    return Scope(None, audience, False, False)                    # no society, not a platform admin: manuals only


# ── Input handling ───────────────────────────────────────────────────────────

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(s: str, limit: int) -> str:
    return re.sub(r"\s+", " ", _CTRL.sub(" ", s or "")).strip()[:limit]


def clean_output(s: str, limit: int) -> str:
    """Like clean_text but keeps line breaks, so a bulleted answer stays readable."""
    s = _CTRL.sub(" ", (s or "").replace("\r", "").replace("\t", " ").replace("\x00", ""))
    s = s.replace("\n", "\u0001")                      # _CTRL leaves \n alone; protect it from the space collapse
    s = re.sub(r"[ \u00a0]+", " ", s).replace("\u0001", "\n")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r" ?\n ?", "\n", s)).strip()[:limit]


_ENTITY_ID = (r"(\b(flat|unit|room|wing)\s*(no\.?|number)?\s*[a-z]?[-\s]?\d+\b|\b[a-z]-?\d{3,4}\b"
              r"|\b(vendor|resident|tenant|owner|member)\s+(named|called)\b)")
_RECORD = (r"\b(dues|balance|outstanding|arrears|payments?|paid|salary|phone|mobile|contact|e-?mail|address|owner|"
           r"invoice|ledger|pan|gst(in)?|bank details|account number|name)\b")
_ALL_OF = r"\b(all|every|each|list of|the)\s+(the\s+)?(residents?|tenants?|owners?|vendors?|members?|defaulters?|staff)\b|\bdefaulters\b"
_VERB = r"\b(list|show|give|export|dump|tell|send|reveal|display|print)\b"
_PROCEDURAL = re.compile(r"^\s*(how|where|what is the (process|procedure|way)|steps? to|can i|should i)\b", re.I)


def asks_for_records(question: str) -> bool:
    """True when the question asks the assistant to look up or list actual records. It has no access to any, so this
    only decides the wording of the refusal; disclosure is impossible regardless of what this returns."""
    q = question.lower()
    if _PROCEDURAL.search(q):
        return False
    if re.search(_ENTITY_ID, q) and re.search(_RECORD, q):
        return True
    return bool(re.search(_VERB, q) and re.search(_ALL_OF, q) and re.search(_RECORD + r"|\bdefaulters\b|\blist\b", q))


_FOLLOW_UP = re.compile(r"^\s*(and|also|what about|how about|then|why|so|it|that|this|those|them)\b", re.I)


def _leaf(section: str) -> str:
    return section.split(" › ")[-1].strip()


def _intro(chunk, steps) -> str:
    """One friendly line before the manual's own words. It only names the manual section; it adds no facts."""
    topic = _leaf(chunk.section)
    if len(steps) >= 2:
        return f"Here's how it works, from “{topic}” in the {chunk.title}. The steps are below:"
    return f"Here's what the {chunk.title} says under “{topic}”:"


_VAGUE_HEADINGS = {"who does what", "introduction", "quick answers", "good to know", "notes", "overview", "contents", "tips"}


def follow_ups_from(hits, asked: str, audience_roles: Tuple[str, ...] = ()) -> List[str]:
    """Other sections the search found, offered as questions to ask next. Each is the section's own heading, so asking
    it finds that section again."""
    out, out_topics, seen = [], [], {_leaf(hits[0][0].section).lower()}
    top_score = hits[0][1]
    for chunk, score in hits[1:]:
        if score < 0.65 * top_score:                      # a weak match is not a useful "next question"
            continue
        if audience_roles and not ({"all", *audience_roles} & set(chunk.roles)):
            continue                                      # a section written for another role (e.g. staff-only duties)
        topic = re.sub(r"^((\d+\.)*\d+[.)]?|Step \d+\s*[—-]|Part \d+\s*[—-])\s*", "", _leaf(chunk.section)).strip()
        if topic.lower() in seen or topic.lower() in _VAGUE_HEADINGS or len(topic) < 12 or len(topic) > 70 or topic.lower() in asked.lower() or re.search(r"\bapi\b|/api/", topic, re.I) \
                or any(topic.lower() in o.lower() or o.lower() in topic.lower() for o in out_topics):
            continue
        seen.add(topic.lower())
        out_topics.append(topic)
        out.append(f"Tell me about {topic}")
        if len(out) == 3:
            break
    return out


def _history_query(history, question: str, question_tokens: int) -> str:
    """The person's previous question, but only when this one cannot stand alone ("and then?", "why?"). A complete
    question is searched on its own: blending in an older topic would drag the answer towards it."""
    if question_tokens > 3 and not _FOLLOW_UP.match(question):
        return ""
    for t in reversed(history):
        if t.role == "user":
            return clean_text(t.content, settings.ASSISTANT_MAX_HISTORY_CHARS)
    return ""


# ── Public operations ────────────────────────────────────────────────────────

def new_request_id() -> str:
    return uuid.uuid4().hex


def _provider_info() -> Tuple[str, ProviderInfo]:
    mode = prov.provider_mode(settings.ASSISTANT_PROVIDER, settings.APP_ENV)
    return mode, ProviderInfo(mode=mode, status="disabled" if mode in ("disabled", "misconfigured") else "not_used")


def status(db: Session, user: User, request_id: str) -> StatusResponse:
    scope = resolve_scope(db, user, None)
    index = knowledge.get_index()
    _, info = _provider_info()
    return StatusResponse(
        request_id=request_id, enabled=settings.ASSISTANT_ENABLED, provider=info, audience=scope.audience,
        diagnostics_available=scope.can_diagnose or scope.needs_target, diagnostic_topics=list(diagnostics.TOPICS) if (scope.can_diagnose or scope.needs_target) else [],
        needs_target_society=scope.needs_target, index_version=index.version, document_count=len(index.documents),
        limits={"max_question_chars": settings.ASSISTANT_MAX_QUESTION_CHARS, "max_history_turns": settings.ASSISTANT_MAX_HISTORY_TURNS,
                "rate_limit_per_minute": settings.ASSISTANT_RATE_LIMIT_PER_MINUTE},
        suggested_questions=suggested_questions(scope.audience),
    )


def _require_enabled() -> None:
    if not settings.ASSISTANT_ENABLED:
        raise HTTPException(status_code=503, detail="The help assistant is switched off. Please use the Help guide.")


def run_checks(db: Session, scope: Scope, topics: List[str]) -> List[Finding]:
    return diagnostics.run_diagnostics(db, scope.society_id, topics, effective_services(db, scope.society_id))


def diagnose(db: Session, user: User, data: DiagnosticsRequest, request_id: str) -> DiagnosticsResponse:
    _require_enabled()
    check_rate_limit(user.id)
    scope = resolve_scope(db, user, data.target_society_id)
    if scope.needs_target:
        raise HTTPException(status_code=400, detail="Platform admins must choose a target society (target_society_id).")
    if not scope.can_diagnose or scope.society_id is None:
        raise HTTPException(status_code=403, detail="Configuration checks need manager-level access.")
    unknown = [t for t in data.topics if t not in diagnostics.TOPICS]
    if unknown:
        raise HTTPException(status_code=422, detail="Unknown diagnostic topic")
    topics = list(dict.fromkeys(data.topics)) or list(diagnostics.TOPICS)
    logger.info("assistant.diagnostics request=%s audience=%s topics=%d", request_id, scope.audience, len(topics))
    return DiagnosticsResponse(request_id=request_id, findings=run_checks(db, scope, topics))


def ask(db: Session, user: User, data: AskRequest, request_id: str) -> AskResponse:
    _require_enabled()
    check_rate_limit(user.id)
    question = clean_text(data.question, 10_000)
    if not question:
        raise HTTPException(status_code=422, detail="Please type a question.")
    if len(question) > settings.ASSISTANT_MAX_QUESTION_CHARS:
        raise HTTPException(status_code=422, detail=f"Please keep the question under {settings.ASSISTANT_MAX_QUESTION_CHARS} characters.")
    history = data.history[-settings.ASSISTANT_MAX_HISTORY_TURNS:]

    scope = resolve_scope(db, user, data.target_society_id)
    if data.include_diagnostics and scope.needs_target:
        raise HTTPException(status_code=400, detail="Platform admins must choose a target society (target_society_id).")

    index = knowledge.get_index()
    mode, info = _provider_info()
    base = dict(request_id=request_id, audience=scope.audience, index_version=index.version)

    if asks_for_records(question):
        return AskResponse(status="restricted", steps=[], sources=[], config_gaps=[], provider=info, **base,
            answer="I can't look up or list individual residents, dues, payments, vendors or other records. I only "
                   "explain how things work from the approved manuals.",
            uncertainty=None,
            escalation="For a specific record, open the relevant screen in the app (you will only see what your "
                       "role allows) or ask your society manager.")

    query = question + " " + _history_query(history, question, len(knowledge.tokenize(question)))
    hits = index.search(query, _AUDIENCE_ROLES.get(scope.audience, ()))

    gaps: List[Finding] = []
    notes: List[str] = []
    if data.include_diagnostics:
        if scope.can_diagnose and scope.society_id is not None:
            topics = diagnostics.topics_for_question(question) or list(diagnostics.TOPICS)
            gaps = [f for f in run_checks(db, scope, topics) if f.status != "ok"]
        else:
            notes.append("Live configuration checks need manager-level access, so none were run.")

    if not hits:
        logger.info("assistant.ask request=%s status=insufficient audience=%s qlen=%d", request_id, scope.audience, len(question))
        return AskResponse(status="insufficient_evidence", steps=[], sources=[], config_gaps=gaps, provider=info, **base,
            answer="I couldn't find this in the approved DuxOS manuals, so I won't guess.",
            uncertainty="No manual section matched your question closely enough.",
            escalation=" ".join(notes + [ESCALATION]))

    sources, seen = [], set()
    for chunk, _ in hits:
        key = (chunk.document, chunk.section)
        if key not in seen:
            seen.add(key)
            sources.append(Source(title=chunk.title, section=chunk.section, document=chunk.document, chunk_id=chunk.chunk_id))
    steps: List[str] = []
    for chunk, _ in hits[:2]:
        steps = knowledge.extract_steps(chunk.text)
        if len(steps) >= 2:                              # a lone numbered line is not a procedure
            break
        steps = []

    top_chunk, top_score = hits[0]
    answer, provider_status = None, info.status
    impl = prov.get_provider(settings.ASSISTANT_PROVIDER, settings.APP_ENV)
    if impl is not None:
        try:
            out = prov.call_with_timeout(
                impl, prov.ProviderRequest(question=question, excerpts=[c.text for c, _ in hits]),
                settings.ASSISTANT_PROVIDER_TIMEOUT_SECONDS)
            answer = clean_output(out, settings.ASSISTANT_MAX_ANSWER_CHARS)
            if not answer or knowledge.looks_like_injection(answer):
                answer, provider_status = None, "malformed"
            else:
                provider_status = "ok"
        except prov.ProviderError as exc:
            provider_status = str(exc) if str(exc) in ("timeout", "malformed") else "error"
    if answer is None:
        body = knowledge.lead_text(top_chunk.text)
        if len(steps) >= 2:                              # the steps are listed under the answer; do not say them twice
            body = "\n".join(l for l in body.splitlines() if not re.match(r"^\d+\.\s", l)).strip()
        answer = clean_output(f"{_intro(top_chunk, steps)}\n{body}", settings.ASSISTANT_MAX_ANSWER_CHARS)
    uncertainty = None
    if top_score < 6.0:
        uncertainty = "The closest manual sections only partly match your question; please confirm with your administrator."
    if impl is not None and provider_status != "ok":
        notes.append("The AI summary was unavailable, so the manual's own wording is shown.")
    logger.info("assistant.ask request=%s status=answered audience=%s provider=%s/%s sources=%d gaps=%d qlen=%d",
                request_id, scope.audience, mode, provider_status, len(sources), len(gaps), len(question))
    return AskResponse(status="answered", answer=answer, steps=steps, sources=sources, config_gaps=gaps,
                       follow_ups=follow_ups_from(hits, question, _AUDIENCE_ROLES.get(scope.audience, ())), uncertainty=uncertainty, escalation=" ".join(notes) or None,
                       provider=ProviderInfo(mode=mode, status=provider_status), **base)
