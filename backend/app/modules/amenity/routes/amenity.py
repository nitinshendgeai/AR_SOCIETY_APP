from typing import List
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_any_member,
)
from app.models.user import User
from app.modules.amenity.schemas.amenity import (
    AmenityCreate, AmenityUpdate, AmenityOut,
    RuleCreate, RuleOut, PricingCreate, PricingOut,
    BlackoutCreate, BlackoutOut, SlotCreate, SlotOut,
    BookingCreate, BookingOut, BookingApproveRequest,
    BookingRejectRequest, BookingCancelRequest, UsageLogCreate,
)
from app.modules.amenity.services.amenity_service import AmenityService

router = APIRouter(prefix="/amenities", tags=["Amenity Management"])

committee_or_admin = require_admin_committee
any_member         = require_any_member


# ── Amenity CRUD ──────────────────────────────────────────────────────────────

@router.post("/", response_model=AmenityOut, status_code=201,
             dependencies=[Depends(committee_or_admin)])
def create_amenity(data: AmenityCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return AmenityService(db).create_amenity(data, user, request)


@router.patch("/{amenity_id}", response_model=AmenityOut,
              dependencies=[Depends(committee_or_admin)])
def update_amenity(amenity_id: UUID, data: AmenityUpdate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return AmenityService(db).update_amenity(amenity_id, data, user, request)


@router.get("/society/{society_id}", response_model=List[AmenityOut],
            dependencies=[Depends(any_member)])
def list_amenities(society_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).list_amenities(society_id)


@router.get("/{amenity_id}", response_model=AmenityOut,
            dependencies=[Depends(any_member)])
def get_amenity(amenity_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).get_amenity(amenity_id)


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/rules", response_model=RuleOut, status_code=201)
def add_rule(amenity_id: UUID, data: RuleCreate, request: Request,
             db: Session = Depends(get_db),
             user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_rule(amenity_id, data, user, request)


@router.get("/{amenity_id}/rules", response_model=List[RuleOut],
            dependencies=[Depends(committee_or_admin)])
def get_rules(amenity_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).get_rules(amenity_id)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(committee_or_admin)):
    AmenityService(db).delete_rule(rule_id, user)


# ── Pricing ───────────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/pricing", response_model=PricingOut, status_code=201)
def add_pricing(amenity_id: UUID, data: PricingCreate,
                db: Session = Depends(get_db),
                user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_pricing(amenity_id, data, user)


# ── Blackout dates ────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/blackouts", response_model=BlackoutOut, status_code=201)
def add_blackout(amenity_id: UUID, data: BlackoutCreate,
                 db: Session = Depends(get_db),
                 user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_blackout(amenity_id, data, user)


@router.get("/{amenity_id}/blackouts", response_model=List[BlackoutOut],
            dependencies=[Depends(any_member)])
def get_blackouts(amenity_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).get_blackouts(amenity_id)


@router.delete("/blackouts/{blackout_id}", status_code=204)
def remove_blackout(blackout_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(committee_or_admin)):
    AmenityService(db).remove_blackout(blackout_id, user)


# ── Slots / Availability ──────────────────────────────────────────────────────

@router.post("/{amenity_id}/slots", response_model=SlotOut, status_code=201,
             dependencies=[Depends(committee_or_admin)])
def add_slot(amenity_id: UUID, data: SlotCreate,
             db: Session = Depends(get_db)):
    return AmenityService(db).add_slot(amenity_id, data)


@router.get("/{amenity_id}/availability", response_model=List[SlotOut],
            dependencies=[Depends(any_member)])
def get_availability(amenity_id: UUID,
                     for_date: date = Query(..., description="YYYY-MM-DD"),
                     db: Session = Depends(get_db)):
    return AmenityService(db).get_availability(amenity_id, for_date)


# ── Bookings ──────────────────────────────────────────────────────────────────

@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    return AmenityService(db).create_booking(data, user, request)


@router.get("/bookings/{booking_id}", response_model=BookingOut,
            dependencies=[Depends(any_member)])
def get_booking(booking_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).get_booking(booking_id)


@router.post("/bookings/{booking_id}/approve", response_model=BookingOut)
def approve_booking(booking_id: UUID, data: BookingApproveRequest,
                    request: Request, db: Session = Depends(get_db),
                    user: User = Depends(committee_or_admin)):
    return AmenityService(db).approve_booking(booking_id, data, user, request)


@router.post("/bookings/{booking_id}/reject", response_model=BookingOut)
def reject_booking(booking_id: UUID, data: BookingRejectRequest,
                   request: Request, db: Session = Depends(get_db),
                   user: User = Depends(committee_or_admin)):
    return AmenityService(db).reject_booking(booking_id, data, user, request)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: UUID, data: BookingCancelRequest,
                   request: Request, db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    return AmenityService(db).cancel_booking(booking_id, data, user, request)


@router.post("/bookings/{booking_id}/complete", response_model=BookingOut)
def complete_booking(booking_id: UUID, data: UsageLogCreate,
                     request: Request, db: Session = Depends(get_db),
                     user: User = Depends(committee_or_admin)):
    return AmenityService(db).complete_booking(booking_id, data, user, request)


# ── Query endpoints ───────────────────────────────────────────────────────────

@router.get("/bookings/me/list", response_model=List[BookingOut])
def my_bookings(skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db),
                user: User = Depends(any_member)):
    return AmenityService(db).my_bookings(user.id, skip, limit)


@router.get("/bookings/society/{society_id}", response_model=List[BookingOut],
            dependencies=[Depends(committee_or_admin)])
def society_bookings(society_id: UUID, skip: int = 0, limit: int = 50,
                     db: Session = Depends(get_db)):
    return AmenityService(db).society_bookings(society_id, skip, limit)


@router.get("/bookings/society/{society_id}/pending", response_model=List[BookingOut],
            dependencies=[Depends(committee_or_admin)])
def pending_bookings(society_id: UUID, db: Session = Depends(get_db)):
    return AmenityService(db).pending_bookings(society_id)
