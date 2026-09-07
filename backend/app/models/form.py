from sqlalchemy import Column, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Form(Base, TimestampMixin):
    """
    A top-level navigable screen (e.g. "Residents", "Staff", "Permission
    Matrix"). Roles are granted visibility into a form via RoleForm; the
    mobile app fetches the current user's granted form codes on login and
    only renders navigation for those, instead of hardcoding role checks.
    """
    __tablename__ = "forms"

    code        = Column(String(50), nullable=False, unique=True, index=True)
    name        = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    role_forms = relationship(
        "RoleForm", back_populates="form", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Form id={self.id} code={self.code!r}>"


class RoleForm(Base, TimestampMixin):
    """Join table granting a Form to a Role (many-to-many)."""
    __tablename__ = "role_forms"
    __table_args__ = (
        UniqueConstraint("role_id", "form_id", name="uq_role_form"),
    )

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False, index=True)

    role = relationship("Role", back_populates="role_forms")
    form = relationship("Form", back_populates="role_forms")

    def __repr__(self):
        return f"<RoleForm role={self.role_id} form={self.form_id}>"
