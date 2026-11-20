"""The versioned legal rule registry: which rule applies to a society on a date, conflicts between sources, and how
strongly a breach may be stated.

Hierarchy (Part 3) is applied with scope and applicability, never as a blind ranking:
- a rule only governs on the dates it was in force (effective_from / effective_until), so an older transaction is
  judged by the version in force on its own date;
- a society-level source (registered bye-law, resolution, policy) can never relax a statutory limit. A stricter
  society limit is honoured; a more permissive one is a LEGAL_SOURCE_CONFLICT sent for legal review;
- a society's own rule governs only once verified against an operative (verified, registered/approved) document;
- a model bye-law is a reference, never the society's registered bye-law;
- a draft never governs; a rejected source never governs;
- a rule named by an open blocking review can never yield a confirmed violation.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts_agent.legal.models import (
    JURISDICTION_MH, OPEN_REVIEW_STATUSES, OPERATIVE_DOCUMENT_STATUSES, VERIFIED, LegalDocument, LegalProfile,
    LegalReview, LegalRule,
)
from app.modules.accounts_agent.legal.seed import CENTRAL, REVIEW_PACK, RULE_PACK
from app.modules.accounts_agent.services import audit

STATUTORY = ("A", "B", "C")
SOCIETY_LEVELS = ("D", "E", "F", "G")
LEVEL_ORDER = "ABCDEFGH"
MAX_TYPES = ("max_pct", "max_amount")
MIN_TYPES = ("min_pct",)


# ── Seeding ────────────────────────────────────────────────────────────────────────────────────────────────────────

def ensure_jurisdiction_pack(db: Session) -> int:
    """Insert the shipped rule pack and review items that are missing. Idempotent; never overwrites an existing row
    (a verified or re-versioned rule stays as the reviewer left it)."""
    have = {(s, c, v) for s, c, v in db.query(LegalRule.scope, LegalRule.rule_code, LegalRule.version)
            .filter(LegalRule.society_id.is_(None))}
    added = 0
    for r in RULE_PACK:
        if (r["scope"], r["rule_code"], r["version"]) in have:
            continue
        db.add(LegalRule(society_id=None, **r))
        added += 1
    if added:
        db.flush()
        _link_versions(db)
    have_reviews = {k for (k,) in db.query(LegalReview.dedupe_key).filter(LegalReview.society_id.is_(None))}
    for rv in REVIEW_PACK:
        if rv["dedupe_key"] not in have_reviews:
            db.add(LegalReview(scope=JURISDICTION_MH, society_id=None, status="OPEN", **rv))
            added += 1
    db.flush()
    return added


def _link_versions(db: Session) -> None:
    rows = db.query(LegalRule).filter(LegalRule.society_id.is_(None)).order_by(LegalRule.rule_code, LegalRule.version).all()
    prev: Dict[tuple, LegalRule] = {}
    for r in rows:
        key = (r.scope, r.rule_code)
        if key in prev and prev[key].superseded_by_id is None:
            prev[key].superseded_by_id = r.id
        prev[key] = r


# ── Lookup ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def profile_for(db: Session, society_id: UUID) -> Optional[LegalProfile]:
    return db.query(LegalProfile).filter(LegalProfile.society_id == society_id).first()


def scopes_for(db: Session, society_id: UUID) -> List[str]:
    p = profile_for(db, society_id)
    return [CENTRAL, (p.jurisdiction if p else JURISDICTION_MH), str(society_id)]


def in_force(rule: LegalRule, on: date) -> bool:
    if rule.legal_status == "DRAFT" or rule.verification_status == "REJECTED_SOURCE":
        return False
    if rule.effective_from and rule.effective_from > on:
        return False
    if rule.effective_until and rule.effective_until < on:
        return False
    return True


def society_rule_operative(db: Session, rule: LegalRule) -> bool:
    """A society's own rule governs only when verified and its source document is operative and verified."""
    if rule.society_id is None:
        return True
    if rule.verification_status not in VERIFIED:
        return False
    doc = db.get(LegalDocument, rule.source_document_id) if rule.source_document_id else None
    return bool(doc and doc.society_id == rule.society_id and doc.status in OPERATIVE_DOCUMENT_STATUSES
                and doc.verification_status in VERIFIED)


