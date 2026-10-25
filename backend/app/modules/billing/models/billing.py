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
- PaymentAllocation: how much of a recorded payment settled which bill
"""
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Date, Enum, ForeignKey, Numeric, LargeBinary, UniqueConstraint
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


class ChargeBasis(str, enum.Enum):
    """How a charge head turns into a per-flat amount. `default_amount`
    on the charge means a different thing for each basis (see
    MaintenanceCalculator):

    FIXED                  ₹ per flat per month (service charges, lift, common
                           electricity — shared equally per bye-law 67)
    PER_SQFT               ₹ per sq ft of flat area per month
    CONSTRUCTION_COST_PCT  % per annum of the flat's construction cost (area ×
                           society construction cost/sq ft) — sinking fund
                           0.25%, repair & maintenance fund 0.75%
    BUDGET_EQUAL           annual budget ₹, split equally across flats
    BUDGET_AREA            annual budget ₹, split in proportion to flat area
    PARKING                ₹ per allotted parking slot per month (an
                           allocation's own monthly_charge overrides it)
    """
    FIXED                 = "fixed"
    PER_SQFT              = "per_sqft"
    CONSTRUCTION_COST_PCT = "construction_cost_pct"
    BUDGET_EQUAL          = "budget_equal"
    BUDGET_AREA           = "budget_area"
    PARKING               = "parking"


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


class ReconciliationStatus(str, enum.Enum):
    PENDING          = "pending"    # just submitted, not yet checked against the bank statement
    RECONCILED       = "reconciled" # confirmed against the bank statement
    REJECTED         = "rejected"   # screenshot didn't match / invalid, e.g. duplicate or wrong society


class BankStatementMatchStatus(str, enum.Enum):
    UNMATCHED = "unmatched"  # imported, no confirmed link to a payment submission yet
    MATCHED   = "matched"    # linked to an OnlinePaymentSubmission, which is now RECONCILED
    IGNORED   = "ignored"    # not a resident payment (bank interest, charges, unrelated transfer)


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
    closed_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    society  = relationship("Society")
    closer   = relationship("User", foreign_keys=[closed_by])
    cycles   = relationship("BillingCycle", back_populates="period", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FinancialPeriod {self.name}>"


# ── MaintenanceElement ────────────────────────────────────────────────────────

class MaintenanceElement(Base, TimestampMixin):
    """
    A society's master list of maintenance elements — the kinds of charge
    it can levy (service charges, sinking fund, property tax, lift, …) with
    the default way each is calculated. Seeded with the standard bye-law
    elements on first use (see standard_elements.py) and fully editable
    afterwards; charge heads are created from these.
    """
    __tablename__ = "maintenance_elements"
    __table_args__ = (UniqueConstraint("society_id", "code", name="uq_maintenance_element_code"),)

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    code              = Column(String(50), nullable=False)          # stable slug, unique per society
    name              = Column(String(150), nullable=False)
    description       = Column(Text, nullable=True)
    bye_law_ref       = Column(String(150), nullable=True)
    category          = Column(Enum(ChargeType, values_callable=lambda e: [x.value for x in e]),
                               default=ChargeType.OTHER, nullable=False)
    default_basis     = Column(Enum(ChargeBasis, values_callable=lambda e: [x.value for x in e]),
                               default=ChargeBasis.FIXED, nullable=False)
    default_amount    = Column(Numeric(12, 2), nullable=True)
    is_service_charge = Column(Boolean, default=False, nullable=False)
    gst_applicable    = Column(Boolean, default=True, nullable=False)
    sort_order        = Column(Integer, default=100, nullable=False)
    is_system         = Column(Boolean, default=False, nullable=False)  # seeded standard element

    society = relationship("Society")

    def __repr__(self):
        return f"<MaintenanceElement {self.code}>"


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
    basis         = Column(Enum(ChargeBasis, values_callable=lambda e: [x.value for x in e]),
                           default=ChargeBasis.FIXED, nullable=False)
    is_service_charge = Column(Boolean, default=False, nullable=False)  # base for non-occupancy charges
    gst_applicable    = Column(Boolean, default=True, nullable=False)
    is_mandatory  = Column(Boolean, default=True, nullable=False)
    applicable_flat_types = Column(String(255), nullable=True)   # CSV of FlatType values
    tax_percent   = Column(Numeric(5, 2), default=0, nullable=False)
    effective_from = Column(Date, nullable=True)
    effective_to  = Column(Date, nullable=True)
    element_id    = Column(UUID(as_uuid=True), ForeignKey("maintenance_elements.id", ondelete="SET NULL"),
                           nullable=True, index=True)
    # Budget this head from what was actually spent on the expense ledgers linked to its
    # element (over the last `expense_months`), instead of the typed amount.
    auto_from_expenses = Column(Boolean, default=False, nullable=False)
    expense_months     = Column(Integer, default=12, nullable=False)
    # How "budget from expenses" reads the books. "trailing": the last `expense_months` months up to the day the bills
    # are made, annualised (the original behaviour). "period": the approved expenses dated inside the billing cycle's
    # own period, shared out exactly - by flat area for the per-sq-ft / area-budget bases, equally for the others -
    # and recorded as a snapshot (BillingExpenseAllocation) when the bills are generated.
    expense_mode       = Column(String(10), default="trailing", server_default="trailing", nullable=False)
    # A parking head only: ₹ a month for a slot held for a two-wheeler (motorcycle, scooter, bicycle). Empty: a
    # two-wheeler pays the head's own rate, the same as a car.
    two_wheeler_rate   = Column(Numeric(10, 2), nullable=True)

    society      = relationship("Society")
    element      = relationship("MaintenanceElement")

    def __repr__(self):
        return f"<ChargeConfig {self.name} ₹{self.default_amount}>"


# ── MaintenanceSettings ───────────────────────────────────────────────────────

class MaintenanceSettings(Base, TimestampMixin):
    """Society-wide rules the maintenance calculator applies to every bill.
    Defaults follow the Maharashtra model bye-laws as amended in 2026:
    simple interest on arrears capped at 12% p.a., non-occupancy charges
    capped at 10% of service charges, and GST at 18% only once a flat's
    monthly contribution crosses ₹7,500 (and the society is registered —
    turnover above ₹20 lakh — which is what gst_enabled records)."""
    __tablename__ = "maintenance_settings"

    society_id                 = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"),
                                        nullable=False, unique=True, index=True)
    construction_cost_per_sqft = Column(Numeric(10, 2), nullable=True)   # architect-certified, excl. land
    interest_rate_pct          = Column(Numeric(5, 2), default=12, nullable=False)   # simple, per annum
    interest_grace_days        = Column(Integer, default=0, nullable=False)
    non_occupancy_pct          = Column(Numeric(5, 2), default=0, nullable=False)    # of service charges
    gst_enabled                = Column(Boolean, default=False, nullable=False)
    gst_rate_pct               = Column(Numeric(5, 2), default=18, nullable=False)
    gst_threshold_monthly      = Column(Numeric(10, 2), default=7500, nullable=False)

    # Printed on every bill so members know where to pay (all optional).
    bank_account_name   = Column(String(150), nullable=True)
    bank_name           = Column(String(100), nullable=True)
    bank_account_number = Column(String(40), nullable=True)
    bank_ifsc           = Column(String(20), nullable=True)
    upi_id              = Column(String(100), nullable=True)
    bill_notes          = Column(Text, nullable=True)   # extra lines under the bye-law notes

    # "Billing in this app starts on": when set, each flat is billed for the days from the end of what it was last
    # billed for — or, for a flat never billed here, from its possession date (never earlier than this date) — up to
    # the end of the cycle being billed. Empty: every cycle bills its own period only, as before.
    billing_start_date  = Column(Date, nullable=True)

    # Off (the default): a payment voucher, including an expense, waits for a second admin / committee member to
    # approve it (maker and checker). On: a payment entered by someone who could approve it themselves is posted
    # as approved straight away - for a society whose treasurer is also the admin and has no one else to approve.
    auto_approve_admin_expenses = Column(Boolean, default=False, server_default="false", nullable=False)

    # On: each bill's amount is rounded to the nearest whole rupee (half a rupee up) and the difference, up to 50 paise
    # either way, is shown on the bill as "Round off" and posted to the Rounding Off ledger. Off: bills run to the paisa.
    round_to_rupee = Column(Boolean, default=False, server_default="false", nullable=False)

    society = relationship("Society")


# ── BillingCycle ──────────────────────────────────────────────────────────────

class BillingCycle(Base, TimestampMixin):
    """
    A billing run for a society covering a specific period.
    Generates one MaintenanceBill per flat.
    """
    __tablename__ = "billing_cycles"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_id     = Column(UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

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
    generated_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    invoice_number  = Column(String(30), nullable=False, index=True)
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
    # Unpaid balance of this flat's earlier bills when this one was
    # generated — shown on the bill as arrears, not added to total_amount
    # (each earlier bill still carries its own outstanding).
    previous_dues   = Column(Numeric(12, 2), default=0, nullable=False)
    # Interest on this bill's unpaid balance has been billed (on later
    # bills) up to this date, so the next bill only charges the new days.
    arrears_interest_upto = Column(Date, nullable=True)
    # How the interest on this bill was worked out, per earlier bill (JSON list), for the printed bill. Empty on bills
    # made before this existed or with no interest.
    interest_working = Column(Text, nullable=True)
    # The rounding to a whole rupee that is inside total_amount (negative: rounded down). Nothing when the society
    # does not round, or on bills made before this existed.
    round_off       = Column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    # The days this bill charges for. Normally the cycle's own period; longer for a flat billed from its possession
    # date or from its last bill (catch-up), shorter for a flat that took possession during the cycle. Empty on bills
    # made before this existed: the cycle's period then.
    period_start    = Column(Date, nullable=True)
    period_end      = Column(Date, nullable=True)

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "invoice_number", name="uq_bill_society_invoice_number"),)

    society    = relationship("Society")
    cycle      = relationship("BillingCycle", back_populates="bills")
    flat       = relationship("Flat")
    resident   = relationship("Resident", foreign_keys=[resident_id])
    generator  = relationship("User", foreign_keys=[generated_by])
    line_items = relationship("InvoiceLineItem", back_populates="bill", cascade="all, delete-orphan")
    receipts   = relationship("PaymentReceipt",  back_populates="bill", cascade="all, delete-orphan")
    online_payments = relationship("OnlinePaymentSubmission", back_populates="bill")
    allocations = relationship("PaymentAllocation", back_populates="bill")

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
    # Set on a line that shares out actual expenses: the snapshot of how the pool was worked out (see
    # BillingExpenseAllocation). Empty on every other line.
    allocation_id = Column(UUID(as_uuid=True), ForeignKey("billing_expense_allocations.id", ondelete="SET NULL"),
                           nullable=True, index=True)

    bill = relationship("MaintenanceBill", back_populates="line_items")
    allocation = relationship("BillingExpenseAllocation")


# ── PaymentReceipt ────────────────────────────────────────────────────────────

class PaymentReceipt(Base, TimestampMixin):
    """Immutable payment record — append-only, never modified after creation."""
    __tablename__ = "payment_receipts"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id         = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id         = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    received_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    receipt_number  = Column(String(30), nullable=False, index=True)
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

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "receipt_number", name="uq_receipt_society_number"),)

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
    advance_balance  = Column(Numeric(14, 2), default=0, nullable=False)
    last_payment_date = Column(Date, nullable=True)
    last_bill_date   = Column(Date, nullable=True)
    overdue_months   = Column(Integer, default=0, nullable=False)   # for reporting
    last_updated_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

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


# ── FlatCharge (fines and additional charges on one flat) ─────────────────────

class FlatChargeKind(str, enum.Enum):
    FINE   = "fine"        # a penalty: not interest-bearing, not GST
    EXTRA  = "extra"       # an additional charge for this flat only


class FlatChargeStatus(str, enum.Enum):
    ACTIVE    = "active"     # waiting to go on the next bill (one-off) / on every bill (recurring)
    BILLED    = "billed"     # a one-off charge that is on a bill
    CANCELLED = "cancelled"


class FlatCharge(Base, TimestampMixin):
    """
    A fine or additional charge on one flat, added by the committee or manager
    with a reason. The maintenance calculator puts every active one on the
    flat's next bill (preview and generation alike); a one-off is then marked
    billed against that bill — and released again if the bill is cancelled —
    while a recurring one goes on every bill from its effective date until it
    ends or is cancelled.
    """
    __tablename__ = "flat_charges"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id      = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id      = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    kind           = Column(Enum(FlatChargeKind, values_callable=lambda e: [x.value for x in e]),
                            default=FlatChargeKind.FINE, nullable=False, index=True)
    title          = Column(String(150), nullable=False)
    reason         = Column(Text, nullable=True)
    amount         = Column(Numeric(12, 2), nullable=False)
    gst_applicable = Column(Boolean, default=False, nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    recurring      = Column(Boolean, default=False, nullable=False)
    end_date       = Column(Date, nullable=True)
    status         = Column(Enum(FlatChargeStatus, values_callable=lambda e: [x.value for x in e]),
                            default=FlatChargeStatus.ACTIVE, nullable=False, index=True)
    cancelled_at   = Column(DateTime, nullable=True)
    cancel_reason  = Column(Text, nullable=True)
    # The income head an additional charge is booked to on the bill (amenities, parking...); unset: Other Charges
    # Recovered. A fine always goes to Fines & Penalties.
    charge_type    = Column(Enum(ChargeType, values_callable=lambda e: [x.value for x in e]), nullable=True)
    # What raised it (an amenity booking, a parking violation), so it can be found, and withdrawn while unbilled.
    source_type    = Column(String(40), nullable=True, index=True)
    source_id      = Column(UUID(as_uuid=True), nullable=True, index=True)

    society = relationship("Society")
    flat    = relationship("Flat")
    bill    = relationship("MaintenanceBill", foreign_keys=[bill_id])

    @property
    def flat_number(self):
        return self.flat.flat_number if self.flat else None

    @property
    def wing_name(self):
        return self.flat.wing.name if self.flat and self.flat.wing else None

    @property
    def invoice_number(self):
        return self.bill.invoice_number if self.bill else None

    def __repr__(self):
        return f"<FlatCharge {self.kind} {self.title} ₹{self.amount}>"


# ── InterestWaiver ───────────────────────────────────────────────────────────

class InterestWaiver(Base, TimestampMixin):
    """
    A concession on the interest charged on one flat's arrears: no interest at
    all (`waive`), or a lower rate than the society's (`rate`), for the days
    from `from_date` to `to_date` (open-ended when empty). The committee gives
    it with a reason; the maintenance calculator applies it when it works out
    the interest on the flat's next bill, and bills already issued are never
    changed. Where several cover the same day, the newest one wins.
    """
    __tablename__ = "interest_waivers"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id      = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    mode          = Column(String(10), nullable=False, default="waive")     # waive | rate
    rate_pct      = Column(Numeric(5, 2), nullable=True)                    # for mode "rate": the % p.a. charged instead
    from_date     = Column(Date, nullable=False)
    to_date       = Column(Date, nullable=True)
    reason        = Column(Text, nullable=False)
    status        = Column(String(10), nullable=False, default="active", index=True)   # active | cancelled
    cancelled_at  = Column(DateTime, nullable=True)
    cancel_reason = Column(Text, nullable=True)

    society = relationship("Society")
    flat    = relationship("Flat")

    @property
    def flat_number(self):
        return self.flat.flat_number if self.flat else None

    @property
    def wing_name(self):
        return self.flat.wing.name if self.flat and self.flat.wing else None

    def covers(self, day) -> bool:
        return self.from_date <= day and (self.to_date is None or day <= self.to_date)

    def __repr__(self):
        return f"<InterestWaiver {self.mode} {self.from_date}..{self.to_date}>"


# ── OnlinePaymentSubmission ──────────────────────────────────────────────────

class OnlinePaymentSubmission(Base, TimestampMixin):
    """
    The single "record a payment" entry point — an FMC Manager records
    either an ON ACCOUNT payment (`bill_id` null: log what a resident says
    they paid, e.g. a screenshot, with nothing to apply it against yet) or
    an ON BILL payment (`bill_id` set at creation: applied immediately to
    that MaintenanceBill/DueTracker via BillingService._apply_payment_to_bill,
    the same accounting logic `record_payment()`/PaymentReceipt uses).
    Either way, a receipt is issued immediately.

    Bank reconciliation is a separate, later step (see `status` below) —
    it does not gate the bill being marked paid or the receipt being
    issued. `status` starts RECONCILED for cash (nothing to check against
    a bank statement) and PENDING for every other payment mode, including
    cheque (can still bounce) and the online modes; a manager clears
    PENDING rows via update_online_payment_status().

    The screenshot is optional — required only for the online payment
    modes (UPI/bank transfer/NEFT/RTGS/online gateway) where it's the
    actual proof of payment; cash and cheque have no such artifact. When
    present it's stored inline (bytea) rather than as a file path/URL —
    the backend container's filesystem is ephemeral, so a disk-stored
    file would be lost on every redeploy.
    """
    __tablename__ = "online_payment_submissions"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    wing_id         = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="SET NULL"), nullable=True, index=True)
    flat_id         = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=False, index=True)
    bill_id         = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    receipt_number  = Column(String(30), nullable=False, index=True)
    amount          = Column(Numeric(12, 2), nullable=False)
    payment_date    = Column(Date, nullable=False, index=True)
    payment_mode    = Column(Enum(PaymentMode, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    transaction_ref = Column(String(100), nullable=True, index=True)   # UPI/UTR/bank reference
    bank_name       = Column(String(100), nullable=True)
    notes           = Column(Text, nullable=True)
    # What the resident says the payment is for. No bill exists to derive
    # this from (see class docstring), so it's captured directly and printed
    # on the receipt as "on account of <purpose>" — standard society-receipt
    # phrasing. Defaults to MAINTENANCE since that's the overwhelming case.
    purpose         = Column(Enum(ChargeType, values_callable=lambda e: [x.value for x in e]),
                              default=ChargeType.MAINTENANCE, nullable=False)

    status          = Column(Enum(ReconciliationStatus, values_callable=lambda e: [x.value for x in e]),
                              default=ReconciliationStatus.PENDING, nullable=False, index=True)
    reviewed_at     = Column(DateTime, nullable=True)
    review_notes    = Column(Text, nullable=True)

    screenshot_data      = Column(LargeBinary, nullable=True)
    screenshot_mime_type = Column(String(50), nullable=True)
    screenshot_file_name = Column(String(255), nullable=True)

    # The society's cash or bank ledger the money went into (unset: cash in hand for cash, else the default bank).
    deposit_account_id   = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    # Numbers run per society, so they are unique within one.
    __table_args__ = (UniqueConstraint("society_id", "receipt_number", name="uq_online_payment_society_receipt"),)

    society   = relationship("Society")
    deposit_account = relationship("Account", foreign_keys=[deposit_account_id])
    wing      = relationship("Wing")
    flat      = relationship("Flat")
    bill      = relationship("MaintenanceBill", back_populates="online_payments")
    recorder  = relationship("User", foreign_keys=[recorded_by])
    reviewer  = relationship("User", foreign_keys=[reviewed_by])
    allocations = relationship("PaymentAllocation", back_populates="payment",
                               order_by="PaymentAllocation.created_at")

    def __repr__(self):
        return f"<OnlinePaymentSubmission {self.receipt_number} ₹{self.amount} [{self.status}]>"


# ── PaymentAllocation ─────────────────────────────────────────────────────────

class PaymentAllocation(Base, TimestampMixin):
    """
    How much of a recorded payment (OnlinePaymentSubmission) settled which
    maintenance bill. A member's payment is set off against the flat's open
    bills, oldest first; what is left over is an advance, set off against
    the next bill when it is issued (see services/allocations.py).

    A payment that is rejected, or a bill that is cancelled, releases its
    allocations (`released_at`): the bill is unpaid again by that amount
    and the money goes back to the member's credit. Rows are kept for the
    record.
    """
    __tablename__ = "payment_allocations"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id    = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("online_payment_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id    = Column(UUID(as_uuid=True), ForeignKey("maintenance_bills.id", ondelete="CASCADE"), nullable=False, index=True)
    amount     = Column(Numeric(12, 2), nullable=False)
    allocated_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    released_at     = Column(DateTime, nullable=True)
    released_reason = Column(Text, nullable=True)

    payment = relationship("OnlinePaymentSubmission", back_populates="allocations")
    bill    = relationship("MaintenanceBill", back_populates="allocations")

    @property
    def is_live(self) -> bool:
        return self.released_at is None

    def __repr__(self):
        return f"<PaymentAllocation ₹{self.amount} bill={self.bill_id}>"


# ── BankStatementEntry ────────────────────────────────────────────────────────

class BankStatementEntry(Base, TimestampMixin):
    """
    One row (credit or debit) from an imported bank statement — the other half of
    reconciliation. OnlinePaymentSubmission is what the society *recorded*
    as received from a resident; this is what the bank *actually shows*
    credited. Matching the two closes the loop: a submission only moves
    PENDING -> RECONCILED once its money is confirmed to have landed in
    the account, via BillingService.confirm_bank_match() — never on
    import alone, which only creates UNMATCHED rows.
    """
    __tablename__ = "bank_statement_entries"

    society_id             = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    imported_by            = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_submission_id  = Column(UUID(as_uuid=True), ForeignKey("online_payment_submissions.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_by             = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    txn_date      = Column(Date, nullable=False, index=True)
    description   = Column(String(500), nullable=False)
    reference     = Column(String(100), nullable=True, index=True)   # bank's own UTR/ref, if present
    amount        = Column(Numeric(12, 2), nullable=False)
    # credit: money the bank received (a deposit); debit: money it paid out (a cheque cleared, a transfer).
    direction     = Column(String(6), default="credit", server_default="credit", nullable=False)
    # The bank ledger the statement belongs to (unset on rows imported before there were several bank accounts).
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    # The books' own line this row was matched to (see accounts/services/bank_reconciliation.py).
    matched_entry_id = Column(UUID(as_uuid=True), ForeignKey("voucher_entries.id", ondelete="SET NULL"), nullable=True, index=True)

    match_status  = Column(Enum(BankStatementMatchStatus, values_callable=lambda e: [x.value for x in e]),
                            default=BankStatementMatchStatus.UNMATCHED, nullable=False, index=True)
    matched_at    = Column(DateTime, nullable=True)
    ignore_reason = Column(Text, nullable=True)

    society            = relationship("Society")
    importer           = relationship("User", foreign_keys=[imported_by])
    matcher            = relationship("User", foreign_keys=[matched_by])
    matched_submission = relationship("OnlinePaymentSubmission")

    def __repr__(self):
        return f"<BankStatementEntry {self.txn_date} ₹{self.amount} [{self.match_status}]>"



# ── Actual-expense allocation snapshot ────────────────────────────────────────

class BillingExpenseAllocation(Base, TimestampMixin):
    """How one charge head's actual expenses for one billing cycle were shared out, written in the same transaction
    that generates the bills and never changed afterwards. It is the audit record behind every bill line that
    carries its id: the period, the pool (the approved expenses dated in the period on the ledgers linked to the
    head's element), how it was shared (by area or equally), the total of the weights it was shared over and the
    rate that gives, and the expense entries that made up the pool (BillingExpenseSource)."""
    __tablename__ = "billing_expense_allocations"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_id     = Column(UUID(as_uuid=True), ForeignKey("billing_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_id    = Column(UUID(as_uuid=True), ForeignKey("maintenance_charge_configs.id", ondelete="SET NULL"),
                          nullable=True, index=True)
    element_id   = Column(UUID(as_uuid=True), ForeignKey("maintenance_elements.id", ondelete="SET NULL"),
                          nullable=True, index=True)
    charge_name  = Column(String(150), nullable=False)            # kept as it was when the bills were made
    element_name = Column(String(150), nullable=True)
    method       = Column(String(10), nullable=False)             # "area" | "equal"
    period_start = Column(Date, nullable=False)
    period_end   = Column(Date, nullable=False)
    pool_amount  = Column(Numeric(14, 2), nullable=False)         # the expenses shared out
    allocated_amount = Column(Numeric(14, 2), nullable=False)     # what the bill lines add up to (= pool by construction)
    eligible_flats = Column(Integer, nullable=False)              # flats that carry a share
    total_weight = Column(Numeric(18, 4), nullable=False)         # sq ft x share of the cycle (area), or share of the cycle (equal)
    rate         = Column(Numeric(18, 8), nullable=False)         # pool / total_weight: Rs per sq ft (area) or per flat (equal)

    sources = relationship("BillingExpenseSource", back_populates="allocation", cascade="all, delete-orphan",
                           order_by="BillingExpenseSource.voucher_date")

    def __repr__(self):
        return f"<BillingExpenseAllocation {self.charge_name} {self.period_start}..{self.period_end} ₹{self.pool_amount}>"


class BillingExpenseSource(Base, TimestampMixin):
    """One voucher's net spend inside an allocation's pool."""
    __tablename__ = "billing_expense_sources"

    allocation_id  = Column(UUID(as_uuid=True), ForeignKey("billing_expense_allocations.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    voucher_id     = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id     = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    voucher_number = Column(String(40), nullable=False)
    voucher_date   = Column(Date, nullable=False)
    ledger_name    = Column(String(150), nullable=False)
    amount         = Column(Numeric(14, 2), nullable=False)       # debits less credits on that ledger in that voucher

    allocation = relationship("BillingExpenseAllocation", back_populates="sources")
