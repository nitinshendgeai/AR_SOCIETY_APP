"""Correction proposals and their approval.

The agent NEVER changes a financial record on its own. It can only *propose*; a person with the right permission must
approve explicitly. Approval runs through the existing AccountsService (update_manual_voucher / cancel_manual_voucher), as
the approving user, so closed-year locks, the maker–checker rule, voucher revisions and the accounting audit log all
apply unchanged. Balances are never touched directly and nothing is ever deleted.

Safety checks at approval time, in order: caller permission (route) → proposal belongs to caller's society → still
PENDING (one-shot: a second approval is refused) → the voucher is unchanged since the proposal (state fingerprint) →
existing accounting rules (inside the service) → agent re-verifies the resulting state.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.services.accounts_service import AccountsService
from app.modules.accounts_agent.models.agent import AgentFinding, AgentProposal
from app.modules.accounts_agent.services import audit, engine
from app.modules.accounts_agent.services.context import money, state_fingerprint

logger = logging.getLogger(__name__)
DUPLICATE_RULES = ("R-DUP-01", "R-DUP-02", "R-DUP-03", "R-DUP-04")
MAPPING_RULES = ("S-MAP-01",)


def _lines(voucher: Voucher) -> List[dict]:
    return [{"account_id": str(e.account_id), "account": e.account.name if e.account else str(e.account_id),
             "debit": str(money(e.debit)), "credit": str(money(e.credit)),
             "flat_id": str(e.flat_id) if e.flat_id else None, "vendor_id": str(e.vendor_id) if e.vendor_id else None,
             "narration": e.narration} for e in voucher.entries]


def _impact(before: List[dict], after: List[dict]) -> List[dict]:
    """Per-ledger effect of the correction: what each ledger's debit/credit totals become, and the net movement."""
    names, b, a = {}, {}, {}
    for rows, acc in ((before, b), (after, a)):
        for l in rows:
            names[l["account_id"]] = l["account"]
            d, c = acc.get(l["account_id"], (Decimal("0"), Decimal("0")))
            acc[l["account_id"]] = (d + Decimal(l["debit"]), c + Decimal(l["credit"]))
    out = []
    for aid in names:
        bd, bc = b.get(aid, (Decimal("0"), Decimal("0")))
        ad, ac = a.get(aid, (Decimal("0"), Decimal("0")))
        net = (ad - ac) - (bd - bc)
        if net or bd != ad or bc != ac:
            out.append({"account_id": aid, "account": names[aid], "debit_before": str(bd), "credit_before": str(bc),
                        "debit_after": str(ad), "credit_after": str(ac),
                        "net_effect": f"{abs(net)} {'Dr' if net > 0 else 'Cr'}" if net else "0"})
    return out


def _get_finding(db: Session, society_id: UUID, finding_id: UUID) -> AgentFinding:
    f = db.query(AgentFinding).filter(AgentFinding.id == finding_id, AgentFinding.society_id == society_id).first()
    if not f:
        raise HTTPException(404, "Finding not found")
    return f


