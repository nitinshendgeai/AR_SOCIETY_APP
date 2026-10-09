"""Short codes the app fills in itself, so nobody has to invent one: a wing's "A", a parking zone's "BAS",
a ledger's next number in its group."""
import re
from typing import Iterable, Optional

# Words that say what kind of place it is, not which one.
_GENERIC = {"wing", "block", "tower", "building", "zone", "parking", "area", "floor", "the"}


def short_code(name: str, taken: Iterable[str] = (), max_len: int = 6) -> str:
    """A short upper-case code for `name` that is not in `taken` (compared ignoring case):
    "A Wing" -> "A", "North Block" -> "NORTH", "Basement" -> "BAS", "Open Air Parking" -> "OA"; a clash
    becomes "A2", "A3"…"""
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    kept = [w for w in words if w.lower() not in _GENERIC] or words
    if not kept:
        kept = ["X"]
    if len(kept) == 1:
        base = kept[0] if len(kept[0]) <= max_len else kept[0][:3]
    else:
        base = "".join(w[0] for w in kept)[:max_len]
    base = base.upper()
    used = {t.upper() for t in taken if t}
    code, n = base, 2
    while code in used:
        code = f"{base}{n}"
        n += 1
    return code


def next_number_code(existing: Iterable[Optional[str]]) -> Optional[str]:
    """The number after the highest purely numeric code in `existing` ("1106" -> "1107"), or None
    when there is none to continue from."""
    numbers = [int(c) for c in existing if c and c.strip().isdigit()]
    return str(max(numbers) + 1) if numbers else None
