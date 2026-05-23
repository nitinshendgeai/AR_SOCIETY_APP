from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from app.modules.amenity.models.amenity import (
    Amenity, AmenityRule, AmenitySlot, AmenityPricing,
    AmenityBlackoutDate, AmenityBooking, AmenityUsageLog,
    BookingStatus,
)
from app.repositories.base import BaseRepository


class AmenityRepository(BaseRepository[Amenity]):
    def __init__(self, db: Session):
        super().__init__(Amenity, db)

    def get_by_society(self, society_id: UUID) -> List[Amenity]:
        return self.db.query(Amenity).filter(
            Amenity.society_id == society_id,
            Amenity.is_active  == True,
        ).all()


class AmenityRuleRepository(BaseRepository[AmenityRule]):
    def __init__(self, db: Session):
        super().__init__(AmenityRule, db)

    def get_by_amenity(self, amenity_id: UUID) -> List[AmenityRule]:
        return self.db.query(AmenityRule).filter(
            AmenityRule.amenity_id == amenity_id,
            AmenityRule.is_active  == True,
        ).all()


class AmenitySlotRepository(BaseRepository[AmenitySlot]):
    def __init__(self, db: Session):
        super().__init__(AmenitySlot, db)

    def get_available(self, amenity_id: UUID, slot_date: date) -> List[AmenitySlot]:
        return self.db.query(AmenitySlot).filter(
            AmenitySlot.amenity_id   == amenity_id,
            AmenitySlot.slot_date    == slot_date,
            AmenitySlot.is_available == True,
            AmenitySlot.is_active    == True,
        ).order_by(AmenitySlot.start_time).all()


class AmenityBlackoutRepository(BaseRepository[AmenityBlackoutDate]):
    def __init__(self, db: Session):
        super().__init__(AmenityBlackoutDate, db)

    def get_by_amenity(self, amenity_id: UUID) -> List[AmenityBlackoutDate]:
        return self.db.query(AmenityBlackoutDate).filter(
            AmenityBlackoutDate.amenity_id == amenity_id,
            AmenityBlackoutDate.is_active  == True,
        ).order_by(AmenityBlackoutDate.blackout_date).all()

    def is_blackout(self, amenity_id: UUID, booking_date: date) -> bool:
        return self.db.query(AmenityBlackoutDate).filter(
            AmenityBlackoutDate.amenity_id    == amenity_id,
            AmenityBlackoutDate.blackout_date == booking_date,
            AmenityBlackoutDate.is_active     == True,
        ).first() is not None


class AmenityBookingRepository(BaseRepository[AmenityBooking]):
    def __init__(self, db: Session):
        super().__init__(AmenityBooking, db)

    def get_by_user(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[AmenityBooking]:
        return self.db.query(AmenityBooking).filter(
            AmenityBooking.booked_by == user_id,
            AmenityBooking.is_active == True,
        ).order_by(AmenityBooking.booking_date.desc()).offset(skip).limit(limit).all()

    def get_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[AmenityBooking]:
        return self.db.query(AmenityBooking).filter(
            AmenityBooking.society_id == society_id,
            AmenityBooking.is_active  == True,
        ).order_by(AmenityBooking.booking_date.desc()).offset(skip).limit(limit).all()

    def get_pending(self, society_id: UUID) -> List[AmenityBooking]:
        return self.db.query(AmenityBooking).filter(
            AmenityBooking.society_id == society_id,
            AmenityBooking.status     == BookingStatus.PENDING,
            AmenityBooking.is_active  == True,
        ).all()

    def get_conflicts(self, amenity_id: UUID, booking_date: date,
                      start_time, end_time) -> List[AmenityBooking]:
        """Detect overlapping bookings for same amenity/date."""
        return self.db.query(AmenityBooking).filter(
            AmenityBooking.amenity_id    == amenity_id,
            AmenityBooking.booking_date  == booking_date,
            AmenityBooking.status.in_([BookingStatus.PENDING, BookingStatus.APPROVED]),
            AmenityBooking.is_active     == True,
            AmenityBooking.start_time    < end_time,
            AmenityBooking.end_time      > start_time,
        ).all()

    def count_user_bookings_in_period(self, user_id: UUID, amenity_id: UUID,
                                      start_date: date, end_date: date) -> int:
        return self.db.query(AmenityBooking).filter(
            AmenityBooking.booked_by    == user_id,
            AmenityBooking.amenity_id   == amenity_id,
            AmenityBooking.booking_date >= start_date,
            AmenityBooking.booking_date <= end_date,
            AmenityBooking.status.notin_([BookingStatus.REJECTED, BookingStatus.CANCELLED]),
            AmenityBooking.is_active    == True,
        ).count()
