from datetime import date, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.society import Society, AccountStatus, ACCOUNT_STATUS_TRANSITIONS
from app.models.audit_log import AuditAction
from app.models.user import User
from app.services.audit_service import AuditService


class PlatformAdminService:

    def __init__(self, db: Session):
        self.db = db

    # ── Society listing ───────────────────────────────────────────────────────

    def list_societies(self, skip: int = 0, limit: int = 50) -> list:
        societies = (
            self.db.query(Society)
            .filter(Society.is_active == True)
            .order_by(Society.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        today = date.today()
        result = []
        for s in societies:
            days_remaining = 0
            if s.trial_end_date:
                days_remaining = max(0, (s.trial_end_date - today).days)
            result.append({
                "id":                          str(s.id),
                "name":                        s.name,
                "society_code":                s.society_code,
                "city":                        s.city,
                "account_status":              s.account_status.value if s.account_status else "TRIAL",
                "is_trial":                    s.is_trial,
                "trial_end_date":              str(s.trial_end_date) if s.trial_end_date else None,
                "trial_days_remaining":        days_remaining,
                "setup_completed":             s.setup_completed,
                "setup_completion_percentage": s.setup_completion_percentage,
                "total_flats":                 s.total_flats,
                "created_at":                  str(s.created_at.date()) if s.created_at else None,
            })
        return result

    # ── Platform stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        today = date.today()
        cutoff = today + timedelta(days=7)

        all_societies = (
            self.db.query(Society)
            .filter(Society.is_active == True)
            .all()
        )

        total      = len(all_societies)
        trial      = sum(1 for s in all_societies if s.account_status == AccountStatus.TRIAL)
        active     = sum(1 for s in all_societies if s.account_status == AccountStatus.ACTIVE)
        expired    = sum(1 for s in all_societies if s.account_status == AccountStatus.EXPIRED)
        suspended  = sum(1 for s in all_societies if s.account_status == AccountStatus.SUSPENDED)
        expiring   = sum(
            1 for s in all_societies
            if s.account_status == AccountStatus.TRIAL
            and s.trial_end_date
            and today <= s.trial_end_date <= cutoff
        )

        return {
            "total_societies":    total,
            "trial_societies":    trial,
            "active_societies":   active,
            "expired_societies":  expired,
            "suspended_societies": suspended,
            "expiring_soon":      expiring,
        }

    # ── Extend trial ──────────────────────────────────────────────────────────

    def extend_trial(self, society_id: str, days: int, admin: User) -> dict:
        society = self._get_society(society_id)

        if society.account_status not in (AccountStatus.TRIAL, AccountStatus.EXPIRED):
            raise HTTPException(
                status_code=400,
                detail=f"Trial can only be extended for TRIAL or EXPIRED societies, not {society.account_status.value}"
            )

        old_end = society.trial_end_date
        base    = max(old_end, date.today()) if old_end else date.today()
        society.trial_end_date  = base + timedelta(days=days)
        society.account_status  = AccountStatus.TRIAL
        society.is_trial        = True

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE,
            module="platform_admin", entity_id=str(society.id),
            entity_type="Society", user=admin,
            new_values={
                "event":        "trial_extended",
                "extend_days":  days,
                "old_end_date": str(old_end),
                "new_end_date": str(society.trial_end_date),
            },
        )
        self.db.commit()

        return {
            "society_id":      str(society.id),
            "trial_end_date":  str(society.trial_end_date),
            "account_status":  society.account_status.value,
            "message":         f"Trial extended by {days} days.",
        }

    # ── Suspend society ───────────────────────────────────────────────────────

    def suspend_society(self, society_id: str, reason: str, admin: User) -> dict:
        society = self._get_society(society_id)
        self._transition(society, AccountStatus.SUSPENDED)

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE,
            module="platform_admin", entity_id=str(society.id),
            entity_type="Society", user=admin,
            new_values={"event": "society_suspended", "reason": reason},
        )
        self.db.commit()

        return {
            "society_id":     str(society.id),
            "account_status": society.account_status.value,
            "message":        "Society has been suspended.",
        }

    # ── Activate society ──────────────────────────────────────────────────────

    def activate_society(self, society_id: str, plan: str, admin: User) -> dict:
        society = self._get_society(society_id)
        self._transition(society, AccountStatus.ACTIVE)

        society.is_trial             = False
        society.subscription_plan    = plan
        society.subscription_status  = "active"
        society.subscription_start_date   = date.today()

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE,
            module="platform_admin", entity_id=str(society.id),
            entity_type="Society", user=admin,
            new_values={"event": "society_activated", "plan": plan},
        )
        self.db.commit()

        return {
            "society_id":        str(society.id),
            "account_status":    society.account_status.value,
            "subscription_plan": society.subscription_plan,
            "message":           f"Society activated on {plan} plan.",
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_society(self, society_id: str) -> Society:
        import uuid as _uuid
        try:
            uid = _uuid.UUID(str(society_id))
        except ValueError:
            raise HTTPException(status_code=404, detail="Society not found")
        society = (
            self.db.query(Society)
            .filter(Society.id == uid, Society.is_active == True)
            .first()
        )
        if not society:
            raise HTTPException(status_code=404, detail="Society not found")
        return society

    def _transition(self, society: Society, new_status: AccountStatus):
        allowed = ACCOUNT_STATUS_TRANSITIONS.get(society.account_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {society.account_status.value} to {new_status.value}",
            )
        society.account_status = new_status
