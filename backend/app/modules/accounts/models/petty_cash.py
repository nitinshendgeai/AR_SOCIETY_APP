"""Petty cash: the society's float and the cash counts made against it.

The money itself lives in the books (the Petty Cash ledger, a cash ledger). This only keeps what the books cannot:
how big the float should be, the most one petty expense may be, who holds the cash, and the physical cash counts.
"""
from sqlalchemy import Column, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class PettyCashSetting(Base, TimestampMixin):
    __tablename__ = "petty_cash_settings"
    __table_args__ = (UniqueConstraint("society_id", name="uq_petty_cash_settings_society"),)

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    float_amount   = Column(Numeric(12, 2), nullable=True)      # the level the cash is topped back up to
    expense_limit  = Column(Numeric(12, 2), nullable=True)      # the most one petty expense may be
    custodian_name = Column(String(150), nullable=True)         # who holds the cash


class PettyCashCount(Base, TimestampMixin):
    """The cash actually counted in the box on a day, against what the books say should be there."""
    __tablename__ = "petty_cash_counts"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    count_date      = Column(Date, nullable=False, index=True)
    counted_amount  = Column(Numeric(12, 2), nullable=False)
    book_balance    = Column(Numeric(12, 2), nullable=False)    # what the books said at the time
    note            = Column(Text, nullable=True)
    counted_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    counter = relationship("User", foreign_keys=[counted_by])

    @property
    def difference(self):
        return self.counted_amount - self.book_balance
