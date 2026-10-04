"""
Create (or repair) a Platform Admin: the AR Society operations user who sees
every society (trials, suspend / activate) and belongs to none.

A database that has just been migrated, or emptied with
`python -m app.utils.reset_data`, has no one who can log in; run this once.

    DATABASE_URL="..." PLATFORM_ADMIN_PASSWORD='a-strong-password' \\
        python -m app.utils.create_platform_admin ops@example.com "Platform Operations"

The password comes from PLATFORM_ADMIN_PASSWORD, or is asked for when not set,
so it never lands in your shell history. At least 10 characters, with letters
and digits.

Safe to run again: an existing user is made a Platform Admin (role and flag)
and keeps their password unless you pass --reset-password.
"""
import argparse
import getpass
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session

ROLE_NAME = "Platform Admin"
ROLE_DESCRIPTION = "AR Society internal cross-society management"


def check_password(password: str) -> None:
    if len(password) < 10 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise SystemExit("Refusing: the password needs at least 10 characters, with letters and digits.")


def create_platform_admin(db: Session, email: str, full_name: str, password: str = None,
                          reset_password: bool = False, force_change: bool = False) -> str:
    """Returns what it did: 'created', 'updated' or 'unchanged'."""
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User, UserRole, UserStatus

    email = email.strip().lower()
    role = db.query(Role).filter(Role.name == ROLE_NAME).first()
    if not role:
        role = Role(name=ROLE_NAME, description=ROLE_DESCRIPTION)
        db.add(role)
        db.flush()

    user = db.query(User).filter(User.email == email).first()
    outcome = "unchanged"
    if user is None:
        if not password:
            raise SystemExit("A password is needed to create the user.")
        check_password(password)
        user = User(
            email=email, full_name=full_name.strip(), hashed_password=hash_password(password),
            status=UserStatus.ACTIVE, is_superadmin=True, society_id=None,
            must_change_password=force_change, terms_accepted=True, setup_completed=True,
        )
        db.add(user)
        db.flush()
        outcome = "created"
    else:
        if not user.is_superadmin:
            user.is_superadmin = True
            outcome = "updated"
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            outcome = "updated"
        if reset_password:
            if not password:
                raise SystemExit("A password is needed to reset it.")
            check_password(password)
            user.hashed_password = hash_password(password)
            user.must_change_password = force_change
            outcome = "updated"
    if not db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first():
        db.add(UserRole(user_id=user.id, role_id=role.id))
        outcome = "created" if outcome == "created" else "updated"
    db.commit()
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or repair a Platform Admin.")
    parser.add_argument("email")
    parser.add_argument("full_name", nargs="?", default="Platform Operations")
    parser.add_argument("--reset-password", action="store_true", help="set the password of an existing user")
    parser.add_argument("--force-change", action="store_true", help="make them choose their own password at first login")
    args = parser.parse_args()

    password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or None
    from app.db.session import get_session_factory
    from app.models.user import User
    db = get_session_factory()()
    try:
        exists = db.query(User).filter(User.email == args.email.strip().lower()).first() is not None
        if (not exists or args.reset_password) and not password:
            password = getpass.getpass("Password for the Platform Admin: ")
        result = create_platform_admin(db, args.email, args.full_name, password,
                                       reset_password=args.reset_password, force_change=args.force_change)
    finally:
        db.close()
    print(f"Platform Admin {args.email.strip().lower()}: {result}.")


if __name__ == "__main__":
    main()
