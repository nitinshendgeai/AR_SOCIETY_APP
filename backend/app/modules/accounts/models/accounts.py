"""
Society accounts — double-entry books of a co-operative housing society.

- AccountGroup: the heads of the Balance Sheet and the Income & Expenditure
  account (Funds, Current Liabilities, Fixed Assets, Cash & Bank Balances,
  Income from Members, Repairs & Maintenance…). `nature` decides which
  statement a group belongs to and which side its balance normally sits on.
- Account: a ledger under a group (Sinking Fund, Members' Dues, Bank
  Account, Service Charges, Security Charges…). System ledgers carry a
  `system_key` the automatic postings look them up by.
- Voucher: one transaction — Receipt, Payment, Journal, Contra, Member Bill
  or Purchase — numbered per type and financial year ("RV/2026-27/0001").
  Vouchers posted automatically from maintenance bills, receipts and vendor
  bills name their source; cancelling one strikes it out of the books.
- VoucherEntry: one debit or credit line. Lines on Members' Dues carry the
  flat (the member's sub-ledger); lines on Sundry Creditors the vendor.

Every voucher balances: total debits == total credits.

- FinancialYearClosing: a financial year whose books are closed. Closing
  posts a Year-end Closing voucher dated 31 March that transfers every
  income and expenditure ledger to the Income & Expenditure Account (and the
  Reserve Fund share of the surplus), then locks the year: no voucher can be
  entered or cancelled in it. A bill or payment cancelled after its year is
  closed is reversed in the open year instead (Voucher.reversal_of_id).
- VoucherRevision: a voucher as it stood before an edit. A voucher the
  society entered can be corrected while its year is open; the earlier
  version is kept, with who changed it, when and why.
"""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

# Group natures. Assets and expenses normally carry debit balances,
# liabilities (funds included) and income credit balances.
NATURES = ("asset", "liability", "income", "expense")
DEBIT_NATURES = ("asset", "expense")

# Voucher types: the four a user enters, and the two the app posts itself.
VOUCHER_TYPES = {
    "receipt":  ("RV", "Receipt"),
    "payment":  ("PV", "Payment"),
    "journal":  ("JV", "Journal"),
    "contra":   ("CV", "Contra"),
    "bill":     ("BV", "Member Bill"),
    "purchase": ("PU", "Purchase"),
    "closing":  ("YC", "Year-end Closing"),
}
MANUAL_VOUCHER_TYPES = ("receipt", "payment", "journal", "contra")


class AccountGroup(Base, TimestampMixin):
    __tablename__ = "account_groups"
    __table_args__ = (UniqueConstraint("society_id", "name", name="uq_account_groups_society_name"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String(120), nullable=False)
    nature     = Column(String(20), nullable=False)          # asset | liability | income | expense
    system_key = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_system  = Column(Boolean, default=False, nullable=False)

    accounts = relationship("Account", back_populates="group", order_by="Account.sort_order")

    def __repr__(self):
        return f"<AccountGroup {self.name}>"


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("society_id", "name", name="uq_accounts_society_name"),)

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id    = Column(UUID(as_uuid=True), ForeignKey("account_groups.id", ondelete="RESTRICT"), nullable=False, index=True)
    code        = Column(String(20), nullable=True)
    name        = Column(String(150), nullable=False)
    system_key  = Column(String(50), nullable=True, index=True)
    description = Column(Text, nullable=True)
    sort_order  = Column(Integer, default=0, nullable=False)
    is_system   = Column(Boolean, default=False, nullable=False)

    # Balance brought forward when the society starts keeping books here.
    opening_balance = Column(Numeric(14, 2), default=0, nullable=False)
    opening_type    = Column(String(2), default="dr", nullable=False)   # dr | cr

    # Cash and bank ledgers — what Receipt, Payment and Contra vouchers move.
    is_cash             = Column(Boolean, default=False, nullable=False)
    is_bank             = Column(Boolean, default=False, nullable=False)
    is_default_bank     = Column(Boolean, default=False, nullable=False)
    bank_name           = Column(String(100), nullable=True)
    bank_account_number = Column(String(40), nullable=True)
    bank_ifsc           = Column(String(20), nullable=True)
    bank_branch         = Column(String(100), nullable=True)

    # An expense ledger can count towards a maintenance element (security,
    # lift …): what is spent on it is that element's actual cost, which the
    # monthly maintenance calculation can be budgeted from.
    maintenance_element_id = Column(UUID(as_uuid=True), ForeignKey("maintenance_elements.id", ondelete="SET NULL"),
                                    nullable=True, index=True)

    group = relationship("AccountGroup", back_populates="accounts")
    maintenance_element = relationship("MaintenanceElement")

    @property
    def maintenance_element_name(self):
        return self.maintenance_element.name if self.maintenance_element else None

    @property
    def is_cash_or_bank(self) -> bool:
        return bool(self.is_cash or self.is_bank)

    def __repr__(self):
        return f"<Account {self.name}>"


