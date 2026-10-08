"""Entity/subledger service for society accounting.

The service creates stable accounting identities for operational parties and
maps them to existing GL control accounts. It does not create a new GL
account per resident/vendor.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.modules.accounts.models.accounts import Account
from app.modules.accounts.models.entities import Entity, EntityAccount
from app.modules.vendor.models.vendor import Vendor


class AccountingEntityService:
    MEMBER_PREFIX = "10"
    VENDOR_PREFIX = "20"
    ADVANCE_PREFIX = "30"

    def __init__(self, db: Session):
        self.db = db

    def _entity(self, society_id: UUID, entity_type: str, source_id: UUID) -> Optional[Entity]:
        return self.db.query(Entity).filter(
            Entity.society_id == society_id,
            Entity.entity_type == entity_type,
            Entity.source_id == source_id,
            Entity.is_active.is_(True),
        ).first()

    def ensure_flat_member(self, flat: Flat, control_account: Account) -> EntityAccount:
        society_id = flat.wing.society_id
        entity = self._entity(society_id, "member", flat.id)
        if entity is None:
            entity = Entity(
                society_id=society_id,
                entity_type="member",
                entity_code=f"FLAT-{flat.id}",
                display_name=flat.flat_number,
                source_type="flat",
                source_id=flat.id,
                is_system=True,
            )
            self.db.add(entity)
            self.db.flush()

        existing = self.db.query(EntityAccount).filter(
            EntityAccount.entity_id == entity.id,
            EntityAccount.subledger_type == "AR",
            EntityAccount.is_active.is_(True),
        ).first()
        if existing:
            return existing

        number = self._next_number(society_id, self.MEMBER_PREFIX)
        account = EntityAccount(
            society_id=society_id,
            entity_id=entity.id,
            control_account_id=control_account.id,
            subledger_type="AR",
            account_number=number,
            is_primary=True,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def ensure_flat_advance(self, flat: Flat, control_account: Account) -> EntityAccount:
        """Ensure the member has a formal advance-credit subledger."""
        society_id = flat.wing.society_id
        entity = self._entity(society_id, "member", flat.id)
        if entity is None:
            entity = Entity(
                society_id=society_id, entity_type="member",
                entity_code=f"FLAT-{flat.id}", display_name=flat.flat_number,
                source_type="flat", source_id=flat.id, is_system=True,
            )
            self.db.add(entity)
            self.db.flush()
        existing = self.db.query(EntityAccount).filter(
            EntityAccount.entity_id == entity.id,
            EntityAccount.subledger_type == "ADVANCE",
            EntityAccount.is_active.is_(True),
        ).first()
        if existing:
            return existing
        account = EntityAccount(
            society_id=society_id, entity_id=entity.id,
            control_account_id=control_account.id, subledger_type="ADVANCE",
            account_number=self._next_number(society_id, self.ADVANCE_PREFIX),
            is_primary=True,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def ensure_vendor(self, vendor: Vendor, control_account: Account) -> EntityAccount:
        society_id = vendor.society_id
        entity = self._entity(society_id, "vendor", vendor.id)
        if entity is None:
            entity = Entity(
                society_id=society_id,
                entity_type="vendor",
                entity_code=f"VENDOR-{vendor.id}",
                display_name=vendor.company_name,
                source_type="vendor",
                source_id=vendor.id,
                is_system=True,
            )
            self.db.add(entity)
            self.db.flush()

        existing = self.db.query(EntityAccount).filter(
            EntityAccount.entity_id == entity.id,
            EntityAccount.subledger_type == "AP",
            EntityAccount.is_active.is_(True),
        ).first()
        if existing:
            return existing

        number = self._next_number(society_id, self.VENDOR_PREFIX)
        account = EntityAccount(
            society_id=society_id,
            entity_id=entity.id,
            control_account_id=control_account.id,
            subledger_type="AP",
            account_number=number,
            is_primary=True,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def _next_number(self, society_id: UUID, prefix: str) -> str:
        """Allocate a human-readable subledger number.

        The unique database constraint is the final guard. The service keeps
        numbering separate by party type so member AR and vendor AP cannot
        collide.
        """
        pattern = f"{prefix}%"
        rows = self.db.query(EntityAccount.account_number).filter(
            EntityAccount.society_id == society_id,
            EntityAccount.account_number.like(pattern),
        ).all()
        highest = 0
        for (value,) in rows:
            try:
                highest = max(highest, int(value))
            except (TypeError, ValueError):
                continue
        return str(max(highest + 1, int(prefix + "000001")))
