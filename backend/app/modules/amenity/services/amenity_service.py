from datetime import datetime, date, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.amenity.models.amenity import (
    Amenity, AmenityRule, AmenitySlot, AmenityPricing,
    AmenityBlackoutDate, AmenityBooking, AmenityUsageLog,
    BookingStatus, BOOKING_TRANSITIONS,
)
from app.modules.amenity.schemas.amenity import (
    AmenityCreate, AmenityUpdate, RuleCreate, PricingCreate,
    BlackoutCreate, SlotCreate, BookingCreate,
    BookingApproveRequest, BookingRejectRequest, BookingCancelRequest,
    UsageLogCreate,
)
from app.modules.amenity.repositories.amenity_repo import (
    AmenityRepository, AmenityRuleRepository, AmenitySlotRepository,
    AmenityBlackoutRepository, AmenityBookingRepository,
)
from app.modules.amenity.services.rule_engine import AmenityRuleEngine
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class AmenityService:

    def __init__(self, db: Session):
        self.db             = db
        self.repo           = AmenityRepository(db)
        self.rule_repo      = AmenityRuleRepository(db)
        self.slot_repo      = AmenitySlotRepository(db)
        self.blackout_repo  = AmenityBlackoutRepository(db)
        self.booking_repo   = AmenityBookingRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_amenity_or_404(self, amenity_id: UUID) -> Amenity:
        a = self.repo.get(amenity_id)
        if not a:
            raise HTTPException(status_code=404, detail="Amenity not found")
        return a

    def _get_booking_or_404(self, booking_id: UUID) -> AmenityBooking:
        b = self.booking_repo.get(booking_id)
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        return b

    def _validate_transition(self, booking: AmenityBooking, new_status: BookingStatus):
        allowed = BOOKING_TRANSITIONS.get(booking.status, set())
        if new_status not in allowed:
            raise HTTPException(status_code=409,
                detail=f"Cannot transition booking from '{booking.status.value}' to '{new_status.value}'")

    def _audit(self, action: AuditAction, entity, entity_type: str,
               user: User, request=None, **kwargs):
        AuditService.log(db=self.db, action=action, module="amenity",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kwargs)

    def _user_roles(self, user: User) -> List[str]:
        return [ur.role.name for ur in user.user_roles if ur.role]

    # ── Amenity CRUD ──────────────────────────────────────────────────────────

    def create_amenity(self, data: AmenityCreate, user: User, request=None) -> Amenity:
        amenity = Amenity(**data.model_dump())
        self.repo.create(amenity)
        self._audit(AuditAction.CREATE, amenity, "Amenity", user, request,
                    new_values={"name": amenity.name, "type": amenity.amenity_type.value})
        return amenity

    def update_amenity(self, amenity_id: UUID, data: AmenityUpdate,
                       user: User, request=None) -> Amenity:
        amenity = self._get_amenity_or_404(amenity_id)
        updated = self.repo.update(amenity, data.model_dump(exclude_none=True))
        self._audit(AuditAction.UPDATE, updated, "Amenity", user, request)
        return updated

    def list_amenities(self, society_id: UUID) -> List[Amenity]:
        return self.repo.get_by_society(society_id)

    def get_amenity(self, amenity_id: UUID) -> Amenity:
        return self._get_amenity_or_404(amenity_id)

    # ── Rules ─────────────────────────────────────────────────────────────────

    def add_rule(self, amenity_id: UUID, data: RuleCreate,
                 user: User, request=None) -> AmenityRule:
        self._get_amenity_or_404(amenity_id)
        rule = AmenityRule(amenity_id=amenity_id, **data.model_dump())
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        self._audit(AuditAction.UPDATE, rule, "AmenityRule", user, request,
                    new_values={"rule_type": data.rule_type.value, "value": data.rule_value})
        return rule

    def get_rules(self, amenity_id: UUID) -> List[AmenityRule]:
        return self.rule_repo.get_by_amenity(amenity_id)

    def delete_rule(self, rule_id: UUID, user: User) -> None:
        rule = self.rule_repo.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        self.rule_repo.soft_delete(rule)

    # ── Pricing ───────────────────────────────────────────────────────────────

    def add_pricing(self, amenity_id: UUID, data: PricingCreate,
                    user: User) -> AmenityPricing:
        self._get_amenity_or_404(amenity_id)
        pricing = AmenityPricing(amenity_id=amenity_id, **data.model_dump())
        self.db.add(pricing)
        self.db.commit()
        self.db.refresh(pricing)
        return pricing

    # ── Blackout dates ────────────────────────────────────────────────────────

    def add_blackout(self, amenity_id: UUID, data: BlackoutCreate,
                     user: User) -> AmenityBlackoutDate:
        self._get_amenity_or_404(amenity_id)
        b = AmenityBlackoutDate(amenity_id=amenity_id, created_by=user.id, **data.model_dump())
        self.db.add(b)
        self.db.commit()
        self.db.refresh(b)
        return b

    def get_blackouts(self, amenity_id: UUID) -> List[AmenityBlackoutDate]:
        return self.blackout_repo.get_by_amenity(amenity_id)

    def remove_blackout(self, blackout_id: UUID, user: User) -> None:
        b = self.blackout_repo.get(blackout_id)
        if not b:
            raise HTTPException(status_code=404, detail="Blackout date not found")
        self.blackout_repo.soft_delete(b)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def add_slot(self, amenity_id: UUID, data: SlotCreate) -> AmenitySlot:
        self._get_amenity_or_404(amenity_id)
        slot = AmenitySlot(amenity_id=amenity_id, **data.model_dump())
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def get_availability(self, amenity_id: UUID, for_date: date) -> List[AmenitySlot]:
        return self.slot_repo.get_available(amenity_id, for_date)

    # ── Booking workflow ──────────────────────────────────────────────────────

    def create_booking(self, data: BookingCreate, user: User,
                       request=None) -> AmenityBooking:
        amenity = self._get_amenity_or_404(data.amenity_id)
        rules   = self.rule_repo.get_by_amenity(amenity.id)
        engine  = AmenityRuleEngine(rules)

        # Collect validation inputs
        is_blackout = self.blackout_repo.is_blackout(amenity.id, data.booking_date)
        conflicts   = self.booking_repo.get_conflicts(
            amenity.id, data.booking_date, data.start_time, data.end_time)

        week_start  = data.booking_date - timedelta(days=data.booking_date.weekday())
        week_end    = week_start + timedelta(days=6)
        month_start = data.booking_date.replace(day=1)
        month_end   = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        booking_count_week  = self.booking_repo.count_user_bookings_in_period(
            user.id, amenity.id, week_start, week_end)
        booking_count_month = self.booking_repo.count_user_bookings_in_period(
            user.id, amenity.id, month_start, month_end)

        # Run rule engine
        meta = engine.validate_booking_request(
            data=data, user=user, user_roles=self._user_roles(user),
            conflicts=conflicts, is_blackout=is_blackout,
            booking_count_week=booking_count_week,
            booking_count_month=booking_count_month,
        )

        # Determine status
        needs_approval = meta["needs_approval"] or amenity.approval_required
        status = BookingStatus.PENDING if needs_approval else BookingStatus.APPROVED

        booking = AmenityBooking(
            **data.model_dump(),
            booked_by=user.id,
            status=status,
            charge_amount=meta.get("charge_amount"),
            deposit_amount=meta.get("deposit_amount"),
        )
        self.db.add(booking)
        self.db.flush()

        self._audit(AuditAction.CREATE, booking, "AmenityBooking", user, request,
                    new_values={"amenity": str(amenity.id), "date": str(data.booking_date),
                                "status": status.value})

        # Notify if pending approval
        if status == BookingStatus.PENDING:
            NotificationService.send(
                db=self.db, user_id=user.id,
                title="Booking Pending Approval",
                body=f"Your booking for {amenity.name} on {data.booking_date} is awaiting approval.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="amenity", entity_id=str(booking.id),
            )

        self.db.commit()
        self.db.refresh(booking)
        return booking

    def approve_booking(self, booking_id: UUID, data: BookingApproveRequest,
                        user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id)
        self._validate_transition(booking, BookingStatus.APPROVED)

        booking.status      = BookingStatus.APPROVED
        booking.approved_by = user.id
        booking.approved_at = datetime.utcnow()

        self._audit(AuditAction.APPROVE, booking, "AmenityBooking", user, request,
                    new_values={"status": "approved"})
        NotificationService.send(
            db=self.db, user_id=booking.booked_by,
            title="Booking Approved",
            body=f"Your amenity booking has been approved.",
            type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
            module="amenity", entity_id=str(booking.id),
        )
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def reject_booking(self, booking_id: UUID, data: BookingRejectRequest,
                       user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id)
        self._validate_transition(booking, BookingStatus.REJECTED)

        booking.status           = BookingStatus.REJECTED
        booking.rejection_reason = data.reason
        booking.approved_by      = user.id
        booking.approved_at      = datetime.utcnow()

        self._audit(AuditAction.REJECT, booking, "AmenityBooking", user, request,
                    new_values={"status": "rejected", "reason": data.reason})
        NotificationService.send(
            db=self.db, user_id=booking.booked_by,
            title="Booking Rejected",
            body=f"Your amenity booking was rejected. Reason: {data.reason}",
            type=NotificationType.WARNING, channel=NotificationChannel.IN_APP,
            module="amenity", entity_id=str(booking.id),
        )
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def cancel_booking(self, booking_id: UUID, data: BookingCancelRequest,
                       user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id)
        self._validate_transition(booking, BookingStatus.CANCELLED)

        booking.status              = BookingStatus.CANCELLED
        booking.cancelled_at        = datetime.utcnow()
        booking.cancellation_reason = data.reason

        self._audit(AuditAction.UPDATE, booking, "AmenityBooking", user, request,
                    new_values={"status": "cancelled"})
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def complete_booking(self, booking_id: UUID, usage_data: UsageLogCreate,
                         user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id)
        self._validate_transition(booking, BookingStatus.COMPLETED)

        booking.status = BookingStatus.COMPLETED

        log = AmenityUsageLog(
            booking_id=booking.id,
            amenity_id=booking.amenity_id,
            society_id=booking.society_id,
            used_by=booking.booked_by,
            **usage_data.model_dump(),
        )
        self.db.add(log)
        self._audit(AuditAction.UPDATE, booking, "AmenityBooking", user, request,
                    new_values={"status": "completed",
                                "damage_noted": usage_data.damage_noted})
        self.db.commit()
        self.db.refresh(booking)
        return booking

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_booking(self, booking_id: UUID) -> AmenityBooking:
        return self._get_booking_or_404(booking_id)

    def my_bookings(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[AmenityBooking]:
        return self.booking_repo.get_by_user(user_id, skip, limit)

    def society_bookings(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[AmenityBooking]:
        return self.booking_repo.get_by_society(society_id, skip, limit)

    def pending_bookings(self, society_id: UUID) -> List[AmenityBooking]:
        return self.booking_repo.get_pending(society_id)
