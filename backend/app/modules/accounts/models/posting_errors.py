"""Accounting posting exception queue and voucher approval metadata.

Posting failures are operationally recoverable, but they must never be silent.
The queue records each failed source and the latest retry state so the Accounts
screen can reconcile operational transactions with the general ledger.

Voucher approval metadata keeps manual Payment/Journal vouchers out of live
balances until an authorised committee/admin user approves them.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


POSTING_ERROR_STATUSES = ("OPEN", "RETRYING", "RESOLVED", "IGNORED")


class AccountingPostingError(Base, TimestampMixin):
    __tablename__ = "accounting_posting_errors"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "source_type", "source_id", "operation",
            name="uq_accounting_posting_error_source",
        ),
    )

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    operation = Column(String(50), nullable=False)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=False)
    first_failed_at = Column(DateTime, nullable=False)
    last_failed_at = Column(DateTime, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="OPEN", nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    last_voucher_id = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True)

    society = relationship("Society")
    resolver = relationship("User", foreign_keys=[resolved_by])
    voucher = relationship("Voucher", foreign_keys=[last_voucher_id])
