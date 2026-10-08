"""
Vendor & AMC Management Models.

Distinct from AssetAMC (inventory module):
- AssetAMC: asset-specific contract stored with the asset
- AMCContract here: vendor-centric contract linking multiple assets/services

Workflows:
  Vendor: ACTIVE/INACTIVE/BLACKLISTED
  AMCContract: DRAFT → ACTIVE → EXPIRED/RENEWED/TERMINATED
  ServiceRequest: OPEN → ASSIGNED → SCHEDULED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED
"""
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Date, Enum, ForeignKey, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr, relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class VendorCategory(str, enum.Enum):
    ELECTRICAL   = "electrical"
    PLUMBING     = "plumbing"
    LIFT         = "lift"
    SECURITY     = "security"
    HOUSEKEEPING = "housekeeping"
    GARDENING    = "gardening"
    PEST_CONTROL = "pest_control"
    CCTV         = "cctv"
    WATER_SUPPLY = "water_supply"
    GENERATOR    = "generator"
    CIVIL        = "civil"
    IT           = "it"
    OTHER        = "other"


class VendorStatus(str, enum.Enum):
    ACTIVE      = "active"
    INACTIVE    = "inactive"
    BLACKLISTED = "blacklisted"
    UNDER_REVIEW= "under_review"


class ContractStatus(str, enum.Enum):
    DRAFT      = "draft"
    ACTIVE     = "active"
    EXPIRED    = "expired"
    RENEWED    = "renewed"
    TERMINATED = "terminated"


class ServiceFrequency(str, enum.Enum):
    WEEKLY      = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY     = "monthly"
    QUARTERLY   = "quarterly"
    HALF_YEARLY = "half_yearly"
    YEARLY      = "yearly"
    ON_CALL     = "on_call"


class ServiceRequestStatus(str, enum.Enum):
    OPEN        = "open"
    ASSIGNED    = "assigned"
    SCHEDULED   = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    VERIFIED    = "verified"
    CLOSED      = "closed"
    CANCELLED   = "cancelled"


