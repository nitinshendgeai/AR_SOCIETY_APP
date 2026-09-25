from typing import List, Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

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
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ── Inline schemas ────────────────────────────────────────────────────────────
class VendorCreate(OrmBase):
    society_id: UUID; company_name: str; mobile: str
    category: VendorCategory
    contact_person: Optional[str] = None; email: Optional[str] = None
    address: Optional[str] = None; city: Optional[str] = None
    gst_number: Optional[str] = None; pan_number: Optional[str] = None
    bank_account: Optional[str] = None; bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None; notes: Optional[str] = None

class VendorServiceCreate(OrmBase):
    service_name: str; category: VendorCategory
    rate_per_visit: Optional[Decimal] = None; rate_per_hour: Optional[Decimal] = None
    description: Optional[str] = None

class BlacklistRequest(OrmBase):
    reason: str

class ContractCreate(OrmBase):
    society_id: UUID; vendor_id: UUID
    contract_name: str; category: VendorCategory
    start_date: date; end_date: date
    service_frequency: ServiceFrequency
    asset_id: Optional[UUID] = None
    sla_response_hours: Optional[int] = None
    scope_of_work: Optional[str] = None
    annual_value: Optional[Decimal] = None
    auto_renew: bool = False; renewal_notice_days: int = 30
    document_url: Optional[str] = None

class SRCreate(OrmBase):
    society_id: UUID; title: str; category: VendorCategory
    description: Optional[str] = None; location: Optional[str] = None
    priority: ServiceRequestPriority = ServiceRequestPriority.MEDIUM
    preferred_date: Optional[date] = None
    vendor_id: Optional[UUID] = None
    complaint_id: Optional[UUID] = None; asset_id: Optional[UUID] = None

class AssignVendorRequest(OrmBase):
    vendor_id: UUID; scheduled_date: Optional[date] = None

class SRStatusUpdate(OrmBase):
    status: ServiceRequestStatus
    notes: Optional[str] = None
    actual_cost: Optional[Decimal] = None

class VisitLogCreate(OrmBase):
    request_id: Optional[UUID] = None; contract_id: Optional[UUID] = None
    society_id: UUID; vendor_id: Optional[UUID] = None
    visit_date: date; work_done: Optional[str] = None
    materials_used: Optional[str] = None
    check_in_time: Optional[str] = None; check_out_time: Optional[str] = None
    next_visit_date: Optional[date] = None
    photo_url: Optional[str] = None; is_satisfactory: bool = True

class VendorInvoiceCreate(OrmBase):
    society_id: UUID; vendor_id: UUID
    contract_id: Optional[UUID] = None; request_id: Optional[UUID] = None
    invoice_number: str; invoice_date: date; due_date: Optional[date] = None
    amount: Decimal; gst_amount: Decimal = Decimal(0); total_amount: Decimal
    description: Optional[str] = None; doc_url: Optional[str] = None

class RecordPaymentRequest(OrmBase):
    amount: Decimal; paid_date: date; payment_mode: VendorPaymentMode
    payment_ref: Optional[str] = None; bank_name: Optional[str] = None


