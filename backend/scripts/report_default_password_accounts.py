"""
Read-only report: accounts that still have one of the retired fixed default passwords.

    python scripts/report_default_password_accounts.py

Run it from the backend/ directory against the database in DATABASE_URL (the same variable the app uses). It changes
nothing: it only reads users, checks each password against the three defaults the system used to give every new
account, and lists the ones that still match.

Why: new accounts now get their own random temporary password, but accounts made before that change were given
"Staff@1234" (staff), "admin1234" (residents and tenants) or "Admin@1234" (a society's first four accounts), and keep
it until the person signs in and sets their own. Until then anyone who knows the login can sign in as them.

What to do with the list: for each account, an admin resets the password from Users & Roles (the reset now makes a
random temporary password and shows it once), and tells the person. An account whose person has already changed their
password does not match and is not listed.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import verify_password  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402

RETIRED_DEFAULTS = ("Staff@1234", "admin1234", "Admin@1234")


def find_default_password_accounts(db):
    """Active users whose password is still a retired default: [(user, which_default), ...]."""
    found = []
    for user in db.query(User).filter(User.status == UserStatus.ACTIVE).order_by(User.created_at):
        for old in RETIRED_DEFAULTS:
            if verify_password(old, user.hashed_password):
                found.append((user, old))
                break
    return found


def main(argv=None) -> int:
    argparse.ArgumentParser(description="List accounts that still have a retired default password (read-only).").parse_args(argv)
    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        found = find_default_password_accounts(db)
        print(f"{len(found)} active account(s) still have a retired default password.")
        for user, old in found:
            who = user.email if not (user.email or "").endswith("@duxos.local") else f"mobile {user.phone}"
            print(f"  {who:<42} society {str(user.society_id)[:8] if user.society_id else '-':<9} "
                  f"must_change={'yes' if user.must_change_password else 'NO'}  default {old[:2]}…")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
