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
    get_current_user, require_roles,
    require_admin_committee, require_any_member, require_manager_above,
)
from app.models.user import User
from app.modules.billing.models.billing import (
    ChargeType, BillStatus, PaymentMode, PenaltyCalculationType, CycleFrequency,
    ReconciliationStatus,
)
from app.modules.billing.services.billing_service import BillingService
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
        "receipt_number": s.receipt_number,
        "amount": str(s.amount),
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
@router.post("/charges", status_code=201, dependencies=[Depends(admin_committee)])
def create_charge(data: ChargeConfigCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return BillingService(db).create_charge_config(data.model_dump(), user)

@router.get("/charges/{society_id}", dependencies=[Depends(admin_committee)])
def list_charges(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).list_charge_configs(society_id)


# ── Billing Cycles ────────────────────────────────────────────────────────────
@router.post("/cycles", status_code=201, dependencies=[Depends(admin_committee)])
def create_cycle(data: CycleCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return BillingService(db).create_cycle(data.model_dump(), user, request)

@router.get("/cycles/{society_id}", dependencies=[Depends(admin_committee)])
def list_cycles(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).list_cycles(society_id)

@router.post("/cycles/{cycle_id}/generate-bills", dependencies=[Depends(admin_committee)])
def generate_bills(cycle_id: UUID, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    bills = BillingService(db).generate_bills_for_cycle(cycle_id, user, request)
    return {"bills_generated": len(bills), "cycle_id": str(cycle_id)}


# ── Bills ─────────────────────────────────────────────────────────────────────
@router.get("/bills/{bill_id}", dependencies=[Depends(any_member)])
def get_bill(bill_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).get_bill(bill_id)

@router.post("/bills/{bill_id}/issue", dependencies=[Depends(admin_committee)])
def issue_bill(bill_id: UUID, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return BillingService(db).issue_bill(bill_id, user, request)

@router.post("/bills/{bill_id}/cancel", dependencies=[Depends(admin_committee)])
def cancel_bill(bill_id: UUID, data: CancelBillRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return BillingService(db).cancel_bill(bill_id, data.reason, user)

@router.get("/bills/flat/{flat_id}", dependencies=[Depends(any_member)])
def flat_bills(flat_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return BillingService(db).get_flat_bills(flat_id, skip, limit)

@router.get("/bills/overdue/{society_id}", dependencies=[Depends(admin_committee)])
def overdue_bills(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).get_overdue_bills(society_id)

@router.get("/bills/outstanding/{society_id}", dependencies=[Depends(admin_committee)])
def outstanding_bills(society_id: UUID, db: Session = Depends(get_db)):
    return BillingService(db).get_outstanding_bills(society_id)


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


# ── Online Payment Submissions (resident payment screenshots) ────────────────
# FMC Manager selects a Wing + Flat, uploads a resident's UPI/bank-transfer
# screenshot, and the details are captured here for later bank
# reconciliation. Independent of the bill-linked Payments/Receipts above —
# no bill needs to exist yet.

MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024

@router.post("/online-payments", status_code=201, dependencies=[Depends(manager_above)])
def submit_online_payment(
    flat_id: UUID = Form(...),
    amount: Decimal = Form(...),
    payment_date: date = Form(...),
    payment_mode: PaymentMode = Form(...),
    transaction_ref: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    screenshot: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content_type = screenshot.content_type or "application/octet-stream"
    data = screenshot.file.read()
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise HTTPException(422, f"Screenshot exceeds the {MAX_SCREENSHOT_BYTES // (1024*1024)}MB limit")
    submission = BillingService(db).create_online_payment_submission(
        flat_id=flat_id, amount=amount, payment_date=payment_date,
        payment_mode=payment_mode, transaction_ref=transaction_ref,
        bank_name=bank_name, notes=notes,
        screenshot_bytes=data, screenshot_mime_type=content_type,
        screenshot_file_name=screenshot.filename, user=user,
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
