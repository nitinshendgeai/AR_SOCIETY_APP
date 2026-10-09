"""Fields a flat and a shop share: when the owner took possession, and the electricity connection."""
from datetime import date, timedelta
from typing import Optional

EARLIEST_POSSESSION = date(1950, 1, 1)


def clean_possession_date(v: Optional[date]) -> Optional[date]:
    """A possession date is a real handover: not before 1950, and no more than a year ahead (a handover that is
    scheduled)."""
    if v is None:
        return None
    if v < EARLIEST_POSSESSION or v > date.today() + timedelta(days=366):
        raise ValueError("Possession date must be between 1950 and a year from today")
    return v


def clean_ref(v: Optional[str]) -> Optional[str]:
    """A meter or consumer number as printed: trimmed, inner runs of spaces collapsed; blank means none."""
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None
