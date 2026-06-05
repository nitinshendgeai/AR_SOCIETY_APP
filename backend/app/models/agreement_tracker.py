"""
AgreementTracker — tracks tenant agreement lifecycle with expiry alerting readiness.
Separate from Tenant model to support multiple agreements per flat over time.
"""
import enum
from sqlalchemy import Column, String, Date, Numeric, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class AgreementStatus(str, enum.Enum):
    ACTIVE   = "active"
    EXPIRED  = "expired"
    RENEWED  = "renewed"
    TERMINATED = "terminated"


class AgreementTracker(Base, TimestampMixin):
    __tablename__ = "agreement_tracker"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id         = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id       = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    resident_id     = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True)

    agreement_number = Column(String(50), nullable=True, index=True)
    start_date      = Column(Date, nullable=False, index=True)
    end_date        = Column(Date, nullable=False, index=True)
    monthly_rent    = Column(Numeric(12, 2), nullable=True)
    security_deposit = Column(Numeric(12, 2), nullable=True)
    status          = Column(Enum(AgreementStatus, values_callable=lambda e: [x.value for x in e]), default=AgreementStatus.ACTIVE, nullable=False, index=True)
    document_url    = Column(String(500), nullable=True)
    renewal_of_id   = Column(UUID(as_uuid=True), nullable=True)   # FK to previous agreement
    termination_reason = Column(Text, nullable=True)
    alert_sent_30   = Column(Boolean, default=False)  # 30-day expiry alert sent
    alert_sent_7    = Column(Boolean, default=False)  # 7-day expiry alert sent
    created_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society  = relationship("Society")
    flat     = relationship("Flat")
    tenant   = relationship("Tenant", foreign_keys=[tenant_id])
    resident = relationship("Resident", foreign_keys=[resident_id])
    creator  = relationship("User", foreign_keys=[created_by])

    def days_to_expiry(self) -> int:
        from datetime import date
        return (self.end_date - date.today()).days

    def __repr__(self):
        return f"<AgreementTracker flat={self.flat_id} {self.start_date}→{self.end_date} [{self.status}]>"
