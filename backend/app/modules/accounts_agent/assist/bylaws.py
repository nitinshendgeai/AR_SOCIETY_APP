"""Questions answered from the bye-laws in the Legal Library, with clause references.

Sources, in order of authority: the society's own registered bye-laws and amendments, then the model bye-laws
(which apply only where the registered bye-laws adopted them). The app finds the relevant clauses itself (keyword
search over the extracted clause text); Claude, when enabled, only words the answer from those clauses and may cite
nothing else. Without Claude the answer lists the clauses found. Nothing is ever cited that is not in the library.

Tokens are spent only when they add something (token_guard.py): the question is cleaned and its Hindi / Marathi words
mapped locally (prompt_opt.py); a question about the society's own figures is answered from the books; an earlier
answer to the same question on the same clauses is reused; and over the monthly budget the clauses are listed instead.
When a request is sent it carries the three best clauses cut to their relevant sentences, and no society figures.
"""
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts_agent.assist import claude, prompt_opt, token_guard
from app.modules.accounts_agent.legal.models import LegalClause, LegalDocument
from app.modules.accounts_agent.services import audit

SOCIETY_TYPES = ("REGISTERED_BYELAWS", "BYELAW_AMENDMENT")
MODEL_TYPES = ("MODEL_BYELAWS",)
TOP_K = 6
AI_K = 3                      # clauses sent to the AI (the best ones; the rest are still listed for the reader)
AI_CLAUSE_CHARS = 1200        # each sent clause is cut to its relevant sentences, at most this long
FEATURE = "bylaw_answer"
# Words that mean the person asks what the rules say (not only what the books show).
_RULE_WORDS = set("""rule rules bye-law bye-laws bylaw bylaws byelaw byelaws clause allowed allow permitted permit can
may must should shall required require legal law notice quorum procedure process eligible eligibility entitled right
rights penalty fine limit maximum minimum days period nomination transfer election tenant licence non-occupancy
नियम कायदा उपविधी उपनियम परवानगी अनुमति अधिकार नोटीस सूचना niyam kayda""".split())
SOURCE_NAMES = {"REGISTERED_BYELAWS": "Registered bye-laws", "BYELAW_AMENDMENT": "Bye-law amendment",
                "MODEL_BYELAWS": "Model bye-laws"}

_STOP = set("""a an the of to in on for and or is are was were be been can could should would may might shall will
do does did our we us you your i me my it its this that these those what which who whom how when where why with by
from as at about into than then there their them any all if not no yes per under over also such each other more most
society societies member members""".split())
# A few everyday words → the words bye-laws use.
_SYNONYMS = {
    "agm": ["annual", "general", "meeting"], "sgm": ["special", "general", "meeting"],
    "meeting": ["meeting"], "notice": ["notice"], "dues": ["dues", "arrears", "charges"],
    "defaulter": ["defaulter", "arrears", "default"], "interest": ["interest", "arrears"],
    "penalty": ["interest", "penalty", "fine"], "fine": ["fine", "penalty"],
    "rent": ["let", "leave", "licence", "non-occupancy"], "rented": ["let", "leave", "licence", "non-occupancy"],
    "tenant": ["licensee", "leave", "licence", "occupant"], "nonoccupancy": ["non-occupancy"],
    "sinking": ["sinking", "fund"], "repair": ["repairs", "maintenance", "fund"], "repairs": ["repairs", "maintenance"],
    "transfer": ["transfer", "premium", "shares"], "sale": ["transfer", "shares"], "sell": ["transfer", "shares"],
    "parking": ["parking", "vehicle"], "committee": ["committee", "managing"], "election": ["election", "elected"],
    "audit": ["audit", "auditor"], "budget": ["budget", "expenditure"], "spend": ["expenditure", "limit"],
    "expense": ["expenditure", "expenses"], "pet": ["pets", "animals"], "nomination": ["nomination", "nominee"],
}
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*|[ऀ-ॿ]+")


def tokens(text: str) -> List[str]:
    out = []
    for t in _TOKEN.findall((text or "").lower()):
        if t in _STOP or len(t) < 2:
            continue
        out.append(t)
        out.extend(_SYNONYMS.get(t.replace("-", ""), []))
    return out


