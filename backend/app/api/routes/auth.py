from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
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
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    service = AuthService(db)
    return service.login(data)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate tokens using a valid refresh token."""
    service = AuthService(db)
    return service.refresh(data.refresh_token)


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
