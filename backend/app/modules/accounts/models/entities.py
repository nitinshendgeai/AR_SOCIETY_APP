"""Accounting entities and subledger accounts.

An Entity is the accounting identity behind a business party (member/flat,
vendor, supplier, customer, etc.). EntityAccount maps that party to an
existing control ledger such as Members' Dues or Sundry Creditors without
creating hundreds of GL accounts.

This deliberately separates:
  Flat.virtual_account_number -> bank/payment identifier
  EntityAccount.account_number -> society accounting subledger identifier
  Account -> general-ledger control account
"""
from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


ENTITY_TYPES = (
    "member",
    "resident",
    "tenant",
    "vendor",
    "supplier",
    "customer",
    "staff",
    "other",
)

SUBLEDGER_TYPES = (
    "AR",       # member/customer receivables
    "AP",       # vendor/supplier payables
    "VL",       # vendor ledger
    "CL",       # customer ledger
    "GST",      # tax subledger
    "BL",       # bank-linked operational ledger
    "ADVANCE",  # advances received/paid
)


class Entity(Base, TimestampMixin):
    __tablename__ = "accounting_entities"
    __table_args__ = (
        UniqueConstraint("society_id", "entity_type", "source_id",
                         name="uq_accounting_entity_source"),
        UniqueConstraint("society_id", "entity_code",
                         name="uq_accounting_entity_code"),
    )

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    entity_type = Column(String(20), nullable=False, index=True)
    entity_code = Column(String(40), nullable=False)
    display_name = Column(String(255), nullable=False)
    source_type = Column(String(40), nullable=True)
    source_id   = Column(UUID(as_uuid=True), nullable=True, index=True)
    is_system   = Column(Boolean, default=False, nullable=False)

    accounts = relationship("EntityAccount", back_populates="entity",
                            cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Entity {self.entity_code} {self.display_name}>"


class EntityAccount(Base, TimestampMixin):
    __tablename__ = "entity_accounts"
    __table_args__ = (
        UniqueConstraint("society_id", "account_number",
                         name="uq_entity_account_number"),
        UniqueConstraint("entity_id", "subledger_type",
                         name="uq_entity_account_subledger"),
    )

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    entity_id      = Column(UUID(as_uuid=True), ForeignKey("accounting_entities.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    control_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"),
                                 nullable=False, index=True)
    subledger_type = Column(String(20), nullable=False, index=True)
    account_number = Column(String(30), nullable=False)
    is_primary     = Column(Boolean, default=False, nullable=False)

    entity = relationship("Entity", back_populates="accounts")
    control_account = relationship("Account")

    def __repr__(self):
        return f"<EntityAccount {self.account_number} {self.subledger_type}>"
