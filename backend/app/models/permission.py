from sqlalchemy import Column, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Permission(Base, TimestampMixin):
    """
    A named access tier (e.g. "admin_committee", "any_staff") that mirrors
    one of the guard functions in app.core.dependencies. Roles are granted
    permissions via RolePermission; a guard passes if the current user holds
    any role carrying that permission's code.
    """
    __tablename__ = "permissions"

    code        = Column(String(50), nullable=False, unique=True, index=True)
    name        = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    role_permissions = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Permission id={self.id} code={self.code!r}>"


class RolePermission(Base, TimestampMixin):
    """Join table granting a Permission to a Role (many-to-many)."""
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    role_id       = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    role       = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    def __repr__(self):
        return f"<RolePermission role={self.role_id} permission={self.permission_id}>"
