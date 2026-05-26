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
    DateTime, Date, Enum, ForeignKey, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
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
    vendor_code      = Column(String(20), nullable=False, unique=True, index=True)
    company_name     = Column(String(255), nullable=False, index=True)
    contact_person   = Column(String(255), nullable=True)
    mobile           = Column(String(20), nullable=False, index=True)
    email            = Column(String(255), nullable=True)
    category         = Column(Enum(VendorCategory), nullable=False, index=True)
    status           = Column(Enum(VendorStatus), default=VendorStatus.ACTIVE, nullable=False, index=True)

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

    registered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

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
    category     = Column(Enum(VendorCategory), nullable=False)
    rate_per_visit= Column(Numeric(10, 2), nullable=True)
    rate_per_hour = Column(Numeric(8, 2), nullable=True)
    description  = Column(Text, nullable=True)

    vendor = relationship("Vendor", back_populates="services")


# ── AMCContract ───────────────────────────────────────────────────────────────

class AMCContract(Base, TimestampMixin):
    __tablename__ = "amc_contracts"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id        = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id         = Column(UUID(as_uuid=True), nullable=True, index=True)   # optional asset linkage
    created_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    contract_number  = Column(String(50), nullable=False, unique=True, index=True)
    contract_name    = Column(String(255), nullable=False)
    category         = Column(Enum(VendorCategory), nullable=False, index=True)
    status           = Column(Enum(ContractStatus), default=ContractStatus.DRAFT, nullable=False, index=True)

    start_date       = Column(Date, nullable=False, index=True)
    end_date         = Column(Date, nullable=False, index=True)
    auto_renew       = Column(Boolean, default=False, nullable=False)
    renewal_notice_days = Column(Integer, default=30, nullable=False)

    # Service config
    service_frequency = Column(Enum(ServiceFrequency), nullable=False)
    sla_response_hours = Column(Integer, nullable=True)   # SLA readiness
    scope_of_work     = Column(Text, nullable=True)
    inclusions        = Column(Text, nullable=True)
    exclusions        = Column(Text, nullable=True)

    # Finance
    annual_value      = Column(Numeric(12, 2), nullable=True)
    payment_terms     = Column(String(255), nullable=True)
    document_url      = Column(String(500), nullable=True)

    # Alert flags
    alert_sent_60     = Column(Boolean, default=False)
    alert_sent_30     = Column(Boolean, default=False)
    alert_sent_7      = Column(Boolean, default=False)

    # Renewal linkage
    renewed_from_id   = Column(UUID(as_uuid=True), nullable=True)

    society   = relationship("Society")
    vendor    = relationship("Vendor", back_populates="contracts")
    creator   = relationship("User", foreign_keys=[created_by])
    schedules = relationship("AMCServiceSchedule", back_populates="contract", cascade="all, delete-orphan")

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
    status         = Column(Enum(ScheduleStatus), default=ScheduleStatus.SCHEDULED, nullable=False, index=True)
    completed_date = Column(Date, nullable=True)
    notes          = Column(Text, nullable=True)
    visit_log_id   = Column(UUID(as_uuid=True), nullable=True)   # ref to ServiceVisitLog

    contract = relationship("AMCContract", back_populates="schedules")
    society  = relationship("Society")


# ── ServiceRequest ────────────────────────────────────────────────────────────

class ServiceRequest(Base, TimestampMixin):
    __tablename__ = "service_requests"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    raised_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    complaint_id   = Column(UUID(as_uuid=True), nullable=True)   # linked complaint
    asset_id       = Column(UUID(as_uuid=True), nullable=True)   # linked asset

    request_number = Column(String(20), nullable=False, unique=True, index=True)
    title          = Column(String(255), nullable=False)
    description    = Column(Text, nullable=True)
    category       = Column(Enum(VendorCategory), nullable=False, index=True)
    priority       = Column(Enum(ServiceRequestPriority), default=ServiceRequestPriority.MEDIUM, nullable=False)
    status         = Column(Enum(ServiceRequestStatus), default=ServiceRequestStatus.OPEN, nullable=False, index=True)
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
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    logged_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

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
    """Vendor invoice for service/AMC — finance ERP ready."""
    __tablename__ = "vendor_invoices"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id    = Column(UUID(as_uuid=True), ForeignKey("amc_contracts.id", ondelete="SET NULL"), nullable=True)
    request_id     = Column(UUID(as_uuid=True), ForeignKey("service_requests.id", ondelete="SET NULL"), nullable=True)
    approved_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    invoice_number = Column(String(50), nullable=False, index=True)
    invoice_date   = Column(Date, nullable=False, index=True)
    due_date       = Column(Date, nullable=True)
    amount         = Column(Numeric(12, 2), nullable=False)
    gst_amount     = Column(Numeric(10, 2), default=0, nullable=False)
    total_amount   = Column(Numeric(12, 2), nullable=False)
    paid_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    is_paid        = Column(Boolean, default=False, nullable=False, index=True)
    paid_date      = Column(Date, nullable=True)
    payment_ref    = Column(String(100), nullable=True)
    description    = Column(Text, nullable=True)
    doc_url        = Column(String(500), nullable=True)

    society  = relationship("Society")
    vendor   = relationship("Vendor", back_populates="invoices")
    contract = relationship("AMCContract")
    request  = relationship("ServiceRequest")
    approver = relationship("User", foreign_keys=[approved_by])
