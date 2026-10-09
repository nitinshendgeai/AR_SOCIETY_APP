from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List, Optional

from app.models.flat import Flat
from app.models.user import User
from app.repositories.flat_repo import FlatRepository
from app.repositories.wing_repo import WingRepository
from app.schemas.flat import FlatCreate, FlatUpdate, FlatOut
from app.core.tenant_scope import assert_society_access


def _enrich(flat: Flat) -> FlatOut:
    out = FlatOut.model_validate(flat)
    if hasattr(flat, 'wing') and flat.wing:
        out.wing_name = flat.wing.name
    return out

from app.services.meter_registry import assert_meter_free


class FlatService:
    def __init__(self, db: Session):
        self.repo      = FlatRepository(db)
        self.wing_repo = WingRepository(db)

    def create(self, data: FlatCreate, current_user: User) -> FlatOut:
        # Flat has no society_id of its own — scoping is entirely a function
        # of whether the target wing belongs to the caller's own society.
        wing = self.wing_repo.get_kept(data.wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        if not wing.is_active:
            raise HTTPException(409, f"Wing '{wing.name}' is deactivated — activate it first")
        self.repo.assert_unique_flat_number(data.wing_id, data.flat_number)
        if data.virtual_account_number:
            self.repo.assert_unique_van(wing.society_id, data.virtual_account_number)
        assert_meter_free(self.repo.db, wing.society_id, data.electric_meter_no)
        flat = Flat(**data.model_dump())
        return _enrich(self.repo.create(flat))

    def get_or_404(self, id: UUID, current_user: User) -> FlatOut:
        obj = self.repo.get(id, society_id=current_user.society_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Flat not found")
        return _enrich(obj)

    def list(self, current_user: User, skip: int = 0, limit: int = 50) -> List[FlatOut]:
        return [_enrich(f) for f in self.repo.get_all(skip, limit, society_id=current_user.society_id)]

    def list_by_wing(self, wing_id: UUID, current_user: User) -> List[FlatOut]:
        wing = self.wing_repo.get_kept(wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        return [_enrich(f) for f in self.repo.get_by_wing(wing_id)]

    def list_by_society(self, society_id: UUID, current_user: User) -> List[FlatOut]:
        assert_society_access(current_user, society_id)
        return [_enrich(f) for f in self.repo.get_by_society(society_id)]

    def update(self, id: UUID, data: FlatUpdate, current_user: User) -> FlatOut:
        flat = self.repo.get(id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")
        patch = data.model_dump(exclude_none=True)
        # Unlike the other fields, the VAN can be cleared (sent as null / "")
        if "virtual_account_number" in data.model_fields_set:
            patch["virtual_account_number"] = data.virtual_account_number
            if data.virtual_account_number:
                self.repo.assert_unique_van(flat.wing.society_id, data.virtual_account_number, exclude_id=id)
        # The possession date and the electricity numbers can be cleared the same way (sent as null / "")
        for key in ("possession_date", "electric_meter_no", "electric_consumer_no"):
            if key in data.model_fields_set:
                patch[key] = getattr(data, key)
        if patch.get("electric_meter_no"):
            assert_meter_free(self.repo.db, flat.wing.society_id, patch["electric_meter_no"], exclude_flat_id=id)
        if "flat_number" in patch and patch["flat_number"] != flat.flat_number:
            self.repo.assert_unique_flat_number(
                flat.wing_id, patch["flat_number"], exclude_id=id
            )
        return _enrich(self.repo.update(flat, patch))

    def delete(self, id: UUID, current_user: User) -> None:
        flat = self.repo.get(id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")
        self._assert_removable(flat)
        self.repo.soft_delete(flat)

    def _assert_removable(self, flat: Flat) -> None:
        """A flat with people living in it or dues against it stays: those
        records (and the bills' history) point at it."""
        from app.models.resident import Resident
        from app.models.tenant import Tenant
        from app.modules.billing.models.billing import BillStatus, MaintenanceBill
        db = self.repo.db
        residents = db.query(Resident).filter(Resident.flat_id == flat.id, Resident.is_active == True).count()
        tenants = db.query(Tenant).filter(Tenant.flat_id == flat.id, Tenant.is_active == True).count()
        if residents or tenants:
            who = " and ".join(x for x in (
                f"{residents} resident{'s' if residents != 1 else ''}" if residents else "",
                f"{tenants} tenant{'s' if tenants != 1 else ''}" if tenants else "") if x)
            raise HTTPException(409, f"Flat {flat.flat_number} has {who}. Move them out first.")
        unpaid = db.query(MaintenanceBill).filter(
            MaintenanceBill.flat_id == flat.id, MaintenanceBill.is_active == True,
            MaintenanceBill.bill_status.in_([BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE]),
            MaintenanceBill.outstanding > 0).count()
        if unpaid:
            raise HTTPException(
                409, f"Flat {flat.flat_number} has {unpaid} unpaid maintenance bill{'s' if unpaid != 1 else ''}. "
                     f"Collect or cancel them first.")
