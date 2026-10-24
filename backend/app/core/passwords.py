"""Temporary passwords handed to a person for their first sign-in.

Every account that the system creates for someone else (a staff login, a resident's mobile-number login, a new
society's first accounts, an admin-created user, a password reset) gets its own random password from here, shown once
to whoever created it, with ``must_change_password`` set. A fixed default would be known to anyone who has read the
code or the screen, and would let them sign in as a new person until that person first signs in.
"""
import secrets
import string

# No look-alikes (0 O o 1 l I): the password is read off a screen and typed on a phone.
_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0Oo1lI")


def generate_temp_password(length: int = 12) -> str:
    """A random password with at least one upper-case letter, one lower-case letter and one digit."""
    while True:
        pwd = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isupper() for c in pwd) and any(c.islower() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd
