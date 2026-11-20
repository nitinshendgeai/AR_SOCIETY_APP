"""The configurable statutory compliance calendar.

Each requirement records its legal source, applicability, responsible role, period, due date and status. The agent
never assumes a society is subject to a tax: applicability is APPLICABLE only when the society's own data shows it
(a GST number or GST billing switched on; TDS actually deducted), otherwise PROFESSIONAL_VERIFICATION_REQUIRED.
Due dates are only filled where the date is well established, and every one is marked PENDING_VERIFICATION with its
basis; the committee can edit any date, mark an item not applicable, or add its own items.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.services.accounts_service import fiscal_year, fiscal_year_bounds
from app.modules.accounts_agent.legal.models import APPLICABILITY, COMPLETION_STATUSES, ComplianceItem
from app.modules.accounts_agent.services import audit

PV = "PROFESSIONAL_VERIFICATION_REQUIRED"


def obligation_start(db: Session, society_id: UUID):
    """From when the society's statutory obligations can be judged (D-05 of the functional audit): the registration
    date in its legal profile when recorded ("REGISTRATION"); otherwise the day it started using the app
    ("ONBOARDING"), which says nothing about whether earlier obligations existed — only that the app cannot know."""
    from app.models.society import Society
    from app.modules.accounts_agent.legal.models import LegalProfile
    p = db.query(LegalProfile).filter(LegalProfile.society_id == society_id).first()
    if p and p.registration_date:
        return p.registration_date, "REGISTRATION"
    soc = db.get(Society, society_id)
    created = getattr(soc, "created_at", None)
    return (created.date() if created else None), "ONBOARDING"


def _before_start(items: List[dict], fy_end: date, start: Optional[date], basis: str) -> None:
    """A year that ended before the society was registered is NOT_APPLICABLE; one that ended before it joined the app
    (registration date unknown) needs confirmation rather than being declared overdue."""
    if not start or fy_end >= start:
        return
    for it in items:
        if basis == "REGISTRATION":
            it["applicability"] = "NOT_APPLICABLE"
            it["applicability_reason"] = (f"The society was registered on {start:%d %b %Y}, after this financial year "
                                          "ended.")
        elif it["applicability"] == "APPLICABLE":
            it["applicability"] = PV
            it["applicability_reason"] = (f"This financial year ended before the society started using the app "
                                          f"({start:%d %b %Y}) and its registration date is not recorded: confirm "
                                          "whether it applies (record the registration date in the legal profile), "
                                          "or mark it done with the evidence.")


def _templates(db: Session, society_id: UUID, fy: str) -> List[dict]:
    from app.models.society import Society
    from app.modules.billing.models.billing import MaintenanceSettings
    from app.modules.vendor.models.vendor import VendorPaymentTransaction
    start, end = fiscal_year_bounds(fy)
    y = end.year                                              # the calendar year the FY ends in
    soc = db.get(Society, society_id)
    ms = db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == society_id).first()
    gst = bool((soc and soc.gst_number) or (ms and ms.gst_enabled))
    tds = (db.query(func.count(VendorPaymentTransaction.id)).filter(VendorPaymentTransaction.society_id == society_id,
                                                                    VendorPaymentTransaction.tds_amount > 0).scalar() or 0) > 0
    verify = "Due date to be verified against the current Act/Rules and the society's bye-laws."
    items = [
        dict(code="FIN_STATEMENTS", title=f"Prepare annual financial statements for {fy}", category="FINANCIAL_STATEMENTS",
             legal_source="Maharashtra Co-operative Societies Act, 1960 (Chapter XIII-B) and Rules — to be verified",
             applicability="APPLICABLE", applicability_reason="Every registered housing society keeps annual accounts.",
             responsible_role="Treasurer / Secretary", due_date=None,
             due_date_basis="Not set: enter the date required by your bye-laws / auditor.",
             supporting_documents=["Income & Expenditure account", "Balance sheet", "Trial balance"]),
        dict(code="STATUTORY_AUDIT", title=f"Statutory audit of {fy} accounts", category="STATUTORY_AUDIT",
             legal_source="Act Chapter XIII-B (audit provisions) — section to be verified",
             applicability="APPLICABLE", applicability_reason="Annual statutory audit by an auditor from the approved panel.",
             responsible_role="Managing Committee", due_date=None,
             due_date_basis="Not set: the audit must be completed before the AGM; enter your auditor's date.",
             supporting_documents=["Audit report", "Audit memo"]),
        dict(code="AGM", title=f"Annual General Meeting adopting the {fy} accounts", category="AGM",
             legal_source="Act section 75 (as amended) / Chapter XIII-B — to be verified",
             applicability="APPLICABLE", applicability_reason="Every society holds an AGM each year.",
             responsible_role="Secretary", due_date=date(y, 9, 30),
             due_date_basis="30 September after the financial year (commonly cited). " + verify,
             supporting_documents=["AGM notice", "Minutes", "Adopted accounts"]),
        dict(code="AUDIT_RECTIFICATION", title=f"Audit rectification report for {fy}", category="AUDIT_RECTIFICATION",
             legal_source="Act Chapter XIII-B (rectification of audit defects) — to be verified",
             applicability="APPLICABLE", applicability_reason="Required once the audit report points out defects.",
             responsible_role="Managing Committee", due_date=None,
             due_date_basis="Not set: depends on the audit report date.", supporting_documents=["Rectification report"]),
        dict(code="INCOME_TAX_RETURN", title=f"Income-tax return for {fy}", category="INCOME_TAX",
             legal_source="Income-tax Act — applicability depends on the society's income", applicability=PV,
             applicability_reason="Whether a return is required and its due date depend on taxable income and audit "
                                  "status: professional verification required.", responsible_role="Treasurer",
             due_date=None, due_date_basis="Professional verification required.", supporting_documents=["ITR acknowledgement"]),
        dict(code="TDS_RETURNS", title=f"TDS quarterly returns for {fy}", category="TDS",
             legal_source="Income-tax Act (TDS) and rules", applicability="APPLICABLE" if tds else PV,
             applicability_reason="TDS was deducted from vendor payments in the books." if tds else
             "No TDS deduction is recorded; whether the society must deduct depends on its payments — professional "
             "verification required.", responsible_role="Treasurer", due_date=None,
             due_date_basis="Quarterly; verify the current due dates.", supporting_documents=["Form 26Q / 24Q filings"]),
        dict(code="GST_RETURNS", title=f"GST returns for {fy}", category="GST",
             legal_source="CGST / MGST Acts", applicability="APPLICABLE" if gst else PV,
             applicability_reason="The society has a GST number / GST billing is on." if gst else
             "GST registration is not recorded; whether it is required depends on turnover and per-member contributions "
             "— professional verification required.", responsible_role="Treasurer", due_date=None,
             due_date_basis="Monthly / quarterly per registration; verify.", supporting_documents=["GSTR-1", "GSTR-3B"]),
    ]
    for it in items:
        it.update(financial_period=fy, verification_status="PENDING_VERIFICATION")
    _before_start(items, end, *obligation_start(db, society_id))
    return items


def ensure_items(db: Session, society_id: UUID, today: date) -> int:
    """Create the standard items for the last completed and the current financial year (never overwrites)."""
    n = 0
    current = fiscal_year(today)
    last = fiscal_year(date(fiscal_year_bounds(current)[0].year - 1, 4, 1))
    have = {(c, p) for c, p in db.query(ComplianceItem.code, ComplianceItem.financial_period)
            .filter(ComplianceItem.society_id == society_id)}
    existing = {(c.code, c.financial_period): c for c in db.query(ComplianceItem)
                .filter(ComplianceItem.society_id == society_id)}
    for fy in (last, current):
        for t in _templates(db, society_id, fy):
            it = existing.get((t["code"], fy))
            if it is None:
                db.add(ComplianceItem(society_id=society_id, completion_status="PENDING", **t))
                n += 1
            elif _untouched(db, it) and it.applicability == "APPLICABLE" and t["applicability"] != "APPLICABLE":
                # An item created before the registration / onboarding date was taken into account, never edited by
                # anyone: bring its applicability in line (a person's own choice is never overwritten).
                it.applicability, it.applicability_reason = t["applicability"], t["applicability_reason"]
    db.flush()
    return n


def _untouched(db: Session, it: ComplianceItem) -> bool:
    """Never edited by a person: still pending, and no `compliance_item_updated` entry in the agent's audit log."""
    from app.modules.accounts_agent.models.agent import AgentAuditLog
    if it.completion_status != "PENDING" or it.verification_status != "PENDING_VERIFICATION":
        return False
    return not (db.query(AgentAuditLog.id).filter(AgentAuditLog.society_id == it.society_id,
                                                  AgentAuditLog.action == "compliance_item_updated",
                                                  AgentAuditLog.entity_id == str(it.id)).first())


