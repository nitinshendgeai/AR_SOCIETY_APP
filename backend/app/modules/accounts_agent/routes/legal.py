"""Accounts Agent — legal profile, document library, rule registry, legal reviews, resolutions, budgets, compliance
scan and calendar, recovery readiness and the question assistant.

Society scoping: the society always comes from the authenticated user (platform admins must name one). Jurisdiction-wide
law (society_id NULL) is readable by every society and writable only by a platform administrator. Nothing here can
change an accounting record.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin_committee, require_manager_above, require_platform_admin
from app.core.tenant_scope import resolve_create_society_id
from app.db.session import get_db
from app.models.user import User
from app.modules.accounts.models.accounts import Account
from app.modules.accounts_agent.legal import assistant, calendar as cal, compliance, documents, recovery, registry, sections
from app.modules.accounts_agent.legal import resolutions as res_svc
from app.modules.accounts_agent.legal.models import (
    OPEN_REVIEW_STATUSES, SOURCE_LEVELS, VERIFIED, BudgetLine, ComplianceItem, LegalClause, LegalDocument,
    LegalProfile, LegalReview, LegalRule, SocietyResolution,
)
from app.modules.accounts_agent.models.agent import OPEN_FINDING_STATUSES, UNIFIED_CLASS, AgentFinding, AgentProposal
from app.modules.accounts_agent.services import audit, notify
from app.modules.accounts_agent.services.learning import WINDOW_MONTHS
from app.utils.local_time import society_today

router = APIRouter(prefix="/accounts-agent", tags=["Accounts Agent — Legal & Compliance"])


def _sid(user: User, society_id: Optional[UUID]) -> UUID:
    return resolve_create_society_id(user, society_id)


# ── Schemas ────────────────────────────────────────────────────────────────────────────────────────────────────────

class ProfileIn(BaseModel):
    registration_number: Optional[str] = Field(None, max_length=100)
    society_name: Optional[str] = Field(None, max_length=255)
    registration_date: Optional[date] = None
    classification: Optional[str] = Field(None, max_length=80)
    society_type: Optional[str] = Field(None, pattern="^(housing)$")
    number_of_units: Optional[int] = Field(None, ge=0, le=100000)
    number_of_members: Optional[int] = Field(None, ge=0, le=100000)
    district: Optional[str] = Field(None, max_length=100)
    financial_year_start_month: Optional[int] = Field(None, ge=1, le=12)
    adopted_model_bylaw_version: Optional[str] = Field(None, max_length=60)
    last_legal_review_date: Optional[date] = None


class DocVerifyIn(BaseModel):
    status: str
    verification_status: str
    note: str = Field(..., min_length=3, max_length=2000)
    issue_date: Optional[date] = None
    approval_date: Optional[date] = None
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    override_draft_warning: Optional[str] = Field(None, max_length=500)


class RuleIn(BaseModel):
    rule_code: str = Field(..., min_length=3, max_length=60, pattern=r"^[A-Za-z0-9\-_.]+$")
    topic: str = Field(..., min_length=3, max_length=80)
    rule_category: str = Field(..., max_length=40)
    title: str = Field(..., min_length=3, max_length=300)
    source_level: str = Field(..., pattern="^[DEFG]$")
    source_document_id: UUID
    bye_law_number: Optional[str] = Field(None, max_length=60)
    clause_reference: Optional[str] = Field(None, max_length=120)
    page_number: Optional[str] = Field(None, max_length=30)
    original_text: Optional[str] = Field(None, max_length=20000)
    translated_text: Optional[str] = Field(None, max_length=20000)
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    calculation_method: Optional[dict] = None
    required_evidence: Optional[List[str]] = None
    severity: str = Field("MEDIUM", pattern="^(CRITICAL|HIGH|MEDIUM|LOW|INFORMATIONAL)$")


class RuleVersionIn(BaseModel):
    effective_from: date
    change_note: str = Field(..., min_length=3, max_length=2000)
    calculation_method: Optional[dict] = None
    original_text: Optional[str] = Field(None, max_length=20000)
    translated_text: Optional[str] = Field(None, max_length=20000)
    clause_reference: Optional[str] = Field(None, max_length=120)
    page_number: Optional[str] = Field(None, max_length=30)
    source_document_id: Optional[UUID] = None
    title: Optional[str] = Field(None, max_length=300)


class RuleVerifyIn(BaseModel):
    verification_status: str
    note: str = Field(..., min_length=3, max_length=2000)
    legal_status: Optional[str] = None
    source_document_id: Optional[UUID] = None
    page_number: Optional[str] = Field(None, max_length=30)


class ReviewDecisionIn(BaseModel):
    status: str = Field(..., pattern="^(IN_REVIEW|RESOLVED|DISMISSED)$")
    decision: Optional[str] = Field(None, max_length=40)
    note: str = Field(..., min_length=3, max_length=4000)


class ResolutionIn(BaseModel):
    resolution_number: Optional[str] = Field(None, max_length=60)
    meeting_type: Optional[str] = None
    meeting_date: Optional[date] = None
    notice_date: Optional[date] = None
    agenda: Optional[str] = Field(None, max_length=8000)
    attendance: Optional[int] = Field(None, ge=0)
    quorum_required: Optional[int] = Field(None, ge=0)
    votes_for: Optional[int] = Field(None, ge=0)
    votes_against: Optional[int] = Field(None, ge=0)
    votes_abstain: Optional[int] = Field(None, ge=0)
    approval_authority: Optional[str] = None
    category: Optional[str] = None
    purpose: Optional[str] = Field(None, max_length=8000)
    approved_amount: Optional[Decimal] = Field(None, ge=0, max_digits=14, decimal_places=2)
    vendor_id: Optional[UUID] = None
    account_id: Optional[UUID] = None
    work_order_id: Optional[UUID] = None
    contract_id: Optional[UUID] = None
    conditions: Optional[str] = Field(None, max_length=4000)
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    supporting_document_id: Optional[UUID] = None
    supersedes_id: Optional[UUID] = None


class VerifyNote(BaseModel):
    note: Optional[str] = Field(None, max_length=2000)


class BudgetLineIn(BaseModel):
    account_id: UUID
    approved_amount: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2)
    resolution_id: Optional[UUID] = None
    note: Optional[str] = Field(None, max_length=500)


class BudgetIn(BaseModel):
    fiscal_year: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    lines: List[BudgetLineIn] = Field(..., max_length=500)


class CalendarItemIn(BaseModel):
    applicability: Optional[str] = None
    applicability_reason: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[date] = None
    due_date_basis: Optional[str] = Field(None, max_length=1000)
    completion_status: Optional[str] = None
    completed_on: Optional[date] = None
    evidence_ref: Optional[str] = Field(None, max_length=200)
    responsible_role: Optional[str] = Field(None, max_length=60)


class SignOffIn(BaseModel):
    role: str = Field(..., pattern="^(COMMITTEE|AUDITOR)$")
    note: str = Field(..., min_length=3, max_length=500)
    fingerprint: str = Field(..., min_length=64, max_length=64)


class AskIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


# ── Legal profile ──────────────────────────────────────────────────────────────────────────────────────────────────

def _profile(db: Session, sid: UUID) -> LegalProfile:
    from app.models.society import Society
    from app.modules.vendor.services.work_orders import member_count
    p = registry.profile_for(db, sid)
    if p is None:
        soc = db.get(Society, sid)
        p = LegalProfile(society_id=sid, society_name=soc.name if soc else None,
                         registration_number=soc.registration_number if soc else None, state=soc.state if soc else None,
                         number_of_units=member_count(db, sid))
        db.add(p)
        db.flush()
    return p


def _profile_dict(db: Session, p: LegalProfile) -> dict:
    bylaw = db.get(LegalDocument, p.registered_bylaw_document_id) if p.registered_bylaw_document_id else None
    return {"society_id": str(p.society_id), "registration_number": p.registration_number, "society_name": p.society_name,
            "registration_date": p.registration_date.isoformat() if p.registration_date else None,
            "classification": p.classification, "society_type": p.society_type, "number_of_units": p.number_of_units,
            "number_of_members": p.number_of_members, "state": p.state, "district": p.district,
            "jurisdiction": p.jurisdiction, "financial_year_start_month": p.financial_year_start_month,
            "registered_bylaw": documents.document_dict(bylaw) if bylaw else None,
            "registered_bylaw_version": p.registered_bylaw_version, "approved_amendments": p.approved_amendments or [],
            "adopted_model_bylaw_version": p.adopted_model_bylaw_version,
            "legal_verification_status": p.legal_verification_status,
            "last_legal_review_date": p.last_legal_review_date.isoformat() if p.last_legal_review_date else None}


@router.get("/legal/profile")
def get_profile(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    p = _profile(db, sid)
    db.commit()
    return _profile_dict(db, p)


@router.put("/legal/profile")
def put_profile(data: ProfileIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    p = _profile(db, sid)
    changes = data.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    p.updated_by = user.id
    # A profile edit is a claim, not a verification: it needs a fresh legal review.
    p.legal_verification_status = "PENDING_VERIFICATION"
    audit.record(db, sid, "legal_profile_updated", "legal_profile", p.id, user.id, {"fields": sorted(changes)})
    db.commit()
    return _profile_dict(db, p)


# ── Document library ───────────────────────────────────────────────────────────────────────────────────────────────

def _visible_doc(db: Session, sid: UUID, doc_id: UUID) -> LegalDocument:
    d = db.get(LegalDocument, doc_id)
    if d is None or (d.society_id is not None and d.society_id != sid):
        raise HTTPException(404, "Document not found")
    return d


@router.get("/legal/documents")
def list_documents(society_id: Optional[UUID] = None, scope: str = Query("all", pattern="^(all|society|jurisdiction)$"),
                   document_type: Optional[str] = None, status: Optional[str] = None,
                   db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    q = db.query(LegalDocument)
    if scope == "society":
        q = q.filter(LegalDocument.society_id == sid)
    elif scope == "jurisdiction":
        q = q.filter(LegalDocument.society_id.is_(None))
    else:
        q = q.filter((LegalDocument.society_id == sid) | LegalDocument.society_id.is_(None))
    if document_type:
        q = q.filter(LegalDocument.document_type == document_type)
    if status:
        q = q.filter(LegalDocument.status == status)
    return [documents.document_dict(d) for d in q.order_by(LegalDocument.created_at.desc()).limit(500)]


async def _read(file: UploadFile) -> bytes:
    data = await file.read(documents.MAX_BYTES + 1)
    if len(data) > documents.MAX_BYTES:
        raise HTTPException(413, "The file is larger than 15 MB")
    return data


@router.post("/legal/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), document_type: str = Form(...), title: str = Form(..., max_length=300),
                          requested_status: Optional[str] = Form(None), reference_number: Optional[str] = Form(None),
                          source_authority: Optional[str] = Form(None), issue_date: Optional[date] = Form(None),
                          approval_date: Optional[date] = Form(None), effective_from: Optional[date] = Form(None),
                          society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                          user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    data = await _read(file)
    d = documents.upload(db, society_id=sid, user=user, file_name=file.filename or "document", data=data,
                         mime_type=file.content_type, document_type=document_type, title=title,
                         requested_status=requested_status, reference_number=reference_number,
                         source_authority=source_authority, issue_date=issue_date, approval_date=approval_date,
                         effective_from=effective_from)
    db.commit()
    return documents.document_dict(d)


@router.post("/legal/jurisdiction-documents", status_code=201)
async def upload_jurisdiction_document(file: UploadFile = File(...), document_type: str = Form(...),
                                       title: str = Form(..., max_length=300), source_authority: Optional[str] = Form(None),
                                       source_url: Optional[str] = Form(None), is_primary_source: bool = Form(False),
                                       reference_number: Optional[str] = Form(None), issue_date: Optional[date] = Form(None),
                                       effective_from: Optional[date] = Form(None), db: Session = Depends(get_db),
                                       user: User = Depends(require_platform_admin)):
    data = await _read(file)
    d = documents.upload(db, society_id=None, user=user, file_name=file.filename or "document", data=data,
                         mime_type=file.content_type, document_type=document_type, title=title,
                         source_authority=source_authority, source_url=source_url, is_primary_source=is_primary_source,
                         reference_number=reference_number, issue_date=issue_date, effective_from=effective_from)
    db.commit()
    return documents.document_dict(d)


@router.get("/legal/documents/{doc_id}")
def get_document(doc_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_manager_above)):
    return documents.document_dict(_visible_doc(db, _sid(user, society_id), doc_id), detail=True)


@router.get("/legal/documents/{doc_id}/file")
def download_document(doc_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                      user: User = Depends(require_manager_above)):
    d = _visible_doc(db, _sid(user, society_id), doc_id)
    safe = "".join(ch for ch in d.file_name if ch.isalnum() or ch in "._- ") or "document"
    return Response(d.data, media_type=d.mime_type, headers={"Content-Disposition": f'attachment; filename="{safe}"',
                                                             "X-Content-SHA256": d.sha256})


@router.get("/legal/documents/{doc_id}/clauses")
def document_clauses(doc_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                     user: User = Depends(require_manager_above)):
    d = _visible_doc(db, _sid(user, society_id), doc_id)
    return [documents.clause_dict(c) for c in db.query(LegalClause).filter(LegalClause.document_id == d.id)
            .order_by(LegalClause.page_number, LegalClause.created_at).limit(2000)]


@router.post("/legal/documents/{doc_id}/verify")
def verify_document(doc_id: UUID, data: DocVerifyIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    d = _visible_doc(db, sid, doc_id)
    documents.verify(db, d, user, **data.model_dump())
    db.commit()
    return documents.document_dict(d)


# ── Rule registry ──────────────────────────────────────────────────────────────────────────────────────────────────

def _visible_rule(db: Session, sid: UUID, rule_id: UUID) -> LegalRule:
    r = db.get(LegalRule, rule_id)
    if r is None or r.scope not in registry.scopes_for(db, sid):
        raise HTTPException(404, "Rule not found")
    return r


@router.get("/legal/hierarchy")
def hierarchy(user: User = Depends(require_manager_above)):
    return {"levels": [{"level": k, "name": v} for k, v in SOURCE_LEVELS.items()],
            "principles": [
                "A resolution cannot override legislation or binding statutory requirements.",
                "A registered bye-law cannot be assumed to override the Act or Rules; a stricter bye-law limit is honoured.",
                "A model bye-law is a reference, never the society's registered bye-law.",
                "A draft never governs; an uploaded document governs only after verification.",
                "Conflicts are recorded and sent for legal review; uncertain interpretations are not enforced."]}


def _check_ledger_rule(db: Session, sid: UUID, topic: str, calc: Optional[dict]) -> None:
    """An element → ledger rule must name one of this society's elements and one of its own active ledgers."""
    from app.modules.accounts_agent.legal import ledger_mapping as lm
    from app.modules.billing.models.billing import MaintenanceElement
    if not topic.startswith(lm.TOPIC_PREFIX):
        return
    code = topic[len(lm.TOPIC_PREFIX):]
    if not db.query(MaintenanceElement.id).filter(MaintenanceElement.society_id == sid, MaintenanceElement.code == code).first():
        raise HTTPException(422, f"Element '{code}' does not exist in this society")
    calc = calc or {}
    if calc.get("type") != lm.CALC_TYPE or not calc.get("account_id"):
        raise HTTPException(422, "An element → ledger rule needs calculation_method {type: element_ledger, account_id}")
    try:
        acc = db.get(Account, UUID(str(calc["account_id"])))
    except ValueError:
        acc = None
    if acc is None or acc.society_id != sid or not acc.is_active:
        raise HTTPException(422, "The ledger is not an active ledger of this society")
    calc["element"] = code


