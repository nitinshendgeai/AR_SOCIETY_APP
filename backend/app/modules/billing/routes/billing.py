from typing import List, Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles, _user_has_permission,
    require_admin_committee, require_any_member, require_manager_above,
)
from app.models.user import User
from app.modules.billing.models.billing import (
    ChargeType, BillStatus, PaymentMode, PenaltyCalculationType, CycleFrequency,
    ReconciliationStatus,
)
from app.modules.billing.services.billing_service import BillingService, RESIDENT_VISIBLE_BILL_STATUSES
from app.schemas.common import OrmBase, TimestampSchema
from typing import Optional

router = APIRouter(prefix="/billing", tags=["Maintenance Billing & Finance"])

admin_committee = require_admin_committee
any_member      = require_any_member
manager_above   = require_manager_above


# ── Inline schemas ────────────────────────────────────────────────────────────
class PeriodCreate(OrmBase):
    society_id: UUID; name: str; period_start: date; period_end: date

class ChargeConfigCreate(OrmBase):
    society_id: UUID; charge_type: ChargeType; name: str
    default_amount: Optional[Decimal] = None; is_per_sqft: bool = False
    is_mandatory: bool = True; tax_percent: Decimal = Decimal(0)
    description: Optional[str] = None; effective_from: Optional[date] = None

class CycleCreate(OrmBase):
    society_id: UUID; name: str; cycle_start: date; cycle_end: date
    due_date: date; frequency: CycleFrequency = CycleFrequency.MONTHLY
    period_id: Optional[UUID] = None; notes: Optional[str] = None

class CancelBillRequest(OrmBase):
    reason: str

class PaymentCreate(OrmBase):
    bill_id: UUID; amount: Decimal; payment_date: date
    payment_mode: PaymentMode
    transaction_ref: Optional[str] = None
    cheque_number:   Optional[str] = None
    bank_name:       Optional[str] = None
    notes:           Optional[str] = None
    is_advance:      bool = False

class PenaltyRuleCreate(OrmBase):
    society_id: UUID; name: str
    calc_type: PenaltyCalculationType = PenaltyCalculationType.PERCENTAGE
    rate: Decimal; grace_period_days: int = 10
    max_penalty_pct: Optional[Decimal] = None

class OnlinePaymentStatusUpdate(OrmBase):
    status: ReconciliationStatus
    review_notes: Optional[str] = None

class BankMatchConfirm(OrmBase):
    submission_id: UUID

class BankEntryIgnore(OrmBase):
    reason: Optional[str] = None


