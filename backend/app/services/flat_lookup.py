"""Finding a flat of a society from the wing and flat number a sheet gives."""
from collections import defaultdict
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.repositories.flat_repo import FlatRepository


def clean(v: Optional[str]) -> str:
    return " ".join(str(v).split()) if v is not None else ""


class FlatLookup:
    """The active flats of one society, found by wing (name or code) + flat number. The wing may be left out when
    the flat number is used only once in the society."""

    def __init__(self, db: Session, society_id: UUID):
        self.by_wing = {}                        # (wing name or code, flat number), lower-cased -> flat
        self.by_number = defaultdict(list)       # flat number, lower-cased -> every flat of the society with it
        for f in FlatRepository(db).get_by_society(society_id):
            for wing_key in {f.wing.name.lower(), (f.wing.code or f.wing.name).lower()}:
                self.by_wing[(wing_key, f.flat_number.lower())] = f
            self.by_number[f.flat_number.lower()].append(f)

    def find(self, wing: str, number: str) -> Flat:
        """The flat, or a ValueError saying why not."""
        wing, number = clean(wing), clean(number)
        if not number:
            raise ValueError("Flat number is required")
        if wing:
            flat = self.by_wing.get((wing.lower(), number.lower()))
            if flat is None:
                raise ValueError(f"No flat {number} in wing {wing}")
            return flat
        found = self.by_number.get(number.lower(), [])
        if not found:
            raise ValueError(f"No flat {number}")
        if len(found) > 1:
            raise ValueError(f"Flat {number} is in more than one wing — add the Wing column")
        return found[0]
