"""Input tidying shared by the schemas: what a form sends is trimmed, and
what can't be right is refused with a message that says why."""
import re

_PHONE = re.compile(r"^\+?[0-9]{7,15}$")


def text(v):
    """Trimmed, inner whitespace collapsed; blank means nothing."""
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None


def name(v):
    """A name that is never blank when given (None passes: a partial update
    leaves it as it is, and a create fails its own type check)."""
    if v is None:
        return None
    v = text(v)
    if v is None:
        raise ValueError("Name cannot be blank")
    return v


def phone(v):
    """A phone number as digits (and a leading +); spaces, dashes and
    brackets typed around it are dropped."""
    v = text(v)
    if v is None:
        return None
    digits = re.sub(r"[ \-()]", "", v)
    if not _PHONE.match(digits):
        raise ValueError("Enter a valid phone number")
    return digits


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def email(v):
    """An email address, trimmed and lower-cased; blank means none."""
    v = text(v)
    if v is None:
        return None
    v = v.lower()
    if len(v) > 255 or not _EMAIL.match(v):
        raise ValueError("Enter a valid email address")
    return v


def limited(n):
    """Trimmed text of at most `n` characters; blank means none."""
    def check(v):
        v = text(v)
        if v is not None and len(v) > n:
            raise ValueError(f"Keep this to {n} characters or fewer")
        return v
    return check


def contact_phone(v):
    """An emergency/contact number: a phone number of at most 20 characters,
    as typed (trimmed); blank means none."""
    v = text(v)
    if v is None:
        return None
    phone(v)
    if len(v) > 20:
        raise ValueError("Keep this to 20 characters or fewer")
    return v


def mobile(v):
    """A person's mobile number (10-digit Indian), as typed, trimmed; blank
    means none."""
    from app.utils.phone import validate_mobile_number
    v = text(v)
    if v is None:
        return None
    validate_mobile_number(v)
    if len(v) > 20:
        raise ValueError("Keep this to 20 characters or fewer")
    return v


def birth_date(v):
    """A date of birth: not in the future, not absurdly old."""
    from datetime import date
    if v is not None and not (date(1900, 1, 1) <= v <= date.today()):
        raise ValueError("Enter a valid date of birth")
    return v


def sane_date(v):
    """A calendar date within a plausible range (guards typos like year 0002)."""
    from datetime import date
    if v is not None and not (date(1900, 1, 1) <= v <= date(2100, 12, 31)):
        raise ValueError("Enter a valid date")
    return v


def note(v):
    """Free text (newlines kept): trimmed; blank means none."""
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def note_max(n, required=False):
    """Free text (newlines kept) of at most `n` characters: trimmed; blank means
    none, or an error when `required`."""
    def check(v):
        v = note(v)
        if v is None:
            if required:
                raise ValueError("This can't be left blank")
            return None
        if len(v) > n:
            raise ValueError(f"Keep this to {n} characters or fewer")
        return v
    return check


def mobile_any(v):
    """A visitor's phone number: digits only (leading + kept), 7-15 of them.
    An Indian mobile typed with +91/91/0 is stored as its 10 digits, so the same
    person typed two ways is the same number."""
    digits = phone(v)
    if digits is None:
        return None
    if re.fullmatch(r"[6-9]\d{9}", digits):
        return digits
    for prefix in ("+91", "91", "0"):
        if digits.startswith(prefix) and re.fullmatch(r"[6-9]\d{9}", digits[len(prefix):]):
            return digits[len(prefix):]
    return digits


def line_max(n, required=False):
    """A single line of at most `n` characters, inner spaces collapsed; blank
    means none, or an error when `required`."""
    def check(v):
        v = text(v)
        if v is None:
            if required:
                raise ValueError("This can't be left blank")
            return None
        if len(v) > n:
            raise ValueError(f"Keep this to {n} characters or fewer")
        return v
    return check
