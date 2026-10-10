"""Requests for a certificate or NOC from the society."""
from sqlalchemy import Column, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

# kind -> (title printed on the certificate, certificate-number prefix, needs the flat's dues to be clear)
CERTIFICATE_KINDS = {
    "noc_sale": ("No Objection Certificate for sale / transfer of flat", "NOC", True),
    "noc_rent": ("No Objection Certificate for letting the flat", "NOC", True),
    "noc_loan": ("No Objection Certificate for home loan / mortgage", "NOC", True),
    "noc_renovation": ("No Objection Certificate for interior work / renovation", "NOC", False),
    "no_dues": ("No Dues Certificate", "ND", True),
    "address_proof": ("Address / residence certificate", "AP", False),
    "other": ("Certificate", "CERT", False),
}
TENANT_KINDS = ("address_proof", "other")
CERTIFICATE_STATUSES = ("pending", "approved", "rejected", "cancelled")


class CertificateRequest(Base, TimestampMixin):
    __tablename__ = "certificate_requests"
    __table_args__ = (UniqueConstraint("society_id", "certificate_no", name="uq_certificate_no"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    applicant_name = Column(String(200), nullable=False)
    kind = Column(String(20), nullable=False)
    purpose = Column(Text, nullable=True)
    party_name = Column(String(200), nullable=True)         # the buyer / tenant / bank, where there is one
    status = Column(String(12), nullable=False, default="pending", index=True)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_on = Column(Date, nullable=True)
    decision_note = Column(Text, nullable=True)
    dues_at_decision = Column(Numeric(12, 2), nullable=True)
    certificate_no = Column(String(40), nullable=True)
