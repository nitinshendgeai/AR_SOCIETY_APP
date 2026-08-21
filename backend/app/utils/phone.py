"""
Shared mobile-number validation (M1.9-R3 Gap C).

Before this, Resident/Tenant `phone` and `emergency_contact_phone` were bare
`Optional[str]` with zero format validation anywhere in the stack — the
Flutter form's own client-side check didn't actually block submission either
(see M1.9-R2), so `"abc123"` could reach the database as a stored mobile
number. This is the single canonical rule for both entities: import
`normalize_phone` everywhere a resident/tenant phone number is accepted
instead of re-declaring the pattern.

Format follows the Flutter form's own pre-existing hint text ("10-digit
mobile number") and the standard Indian mobile numbering plan: exactly 10
digits, first digit 6-9. A leading +91/91/0 STD-style prefix is stripped
before validation so "+91 98765 43210" and "9876543210" normalize to the
same stored value.
"""
import re
from typing import Optional

_DIGITS_ONLY = re.compile(r"[^0-9]")
_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalize_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None

    digits = _DIGITS_ONLY.sub("", trimmed)
    # Strip a leading country/STD prefix so "+91 98765-43210" and "09876543210"
    # normalize the same as "9876543210".
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if not _INDIAN_MOBILE.match(digits):
        raise ValueError("must be a valid 10-digit mobile number")
    return digits
