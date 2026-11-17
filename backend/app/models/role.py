from sqlalchemy import Column, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    """A role. The standard roles (Society Admin, Manager, Resident...) belong to the platform and are shared by every
    society (`society_id` empty). A society can add roles of its own, which only that society sees and can give out
    (`society_id` set); what they may do is granted in the Permission Matrix and the Forms Matrix, as for any role."""
    __tablename__ = "roles"

    name        = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=True, index=True)

    # A standard role's name is unique across the platform; a society's own roles are unique within the society.
    __table_args__ = (
        Index("uq_roles_system_name", "name", unique=True,
              postgresql_where=text("society_id IS NULL"), sqlite_where=text("society_id IS NULL")),
        Index("uq_roles_society_name", "society_id", "name", unique=True,
              postgresql_where=text("society_id IS NOT NULL"), sqlite_where=text("society_id IS NOT NULL")),
    )

    # Relationships
    user_roles       = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    role_forms       = relationship("RoleForm", back_populates="role", cascade="all, delete-orphan")

    @property
    def is_custom(self) -> bool:
        return self.society_id is not None

    def __repr__(self):
        return f"<Role id={self.id} name={self.name!r}>"
