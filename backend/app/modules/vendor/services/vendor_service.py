from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.vendor.models.vendor import (
    Vendor, VendorService, AMCContract, AMCServiceSchedule,
    ServiceRequest, ServiceVisitLog, VendorInvoice, VendorPaymentTransaction, VendorPaymentMode,
    ContractStatus, ServiceRequestStatus, ScheduleStatus,
    ServiceFrequency, SR_TRANSITIONS,
)
from app.modules.vendor.repositories.vendor_repo import (
    VendorRepo, AMCContractRepo, ServiceRequestRepo,
)
from app.core.tenant_scope import resolve_create_society_id
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

    @staticmethod
    def _scoped(user: Optional[User], obj, what: str):
        """A record of the caller's own society; another society's reads as
        not found. Platform admins (no society) see everything."""
        if user is not None and user.society_id is not None and obj.society_id != user.society_id:
            raise HTTPException(404, f"{what} not found")
        return obj

    def _vendor_in(self, vendor_id: Optional[UUID], society_id: UUID, active_only: bool = False) -> Optional[Vendor]:
        if vendor_id is None:
            return None
        v = self.vendor_repo.get(vendor_id)
        if v is None or v.society_id != society_id:
            raise HTTPException(422, "Vendor not found in this society")
        if active_only:
            from app.modules.vendor.models.vendor import VendorStatus
            if v.status != VendorStatus.ACTIVE:
                raise HTTPException(422, f"{v.company_name} is {v.status.value} and can't be given work")
        return v

    def _contract_in(self, contract_id: Optional[UUID], society_id: UUID) -> None:
        if contract_id is None:
            return
        c = self.contract_repo.get(contract_id)
        if c is None or c.society_id != society_id:
            raise HTTPException(422, "Contract not found in this society")

    def _request_in(self, request_id: Optional[UUID], society_id: UUID) -> None:
        if request_id is None:
            return
        r = self.sr_repo.get(request_id)
        if r is None or r.society_id != society_id:
            raise HTTPException(422, "Service request not found in this society")

    def _post(self, hook: str, *args) -> None:
        """Post to the society's books (see accounts/services/postings.py);
        never fails the vendor action."""
        from app.modules.accounts.services.postings import AccountPostings
        AccountPostings(self.db).run(hook, *args)

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="vendor",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Vendor CRUD ───────────────────────────────────────────────────────────

    def create_vendor(self, data: dict, user: User, request=None) -> Vendor:
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        same_name = self.db.query(Vendor).filter(
            Vendor.society_id == society_id, Vendor.is_active == True,  # noqa: E712
            func.lower(Vendor.company_name) == data["company_name"].lower()).first()
        if same_name:
            raise HTTPException(409, f"A vendor named '{same_name.company_name}' ({same_name.vendor_code}) already exists")
        if data.get("gst_number"):
            same_gst = self.db.query(Vendor).filter(
                Vendor.society_id == society_id, Vendor.is_active == True,  # noqa: E712
                Vendor.gst_number == data["gst_number"]).first()
            if same_gst:
                raise HTTPException(409, f"GST number {data['gst_number']} already belongs to {same_gst.company_name}")
        self._check_tds_setup(data)
        if data.get("constitution") and not data.get("tds_section"):
            from app.modules.vendor.services.vendor_tds import CATEGORY_DEFAULT_SECTION
            cat = data["category"]
            data["tds_section"] = CATEGORY_DEFAULT_SECTION.get(getattr(cat, "value", cat))
        code   = self.vendor_repo.next_vendor_code(society_id)
        vendor = Vendor(**data, vendor_code=code, registered_by=user.id)
        self.vendor_repo.create(vendor)
        self._audit(AuditAction.CREATE, vendor, "Vendor", user, request,
                    new_values={"code": code, "name": data["company_name"]})
        self.db.refresh(vendor)
        return vendor

    @staticmethod
    def _check_tds_setup(d: dict) -> None:
        """The vendor's type, PAN and TDS section have to agree, because the rate we deduct comes from them."""
        from app.modules.vendor.services import vendor_tds as t
        constitution, section = d.get("constitution"), d.get("tds_section")
        if constitution and constitution not in t.CONSTITUTION_VALUES:
            raise HTTPException(422, "Choose the vendor's type from the list")
        if section and section not in t.SECTION_VALUES:
            raise HTTPException(422, "Choose the TDS section from the list")
        if section and not constitution:
            raise HTTPException(422, "Choose the vendor's type (individual, firm, company...): the TDS rate depends on it")
        clash = t.pan_mismatch(d.get("pan_number"), constitution)
        if clash:
            raise HTTPException(422, clash)
        lower, start, end = d.get("tds_lower_rate"), d.get("tds_lower_valid_from"), d.get("tds_lower_valid_to")
        if lower is not None and not (0 <= Decimal(lower) <= 30):
            raise HTTPException(422, "A lower-deduction rate must be between 0 and 30%")
        if start and end and end < start:
            raise HTTPException(422, "The certificate's valid-to date is before its valid-from date")

    def update_vendor(self, vendor_id: UUID, data: dict, user: User, request=None) -> Vendor:
        from app.modules.vendor.models.vendor import VendorStatus
        v = self.get_vendor(vendor_id, user)
        if data.get("company_name") and data["company_name"].lower() != v.company_name.lower():
            same = self.db.query(Vendor).filter(
                Vendor.society_id == v.society_id, Vendor.is_active == True, Vendor.id != v.id,  # noqa: E712
                func.lower(Vendor.company_name) == data["company_name"].lower()).first()
            if same:
                raise HTTPException(409, f"A vendor named '{same.company_name}' ({same.vendor_code}) already exists")
        if data.get("gst_number"):
            same = self.db.query(Vendor).filter(
                Vendor.society_id == v.society_id, Vendor.is_active == True, Vendor.id != v.id,  # noqa: E712
                Vendor.gst_number == data["gst_number"]).first()
            if same:
                raise HTTPException(409, f"GST number {data['gst_number']} already belongs to {same.company_name}")
        self._check_tds_setup({**{k: getattr(v, k) for k in (
            "pan_number", "constitution", "tds_section", "tds_lower_rate", "tds_lower_valid_from",
            "tds_lower_valid_to")}, **data})
        old = {k: getattr(v, k) for k in data}
        for k, val_ in data.items():
            setattr(v, k, val_)
        if "status" in data and data["status"] != VendorStatus.BLACKLISTED:
            v.blacklist_reason = None
        self._audit(AuditAction.UPDATE, v, "Vendor", user, request,
                    old_values={k: str(x) if x is not None else None for k, x in old.items()},
                    new_values={k: str(x) if x is not None else None for k, x in data.items()})
        self.db.commit()
        self.db.refresh(v)
        return v

    def blacklist_vendor(self, vendor_id: UUID, reason: str, user: User) -> Vendor:
        v = self.get_vendor(vendor_id, user)
        from app.modules.vendor.models.vendor import VendorStatus
        v.status = VendorStatus.BLACKLISTED
        v.blacklist_reason = reason
        self._audit(AuditAction.UPDATE, v, "Vendor", user, new_values={"status": "blacklisted", "reason": reason})
        self.db.commit()
        self.db.refresh(v)
        return v

    def get_vendor(self, vendor_id: UUID, user: Optional[User] = None) -> Vendor:
        v = self.vendor_repo.get(vendor_id)
        if not v: raise HTTPException(404, "Vendor not found")
        return self._scoped(user, v, "Vendor")

    def list_vendors(self, society_id: UUID, skip=0, limit=50) -> List[Vendor]:
        return self.vendor_repo.get_by_society(society_id, skip, limit)

    def list_by_category(self, society_id: UUID, category) -> List[Vendor]:
        return self.vendor_repo.get_by_category(society_id, category)

    def add_service(self, vendor_id: UUID, data: dict, user: Optional[User] = None) -> VendorService:
        self.get_vendor(vendor_id, user)
        svc = VendorService(vendor_id=vendor_id, **data)
        self.db.add(svc)
        self.db.commit()
        self.db.refresh(svc)
        return svc

    # ── AMC Contracts ─────────────────────────────────────────────────────────

    def create_contract(self, data: dict, user: User, request=None) -> AMCContract:
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        self._vendor_in(data["vendor_id"], society_id)
        if data.get("asset_id"):
            from app.modules.inventory.models.inventory import Asset
            asset = self.db.get(Asset, data["asset_id"])
            if asset is None or asset.society_id != society_id:
                raise HTTPException(422, "Asset not found in this society")
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

        number   = self.contract_repo.next_contract_number(society_id)
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
        self._scoped(user, c, "Contract")
        if c.status != ContractStatus.DRAFT:
            raise HTTPException(409, f"Contract is already {c.status.value}")
        if not c.sanctioned_at:
            raise HTTPException(409, "Record the committee's sanction (and the general body's where needed) "
                                     "before the contract starts")
        from app.modules.vendor.models.vendor import VendorStatus
        if c.vendor.status != VendorStatus.ACTIVE:
            raise HTTPException(422, f"{c.vendor.company_name} is {c.vendor.status.value} and can't be given work")
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
        self._scoped(user, c, "Contract")
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
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        self._vendor_in(data.get("vendor_id"), society_id)
        if data.get("complaint_id"):
            from app.modules.complaint.models.complaint import Complaint
            complaint = self.db.get(Complaint, data["complaint_id"])
            if complaint is None or complaint.society_id != society_id:
                raise HTTPException(422, "Complaint not found in this society")
        if data.get("asset_id"):
            from app.modules.inventory.models.inventory import Asset
            asset = self.db.get(Asset, data["asset_id"])
            if asset is None or asset.society_id != society_id:
                raise HTTPException(422, "Asset not found in this society")
        number = self.sr_repo.next_request_number(society_id)
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
        self._scoped(user, sr, "Service request")
        allowed = SR_TRANSITIONS.get(sr.status, set())
        if ServiceRequestStatus.ASSIGNED not in allowed:
            raise HTTPException(409, f"Cannot assign vendor from status '{sr.status.value}'")

        self._vendor_in(vendor_id, sr.society_id, active_only=True)
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
        self._scoped(user, sr, "Service request")
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
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        self._vendor_in(data.get("vendor_id"), society_id)
        self._contract_in(data.get("contract_id"), society_id)
        self._request_in(data.get("request_id"), society_id)
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

    def get_sr(self, sr_id: UUID, user: Optional[User] = None) -> ServiceRequest:
        sr = self.sr_repo.get(sr_id)
        if not sr: raise HTTPException(404, "Service request not found")
        return self._scoped(user, sr, "Service request")

    def list_service_requests(self, society_id: UUID, skip=0, limit=50) -> List[ServiceRequest]:
        return self.sr_repo.get_by_society(society_id, skip, limit)

    def get_open_requests(self, society_id: UUID) -> List[ServiceRequest]:
        return self.sr_repo.get_open(society_id)

    # ── Vendor Invoices ───────────────────────────────────────────────────────

    def create_vendor_invoice(self, data: dict, user: User) -> VendorInvoice:
        data["society_id"] = society_id = resolve_create_society_id(user, data["society_id"])
        vendor = self._vendor_in(data["vendor_id"], society_id)
        self._contract_in(data.get("contract_id"), society_id)
        self._request_in(data.get("request_id"), society_id)
        if data.get("work_order_id"):
            from app.modules.vendor.services.work_orders import WorkOrderService
            WorkOrderService(self.db).check_bill(data["work_order_id"], data)
        same = self.db.query(VendorInvoice).filter(
            VendorInvoice.vendor_id == vendor.id, VendorInvoice.is_active == True,  # noqa: E712
            func.lower(VendorInvoice.invoice_number) == data["invoice_number"].lower()).first()
        if same:
            raise HTTPException(409, f"Invoice {same.invoice_number} is already recorded for {vendor.company_name}")
        if data.get("expense_account_id"):
            from app.modules.accounts.models.accounts import Account
            head = self.db.query(Account).filter(Account.id == data["expense_account_id"]).first()
            if not head or head.society_id != data["society_id"] or not head.is_active:
                raise HTTPException(422, "Expense head not found in this society")
        # Tax is calculated before the invoice is posted. The calculation is
        # additive: zero-tax invoices retain the existing two-leg AP posting.
        data["gst_component"] = data.get("gst_component") or "NONE"
        if data["gst_component"] == "NONE" and (
                Decimal(data.get("gst_amount") or 0) > 0 or Decimal(data.get("gst_rate") or 0) > 0):
            data["gst_component"] = self._default_gst_component(vendor, society_id)
        try:
            tax = self._calculate_tax(society_id, data)
        except ValueError as e:                 # a bill that does not add up is the caller's to correct, not a 500
            raise HTTPException(422, str(e))
        data.update(
            gst_amount=tax.gst_amount,
            cgst_amount=tax.cgst_amount,
            sgst_amount=tax.sgst_amount,
            igst_amount=tax.igst_amount,
            gst_rate=data.get("gst_rate", 0),
            tds_base_amount=tax.tds_base_amount,
            tds_amount=tax.tds_amount,
            net_payable_amount=tax.net_payable_amount,
        )
        if tax.tds_amount and not data.get("tds_applicable"):
            data["tds_applicable"] = True
        # tds_base is a calculation input, not a persisted invoice column.
        data.pop("tds_base", None)

        inv = VendorInvoice(**data)
        self.db.add(inv)
        self.db.flush()
        self._post("post_vendor_invoice", inv, user)
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def _default_gst_component(self, vendor, society_id: UUID) -> str:
        """CGST_SGST for a vendor in the society's own state, IGST for another state. The state is the first two
        digits of the GSTIN; when either GSTIN is missing the bill is treated as in-state."""
        from app.models.society import Society
        society = self.db.query(Society).filter(Society.id == society_id).first()
        mine, theirs = ((society.gst_number if society else None) or "")[:2], (vendor.gst_number or "")[:2]
        if mine.isdigit() and theirs.isdigit() and mine != theirs:
            return "IGST"
        return "CGST_SGST"

    def _calculate_tax(self, society_id: UUID, data: dict):
        from app.modules.accounts.services.taxes import TaxCalculationService
        return TaxCalculationService(self.db).calculate_vendor_invoice(
            society_id,
            amount=data["amount"],
            invoice_date=data.get("invoice_date"),
            gst_amount=data.get("gst_amount", 0),
            cgst_amount=data.get("cgst_amount", 0),
            sgst_amount=data.get("sgst_amount", 0),
            igst_amount=data.get("igst_amount", 0),
            gst_rate=data.get("gst_rate", 0),
            gst_component=data.get("gst_component", "NONE"),
            tds_applicable=data.get("tds_applicable", False),
            tds_rate=data.get("tds_rate", 0),
            tds_base=data.get("tds_base", "taxable_amount"),
            tds_amount=data.get("tds_amount", 0),
            gst_config_code=data.get("gst_config_code"),
            tds_config_code=data.get("tds_config_code"),
            gross_amount=data.get("total_amount"),
        )

    def _payment_ledger(self, society_id: UUID, payment_mode: VendorPaymentMode, account_id: Optional[UUID]):
        """The cash or bank ledger a payment is made from: the one chosen, which must suit the way it is paid."""
        if account_id is None:
            return None
        from app.modules.accounts.models.accounts import Account
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account or account.society_id != society_id or not account.is_active or not (
                account.is_cash or account.is_bank):
            raise HTTPException(422, "Choose a cash or bank ledger of this society to pay from")
        if (payment_mode == VendorPaymentMode.CASH) != bool(account.is_cash):
            raise HTTPException(422, "A cash payment is made from a cash ledger, and any other payment from a bank ledger")
        return account

    def record_vendor_payment(self, inv_id: UUID, amount: Decimal, paid_date: date,
                               payment_mode: VendorPaymentMode, transaction_ref: Optional[str],
                               bank_name: Optional[str], user: User,
                               bank_account_id: Optional[UUID] = None) -> VendorInvoice:
        """Record one immutable AP payment transaction against an invoice."""
        inv = self._pay_invoice(inv_id, amount, paid_date, payment_mode, transaction_ref, bank_name, user,
                                bank_account_id).invoice
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def _check_payable(self, inv_id: UUID, amount: Decimal, paid_date: date, payment_mode: VendorPaymentMode,
                       user: User, bank_account_id: Optional[UUID] = None):
        """Everything that decides whether `amount` can be paid against the invoice, without paying it:
        (invoice, ledger it is paid from, amount)."""
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        self._scoped(user, inv, "Invoice")
        if not inv.is_active:
            raise HTTPException(409, "Invoice was cancelled")
        ledger = self._payment_ledger(inv.society_id, payment_mode, bank_account_id)
        if paid_date < inv.invoice_date:
            raise HTTPException(422, "The payment can't be dated before the invoice")
        if inv.is_paid:
            raise HTTPException(409, "Invoice is already fully paid")
        amount = Decimal(amount)
        if amount <= 0:
            raise HTTPException(422, "Payment amount must be positive")
        tds_deducted = Decimal(inv.tds_amount or 0)
        outstanding = Decimal(inv.total_amount) - Decimal(inv.paid_amount) - tds_deducted
        if outstanding < 0:
            outstanding = Decimal("0")
        if amount > outstanding:
            raise HTTPException(422, f"Payment of {amount} exceeds outstanding balance of {outstanding}")
        if inv.work_order_id:
            from app.modules.vendor.services.work_orders import WorkOrderService
            WorkOrderService(self.db).check_payment(inv, amount)
        return inv, ledger, amount

    def _pay_invoice(self, inv_id: UUID, amount: Decimal, paid_date: date,
                     payment_mode: VendorPaymentMode, transaction_ref: Optional[str],
                     bank_name: Optional[str], user: User,
                     bank_account_id: Optional[UUID] = None) -> VendorPaymentTransaction:
        """One payment against one invoice, posted to the books."""
        inv, ledger, amount = self._check_payable(inv_id, amount, paid_date, payment_mode, user, bank_account_id)

        from app.modules.vendor.services.vendor_tds import compute_payment_tds
        tds = compute_payment_tds(self.db, inv.vendor, inv, amount, paid_date)
        payment = VendorPaymentTransaction(
            society_id=inv.society_id,
            vendor_id=inv.vendor_id,
            invoice_id=inv.id,
            payment_number="PENDING",
            payment_date=paid_date,
            amount=amount,
            taxable_value=tds.taxable_value,
            tds_section=tds.section if (tds.applies or tds.rule_code) else None,   # counts towards the year's total
            tds_rate=tds.rate if tds.applies else 0,
            tds_base_amount=tds.base,
            tds_amount=tds.tds,
            tds_note=tds.note[:255] or None,
            payment_mode=payment_mode,
            transaction_ref=transaction_ref,
            bank_name=bank_name,
            bank_account_id=ledger.id if ledger else None,
            created_by=user.id,
        )
        self.db.add(payment)
        self.db.flush()
        payment.payment_number = f"VP-{payment.id.hex[:12].upper()}"

        inv.paid_amount = Decimal(inv.paid_amount) + amount
        inv.payment_mode = payment_mode
        inv.payment_ref = transaction_ref
        inv.bank_name = bank_name
        inv.paid_date = paid_date
        inv.approved_by = user.id
        inv.is_paid = (Decimal(inv.paid_amount) + Decimal(inv.tds_amount or 0)) >= Decimal(inv.total_amount)

        self._post("post_vendor_payment", payment, user)

        self._audit(
            AuditAction.UPDATE, payment, "VendorPaymentTransaction", user,
            new_values={
                "amount": str(amount),
                "invoice": inv.invoice_number,
                "payment_number": payment.payment_number,
                "tds": str(tds.tds),
            },
        )
        return payment

    def open_bills(self, vendor_id: UUID, user: Optional[User] = None) -> dict:
        """What the society still owes a vendor, bill by bill, oldest due first — so a payment can be made against
        the bills it settles. The bill's own TDS (deducted when it was booked) is not payable to the vendor."""
        vendor = self.get_vendor(vendor_id, user)
        rows = (self.db.query(VendorInvoice)
                .filter(VendorInvoice.vendor_id == vendor.id, VendorInvoice.is_active == True,  # noqa: E712
                        VendorInvoice.is_paid == False)
                .order_by(VendorInvoice.due_date.is_(None), VendorInvoice.due_date, VendorInvoice.invoice_date).all())
        bills = []
        for i in rows:
            left = max(Decimal(i.total_amount) - Decimal(i.tds_amount or 0) - Decimal(i.paid_amount), Decimal("0"))
            if left <= 0:
                continue
            due = i.due_date or i.invoice_date
            bills.append({
                "invoice_id": str(i.id), "invoice_number": i.invoice_number, "description": i.description,
                "invoice_date": i.invoice_date.isoformat(), "due_date": due.isoformat(),
                "total": str(i.total_amount), "paid": str(i.paid_amount), "outstanding": str(left),
                "days_overdue": max(0, (date.today() - due).days),
            })
        return {"vendor_id": str(vendor.id), "vendor_name": vendor.company_name,
                "total_outstanding": str(sum((Decimal(b["outstanding"]) for b in bills), Decimal("0"))),
                "bills": bills}

    def pay_bills(self, vendor_id: UUID, items: List[dict], paid_date: date, payment_mode: VendorPaymentMode,
                  transaction_ref: Optional[str], bank_name: Optional[str], user: User,
                  bank_account_id: Optional[UUID] = None) -> dict:
        """One cheque or transfer settling several of a vendor's bills — each bill gets its own payment (and TDS),
        all or none. `items` are {invoice_id, amount}."""
        vendor = self.get_vendor(vendor_id, user)
        if not items:
            raise HTTPException(422, "Choose at least one bill to pay")
        seen = set()
        for it in items:
            if it["invoice_id"] in seen:
                raise HTTPException(422, "A bill can be paid only once in one payment")
            seen.add(it["invoice_id"])
        # Every bill is checked before the first is paid, so one that can't be paid stops the whole payment.
        for it in items:
            inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == it["invoice_id"]).first()
            if not inv or inv.vendor_id != vendor.id:
                raise HTTPException(422, "A bill chosen is not this vendor's")
            self._check_payable(inv.id, it["amount"], paid_date, payment_mode, user, bank_account_id)
        made = [self._pay_invoice(it["invoice_id"], Decimal(it["amount"]), paid_date, payment_mode, transaction_ref,
                                  bank_name, user, bank_account_id) for it in items]
        self.db.commit()
        total = sum((Decimal(p.amount) for p in made), Decimal("0"))
        tds = sum((Decimal(p.tds_amount or 0) for p in made), Decimal("0"))
        return {"vendor_id": str(vendor.id), "bills_paid": len(made), "settled": str(total),
                "tds_held": str(tds), "paid_to_vendor": str(total - tds),
                "payments": [{"invoice_number": p.invoice.invoice_number, "payment_number": p.payment_number,
                              "amount": str(p.amount), "tds": str(p.tds_amount or 0)} for p in made]}

    def cancel_invoice(self, inv_id: UUID, reason: str, user: User, reverse_payments: bool = False) -> VendorInvoice:
        """Take a wrongly entered bill out of the books and the payables. A bill that has been paid can't be
        cancelled until its payments are reversed: reverse them one by one first, or pass `reverse_payments` to
        reverse every payment of the bill and cancel it in one step (all or nothing)."""
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        self._scoped(user, inv, "Invoice")
        if not inv.is_active:
            raise HTTPException(409, "Invoice is already cancelled")
        live = [p for p in inv.payments if not p.is_reversed]
        if live and not reverse_payments:
            raise HTTPException(409, "This bill has payments against it — reverse them before cancelling the bill")
        payment_reason = f"Bill {inv.invoice_number} cancelled: {reason}"
        try:
            for payment in live:
                self._reverse_payment(payment, payment_reason, user)
        except Exception:
            self.db.rollback()
            raise
        inv.is_active = False
        from app.modules.accounts.services.postings import AccountPostings
        AccountPostings(self.db)._cancel_source(
            "vendor_invoice", inv.id, f"Bill {inv.invoice_number} cancelled: {reason}", user)
        self.db.flush()
        for payment in live:
            self._audit_payment_reversed(payment, payment_reason, user)
        self._audit(AuditAction.UPDATE, inv, "VendorInvoice", user,
                    new_values={"cancelled": True, "reason": reason, "invoice": inv.invoice_number,
                                "payments_reversed": len(live)})
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def payment_preview(self, inv_id: UUID, amount: Decimal, paid_date: date, user: User) -> dict:
        """What paying `amount` on `paid_date` would do: the TDS and what the vendor receives. Saves nothing."""
        from app.modules.vendor.services.vendor_tds import compute_payment_tds
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        self._scoped(user, inv, "Invoice")
        amount = Decimal(amount)
        r = compute_payment_tds(self.db, inv.vendor, inv, amount, paid_date)
        self.db.commit()          # the society's starting TDS rules, if this was the first use
        return {
            "amount": str(amount), "taxable_value": str(r.taxable_value), "applies": r.applies,
            "section": r.section, "section_label": r.section_label, "rate": str(r.rate),
            "tds_base": str(r.base), "tds_amount": str(r.tds), "net_payable": str(amount - r.tds),
            "note": r.note,
        }

    def reverse_vendor_payment(self, payment_id: UUID, reason: str, user: User) -> VendorInvoice:
        payment = self.db.query(VendorPaymentTransaction).filter(
            VendorPaymentTransaction.id == payment_id
        ).first()
        if not payment:
            raise HTTPException(404, "Payment transaction not found")
        self._scoped(user, payment, "Payment transaction")
        inv = self._reverse_payment(payment, reason, user)
        self._audit_payment_reversed(payment, reason, user)
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def _reverse_payment(self, payment: VendorPaymentTransaction, reason: str, user: User) -> VendorInvoice:
        """Reverse one payment of a bill: the bill's paid amount and status go back, and the payment's accounting
        entry is reversed. Flushed, not committed, so a caller can do several in one transaction."""
        if payment.is_reversed:
            raise HTTPException(409, "Payment transaction is already reversed")

        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == payment.invoice_id).first()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if Decimal(inv.paid_amount) < Decimal(payment.amount):
            raise HTTPException(409, "Invoice payment balance is inconsistent")

        payment.is_reversed = True
        payment.reversed_at = datetime.utcnow()
        payment.reversal_reason = reason
        inv.paid_amount = Decimal(inv.paid_amount) - Decimal(payment.amount)
        inv.is_paid = (Decimal(inv.paid_amount) + Decimal(inv.tds_amount or 0)) >= Decimal(inv.total_amount)
        latest = self.db.query(VendorPaymentTransaction).filter(
            VendorPaymentTransaction.invoice_id == inv.id,
            VendorPaymentTransaction.is_reversed == False,
        ).order_by(
            VendorPaymentTransaction.payment_date.desc(),
            VendorPaymentTransaction.created_at.desc(),
        ).first()
        if latest:
            inv.paid_date = latest.payment_date
            inv.payment_mode = latest.payment_mode
            inv.payment_ref = latest.transaction_ref
            inv.bank_name = latest.bank_name
        else:
            inv.paid_date = None
            inv.payment_mode = None
            inv.payment_ref = None
            inv.bank_name = None
        self._post("reverse_vendor_payment", payment, reason, user)
        return inv

    def _audit_payment_reversed(self, payment: VendorPaymentTransaction, reason: str, user: User) -> None:
        """The audit entry commits, so it is written only once all the reversals of a request are done."""
        self._audit(AuditAction.UPDATE, payment, "VendorPaymentTransaction", user,
                    new_values={"reversed": True, "reason": reason})

    def get_vendor_invoices(self, vendor_id: UUID, user: Optional[User] = None) -> List[VendorInvoice]:
        self.get_vendor(vendor_id, user)
        return self.db.query(VendorInvoice).filter(
            VendorInvoice.vendor_id == vendor_id, VendorInvoice.is_active == True  # noqa: E712
        ).order_by(VendorInvoice.invoice_date.desc()).all()

    def list_invoices_by_society(self, society_id: UUID, is_paid: Optional[bool] = None,
                                  skip=0, limit=50) -> List[VendorInvoice]:
        q = self.db.query(VendorInvoice).filter(VendorInvoice.society_id == society_id,
                                                VendorInvoice.is_active == True)  # noqa: E712
        if is_paid is not None:
            q = q.filter(VendorInvoice.is_paid == is_paid)
        return q.order_by(VendorInvoice.invoice_date.desc()).offset(skip).limit(limit).all()

    def get_vendor_invoice(self, inv_id: UUID, user: Optional[User] = None) -> VendorInvoice:
        inv = self.db.query(VendorInvoice).filter(VendorInvoice.id == inv_id).first()
        if not inv: raise HTTPException(404, "Invoice not found")
        return self._scoped(user, inv, "Invoice")
