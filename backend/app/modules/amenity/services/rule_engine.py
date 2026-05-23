"""
AmenityRuleEngine — database-driven policy validation.

Validates booking requests against configured AmenityRule records.
Rules are fetched fresh from DB on each validation — no hardcoding.
Designed to be reusable as a general policy engine in future modules.
"""
from datetime import date, timedelta, datetime, time as dtime
from typing import List
from fastapi import HTTPException
from app.modules.amenity.models.amenity import AmenityRule, RuleType, AmenityBooking
from app.modules.amenity.schemas.amenity import BookingCreate
from app.models.user import User


class AmenityRuleEngine:

    def __init__(self, rules: List[AmenityRule]):
        # Index rules by type for O(1) lookup
        self._rules: dict = {r.rule_type: r for r in rules if r.is_active}

    def _has(self, rule_type: RuleType) -> bool:
        return rule_type in self._rules

    def _val(self, rule_type: RuleType):
        r = self._rules.get(rule_type)
        return r.get_value() if r else None

    # ── Public validation entry point ─────────────────────────────────────────

    def validate_booking_request(
        self,
        data:              BookingCreate,
        user:              User,
        user_roles:        List[str],
        conflicts:         List[AmenityBooking],
        is_blackout:       bool,
        booking_count_week: int,
        booking_count_month: int,
    ) -> dict:
        """
        Run all applicable rules. Returns booking metadata (charge, deposit, needs_approval).
        Raises HTTPException on any violation.
        """
        errors = []

        # 1. Blackout date
        if is_blackout:
            raise HTTPException(status_code=409,
                detail="This amenity is not available on the selected date (blackout period).")

        # 2. Role eligibility
        if self._has(RuleType.OWNERS_ONLY):
            if "Resident" not in user_roles:
                errors.append("This amenity is available to registered residents only.")

        if self._has(RuleType.TENANTS_RESTRICTED):
            # Future: check resident_type from Resident model
            pass

        # 3. Conflict / overlap
        if conflicts:
            raise HTTPException(status_code=409,
                detail=f"Time slot conflict: {len(conflicts)} overlapping booking(s) exist.")

        # 4. Advance booking limits
        today = date.today()
        days_ahead = (data.booking_date - today).days
        if days_ahead < 0:
            errors.append("Cannot book for a past date.")
        if self._has(RuleType.MIN_ADVANCE_HOURS):
            min_hours = self._val(RuleType.MIN_ADVANCE_HOURS)
            booking_dt = datetime.combine(data.booking_date, data.start_time)
            hours_ahead = (booking_dt - datetime.now()).total_seconds() / 3600
            if hours_ahead < min_hours:
                errors.append(f"Booking must be made at least {min_hours} hours in advance.")
        if self._has(RuleType.MAX_ADVANCE_DAYS):
            max_days = self._val(RuleType.MAX_ADVANCE_DAYS)
            if days_ahead > max_days:
                errors.append(f"Cannot book more than {max_days} days in advance.")

        # 5. Duration limit
        if self._has(RuleType.MAX_DURATION_HOURS):
            max_h = self._val(RuleType.MAX_DURATION_HOURS)
            start_dt = datetime.combine(date.today(), data.start_time)
            end_dt   = datetime.combine(date.today(), data.end_time)
            duration_h = (end_dt - start_dt).total_seconds() / 3600
            if duration_h > max_h:
                errors.append(f"Maximum booking duration is {max_h} hour(s). Requested: {duration_h:.1f}h.")

        # 6. Frequency limits
        if self._has(RuleType.MAX_BOOKINGS_PER_WEEK):
            max_w = int(self._val(RuleType.MAX_BOOKINGS_PER_WEEK))
            if booking_count_week >= max_w:
                errors.append(f"Weekly booking limit of {max_w} reached for this amenity.")

        if self._has(RuleType.MAX_BOOKINGS_PER_MONTH):
            max_m = int(self._val(RuleType.MAX_BOOKINGS_PER_MONTH))
            if booking_count_month >= max_m:
                errors.append(f"Monthly booking limit of {max_m} reached for this amenity.")

        # 7. Guest count
        if self._has(RuleType.MAX_GUESTS):
            max_g = int(self._val(RuleType.MAX_GUESTS))
            if data.guest_count > max_g:
                errors.append(f"Maximum {max_g} guests allowed. Requested: {data.guest_count}.")

        if errors:
            raise HTTPException(status_code=422,
                detail={"message": "Booking rule violations", "violations": errors})

        # Calculate charges
        charge  = self._calculate_charge(data)
        deposit = float(self._val(RuleType.DEPOSIT_REQUIRED) or 0) if self._has(RuleType.DEPOSIT_REQUIRED) else None
        needs_approval = self._has(RuleType.APPROVAL_REQUIRED)

        return {"charge_amount": charge, "deposit_amount": deposit, "needs_approval": needs_approval}

    def _calculate_charge(self, data: BookingCreate):
        if not self._has(RuleType.CHARGE_PER_HOUR):
            return None
        rate = float(self._val(RuleType.CHARGE_PER_HOUR))
        start_dt = datetime.combine(date.today(), data.start_time)
        end_dt   = datetime.combine(date.today(), data.end_time)
        hours    = (end_dt - start_dt).total_seconds() / 3600
        return round(rate * hours, 2)