def create_proposal(db: Session, society_id: UUID, finding_id: UUID, user: User) -> AgentProposal:
    f = _get_finding(db, society_id, finding_id)
    v = engine.load_voucher(db, society_id, f.voucher_id) if f.voucher_id else None
    if v is None:
        raise HTTPException(409, "The voucher this finding refers to no longer exists")
    if v.is_cancelled:
        raise HTTPException(409, "The voucher is already cancelled; nothing to correct")
    if db.query(AgentProposal.id).filter(AgentProposal.finding_id == f.id, AgentProposal.status == "PENDING").first():
        raise HTTPException(409, "This finding already has a proposal waiting for approval")
    svc = AccountsService(db)
    before_lines = _lines(v)
    before = {"voucher_number": v.voucher_number, "voucher_date": v.voucher_date.isoformat(), "amount": str(money(v.amount)),
              "narration": v.narration, "reference": v.reference, "is_cancelled": False, "lines": before_lines}

    if v.source_type:
        action, executable, after, impact = "source_review", False, None, []
        title = f"Review the source of {v.voucher_number}"
        text = (f"{v.voucher_number} was posted automatically from '{v.source_type}'. Editing a generated voucher would only be "
                f"overwritten or lose the link to its source. The underlying {v.source_type} (or the posting/ledger mapping that "
                "produced it) should be corrected, then re-posted. Approving records that the review is done; it changes no books.")
    elif f.rule_code in DUPLICATE_RULES:
        svc._assert_manual(v, "cancel")
        action, executable = "cancel_voucher", True
        after = {**before, "is_cancelled": True}
        impact = _impact(before_lines, [])
        title = f"Cancel duplicate {v.voucher_number}"
        text = (f"Cancel {v.voucher_number}, which duplicates another voucher. Cancelling keeps the voucher on record (struck out) and "
                "removes its effect from every ledger; it is not deleted.")
    elif f.rule_code in MAPPING_RULES:
        svc._assert_manual(v, "edit")
        ev = f.evidence or {}
        wrong, right = ev.get("actual_ledger_id"), ev.get("usual_ledger_id")
        if not wrong or not right or not any(l["account_id"] == wrong for l in before_lines):
            raise HTTPException(409, "The flagged line is no longer on the voucher")
        right_acc = svc.get_account(UUID(right))
        if right_acc.society_id != society_id or not right_acc.is_active:
            raise HTTPException(409, "The usual ledger is not available")
        after_lines = [{**l, "account_id": right, "account": right_acc.name} if l["account_id"] == wrong else dict(l)
                       for l in before_lines]
        action, executable = "edit_voucher", True
        after = {**before, "lines": after_lines}
        impact = _impact(before_lines, after_lines)
        title = f"Re-map {v.voucher_number} to '{right_acc.name}'"
        text = (f"Move the flagged line from '{ev.get('actual_ledger')}' to '{right_acc.name}', the ledger this vendor's expenses normally go to. "
                "The amount and the other lines are unchanged. Editing a payment/journal puts it back for approval as usual.")
    else:
        raise HTTPException(422, "No correction can be derived automatically for this finding. Review it and mark it "
                                 "resolved or ignored, or correct the voucher manually in Accounts.")
    p = AgentProposal(society_id=society_id, finding_id=f.id, voucher_id=v.id, action_type=action,
                      status="PENDING", voucher_fingerprint=state_fingerprint(v), title=title, explanation=text,
                      before_values=before, after_values=after, impact=impact, executable=executable, created_by=user.id)
    db.add(p)
    f.status = "UNDER_REVIEW" if f.status == "NEW" else f.status
    db.flush()
    audit.record(db, society_id, "proposal_created", "proposal", p.id, user.id, {"finding": str(f.id), "action": action})
    db.commit()
    try:
        from app.modules.accounts_agent.services import notify
        notify.notify_proposal_needs_approval(db, society_id, p)
    except Exception:  # noqa: BLE001
        db.rollback()
    return p


def _get_proposal(db: Session, society_id: UUID, proposal_id: UUID, lock: bool = False) -> AgentProposal:
    q = db.query(AgentProposal).filter(AgentProposal.id == proposal_id, AgentProposal.society_id == society_id)
    if lock and db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update()
    p = q.first()
    if not p:
        raise HTTPException(404, "Proposal not found")
    return p


def reject_proposal(db: Session, society_id: UUID, proposal_id: UUID, user: User, reason: str) -> AgentProposal:
    p = _get_proposal(db, society_id, proposal_id, lock=True)
    if p.status != "PENDING":
        raise HTTPException(409, f"Proposal is already {p.status.lower()}")
    p.status, p.decided_by, p.decided_at, p.decision_note = "REJECTED", user.id, datetime.utcnow(), reason
    audit.record(db, society_id, "proposal_rejected", "proposal", p.id, user.id, {"reason": reason[:200]})
    db.commit()
    try:
        from app.modules.accounts_agent.services import notify
        notify.notify_proposal_decided(db, society_id, p, "rejected", user.id)
    except Exception:  # noqa: BLE001
        db.rollback()
    return p