def _open_blocking(db: Session, rule: LegalRule) -> List[LegalReview]:
    q = db.query(LegalReview).filter(LegalReview.status.in_(OPEN_REVIEW_STATUSES), LegalReview.blocking == True)  # noqa: E712
    q = q.filter(LegalReview.society_id.is_(None) | (LegalReview.society_id == rule.society_id)) if rule.society_id \
        else q.filter(LegalReview.society_id.is_(None))
    return [r for r in q.all() if rule.rule_code in (r.rule_codes or [])]


def blocking_reviews(db: Session, society_id: UUID, rule_code: str) -> List[LegalReview]:
    rows = (db.query(LegalReview).filter(LegalReview.status.in_(OPEN_REVIEW_STATUSES), LegalReview.blocking == True,  # noqa: E712
                                         (LegalReview.society_id.is_(None)) | (LegalReview.society_id == society_id))
            .all())
    return [r for r in rows if rule_code in (r.rule_codes or [])]


@dataclass
class Applicable:
    topic: str
    on: date
    rule: Optional[LegalRule] = None              # the governing rule
    effective_value: Optional[float] = None       # the figure to test against (stricter society limit honoured)
    candidates: List[LegalRule] = field(default_factory=list)
    not_operative: List[LegalRule] = field(default_factory=list)
    conflicts: List[dict] = field(default_factory=list)
    blocked_by: List[LegalReview] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_by)

    def value(self, key="value"):
        return (self.rule.calculation_method or {}).get(key) if self.rule else None


def resolve(db: Session, society_id: UUID, topic: str, on: date) -> Applicable:
    """The rule governing `topic` for this society on `on`, with every candidate and conflict found on the way."""
    scopes = scopes_for(db, society_id)
    rows = db.query(LegalRule).filter(LegalRule.scope.in_(scopes), LegalRule.topic == topic).all()
    out = Applicable(topic=topic, on=on)
    for r in rows:
        if r.society_id is not None and r.society_id != society_id:   # defensive: scope already restricts this
            continue
        if not in_force(r, on):
            continue
        if not society_rule_operative(db, r):
            out.not_operative.append(r)
            continue
        out.candidates.append(r)
    if not out.candidates:
        return out
    out.candidates.sort(key=lambda r: (LEVEL_ORDER.index(r.source_level), -(r.version or 1)))
    statutory = [r for r in out.candidates if r.source_level in STATUTORY]
    society = [r for r in out.candidates if r.source_level in SOCIETY_LEVELS]
    model = [r for r in out.candidates if r.source_level == "H"]

    # Two versions of one rule in force on the same day (overlapping dates) — a registry defect.
    by_code: Dict[str, List[LegalRule]] = {}
    for r in out.candidates:
        by_code.setdefault(f"{r.scope}:{r.rule_code}", []).append(r)
    for code, rs in by_code.items():
        if len(rs) > 1:
            out.conflicts.append({"type": "OVERLAPPING_VERSIONS", "rule_code": rs[0].rule_code,
                                  "versions": [x.version for x in rs],
                                  "explanation": f"{len(rs)} versions of {rs[0].rule_code} are in force on {on}. "
                                                 "Their effective dates overlap; the registry must be corrected."})
    governing = statutory[0] if statutory else (society[0] if society else model[0])
    out.rule = governing
    gtype = (governing.calculation_method or {}).get("type")
    gval = (governing.calculation_method or {}).get("value")
    out.effective_value = gval
    if statutory and society and gtype in MAX_TYPES + MIN_TYPES and gval is not None:
        for s in society:
            sval = (s.calculation_method or {}).get("value")
            if sval is None:
                continue
            looser = (sval > gval) if gtype in MAX_TYPES else (sval < gval)
            if looser:
                out.conflicts.append({
                    "type": "BYELAW_OVERRIDE_ATTEMPT", "rule_code": s.rule_code, "statutory_rule_code": governing.rule_code,
                    "society_value": sval, "statutory_value": gval,
                    "explanation": f"The society's {LEVEL_NAMES[s.source_level]} ({s.rule_code}, {sval}) is less strict "
                                   f"than {governing.rule_code} ({gval}). A bye-law or resolution cannot override the "
                                   "Act or Rules; the statutory figure is applied and the conflict is sent for review."})
            else:                       # stricter (or equal): the society's own, stricter figure is honoured
                out.effective_value = min(out.effective_value, sval) if gtype in MAX_TYPES else max(out.effective_value, sval)
    elif not statutory and society and model:
        sv, mv = (society[0].calculation_method or {}).get("value"), (model[0].calculation_method or {}).get("value")
        if sv is not None and mv is not None and sv != mv:
            out.conflicts.append({"type": "DIFFERS_FROM_MODEL", "rule_code": society[0].rule_code,
                                  "explanation": "The society's registered rule differs from the model bye-law figure. "
                                                 "The registered bye-law governs; the model figure is a reference only.",
                                  "society_value": sv, "model_value": mv, "blocking": False})
    out.blocked_by = blocking_reviews(db, society_id, governing.rule_code)
    return out


