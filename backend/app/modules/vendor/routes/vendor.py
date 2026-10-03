from typing import List, Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas import validators as val
from app.core.tenant_scope import assert_society_access

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_supervisor_above, require_any_member,
    require_manager_above,
)
from app.models.user import User
from app.modules.vendor.models.vendor import (
    VendorCategory, VendorStatus, ServiceFrequency, VendorPaymentMode,
    ServiceRequestStatus, ServiceRequestPriority,
)
from app.modules.vendor.services.vendor_service import VendorService_
from app.schemas.common import OrmBase

router = APIRouter(prefix="/vendors", tags=["Vendor & AMC Management"])

admin_committee = require_admin_committee
staff_above     = require_supervisor_above
any_member      = require_any_member
manager_above   = require_manager_above


def _vendor_out(v) -> dict:
    return {
        "id": str(v.id),
        "society_id": str(v.society_id),
        "vendor_code": v.vendor_code,
        "company_name": v.company_name,
        "contact_person": v.contact_person,
        "mobile": v.mobile,
        "email": v.email,
        "category": v.category.value,
        "status": v.status.value,
        "gst_number": v.gst_number,
        "bank_account": v.bank_account,
        "bank_name": v.bank_name,
        "bank_ifsc": v.bank_ifsc,
    }

def _invoice_out(i) -> dict:
    return {
        "id": str(i.id),
        "society_id": str(i.society_id),
        "vendor_id": str(i.vendor_id),
        "vendor_name": i.vendor.company_name if i.vendor else None,
        "invoice_number": i.invoice_number,
        "invoice_date": i.invoice_date.isoformat(),
        "due_date": i.due_date.isoformat() if i.due_date else None,
        "amount": str(i.amount),
        "gst_amount": str(i.gst_amount),
        "total_amount": str(i.total_amount),
        "paid_amount": str(i.paid_amount),
        "outstanding": str(i.total_amount - i.paid_amount),
        "is_paid": i.is_paid,
        "paid_date": i.paid_date.isoformat() if i.paid_date else None,
        "payment_mode": i.payment_mode.value if i.payment_mode else None,
        "payment_ref": i.payment_ref,
        "bank_name": i.bank_name,
        "description": i.description,
        "expense_account_id": str(i.expense_account_id) if i.expense_account_id else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ── Inline schemas ────────────────────────────────────────────────────────────
_GST = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PAN = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def _upper_match(pattern, message):
    def check(v):
        v = val.text(v)
        if v is None:
            return None
        v = v.replace(" ", "").upper()
        if not pattern.match(v):
            raise ValueError(message)
        return v
    return check


def _account(v):
    v = val.text(v)
    if v is None:
        return None
    v = v.replace(" ", "").replace("-", "")
    if not re.fullmatch(r"[0-9A-Za-z]{5,34}", v):
        raise ValueError("Enter a valid bank account number")
    return v


def _link(v):
    v = val.text(v)
    if v is None:
        return None
    if len(v) > 500 or not re.match(r"^https?://\S+$", v):
        raise ValueError("Enter a valid link starting with http:// or https://")
    return v


class VendorCreate(OrmBase):
    society_id: UUID; company_name: str = Field(max_length=255); mobile: str
    category: VendorCategory
    contact_person: Optional[str] = None; email: Optional[str] = None
    address: Optional[str] = None; city: Optional[str] = None
    gst_number: Optional[str] = None; pan_number: Optional[str] = None
    bank_account: Optional[str] = None; bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None; notes: Optional[str] = None

    _company = field_validator("company_name", mode="before")(val.line_max(255, required=True))
    _mobile = field_validator("mobile", mode="before")(val.mobile_any)
    _person = field_validator("contact_person", mode="before")(val.line_max(255))
    _email = field_validator("email", mode="before")(val.email)
    _address = field_validator("address", mode="before")(val.note_max(1000))
    _city = field_validator("city", mode="before")(val.line_max(100))
    _gst = field_validator("gst_number", mode="before")(_upper_match(_GST, "Enter a valid 15-character GSTIN"))
    _pan = field_validator("pan_number", mode="before")(_upper_match(_PAN, "Enter a valid PAN, e.g. ABCDE1234F"))
    _account_no = field_validator("bank_account", mode="before")(_account)
    _bank = field_validator("bank_name", mode="before")(val.line_max(100))
    _ifsc = field_validator("bank_ifsc", mode="before")(_upper_match(_IFSC, "Enter a valid IFSC, e.g. HDFC0001234"))
    _notes = field_validator("notes", mode="before")(val.note_max(2000))

class VendorServiceCreate(OrmBase):
    service_name: str = Field(max_length=150); category: VendorCategory
    rate_per_visit: Optional[Decimal] = Field(default=None, ge=0, lt=100_000_000, decimal_places=2)
    rate_per_hour: Optional[Decimal] = Field(default=None, ge=0, lt=1_000_000, decimal_places=2)
    description: Optional[str] = None

    _name = field_validator("service_name", mode="before")(val.line_max(150, required=True))
    _description = field_validator("description", mode="before")(val.note_max(1000))

class BlacklistRequest(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(1000, required=True))

class ContractCreate(OrmBase):
    society_id: UUID; vendor_id: UUID
    contract_name: str = Field(max_length=255); category: VendorCategory
    start_date: date; end_date: date
    service_frequency: ServiceFrequency
    asset_id: Optional[UUID] = None
    sla_response_hours: Optional[int] = Field(default=None, ge=0, le=8760)
    scope_of_work: Optional[str] = None
    annual_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    auto_renew: bool = False; renewal_notice_days: int = Field(default=30, ge=0, le=365)
    document_url: Optional[str] = None

    _name = field_validator("contract_name", mode="before")(val.line_max(255, required=True))
    _scope = field_validator("scope_of_work", mode="before")(val.note_max(5000))
    _url = field_validator("document_url", mode="before")(_link)
    _dates = field_validator("start_date", "end_date")(val.sane_date)

    @model_validator(mode="after")
    def _period(self):
        if self.end_date <= self.start_date:
            raise ValueError("The contract must end after it starts")
        return self

class SRCreate(OrmBase):
    society_id: UUID; title: str = Field(max_length=255); category: VendorCategory
    description: Optional[str] = None; location: Optional[str] = Field(default=None, max_length=255)
    priority: ServiceRequestPriority = ServiceRequestPriority.MEDIUM
    preferred_date: Optional[date] = None
    vendor_id: Optional[UUID] = None
    complaint_id: Optional[UUID] = None; asset_id: Optional[UUID] = None

    _title = field_validator("title", mode="before")(val.line_max(255, required=True))
    _location = field_validator("location", mode="before")(val.line_max(255))
    _description = field_validator("description", mode="before")(val.note_max(3000))
    _date = field_validator("preferred_date")(val.sane_date)

class AssignVendorRequest(OrmBase):
    vendor_id: UUID; scheduled_date: Optional[date] = None

    _date = field_validator("scheduled_date")(val.sane_date)

class SRStatusUpdate(OrmBase):
    status: ServiceRequestStatus
    notes: Optional[str] = None
    actual_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    _notes = field_validator("notes", mode="before")(val.note_max(1000))

class VisitLogCreate(OrmBase):
    request_id: Optional[UUID] = None; contract_id: Optional[UUID] = None
    society_id: UUID; vendor_id: Optional[UUID] = None
    visit_date: date; work_done: Optional[str] = None
    materials_used: Optional[str] = None
    check_in_time: Optional[datetime] = None; check_out_time: Optional[datetime] = None
    next_visit_date: Optional[date] = None
    photo_url: Optional[str] = None; is_satisfactory: bool = True

    _text = field_validator("work_done", "materials_used", mode="before")(val.note_max(3000))
    _photo = field_validator("photo_url", mode="before")(_link)
    _dates = field_validator("visit_date", "next_visit_date")(val.sane_date)

    @model_validator(mode="after")
    def _times(self):
        if self.check_in_time and self.check_out_time and self.check_out_time <= self.check_in_time:
            raise ValueError("Check-out must be after check-in")
        if self.next_visit_date and self.next_visit_date < self.visit_date:
            raise ValueError("The next visit can't be before this one")
        return self

class VendorInvoiceCreate(OrmBase):
    society_id: UUID; vendor_id: UUID
    contract_id: Optional[UUID] = None; request_id: Optional[UUID] = None
    invoice_number: str = Field(max_length=50); invoice_date: date; due_date: Optional[date] = None
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    gst_amount: Decimal = Field(default=Decimal(0), ge=0, max_digits=10, decimal_places=2)
    total_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: Optional[str] = None; doc_url: Optional[str] = None
    expense_account_id: Optional[UUID] = None  # accounts ledger; default by vendor category

    _number = field_validator("invoice_number", mode="before")(val.line_max(50, required=True))
    _description = field_validator("description", mode="before")(val.note_max(2000))
    _doc = field_validator("doc_url", mode="before")(_link)
    _dates = field_validator("invoice_date", "due_date")(val.sane_date)

    @model_validator(mode="after")
    def _totals(self):
        if self.total_amount != self.amount + self.gst_amount:
            raise ValueError("The total must equal the amount plus GST")
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("The due date can't be before the invoice date")
        return self

class RecordPaymentRequest(OrmBase):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    paid_date: date; payment_mode: VendorPaymentMode
    payment_ref: Optional[str] = None; bank_name: Optional[str] = None

    _ref = field_validator("payment_ref", mode="before")(val.line_max(100))
    _bank = field_validator("bank_name", mode="before")(val.line_max(100))

    @field_validator("paid_date")
    @classmethod
    def _not_future(cls, v):
        if v > date.today():
            raise ValueError("The payment date can't be in the future")
        return val.sane_date(v)


# ── Vendors ───────────────────────────────────────────────────────────────────
@router.post("/", status_code=201, dependencies=[Depends(admin_committee)])
def create_vendor(data: VendorCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return VendorService_(db).create_vendor(data.model_dump(), user, request)

@router.get("/{vendor_id}")
def get_vendor(vendor_id: UUID, db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    return _vendor_out(VendorService_(db).get_vendor(vendor_id, user))

@router.get("/society/{society_id}")
def list_vendors(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                 db: Session = Depends(get_db), user: User = Depends(manager_above)):
    assert_society_access(user, society_id)
    return [_vendor_out(v) for v in VendorService_(db).list_vendors(society_id, skip, limit)]

@router.get("/society/{society_id}/category/{category}")
def vendors_by_category(society_id: UUID, category: VendorCategory, db: Session = Depends(get_db),
                        user: User = Depends(admin_committee)):
    assert_society_access(user, society_id)
    return VendorService_(db).list_by_category(society_id, category)

@router.post("/{vendor_id}/blacklist", dependencies=[Depends(admin_committee)])
def blacklist_vendor(vendor_id: UUID, data: BlacklistRequest, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return VendorService_(db).blacklist_vendor(vendor_id, data.reason, user)

@router.post("/{vendor_id}/services", status_code=201)
def add_service(vendor_id: UUID, data: VendorServiceCreate, db: Session = Depends(get_db),
                user: User = Depends(admin_committee)):
    return VendorService_(db).add_service(vendor_id, data.model_dump(), user)


# ── AMC Contracts ─────────────────────────────────────────────────────────────
@router.post("/contracts", status_code=201, dependencies=[Depends(admin_committee)])
def create_contract(data: ContractCreate, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return VendorService_(db).create_contract(data.model_dump(), user, request)

@router.post("/contracts/{contract_id}/activate", dependencies=[Depends(admin_committee)])
def activate_contract(contract_id: UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    return VendorService_(db).activate_contract(contract_id, user)

@router.post("/contracts/{contract_id}/generate-schedule", dependencies=[Depends(admin_committee)])
def generate_schedule(contract_id: UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    schedules = VendorService_(db).generate_schedule(contract_id, user)
    return {"schedules_generated": len(schedules), "contract_id": str(contract_id)}

@router.get("/contracts/society/{society_id}")
def list_contracts(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                   db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    assert_society_access(user, society_id)
    return VendorService_(db).list_contracts(society_id, skip, limit)

@router.get("/contracts/expiring/{society_id}")
def expiring_contracts(society_id: UUID,
                        days: int = Query(60, ge=1, le=3650, description="Look-ahead days"),
                        db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    assert_society_access(user, society_id)
    return VendorService_(db).get_expiring_contracts(society_id, days)


# ── Service Requests ──────────────────────────────────────────────────────────
@router.post("/service-requests", status_code=201)
def create_sr(data: SRCreate, request: Request, db: Session = Depends(get_db),
              user: User = Depends(staff_above)):
    return VendorService_(db).create_service_request(data.model_dump(), user, request)

@router.get("/service-requests/{sr_id}")
def get_sr(sr_id: UUID, db: Session = Depends(get_db), user: User = Depends(staff_above)):
    return VendorService_(db).get_sr(sr_id, user)

@router.post("/service-requests/{sr_id}/assign-vendor")
def assign_vendor(sr_id: UUID, data: AssignVendorRequest, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    return VendorService_(db).assign_vendor(sr_id, data.vendor_id, data.scheduled_date, user, request)

@router.post("/service-requests/{sr_id}/status")
def update_sr_status(sr_id: UUID, data: SRStatusUpdate, request: Request,
                     db: Session = Depends(get_db), user: User = Depends(staff_above)):
    return VendorService_(db).update_sr_status(sr_id, data.status, data.notes or "", user, request, data.actual_cost)

@router.get("/service-requests/society/{society_id}")
def list_srs(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
             db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    assert_society_access(user, society_id)
    return VendorService_(db).list_service_requests(society_id, skip, limit)

@router.get("/service-requests/open/{society_id}")
def open_srs(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    assert_society_access(user, society_id)
    return VendorService_(db).get_open_requests(society_id)


# ── Visit Logs ────────────────────────────────────────────────────────────────
@router.post("/visits", status_code=201, dependencies=[Depends(staff_above)])
def log_visit(data: VisitLogCreate, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    return VendorService_(db).log_visit(data.model_dump(), user)


# ── Vendor Invoices (bills owed to vendors) ────────────────────────────────────
@router.post("/invoices", status_code=201, dependencies=[Depends(manager_above)])
def create_invoice(data: VendorInvoiceCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return _invoice_out(VendorService_(db).create_vendor_invoice(data.model_dump(), user))

@router.get("/invoices/{inv_id}")
def get_invoice(inv_id: UUID, db: Session = Depends(get_db), user: User = Depends(manager_above)):
    return _invoice_out(VendorService_(db).get_vendor_invoice(inv_id, user))

@router.post("/invoices/{inv_id}/payments", dependencies=[Depends(manager_above)])
def record_payment(inv_id: UUID, data: RecordPaymentRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    inv = VendorService_(db).record_vendor_payment(
        inv_id, data.amount, data.paid_date, data.payment_mode,
        data.payment_ref, data.bank_name, user)
    return _invoice_out(inv)

@router.get("/invoices/vendor/{vendor_id}")
def vendor_invoices(vendor_id: UUID, db: Session = Depends(get_db), user: User = Depends(manager_above)):
    return [_invoice_out(i) for i in VendorService_(db).get_vendor_invoices(vendor_id, user)]

@router.get("/invoices/society/{society_id}")
def list_society_invoices(
    society_id: UUID, is_paid: Optional[bool] = None,
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db),
    user: User = Depends(manager_above),
):
    assert_society_access(user, society_id)
    rows = VendorService_(db).list_invoices_by_society(society_id, is_paid=is_paid, skip=skip, limit=limit)
    return [_invoice_out(i) for i in rows]
