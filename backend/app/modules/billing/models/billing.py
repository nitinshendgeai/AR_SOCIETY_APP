"""
Maintenance Billing & Finance Foundation Models.

Bill FSM:  DRAFT → GENERATED → ISSUED → PARTIALLY_PAID → PAID → OVERDUE | CANCELLED

Architecture is finance-ERP-ready:
- FinancialPeriod: accounting periods for future ledger integration
- BillingCycle: per-society billing runs with configurable charges
- MaintenanceBill: per-flat invoice with line items
- PaymentReceipt: immutable payment records
- DueTracker: rolling balance sheet per flat
- PenaltyRule: configurable late-fee engine
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

class ChargeType(str, enum.Enum):
    MAINTENANCE     = "maintenance"
    WATER           = "water"
    PARKING         = "parking"
    SINKING_FUND    = "sinking_fund"
    REPAIR_FUND     = "repair_fund"
    AMENITIES       = "amenities"
    PENALTY         = "penalty"
    SPECIAL_ASSESSMENT = "special_assessment"
    OTHER           = "other"


class BillStatus(str, enum.Enum):
    DRAFT            = "draft"
    GENERATED        = "generated"
    ISSUED           = "issued"
    PARTIALLY_PAID   = "partially_paid"
    PAID             = "paid"
    OVERDUE          = "overdue"
    CANCELLED        = "cancelled"


class PaymentMode(str, enum.Enum):
    CASH             = "cash"
    UPI              = "upi"
    BANK_TRANSFER    = "bank_transfer"
    CHEQUE           = "cheque"
    ONLINE_GATEWAY   = "online_gateway"
    NEFT             = "neft"
    RTGS             = "rtgs"


class PenaltyCalculationType(str, enum.Enum):
    FLAT_AMOUNT      = "flat_amount"
    PERCENTAGE       = "percentage"
    COMPOUND_DAILY   = "compound_daily"


class CycleFrequency(str, enum.Enum):
    MONTHLY          = "monthly"
    QUARTERLY        = "quarterly"
    HALF_YEARLY      = "half_yearly"
    YEARLY           = "yearly"
    CUSTOM           = "custom"


# ── FinancialPeriod ───────────────────────────────────────────────────────────

class FinancialPeriod(Base, TimestampMixin):
    """
    Accounting period (month/quarter/year) for future ledger integration.
    All bills and receipts reference a financial period.
    """
    __tablename__ = "financial_periods"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name         = Column(String(100), nullable=False)   # "April 2026", "Q1 FY2026-27"
    period_start = Column(Date, nullable=False, index=True)
    period_end   = Column(Date, nullable=False)
    is_closed    = Column(Boolean, default=False, nullable=False)  # locked after reconciliation
    closed_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society  = relationship("Society")
    closer   = relationship("User", foreign_keys=[closed_by])
    cycles   = relationship("BillingCycle", back_populates="period", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FinancialPeriod {self.name}>"


# ── MaintenanceChargeConfig ───────────────────────────────────────────────────

class MaintenanceChargeConfig(Base, TimestampMixin):
    """
    Configurable charge types per society.
    Used as the master charge catalogue when generating bills.
    """
    __tablename__ = "maintenance_charge_configs"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_type   = Column(Enum(ChargeType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    name          = Column(String(150), nullable=False)
    description   = Column(Text, nullable=True)
    default_amount = Column(Numeric(10, 2), nullable=True)      # per flat per cycle
    is_per_sqft   = Column(Boolean, default=False, nullable=False)   # amount × area_sqft
    is_mandatory  = Column(Boolean, default=True, nullable=False)
    applicable_flat_types = Column(String(255), nullable=True)   # CSV of FlatType values
    tax_percent   = Column(Numeric(5, 2), default=0, nullable=False)
    effective_from = Column(Date, nullable=True)
    effective_to  = Column(Date, nullable=True)

    society      = relationship("Society")

    def __repr__(self):
        return f"<ChargeConfig {self.name} ₹{self.default_amount}>"


# ── BillingCycle ──────────────────────────────────────────────────────────────

class BillingCycle(Base, TimestampMixin):
    """
    A billing run for a society covering a specific period.
    Generates one MaintenanceBill per flat.
    """
    __tablename__ = "billing_cycles"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_id     = Column(UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name          = Column(String(150), nullable=False)      # "May 2026 Maintenance"
    cycle_start   = Column(Date, nullable=False)
    cycle_end     = Column(Date, nullable=False)
    due_date      = Column(Date, nullable=False, index=True)
    frequency     = Column(Enum(CycleFrequency, values_callable=lambda e: [x.value for x in e]), default=CycleFrequency.MONTHLY, nullable=False)
    is_finalized  = Column(Boolean, default=False, nullable=False)  # locked after bills generated
    total_flats_billed = Column(Integer, default=0, nullable=False)
    total_amount_generated = Column(Numeric(14, 2), default=0, nullable=False)
    total_collected = Column(Numeric(14, 2), default=0, nullable=False)
    notes         = Column(Text, nullable=True)

    society  = relationship("Society")
    period   = relationship("FinancialPeriod", back_populates="cycles")
    creator  = relationship("User", foreign_keys=[created_by])
    bills    = relationship("MaintenanceBill", back_populates="cycle", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BillingCycle {self.name}>"


# ── MaintenanceBill ───────────────────────────────────────────────────────────

class MaintenanceBill(Base, TimestampMixin):
    """Per-flat invoice for a billing cycle."""
    __tablename__ = "maintenance_bills"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id      = Column(UUID(as_uuid=True), ForeignKey("billing_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id       = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=False, index=True)
    resident_id   = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    invoice_number  = Column(String(30), nullable=False, unique=True, index=True)
    bill_status     = Column(Enum(BillStatus, values_callable=lambda e: [x.value for x in e]), default=BillStatus.DRAFT, nullable=False, index=True)
    bill_date       = Column(Date, nullable=False)
    due_date        = Column(Date, nullable=False, index=True)

    # Amounts
    subtotal        = Column(Numeric(12, 2), default=0, nullable=False)
    tax_amount      = Column(Numeric(10, 2), default=0, nullable=False)
    penalty_amount  = Column(Numeric(10, 2), default=0, nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0, nullable=False)
    total_amount    = Column(Numeric(12, 2), default=0, nullable=False)
    paid_amount     = Column(Numeric(12, 2), default=0, nullable=False)
    outstanding     = Column(Numeric(12, 2), default=0, nullable=False)

    # Tracking
    issued_at       = Column(DateTime, nullable=True)
    paid_at         = Column(DateTime, nullable=True)
    cancelled_at    = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    remarks         = Column(Text, nullable=True)

    society    = relationship("Society")
    cycle      = relationship("BillingCycle", back_populates="bills")
    flat       = relationship("Flat")
    resident   = relationship("Resident", foreign_keys=[resident_id])
    generator  = relationship("User", foreign_keys=[generated_by])
    line_items = relationship("InvoiceLineItem", back_populates="bill", cascade="all, delete-orphan")
    receipts   = relationship("PaymentReceipt",  back_populates="bill", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MaintenanceBill {self.invoice_number} [{self.bill_status}] ₹{self.total_amount}>"


# ── InvoiceLineItem ───────────────────────────────────────────────────────────

class InvoiceLineItem(Base, TimestampMixin):
    __tablename__ = "invoice_line_items"

    bill_id     = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_type = Column(Enum(ChargeType, values_callable=lambda e: [x.value for x in e]), nullable=False)
    description = Column(String(255), nullable=False)
    quantity    = Column(Float, default=1.0, nullable=False)
    unit_rate   = Column(Numeric(10, 2), nullable=False)
    amount      = Column(Numeric(12, 2), nullable=False)
    tax_percent = Column(Numeric(5, 2), default=0, nullable=False)
    tax_amount  = Column(Numeric(10, 2), default=0, nullable=False)
    total       = Column(Numeric(12, 2), nullable=False)

    bill = relationship("MaintenanceBill", back_populates="line_items")


# ── PaymentReceipt ────────────────────────────────────────────────────────────

class PaymentReceipt(Base, TimestampMixin):
    """Immutable payment record — append-only, never modified after creation."""
    __tablename__ = "payment_receipts"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id         = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id         = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    received_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    receipt_number  = Column(String(30), nullable=False, unique=True, index=True)
    payment_date    = Column(Date, nullable=False, index=True)
    amount          = Column(Numeric(12, 2), nullable=False)
    payment_mode    = Column(Enum(PaymentMode, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    transaction_ref = Column(String(100), nullable=True, index=True)  # UPI/bank ref
    cheque_number   = Column(String(50), nullable=True)
    bank_name       = Column(String(100), nullable=True)
    notes           = Column(Text, nullable=True)
    is_advance      = Column(Boolean, default=False, nullable=False)  # advance payment
    is_reversed     = Column(Boolean, default=False, nullable=False)  # bounced cheque etc.
    reversed_reason = Column(Text, nullable=True)

    society   = relationship("Society")
    bill      = relationship("MaintenanceBill", back_populates="receipts")
    flat      = relationship("Flat")
    receiver  = relationship("User", foreign_keys=[received_by])

    def __repr__(self):
        return f"<PaymentReceipt {self.receipt_number} ₹{self.amount} [{self.payment_mode}]>"


# ── DueTracker ────────────────────────────────────────────────────────────────

class DueTracker(Base, TimestampMixin):
    """
    Rolling balance per flat — updated on every bill or payment.
    Single source of truth for outstanding dues.
    """
    __tablename__ = "due_trackers"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id          = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    total_billed     = Column(Numeric(14, 2), default=0, nullable=False)
    total_paid       = Column(Numeric(14, 2), default=0, nullable=False)
    total_penalty    = Column(Numeric(10, 2), default=0, nullable=False)
    total_discount   = Column(Numeric(10, 2), default=0, nullable=False)
    outstanding      = Column(Numeric(14, 2), default=0, nullable=False)  # computed: billed - paid - discount + penalty
    advance_balance  = Column(Numeric(10, 2), default=0, nullable=False)
    last_payment_date = Column(Date, nullable=True)
    last_bill_date   = Column(Date, nullable=True)
    overdue_months   = Column(Integer, default=0, nullable=False)   # for reporting
    last_updated_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society = relationship("Society")
    flat    = relationship("Flat")
    updater = relationship("User", foreign_keys=[last_updated_by])

    def __repr__(self):
        return f"<DueTracker flat={self.flat_id} outstanding=₹{self.outstanding}>"


# ── PenaltyRule ───────────────────────────────────────────────────────────────

class PenaltyRule(Base, TimestampMixin):
    """
    Configurable late payment penalty rules per society.
    Applied by billing engine when due_date is crossed.
    """
    __tablename__ = "penalty_rules"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name             = Column(String(100), nullable=False)
    calc_type        = Column(Enum(PenaltyCalculationType, values_callable=lambda e: [x.value for x in e]), default=PenaltyCalculationType.PERCENTAGE, nullable=False)
    rate             = Column(Numeric(8, 4), nullable=False)   # % or flat amount
    grace_period_days = Column(Integer, default=10, nullable=False)
    max_penalty_pct  = Column(Numeric(5, 2), nullable=True)    # cap at X% of bill amount
    applies_to_charge_types = Column(String(255), nullable=True)  # CSV of ChargeType values, null=all
    is_active        = Column(Boolean, default=True, nullable=False)

    society = relationship("Society")

    def __repr__(self):
        return f"<PenaltyRule {self.name} [{self.calc_type}] {self.rate}>"