# ── Vendors ───────────────────────────────────────────────────────────────────
@router.post("/", status_code=201, dependencies=[Depends(admin_committee)])
def create_vendor(data: VendorCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return VendorService_(db).create_vendor(data.model_dump(), user, request)

@router.get("/{vendor_id}", dependencies=[Depends(admin_committee)])
def get_vendor(vendor_id: UUID, db: Session = Depends(get_db)):
    return _vendor_out(VendorService_(db).get_vendor(vendor_id))

@router.get("/society/{society_id}", dependencies=[Depends(manager_above)])
def list_vendors(society_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return [_vendor_out(v) for v in VendorService_(db).list_vendors(society_id, skip, limit)]

@router.get("/society/{society_id}/category/{category}", dependencies=[Depends(admin_committee)])
def vendors_by_category(society_id: UUID, category: VendorCategory, db: Session = Depends(get_db)):
    return VendorService_(db).list_by_category(society_id, category)

@router.post("/{vendor_id}/blacklist", dependencies=[Depends(admin_committee)])
def blacklist_vendor(vendor_id: UUID, data: BlacklistRequest, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return VendorService_(db).blacklist_vendor(vendor_id, data.reason, user)

@router.post("/{vendor_id}/services", status_code=201, dependencies=[Depends(admin_committee)])
def add_service(vendor_id: UUID, data: VendorServiceCreate, db: Session = Depends(get_db)):
    return VendorService_(db).add_service(vendor_id, data.model_dump())


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

@router.get("/contracts/society/{society_id}", dependencies=[Depends(admin_committee)])
def list_contracts(society_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return VendorService_(db).list_contracts(society_id, skip, limit)

@router.get("/contracts/expiring/{society_id}", dependencies=[Depends(admin_committee)])
def expiring_contracts(society_id: UUID,
                        days: int = Query(60, description="Look-ahead days"),
                        db: Session = Depends(get_db)):
    return VendorService_(db).get_expiring_contracts(society_id, days)


# ── Service Requests ──────────────────────────────────────────────────────────
@router.post("/service-requests", status_code=201)
def create_sr(data: SRCreate, request: Request, db: Session = Depends(get_db),
              user: User = Depends(staff_above)):
    return VendorService_(db).create_service_request(data.model_dump(), user, request)

@router.get("/service-requests/{sr_id}", dependencies=[Depends(staff_above)])
def get_sr(sr_id: UUID, db: Session = Depends(get_db)):
    return VendorService_(db).get_sr(sr_id)

@router.post("/service-requests/{sr_id}/assign-vendor")
def assign_vendor(sr_id: UUID, data: AssignVendorRequest, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(admin_committee)):
    return VendorService_(db).assign_vendor(sr_id, data.vendor_id, data.scheduled_date, user, request)

@router.post("/service-requests/{sr_id}/status")
def update_sr_status(sr_id: UUID, data: SRStatusUpdate, request: Request,
                     db: Session = Depends(get_db), user: User = Depends(staff_above)):
    return VendorService_(db).update_sr_status(sr_id, data.status, data.notes or "", user, request, data.actual_cost)

@router.get("/service-requests/society/{society_id}", dependencies=[Depends(admin_committee)])
def list_srs(society_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return VendorService_(db).list_service_requests(society_id, skip, limit)

@router.get("/service-requests/open/{society_id}", dependencies=[Depends(admin_committee)])
def open_srs(society_id: UUID, db: Session = Depends(get_db)):
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

@router.get("/invoices/{inv_id}", dependencies=[Depends(manager_above)])
def get_invoice(inv_id: UUID, db: Session = Depends(get_db)):
    return _invoice_out(VendorService_(db).get_vendor_invoice(inv_id))

@router.post("/invoices/{inv_id}/payments", dependencies=[Depends(manager_above)])
def record_payment(inv_id: UUID, data: RecordPaymentRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    inv = VendorService_(db).record_vendor_payment(
        inv_id, data.amount, data.paid_date, data.payment_mode,
        data.payment_ref, data.bank_name, user)
    return _invoice_out(inv)

@router.get("/invoices/vendor/{vendor_id}", dependencies=[Depends(manager_above)])
def vendor_invoices(vendor_id: UUID, db: Session = Depends(get_db)):
    return [_invoice_out(i) for i in VendorService_(db).get_vendor_invoices(vendor_id)]

@router.get("/invoices/society/{society_id}", dependencies=[Depends(manager_above)])
def list_society_invoices(
    society_id: UUID, is_paid: Optional[bool] = None,
    skip: int = 0, limit: int = 50, db: Session = Depends(get_db),
):
    rows = VendorService_(db).list_invoices_by_society(society_id, is_paid=is_paid, skip=skip, limit=limit)
    return [_invoice_out(i) for i in rows]