class ServiceRequestPriority(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class ScheduleStatus(str, enum.Enum):
    SCHEDULED  = "scheduled"
    COMPLETED  = "completed"
    MISSED     = "missed"
    RESCHEDULED= "rescheduled"


class VendorPaymentMode(str, enum.Enum):
    CASH          = "cash"
    UPI           = "upi"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE        = "cheque"
    NEFT          = "neft"
    RTGS          = "rtgs"


class WorkOrderStatus(str, enum.Enum):
    DRAFT      = "draft"        # quotations being collected
    SANCTIONED = "sanctioned"   # awarded by committee / general body resolution
    ISSUED     = "issued"       # work order given to the vendor
    COMPLETED  = "completed"    # completion certified by the committee
    CLOSED     = "closed"       # every bill paid
    CANCELLED  = "cancelled"


class SanctionLevel(str, enum.Enum):
    COMMITTEE    = "committee"
    GENERAL_BODY = "general_body"


# ── Sanction (who approved spending the society's money, and how) ───────────

class SanctionMixin:
    """The decision to award a work or contract, as the model bye-laws
    require it to be recorded: the committee's resolution, the general
    body's when the amount is beyond what the committee may spend on its own
    or tenders were needed, the date tenders were opened in the committee
    meeting, why a quotation other than the lowest was chosen, and the
    declaration that no committee member has an interest in it."""
    sanctioned_amount      = Column(Numeric(12, 2), nullable=True)
    sanction_level         = Column(Enum(SanctionLevel, values_callable=lambda e: [x.value for x in e]), nullable=True)
    committee_resolution_no = Column(String(50), nullable=True)
    committee_meeting_date = Column(Date, nullable=True)
    gb_resolution_no       = Column(String(50), nullable=True)
    gb_meeting_date        = Column(Date, nullable=True)
    tenders_opened_on      = Column(Date, nullable=True)
    selection_reason       = Column(Text, nullable=True)
    no_interest_declared   = Column(Boolean, default=False, nullable=False)
    sanctioned_at          = Column(DateTime, nullable=True)

    @declared_attr
    def sanctioned_by(cls):
        return Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ── ServiceRequest FSM transitions ───────────────────────────────────────────
SR_TRANSITIONS: dict = {
    ServiceRequestStatus.OPEN:        {ServiceRequestStatus.ASSIGNED, ServiceRequestStatus.CANCELLED},
    ServiceRequestStatus.ASSIGNED:    {ServiceRequestStatus.SCHEDULED, ServiceRequestStatus.CANCELLED},
    ServiceRequestStatus.SCHEDULED:   {ServiceRequestStatus.IN_PROGRESS, ServiceRequestStatus.CANCELLED},
    ServiceRequestStatus.IN_PROGRESS: {ServiceRequestStatus.COMPLETED, ServiceRequestStatus.CANCELLED},
    ServiceRequestStatus.COMPLETED:   {ServiceRequestStatus.VERIFIED, ServiceRequestStatus.IN_PROGRESS},
    ServiceRequestStatus.VERIFIED:    {ServiceRequestStatus.CLOSED},
    ServiceRequestStatus.CLOSED:      set(),
    ServiceRequestStatus.CANCELLED:   set(),
}


# ── Vendor ────────────────────────────────────────────────────────────────────

class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_code      = Column(String(20), nullable=False, index=True)
    company_name     = Column(String(255), nullable=False, index=True)
    contact_person   = Column(String(255), nullable=True)
    mobile           = Column(String(20), nullable=False, index=True)
    email            = Column(String(255), nullable=True)
    category         = Column(Enum(VendorCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    status           = Column(Enum(VendorStatus, values_callable=lambda e: [x.value for x in e]), default=VendorStatus.ACTIVE, nullable=False, index=True)

    # Address
    address          = Column(Text, nullable=True)
    city             = Column(String(100), nullable=True)
    pincode          = Column(String(10), nullable=True)

    # Finance readiness
    gst_number       = Column(String(20), nullable=True, index=True)
    pan_number       = Column(String(20), nullable=True)
    bank_account     = Column(String(50), nullable=True)
    bank_name        = Column(String(100), nullable=True)
    bank_ifsc        = Column(String(20), nullable=True)

    # Ratings / performance readiness
    rating           = Column(Float, nullable=True)      # 1-5 star
    total_services   = Column(Integer, default=0, nullable=False)
    services_on_time = Column(Integer, default=0, nullable=False)

    # Documents readiness
    agreement_doc_url = Column(String(500), nullable=True)
    insurance_expiry  = Column(Date, nullable=True)
    notes             = Column(Text, nullable=True)
    blacklist_reason  = Column(Text, nullable=True)

    registered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "vendor_code", name="uq_vendor_society_code"),)

    society      = relationship("Society")
    registrar    = relationship("User", foreign_keys=[registered_by])
    contracts    = relationship("AMCContract",    back_populates="vendor", cascade="all, delete-orphan")
    services     = relationship("VendorService",  back_populates="vendor", cascade="all, delete-orphan")
    invoices     = relationship("VendorInvoice",  back_populates="vendor", cascade="all, delete-orphan")
    service_reqs = relationship("ServiceRequest", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor {self.vendor_code} {self.company_name}>"


# ── VendorService (capability catalogue) ─────────────────────────────────────

class VendorService(Base, TimestampMixin):
    """Services a vendor offers — used for matching when assigning."""
    __tablename__ = "vendor_services"

    vendor_id    = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(150), nullable=False)
    category     = Column(Enum(VendorCategory, values_callable=lambda e: [x.value for x in e]), nullable=False)
    rate_per_visit= Column(Numeric(10, 2), nullable=True)
    rate_per_hour = Column(Numeric(8, 2), nullable=True)
    description  = Column(Text, nullable=True)

    vendor = relationship("Vendor", back_populates="services")


# ── AMCContract ───────────────────────────────────────────────────────────────

class AMCContract(Base, TimestampMixin, SanctionMixin):
    __tablename__ = "amc_contracts"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id        = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id         = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)   # optional asset linkage
    created_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    contract_number  = Column(String(50), nullable=False, index=True)
    contract_name    = Column(String(255), nullable=False)
    category         = Column(Enum(VendorCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    status           = Column(Enum(ContractStatus, values_callable=lambda e: [x.value for x in e]), default=ContractStatus.DRAFT, nullable=False, index=True)

    start_date       = Column(Date, nullable=False, index=True)
    end_date         = Column(Date, nullable=False, index=True)
    auto_renew       = Column(Boolean, default=False, nullable=False)
    renewal_notice_days = Column(Integer, default=30, nullable=False)

    # Service config
    service_frequency = Column(Enum(ServiceFrequency, values_callable=lambda e: [x.value for x in e]), nullable=False)
    sla_response_hours = Column(Integer, nullable=True)   # SLA readiness
    scope_of_work     = Column(Text, nullable=True)
    inclusions        = Column(Text, nullable=True)
    exclusions        = Column(Text, nullable=True)

    # Finance
    annual_value      = Column(Numeric(12, 2), nullable=True)
    payment_terms     = Column(String(255), nullable=True)
    document_url      = Column(String(500), nullable=True)

    # Alert flags
    alert_sent_60     = Column(Boolean, default=False, nullable=False)
    alert_sent_30     = Column(Boolean, default=False, nullable=False)
    alert_sent_7      = Column(Boolean, default=False, nullable=False)

    # Renewal linkage
    renewed_from_id   = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "contract_number", name="uq_contract_society_number"),)

    society   = relationship("Society")
    vendor    = relationship("Vendor", back_populates="contracts")
    creator   = relationship("User", foreign_keys=[created_by])
    sanctioner = relationship("User", foreign_keys="AMCContract.sanctioned_by")
    schedules = relationship("AMCServiceSchedule", back_populates="contract", cascade="all, delete-orphan")
    quotations = relationship("Quotation", back_populates="contract", order_by="Quotation.total_amount")

    def days_to_expiry(self) -> int:
        from datetime import date
        return (self.end_date - date.today()).days

    def __repr__(self):
        return f"<AMCContract {self.contract_number} [{self.status}]>"


