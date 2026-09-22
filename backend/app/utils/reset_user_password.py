"""
One-off admin utility — set a user's password directly in the database.

Usage (run from backend/, against whichever DATABASE_URL is in the env —
point this at production only when you actually mean to):

    DATABASE_URL="..." python -m app.utils.reset_user_password <email> <new_password>

By default this also sets must_change_password=True (same behavior as the
in-app admin "Reset Password" action), forcing the user to pick their own
password on next login. Pass --keep-password to leave it False if you want
the given password to stick.

Prints only the email and outcome — never the password — since by the
time this runs it's already sitting in your shell history from the
command above.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import get_session_factory
from app.core.security import hash_password
from app.models.user import User


def reset_password(email: str, new_password: str, force_change: bool = True) -> None:
    if len(new_password) < 8:
        raise SystemExit(f"Refusing: password must be at least 8 characters (got {len(new_password)}).")

    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise SystemExit(f"No user found with email {email!r}.")

        user.hashed_password = hash_password(new_password)
        user.must_change_password = force_change
        db.commit()
        print(f"Password updated for {email} (id={user.id}). "
              f"must_change_password={force_change}.")
    finally:
        db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    force_change = True
    if "--keep-password" in args:
        force_change = False
        args.remove("--keep-password")

    if len(args) != 2:
        raise SystemExit(
            "Usage: python -m app.utils.reset_user_password <email> <new_password> [--keep-password]"
        )
    reset_password(args[0], args[1], force_change=force_change)
