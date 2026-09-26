"""
PasswordResetService — "Forgot password?" from the login screen.

A member who can't sign in enters their email or mobile number. Residents
sign in by mobile and have no real email (their accounts carry a
placeholder address), and no SMS/email provider is set up, so the reset
goes through the society's admins: the request notifies them (in-app, and
pushed when Firebase is configured); an admin resets the password from the
Password Reset Requests list and gives the member the temporary password,
which must be changed at the next sign-in.

The public endpoint answers the same way whether or not the account exists,
so it can't be used to find out which numbers/emails have accounts.
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.notification import NotificationType
from app.models.password_reset_request import PasswordResetRequest, PasswordResetStatus
from app.models.permission import Permission, RolePermission
from app.models.resident import Resident
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User, UserRole, UserStatus
from app.repositories.user_repo import UserRepository
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

# Where the admins' list lives in the app (a tap on the notification opens it).
REQUESTS_ROUTE = "/users/password-requests"
PLACEHOLDER_EMAIL_DOMAIN = "@duxos.local"


class PasswordResetService:

    def __init__(self, db: Session):
        self.db = db

    # ── Member side (public) ──────────────────────────────────────────────────

    def request_reset(self, identifier: str) -> None:
        """Record a request for the account `identifier` signs in with and
        tell the society's admins. Silent when there's no such active account.
        A request already pending isn't duplicated (and admins aren't
        notified again) — asking twice just refreshes it."""
        user = UserRepository(self.db).get_by_email_or_phone(identifier)
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            logger.info("[password-reset] request for unknown/inactive account")
            return

        pending = self.db.query(PasswordResetRequest).filter(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.status == PasswordResetStatus.PENDING,
            PasswordResetRequest.is_active == True,
        ).first()
        if pending:
            pending.updated_at = datetime.utcnow()
            self.db.commit()
            return

        req = PasswordResetRequest(user_id=user.id, society_id=user.society_id,
                                   identifier=identifier.strip()[:255])
        self.db.add(req)
        self.db.commit()

        who = _display_contact(user)
        for admin in self._admins(user.society_id):
            NotificationService.send(
                db=self.db, user_id=admin.id,
                title="Password reset requested",
                body=f"{user.full_name}{f' ({who})' if who else ''} can't sign in and asked for a new password.",
                type=NotificationType.APPROVAL,
                module="auth", entity_id=str(req.id),
                action_url=REQUESTS_ROUTE, push=True,
            )

    def _admins(self, society_id: Optional[UUID]) -> List[User]:
        """Active users of the society who can reset passwords (the `admin`
        permission — Society Admin)."""
        if society_id is None:
            return []
        return (
            self.db.query(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(Permission.code == "admin", User.society_id == society_id,
                    User.is_active == True, User.status == UserStatus.ACTIVE)
            .distinct().all()
        )

    # ── Admin side ────────────────────────────────────────────────────────────

    def list_requests(self, society_id: Optional[UUID], status: Optional[PasswordResetStatus]) -> List[dict]:
        q = self.db.query(PasswordResetRequest).filter(PasswordResetRequest.is_active == True)
        if society_id is not None:
            q = q.filter(PasswordResetRequest.society_id == society_id)
        if status is not None:
            q = q.filter(PasswordResetRequest.status == status)
        return [self._out(r) for r in q.order_by(PasswordResetRequest.created_at.desc()).limit(200).all()]

    def resolve(self, request_id: UUID, admin: User) -> str:
        """Reset the member's password; returns the temporary password to give them."""
        req = self._get_pending(request_id, admin)
        _, temp_password = UserService(self.db).reset_password(req.user_id, admin.society_id)
        self._close(req, PasswordResetStatus.COMPLETED, admin)
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="auth",
                         entity_id=str(req.user_id), entity_type="User", user=admin,
                         notes="Password reset on the member's Forgot-password request")
        return temp_password

    def dismiss(self, request_id: UUID, admin: User) -> dict:
        req = self._get_pending(request_id, admin)
        self._close(req, PasswordResetStatus.DISMISSED, admin)
        return self._out(req)

    def close_pending_for_user(self, user_id: UUID, admin: User) -> None:
        """An admin reset this user's password some other way (user or staff
        screen): their pending requests are done too."""
        for req in self.db.query(PasswordResetRequest).filter(
                PasswordResetRequest.user_id == user_id,
                PasswordResetRequest.status == PasswordResetStatus.PENDING).all():
            self._close(req, PasswordResetStatus.COMPLETED, admin)

    def _get_pending(self, request_id: UUID, admin: User) -> PasswordResetRequest:
        req = self.db.get(PasswordResetRequest, request_id)
        if not req or not req.is_active or (
                admin.society_id is not None and req.society_id != admin.society_id):
            raise HTTPException(404, "Request not found")
        if req.status != PasswordResetStatus.PENDING:
            raise HTTPException(409, f"This request is already {req.status.value}")
        return req

    def _close(self, req: PasswordResetRequest, status: PasswordResetStatus, admin: User) -> None:
        req.status, req.resolved_by, req.resolved_at = status, admin.id, datetime.utcnow()
        self.db.commit()

    def _out(self, req: PasswordResetRequest) -> dict:
        user = req.user
        return {
            "id": str(req.id),
            "user_id": str(req.user_id),
            "full_name": user.full_name if user else None,
            "contact": _display_contact(user) if user else None,
            "roles": [ur.role.name for ur in user.user_roles if ur.role] if user else [],
            "flats": self._flats(req.user_id),
            "identifier": req.identifier,
            "status": req.status.value,
            "requested_at": req.created_at.isoformat(),
            "last_asked_at": req.updated_at.isoformat(),
            "resolved_by": req.resolver.full_name if req.resolver else None,
            "resolved_at": req.resolved_at.isoformat() if req.resolved_at else None,
        }

    def _flats(self, user_id: UUID) -> List[str]:
        flats = []
        for model in (Resident, Tenant):
            for person in self.db.query(model).filter(model.user_id == user_id, model.is_active == True).all():
                flat = person.flat
                if flat:
                    flats.append(f"{flat.wing.name}-{flat.flat_number}" if flat.wing else flat.flat_number)
        return sorted(set(flats))


def _display_contact(user: User) -> Optional[str]:
    """Mobile and email, leaving out residents' placeholder email."""
    parts = [user.phone] if user.phone else []
    if user.email and not user.email.endswith(PLACEHOLDER_EMAIL_DOMAIN):
        parts.append(user.email)
    return " · ".join(parts) or None