# ── AMCServiceSchedule ────────────────────────────────────────────────────────

class AMCServiceSchedule(Base, TimestampMixin):
    __tablename__ = "amc_service_schedules"

    contract_id    = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_date = Column(Date, nullable=False, index=True)
    status         = Column(Enum(ScheduleStatus, values_callable=lambda e: [x.value for x in e]), default=ScheduleStatus.SCHEDULED, nullable=False, index=True)
    completed_date = Column(Date, nullable=True)
    notes          = Column(Text, nullable=True)
    visit_log_id   = Column(UUID(as_uuid=True), ForeignKey("service_visit_logs.id", ondelete="SET NULL"), nullable=True, index=True)   # ref to ServiceVisitLog

    contract = relationship("AMCContract", back_populates="schedules")
    society  = relationship("Society")


# ── ServiceRequest ────────────────────────────────────────────────────────────

class ServiceRequest(Base, TimestampMixin):
    __tablename__ = "service_requests"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    raised_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    verified_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    complaint_id   = Column(UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True, index=True)   # linked complaint
    asset_id       = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)   # linked asset

    request_number = Column(String(20), nullable=False, index=True)
    title          = Column(String(255), nullable=False)
    description    = Column(Text, nullable=True)
    category       = Column(Enum(VendorCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    priority       = Column(Enum(ServiceRequestPriority, values_callable=lambda e: [x.value for x in e]), default=ServiceRequestPriority.MEDIUM, nullable=False)
    status         = Column(Enum(ServiceRequestStatus, values_callable=lambda e: [x.value for x in e]), default=ServiceRequestStatus.OPEN, nullable=False, index=True)
    location       = Column(String(255), nullable=True)

    # Scheduling
    preferred_date = Column(Date, nullable=True)
    scheduled_date = Column(Date, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    verified_date  = Column(DateTime, nullable=True)

    # SLA
    sla_due_date   = Column(DateTime, nullable=True)
    is_overdue     = Column(Boolean, default=False, nullable=False, index=True)

    # Closure
    completion_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    estimated_cost   = Column(Numeric(10, 2), nullable=True)
    actual_cost      = Column(Numeric(10, 2), nullable=True)

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "request_number", name="uq_service_request_society_number"),)

    society      = relationship("Society")
    vendor       = relationship("Vendor", back_populates="service_reqs", foreign_keys=[vendor_id])
    raiser       = relationship("User", foreign_keys=[raised_by])
    assigner     = relationship("User", foreign_keys=[assigned_by])
    verifier     = relationship("User", foreign_keys=[verified_by])
    visit_logs   = relationship("ServiceVisitLog", back_populates="request", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ServiceRequest {self.request_number} [{self.status}]>"


# ── ServiceVisitLog ───────────────────────────────────────────────────────────

class ServiceVisitLog(Base, TimestampMixin):
    """Append-only log for every vendor visit against a service request or AMC schedule."""
    __tablename__ = "service_visit_logs"

    request_id     = Column(UUID(as_uuid=True), ForeignKey("service_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    contract_id    = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    logged_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    visit_date     = Column(Date, nullable=False, index=True)
    check_in_time  = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    work_done      = Column(Text, nullable=True)
    materials_used = Column(Text, nullable=True)
    next_visit_date= Column(Date, nullable=True)
    photo_url      = Column(String(500), nullable=True)
    is_satisfactory= Column(Boolean, default=True, nullable=False)

    request  = relationship("ServiceRequest", back_populates="visit_logs")
    society  = relationship("Society")
    vendor   = relationship("Vendor", foreign_keys=[vendor_id])
    logger   = relationship("User", foreign_keys=[logged_by])


# ── VendorInvoice ─────────────────────────────────────────────────────────────

class VendorInvoice(Base, TimestampMixin):
    """Vendor invoice for service/AMC — finance ERP ready. This is the
    society's payable side, the mirror of the resident-facing
    OnlinePaymentSubmission (billing module): amount owed here goes OUT
    to a vendor rather than coming IN from a resident. paid_amount
    accumulates across possibly-partial payments (see
    VendorService_.record_vendor_payment); is_paid flips true only once
    paid_amount reaches total_amount."""
    __tablename__ = "vendor_invoices"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id    = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    request_id     = Column(UUID(as_uuid=True), ForeignKey("service_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    work_order_id  = Column(UUID(as_uuid=True), ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    invoice_number = Column(String(50), nullable=False, index=True)
    invoice_date   = Column(Date, nullable=False, index=True)
    due_date       = Column(Date, nullable=True)
    amount         = Column(Numeric(12, 2), nullable=False)
    gst_amount     = Column(Numeric(10, 2), default=0, nullable=False)
    gst_rate       = Column(Numeric(7, 4), default=0, nullable=False)
    gst_component  = Column(String(20), default="NONE", nullable=False)  # CGST_SGST | IGST | NONE
    cgst_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    sgst_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    igst_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    gst_itc_eligible = Column(Boolean, default=True, nullable=False)
    tds_applicable = Column(Boolean, default=False, nullable=False)
    tds_section    = Column(String(30), nullable=True)
    tds_rate       = Column(Numeric(7, 4), default=0, nullable=False)
    tds_base_amount = Column(Numeric(12, 2), default=0, nullable=False)
    tds_amount     = Column(Numeric(12, 2), default=0, nullable=False)
    net_payable_amount = Column(Numeric(12, 2), nullable=True)
    gst_config_code = Column(String(40), nullable=True)
    tds_config_code = Column(String(40), nullable=True)
    total_amount   = Column(Numeric(12, 2), nullable=False)
    paid_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    is_paid        = Column(Boolean, default=False, nullable=False, index=True)
    paid_date      = Column(Date, nullable=True)
    payment_mode   = Column(Enum(VendorPaymentMode, values_callable=lambda e: [x.value for x in e]), nullable=True)
    payment_ref    = Column(String(100), nullable=True)
    bank_name      = Column(String(100), nullable=True)
    description    = Column(Text, nullable=True)
    doc_url        = Column(String(500), nullable=True)
    # Expense head (accounts ledger) the bill is booked to; unset: by the
    # vendor's category (see accounts/services/chart_of_accounts.py).
    expense_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    society  = relationship("Society")
    vendor   = relationship("Vendor", back_populates="invoices")
    contract = relationship("AMCContract")
    request  = relationship("ServiceRequest")
    work_order = relationship("WorkOrder", back_populates="invoices")
    approver = relationship("User", foreign_keys=[approved_by])
    payments = relationship("VendorPaymentTransaction", back_populates="invoice",
                            cascade="all, delete-orphan", order_by="VendorPaymentTransaction.payment_date")


# ── Vendor payment transactions ───────────────────────────────────────────────

class VendorPaymentTransaction(Base, TimestampMixin):
    """Immutable identity for each vendor payment.

    One invoice can have many partial payments. The invoice's paid_amount is
    only the aggregate; this table is the transaction-level audit trail used
    by AP and the accounting posting source.
    """
    __tablename__ = "vendor_payment_transactions"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("vendor_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_number = Column(String(40), nullable=False, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_mode = Column(Enum(VendorPaymentMode, values_callable=lambda e: [x.value for x in e]), nullable=True, index=True)
    transaction_ref = Column(String(100), nullable=True, index=True)
    bank_name = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)
    is_reversed = Column(Boolean, default=False, nullable=False, index=True)
    is_legacy = Column(Boolean, default=False, nullable=False, index=True)
    reversed_at = Column(DateTime, nullable=True)
    reversal_reason = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society = relationship("Society")
    vendor = relationship("Vendor")
    invoice = relationship("VendorInvoice", back_populates="payments")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("society_id", "payment_number", name="uq_vendor_payment_society_number"),
    )


# ── Procurement rules (fixed by the general body) ─────────────────────────────

class ProcurementSettings(Base, TimestampMixin):
    """How much the committee may spend on a work by itself, and above what
    amount tenders are needed — model bye-law 157. Left blank, the committee
    limit is the bye-law slab for the society's size (₹25,000 up to 25
    members, ₹50,000 up to 50, ₹1,00,000 above) and the tender limit equals
    it. A general body can fix other figures; the resolution is recorded."""
    __tablename__ = "procurement_settings"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"),
                             nullable=False, unique=True, index=True)
    committee_limit = Column(Numeric(12, 2), nullable=True)
    tender_limit    = Column(Numeric(12, 2), nullable=True)
    min_quotations  = Column(Integer, default=3, nullable=False)
    gb_resolution_no = Column(String(50), nullable=True)     # the general body decision fixing these limits
    gb_meeting_date = Column(Date, nullable=True)

    society = relationship("Society")


# ── Work order ────────────────────────────────────────────────────────────────

class WorkOrder(Base, TimestampMixin, SanctionMixin):
    """A one-time work given to a vendor: quotations are collected, the work
    is sanctioned by resolution, the written work order is issued, the
    committee certifies completion, and the vendor's bills are paid within
    the sanctioned amount — advance before completion, retention held for
    the defect liability period."""
    __tablename__ = "work_orders"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    service_request_id = Column(UUID(as_uuid=True), ForeignKey("service_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    complaint_id   = Column(UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id       = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    expense_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    created_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancelled_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    wo_number      = Column(String(30), nullable=False, index=True)
    title          = Column(String(255), nullable=False)
    scope_of_work  = Column(Text, nullable=True)
    location       = Column(String(255), nullable=True)
    category       = Column(Enum(VendorCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    estimated_cost = Column(Numeric(12, 2), nullable=True)
    status         = Column(Enum(WorkOrderStatus, values_callable=lambda e: [x.value for x in e]),
                            default=WorkOrderStatus.DRAFT, nullable=False, index=True)

    # Terms printed on the work order
    start_date     = Column(Date, nullable=True)
    due_date       = Column(Date, nullable=True)       # to be completed by
    payment_terms  = Column(Text, nullable=True)
    advance_amount = Column(Numeric(12, 2), default=0, nullable=False)
    retention_pct  = Column(Numeric(5, 2), default=0, nullable=False)
    defect_liability_months = Column(Integer, default=0, nullable=False)

    issued_on      = Column(Date, nullable=True)
    completed_on   = Column(Date, nullable=True)
    completion_notes = Column(Text, nullable=True)
    certificate_ref = Column(String(100), nullable=True)   # architect / engineer's certificate, if any
    retention_released_on = Column(Date, nullable=True)
    closed_on      = Column(Date, nullable=True)
    cancelled_at   = Column(DateTime, nullable=True)
    cancel_reason  = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("society_id", "wo_number", name="uq_work_order_society_number"),)

    society    = relationship("Society")
    vendor     = relationship("Vendor", foreign_keys=[vendor_id])
    quotations = relationship("Quotation", back_populates="work_order", order_by="Quotation.total_amount")
    invoices   = relationship("VendorInvoice", back_populates="work_order")
    sanctioner = relationship("User", foreign_keys="WorkOrder.sanctioned_by")
    certifier  = relationship("User", foreign_keys=[completed_by])
    expense_account = relationship("Account", foreign_keys=[expense_account_id])

    def __repr__(self):
        return f"<WorkOrder {self.wo_number} [{self.status}]>"


# ── Quotation / tender ────────────────────────────────────────────────────────

class Quotation(Base, TimestampMixin):
    """A vendor's offer for a work order or an annual contract."""
    __tablename__ = "vendor_quotations"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_id  = Column(UUID(as_uuid=True), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=True, index=True)
    contract_id    = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="CASCADE"), nullable=True, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    received_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    quotation_ref  = Column(String(50), nullable=True)
    quotation_date = Column(Date, nullable=False)
    valid_until    = Column(Date, nullable=True)
    amount         = Column(Numeric(12, 2), nullable=False)
    gst_amount     = Column(Numeric(12, 2), default=0, nullable=False)
    total_amount   = Column(Numeric(12, 2), nullable=False)
    remarks        = Column(Text, nullable=True)
    doc_url        = Column(String(500), nullable=True)
    is_selected    = Column(Boolean, default=False, nullable=False)   # the one awarded

    work_order = relationship("WorkOrder", back_populates="quotations")
    contract   = relationship("AMCContract", back_populates="quotations")
    vendor     = relationship("Vendor")
