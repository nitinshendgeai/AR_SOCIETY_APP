"""
Shared Indian mobile number validation.

Mirrors the convention already established by
`SelfRegistrationRequest.validate_mobile` (app/modules/onboarding/schemas/
onboarding.py) — a valid mobile number reduces to exactly 10 digits
starting with 6-9. Resident/Tenant `phone` previously had no format
validation at all (plain `Optional[str]`), which let obviously malformed
values like "abc123" be stored. Import this validator everywhere a
person's mobile number is accepted instead of re-declaring the check.

Unlike the onboarding validator, this does not rewrite the stored value —
Resident/Tenant phone numbers are not normalized elsewhere in the domain,
so silently reformatting user input here would be a new, unrequested
behavior change.
"""
import re

_MOBILE_RE = re.compile(r'^[6-9]\d{9}$')


def validate_mobile_number(value):
    """Raise ValueError if `value` is a non-empty string that isn't a
    plausible 10-digit Indian mobile number. None/empty values pass through
    unchanged since the field remains optional."""
    if value is None:
        return value
    stripped = value.strip()
    if stripped == "":
        return value

    digits = re.sub(r'[\s\-()]', '', stripped)
    if digits.startswith('+91'):
        digits = digits[3:]
    elif digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]

    if not _MOBILE_RE.match(digits):
        raise ValueError("must be a valid 10-digit Indian mobile number")
    return value
