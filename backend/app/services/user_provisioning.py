"""
Auto-provisions a mobile-app login for a person (Resident, Tenant, ...) who
is identified in the system only by their mobile number — so an admin
entering a resident's details doesn't have to separately create a User
account before that resident can sign in.

Convention: the mobile number is both the login identifier (see
AuthService.login()'s email-or-phone lookup) and the source of the
placeholder email required by User.email's NOT NULL/UNIQUE constraint.
Each new login gets its own random temporary password (app/core/passwords.py)
with must_change_password=True forced on the account. It is shown once, in the
message returned to the admin who triggered this, and is never stored in the
clear.
"""
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.core.security import hash_password
from app.core.passwords import generate_temp_password


def provision_login_by_phone(
    db: Session,
    *,
    society_id: Optional[UUID],
    phone: str,
    full_name: str,
    role_name: str,
) -> Tuple[User, str]:
    """Create (or reuse) a User account for `phone` and return it alongside
    a human-readable message describing what happened, meant to be surfaced
    to the admin who triggered this (e.g. via a response 'warnings' list)
    since it's the only place the initial password is ever shown."""
    repo = UserRepository(db)
    # The login in *this* society (a person in another society has a login there; this one is separate). A
    # disabled user doesn't hold the number, so a new login is made.
    existing = repo.get_by_phone(phone, society_id=society_id)
    if existing:
        repo.assign_role(existing, role_name)
        return existing, (
            f"A login account already exists for mobile number {phone} in this society — "
            "linked to the existing account."
        )

    temp_password = generate_temp_password()
    user = User(
        society_id=society_id,
        email=f"{role_name.lower()}.{phone}@duxos.local",
        phone=phone,
        full_name=full_name,
        hashed_password=hash_password(temp_password),
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    user = repo.create(user)
    repo.assign_role(user, role_name)
    return user, (
        f"Login created — Mobile Number: {phone}, Password: {temp_password} "
        "(must be changed on first login)."
    )
