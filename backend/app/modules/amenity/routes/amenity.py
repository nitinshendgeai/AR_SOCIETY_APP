from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_admin_committee, require_manager_above, require_any_member,
)
from app.models.user import User
from app.modules.amenity.schemas.amenity import (
    AmenityCreate, AmenityUpdate, AmenityOut,
    RuleCreate, RuleOut, PricingCreate, PricingOut,
    BlackoutCreate, BlackoutOut, SlotCreate, SlotOut,
    BookingCreate, BookingApproveRequest,
    BookingRejectRequest, BookingCancelRequest, UsageLogCreate,
)
from app.modules.amenity.services.amenity_service import AmenityService

router = APIRouter(prefix="/amenities", tags=["Amenity Management"])

# The committee sets amenities up; the manager and above run the bookings day to day.
committee_or_admin = require_admin_committee
booking_manager    = require_manager_above
any_member         = require_any_member


# ── Amenity CRUD ──────────────────────────────────────────────────────────────

@router.post("/", response_model=AmenityOut, status_code=201,
             dependencies=[Depends(committee_or_admin)])
def create_amenity(data: AmenityCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return AmenityService(db).create_amenity(data, user, request)


# ── Bookings (declared before /{amenity_id} so the fixed paths win) ───────────

@router.post("/bookings", status_code=201)
def create_booking(data: BookingCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    service = AmenityService(db)
    return service.out([service.create_booking(data, user, request)])[0]


@router.get("/bookings/me/list")
def my_bookings(skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db),
                user: User = Depends(any_member)):
    return AmenityService(db).my_bookings(user, skip, limit)


@router.get("/bookings/society/{society_id}/pending",
            dependencies=[Depends(booking_manager)])
def pending_bookings(society_id: UUID, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return AmenityService(db).pending_bookings(society_id, user)


@router.get("/bookings/society/{society_id}",
            dependencies=[Depends(booking_manager)])
def society_bookings(society_id: UUID, skip: int = 0, limit: int = 50,
                     status: Optional[str] = None, amenity_id: Optional[UUID] = None,
                     date_from: Optional[date] = None, date_to: Optional[date] = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return AmenityService(db).society_bookings(society_id, user, skip, limit, status, amenity_id, date_from, date_to)


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(any_member)):
    return AmenityService(db).get_booking(booking_id, user)


def _one(service: AmenityService, booking):
    return service.out([booking])[0]


@router.post("/bookings/{booking_id}/approve")
def approve_booking(booking_id: UUID, data: BookingApproveRequest,
                    request: Request, db: Session = Depends(get_db),
                    user: User = Depends(booking_manager)):
    service = AmenityService(db)
    return _one(service, service.approve_booking(booking_id, data, user, request))


@router.post("/bookings/{booking_id}/reject")
def reject_booking(booking_id: UUID, data: BookingRejectRequest,
                   request: Request, db: Session = Depends(get_db),
                   user: User = Depends(booking_manager)):
    service = AmenityService(db)
    return _one(service, service.reject_booking(booking_id, data, user, request))


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: UUID, data: BookingCancelRequest,
                   request: Request, db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    service = AmenityService(db)
    return _one(service, service.cancel_booking(booking_id, data, user, request))


@router.post("/bookings/{booking_id}/complete")
def complete_booking(booking_id: UUID, data: UsageLogCreate,
                     request: Request, db: Session = Depends(get_db),
                     user: User = Depends(booking_manager)):
    service = AmenityService(db)
    return _one(service, service.complete_booking(booking_id, data, user, request))


# ── Rules / pricing / blackouts: fixed-prefix deletes ─────────────────────────

@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(committee_or_admin)):
    AmenityService(db).delete_rule(rule_id, user)


@router.delete("/pricing/{pricing_id}", status_code=204)
def delete_pricing(pricing_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(committee_or_admin)):
    AmenityService(db).delete_pricing(pricing_id, user)


@router.delete("/blackouts/{blackout_id}", status_code=204)
def remove_blackout(blackout_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(committee_or_admin)):
    AmenityService(db).remove_blackout(blackout_id, user)


# ── Listing and one amenity ───────────────────────────────────────────────────

@router.get("/society/{society_id}", response_model=List[AmenityOut],
            dependencies=[Depends(any_member)])
def list_amenities(society_id: UUID, include_closed: bool = False,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Closed amenities are only listed for the committee that manages them.
    service = AmenityService(db)
    return service.list_amenities(society_id, user, include_closed and service._manages(user))


@router.patch("/{amenity_id}", response_model=AmenityOut,
              dependencies=[Depends(committee_or_admin)])
def update_amenity(amenity_id: UUID, data: AmenityUpdate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return AmenityService(db).update_amenity(amenity_id, data, user, request)


@router.get("/{amenity_id}", response_model=AmenityOut,
            dependencies=[Depends(any_member)])
def get_amenity(amenity_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return AmenityService(db).get_amenity(amenity_id, user)


@router.get("/{amenity_id}/day")
def day_view(amenity_id: UUID, for_date: date = Query(..., description="YYYY-MM-DD"),
             db: Session = Depends(get_db), user: User = Depends(any_member)):
    return AmenityService(db).day_view(amenity_id, for_date, user)


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/rules", response_model=RuleOut, status_code=201)
def add_rule(amenity_id: UUID, data: RuleCreate, request: Request,
             db: Session = Depends(get_db),
             user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_rule(amenity_id, data, user, request)


@router.get("/{amenity_id}/rules", response_model=List[RuleOut],
            dependencies=[Depends(any_member)])
def get_rules(amenity_id: UUID, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    # Residents read the rules to know what applies before they book.
    return AmenityService(db).get_rules(amenity_id, user)


# ── Pricing ───────────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/pricing", response_model=PricingOut, status_code=201)
def add_pricing(amenity_id: UUID, data: PricingCreate,
                db: Session = Depends(get_db),
                user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_pricing(amenity_id, data, user)


@router.get("/{amenity_id}/pricing", response_model=List[PricingOut],
            dependencies=[Depends(any_member)])
def get_pricing(amenity_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return AmenityService(db).get_pricing(amenity_id, user)


# ── Blackout dates ────────────────────────────────────────────────────────────

@router.post("/{amenity_id}/blackouts", response_model=BlackoutOut, status_code=201)
def add_blackout(amenity_id: UUID, data: BlackoutCreate,
                 db: Session = Depends(get_db),
                 user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_blackout(amenity_id, data, user)


@router.get("/{amenity_id}/blackouts", response_model=List[BlackoutOut],
            dependencies=[Depends(any_member)])
def get_blackouts(amenity_id: UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return AmenityService(db).get_blackouts(amenity_id, user)


# ── Slots / Availability (older, kept) ────────────────────────────────────────

@router.post("/{amenity_id}/slots", response_model=SlotOut, status_code=201)
def add_slot(amenity_id: UUID, data: SlotCreate, db: Session = Depends(get_db),
             user: User = Depends(committee_or_admin)):
    return AmenityService(db).add_slot(amenity_id, data, user)


@router.get("/{amenity_id}/availability", response_model=List[SlotOut],
            dependencies=[Depends(any_member)])
def get_availability(amenity_id: UUID,
                     for_date: date = Query(..., description="YYYY-MM-DD"),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return AmenityService(db).get_availability(amenity_id, for_date, user)