def _online_payment_out(s) -> dict:
    """Serialize an OnlinePaymentSubmission, deliberately excluding the
    binary screenshot_data column — that's served separately via the
    /screenshot endpoint so list/detail responses stay small."""
    return {
        "id": str(s.id),
        "society_id": str(s.society_id),
        "wing_id": str(s.wing_id) if s.wing_id else None,
        "wing_name": s.wing.name if s.wing else None,
        "flat_id": str(s.flat_id),
        "flat_number": s.flat.flat_number if s.flat else None,
        "bill_id": str(s.bill_id) if s.bill_id else None,
        "bill_invoice_number": s.bill.invoice_number if s.bill else None,
        "receipt_number": s.receipt_number,
        "amount": str(s.amount),
        "purpose": s.purpose.value,
        "payment_date": s.payment_date.isoformat(),
        "payment_mode": s.payment_mode.value,
        "transaction_ref": s.transaction_ref,
        "bank_name": s.bank_name,
        "notes": s.notes,
        "status": s.status.value,
        "recorded_by": str(s.recorded_by) if s.recorded_by else None,
        "reviewed_by": str(s.reviewed_by) if s.reviewed_by else None,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        "review_notes": s.review_notes,
        "screenshot_mime_type": s.screenshot_mime_type,
        "screenshot_file_name": s.screenshot_file_name,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── Financial Periods ─────────────────────────────────────────────────────────
@router.post("/periods", status_code=201, dependencies=[Depends(admin_committee)])
def create_period(data: PeriodCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return BillingService(db).create_period(data.model_dump(), user)

@router.post("/periods/{period_id}/close", dependencies=[Depends(admin_committee)])
def close_period(period_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return BillingService(db).close_period(period_id, user)

@router.get("/periods/{society_id}", dependencies=[Depends(admin_committee)])
def list_periods(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).list_periods(society_id)


# ── Charge Config ─────────────────────────────────────────────────────────────
class ChargeConfigUpdate(OrmBase):
    name: Optional[str] = None
    charge_type: Optional[ChargeType] = None
    default_amount: Optional[Decimal] = None
    is_per_sqft: Optional[bool] = None
    tax_percent: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _charge_out(c) -> dict:
    return {
        "id": str(c.id),
        "society_id": str(c.society_id),
        "charge_type": c.charge_type.value,
        "name": c.name,
        "description": c.description,
        "default_amount": str(c.default_amount) if c.default_amount is not None else None,
        "is_per_sqft": c.is_per_sqft,
        "is_mandatory": c.is_mandatory,
        "tax_percent": str(c.tax_percent),
        "is_active": c.is_active,
    }

@router.post("/charges", status_code=201, dependencies=[Depends(manager_above)])
def create_charge(data: ChargeConfigCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return _charge_out(BillingService(db).create_charge_config(data.model_dump(), user))

@router.get("/charges/{society_id}", dependencies=[Depends(manager_above)])
def list_charges(society_id: UUID, db: Session = Depends(get_db)):
    return [_charge_out(c) for c in BillingService(db).list_charge_configs(society_id)]

@router.patch("/charges/{config_id}", dependencies=[Depends(manager_above)])
def update_charge(config_id: UUID, data: ChargeConfigUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    changes = data.model_dump(exclude_unset=True)
    return _charge_out(BillingService(db).update_charge_config(config_id, changes, user))


# ── Billing Cycles ────────────────────────────────────────────────────────────
def _cycle_out(cy) -> dict:
    live = [b for b in cy.bills if b.is_active and b.bill_status != BillStatus.CANCELLED]
    today = date.today()
    return {
        "id": str(cy.id),
        "society_id": str(cy.society_id),
        "name": cy.name,
        "cycle_start": cy.cycle_start.isoformat(),
        "cycle_end": cy.cycle_end.isoformat(),
        "due_date": cy.due_date.isoformat(),
        "frequency": cy.frequency.value,
        "is_finalized": cy.is_finalized,
        "notes": cy.notes,
        "bills_count": len(live),
        "generated_count": sum(1 for b in live if b.bill_status == BillStatus.GENERATED),
        "paid_count": sum(1 for b in live if b.bill_status == BillStatus.PAID),
        "overdue_count": sum(1 for b in live if _is_overdue(b, today)),
        "total_billed": str(sum((b.total_amount for b in live), Decimal(0))),
        "total_collected": str(sum((b.paid_amount for b in live), Decimal(0))),
        "total_outstanding": str(sum((b.outstanding for b in live), Decimal(0))),
    }

@router.post("/cycles", status_code=201, dependencies=[Depends(manager_above)])
def create_cycle(data: CycleCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    if data.cycle_end < data.cycle_start:
        raise HTTPException(422, "Cycle end date must be on or after the start date")
    return _cycle_out(BillingService(db).create_cycle(data.model_dump(), user, request))

@router.get("/cycles/{society_id}", dependencies=[Depends(manager_above)])
def list_cycles(society_id: UUID, db: Session = Depends(get_db)):
    return [_cycle_out(c) for c in BillingService(db).list_cycles(society_id)]

@router.get("/cycles/detail/{cycle_id}", dependencies=[Depends(manager_above)])
def get_cycle(cycle_id: UUID, db: Session = Depends(get_db)):
    return _cycle_out(BillingService(db).get_cycle(cycle_id))

@router.post("/cycles/{cycle_id}/generate-bills", dependencies=[Depends(manager_above)])
def generate_bills(cycle_id: UUID, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    bills = BillingService(db).generate_bills_for_cycle(cycle_id, user, request)
    return {"bills_generated": len(bills), "cycle_id": str(cycle_id)}

@router.post("/cycles/{cycle_id}/issue-all", dependencies=[Depends(manager_above)])
def issue_all_bills(cycle_id: UUID, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    issued = BillingService(db).issue_all_bills(cycle_id, user, request)
    return {"bills_issued": issued, "cycle_id": str(cycle_id)}

@router.get("/cycles/{cycle_id}/bills", dependencies=[Depends(manager_above)])
def cycle_bills(cycle_id: UUID, db: Session = Depends(get_db)):
    bills = BillingService(db).list_cycle_bills(cycle_id)
    bills.sort(key=lambda b: (
        b.flat.wing.name if b.flat and b.flat.wing else "",
        b.flat.flat_number if b.flat else "",
    ))
    return [_bill_out(b) for b in bills]


# ── Bills ─────────────────────────────────────────────────────────────────────
def _is_overdue(b, today: date) -> bool:
    return (b.outstanding > 0 and b.due_date < today
            and b.bill_status not in (BillStatus.CANCELLED, BillStatus.PAID, BillStatus.GENERATED))

def _bill_out(b) -> dict:
    flat = b.flat
    return {
        "id": str(b.id),
        "cycle_id": str(b.cycle_id),
        "cycle_name": b.cycle.name if b.cycle else None,
        "flat_id": str(b.flat_id),
        "flat_number": flat.flat_number if flat else None,
        "wing_id": str(flat.wing_id) if flat else None,
        "wing_name": flat.wing.name if flat and flat.wing else None,
        "resident_name": b.resident.full_name if b.resident else None,
        "invoice_number": b.invoice_number,
        "bill_status": b.bill_status.value,
        "is_overdue": _is_overdue(b, date.today()),
        "bill_date": b.bill_date.isoformat(),
        "due_date": b.due_date.isoformat(),
        "subtotal": str(b.subtotal),
        "tax_amount": str(b.tax_amount),
        "penalty_amount": str(b.penalty_amount),
        "discount_amount": str(b.discount_amount),
        "total_amount": str(b.total_amount),
        "paid_amount": str(b.paid_amount),
        "outstanding": str(b.outstanding),
        "cancellation_reason": b.cancellation_reason,
    }

def _bill_detail_out(b) -> dict:
    out = _bill_out(b)
    out["line_items"] = [{
        "charge_type": li.charge_type.value,
        "description": li.description,
        "amount": str(li.amount),
        "tax_percent": str(li.tax_percent),
        "tax_amount": str(li.tax_amount),
        "total": str(li.total),
    } for li in b.line_items]
    # Payments land in two tables depending on how they were recorded:
    # PaymentReceipt (POST /payments) and on-bill OnlinePaymentSubmission
    # (the Record Payment form). Both count towards paid_amount.
    payments = [{
        "receipt_number": r.receipt_number,
        "payment_date": r.payment_date.isoformat(),
        "amount": str(r.amount),
        "payment_mode": r.payment_mode.value,
        "transaction_ref": r.transaction_ref,
    } for r in b.receipts if not r.is_reversed]
    payments += [{
        "receipt_number": s.receipt_number,
        "payment_date": s.payment_date.isoformat(),
        "amount": str(s.amount),
        "payment_mode": s.payment_mode.value,
        "transaction_ref": s.transaction_ref,
    } for s in b.online_payments if s.is_active and s.status != ReconciliationStatus.REJECTED]
    out["payments"] = sorted(payments, key=lambda p: p["payment_date"])
    return out

def _ensure_can_view_flat(db: Session, user: User, flat_id) -> None:
    """Managers and above see every flat; anyone else (residents, staff)
    only the flats they're an active resident of. 404 rather than 403 so
    bill/flat IDs can't be probed."""
    if _user_has_permission(user, "manager_above"):
        return
    if flat_id not in BillingService(db).resident_flat_ids(user):
        raise HTTPException(404, "Bill not found")

def _get_viewable_bill(db: Session, user: User, bill_id: UUID):
    bill = BillingService(db).get_bill(bill_id)
    _ensure_can_view_flat(db, user, bill.flat_id)
    if (not _user_has_permission(user, "manager_above")
            and bill.bill_status not in RESIDENT_VISIBLE_BILL_STATUSES):
        raise HTTPException(404, "Bill not found")
    return bill

@router.get("/bills/me", dependencies=[Depends(any_member)])
def my_bills(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bills = BillingService(db).get_my_bills(user)
    today = date.today()
    open_bills = [b for b in bills if b.outstanding > 0]
    return {
        "total_outstanding": str(sum((b.outstanding for b in open_bills), Decimal(0))),
        "open_count": len(open_bills),
        "overdue_count": sum(1 for b in open_bills if _is_overdue(b, today)),
        "bills": [_bill_out(b) for b in bills],
    }

@router.get("/bills/{bill_id}", dependencies=[Depends(any_member)])
def get_bill(bill_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _bill_detail_out(_get_viewable_bill(db, user, bill_id))

@router.get("/bills/{bill_id}/pdf", dependencies=[Depends(any_member)])
def get_bill_pdf(bill_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bill = _get_viewable_bill(db, user, bill_id)
    pdf_bytes = BillingService(db).generate_bill_pdf(bill.id)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={bill.invoice_number}.pdf"},
    )

@router.post("/bills/{bill_id}/issue", dependencies=[Depends(manager_above)])
def issue_bill(bill_id: UUID, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return _bill_detail_out(BillingService(db).issue_bill(bill_id, user, request))

@router.post("/bills/{bill_id}/cancel", dependencies=[Depends(manager_above)])
def cancel_bill(bill_id: UUID, data: CancelBillRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return _bill_detail_out(BillingService(db).cancel_bill(bill_id, data.reason, user))

@router.get("/bills/flat/{flat_id}", dependencies=[Depends(any_member)])
def flat_bills(flat_id: UUID, outstanding_only: bool = False, skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_can_view_flat(db, user, flat_id)
    bills = BillingService(db).get_flat_bills(flat_id, skip, limit)
    if not _user_has_permission(user, "manager_above"):
        bills = [b for b in bills if b.bill_status in RESIDENT_VISIBLE_BILL_STATUSES]
    if outstanding_only:
        bills = [b for b in bills if b.outstanding > 0 and b.bill_status != BillStatus.CANCELLED]
    return [_bill_out(b) for b in bills]

@router.get("/bills/overdue/{society_id}", dependencies=[Depends(manager_above)])
def overdue_bills(society_id: UUID, db: Session = Depends(get_db)):
    return [_bill_out(b) for b in BillingService(db).get_overdue_bills(society_id)]

@router.get("/bills/outstanding/{society_id}", dependencies=[Depends(manager_above)])
def outstanding_bills(society_id: UUID, db: Session = Depends(get_db)):
    return [_bill_out(b) for b in BillingService(db).get_outstanding_bills(society_id)]


# ── Payments & Receipts ───────────────────────────────────────────────────────
@router.post("/payments", status_code=201, dependencies=[Depends(admin_committee)])
def record_payment(data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return BillingService(db).record_payment(data.model_dump(), user, request)

@router.get("/receipts/flat/{flat_id}", dependencies=[Depends(any_member)])
def flat_receipts(flat_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return BillingService(db).get_flat_receipts(flat_id, skip, limit)


# ── Dues ──────────────────────────────────────────────────────────────────────
@router.get("/dues/flat/{flat_id}/{society_id}", dependencies=[Depends(any_member)])
def flat_dues(flat_id: UUID, society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).get_flat_due(flat_id, society_id)

@router.get("/dues/outstanding/{society_id}", dependencies=[Depends(admin_committee)])
def all_outstanding_dues(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).get_all_outstanding_dues(society_id)


# ── Penalty Rules ─────────────────────────────────────────────────────────────
@router.post("/penalty-rules", status_code=201, dependencies=[Depends(admin_committee)])
def create_penalty_rule(data: PenaltyRuleCreate, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    return BillingService(db).create_penalty_rule(data.model_dump(), user)

@router.get("/penalty-rules/{society_id}", dependencies=[Depends(admin_committee)])
def list_penalty_rules(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).list_penalty_rules(society_id)


# ── Payment Receipts (on-bill or on-account, single form) ────────────────────
# FMC Manager records a resident's payment against an existing bill
# (applied immediately, same accounting as /payments above) or on account
# (no bill yet). Either way a receipt is issued immediately; bank
# reconciliation for non-cash modes happens later via the status endpoint
# below — see OnlinePaymentSubmission's docstring.

MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024

@router.post("/online-payments", status_code=201, dependencies=[Depends(manager_above)])
def submit_online_payment(
    flat_id: UUID = Form(...),
    amount: Decimal = Form(...),
    payment_date: date = Form(...),
    payment_mode: PaymentMode = Form(...),
    bill_id: Optional[UUID] = Form(None),
    purpose: ChargeType = Form(ChargeType.MAINTENANCE),
    transaction_ref: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    screenshot_bytes = None
    content_type = None
    if screenshot is not None and screenshot.filename:
        content_type = screenshot.content_type or "application/octet-stream"
        screenshot_bytes = screenshot.file.read()
        if len(screenshot_bytes) > MAX_SCREENSHOT_BYTES:
            raise HTTPException(422, f"Screenshot exceeds the {MAX_SCREENSHOT_BYTES // (1024*1024)}MB limit")
    submission = BillingService(db).create_online_payment_submission(
        flat_id=flat_id, amount=amount, payment_date=payment_date,
        payment_mode=payment_mode, bill_id=bill_id, purpose=purpose,
        transaction_ref=transaction_ref, bank_name=bank_name, notes=notes,
        screenshot_bytes=screenshot_bytes, screenshot_mime_type=content_type,
        screenshot_file_name=screenshot.filename if screenshot else None, user=user,
    )
    return _online_payment_out(submission)

@router.get("/online-payments/society/{society_id}", dependencies=[Depends(manager_above)])
def list_online_payments(
    society_id: UUID,
    status: Optional[ReconciliationStatus] = None,
    wing_id: Optional[UUID] = None,
    flat_id: Optional[UUID] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
):
    rows = BillingService(db).list_online_payment_submissions(
        society_id, status=status, wing_id=wing_id, flat_id=flat_id, skip=skip, limit=limit)
    return [_online_payment_out(r) for r in rows]

@router.get("/online-payments/society/{society_id}/export", dependencies=[Depends(manager_above)])
def export_online_payments(
    society_id: UUID,
    status: Optional[ReconciliationStatus] = None,
    wing_id: Optional[UUID] = None,
    flat_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    csv_text = BillingService(db).export_online_payments_csv(
        society_id, status=status, wing_id=wing_id, flat_id=flat_id)
    return StreamingResponse(
        BytesIO(csv_text.encode("utf-8")), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=online_payments.csv"},
    )

@router.get("/online-payments/{submission_id}", dependencies=[Depends(manager_above)])
def get_online_payment(submission_id: UUID, db: Session = Depends(get_db)):
    return _online_payment_out(BillingService(db).get_online_payment_submission(submission_id))

@router.get("/online-payments/{submission_id}/screenshot", dependencies=[Depends(manager_above)])
def get_online_payment_screenshot(submission_id: UUID, db: Session = Depends(get_db)):
    s = BillingService(db).get_online_payment_submission(submission_id)
    if not s.screenshot_data:
        raise HTTPException(404, "This payment has no screenshot attached")
    return Response(content=s.screenshot_data, media_type=s.screenshot_mime_type)

@router.get("/online-payments/{submission_id}/receipt", dependencies=[Depends(manager_above)])
def get_online_payment_receipt(submission_id: UUID, db: Session = Depends(get_db)):
    pdf_bytes = BillingService(db).generate_online_payment_receipt_pdf(submission_id)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=receipt.pdf"},
    )

@router.patch("/online-payments/{submission_id}/status", dependencies=[Depends(manager_above)])
def update_online_payment_status(
    submission_id: UUID, data: OnlinePaymentStatusUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    submission = BillingService(db).update_online_payment_status(
        submission_id, data.status, data.review_notes, user)
    return _online_payment_out(submission)


# ── Bank Reconciliation ───────────────────────────────────────────────────────
#
# Imports a bank statement (as CSV) and suggests matches against PENDING
# online payment submissions by amount + nearby date. Confirming a match
# is the only thing that flips a submission to RECONCILED via this path —
# see BillingService's Bank Reconciliation section for the full rationale.

def _bank_entry_out(e) -> dict:
    return {
        "id": str(e.id),
        "society_id": str(e.society_id),
        "txn_date": e.txn_date.isoformat(),
        "description": e.description,
        "reference": e.reference,
        "amount": str(e.amount),
        "match_status": e.match_status.value,
        "matched_submission_id": str(e.matched_submission_id) if e.matched_submission_id else None,
        "matched_submission_receipt_number": e.matched_submission.receipt_number if e.matched_submission else None,
        "matched_at": e.matched_at.isoformat() if e.matched_at else None,
        "ignore_reason": e.ignore_reason,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }

@router.post("/bank-reconciliation/society/{society_id}/import", status_code=201,
             dependencies=[Depends(manager_above)])
async def import_bank_statement(
    society_id: UUID, statement: UploadFile = File(...),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    csv_bytes = await statement.read()
    entries = BillingService(db).import_bank_statement_csv(
        society_id, csv_bytes.decode("utf-8-sig"), user)
    return [_bank_entry_out(e) for e in entries]

@router.get("/bank-reconciliation/society/{society_id}", dependencies=[Depends(manager_above)])
def list_bank_statement_entries(
    society_id: UUID,
    match_status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
):
    from app.modules.billing.models.billing import BankStatementMatchStatus
    status_enum = BankStatementMatchStatus(match_status) if match_status else None
    rows = BillingService(db).list_bank_statement_entries(
        society_id, match_status=status_enum, skip=skip, limit=limit)
    return [_bank_entry_out(e) for e in rows]

@router.get("/bank-reconciliation/{entry_id}/candidates", dependencies=[Depends(manager_above)])
def get_bank_match_candidates(entry_id: UUID, db: Session = Depends(get_db)):
    candidates = BillingService(db).suggest_matches(entry_id)
    return [_online_payment_out(c) for c in candidates]

@router.post("/bank-reconciliation/{entry_id}/confirm", dependencies=[Depends(manager_above)])
def confirm_bank_match(
    entry_id: UUID, data: BankMatchConfirm,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    entry = BillingService(db).confirm_bank_match(entry_id, data.submission_id, user)
    return _bank_entry_out(entry)

@router.post("/bank-reconciliation/{entry_id}/ignore", dependencies=[Depends(manager_above)])
def ignore_bank_entry(
    entry_id: UUID, data: BankEntryIgnore,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    entry = BillingService(db).ignore_bank_entry(entry_id, data.reason, user)
    return _bank_entry_out(entry)
