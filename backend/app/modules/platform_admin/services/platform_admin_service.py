from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.society import Society, AccountStatus, ACCOUNT_STATUS_TRANSITIONS
from app.models.audit_log import AuditAction, AuditLog
from app.models.flat import Flat
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.wing import Wing
from app.services.audit_service import AuditService


class PlatformAdminService:

    def __init__(self, db: Session):
        self.db = db

    # ── Society listing ───────────────────────────────────────────────────────

    def _usage(self, society_ids: list) -> dict:
        """Users, flats and the last sign-in for each society, in three queries."""
        if not society_ids:
            return {}
        users = dict(self.db.query(User.society_id, func.count(User.id))
                     .filter(User.society_id.in_(society_ids), User.is_active == True)
                     .group_by(User.society_id).all())
        last = dict(self.db.query(User.society_id, func.max(User.last_login))
                    .filter(User.society_id.in_(society_ids)).group_by(User.society_id).all())
        flats = dict(self.db.query(Wing.society_id, func.count(Flat.id))
                     .join(Flat, Flat.wing_id == Wing.id)
                     .filter(Wing.society_id.in_(society_ids), Flat.is_active == True)
                     .group_by(Wing.society_id).all())
        return {sid: {"users": users.get(sid, 0), "flats": flats.get(sid, 0), "last_login": last.get(sid)}
                for sid in society_ids}

    @staticmethod
    def _row(s: Society, usage: dict, today: date) -> dict:
        days_remaining = max(0, (s.trial_end_date - today).days) if s.trial_end_date else 0
        status = s.account_status.value if s.account_status else "TRIAL"
        u = usage.get(s.id, {})
        return {
            "id":                          str(s.id),
            "name":                        s.name,
            "society_code":                s.society_code,
            "city":                        s.city,
            "state":                       s.state,
            "account_status":              status,
            "is_trial":                    s.is_trial,
            "trial_end_date":              str(s.trial_end_date) if s.trial_end_date else None,
            "trial_days_remaining":        days_remaining,
            # the trial date has passed but nobody has marked it expired yet
            "trial_ended":                 bool(status == "TRIAL" and s.trial_end_date and s.trial_end_date < today),
            "subscription_plan":           s.subscription_plan,
            "subscription_expiry_date":    str(s.subscription_expiry_date) if s.subscription_expiry_date else None,
            "setup_completed":             s.setup_completed,
            "setup_completion_percentage": s.setup_completion_percentage,
            "total_flats":                 s.total_flats,
            "user_count":                  u.get("users", 0),
            "flat_count":                  u.get("flats", 0),
            "allowed_users":               s.allowed_users,
            "allowed_flats":               s.allowed_flats,
            "last_login":                  u["last_login"].isoformat() if u.get("last_login") else None,
            "contact_person_name":         s.contact_person_name,
            "contact_email":               s.contact_email,
            "contact_phone":               s.contact_phone,
            "created_at":                  str(s.created_at.date()) if s.created_at else None,
        }

    def list_societies(self, skip: int = 0, limit: int = 50, q: Optional[str] = None,
                       status: Optional[str] = None) -> list:
        query = self.db.query(Society).filter(Society.is_active == True)
        if q and q.strip():
            like = f"%{q.strip()}%"
            query = query.filter((Society.name.ilike(like)) | (Society.society_code.ilike(like))
                                 | (Society.city.ilike(like)) | (Society.contact_email.ilike(like)))
        if status:
            try:
                query = query.filter(Society.account_status == AccountStatus(status.upper()))
            except ValueError:
                raise HTTPException(status_code=422, detail="Unknown status")
        societies = query.order_by(Society.created_at.desc()).offset(skip).limit(limit).all()
        usage = self._usage([s.id for s in societies])
        today = date.today()
        return [self._row(s, usage, today) for s in societies]

    # ── One society ───────────────────────────────────────────────────────────

    def society_detail(self, society_id: str) -> dict:
        society = self._get_society(society_id)
        usage = self._usage([society.id])
        row = self._row(society, usage, date.today())
        admins = (self.db.query(User).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
                  .filter(User.society_id == society.id, Role.name == "Society Admin").order_by(User.full_name).all())
        row.update({
            "address":       society.address,
            "pincode":       society.pincode,
            "timezone":      society.timezone,
            "registration_number": society.registration_number,
            "subscription_status": society.subscription_status,
            "subscription_start_date": str(society.subscription_start_date) if society.subscription_start_date else None,
            "trial_start_date": str(society.trial_start_date) if society.trial_start_date else None,
            "allowed_storage_mb": society.allowed_storage_mb,
            "wings": self.db.query(func.count(Wing.id)).filter(Wing.society_id == society.id, Wing.is_active == True).scalar() or 0,
            "admins": [{
                "id": str(a.id), "name": a.full_name, "email": a.email, "phone": a.phone,
                "status": a.status.value if a.status else None,
                "last_login": a.last_login.isoformat() if a.last_login else None,
            } for a in admins],
            "history": self.activity(society_id=str(society.id), limit=20),
        })
        return row

    # ── What platform admins have done ────────────────────────────────────────

    def activity(self, limit: int = 50, society_id: Optional[str] = None) -> list:
        q = self.db.query(AuditLog).filter(AuditLog.module == "platform_admin")
        if society_id:
            q = q.filter(AuditLog.entity_id == str(society_id))
        logs = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
        names = {}
        ids = {l.entity_id for l in logs if l.entity_id}
        if ids:
            for sid, name in self.db.query(Society.id, Society.name).all():
                names[str(sid)] = name
        rows = []
        for l in logs:
            nv = l.new_values or {}
            rows.append({
                "id": str(l.id),
                "at": l.created_at.isoformat() if l.created_at else None,
                "by": l.user.full_name if l.user else l.user_email,
                "society_id": l.entity_id,
                "society_name": names.get(str(l.entity_id)),
                "event": nv.get("event"),
                "details": {k: v for k, v in nv.items() if k != "event"},
            })
        return rows

    # ── Limits ────────────────────────────────────────────────────────────────

    def set_limits(self, society_id: str, users: int, flats: int, storage_mb: int, admin: User) -> dict:
        society = self._get_society(society_id)
        usage = self._usage([society.id]).get(society.id, {})
        if users < usage.get("users", 0):
            raise HTTPException(status_code=409, detail=f"The society already has {usage['users']} users. Choose at least that many.")
        if flats < usage.get("flats", 0):
            raise HTTPException(status_code=409, detail=f"The society already has {usage['flats']} flats. Choose at least that many.")
        old = {"users": society.allowed_users, "flats": society.allowed_flats, "storage_mb": society.allowed_storage_mb}
        society.allowed_users, society.allowed_flats, society.allowed_storage_mb = users, flats, storage_mb
        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="platform_admin", entity_id=str(society.id),
            entity_type="Society", user=admin,
            new_values={"event": "limits_changed", "old": old, "new": {"users": users, "flats": flats, "storage_mb": storage_mb}},
        )
        self.db.commit()
        return {"society_id": str(society.id), "allowed_users": users, "allowed_flats": flats,
                "allowed_storage_mb": storage_mb, "message": "Limits saved."}

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

        today_ended = sum(1 for s in all_societies if s.account_status == AccountStatus.TRIAL
                          and s.trial_end_date and s.trial_end_date < today)
        total_users = self.db.query(func.count(User.id)).filter(User.society_id.isnot(None), User.is_active == True).scalar() or 0
        total_flats = (self.db.query(func.count(Flat.id)).join(Wing, Wing.id == Flat.wing_id)
                       .filter(Flat.is_active == True).scalar() or 0)
        return {
            "trial_ended_not_marked": today_ended,
            "total_users":        total_users,
            "total_flats":        total_flats,
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

    def activate_society(self, society_id: str, plan: str, admin: User, expires_on: Optional[date] = None) -> dict:
        society = self._get_society(society_id)
        if expires_on is not None and expires_on <= date.today():
            raise HTTPException(status_code=422, detail="The subscription must end after today")
        self._transition(society, AccountStatus.ACTIVE)

        society.is_trial             = False
        society.subscription_plan    = plan
        society.subscription_status  = "active"
        society.subscription_start_date   = date.today()
        if expires_on is not None:
            society.subscription_expiry_date = expires_on

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE,
            module="platform_admin", entity_id=str(society.id),
            entity_type="Society", user=admin,
            new_values={"event": "society_activated", "plan": plan, "expires_on": str(expires_on) if expires_on else None},
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