LEVEL_NAMES = {"A": "statute", "B": "Government direction", "C": "court order", "D": "registered bye-law",
               "E": "General Body resolution", "F": "Managing Committee resolution", "G": "internal policy",
               "H": "model bye-law"}


def classify(app: Applicable, *, deterministic: bool = True) -> str:
    """How strongly a breach of `app.rule` may be stated. Only a verified, binding, primary-source statutory rule with
    no open blocking review and a deterministic calculation gives a confirmed statutory failure."""
    r = app.rule
    if r is None:
        return "ADVISORY_OBSERVATION"
    if r.legal_status in ("ADVISORY", "MODEL_REFERENCE") or r.source_level == "H":
        return "ADVISORY_OBSERVATION"
    if r.source_level in ("E", "F", "G"):
        return "INTERNAL_POLICY_DEVIATION"
    if (r.source_level in STATUTORY and r.legal_status == "BINDING" and r.verification_status == "VERIFIED_PRIMARY_SOURCE"
            and not app.blocked and deterministic):
        return "CONFIRMED_STATUTORY_VALIDATION_FAILURE"
    return "POTENTIAL_NON_COMPLIANCE"


def source_ref(rule: Optional[LegalRule], app: Optional[Applicable] = None) -> Optional[dict]:
    """What a finding shows about its legal basis."""
    if rule is None:
        return None
    return {"rule_code": rule.rule_code, "version": rule.version, "title": rule.title,
            "source_level": rule.source_level, "source_level_name": LEVEL_NAMES.get(rule.source_level),
            "source": rule.source_document_title, "authority": rule.source_authority, "act_section": rule.act_section,
            "rule_number": rule.rule_number, "bye_law_number": rule.bye_law_number, "clause": rule.clause_reference,
            "page": rule.page_number, "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
            "effective_until": rule.effective_until.isoformat() if rule.effective_until else None,
            "legal_status": rule.legal_status, "verification_status": rule.verification_status,
            "verified": rule.verification_status in VERIFIED, "verification_note": rule.verification_note,
            "society_specific": rule.society_id is not None,
            "blocked_by_reviews": [r.title for r in (app.blocked_by if app else [])],
            "conflicts": (app.conflicts if app else []),
            "uncertainty": None if rule.verification_status == "VERIFIED_PRIMARY_SOURCE" else
            "This legal reference has not been verified against the original publication; treat the result as a "
            "potential issue for professional review."}


# ── Versioning and verification ────────────────────────────────────────────────────────────────────────────────────

RULE_FIELDS = ("topic", "rule_category", "title", "source_level", "source_document_id", "source_document_title",
               "source_authority", "act_section", "rule_number", "bye_law_number", "clause_reference", "page_number",
               "original_text", "translated_text", "publication_date", "effective_from", "effective_until",
               "legal_status", "applicability_conditions", "calculation_method", "validation_expression",
               "required_evidence", "severity", "human_review_required", "society_type")