def approve_proposal(db: Session, society_id: UUID, proposal_id: UUID, user: User, note: Optional[str]) -> AgentProposal:
    p = _get_proposal(db, society_id, proposal_id, lock=True)
    if p.status != "PENDING":
        raise HTTPException(409, f"Proposal is already {p.status.lower()} and cannot be approved again")
    finding = db.get(AgentFinding, p.finding_id)
    v = engine.load_voucher(db, society_id, p.voucher_id) if p.voucher_id else None
    if v is None or state_fingerprint(v) != p.voucher_fingerprint:
        p.status, p.decided_by, p.decided_at = "STALE", user.id, datetime.utcnow()
        p.decision_note = "The voucher changed after this proposal was made; it was not applied."
        audit.record(db, society_id, "proposal_stale", "proposal", p.id, user.id)
        db.commit()
        raise HTTPException(409, "The voucher has changed since this proposal was made. Nothing was applied — ask the "
                                 "agent to re-check it.")
    p.decided_by, p.decided_at, p.decision_note = user.id, datetime.utcnow(), note
    svc = AccountsService(db)
    try:
        if p.action_type == "source_review":
            p.status, p.result = "ACKNOWLEDGED", {"executed": False, "note": "Source review acknowledged; no books were changed."}
            audit.record(db, society_id, "proposal_acknowledged", "proposal", p.id, user.id)
            if finding:
                finding.status, finding.reviewed_by, finding.reviewed_at = "APPROVED", user.id, datetime.utcnow()
            db.commit()
            return p
        reason = f"Accounts Agent correction approved by reviewer: {p.title}"[:300]
        p.status = "EXECUTED"                         # committed together with the accounting change by the service
        audit.record(db, society_id, "proposal_approved", "proposal", p.id, user.id, {"action": p.action_type})
        if p.action_type == "cancel_voucher":
            svc.cancel_manual_voucher(v.id, reason, user)
        elif p.action_type == "edit_voucher":
            lines = p.after_values["lines"]
            svc.update_manual_voucher(v.id, {
                "voucher_date": v.voucher_date, "narration": v.narration, "reference": v.reference, "vendor_id": v.vendor_id,
                "entries": [{"account_id": UUID(l["account_id"]), "debit": Decimal(l["debit"]), "credit": Decimal(l["credit"]),
                             "flat_id": UUID(l["flat_id"]) if l["flat_id"] else None,
                             "vendor_id": UUID(l["vendor_id"]) if l["vendor_id"] else None, "narration": l["narration"]}
                            for l in lines],
                "reason": reason}, user)
        else:  # pragma: no cover — defensive: unknown action types are never executed
            raise HTTPException(422, "Unknown proposal action")
    except HTTPException as exc:
        db.rollback()
        p = _get_proposal(db, society_id, proposal_id)
        p.status, p.decided_by, p.decided_at = "FAILED", user.id, datetime.utcnow()
        p.result = {"executed": False, "error": str(exc.detail)[:300]}
        audit.record(db, society_id, "proposal_failed", "proposal", p.id, user.id, {"error": str(exc.detail)[:200]})
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise
    _verify(db, society_id, p, finding, user)
    return p


def _verify(db: Session, society_id: UUID, p: AgentProposal, finding: Optional[AgentFinding], user: User) -> None:
    """The agent re-reads the resulting state and re-runs its checks. Never fails the (already committed) correction."""
    try:
        p = _get_proposal(db, society_id, p.id)
        v = engine.load_voucher(db, society_id, p.voucher_id)
        if v is None:
            return
        drafts = [] if v.is_cancelled else engine.analyse(db, v, "voucher.edited")
        remaining = sorted({d.rule_code for d in drafts})
        fixed = finding is not None and finding.dedupe_key not in {d.dedupe_key(v.id) for d in drafts}
        p.result = {"executed": True, "voucher_cancelled": bool(v.is_cancelled), "approval_status": v.approval_status,
                    "verification": {"finding_cleared": fixed, "remaining_rules": remaining,
                                     "note": ("Re-checked: the issue is no longer detected." if fixed
                                              else "Re-checked: the issue is still detected; review it.")}}
        if finding is not None:
            f = db.get(AgentFinding, finding.id)
            if fixed:
                f.status, f.resolved_at, f.reviewed_by, f.reviewed_at = "RESOLVED", datetime.utcnow(), user.id, datetime.utcnow()
                f.resolution_note = f"Corrected through approved proposal: {p.title}"
            else:
                f.status = "APPROVED"
        audit.record(db, society_id, "proposal_verified", "proposal", p.id, None, p.result["verification"])
        db.commit()
        from app.modules.accounts_agent.services import notify
        notify.notify_proposal_decided(db, society_id, p, "approved", user.id)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[accounts-agent] post-correction verification failed society=%s", society_id)


FINDING_TARGETS = ("UNDER_REVIEW", "APPROVED", "REJECTED", "RESOLVED", "IGNORED")


def review_finding(db: Session, society_id: UUID, finding_id: UUID, user: User, status: str, note: Optional[str]) -> AgentFinding:
    if status not in FINDING_TARGETS:
        raise HTTPException(422, f"Status must be one of: {', '.join(FINDING_TARGETS)}")
    if status in ("REJECTED", "IGNORED", "RESOLVED") and not (note or "").strip():
        raise HTTPException(422, "Please give a short reason")
    f = _get_finding(db, society_id, finding_id)
    old = f.status
    f.status, f.reviewed_by, f.reviewed_at, f.resolution_note = status, user.id, datetime.utcnow(), note or f.resolution_note
    if status == "RESOLVED":
        f.resolved_at = datetime.utcnow()
    audit.record(db, society_id, "finding_reviewed", "finding", f.id, user.id, {"from": old, "to": status, "note": (note or "")[:200]})
    db.commit()
    return f
