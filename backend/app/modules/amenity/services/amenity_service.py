"""Amenities (clubhouse, gym, pool, party hall…) and their bookings.

A society sets up each amenity with its hours, capacity and rules (maximum hours, how far ahead, how many a week,
guests, owners only, charges, whether the committee must approve). Residents book a time; the booking is checked
against the hours, the rules, blackout dates and everyone else's bookings, and is either approved at once or waits
for the committee. Everything is confined to the caller's society: something of another society reads as not found.
"""
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.notification import NotificationChannel, NotificationType
from app.models.resident import Resident
from app.models.society import Society
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.modules.amenity.models.amenity import (
    Amenity, AmenityBlackoutDate, AmenityBooking, AmenityPricing, AmenityRule, AmenitySlot, AmenityUsageLog,
    BOOKING_TRANSITIONS, BookingStatus, RuleType,
)
from app.modules.amenity.repositories.amenity_repo import (
    AmenityBlackoutRepository, AmenityBookingRepository, AmenityRepository, AmenityRuleRepository,
    AmenitySlotRepository,
)
from app.modules.amenity.schemas.amenity import (
    AmenityCreate, AmenityUpdate, BlackoutCreate, BookingApproveRequest, BookingCancelRequest, BookingCreate,
    BookingOut, BookingRejectRequest, PricingCreate, RuleCreate, SlotCreate, UsageLogCreate,
)
from app.modules.amenity.services.rule_engine import AmenityRuleEngine
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.utils.local_time import local_now, zone

MANAGER_ROLES = {"Platform Admin", "Society Admin", "Committee Chairman", "Committee Secretary",
                 "Committee Treasurer", "Committee Member", "Manager"}

# Rules whose value is a number, and which of those may be a fraction.
NUMERIC_RULES = {
    RuleType.MAX_DURATION_HOURS: True, RuleType.MAX_BOOKINGS_PER_WEEK: False, RuleType.MAX_BOOKINGS_PER_MONTH: False,
    RuleType.MIN_ADVANCE_HOURS: True, RuleType.MAX_ADVANCE_DAYS: False, RuleType.DEPOSIT_REQUIRED: True,
    RuleType.CHARGE_PER_HOUR: True, RuleType.MAX_GUESTS: False,
}