def new_version(db: Session, rule: LegalRule, changes: dict, user, note: str) -> LegalRule:
    """A changed provision is a new version. The old version is closed the day before the new one takes effect and
    pointed at its successor; it is never edited otherwise."""
    if rule.superseded_by_id:
        raise HTTPException(409, "Only the latest version of a rule can be revised")
    eff = changes.get("effective_from")
    if not eff:
        raise HTTPException(422, "A new version needs the date it takes effect (effective_from)")
    if rule.effective_from and eff <= rule.effective_from:
        raise HTTPException(422, "The new version must take effect after the current version")
    data = {f: getattr(rule, f) for f in RULE_FIELDS}
    data.update({k: v for k, v in changes.items() if k in RULE_FIELDS})
    nv = LegalRule(scope=rule.scope, society_id=rule.society_id, rule_code=rule.rule_code, version=(rule.version or 1) + 1,
                   jurisdiction=rule.jurisdiction, verification_status="PENDING_VERIFICATION", change_note=note,
                   created_by=user.id, **data)
    if nv.legal_status == "SUPERSEDED":
        nv.legal_status = "UNVERIFIED"
    db.add(nv)
    db.flush()
    rule.superseded_by_id = nv.id
    rule.effective_until = eff - timedelta(days=1)
    rule.legal_status = "SUPERSEDED"
    sid = rule.society_id or user.society_id
    if sid:
        audit.record(db, sid, "legal_rule_versioned", "legal_rule", nv.id, user.id,
                     {"rule_code": rule.rule_code, "from_version": rule.version, "to_version": nv.version})
    return nv


def verify_rule(db: Session, rule: LegalRule, user, status: str, note: str, legal_status: Optional[str],
                source_document_id: Optional[UUID], page_number: Optional[str]) -> LegalRule:
    if status not in ("VERIFIED_PRIMARY_SOURCE", "VERIFIED_SECONDARY_SOURCE", "LEGAL_REVIEW_REQUIRED",
                      "REJECTED_SOURCE", "PENDING_VERIFICATION"):
        raise HTTPException(422, "Unknown verification status")
    if rule.society_id is None and user.society_id is not None:
        raise HTTPException(403, "Jurisdiction-wide law can only be verified by a platform administrator")
    if rule.society_id is not None and user.society_id not in (None, rule.society_id):
        raise HTTPException(404, "Rule not found")
    if status in VERIFIED:
        if _open_blocking(db, rule):
            raise HTTPException(409, "An open legal review blocks this rule. Resolve the review first.")
        doc_id = source_document_id or rule.source_document_id
        doc = db.get(LegalDocument, doc_id) if doc_id else None
        if doc is None:
            raise HTTPException(422, "Verification needs the source document the rule was checked against")
        if doc.society_id not in (None, rule.society_id):
            raise HTTPException(422, "The source document belongs to another society")
        if doc.verification_status not in VERIFIED:
            raise HTTPException(422, "The source document itself has not been verified")
        if rule.society_id is not None and doc.status not in OPERATIVE_DOCUMENT_STATUSES:
            raise HTTPException(422, f"The source document is {doc.status.lower()}; only a registered or approved "
                                     "document can govern compliance")
        if status == "VERIFIED_PRIMARY_SOURCE" and not doc.is_primary_source:
            raise HTTPException(422, "A primary-source verification needs the original government publication; "
                                     "this document is not marked as a primary source")
        if not (page_number or rule.page_number):
            raise HTTPException(422, "Record the page the clause was verified on")
        rule.source_document_id, rule.source_document_title = doc.id, doc.title
        if page_number:
            rule.page_number = page_number
        rule.last_verified_at, rule.verified_by = datetime.utcnow(), user.id
    if legal_status:
        if legal_status not in ("BINDING", "CONDITIONAL", "ADVISORY", "MODEL_REFERENCE", "DRAFT", "UNVERIFIED"):
            raise HTTPException(422, "Unknown legal status")
        if legal_status == "BINDING" and status not in VERIFIED:
            raise HTTPException(422, "A rule can only be marked binding once it is verified")
        rule.legal_status = legal_status
    rule.verification_status, rule.verification_note = status, note
    return rule