def _documents(db: Session, society_id: UUID) -> List[LegalDocument]:
    return (db.query(LegalDocument)
            .filter(LegalDocument.document_type.in_(SOCIETY_TYPES + MODEL_TYPES),
                    LegalDocument.status.notin_(("REJECTED", "SUPERSEDED")),
                    (LegalDocument.society_id == society_id) | (LegalDocument.society_id.is_(None)))
            .all())


def search(db: Session, society_id: UUID, question: str, k: int = TOP_K) -> List[dict]:
    """The clauses that best match the question (BM25 over clause heading + text), society bye-laws first."""
    docs = {d.id: d for d in _documents(db, society_id)}
    if not docs:
        return []
    clauses = db.query(LegalClause).filter(LegalClause.document_id.in_(list(docs))).all()
    q = Counter(tokens(question))
    if not q or not clauses:
        return []
    bags = [Counter(tokens(f"{c.heading or ''} {c.clause_ref} {c.text}")) for c in clauses]
    n = len(bags)
    avg = sum(sum(b.values()) for b in bags) / n or 1.0
    df: Dict[str, int] = Counter()
    for b in bags:
        for t in set(b):
            df[t] += 1
    scored: List[Tuple[float, LegalClause]] = []
    for c, b in zip(clauses, bags):
        length = sum(b.values()) or 1
        s = 0.0
        for t, qn in q.items():
            if t not in b:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            tf = b[t]
            s += qn * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / avg))
        if s <= 0:
            continue
        if docs[c.document_id].document_type in SOCIETY_TYPES:
            s *= 1.25                                  # the society's own bye-laws outrank the model text
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][0] if scored else 0
    out = []
    for s, c in scored[:k]:
        if s < best * 0.25:
            break
        d = docs[c.document_id]
        out.append({"clause_id": str(c.id), "document_id": str(d.id), "document_title": d.title,
                    "source_type": d.document_type, "source": SOURCE_NAMES.get(d.document_type, d.document_type),
                    "society_specific": d.society_id is not None, "document_status": d.status,
                    "document_verified": (d.verification_status or "").startswith("VERIFIED"),
                    "clause_verified": bool(c.verified), "clause_ref": c.clause_ref, "heading": c.heading,
                    "page": c.page_number, "language": c.language, "text": c.text, "score": round(s, 3)})
    return out


def _facts(db: Session, society_id: UUID, question: str) -> Optional[str]:
    """The society's own figures for questions the deterministic assistant understands (dues, funds, approvals …)."""
    from app.modules.accounts_agent.legal import assistant
    try:
        r = assistant.ask(db, society_id, question)
    except Exception:  # noqa: BLE001
        return None
    return r.get("answer") if r.get("intent") else None


def _asks_about_rules(q: "prompt_opt.OptimizedQuery") -> bool:
    words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*|[\u0900-\u097F]+", q.text.lower())) | set(q.keywords)
    return bool(words & _RULE_WORDS)