def update_item(db: Session, it: ComplianceItem, user, data: dict) -> ComplianceItem:
    if "applicability" in data and data["applicability"] not in APPLICABILITY:
        raise HTTPException(422, "Unknown applicability")
    if "completion_status" in data and data["completion_status"] not in COMPLETION_STATUSES:
        raise HTTPException(422, "Unknown status")
    if data.get("completion_status") == "COMPLETED" and not (data.get("evidence_ref") or it.evidence_ref):
        raise HTTPException(422, "Record the evidence (acknowledgement / report number) when marking it done")
    if data.get("applicability") == "NOT_APPLICABLE" and not data.get("applicability_reason"):
        raise HTTPException(422, "Record why it does not apply")
    for k in ("applicability", "applicability_reason", "due_date", "due_date_basis", "completion_status", "completed_on",
              "evidence_ref", "responsible_role"):
        if k in data and data[k] is not None:
            setattr(it, k, data[k])
    if it.completion_status == "COMPLETED" and not it.completed_on:
        it.completed_on = date.today()
    if it.applicability == "NOT_APPLICABLE":
        it.completion_status = "NOT_APPLICABLE"
    it.updated_by = user.id
    audit.record(db, it.society_id, "compliance_item_updated", "compliance_item", it.id, user.id,
                 {k: str(v) for k, v in data.items() if v is not None})
    return it


def item_dict(it: ComplianceItem, today: Optional[date] = None) -> dict:
    overdue = bool(today and it.due_date and it.due_date < today and it.completion_status == "PENDING")
    return {"id": str(it.id), "code": it.code, "title": it.title, "category": it.category,
            "legal_rule_code": it.legal_rule_code, "legal_source": it.legal_source, "applicability": it.applicability,
            "applicability_reason": it.applicability_reason, "responsible_role": it.responsible_role,
            "financial_period": it.financial_period, "due_date": it.due_date.isoformat() if it.due_date else None,
            "due_date_basis": it.due_date_basis, "supporting_documents": it.supporting_documents or [],
            "completion_status": it.completion_status, "completed_on": it.completed_on.isoformat() if it.completed_on else None,
            "evidence_ref": it.evidence_ref, "verification_status": it.verification_status, "overdue": overdue,
            "professional_verification_required": it.applicability == PV}
