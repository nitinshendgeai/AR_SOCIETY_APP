from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status
from typing import Optional

from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, ChangePasswordRequest, LoginChoiceResponse, SocietyChoice,
)
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
        # Self-registration creates a login that belongs to no society yet: only active users count
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

    # ── Signing in ────────────────────────────────────────────────────────────

    @staticmethod
    def _blocked(user: User) -> Optional[tuple]:
        """(status code, message) if this login can't be used right now, else None. Only an active user of an active
        society can sign in."""
        if user.status != UserStatus.ACTIVE:
            return 403, f"Account is {user.status.value}"
        if not user.is_active:
            return 401, "User account is disabled"
        return None

    def _usable(self, users):
        """The logins among `users` that can be signed in to, and the first reason the others can't."""
        from app.core.society_gate import society_block_reason
        usable, first_reason = [], None
        for u in users:
            reason = self._blocked(u) or ((403, r) if (r := society_block_reason(self.db, u)) else None)
            if reason is None:
                usable.append(u)
            elif first_reason is None:
                first_reason = reason
        return usable, first_reason

    def _choices(self, users, current_id=None):
        from app.models.society import Society
        out = []
        for u in users:
            name = ("Platform console" if u.society_id is None else
                    self.db.query(Society.name).filter(Society.id == u.society_id).scalar() or "Society")
            out.append(SocietyChoice(society_id=str(u.society_id) if u.society_id else None, society_name=name,
                                     roles=self.repo.get_roles(u), current=str(u.id) == str(current_id)))
        return out

    def _issue(self, user: User, peers, request, notes="Login successful") -> TokenResponse:
        """Start a device session for `user` and mint its tokens. `peers` are the ids of the other logins of this
        person (other societies) that the password was proved for, kept in the token so they can switch."""
        roles = self.repo.get_roles(user)
        session = SessionService(self.db).start(
            user, AuditService._get_ua(request), AuditService._get_ip(request))
        extra = {"roles": roles}
        peer_ids = [str(p) for p in peers] if len(peers) > 1 else []
        if peer_ids:
            extra["peers"] = peer_ids
        access  = create_access_token(str(user.id), extra, session_id=str(session.id))
        refresh = create_refresh_token(str(user.id), session_id=str(session.id),
                                       extra={"peers": peer_ids} if peer_ids else None)
        user.last_login = datetime.utcnow()
        self.db.commit()
        AuditService.log(
            db=self.db, action=AuditAction.LOGIN, module="auth",
            entity_id=str(user.id), entity_type="User",
            user=user, request=request, notes=notes,
        )
        logger.info(f"[auth] {notes}: {user.email} roles={roles}")
        return TokenResponse(access_token=access, refresh_token=refresh)

    def login(self, data: LoginRequest, request: Optional[Request] = None):
        """Sign in with an email or mobile number. A person who belongs to several societies has one login in each;
        only active users of active societies whose password matches can be signed in to. One match signs in; several
        answer with the list to choose from (the app sends the same credentials again with `society_id`)."""
        candidates = self.repo.candidates(data.email)[:10]

        # Avoid timing oracle — always verify even on not-found
        if not candidates:
            verify_password(data.password, "$2b$12$KIXoRuQ5zGMVPLNNWqaT5OGqb0ZjU8emfJQQn5PxbWm94PdADk6Ou")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/mobile number or password",
            )

        # Failed attempts are counted against the first login so every society's login shares one lock-out.
        primary = candidates[0]
        if self._too_many_failures(primary):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed sign-in attempts. Please wait 15 minutes and try again.",
            )

        matched = [u for u in candidates if verify_password(data.password, u.hashed_password)]
        if not matched:
            # Audit: failed login
            AuditService.log(
                db=self.db, action=AuditAction.LOGIN, module="auth",
                entity_id=str(primary.id), entity_type="User",
                notes=FAILED_LOGIN_NOTE, request=request,
            )
            logger.warning(f"[auth] Failed login attempt: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/mobile number or password",
            )

        usable, reason = self._usable(matched)
        if not usable:
            code, message = reason
            raise HTTPException(status_code=code, detail=message)

        if data.society_id is not None:
            chosen = [u for u in usable if u.society_id == data.society_id]
            if not chosen:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="You can't sign in to that society with these details")
            user = chosen[0]
        elif len(usable) > 1:
            return LoginChoiceResponse(choices=self._choices(usable))
        else:
            user = usable[0]

        return self._issue(user, [u.id for u in usable], request)

    @staticmethod
    def _uuids(values) -> set:
        import uuid as _uuid
        out = set()
        for v in values:
            try:
                out.add(v if isinstance(v, _uuid.UUID) else _uuid.UUID(str(v)))
            except (ValueError, AttributeError, TypeError):
                continue
        return out

    def societies_for(self, user: User) -> list:
        """The societies this signed-in person can switch between (including the current one), only while each is
        still active; empty when there is just the one."""
        peer_ids = self._uuids(getattr(user, "peer_ids", None) or []) | {user.id}
        if len(peer_ids) < 2:
            return []
        rows = self.db.query(User).filter(User.id.in_(list(peer_ids)), User.is_active == True).all()  # noqa: E712
        usable, _ = self._usable(rows)
        if len(usable) < 2:
            return []
        usable.sort(key=lambda u: (u.created_at, str(u.id)))
        return [c.model_dump() for c in self._choices(usable, current_id=user.id)]

    def switch_society(self, user: User, society_id, request: Optional[Request] = None) -> TokenResponse:
        """Move to this person's login in another society, without asking for the password again. Only the logins the
        password was proved for at sign-in (carried in the token) can be switched to, and only while still active."""
        peer_ids = self._uuids(getattr(user, "peer_ids", None) or [])
        target = None
        if peer_ids:
            rows = self.db.query(User).filter(User.id.in_(list(peer_ids)), User.society_id == society_id,
                                              User.is_active == True).all()  # noqa: E712
            usable, _ = self._usable(rows)
            target = usable[0] if usable else None
        if target is None or target.id == user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't switch to that society")
        # The device keeps one session: end this one, the new one carries on with the same peers.
        sessions = SessionService(self.db)
        old = sessions.get(getattr(user, "current_session_id", None))
        if old is not None:
            sessions.revoke(old, "switched_society")
        return self._issue(target, list(peer_ids | {user.id}), request, notes="Switched society")

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
        peers       = payload.get("peers") or []
        extra       = {"roles": roles, **({"peers": peers} if peers else {})}
        new_access  = create_access_token(str(user.id), extra, session_id=str(session.id))
        new_refresh = create_refresh_token(str(user.id), session_id=str(session.id),
                                           extra={"peers": peers} if peers else None)
        return TokenResponse(access_token=new_access, refresh_token=new_refresh)
