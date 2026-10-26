"""Bring in the maintenance members paid in advance, from a sheet, one payment per row.

Each row is recorded exactly like Record Payment on account: a receipt is issued, the money goes into the bank or cash
ledger, and — the bills not being raised yet — it stays as the flat's advance, credited to the "Advance Maintenance
from Members" ledger (a current liability) under the flat's own advance account. When a bill is raised the advance is
set off against it automatically, oldest bill first, and what is left stays as the flat's balance."""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.user import User
from app.modules.billing.models.billing import (
    ChargeType, OnlinePaymentSubmission, PaymentMode, ReconciliationStatus,
)
from app.modules.billing.services.billing_service import BillingService
from app.services.flat_lookup import FlatLookup, clean

MAX_AMOUNT = Decimal("100000000")

_MODE_WORDS = {
    PaymentMode.CASH: {"cash"},
    PaymentMode.CHEQUE: {"cheque", "check", "chq", "dd", "demand draft"},
    PaymentMode.UPI: {"upi", "gpay", "phonepe", "paytm"},
    PaymentMode.NEFT: {"neft"},
    PaymentMode.RTGS: {"rtgs"},
    PaymentMode.BANK_TRANSFER: {"bank transfer", "bank", "transfer", "imps", "bank_transfer", "net banking", "online"},
}


def parse_mode(text: str) -> PaymentMode:
    key = clean(text).lower().replace("-", " ")
    for mode, words in _MODE_WORDS.items():
        if key in words:
            return mode
    raise ValueError("Payment mode must be cash, cheque, UPI, NEFT, RTGS or bank transfer")


class AdvanceImportRow(BaseModel):
    """One line of the file. Everything arrives as text (or null); the service reads it the way a person typed it."""
    line:            Optional[int] = None
    wing:            Optional[str] = None
    flat_number:     Optional[str] = None
    amount:          Optional[str] = None
    payment_date:    Optional[str] = None       # ISO date; the app converts dd/mm/yyyy before sending
    payment_mode:    Optional[str] = None
    transaction_ref: Optional[str] = None       # cheque / UTR number
    bank_name:       Optional[str] = None
    notes:           Optional[str] = None


class AdvanceImportRequest(BaseModel):
    society_id: Optional[UUID] = None
    rows: List[AdvanceImportRow] = Field(max_length=2000)
    dry_run: bool = False


class AdvanceImportResult(BaseModel):
    line: Optional[int] = None
    wing: Optional[str] = None
    flat_number: Optional[str] = None
    status: str                                 # ready (dry run) | recorded | error
    receipt_number: Optional[str] = None
    message: Optional[str] = None


def _amount(text: str) -> Decimal:
    try:
        value = Decimal(clean(text).replace(",", "").replace("₹", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("Amount must be a number")
    if value <= 0 or value > MAX_AMOUNT:
        raise ValueError("Amount must be more than zero")
    return value


def import_advances(db: Session, society_id: Optional[UUID], rows: List[AdvanceImportRow], dry_run: bool,
                    user: User) -> List[AdvanceImportResult]:
    society_id = resolve_create_society_id(user, society_id)
    lookup = FlatLookup(db, society_id)
    service = BillingService(db)
    seen = {}
    out: List[AdvanceImportResult] = []
    for row in rows:
        wing, number = clean(row.wing), clean(row.flat_number)
        res = lambda status, **kw: out.append(AdvanceImportResult(
            line=row.line, wing=wing or None, flat_number=number or None, status=status, **kw))
        try:
            flat = lookup.find(wing, number)
            amount = _amount(row.amount or "")
            text = clean(row.payment_date)
            if not text:
                raise ValueError("Payment date is empty")
            try:
                paid_on = date.fromisoformat(text)
            except ValueError:
                raise ValueError("Payment date must be a date (yyyy-mm-dd)")
            if paid_on > date.today():
                raise ValueError("Payment date is in the future")
            if paid_on < date(2000, 1, 1):
                raise ValueError("Payment date is too old")
            mode = parse_mode(row.payment_mode or "")
            ref = clean(row.transaction_ref) or None

            # The same payment twice (a file imported again) would double the flat's advance.
            key = (flat.id, amount, paid_on, (ref or "").lower())
            if key in seen:
                raise ValueError(f"The same payment appears again (line {seen[key]} of the file)")
            q = db.query(OnlinePaymentSubmission).filter(
                OnlinePaymentSubmission.flat_id == flat.id, OnlinePaymentSubmission.amount == amount,
                OnlinePaymentSubmission.payment_date == paid_on, OnlinePaymentSubmission.is_active == True,  # noqa: E712
                OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED)
            same = [s for s in q if (s.transaction_ref or "").lower() == (ref or "").lower()]
            if same:
                raise ValueError(f"Already recorded as receipt {same[0].receipt_number}")
            seen[key] = row.line or 0

            if dry_run:
                res("ready")
                continue
            sub = service.create_online_payment_submission(
                flat_id=flat.id, amount=amount, payment_date=paid_on, payment_mode=mode, transaction_ref=ref,
                bank_name=clean(row.bank_name) or None, notes=clean(row.notes) or "Advance maintenance (imported)",
                user=user, purpose=ChargeType.MAINTENANCE, require_screenshot=False)
            res("recorded", receipt_number=sub.receipt_number)
        except HTTPException as exc:
            db.rollback()
            res("error", message=str(exc.detail))
        except ValueError as exc:
            res("error", message=str(exc))
    return out
