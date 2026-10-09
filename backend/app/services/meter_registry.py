"""An electricity meter belongs to one unit — a flat or a shop — so its number can't be given to two of them."""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.wing import Wing


def assert_meter_free(db: Session, society_id: UUID, meter_no: Optional[str], *,
                      exclude_flat_id: Optional[UUID] = None, exclude_shop_id: Optional[UUID] = None) -> None:
    """409 if another active flat or shop of the society already has this meter number (ignoring case)."""
    if not meter_no:
        return
    from app.modules.shops.models.shop import Shop
    wanted = meter_no.strip().lower()
    flat = (db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
            .filter(Wing.society_id == society_id, Flat.is_active == True,       # noqa: E712
                    Flat.electric_meter_no.isnot(None)))
    for f in flat:
        if f.electric_meter_no.strip().lower() == wanted and f.id != exclude_flat_id:
            raise HTTPException(409, f"Meter {meter_no} is already on flat {f.wing.name}-{f.flat_number}")
    for sh in db.query(Shop).filter(Shop.society_id == society_id, Shop.is_active == True,   # noqa: E712
                                    Shop.electric_meter_no.isnot(None)):
        if sh.electric_meter_no.strip().lower() == wanted and sh.id != exclude_shop_id:
            raise HTTPException(409, f"Meter {meter_no} is already on shop {sh.shop_number}")
