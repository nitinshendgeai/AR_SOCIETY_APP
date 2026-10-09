from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status
from typing import Optional

from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, ChangePasswordRequest
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.session_service import SessionService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# After this many wrong passwords for one account within the window, further sign-ins (even with the right
# password) are refused until the window passes. Counted from the audit log, so it holds across restarts
# and workers, and never says whether the account exists.
MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW = timedelta(minutes=15)
FAILED_LOGIN_NOTE = "Failed login attempt"


class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)
        self.db   = db

    def register(self, data: RegisterRequest) -> User:
        if self.repo.get_by_email(data.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        if data.phone and self.repo.get_by_phone(data.phone):
            raise HTTPException(status_code=400, detail="Phone already registered")

        user = User(
            email=data.email, phone=data.phone, full_name=data.full_name,
            hashed_password=hash_password(data.password),
            status=UserStatus.ACTIVE,
        )
        user = self.repo.create(user)
        self.repo.assign_role(user, "Resident")

        # Audit: user registered
        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="auth",
            entity_id=str(user.id), entity_type="User",
            new_values={"email": user.email, "event": "registration"},
        )
        logger.info(f"[auth] New registration: {user.email}")
        return user

    def login(self, data: LoginRequest, request: Optional[Request] = None) -> TokenResponse:
        user = self.repo.get_by_email_or_phone(data.email)

        # Avoid timing oracle — always verify even on not-found
        if not user:
            verify_password(data.password, "$2b$12$KIXoRuQ5zGMVPLNNWqaT5OGqb0ZjU8emfJQQn5PxbWm94PdADk6Ou")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/mobile number or password",
            )

        if self._too_many_failures(user):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed sign-in attempts. Please wait 15 minutes and try again.",
            )

        if not verify_password(data.password, user.hashed_password):
            # Audit: failed login
            AuditService.log(
                db=self.db, action=AuditAction.LOGIN, module="auth",
                entity_id=str(user.id), entity_type="User",
                notes=FAILED_LOGIN_NOTE, request=request,
            )
            logger.warning(f"[auth] Failed login attempt: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/mobile number or password",
            )

        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=403,
                detail=f"Account is {user.status.value}",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
            )

        from app.core.society_gate import society_block_reason
        blocked = society_block_reason(self.db, user)
        if blocked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=blocked)

        roles = self.repo.get_roles(user)
        session = SessionService(self.db).start(
            user, AuditService._get_ua(request), AuditService._get_ip(request))
        access  = create_access_token(str(user.id), {"roles": roles}, session_id=str(session.id))
        refresh = create_refresh_token(str(user.id), session_id=str(session.id))

        # Record last login timestamp
        user.last_login = datetime.utcnow()
        self.db.commit()

        # Audit: successful login
        AuditService.log(
            db=self.db, action=AuditAction.LOGIN, module="auth",
            entity_id=str(user.id), entity_type="User",
            user=user, request=request,
            notes="Login successful",
        )
        logger.info(f"[auth] Login: {user.email} roles={roles}")
        return TokenResponse(access_token=access, refresh_token=refresh)

    def _too_many_failures(self, user: User) -> bool:
        from app.models.audit_log import AuditLog
        since = datetime.utcnow() - FAILED_LOGIN_WINDOW
        failures = self.db.query(AuditLog).filter(
            AuditLog.entity_id == str(user.id), AuditLog.module == "auth",
            AuditLog.action == AuditAction.LOGIN, AuditLog.notes == FAILED_LOGIN_NOTE,
            AuditLog.created_at >= since,
        ).count()
        return failures >= MAX_FAILED_LOGINS

    def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.hashed_password = hash_password(data.new_password)
        user.must_change_password = False
        # Whoever else is signed in with the old password is signed out; this device stays.
        SessionService(self.db).revoke_all(user.id, "password_changed", keep=getattr(user, "current_session_id", None))
        self.db.commit()
        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="auth",
            entity_id=str(user.id), entity_type="User",
            user=user, notes="Password changed",
        )
        logger.info(f"[auth] Password changed: {user.email}")

    def refresh(self, refresh_token: str, request: Optional[Request] = None) -> TokenResponse:
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")
        try:
            import uuid as _uuid
            uid = _uuid.UUID(str(user_id))
            user = self.repo.get(uid)
        except (ValueError, AttributeError):
            user = None

        if not user:
            user = self.repo.get(user_id)

        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        from app.core.society_gate import society_block_reason
        blocked = society_block_reason(self.db, user)
        if blocked:
            raise HTTPException(status_code=403, detail=blocked)

        sessions = SessionService(self.db)
        sid = payload.get("sid")
        if sid:
            session = sessions.get(sid)
            if not sessions.is_live(session, user.id):
                raise HTTPException(status_code=401, detail="This device has been signed out")
            sessions.touch(session)
        else:
            # A token from before sessions existed: swap it for session-bound tokens.
            session = sessions.start(user, AuditService._get_ua(request), AuditService._get_ip(request))
            self.db.commit()

        roles       = self.repo.get_roles(user)
        new_access  = create_access_token(str(user.id), {"roles": roles}, session_id=str(session.id))
        new_refresh = create_refresh_token(str(user.id), session_id=str(session.id))
        return TokenResponse(access_token=new_access, refresh_token=new_refresh)