class Voucher(Base, TimestampMixin):
    __tablename__ = "vouchers"
    __table_args__ = (UniqueConstraint("society_id", "voucher_number", name="uq_vouchers_society_number"),)

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_type   = Column(String(20), nullable=False, index=True)
    voucher_number = Column(String(40), nullable=False)
    voucher_date   = Column(Date, nullable=False, index=True)
    fiscal_year    = Column(String(7), nullable=False, index=True)    # "2026-27"
    amount         = Column(Numeric(14, 2), nullable=False)
    narration      = Column(Text, nullable=True)
    reference      = Column(String(100), nullable=True)

    # Set on vouchers the app posts itself: maintenance_bill, payment_receipt,
    # online_payment, vendor_invoice, vendor_payment.
    source_type = Column(String(40), nullable=True, index=True)
    source_id   = Column(UUID(as_uuid=True), nullable=True, index=True)

    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_cancelled  = Column(Boolean, default=False, nullable=False, index=True)
    cancelled_at  = Column(DateTime, nullable=True)
    cancelled_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancel_reason = Column(Text, nullable=True)

    # A voucher of a closed year can't be cancelled; it is reversed by a
    # voucher in the open year, which points back at it.
    reversal_of_id = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True)
    reversed_at    = Column(DateTime, nullable=True)

    # Last correction; the earlier versions are in VoucherRevision.
    edited_at = Column(DateTime, nullable=True)
    edited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    entries = relationship("VoucherEntry", back_populates="voucher", cascade="all, delete-orphan",
                           order_by="VoucherEntry.line_no")
    creator = relationship("User", foreign_keys=[created_by])
    editor  = relationship("User", foreign_keys=[edited_by])
    revisions = relationship("VoucherRevision", back_populates="voucher", cascade="all, delete-orphan",
                             order_by="VoucherRevision.revision_no")

    def __repr__(self):
        return f"<Voucher {self.voucher_number} ₹{self.amount}>"


class VoucherEntry(Base, TimestampMixin):
    __tablename__ = "voucher_entries"

    voucher_id = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    line_no    = Column(Integer, default=0, nullable=False)
    debit      = Column(Numeric(14, 2), default=0, nullable=False)
    credit     = Column(Numeric(14, 2), default=0, nullable=False)
    flat_id    = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id  = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    narration  = Column(Text, nullable=True)

    voucher = relationship("Voucher", back_populates="entries")
    account = relationship("Account")
    flat    = relationship("Flat")
    vendor  = relationship("Vendor")


class VoucherRevision(Base, TimestampMixin):
    """A voucher as it stood before edit number `revision_no`: date,
    number, amount, narration, reference and its lines (ledger names
    included, so the record reads the same if a ledger is renamed)."""
    __tablename__ = "voucher_revisions"

    voucher_id  = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    snapshot    = Column(JSON, nullable=False)
    reason      = Column(Text, nullable=False)
    edited_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    voucher = relationship("Voucher", back_populates="revisions")
    editor  = relationship("User", foreign_keys=[edited_by])


class FinancialYearClosing(Base, TimestampMixin):
    """A financial year (1 April – 31 March) whose books are closed. Closed
    while `reopened_at` is unset; reopening keeps the row for the record."""
    __tablename__ = "account_year_closings"

    society_id         = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    fiscal_year        = Column(String(7), nullable=False, index=True)       # "2025-26"
    year_start         = Column(Date, nullable=False)
    year_end           = Column(Date, nullable=False)
    total_income       = Column(Numeric(14, 2), default=0, nullable=False)
    total_expenditure  = Column(Numeric(14, 2), default=0, nullable=False)
    surplus            = Column(Numeric(14, 2), default=0, nullable=False)   # negative: deficit
    reserve_pct        = Column(Numeric(5, 2), default=0, nullable=False)
    reserve_transfer   = Column(Numeric(14, 2), default=0, nullable=False)
    closing_voucher_id = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True)
    notes              = Column(Text, nullable=True)
    closed_at          = Column(DateTime, nullable=False)
    closed_by          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopened_at        = Column(DateTime, nullable=True)
    reopened_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopen_reason      = Column(Text, nullable=True)

    closing_voucher = relationship("Voucher", foreign_keys=[closing_voucher_id])
    closer          = relationship("User", foreign_keys=[closed_by])
    reopener        = relationship("User", foreign_keys=[reopened_by])

    @property
    def is_closed(self) -> bool:
        return self.reopened_at is None
