"""Removing a master record that was entered by mistake.

A removed record is hidden (its `is_active` goes off), not erased: bills, vouchers and logs that mention it keep working.
It is refused while something still depends on it, with the reasons in plain words, so the user knows what to clear first
(or to mark it Inactive instead).
"""
from typing import Dict

from fastapi import HTTPException


def refuse_if_in_use(what: str, uses: Dict[str, int], hint: str = "") -> None:
    """Raise 409 naming what the record is still used by, e.g. "Sparkle can't be removed: it has 2 bills and 1 work
    order. Mark it Inactive instead." `uses` maps a plural/singular-neutral label to its count; zero counts are left out."""
    used = {label: count for label, count in uses.items() if count}
    if not used:
        return
    parts = [f"{count} {label}" for label, count in used.items()]
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    raise HTTPException(status_code=409, detail=f"{what} can't be removed: it has {listed}." + (f" {hint}" if hint else ""))
