import re
from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from app.schemas import validators as val
from app.core.tenant_scope import assert_society_access
from fastapi.responses import Response, StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles, _user_has_permission,
    require_any_member, require_manager_above,
)
from app.models.user import User
from app.models.flat import Flat
from app.modules.billing.models.billing import (
    ChargeType, BillStatus, PaymentMode, PenaltyCalculationType, CycleFrequency,
    ReconciliationStatus, ChargeBasis, FlatChargeKind, FlatChargeStatus,
)
from app.modules.billing.services.maintenance_calculator import cycle_months, money
from app.modules.billing.services.billing_service import BillingService, RESIDENT_VISIBLE_BILL_STATUSES
from app.modules.billing.services.budget_suggestions import suggest_budgets
from app.modules.billing.services.flat_charges import FlatChargeService
from app.modules.billing.services.allocations import PaymentAllocator, allocated, payment_counts, unapplied
from app.schemas.common import OrmBase, TimestampSchema
from typing import Optional

router = APIRouter(prefix="/billing", tags=["Maintenance Billing & Finance"])

# The whole maintenance module (periods, charge heads and elements, cycles,
# bills, payments, dues, interest rules) is open to Manager and above: the
# society's manager runs billing day to day, not only the committee.
any_member      = require_any_member
manager_above   = require_manager_above


# ── Inline schemas ────────────────────────────────────────────────────────────
class PeriodCreate(OrmBase):
    society_id: UUID; name: str; period_start: date; period_end: date

class ChargeConfigCreate(OrmBase):
    # With element_id, anything left out is taken from the element.
    society_id: UUID
    element_id: Optional[UUID] = None
    charge_type: Optional[ChargeType] = None; name: Optional[str] = None
    default_amount: Optional[Decimal] = None; is_per_sqft: Optional[bool] = None
    basis: Optional[ChargeBasis] = None
    is_service_charge: Optional[bool] = None; gst_applicable: Optional[bool] = None
    is_mandatory: bool = True; tax_percent: Decimal = Decimal(0)
    description: Optional[str] = None; effective_from: Optional[date] = None
    auto_from_expenses: bool = False
    expense_months: int = Field(default=12, ge=1, le=36)

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
        # Set off against the flat's bills; what's left is the member's advance
        "allocations": [{
            "bill_id": str(a.bill_id),
            "invoice_number": a.bill.invoice_number if a.bill else None,
            "bill_date": a.bill.bill_date.isoformat() if a.bill else None,
            "amount": str(a.amount),
            "allocated_at": a.created_at.isoformat() if a.created_at else None,
            "released_at": a.released_at.isoformat() if a.released_at else None,
            "released_reason": a.released_reason,
        } for a in s.allocations],
        "applied_amount": str(allocated(s)),
        "unapplied_amount": str(unapplied(s)),
    }