class AmenityService:

    def __init__(self, db: Session):
        self.db             = db
        self.repo           = AmenityRepository(db)
        self.rule_repo      = AmenityRuleRepository(db)
        self.slot_repo      = AmenitySlotRepository(db)
        self.blackout_repo  = AmenityBlackoutRepository(db)
        self.booking_repo   = AmenityBookingRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────────
    # Something that belongs to another society is reported as not found, so ids can't be probed.

    @staticmethod
    def _in_scope(user: Optional[User], society_id) -> bool:
        return user is None or user.society_id is None or user.society_id == society_id

    def _scoped_or_404(self, row, user: Optional[User], what: str):
        if row is None or not self._in_scope(user, row.society_id):
            raise HTTPException(status_code=404, detail=f"{what} not found")
        return row

    def _get_amenity_or_404(self, amenity_id: UUID, user: Optional[User] = None) -> Amenity:
        # Closed amenities stay readable (the committee reopens them); booking checks is_active itself.
        return self._scoped_or_404(self.db.query(Amenity).filter(Amenity.id == amenity_id).first(), user, "Amenity")

    def _get_booking_or_404(self, booking_id: UUID, user: Optional[User] = None) -> AmenityBooking:
        return self._scoped_or_404(self.booking_repo.get(booking_id), user, "Booking")

    def _validate_transition(self, booking: AmenityBooking, new_status: BookingStatus):
        if new_status not in BOOKING_TRANSITIONS.get(booking.status, set()):
            raise HTTPException(status_code=409,
                detail=f"A booking that is {booking.status.value} can't be made {new_status.value}")

    def _audit(self, action: AuditAction, entity, entity_type: str, user: User, request=None, **kwargs):
        AuditService.log(db=self.db, action=action, module="amenity", entity_id=str(entity.id),
                         entity_type=entity_type, user=user, request=request, **kwargs)

    @staticmethod
    def _roles(user: User) -> List[str]:
        return [ur.role.name for ur in user.user_roles if ur.role]

    def _manages(self, user: User) -> bool:
        return bool(set(self._roles(user)) & MANAGER_ROLES)

    def _now(self, society_id: UUID) -> datetime:
        """The society's clock as a naive datetime (booking dates and times are written in it)."""
        society = self.db.query(Society).filter(Society.id == society_id).first()
        return local_now(zone(society.timezone if society else None)).replace(tzinfo=None)

    def _my_flat_ids(self, user_id: UUID, society_id: UUID) -> List[UUID]:
        ids = set()
        for model in (Resident, Tenant):
            for (fid,) in (self.db.query(model.flat_id).join(Flat, Flat.id == model.flat_id)
                           .join(Wing, Wing.id == Flat.wing_id)
                           .filter(model.user_id == user_id, model.is_active == True,
                                   Wing.society_id == society_id).all()):
                ids.add(fid)
        return list(ids)

    def _flat_labels(self, flat_ids) -> Dict[UUID, str]:
        ids = [f for f in set(flat_ids) if f]
        if not ids:
            return {}
        return {f.id: f"{w.name} / {f.flat_number}" for f, w in
                self.db.query(Flat, Wing).join(Wing, Wing.id == Flat.wing_id).filter(Flat.id.in_(ids)).all()}

    # ── Amenity CRUD ──────────────────────────────────────────────────────────

    @staticmethod
    def _check_hours(open_time, close_time) -> None:
        if open_time and close_time and close_time <= open_time:
            raise HTTPException(422, "It must close after it opens")

    def _name_free(self, society_id: UUID, name: str, exclude: Optional[UUID] = None) -> None:
        q = self.db.query(Amenity.id).filter(Amenity.society_id == society_id, Amenity.is_active == True,
                                             Amenity.name.ilike(name))
        if exclude:
            q = q.filter(Amenity.id != exclude)
        if q.first():
            raise HTTPException(409, f"There is already an amenity called “{name}”")

    def create_amenity(self, data: AmenityCreate, user: User, request=None) -> Amenity:
        society_id = resolve_create_society_id(user, data.society_id)
        values = {**data.model_dump(), "society_id": society_id, "name": (data.name or "").strip()}
        if not values["name"]:
            raise HTTPException(422, "Give the amenity a name")
        if data.capacity is not None and data.capacity < 1:
            raise HTTPException(422, "Capacity must be at least 1")
        self._check_hours(data.open_time, data.close_time)
        self._name_free(society_id, values["name"])
        amenity = Amenity(**values)
        self.repo.create(amenity)
        self._audit(AuditAction.CREATE, amenity, "Amenity", user, request,
                    new_values={"name": amenity.name, "type": amenity.amenity_type.value})
        return amenity

    def update_amenity(self, amenity_id: UUID, data: AmenityUpdate, user: User, request=None) -> Amenity:
        amenity = self._get_amenity_or_404(amenity_id, user)
        changes = data.model_dump(exclude_unset=True)
        for required in ("name", "amenity_type", "is_active", "booking_required", "approval_required", "is_chargeable"):
            if required in changes and changes[required] is None:
                changes.pop(required)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise HTTPException(422, "Give the amenity a name")
            self._name_free(amenity.society_id, changes["name"], exclude=amenity.id)
        if changes.get("capacity") is not None and changes["capacity"] < 1:
            raise HTTPException(422, "Capacity must be at least 1")
        self._check_hours(changes.get("open_time", amenity.open_time), changes.get("close_time", amenity.close_time))
        for key, value in changes.items():
            setattr(amenity, key, value)
        self._audit(AuditAction.UPDATE, amenity, "Amenity", user, request, new_values={k: str(v) for k, v in changes.items()})
        self.db.commit()
        self.db.refresh(amenity)
        return amenity

    def list_amenities(self, society_id: UUID, user: Optional[User] = None, include_closed: bool = False) -> List[Amenity]:
        if user is not None:
            assert_society_access(user, society_id)
        q = self.db.query(Amenity).filter(Amenity.society_id == society_id)
        if not include_closed:
            q = q.filter(Amenity.is_active == True)
        return q.order_by(Amenity.name).all()

    def get_amenity(self, amenity_id: UUID, user: Optional[User] = None) -> Amenity:
        return self._get_amenity_or_404(amenity_id, user)

    # ── Rules ─────────────────────────────────────────────────────────────────

    def add_rule(self, amenity_id: UUID, data: RuleCreate, user: User, request=None) -> AmenityRule:
        """Set a rule. An amenity has one rule of each kind: setting it again replaces the earlier value."""
        self._get_amenity_or_404(amenity_id, user)
        value = (data.rule_value or "").strip() or None
        if data.rule_type in NUMERIC_RULES:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise HTTPException(422, "This rule needs a number")
            if number <= 0 or (not NUMERIC_RULES[data.rule_type] and number != int(number)):
                raise HTTPException(422, "Enter a whole number above zero" if not NUMERIC_RULES[data.rule_type]
                                    else "Enter an amount above zero")
        existing = self.db.query(AmenityRule).filter(
            AmenityRule.amenity_id == amenity_id, AmenityRule.rule_type == data.rule_type,
            AmenityRule.is_active == True).all()
        rule = existing[0] if existing else AmenityRule(amenity_id=amenity_id, rule_type=data.rule_type)
        for extra in existing[1:]:
            extra.is_active = False
        rule.rule_value = value
        rule.description = data.description
        rule.is_active = True
        self.db.add(rule)
        self.db.flush()
        self._audit(AuditAction.UPDATE, rule, "AmenityRule", user, request,
                    new_values={"rule_type": data.rule_type.value, "value": value})
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_rules(self, amenity_id: UUID, user: Optional[User] = None) -> List[AmenityRule]:
        self._get_amenity_or_404(amenity_id, user)
        return self.rule_repo.get_by_amenity(amenity_id)

    def delete_rule(self, rule_id: UUID, user: User) -> None:
        rule = self.rule_repo.get(rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        self._get_amenity_or_404(rule.amenity_id, user)
        self.rule_repo.soft_delete(rule)

    # ── Pricing ───────────────────────────────────────────────────────────────

    def add_pricing(self, amenity_id: UUID, data: PricingCreate, user: User) -> AmenityPricing:
        self._get_amenity_or_404(amenity_id, user)
        if not (data.label or "").strip():
            raise HTTPException(422, "Name this rate")
        for v in (data.price_per_hour, data.flat_price, data.deposit_amount):
            if v is not None and v < 0:
                raise HTTPException(422, "An amount can't be negative")
        if data.price_per_hour is None and data.flat_price is None and data.deposit_amount is None:
            raise HTTPException(422, "Give a rate per hour, a flat price or a deposit")
        if data.is_default:
            for other in self.db.query(AmenityPricing).filter(AmenityPricing.amenity_id == amenity_id,
                                                              AmenityPricing.is_default == True).all():
                other.is_default = False
        pricing = AmenityPricing(amenity_id=amenity_id, **{**data.model_dump(), "label": data.label.strip()})
        self.db.add(pricing)
        self.db.commit()
        self.db.refresh(pricing)
        return pricing

    def get_pricing(self, amenity_id: UUID, user: Optional[User] = None) -> List[AmenityPricing]:
        self._get_amenity_or_404(amenity_id, user)
        return self.db.query(AmenityPricing).filter(AmenityPricing.amenity_id == amenity_id,
                                                    AmenityPricing.is_active == True).all()

    def delete_pricing(self, pricing_id: UUID, user: User) -> None:
        p = self.db.query(AmenityPricing).filter(AmenityPricing.id == pricing_id, AmenityPricing.is_active == True).first()
        if p is None:
            raise HTTPException(404, "Rate not found")
        self._get_amenity_or_404(p.amenity_id, user)
        p.is_active = False
        self.db.commit()

    # ── Blackout dates ────────────────────────────────────────────────────────

    def add_blackout(self, amenity_id: UUID, data: BlackoutCreate, user: User) -> AmenityBlackoutDate:
        amenity = self._get_amenity_or_404(amenity_id, user)
        if data.blackout_date < self._now(amenity.society_id).date():
            raise HTTPException(422, "Choose today or a later date")
        if self.blackout_repo.is_blackout(amenity_id, data.blackout_date):
            raise HTTPException(409, "That date is already closed")
        b = AmenityBlackoutDate(amenity_id=amenity_id, created_by=user.id, **data.model_dump())
        self.db.add(b)
        self.db.commit()
        self.db.refresh(b)
        return b

    def get_blackouts(self, amenity_id: UUID, user: Optional[User] = None) -> List[AmenityBlackoutDate]:
        self._get_amenity_or_404(amenity_id, user)
        return self.blackout_repo.get_by_amenity(amenity_id)

    def remove_blackout(self, blackout_id: UUID, user: User) -> None:
        b = self.blackout_repo.get(blackout_id)
        if b is None:
            raise HTTPException(status_code=404, detail="Blackout date not found")
        self._get_amenity_or_404(b.amenity_id, user)
        self.blackout_repo.soft_delete(b)

    # ── Slots (kept for older callers) ────────────────────────────────────────

    def add_slot(self, amenity_id: UUID, data: SlotCreate, user: Optional[User] = None) -> AmenitySlot:
        self._get_amenity_or_404(amenity_id, user)
        slot = AmenitySlot(amenity_id=amenity_id, **data.model_dump())
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def get_availability(self, amenity_id: UUID, for_date: date, user: Optional[User] = None) -> List[AmenitySlot]:
        self._get_amenity_or_404(amenity_id, user)
        return self.slot_repo.get_available(amenity_id, for_date)

    def day_view(self, amenity_id: UUID, for_date: date, user: User) -> dict:
        """One day of one amenity: its hours, whether it is closed that day, and who has it when. Residents see
        the times that are taken (and which are their own); the committee also sees who booked."""
        amenity = self._get_amenity_or_404(amenity_id, user)
        blackout = self.db.query(AmenityBlackoutDate).filter(
            AmenityBlackoutDate.amenity_id == amenity_id, AmenityBlackoutDate.blackout_date == for_date,
            AmenityBlackoutDate.is_active == True).first()
        rows = self.db.query(AmenityBooking).filter(
            AmenityBooking.amenity_id == amenity_id, AmenityBooking.booking_date == for_date,
            AmenityBooking.status.in_([BookingStatus.PENDING, BookingStatus.APPROVED]),
            AmenityBooking.is_active == True).order_by(AmenityBooking.start_time).all()
        manages = self._manages(user)
        labels = self._flat_labels([b.flat_id for b in rows]) if manages else {}
        return {
            "amenity_id": str(amenity.id), "name": amenity.name, "date": for_date.isoformat(),
            "open_time": amenity.open_time.isoformat() if amenity.open_time else None,
            "close_time": amenity.close_time.isoformat() if amenity.close_time else None,
            "closed": blackout is not None, "closed_reason": blackout.reason if blackout else None,
            "capacity": amenity.capacity,
            "bookings": [{
                "id": str(b.id), "start_time": b.start_time.isoformat(), "end_time": b.end_time.isoformat(),
                "status": b.status.value, "mine": b.booked_by == user.id,
                **({"booked_by_name": b.booker.full_name if b.booker else None, "flat": labels.get(b.flat_id)} if manages else {}),
            } for b in rows],
        }

    # ── Booking workflow ──────────────────────────────────────────────────────

    def _check_window(self, amenity: Amenity, data: BookingCreate) -> None:
        if not amenity.is_active:
            raise HTTPException(409, f"{amenity.name} is closed")
        if not amenity.booking_required:
            raise HTTPException(409, f"{amenity.name} doesn't need a booking. Just go.")
        problems = []
        if amenity.open_time and data.start_time < amenity.open_time:
            problems.append(f"{amenity.name} opens at {amenity.open_time.strftime('%I:%M %p').lstrip('0')}.")
        if amenity.close_time and data.end_time > amenity.close_time:
            problems.append(f"{amenity.name} closes at {amenity.close_time.strftime('%I:%M %p').lstrip('0')}.")
        if amenity.capacity and data.guest_count > amenity.capacity:
            problems.append(f"{amenity.name} holds {amenity.capacity} people. You asked for {data.guest_count}.")
        if problems:
            raise HTTPException(status_code=422, detail=" ".join(problems))

    def _charges(self, amenity: Amenity, meta: dict, data: BookingCreate):
        """Charge and deposit: the rules first, else the amenity's default rate. Nothing for a free amenity."""
        if not amenity.is_chargeable and meta.get("charge_amount") is None and meta.get("deposit_amount") is None:
            return None, None
        charge, deposit = meta.get("charge_amount"), meta.get("deposit_amount")
        rate = self.db.query(AmenityPricing).filter(AmenityPricing.amenity_id == amenity.id,
                                                    AmenityPricing.is_active == True,
                                                    AmenityPricing.is_default == True).first()
        if rate is not None:
            hours = (datetime.combine(date.min, data.end_time) - datetime.combine(date.min, data.start_time)).total_seconds() / 3600
            if charge is None:
                if rate.flat_price is not None:
                    charge = round(rate.flat_price, 2)
                elif rate.price_per_hour is not None:
                    charge = round(rate.price_per_hour * hours, 2)
            if deposit is None and rate.deposit_amount is not None:
                deposit = rate.deposit_amount
        return charge, deposit

    def create_booking(self, data: BookingCreate, user: User, request=None) -> AmenityBooking:
        amenity = self._get_amenity_or_404(data.amenity_id, user)
        if user.society_id is not None and user.society_id != amenity.society_id:
            raise HTTPException(status_code=404, detail="Amenity not found")
        self._check_window(amenity, data)

        # The flat a booking is for must be the booker's own.
        mine = self._my_flat_ids(user.id, amenity.society_id)
        flat_id = data.flat_id
        if flat_id is not None and flat_id not in mine and not self._manages(user):
            raise HTTPException(422, "That isn't your flat")
        if flat_id is None and len(mine) == 1:
            flat_id = mine[0]

        rules   = self.rule_repo.get_by_amenity(amenity.id)
        engine  = AmenityRuleEngine(rules)
        is_blackout = self.blackout_repo.is_blackout(amenity.id, data.booking_date)
        conflicts   = self.booking_repo.get_conflicts(amenity.id, data.booking_date, data.start_time, data.end_time)

        week_start  = data.booking_date - timedelta(days=data.booking_date.weekday())
        week_end    = week_start + timedelta(days=6)
        month_start = data.booking_date.replace(day=1)
        month_end   = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        booking_count_week  = self.booking_repo.count_user_bookings_in_period(user.id, amenity.id, week_start, week_end)
        booking_count_month = self.booking_repo.count_user_bookings_in_period(user.id, amenity.id, month_start, month_end)

        meta = engine.validate_booking_request(
            data=data, user=user, user_roles=self._roles(user), conflicts=conflicts, is_blackout=is_blackout,
            booking_count_week=booking_count_week, booking_count_month=booking_count_month,
            now=self._now(amenity.society_id))

        needs_approval = meta["needs_approval"] or amenity.approval_required
        status = BookingStatus.PENDING if needs_approval else BookingStatus.APPROVED
        charge, deposit = self._charges(amenity, meta, data)

        values = {**data.model_dump(), "society_id": amenity.society_id, "flat_id": flat_id}
        booking = AmenityBooking(**values, booked_by=user.id, status=status, charge_amount=charge, deposit_amount=deposit)
        self.db.add(booking)
        self.db.flush()
        self._audit(AuditAction.CREATE, booking, "AmenityBooking", user, request,
                    new_values={"amenity": str(amenity.id), "date": str(data.booking_date), "status": status.value})
        if status == BookingStatus.PENDING:
            NotificationService.send(
                db=self.db, user_id=user.id, title="Booking Pending Approval",
                body=f"Your booking for {amenity.name} on {data.booking_date} is awaiting approval.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="amenity", entity_id=str(booking.id))
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def approve_booking(self, booking_id: UUID, data: BookingApproveRequest, user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id, user)
        self._validate_transition(booking, BookingStatus.APPROVED)
        # Things may have changed since it was asked for.
        if datetime.combine(booking.booking_date, booking.end_time) <= self._now(booking.society_id):
            raise HTTPException(409, "That time has passed. Reject the booking instead.")
        if self.blackout_repo.is_blackout(booking.amenity_id, booking.booking_date):
            raise HTTPException(409, "The amenity has been closed on that date. Reject the booking instead.")
        clash = [c for c in self.booking_repo.get_conflicts(booking.amenity_id, booking.booking_date,
                                                            booking.start_time, booking.end_time) if c.id != booking.id
                 and c.status == BookingStatus.APPROVED]
        if clash:
            raise HTTPException(409, "Another approved booking overlaps this time.")
        booking.status = BookingStatus.APPROVED
        booking.approved_by = user.id
        booking.approved_at = datetime.utcnow()
        self._audit(AuditAction.APPROVE, booking, "AmenityBooking", user, request, new_values={"status": "approved"})
        NotificationService.send(
            db=self.db, user_id=booking.booked_by, title="Booking Approved",
            body="Your amenity booking has been approved.", type=NotificationType.INFO,
            channel=NotificationChannel.IN_APP, module="amenity", entity_id=str(booking.id))
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def reject_booking(self, booking_id: UUID, data: BookingRejectRequest, user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id, user)
        self._validate_transition(booking, BookingStatus.REJECTED)
        reason = (data.reason or "").strip()
        if not reason:
            raise HTTPException(422, "Say why, so the resident knows")
        booking.status = BookingStatus.REJECTED
        booking.rejection_reason = reason
        booking.approved_by = user.id
        booking.approved_at = datetime.utcnow()
        self._audit(AuditAction.REJECT, booking, "AmenityBooking", user, request,
                    new_values={"status": "rejected", "reason": reason})
        NotificationService.send(
            db=self.db, user_id=booking.booked_by, title="Booking Rejected",
            body=f"Your amenity booking was rejected. Reason: {reason}", type=NotificationType.WARNING,
            channel=NotificationChannel.IN_APP, module="amenity", entity_id=str(booking.id))
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def cancel_booking(self, booking_id: UUID, data: BookingCancelRequest, user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id, user)
        if booking.booked_by != user.id and not self._manages(user):
            raise HTTPException(403, "Only the person who booked it, or the committee, can cancel a booking")
        self._validate_transition(booking, BookingStatus.CANCELLED)
        if (not self._manages(user)
                and datetime.combine(booking.booking_date, booking.start_time) <= self._now(booking.society_id)):
            raise HTTPException(409, "It has already started. Ask the committee.")
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = (data.reason or "").strip() or None
        self._audit(AuditAction.UPDATE, booking, "AmenityBooking", user, request, new_values={"status": "cancelled"})
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def complete_booking(self, booking_id: UUID, usage_data: UsageLogCreate, user: User, request=None) -> AmenityBooking:
        booking = self._get_booking_or_404(booking_id, user)
        self._validate_transition(booking, BookingStatus.COMPLETED)
        if datetime.combine(booking.booking_date, booking.start_time) > self._now(booking.society_id):
            raise HTTPException(409, "It hasn't started yet")
        if usage_data.damage_noted and not (usage_data.damage_notes or "").strip():
            raise HTTPException(422, "Say what was damaged")
        if usage_data.extra_charges is not None and usage_data.extra_charges < 0:
            raise HTTPException(422, "A charge can't be negative")
        booking.status = BookingStatus.COMPLETED
        self.db.add(AmenityUsageLog(booking_id=booking.id, amenity_id=booking.amenity_id,
                                    society_id=booking.society_id, used_by=booking.booked_by,
                                    **usage_data.model_dump()))
        self._audit(AuditAction.UPDATE, booking, "AmenityBooking", user, request,
                    new_values={"status": "completed", "damage_noted": usage_data.damage_noted})
        self.db.commit()
        self.db.refresh(booking)
        return booking

    # ── Queries ───────────────────────────────────────────────────────────────

    def out(self, bookings: List[AmenityBooking]) -> List[dict]:
        """Bookings with the names a screen shows: the amenity, who booked, which flat, who decided."""
        labels = self._flat_labels([b.flat_id for b in bookings])
        rows = []
        for b in bookings:
            d = BookingOut.model_validate(b).model_dump(mode="json")
            d.update({
                "amenity_name": b.amenity.name if b.amenity else None,
                "booked_by_name": b.booker.full_name if b.booker else None,
                "flat": labels.get(b.flat_id),
                "approved_by_name": b.approver.full_name if b.approver else None,
                "special_notes": b.special_notes,
                "cancellation_reason": b.cancellation_reason,
            })
            rows.append(d)
        return rows

    def get_booking(self, booking_id: UUID, user: User) -> dict:
        b = self._get_booking_or_404(booking_id, user)
        if b.booked_by != user.id and not self._manages(user):
            raise HTTPException(404, "Booking not found")
        return self.out([b])[0]

    def my_bookings(self, user: User, skip: int = 0, limit: int = 50) -> List[dict]:
        return self.out(self.booking_repo.get_by_user(user.id, skip, limit))

    def society_bookings(self, society_id: UUID, user: User, skip: int = 0, limit: int = 50,
                         status: Optional[str] = None, amenity_id: Optional[UUID] = None,
                         date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[dict]:
        assert_society_access(user, society_id)
        q = self.db.query(AmenityBooking).filter(AmenityBooking.society_id == society_id, AmenityBooking.is_active == True)
        if status:
            q = q.filter(AmenityBooking.status == status)
        if amenity_id:
            q = q.filter(AmenityBooking.amenity_id == amenity_id)
        if date_from:
            q = q.filter(AmenityBooking.booking_date >= date_from)
        if date_to:
            q = q.filter(AmenityBooking.booking_date <= date_to)
        rows = q.order_by(AmenityBooking.booking_date.desc(), AmenityBooking.start_time.desc()).offset(skip).limit(limit).all()
        return self.out(rows)

    def pending_bookings(self, society_id: UUID, user: User) -> List[dict]:
        assert_society_access(user, society_id)
        rows = self.booking_repo.get_pending(society_id)
        rows.sort(key=lambda b: (b.booking_date, b.start_time))
        return self.out(rows)
