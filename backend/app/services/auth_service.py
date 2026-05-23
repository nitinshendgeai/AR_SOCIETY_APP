from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse


class AuthService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def register(self, data: RegisterRequest) -> User:
        if self.repo.get_by_email(data.email):
            raise HTTPException(status_code=400, detail="Email already registered")

        if data.phone and self.repo.get_by_phone(data.phone):
            raise HTTPException(status_code=400, detail="Phone already registered")

        user = User(
            email           = data.email,
            phone           = data.phone,
            full_name       = data.full_name,
            hashed_password = hash_password(data.password),
            status          = UserStatus.ACTIVE,
        )
        user = self.repo.create(user)
        self.repo.assign_role(user, "Resident")   # default role
        return user

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.repo.get_by_email(data.email)

        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=403, detail=f"Account is {user.status.value}")

        roles = self.repo.get_roles(user)
        access  = create_access_token(str(user.id), {"roles": roles})
        refresh = create_refresh_token(str(user.id))

        return TokenResponse(access_token=access, refresh_token=refresh)

    def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = self.repo.get(payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")

        roles   = self.repo.get_roles(user)
        access  = create_access_token(str(user.id), {"roles": roles})
        new_refresh = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access, refresh_token=new_refresh)