def _ai_answer(db: Session, society_id: UUID, q: "prompt_opt.OptimizedQuery", found: List[dict], settings):
    """(answer or None, how it was obtained, a note for the reader or None, the reuse key). Decides whether a request is worth
    sending, and sends the smallest one that can answer."""
    best = found[0]["score"] if found else 0
    chosen = [f for f in found[:AI_K] if f["score"] >= best * 0.4]
    words = prompt_opt._WORD.findall(q.text.lower()) + q.keywords
    payload = [{"id": f"C{found.index(f) + 1}",
                "source": f["source"] + ("" if f["society_specific"] else " (model bye-laws)"),
                "ref": f["clause_ref"], "heading": f["heading"], "page": f["page"],
                "text": prompt_opt.relevant_excerpt(f["text"], words, AI_CLAUSE_CHARS)} for f in chosen]
    # The key covers the question's words, the clauses chosen and their exact text, so an edited clause asks afresh.
    key = q.key([f["clause_id"] for f in chosen], [_digest(p["text"]) for p in payload], [q.language])
    kept = token_guard.reuse(db, society_id, FEATURE, key)
    if kept:
        token_guard.note(db, society_id, FEATURE, "reused_answers")
        try:
            return claude.BylawAnswer(**kept), "saved_answer", "Same question answered before: no AI tokens used.", key
        except Exception:  # noqa: BLE001 — a kept answer that no longer fits the schema is simply asked afresh
            pass
    estimate = token_guard.estimate_tokens(claude.BYLAW_SYSTEM, claude.bylaw_prompt(q.text, payload),
                                           reply=claude.BYLAW_MAX_TOKENS // 2)
    ok, why, message = token_guard.check(db, society_id, settings, estimate)
    if not ok:
        token_guard.note(db, society_id, FEATURE, why)
        return None, "library", message, key
    ai = claude.answer_bylaw_question(q.text, payload, None)
    token_guard.record_call(db, society_id, FEATURE, claude.take_usage(), ok=ai is not None)
    return ai, "ai", None, key


def _digest(text: str) -> str:
    import hashlib
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def ask(db: Session, society_id: UUID, question: str, user, settings) -> dict:
    question = (question or "").strip()
    q = prompt_opt.normalize(question)
    found = search(db, society_id, q.search_text)
    has_library = bool(_documents(db, society_id))
    facts = _facts(db, society_id, question)
    sources = [{**f, "cite": f"C{i + 1}"} for i, f in enumerate(found)]
    ai_used, ai, answered_from, token_note, key = False, None, "library", None, None
    if sources and claude.enabled(settings):
        if facts and not _asks_about_rules(q):
            # A question about the society's own figures: the books answer it; wording clauses would add nothing.
            token_guard.note(db, society_id, FEATURE, "answered_locally")
            token_note = "Answered from your society's books: no AI tokens used."
        else:
            ai, answered_from, token_note, key = _ai_answer(db, society_id, q, found, settings)
    if ai is not None:
        valid = {s["cite"] for s in sources}
        cited = [c for c in ai.cited if c in valid]
        if ai.cited and not cited:
            ai, answered_from = None, "library"          # cited only things it was not given: not used
        else:
            ai_used = True
            if answered_from == "ai" and key:
                token_guard.keep(db, society_id, FEATURE, key, ai.model_dump())    # the next asker pays nothing
            answer, cited_set = ai.answer, set(cited)
            sources = [{**s, "cited": s["cite"] in cited_set} for s in sources]
            answered = ai.answered_by_sources and bool(cited)
            review = ai.needs_professional_review
    if not ai_used:
        answered_from = "library"
        if sources:
            answer = ("These bye-law clauses are the closest match to your question. Read them in full; the app "
                      "does not interpret them for you.")
        elif has_library:
            answer = "No clause in the bye-laws in the Legal Library matches this question."
        else:
            answer = ("No bye-laws are in the Legal Library yet. The platform administrator uploads the model "
                      "bye-laws once for every society; your committee uploads the society's registered bye-laws "
                      "(Accounts Agent → Legal Library). Questions can then be answered with clause references.")
        sources = [{**s, "cited": True} for s in sources]
        answered, review = bool(sources), True
    only_model = bool(sources) and not any(s["society_specific"] for s in sources if s["cited"])
    unverified = any(not (s["document_verified"] and s["clause_verified"]) for s in sources if s["cited"])
    notes = []
    if only_model:
        notes.append("Based on the model bye-laws: they apply to your society only if its registered bye-laws adopted "
                     "them unchanged. Check your registered bye-laws.")
    if unverified:
        notes.append("The clause text was extracted from an uploaded copy and has not been checked against the "
                     "original: verify it before relying on it.")
    audit.record(db, society_id, "bylaw_question", "society", society_id, getattr(user, "id", None),
                 {"question": question[:200], "clauses": [s["clause_id"] for s in sources if s["cited"]],
                  "ai": ai_used})
    db.commit()
    return {"question": question, "answer": answer, "answered_by_sources": answered,
            "needs_professional_review": review, "ai_generated": ai_used,
            "answered_from": answered_from, "token_note": token_note, "language": q.language,
            "ai_available": claude.enabled(settings) and token_guard.plans.entitlement(db, society_id, settings)["allowed"],
            "notes": notes, "society_facts": facts,
            "sources": [{k: v for k, v in s.items() if k != "score"} for s in sources],
            "disclaimer": "Not legal advice. Answers come only from the bye-laws in the Legal Library"
                          + (" and were worded by an AI model (Claude) from the clauses shown." if ai_used else ".")}
