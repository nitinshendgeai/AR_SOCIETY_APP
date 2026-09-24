from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.vendor.models.vendor import (
    Vendor, VendorService, AMCContract, AMCServiceSchedule,
    ServiceRequest, ServiceVisitLog, VendorInvoice, VendorPaymentMode,
    ContractStatus, ServiceRequestStatus, ScheduleStatus,
    ServiceFrequency, SR_TRANSITIONS,
)
from app.modules.vendor.repositories.vendor_repo import (
    VendorRepo, AMCContractRepo, ServiceRequestRepo,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class VendorService_:  # trailing underscore avoids clash with model name

    def __init__(self, db: Session):
        self.db            = db
        self.vendor_repo   = VendorRepo(db)
        self.contract_repo = AMCContractRepo(db)
        self.sr_repo       = ServiceRequestRepo(db)

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="vendor",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Vendor CRUD ───────────────────────────────────────────────────────────

    def create_vendor(self, data: dict, user: User, request=None) -> Vendor:
        code   = self.vendor_repo.next_vendor_code(data["society_id"])
        vendor = Vendor(**data, vendor_code=code, registered_by=user.id)
        self.vendor_repo.create(vendor)
        self._audit(AuditAction.CREATE, vendor, "Vendor", user, request,
                    new_values={"code": code, "name": data["company_name"]})
        self.db.refresh(vendor)
        return vendor

    def update_vendor(self, vendor_id: UUID, data: dict, user: User) -> Vendor:
        v = self.vendor_repo.get(vendor_id)
        if not v: raise HTTPException(404, "Vendor not found")
        return self.vendor_repo.update(v, data)

    def blacklist_vendor(self, vendor_id: UUID, reason: str, user: User) -> Vendor:
        v = self.vendor_repo.get(vendor_id)
        if not v: raise HTTPException(404, "Vendor not found")
        from app.modules.vendor.models.vendor import VendorStatus
        v.status = VendorStatus.BLACKLISTED
        v.blacklist_reason = reason
        self.db.commit()
        self.db.refresh(v)
        return v

    def get_vendor(self, vendor_id: UUID) -> Vendor:
        v = self.vendor_repo.get(vendor_id)
        if not v: raise HTTPException(404, "Vendor not found")
        return v

    def list_vendors(self, society_id: UUID, skip=0, limit=50) -> List[Vendor]:
        return self.vendor_repo.get_by_society(society_id, skip, limit)

    def list_by_category(self, society_id: UUID, category) -> List[Vendor]:
        return self.vendor_repo.get_by_category(society_id, category)

    def add_service(self, vendor_id: UUID, data: dict) -> VendorService:
        svc = VendorService(vendor_id=vendor_id, **data)
        self.db.add(svc)
        self.db.commit()
        self.db.refresh(svc)
        return svc

    # ── AMC Contracts ─────────────────────────────────────────────────────────

    def create_contract(self, data: dict, user: User, request=None) -> AMCContract:
        # Check for overlapping active contract with same vendor+asset
        if data.get("asset_id"):
            overlap = self.db.query(AMCContract).filter(
                AMCContract.society_id == data["society_id"],
                AMCContract.vendor_id  == data["vendor_id"],
                AMCContract.asset_id   == data.get("asset_id"),
                AMCContract.status     == ContractStatus.ACTIVE,
                AMCContract.start_date <= data["end_date"],
                AMCContract.end_date   >= data["start_date"],
                AMCContract.is_active  == True,
            ).first()
            if overlap:
                raise HTTPException(409, "An active AMC already covers this vendor+asset for the given dates")

        number   = self.contract_repo.next_contract_number(data["society_id"])
        contract = AMCContract(**data, contract_number=number, created_by=user.id)
        self.db.add(contract)
        self.db.flush()
        self._audit(AuditAction.CREATE, contract, "AMCContract", user, request,
                    new_values={"number": number, "vendor": str(data["vendor_id"])})
        self.db.commit()
        self.db.refresh(contract)
        return contract

    def activate_contract(self, contract_id: UUID, user: User) -> AMCContract:
        c = self.contract_repo.get(contract_id)
        if not c: raise HTTPException(404, "Contract not found")
        if c.status != ContractStatus.DRAFT:
            raise HTTPException(409, f"Contract is already {c.status.value}")
        c.status = ContractStatus.ACTIVE
        self.db.commit()
        self.db.refresh(c)
        self._audit(AuditAction.UPDATE, c, "AMCContract", user,
                    new_values={"status": "active"})
        return c

    def generate_schedule(self, contract_id: UUID, user: User) -> List[AMCServiceSchedule]:
        """Auto-generate service schedule dates for the contract period."""
        c = self.contract_repo.get(contract_id)
        if not c: raise HTTPException(404, "Contract not found")
        if c.status not in (ContractStatus.ACTIVE, ContractStatus.DRAFT):
            raise HTTPException(409, "Can only generate schedules for active/draft contracts")

        # Delete existing scheduled entries
        self.db.query(AMCServiceSchedule).filter(
            AMCServiceSchedule.contract_id == contract_id,
            AMCServiceSchedule.status == ScheduleStatus.SCHEDULED,
        ).delete()

        # Calculate intervals
        freq_days = {
            ServiceFrequency.WEEKLY: 7, ServiceFrequency.FORTNIGHTLY: 14,
            ServiceFrequency.MONTHLY: 30, ServiceFrequency.QUARTERLY: 91,
            ServiceFrequency.HALF_YEARLY: 182, ServiceFrequency.YEARLY: 365,
            ServiceFrequency.ON_CALL: None,
        }
        interval = freq_days.get(c.service_frequency)
        if not interval:
            raise HTTPException(422, "ON_CALL contracts don't have auto-schedules")

        schedules = []
        current = c.start_date
        while current <= c.end_date:
            sched = AMCServiceSchedule(
                contract_id=contract_id, society_id=c.society_id,
                scheduled_date=current,
            )
            self.db.add(sched)
            schedules.append(sched)
            current = current + timedelta(days=interval)

        self.db.commit()
        return schedules

    def list_contracts(self, society_id: UUID, skip=0, limit=50) -> List[AMCContract]:
        return self.contract_repo.get_by_society(society_id, skip, limit)

    def get_expiring_contracts(self, society_id: UUID, days: int = 60) -> List[AMCContract]:
        return self.contract_repo.get_expiring(society_id, days)

    # ── Service Requests ──────────────────────────────────────────────────────

    def create_service_request(self, data: dict, user: User, request=None) -> ServiceRequest:
        number = self.sr_repo.next_request_number(data["society_id"])
        sr = ServiceRequest(**data, request_number=number, raised_by=user.id)
        self.db.add(sr)
        self.db.flush()
        self._audit(AuditAction.CREATE, sr, "ServiceRequest", user, request,
                    new_values={"number": number, "title": data["title"]})
        self.db.commit()
        self.db.refresh(sr)
        return sr

    def assign_vendor(self, sr_id: UUID, vendor_id: UUID, scheduled_date: Optional[date],
                       user: User, request=None) -> ServiceRequest:
        sr = self.sr_repo.get(sr_id)
        if not sr: raise HTTPException(404, "Service request not found")
        allowed = SR_TRANSITIONS.get(sr.status, set())
        if ServiceRequestStatus.ASSIGNED not in allowed:
            raise HTTPException(409, f"Cannot assign vendor from status '{sr.status.value}'")

        sr.vendor_id      = vendor_id
        sr.assigned_by    = user.id
        sr.status         = ServiceRequestStatus.ASSIGNED
        if scheduled_date:
            sr.scheduled_date = scheduled_date
            sr.status = ServiceRequestStatus.SCHEDULED

        # Notify the raising user
        if sr.raised_by:
            NotificationService.send(
                db=self.db, user_id=sr.raised_by,
                title="Vendor Assigned to Your Request",
                body=f"Service request #{sr.request_number} has been assigned to a vendor.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="vendor", entity_id=str(sr.id),
            )
        self._audit(AuditAction.UPDATE, sr, "ServiceRequest", user, request,
                    new_values={"vendor": str(vendor_id), "status": sr.status.value})
        self.db.commit()
        self.db.refresh(sr)
        return sr

    def update_sr_status(self, sr_id: UUID, new_status: ServiceRequestStatus,
                          notes: str, user: User, request=None,
                          actual_cost: Optional[Decimal] = None) -> ServiceRequest:
        sr = self.sr_repo.get(sr_id)
        if not sr: raise HTTPException(404, "Service request not found")
        allowed = SR_TRANSITIONS.get(sr.status, set())
        if new_status not in allowed:
            raise HTTPException(409,
                f"Cannot transition from '{sr.status.value}' to '{new_status.value}'")

        prev = sr.status
        sr.status = new_status
        if new_status == ServiceRequestStatus.COMPLETED:
            sr.completed_date   = datetime.utcnow()
            sr.completion_notes = notes
            if actual_cost: sr.actual_cost = actual_cost
        elif new_status == ServiceRequestStatus.VERIFIED:
            sr.verified_date = datetime.utcnow()
            sr.verified_by   = user.id
        elif new_status == ServiceRequestStatus.CLOSED:
            # Update vendor stats
            if sr.vendor_id:
                vendor = self.vendor_repo.get(sr.vendor_id)
                if vendor: vendor.total_services += 1

        self._audit(AuditAction.UPDATE, sr, "ServiceRequest", user, request,
                    old_values={"status": prev.value}, new_values={"status": new_status.value})
        self.db.commit()
        self.db.refresh(sr)
        return sr

    def log_visit(self, data: dict, user: User) -> ServiceVisitLog:
        log = ServiceVisitLog(**data, logged_by=user.id)
        self.db.add(log)
        # Mark AMC schedule if contract_id provided
        if data.get("contract_id") and data.get("visit_date"):
            sched = self.db.query(AMCServiceSchedule).filter(
                AMCServiceSchedule.contract_id    == data["contract_id"],
                AMCServiceSchedule.scheduled_date == data["visit_date"],
                AMCServiceSchedule.status         == ScheduleStatus.SCHEDULED,
            ).first()
            if sched:
                sched.status = ScheduleStatus.COMPLETED
                sched.completed_date = data["visit_date"]
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_sr(self, sr_id: UUID) -> ServiceRequest:
        sr = self.sr_repo.get(sr_id)
        if not sr: raise HTTPException(404, "Service request not found")
        return sr

    def list_service_requests(self, society_id: UUID, skip=0, limit=50) -> List[ServiceRequest]:
        return self.sr_repo.get_by_society(society_id, skip, limit)

    def get_open_requests(self, society_id: UUID) -> List[ServiceRequest]:
        return self.sr_repo.get_open(society_id)

    # ── Vendor Invoices ───────────────────────────────────────────────────────

    def create_vendor_invoice(self, data: dict, user: User) -> VendorInvoice:
        inv = VendorInvoice(**data)
        self.db.add(inv)
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def record_vendor_payment(self, inv_id: UUID, amount: Decimal, paid_date: date,
                               payment_mode: VendorPaymentMode, transaction_ref: Optional[str],
                               bank_name: Optional[str], user: User) -> VendorInvoice:
        """Records a payment against an invoice — possibly partial. Unlike
        the old mark_invoice_paid (which always force-set paid_amount to
        the full total), this accumulates across calls and only flips
        is_paid once paid_amount reaches total_amount, mirroring how
        MaintenanceBill/PaymentReceipt track partial resident payments."""
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv: raise HTTPException(404, "Invoice not found")
        if inv.is_paid:
            raise HTTPException(409, "Invoice is already fully paid")
        if amount <= 0:
            raise HTTPException(422, "Payment amount must be positive")
        outstanding = inv.total_amount - inv.paid_amount
        if amount > outstanding:
            raise HTTPException(422, f"Payment of {amount} exceeds outstanding balance of {outstanding}")

        inv.paid_amount = inv.paid_amount + amount
        inv.payment_mode = payment_mode
        inv.payment_ref  = transaction_ref
        inv.bank_name    = bank_name
        inv.paid_date    = paid_date
        inv.approved_by  = user.id
        if inv.paid_amount >= inv.total_amount:
            inv.is_paid = True

        self._audit(AuditAction.UPDATE, inv, "VendorInvoice", user,
                    new_values={"amount": str(amount), "paid_amount": str(inv.paid_amount),
                                "is_paid": inv.is_paid, "invoice": inv.invoice_number})
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def get_vendor_invoices(self, vendor_id: UUID) -> List[VendorInvoice]:
        return self.db.query(VendorInvoice).filter(
            VendorInvoice.vendor_id == vendor_id
        ).order_by(VendorInvoice.invoice_date.desc()).all()

    def list_invoices_by_society(self, society_id: UUID, is_paid: Optional[bool] = None,
                                  skip=0, limit=50) -> List[VendorInvoice]:
        q = self.db.query(VendorInvoice).filter(VendorInvoice.society_id == society_id)
        if is_paid is not None:
            q = q.filter(VendorInvoice.is_paid == is_paid)
        return q.order_by(VendorInvoice.invoice_date.desc()).offset(skip).limit(limit).all()

    def get_vendor_invoice(self, inv_id: UUID) -> VendorInvoice:
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv: raise HTTPException(404, "Invoice not found")
        return inv
