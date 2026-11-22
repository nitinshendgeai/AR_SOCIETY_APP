from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class TenantFamilyMember(Base, TimestampMixin):
    """A person who lives with a tenant. Kept apart from residents so a rented flat's tenant family never mixes with
    the owner's family; removed members stay (is_active=False) and drop off every list."""
    __tablename__ = "tenant_family_members"

    tenant_id     = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name     = Column(String(255), nullable=False)
    relation      = Column(String(50), nullable=True)        # spouse, child, parent, sibling, other
    phone         = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)

    tenant = relationship("Tenant")