# ── Financial Periods ─────────────────────────────────────────────────────────
@router.post("/periods", status_code=201, dependencies=[Depends(manager_above)])
def create_period(data: PeriodCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return BillingService(db).create_period(data.model_dump(), user)

@router.post("/periods/{period_id}/close", dependencies=[Depends(manager_above)])
def close_period(period_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return BillingService(db).close_period(period_id, user)

@router.get("/periods/{society_id}", dependencies=[Depends(manager_above)])
def list_periods(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return BillingService(db).list_periods(society_id)


# ── Charge Config ─────────────────────────────────────────────────────────────
class ChargeConfigUpdate(OrmBase):
    name: Optional[str] = None
    charge_type: Optional[ChargeType] = None
    default_amount: Optional[Decimal] = None
    is_per_sqft: Optional[bool] = None
    basis: Optional[ChargeBasis] = None
    is_service_charge: Optional[bool] = None
    gst_applicable: Optional[bool] = None
    tax_percent: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    auto_from_expenses: Optional[bool] = None
    expense_months: Optional[int] = Field(default=None, ge=1, le=36)


def _charge_out(c) -> dict:
    return {
        "id": str(c.id),
        "society_id": str(c.society_id),
        "charge_type": c.charge_type.value,
        "name": c.name,
        "description": c.description,
        "default_amount": str(c.default_amount) if c.default_amount is not None else None,
        "is_per_sqft": c.is_per_sqft,
        "basis": (c.basis or ChargeBasis.FIXED).value,
        "is_service_charge": c.is_service_charge,
        "gst_applicable": c.gst_applicable,
        "is_mandatory": c.is_mandatory,
        "tax_percent": str(c.tax_percent),
        "element_id": str(c.element_id) if c.element_id else None,
        "element_name": c.element.name if c.element else None,
        "auto_from_expenses": bool(c.auto_from_expenses),
        "expense_months": c.expense_months or 12,
        "is_active": c.is_active,
    }

@router.post("/charges", status_code=201, dependencies=[Depends(manager_above)])
def create_charge(data: ChargeConfigCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return _charge_out(BillingService(db).create_charge_config(data.model_dump(), user))

@router.get("/charges/{society_id}", dependencies=[Depends(manager_above)])
def list_charges(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return [_charge_out(c) for c in BillingService(db).list_charge_configs(society_id)]

@router.get("/charges/{society_id}/budget-suggestions", dependencies=[Depends(manager_above)])
def budget_suggestions(society_id: UUID, months: int = Query(12, ge=1, le=36),
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Suggested charge-head amounts from what the last `months` cost on the
    expense ledgers linked to each element (see services/budget_suggestions.py).
    Read-only."""
    assert_society_access(user, society_id)
    return suggest_budgets(db, society_id, months)

@router.patch("/charges/{config_id}", dependencies=[Depends(manager_above)])
def update_charge(config_id: UUID, data: ChargeConfigUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    changes = data.model_dump(exclude_unset=True)
    for key in ("auto_from_expenses", "expense_months"):
        if key in changes and changes[key] is None:
            del changes[key]
    return _charge_out(BillingService(db).update_charge_config(config_id, changes, user))


# ── Maintenance element master ────────────────────────────────────────────────
class ElementCreate(OrmBase):
    society_id: UUID
    name: str = Field(..., min_length=1, max_length=150)
    category: ChargeType = ChargeType.OTHER
    default_basis: ChargeBasis = ChargeBasis.FIXED
    default_amount: Optional[Decimal] = Field(None, ge=0)
    is_service_charge: bool = False
    gst_applicable: bool = True
    description: Optional[str] = None
    bye_law_ref: Optional[str] = Field(None, max_length=150)


class ElementUpdate(OrmBase):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    category: Optional[ChargeType] = None
    default_basis: Optional[ChargeBasis] = None
    default_amount: Optional[Decimal] = Field(None, ge=0)
    is_service_charge: Optional[bool] = None
    gst_applicable: Optional[bool] = None
    description: Optional[str] = None
    bye_law_ref: Optional[str] = Field(None, max_length=150)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ChargesFromElementsItem(OrmBase):
    element_id: UUID
    amount: Optional[Decimal] = Field(None, ge=0)


class ChargesFromElements(OrmBase):
    society_id: UUID
    items: List[ChargesFromElementsItem] = Field(..., min_length=1)


def _element_out(e) -> dict:
    return {
        "id": str(e.id),
        "society_id": str(e.society_id),
        "code": e.code,
        "name": e.name,
        "description": e.description,
        "bye_law_ref": e.bye_law_ref,
        "category": e.category.value,
        "default_basis": e.default_basis.value,
        "default_amount": str(e.default_amount) if e.default_amount is not None else None,
        "is_service_charge": e.is_service_charge,
        "gst_applicable": e.gst_applicable,
        "sort_order": e.sort_order,
        "is_system": e.is_system,
        "is_active": e.is_active,
    }

@router.get("/elements/{society_id}", dependencies=[Depends(manager_above)])
def list_elements(society_id: UUID, include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return [_element_out(e) for e in BillingService(db).list_elements(society_id, include_inactive)]

@router.post("/elements", status_code=201, dependencies=[Depends(manager_above)])
def create_element(data: ElementCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return _element_out(BillingService(db).create_element(data.model_dump(), user))

@router.patch("/elements/{element_id}", dependencies=[Depends(manager_above)])
def update_element(element_id: UUID, data: ElementUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    changes = data.model_dump(exclude_unset=True)
    return _element_out(BillingService(db).update_element(element_id, changes, user))

@router.post("/charges/from-elements", status_code=201, dependencies=[Depends(manager_above)])
def create_charges_from_elements(data: ChargesFromElements, db: Session = Depends(get_db),
                                 user: User = Depends(get_current_user)):
    items = [i.model_dump() for i in data.items]
    created = BillingService(db).create_charges_from_elements(data.society_id, items, user)
    return [_charge_out(c) for c in created]


# ── Maintenance rules ─────────────────────────────────────────────────────────
class MaintenanceSettingsUpdate(OrmBase):
    construction_cost_per_sqft: Optional[Decimal] = Field(None, ge=0)
    # Simple interest on arrears: the 2026 MCS amendment caps it at 12%
    # p.a.; 21% is the older model bye-law ceiling some societies and
    # states still use, so that's the hard limit here.
    interest_rate_pct: Optional[Decimal] = Field(None, ge=0, le=21)
    interest_grace_days: Optional[int] = Field(None, ge=0, le=90)
    # Non-occupancy charges may not exceed 10% of service charges.
    non_occupancy_pct: Optional[Decimal] = Field(None, ge=0, le=10)
    gst_enabled: Optional[bool] = None
    gst_rate_pct: Optional[Decimal] = Field(None, ge=0, le=28)
    gst_threshold_monthly: Optional[Decimal] = Field(None, ge=0)
    # Payment details printed on bills. Empty text clears a field.
    bank_account_name: Optional[str] = Field(None, max_length=150)
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_account_number: Optional[str] = Field(None, max_length=40)
    bank_ifsc: Optional[str] = Field(None, max_length=20)
    upi_id: Optional[str] = Field(None, max_length=100)
    bill_notes: Optional[str] = Field(None, max_length=1000)
    # Billing in this app starts on (empty clears it: every cycle then bills its own period only)
    billing_start_date: Optional[date] = None

    @field_validator("billing_start_date")
    @classmethod
    def _start_sane(cls, v):
        if v is not None and not (date(1990, 1, 1) <= v <= date.today() + timedelta(days=366)):
            raise ValueError("Billing start date must be between 1990 and a year from today")
        return v

    @field_validator("bank_account_name", "bank_name", "bank_account_number",
                     "bank_ifsc", "upi_id", "bill_notes")
    @classmethod
    def _blank_is_none(cls, v):
        return (v.strip() or None) if isinstance(v, str) else v

    @field_validator("bank_account_number")
    @classmethod
    def _account_number(cls, v):
        if v and not re.fullmatch(r"\d{6,20}", v.replace(" ", "")):
            raise ValueError("Account number should be 6-20 digits")
        return v.replace(" ", "") if v else v

    @field_validator("bank_ifsc")
    @classmethod
    def _ifsc(cls, v):
        if v and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", v.upper()):
            raise ValueError("IFSC should look like SBIN0001234")
        return v.upper() if v else v

    @field_validator("upi_id")
    @classmethod
    def _upi(cls, v):
        if v and not re.fullmatch(r"[\w.\-]{2,}@[A-Za-z][\w.]*", v):
            raise ValueError("UPI ID should look like society@okaxis")
        return v


def _settings_out(st) -> dict:
    return {
        "society_id": str(st.society_id),
        "construction_cost_per_sqft": str(st.construction_cost_per_sqft) if st.construction_cost_per_sqft is not None else None,
        "interest_rate_pct": str(st.interest_rate_pct),
        "interest_grace_days": st.interest_grace_days,
        "non_occupancy_pct": str(st.non_occupancy_pct),
        "gst_enabled": st.gst_enabled,
        "gst_rate_pct": str(st.gst_rate_pct),
        "gst_threshold_monthly": str(st.gst_threshold_monthly),
        "bank_account_name": st.bank_account_name,
        "bank_name": st.bank_name,
        "bank_account_number": st.bank_account_number,
        "bank_ifsc": st.bank_ifsc,
        "upi_id": st.upi_id,
        "bill_notes": st.bill_notes,
        "billing_start_date": st.billing_start_date.isoformat() if st.billing_start_date else None,
    }

@router.get("/maintenance-settings/{society_id}", dependencies=[Depends(manager_above)])
def get_maintenance_settings(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return _settings_out(BillingService(db).get_maintenance_settings(society_id))

@router.put("/maintenance-settings/{society_id}", dependencies=[Depends(manager_above)])
def update_maintenance_settings(society_id: UUID, data: MaintenanceSettingsUpdate,
                                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    changes = data.model_dump(exclude_unset=True)
    return _settings_out(BillingService(db).update_maintenance_settings(society_id, changes, user))


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
def list_cycles(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return [_cycle_out(c) for c in BillingService(db).list_cycles(society_id)]

@router.get("/cycles/detail/{cycle_id}", dependencies=[Depends(manager_above)])
def get_cycle(cycle_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cycle = BillingService(db).get_cycle(cycle_id)
    assert_society_access(user, cycle.society_id)
    return _cycle_out(cycle)

@router.get("/cycles/{cycle_id}/preview", dependencies=[Depends(manager_above)])
def preview_cycle(cycle_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cycle = BillingService(db).get_cycle(cycle_id)
    assert_society_access(user, cycle.society_id)
    calc = BillingService(db).preview_cycle(cycle_id)
    flats = []
    for d in sorted(calc.drafts, key=lambda d: (
            d.flat.wing.name if d.flat.wing else "", d.flat.flat_number)):
        flats.append({
            "flat_id": str(d.flat.id),
            "flat_label": f"{d.flat.wing.name if d.flat.wing else ''} / {d.flat.flat_number}".strip(" /"),
            "area_sqft": d.flat.area_sqft,
            "occupancy": d.flat.occupancy_status.value if d.flat.occupancy_status else None,
            "previous_dues": str(d.previous_dues),
            "period_start": d.period_start.isoformat() if d.period_start else None,
            "period_end": d.period_end.isoformat() if d.period_end else None,
            "months": str(d.months.normalize()) if d.months else None,
            "lines": [{
                "charge_type": l.charge_type.value,
                "description": l.description,
                "amount": str(l.amount),
                "tax_percent": str(l.tax_percent),
                "tax_amount": str(l.tax_amount),
                "total": str(l.total),
            } for l in d.lines],
            "subtotal": str(d.subtotal),
            "tax": str(d.tax),
            "total": str(d.total),
        })
    return {
        "cycle_id": str(cycle_id),
        "months": cycle_months(calc.cycle),
        "flats_count": len(flats),
        "total": str(money(sum((d.total for d in calc.drafts), Decimal(0)))),
        "warnings": calc.warnings,
        "flats": flats,
    }

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
def cycle_bills(cycle_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cycle = BillingService(db).get_cycle(cycle_id)
    assert_society_access(user, cycle.society_id)
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
        "previous_dues": str(b.previous_dues or 0),
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
    # PaymentReceipt (POST /payments) and OnlinePaymentSubmission (the
    # Record Payment form), set off against this bill through
    # PaymentAllocation — only the part set off here is listed.
    payments = [{
        "receipt_number": r.receipt_number,
        "payment_date": r.payment_date.isoformat(),
        "amount": str(r.amount),
        "payment_mode": r.payment_mode.value,
        "transaction_ref": r.transaction_ref,
    } for r in b.receipts if not r.is_reversed]
    payments += [{
        "receipt_number": a.payment.receipt_number,
        "payment_date": a.payment.payment_date.isoformat(),
        "amount": str(a.amount),
        "payment_mode": a.payment.payment_mode.value,
        "transaction_ref": a.payment.transaction_ref,
    } for a in b.allocations if a.is_live and payment_counts(a.payment)]
    out["payments"] = sorted(payments, key=lambda p: p["payment_date"])
    return out

def _ensure_can_view_flat(db: Session, user: User, flat_id) -> None:
    """Managers and above see every flat in their own society; anyone else
    (residents, staff) only the flats they're an active resident of.
    404 rather than 403 so bill/flat IDs can't be probed."""
    flat = db.get(Flat, flat_id)
    if flat is None or flat.wing is None:
        raise HTTPException(404, "Bill not found")
    assert_society_access(user, flat.wing.society_id)
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
def overdue_bills(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return [_bill_out(b) for b in BillingService(db).get_overdue_bills(society_id)]

@router.get("/bills/outstanding/{society_id}", dependencies=[Depends(manager_above)])
def outstanding_bills(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return [_bill_out(b) for b in BillingService(db).get_outstanding_bills(society_id)]


# ── Payments & Receipts ───────────────────────────────────────────────────────
@router.post("/payments", status_code=201, dependencies=[Depends(manager_above)])
def record_payment(data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return BillingService(db).record_payment(data.model_dump(), user, request)

@router.get("/receipts/flat/{flat_id}", dependencies=[Depends(any_member)])
def flat_receipts(flat_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_can_view_flat(db, user, flat_id)
    return BillingService(db).get_flat_receipts(flat_id, skip, limit)

@router.get("/receipts/{receipt_number}/pdf", dependencies=[Depends(any_member)])
def get_receipt_pdf(receipt_number: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """The receipt for one payment — on billing or on account — as its own
    document (receipts are never printed on the maintenance bill). Members
    get the receipts of their own flats."""
    svc = BillingService(db)
    payment = svc.get_payment_by_receipt_number(receipt_number)
    try:
        _ensure_can_view_flat(db, user, payment.flat_id)
    except HTTPException:
        raise HTTPException(404, "Receipt not found")
    return Response(
        content=svc.generate_receipt_pdf(payment), media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=Receipt-{receipt_number}.pdf"},
    )


# ── Dues ──────────────────────────────────────────────────────────────────────
@router.get("/dues/flat/{flat_id}/{society_id}", dependencies=[Depends(any_member)])
def flat_dues(flat_id: UUID, society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    flat = db.get(Flat, flat_id)
    if flat is None or flat.wing is None or flat.wing.society_id != society_id:
        raise HTTPException(404, "Flat not found")
    _ensure_can_view_flat(db, user, flat_id)
    return BillingService(db).get_flat_due(flat_id, society_id)

@router.get("/dues/outstanding/{society_id}", dependencies=[Depends(manager_above)])
def all_outstanding_dues(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return BillingService(db).get_all_outstanding_dues(society_id)


# ── Penalty Rules ─────────────────────────────────────────────────────────────
@router.post("/penalty-rules", status_code=201, dependencies=[Depends(manager_above)])
def create_penalty_rule(data: PenaltyRuleCreate, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    return BillingService(db).create_penalty_rule(data.model_dump(), user)

@router.get("/penalty-rules/{society_id}", dependencies=[Depends(manager_above)])
def list_penalty_rules(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
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
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    assert_society_access(user, society_id)
    rows = BillingService(db).list_online_payment_submissions(
        society_id, status=status, wing_id=wing_id, flat_id=flat_id, skip=skip, limit=limit)
    return [_online_payment_out(r) for r in rows]

@router.get("/online-payments/society/{society_id}/export", dependencies=[Depends(manager_above)])
def export_online_payments(
    society_id: UUID,
    status: Optional[ReconciliationStatus] = None,
    wing_id: Optional[UUID] = None,
    flat_id: Optional[UUID] = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    assert_society_access(user, society_id)
    csv_text = BillingService(db).export_online_payments_csv(
        society_id, status=status, wing_id=wing_id, flat_id=flat_id)
    return StreamingResponse(
        BytesIO(csv_text.encode("utf-8")), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=online_payments.csv"},
    )

@router.get("/online-payments/society/{society_id}/unapplied", dependencies=[Depends(manager_above)])
def unapplied_payments(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Money members have paid that isn't set off against a bill yet: an
    advance, or (for payments recorded before set-off) one that could
    settle a bill that is still open."""
    from app.core.tenant_scope import assert_society_access
    assert_society_access(user, society_id)
    alloc = PaymentAllocator(db)
    rows = alloc.society_unapplied(society_id)
    settleable = {f: amt for f, amt in rows.items() if alloc.open_bills(f)}
    return {
        "flats": len(rows), "amount": str(sum(rows.values(), Decimal("0.00"))),
        "flats_with_open_bills": len(settleable),
        "amount_against_open_bills": str(sum(settleable.values(), Decimal("0.00"))),
    }


@router.post("/online-payments/society/{society_id}/apply", dependencies=[Depends(manager_above)])
def apply_unapplied_payments(society_id: UUID, db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """Set every flat's unapplied payments off against its open bills,
    oldest first."""
    from app.core.tenant_scope import assert_society_access
    assert_society_access(user, society_id)
    result = PaymentAllocator(db).apply_society(society_id, user)
    db.commit()
    return result


@router.get("/online-payments/{submission_id}", dependencies=[Depends(manager_above)])
def get_online_payment(submission_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, BillingService(db).get_online_payment_submission(submission_id).society_id)
    return _online_payment_out(BillingService(db).get_online_payment_submission(submission_id))

@router.get("/online-payments/{submission_id}/screenshot", dependencies=[Depends(manager_above)])
def get_online_payment_screenshot(submission_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = BillingService(db).get_online_payment_submission(submission_id, user)
    if not s.screenshot_data:
        raise HTTPException(404, "This payment has no screenshot attached")
    return Response(content=s.screenshot_data, media_type=s.screenshot_mime_type)

@router.get("/online-payments/{submission_id}/receipt", dependencies=[Depends(manager_above)])
def get_online_payment_receipt(submission_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, BillingService(db).get_online_payment_submission(submission_id).society_id)
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
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    assert_society_access(user, society_id)
    from app.modules.billing.models.billing import BankStatementMatchStatus
    status_enum = BankStatementMatchStatus(match_status) if match_status else None
    rows = BillingService(db).list_bank_statement_entries(
        society_id, match_status=status_enum, skip=skip, limit=limit)
    return [_bank_entry_out(e) for e in rows]

@router.get("/bank-reconciliation/{entry_id}/candidates", dependencies=[Depends(manager_above)])
def get_bank_match_candidates(entry_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = BillingService(db).get_bank_statement_entry(entry_id)
    assert_society_access(user, entry.society_id)
    candidates = BillingService(db).suggest_matches(entry_id, user)
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


# ── Members' dues & defaulters ────────────────────────────────────────────────
#
# Each flat's maintenance dues aged from the bills' due dates, and the list
# of defaulters (dues outstanding longer than the limit — 3 months by
# default) the committee reviews, puts up for the general body and sends
# reminders from.

class DuesReminderRequest(OrmBase):
    flat_ids: Optional[List[UUID]] = None   # None: every defaulter
    min_months: int = Field(default=3, ge=1, le=24)


def _defaulters_payload(db: Session, society_id: UUID, min_months: int, include_all: bool) -> dict:
    from app.modules.billing.services.bill_pdf import flat_label
    from app.modules.billing.services.defaulters import (
        AGE_BUCKETS, MemberDues, bill_label, member_contact, months_before,
    )

    as_of = date.today()
    cutoff = months_before(as_of, min_months)
    dues = MemberDues(db).flats(society_id, as_of)
    settings = BillingService(db).get_maintenance_settings(society_id)
    flats, totals = [], {k: Decimal(0) for k, _, _ in AGE_BUCKETS}
    total_outstanding = in_default = defaulters_amount = Decimal(0)
    defaulters = 0
    for fd in dues:
        buckets = fd.by_bucket()
        beyond = fd.overdue_beyond(cutoff)
        total_outstanding += fd.total
        for k, v in buckets.items():
            totals[k] += v
        if beyond > 0:
            defaulters += 1
            defaulters_amount += fd.total
            in_default += beyond
        if not include_all and beyond <= 0:
            continue
        name, phone = member_contact(fd.flat)
        oldest = fd.oldest
        flats.append({
            "flat_id": str(fd.flat.id), "flat_label": flat_label(fd.flat),
            "wing": fd.flat.wing.name if fd.flat.wing else None, "flat_number": fd.flat.flat_number,
            "member_name": name, "phone": phone,
            "total": str(money(fd.total)), "in_default": str(money(beyond)), "is_defaulter": beyond > 0,
            "buckets": {k: str(money(v)) for k, v in buckets.items()},
            "oldest_due_date": oldest.bill.due_date.isoformat(), "days_overdue": oldest.days_overdue,
            "unpaid_bills": len(fd.bills), "on_account": str(money(fd.on_account)),
            "last_payment_date": fd.last_payment_date.isoformat() if fd.last_payment_date else None,
            "last_payment_amount": str(money(fd.last_payment_amount)) if fd.last_payment_amount is not None else None,
            "last_reminded_at": fd.last_reminded_at.isoformat() if fd.last_reminded_at else None,
            "bills": [{
                "bill_id": str(b.bill.id), "invoice_number": b.bill.invoice_number, "period": bill_label(b.bill),
                "bill_date": b.bill.bill_date.isoformat(), "due_date": b.bill.due_date.isoformat(),
                "outstanding": str(money(b.outstanding)), "days_overdue": b.days_overdue, "bucket": b.bucket,
            } for b in fd.bills],
        })
    flats.sort(key=lambda r: ((r["wing"] or ""), _natural(r["flat_number"])))
    return {
        "summary": {
            "as_of": as_of.isoformat(), "min_months": min_months, "include_all": include_all,
            "default_cutoff": cutoff.isoformat(),
            "flats_with_dues": len(dues), "total_outstanding": str(money(total_outstanding)),
            "defaulters": defaulters, "defaulters_outstanding": str(money(defaulters_amount)),
            "in_default": str(money(in_default)),
            "buckets": [{"key": k, "label": label, "amount": str(money(totals[k]))} for k, label, _ in AGE_BUCKETS],
            "interest_rate_pct": str(settings.interest_rate_pct) if settings and settings.interest_rate_pct else None,
        },
        "flats": flats,
    }


def _natural(s: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


@router.get("/defaulters/{society_id}", dependencies=[Depends(manager_above)])
def defaulters_list(society_id: UUID, min_months: int = Query(3, ge=1, le=24), include_all: bool = False,
                    format: str = Query("json", pattern="^(json|pdf)$"),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Defaulters — flats with dues outstanding more than `min_months`
    after the due date — or, with include_all, every flat with dues. JSON,
    or ?format=pdf for the printed list."""
    from app.core.tenant_scope import assert_society_access
    assert_society_access(user, society_id)
    data = _defaulters_payload(db, society_id, min_months, include_all)
    if format == "pdf":
        from app.models.society import Society
        from app.modules.billing.services.defaulters_pdf import render_defaulters_pdf
        society = db.query(Society).filter(Society.id == society_id).first()
        return Response(content=render_defaulters_pdf(data, society), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename=Defaulters-{data['summary']['as_of']}.pdf"})
    return data


@router.post("/defaulters/{society_id}/remind", dependencies=[Depends(manager_above)])
def remind_defaulters(society_id: UUID, data: DuesReminderRequest, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Remind the chosen flats — or every defaulter — of their dues, by app
    notification to the members who have a login."""
    from app.core.tenant_scope import assert_society_access
    from app.modules.billing.services.defaulters import MemberDues
    assert_society_access(user, society_id)
    return MemberDues(db).remind(society_id, data.flat_ids, data.min_months, user)


# ── Fines and additional charges on a flat ────────────────────────────────────

class FlatChargeCreate(OrmBase):
    society_id: UUID
    flat_id: UUID
    kind: FlatChargeKind = FlatChargeKind.FINE
    title: str = Field(max_length=150)
    reason: Optional[str] = None
    amount: Decimal = Field(gt=0, lt=Decimal(100_000_000), max_digits=12, decimal_places=2)
    gst_applicable: bool = False
    effective_date: date
    recurring: bool = False
    end_date: Optional[date] = None

    _title = field_validator("title", mode="before")(val.line_max(150, required=True))
    _reason = field_validator("reason", mode="before")(val.note_max(1000))
    _dates = field_validator("effective_date", "end_date")(val.sane_date)

    @model_validator(mode="after")
    def _period(self):
        if self.end_date and self.end_date < self.effective_date:
            raise ValueError("The end date can't be before the effective date")
        return self


class FlatChargeCancel(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(1000, required=True))


def _flat_charge_out(c) -> dict:
    return {
        "id": str(c.id), "society_id": str(c.society_id), "flat_id": str(c.flat_id),
        "flat_number": c.flat_number, "wing_name": c.wing_name,
        "kind": c.kind.value, "title": c.title, "reason": c.reason, "amount": str(c.amount),
        "gst_applicable": c.gst_applicable, "effective_date": c.effective_date.isoformat(),
        "recurring": c.recurring, "end_date": c.end_date.isoformat() if c.end_date else None,
        "status": c.status.value, "bill_id": str(c.bill_id) if c.bill_id else None,
        "invoice_number": c.invoice_number, "cancel_reason": c.cancel_reason,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.post("/flat-charges", status_code=201)
def create_flat_charge(data: FlatChargeCreate, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(manager_above)):
    """A fine or additional charge on one flat; goes on its next bill."""
    assert_society_access(user, data.society_id)
    return _flat_charge_out(FlatChargeService(db).create(data.model_dump(), user, request))


@router.get("/flat-charges/society/{society_id}")
def list_flat_charges(society_id: UUID, status: Optional[FlatChargeStatus] = None, flat_id: Optional[UUID] = None,
                      skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                      db: Session = Depends(get_db), user: User = Depends(manager_above)):
    assert_society_access(user, society_id)
    return [_flat_charge_out(c) for c in FlatChargeService(db).list_for_society(society_id, status, flat_id, skip, limit)]


@router.get("/flat-charges/flat/{flat_id}")
def flat_flat_charges(flat_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A flat's fines and additional charges (not the cancelled ones): managers
    see any flat's, a member only their own."""
    flat = db.get(Flat, flat_id)
    if flat is None or (user.society_id is not None and flat.wing.society_id != user.society_id):
        raise HTTPException(404, "Flat not found")
    _ensure_can_view_flat(db, user, flat_id)
    return [_flat_charge_out(c) for c in FlatChargeService(db).list_for_flat(flat_id)]


@router.post("/flat-charges/{charge_id}/cancel")
def cancel_flat_charge(charge_id: UUID, data: FlatChargeCancel, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(manager_above)):
    return _flat_charge_out(FlatChargeService(db).cancel(charge_id, data.reason, user, request))
