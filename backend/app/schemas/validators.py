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
