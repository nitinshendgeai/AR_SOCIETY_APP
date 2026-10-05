import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest, SessionOut,
)
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.services.password_reset_service import PasswordResetService
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user (default role: Resident)."""
    service = AuthService(db)
    user = service.register(data)
    return UserOut.from_orm_with_roles(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and receive JWT tokens. Each sign-in is a device session the user can see and end."""
    service = AuthService(db)
    return service.login(data, request)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Rotate tokens using a valid refresh token. Fails once the device has been signed out."""
    service = AuthService(db)
    return service.refresh(data.refresh_token, request)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return UserOut.from_orm_with_roles(current_user)


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for the currently authenticated user."""
    AuthService(db).change_password(current_user, data)


# ── Signed-in devices ─────────────────────────────────────────────────────────

def _session_out(row, current_id) -> SessionOut:
    return SessionOut(id=str(row.id), device=row.device, ip_address=row.ip_address, signed_in_at=row.created_at,
                      last_seen_at=row.last_seen_at, current=str(row.id) == str(current_id))


@router.post("/logout", status_code=204)
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sign this device out: its tokens stop working immediately."""
    sessions = SessionService(db)
    session = sessions.get(getattr(current_user, "current_session_id", None))
    if session is not None:
        sessions.revoke(session, "logout")
        db.commit()


@router.get("/sessions", response_model=List[SessionOut])
def my_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The devices currently signed in to this account, newest activity first."""
    current = getattr(current_user, "current_session_id", None)
    return [_session_out(r, current) for r in SessionService(db).live_for(current_user.id)]


@router.post("/sessions/revoke-others", status_code=204)
def sign_out_other_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sign out every device except this one."""
    SessionService(db).revoke_all(current_user.id, "signed_out",
                                  keep=getattr(current_user, "current_session_id", None))
    db.commit()


@router.delete("/sessions/{session_id}", status_code=204)
def sign_out_device(session_id: uuid.UUID, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Sign out one of your devices."""
    sessions = SessionService(db)
    session = sessions.get(session_id)
    if session is None or str(session.user_id) != str(current_user.id) or session.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Device not found")
    sessions.revoke(session, "signed_out")
    db.commit()


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)   # email or mobile, as on the login screen


FORGOT_PASSWORD_REPLY = {
    "message": "If an account exists for these details, your society office has been asked to reset "
               "your password. They will give you a temporary password to sign in with.",
}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Login screen "Forgot password?": asks the society's admins to reset the
    password. Same reply whether or not the account exists."""
    PasswordResetService(db).request_reset(data.identifier)
    return FORGOT_PASSWORD_REPLY
