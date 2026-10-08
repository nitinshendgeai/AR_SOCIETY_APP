"""Configurable GST/TDS master data used by vendor AP tax calculation.

Tax rates and applicability are data, not hard-coded law. A society can configure
its applicable GST/TDS rules and keep effective dates for auditability.
"""
from sqlalchemy import Boolean, Column, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from app.db.base import Base, TimestampMixin

TAX_TYPES = ("GST", "TDS")
GST_COMPONENTS = ("CGST_SGST", "IGST", "NONE")
TDS_BASES = ("taxable_amount", "gross_amount")


class TaxConfiguration(Base, TimestampMixin):
    __tablename__ = "accounting_tax_configurations"
    __table_args__ = (
        UniqueConstraint("society_id", "code", name="uq_tax_config_society_code"),
    )

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(40), nullable=False)
    name = Column(String(150), nullable=False)
    tax_type = Column(String(10), nullable=False, index=True)
    rate = Column(Numeric(7, 4), nullable=False)
    component = Column(String(20), nullable=True)
    section_code = Column(String(30), nullable=True)
    base_type = Column(String(30), nullable=True)
    threshold_amount = Column(Numeric(14, 2), nullable=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    ledger_system_key = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    society = __import__("sqlalchemy").orm.relationship("Society")
