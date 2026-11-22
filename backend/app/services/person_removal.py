"""Removing a resident or tenant entered by mistake.

The person is hidden (is_active=False) with their vehicles and open agreement, and the flat's occupancy is worked out
again. It is refused, with the reason, when the record has real history: bills, gym visits, a parking allotment, a
move-out, or a tenant's renewed/ended agreements. Their app login is switched off too, but only when it was made for
them, was never used, and belongs to nobody else. Past that, "move out" is the right action and keeps the history."""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.removal import refuse_if_in_use
from app.models.agreement_tracker import AgreementStatus, AgreementTracker
from app.models.flat import Flat
from app.models.resident import Resident
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User, UserRole, UserStatus
from app.models.vehicle import Vehicle
from app.modules.parking.models.parking import AllocationStatus, ParkingAllocation
from app.services.occupancy_service import OccupancyService

_HINT = "Use Move out instead, which keeps the history."


def _parking_allotments(db: Session, vehicle_ids) -> int:
    if not vehicle_ids:
        return 0
    return db.query(ParkingAllocation).filter(
        ParkingAllocation.vehicle_id.in_(vehicle_ids), ParkingAllocation.is_active == True,  # noqa: E712
        ParkingAllocation.status.in_([AllocationStatus.ACTIVE, AllocationStatus.SUSPENDED]),
    ).count()


def _vehicles(db: Session, **who) -> list:
    return db.query(Vehicle).filter(Vehicle.is_active == True, *[getattr(Vehicle, k) == v for k, v in who.items()]).all()  # noqa: E712


def _switch_off_login(db: Session, person) -> None:
    """Disable the login made for this person, if nobody else uses it."""
    if person.user_id is None:
        return
    user: Optional[User] = db.query(User).filter(User.id == person.user_id).first()
    if user is None or user.is_superadmin or user.last_login is not None or not user.must_change_password:
        return
    others = db.query(Resident).filter(Resident.user_id == user.id, Resident.id != getattr(person, "id"),
                                       Resident.is_active == True).count()  # noqa: E712
    others += db.query(Tenant).filter(Tenant.user_id == user.id, Tenant.id != getattr(person, "id"),
                                      Tenant.is_active == True).count()  # noqa: E712
    roles = {r for (r,) in db.query(Role.name).join(UserRole, UserRole.role_id == Role.id).filter(UserRole.user_id == user.id)}
    if others or not roles <= {"Resident", "Tenant"}:
        return
    user.is_active = False
    user.status = UserStatus.INACTIVE


def _finish(db: Session, person, vehicles, flat_id: UUID) -> None:
    person.is_active = False
    for v in vehicles:
        v.is_active = False
    _switch_off_login(db, person)
    flat = db.query(Flat).filter(Flat.id == flat_id).first()
    if flat is not None:
        OccupancyService(db)._sync_status(flat)


def remove_resident(db: Session, resident: Resident) -> None:
    if not resident.is_active or resident.move_out_date is not None:
        raise HTTPException(status_code=409, detail=f"{resident.full_name} has already moved out and can't be removed. History is kept.")
    from app.modules.billing.models.billing import MaintenanceBill
    from app.modules.gym.models.gym import GymVisit
    vehicles = _vehicles(db, resident_id=resident.id)
    refuse_if_in_use(resident.full_name, {
        "bill(s)": db.query(MaintenanceBill).filter(MaintenanceBill.resident_id == resident.id,
                                                    MaintenanceBill.is_active == True).count(),  # noqa: E712
        "gym visit(s)": db.query(GymVisit).filter(GymVisit.resident_id == resident.id).count(),
        "parking allotment(s)": _parking_allotments(db, [v.id for v in vehicles]),
    }, _HINT)
    _finish(db, resident, vehicles, resident.flat_id)


def remove_tenant(db: Session, tenant: Tenant) -> None:
    if not tenant.is_active or tenant.move_out_date is not None:
        raise HTTPException(status_code=409, detail=f"{tenant.full_name} has already moved out and can't be removed. History is kept.")
    agreements = db.query(AgreementTracker).filter(AgreementTracker.tenant_id == tenant.id,
                                                   AgreementTracker.is_active == True).all()  # noqa: E712
    vehicles = _vehicles(db, tenant_id=tenant.id)
    refuse_if_in_use(tenant.full_name, {
        "renewed or ended agreement(s)": sum(1 for a in agreements if a.status != AgreementStatus.ACTIVE),
        "parking allotment(s)": _parking_allotments(db, [v.id for v in vehicles]),
    }, _HINT)
    for a in agreements:
        a.is_active = False
    _finish(db, tenant, vehicles, tenant.flat_id)