@router.get("/legal/rules")
def list_rules(society_id: Optional[UUID] = None, category: Optional[str] = None, topic: Optional[str] = None,
               include_history: bool = False, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    db.commit()
    q = db.query(LegalRule).filter(LegalRule.scope.in_(registry.scopes_for(db, sid)))
    if category:
        q = q.filter(LegalRule.rule_category == category)
    if topic:
        q = q.filter(LegalRule.topic == topic)
    if not include_history:
        q = q.filter(LegalRule.superseded_by_id.is_(None))
    rows = q.order_by(LegalRule.rule_category, LegalRule.rule_code, LegalRule.version).all()
    return {"items": [registry.rule_dict(r) for r in rows],
            "verified": sum(1 for r in rows if r.verification_status in VERIFIED),
            "unverified": sum(1 for r in rows if r.verification_status not in VERIFIED)}


@router.get("/legal/rules/{rule_id}")
def get_rule(rule_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
             user: User = Depends(require_manager_above)):
    r = _visible_rule(db, _sid(user, society_id), rule_id)
    versions = (db.query(LegalRule).filter(LegalRule.scope == r.scope, LegalRule.rule_code == r.rule_code)
                .order_by(LegalRule.version).all())
    return {**registry.rule_dict(r, detail=True), "versions": [registry.rule_dict(v) for v in versions]}


@router.post("/legal/rules", status_code=201)
def create_society_rule(data: RuleIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                        user: User = Depends(require_admin_committee)):
    """A society's own rule (from its registered bye-laws, a resolution or a policy). It does not govern compliance
    until verified against an operative document."""
    sid = _sid(user, society_id)
    doc = _visible_doc(db, sid, data.source_document_id)
    if doc.society_id != sid:
        raise HTTPException(422, "A society rule must cite one of this society's own documents")
    if db.query(LegalRule.id).filter(LegalRule.scope == str(sid), LegalRule.rule_code == data.rule_code).first():
        raise HTTPException(409, "A rule with this code exists; add a new version instead")
    _check_ledger_rule(db, sid, data.topic, data.calculation_method)
    r = LegalRule(scope=str(sid), society_id=sid, version=1, jurisdiction=registry.scopes_for(db, sid)[1],
                  legal_status="UNVERIFIED", verification_status="PENDING_VERIFICATION", created_by=user.id,
                  source_document_title=doc.title, source_authority="Society", **data.model_dump())
    db.add(r)
    db.flush()
    audit.record(db, sid, "legal_rule_created", "legal_rule", r.id, user.id, {"rule_code": r.rule_code})
    db.commit()
    return registry.rule_dict(r, detail=True)


@router.post("/legal/rules/{rule_id}/versions", status_code=201)
def add_rule_version(rule_id: UUID, data: RuleVersionIn, society_id: Optional[UUID] = None,
                     db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    r = _visible_rule(db, sid, rule_id)
    if r.society_id is None and user.society_id is not None:
        raise HTTPException(403, "Jurisdiction-wide law is revised by a platform administrator")
    changes = data.model_dump(exclude_none=True)
    note = changes.pop("change_note")
    if r.society_id is not None and "calculation_method" in changes:
        _check_ledger_rule(db, sid, r.topic, changes["calculation_method"])
    nv = registry.new_version(db, r, changes, user, note)
    db.commit()
    return registry.rule_dict(nv, detail=True)


@router.post("/legal/rules/{rule_id}/verify")
def verify_rule(rule_id: UUID, data: RuleVerifyIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    r = _visible_rule(db, sid, rule_id)
    registry.verify_rule(db, r, user, data.verification_status, data.note, data.legal_status, data.source_document_id,
                         data.page_number)
    audit.record(db, sid, "legal_rule_verification", "legal_rule", r.id, user.id,
                 {"rule_code": r.rule_code, "status": data.verification_status})
    db.commit()
    return registry.rule_dict(r, detail=True)


@router.get("/legal/applicable")
def applicable(topic: str = Query(..., max_length=80), on_date: Optional[date] = None, society_id: Optional[UUID] = None,
               db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    on = on_date or society_today(db, sid)
    app = registry.resolve(db, sid, topic, on)
    db.commit()
    return {"topic": topic, "on_date": on.isoformat(), "governing": registry.source_ref(app.rule, app),
            "effective_value": app.effective_value, "finding_class_if_breached": registry.classify(app),
            "candidates": [registry.rule_dict(r) for r in app.candidates],
            "not_operative": [registry.rule_dict(r) for r in app.not_operative],
            "conflicts": app.conflicts, "blocked_by": [registry.review_dict(r) for r in app.blocked_by]}


# ── Legal reviews ──────────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/legal/reviews")
def list_reviews(society_id: Optional[UUID] = None, status: Optional[str] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    db.commit()
    q = db.query(LegalReview).filter((LegalReview.society_id == sid) | LegalReview.society_id.is_(None))
    if status:
        q = q.filter(LegalReview.status == status)
    return [registry.review_dict(r) for r in q.order_by(LegalReview.created_at.desc()).limit(500)]


@router.post("/legal/reviews/{review_id}/decide")
def decide_review(review_id: UUID, data: ReviewDecisionIn, society_id: Optional[UUID] = None,
                  db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    from datetime import datetime
    sid = _sid(user, society_id)
    r = db.get(LegalReview, review_id)
    if r is None or (r.society_id is not None and r.society_id != sid):
        raise HTTPException(404, "Review not found")
    if r.society_id is None and user.society_id is not None:
        raise HTTPException(403, "A review of jurisdiction-wide law is decided by a platform administrator")
    if r.status not in OPEN_REVIEW_STATUSES:
        raise HTTPException(409, f"The review is already {r.status.lower()}")
    r.status, r.decision, r.decision_note = data.status, data.decision, data.note
    if data.status in ("RESOLVED", "DISMISSED"):
        r.decided_by, r.decided_at = user.id, datetime.utcnow()
    audit.record(db, sid, "legal_review_decided", "legal_review", r.id, user.id, {"status": data.status})
    db.commit()
    return registry.review_dict(r)


# ── Resolutions ────────────────────────────────────────────────────────────────────────────────────────────────────

def _resolution(db: Session, sid: UUID, rid: UUID) -> SocietyResolution:
    r = db.query(SocietyResolution).filter(SocietyResolution.id == rid, SocietyResolution.society_id == sid).first()
    if not r:
        raise HTTPException(404, "Resolution not found")
    return r


@router.get("/resolutions")
def list_resolutions(society_id: Optional[UUID] = None, status: Optional[str] = None, category: Optional[str] = None,
                     db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    q = db.query(SocietyResolution).filter(SocietyResolution.society_id == sid)
    if status:
        q = q.filter(SocietyResolution.status == status)
    if category:
        q = q.filter(SocietyResolution.category == category)
    return [res_svc.resolution_dict(r) for r in q.order_by(SocietyResolution.meeting_date.desc()).limit(1000)]


@router.post("/resolutions", status_code=201)
def create_resolution(data: ResolutionIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                      user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    d = data.model_dump(exclude_none=True)
    for req in ("resolution_number", "meeting_type", "meeting_date", "purpose"):
        if not d.get(req):
            raise HTTPException(422, f"{req.replace('_', ' ')} is required")
    r = res_svc.create(db, sid, user, d)
    db.commit()
    return res_svc.resolution_dict(r)


@router.put("/resolutions/{rid}")
def update_resolution(rid: UUID, data: ResolutionIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                      user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    r = res_svc.update(db, _resolution(db, sid, rid), user, data.model_dump(exclude_none=True))
    db.commit()
    return res_svc.resolution_dict(r)


@router.post("/resolutions/{rid}/verify")
def verify_resolution(rid: UUID, data: VerifyNote, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                      user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    r = res_svc.verify(db, _resolution(db, sid, rid), user, data.note)
    db.commit()
    return res_svc.resolution_dict(r)


@router.post("/resolutions/import-governance")
def import_resolutions(society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                       user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    n = res_svc.import_governance(db, sid, user)
    db.commit()
    return {"imported": n}


# ── Budgets ────────────────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/budgets")
def get_budget(fiscal_year: str = Query(..., pattern=r"^\d{4}-\d{2}$"), society_id: Optional[UUID] = None,
               db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    rows = db.query(BudgetLine, Account).join(Account, Account.id == BudgetLine.account_id).filter(
        BudgetLine.society_id == sid, BudgetLine.fiscal_year == fiscal_year).all()
    return [{"id": str(b.id), "account_id": str(a.id), "account": a.name, "approved_amount": str(b.approved_amount),
             "resolution_id": str(b.resolution_id) if b.resolution_id else None, "note": b.note} for b, a in rows]


@router.put("/budgets")
def put_budget(data: BudgetIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
               user: User = Depends(require_admin_committee)):
    from app.modules.accounts.services.accounts_service import fiscal_year_bounds
    sid = _sid(user, society_id)
    fiscal_year_bounds(data.fiscal_year)
    for line in data.lines:
        a = db.get(Account, line.account_id)
        if a is None or a.society_id != sid:
            raise HTTPException(422, "Ledger not found in this society")
        if line.resolution_id:
            _resolution(db, sid, line.resolution_id)
        b = db.query(BudgetLine).filter(BudgetLine.society_id == sid, BudgetLine.fiscal_year == data.fiscal_year,
                                        BudgetLine.account_id == a.id).first()
        if b is None:
            b = BudgetLine(society_id=sid, fiscal_year=data.fiscal_year, account_id=a.id, approved_amount=line.approved_amount)
            db.add(b)
        b.approved_amount, b.resolution_id, b.note, b.updated_by = line.approved_amount, line.resolution_id, line.note, user.id
    audit.record(db, sid, "budget_updated", "budget", None, user.id, {"fiscal_year": data.fiscal_year, "lines": len(data.lines)})
    db.commit()
    return get_budget(data.fiscal_year, society_id, db, user)


# ── Compliance scan, overview and calendar ─────────────────────────────────────────────────────────────────────────

@router.post("/compliance/scan")
def scan(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    out = compliance.run_scan(db, sid, actor_id=user.id)
    created = out.pop("_created")
    db.commit()
    try:
        notify.notify_findings(db, sid, created)
    except Exception:  # noqa: BLE001 — a notification failure never undoes the scan
        db.rollback()
    return out


def section_of(f: AgentFinding) -> str:
    return sections.section_of(f.category)


@router.get("/compliance/overview")
def overview(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    """The unified dashboard: every section's open findings by class and severity, plus the legal library state."""
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    today = society_today(db, sid)
    cal.ensure_items(db, sid, today)
    db.commit()
    open_f = db.query(AgentFinding).filter(AgentFinding.society_id == sid, AgentFinding.status.in_(OPEN_FINDING_STATUSES)).all()
    tiles = {k: {"key": k, "title": t, "open": 0, "by_class": {}, "by_severity": {}} for k, (t, _) in sections.SECTIONS.items()}
    for f in open_f:
        s = tiles[section_of(f)]
        s["open"] += 1
        c = UNIFIED_CLASS.get(f.finding_class, "ADVISORY_OBSERVATION")
        s["by_class"][c] = s["by_class"].get(c, 0) + 1
        s["by_severity"][f.severity] = s["by_severity"].get(f.severity, 0) + 1
    rules = db.query(LegalRule).filter(LegalRule.scope.in_(registry.scopes_for(db, sid)), LegalRule.superseded_by_id.is_(None)).all()
    docs = db.query(LegalDocument.status, func.count(LegalDocument.id)).filter(LegalDocument.society_id == sid) \
        .group_by(LegalDocument.status).all()
    reviews = db.query(func.count(LegalReview.id)).filter(LegalReview.status.in_(OPEN_REVIEW_STATUSES),
                                                         (LegalReview.society_id == sid) | LegalReview.society_id.is_(None)).scalar()
    pending = db.query(func.count(AgentProposal.id)).filter(AgentProposal.society_id == sid, AgentProposal.status == "PENDING").scalar()
    items = db.query(ComplianceItem).filter(ComplianceItem.society_id == sid, ComplianceItem.completion_status == "PENDING").all()
    rep = recovery.arrears(db, sid, today)
    last_scan = (db.query(func.max(audit.AgentAuditLog.created_at)).filter(audit.AgentAuditLog.society_id == sid,
                                                                          audit.AgentAuditLog.action == "compliance_scan").scalar())
    return {"sections": list(tiles.values()),
            "financial_health": {"member_dues_outstanding": rep["total_outstanding"], "ageing": rep["ageing_totals"],
                                 "defaulters": sum(1 for r in rep["flats"] if r["defaulter"])},
            "pending_approvals": pending or 0,
            "legal_library": {"documents_by_status": {s: n for s, n in docs},
                              "rules_verified": sum(1 for r in rules if r.verification_status in VERIFIED),
                              "rules_unverified": sum(1 for r in rules if r.verification_status not in VERIFIED),
                              "open_legal_reviews": reviews or 0},
            "statutory": {"pending": len(items), "overdue": sum(1 for i in items if i.due_date and i.due_date < today),
                          "professional_verification_required": sum(1 for i in items if i.applicability == cal.PV)},
            "learning_window_months": WINDOW_MONTHS,
            "last_scan_at": last_scan.isoformat() if last_scan else None,
            "llm_required": False}


@router.get("/compliance/calendar")
def get_calendar(society_id: Optional[UUID] = None, financial_period: Optional[str] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    today = society_today(db, sid)
    cal.ensure_items(db, sid, today)
    db.commit()
    q = db.query(ComplianceItem).filter(ComplianceItem.society_id == sid)
    if financial_period:
        q = q.filter(ComplianceItem.financial_period == financial_period)
    rows = q.order_by(ComplianceItem.financial_period.desc(), ComplianceItem.due_date.is_(None), ComplianceItem.due_date).all()
    return [cal.item_dict(r, today) for r in rows]


@router.put("/compliance/calendar/{item_id}")
def update_calendar_item(item_id: UUID, data: CalendarItemIn, society_id: Optional[UUID] = None,
                         db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    it = db.query(ComplianceItem).filter(ComplianceItem.id == item_id, ComplianceItem.society_id == sid).first()
    if not it:
        raise HTTPException(404, "Compliance item not found")
    cal.update_item(db, it, user, data.model_dump(exclude_none=True))
    db.commit()
    return cal.item_dict(it, society_today(db, sid))


# ── Recovery readiness ─────────────────────────────────────────────────────────────────────────────────────────────

@router.get("/recovery/arrears")
def recovery_arrears(society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                     user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    db.commit()
    return recovery.arrears(db, sid, society_today(db, sid))


@router.get("/recovery/checklist/{flat_id}")
def recovery_checklist(flat_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                       user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    db.commit()
    return recovery.checklist(db, sid, flat_id, society_today(db, sid))


# ── Assistant ──────────────────────────────────────────────────────────────────────────────────────────────────────

@router.post("/assistant/ask")
def ask(data: AskIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
        user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    out = assistant.ask(db, sid, data.question)
    audit.record(db, sid, "assistant_question", "assistant", None, user.id, {"intent": out["intent"]})
    db.commit()
    return out


# ── Element → ledger map ───────────────────────────────────────────────────────────────────────────────────────────

@router.get("/ledger-mapping")
def ledger_map(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    """Every active charge head: its element, the ledger bills are credited to and why, the society's own rule (if
    any), what was actually posted recently, and whether the current map has been signed off."""
    from app.modules.accounts_agent.legal import ledger_mapping as lm
    sid = _sid(user, society_id)
    registry.ensure_jurisdiction_pack(db)
    db.commit()
    return lm.mapping(db, sid, society_today(db, sid))


@router.post("/ledger-mapping/sign-off")
def sign_off_ledger_map(data: SignOffIn, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                        user: User = Depends(require_admin_committee)):
    """Record that the committee or auditor reviewed exactly the map that was shown (its fingerprint)."""
    from app.modules.accounts_agent.legal import ledger_mapping as lm
    sid = _sid(user, society_id)
    out = lm.sign_off(db, sid, user, data.role, data.note, data.fingerprint, society_today(db, sid))
    db.commit()
    out["signed_off"] = lm.last_sign_off(db, sid)
    out["signed_off_current"] = True
    return out