# ── Conflict detection ─────────────────────────────────────────────────────────────────────────────────────────────

def topics_for(db: Session, society_id: UUID) -> List[str]:
    return sorted({t for (t,) in db.query(LegalRule.topic).filter(LegalRule.scope.in_(scopes_for(db, society_id)))})


def detect_conflicts(db: Session, society_id: UUID, on: date) -> List[LegalReview]:
    """Open (or refresh) a society-scoped review for each conflict found today. Never resolves anything."""
    made = []
    for topic in topics_for(db, society_id):
        app = resolve(db, society_id, topic, on)
        for c in app.conflicts:
            if c.get("blocking") is False:
                continue
            key = f"conflict:{topic}:{c['type']}:{c.get('rule_code')}"[:200]
            row = db.query(LegalReview).filter(LegalReview.scope == str(society_id), LegalReview.dedupe_key == key).first()
            if row is None:
                row = LegalReview(scope=str(society_id), society_id=society_id, dedupe_key=key,
                                  review_type="BYELAW_OVERRIDE_ATTEMPT" if c["type"] == "BYELAW_OVERRIDE_ATTEMPT" else "SOURCE_CONFLICT",
                                  title=f"Conflicting legal sources for {topic}", description=c["explanation"],
                                  rule_codes=[x for x in (c.get("rule_code"), c.get("statutory_rule_code")) if x],
                                  details=c, blocking=True, status="OPEN")
                db.add(row)
                db.flush()
                audit.record(db, society_id, "legal_conflict_detected", "legal_review", row.id, details={"topic": topic})
            made.append(row)
    return made


def rule_dict(r: LegalRule, detail: bool = False) -> dict:
    d = {"id": str(r.id), "rule_code": r.rule_code, "version": r.version, "topic": r.topic, "title": r.title,
         "rule_category": r.rule_category, "jurisdiction": r.jurisdiction, "society_specific": r.society_id is not None,
         "source_level": r.source_level, "source_level_name": LEVEL_NAMES.get(r.source_level),
         "source_document_id": str(r.source_document_id) if r.source_document_id else None,
         "source_document_title": r.source_document_title, "source_authority": r.source_authority,
         "act_section": r.act_section, "rule_number": r.rule_number, "bye_law_number": r.bye_law_number,
         "clause_reference": r.clause_reference, "page_number": r.page_number,
         "publication_date": r.publication_date.isoformat() if r.publication_date else None,
         "effective_from": r.effective_from.isoformat() if r.effective_from else None,
         "effective_until": r.effective_until.isoformat() if r.effective_until else None,
         "legal_status": r.legal_status, "verification_status": r.verification_status,
         "calculation_method": r.calculation_method, "severity": r.severity,
         "human_review_required": r.human_review_required,
         "superseded_by_id": str(r.superseded_by_id) if r.superseded_by_id else None,
         "last_verified_at": r.last_verified_at.isoformat() if r.last_verified_at else None,
         "verification_note": r.verification_note, "change_note": r.change_note}
    if detail:
        d.update({"original_text": r.original_text, "translated_text": r.translated_text,
                  "applicability_conditions": r.applicability_conditions, "validation_expression": r.validation_expression,
                  "required_evidence": r.required_evidence})
    return d


def review_dict(r: LegalReview) -> dict:
    return {"id": str(r.id), "society_specific": r.society_id is not None, "review_type": r.review_type, "title": r.title,
            "description": r.description, "rule_codes": r.rule_codes, "document_ids": r.document_ids, "details": r.details,
            "blocking": r.blocking, "status": r.status, "decision": r.decision, "decision_note": r.decision_note,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None, "created_at": r.created_at.isoformat()}
