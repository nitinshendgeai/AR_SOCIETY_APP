from typing import List, Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_any_member,
)
from app.models.user import User
from app.modules.billing.models.billing import (
    ChargeType, BillStatus, PaymentMode, PenaltyCalculationType, CycleFrequency,
)
from app.modules.billing.services.billing_service import BillingService
from app.schemas.common import OrmBase, TimestampSchema
from typing import Optional

router = APIRouter(prefix="/billing", tags=["Maintenance Billing & Finance"])

admin_committee = require_admin_committee
any_member      = require_any_member


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
