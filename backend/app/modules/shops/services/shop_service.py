import re
from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.user import User
from app.modules.shops.models.shop import Shop
from app.modules.shops.schemas.shop import ShopCreate, ShopImportResult, ShopImportRow, ShopUpdate
from app.services.audit_service import AuditService
from app.services.meter_registry import assert_meter_free

_OCCUPANCY_WORDS = {
    "owner_run": {"owner run", "owner_run", "owner", "self", "self run", "self occupied", "owner occupied", "own"},
    "rented":    {"rented", "rent", "rented out", "tenant", "tenanted", "leased", "let"},
    "vacant":    {"vacant", "empty", "closed", "unoccupied", "available"},
}
_FLOOR_WORDS = {"g": 0, "gf": 0, "ground": 0, "ground floor": 0, "grd": 0}


def _clean(v: Optional[str]) -> Optional[str]:
    v = " ".join(str(v).split()) if v is not None else None
    return v or None


def parse_occupancy(text: Optional[str]) -> Optional[str]:
    t = _clean(text)
    if t is None:
        return None
    key = t.lower().replace("-", " ")
    for value, words in _OCCUPANCY_WORDS.items():
        if key in words:
            return value
    raise ValueError("Occupancy must be owner run, rented or vacant")


def parse_floor(text: Optional[str]) -> Optional[int]:
    t = _clean(text)
    if t is None:
        return None
    if t.lower() in _FLOOR_WORDS:
        return _FLOOR_WORDS[t.lower()]
    try:
        return int(t)
    except ValueError:
        raise ValueError("Floor must be a whole number (or Ground)")


def parse_area(text: Optional[str]) -> Optional[float]:
    t = _clean(text)
    if t is None:
        return None
    try:
        return float(t.replace(",", ""))
    except ValueError:
        raise ValueError("Area must be a number")


def parse_date(text: Optional[str]) -> Optional[date]:
    t = _clean(text)
    if t is None:
        return None
    try:
        return date.fromisoformat(t)
    except ValueError:
        raise ValueError("Possession date must be a date (yyyy-mm-dd)")


def _first_error(exc: ValidationError) -> str:
    e = exc.errors()[0]
    field = ".".join(str(p) for p in e["loc"]) or "value"
    msg = e["msg"].replace("Value error, ", "")
    return f"{field.replace('_', ' ').capitalize()}: {msg}"


class ShopService:
    def __init__(self, db: Session):
        self.db = db

    def _audit(self, action, shop, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="shops", entity_id=str(shop.id),
                         entity_type="Shop", user=user, request=request, **kw)

    # ── reads ────────────────────────────────────────────────────────────────

    def get(self, shop_id: UUID, user: User) -> Shop:
        """404 for a shop of another society, as for one that doesn't exist."""
        shop = self.db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop or (user.society_id is not None and shop.society_id != user.society_id):
            raise HTTPException(404, "Shop not found")
        return shop

    def list(self, society_id: UUID, user: User, q: Optional[str] = None, occupancy: Optional[str] = None,
             include_inactive: bool = False) -> List[Shop]:
        assert_society_access(user, society_id)
        query = self.db.query(Shop).filter(Shop.society_id == society_id)
        if not include_inactive:
            query = query.filter(Shop.is_active == True)            # noqa: E712
        if occupancy:
            query = query.filter(Shop.occupancy == occupancy)
        if q and q.strip():
            like = f"%{q.strip().lower()}%"
            query = query.filter(or_(
                func.lower(Shop.shop_number).like(like), func.lower(Shop.owner_name).like(like),
                func.lower(func.coalesce(Shop.business_name, "")).like(like),
                func.lower(func.coalesce(Shop.owner_phone, "")).like(like),
                func.lower(func.coalesce(Shop.electric_meter_no, "")).like(like)))
        shops = query.all()
        shops.sort(key=lambda s: [int(p) if p.isdigit() else p.lower()
                                  for p in re.split(r"(\d+)", s.shop_number)])
        return shops

    # ── writes ───────────────────────────────────────────────────────────────

    def _number_free(self, society_id: UUID, number: str, exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Shop).filter(Shop.society_id == society_id, Shop.is_active == True,       # noqa: E712
                                       func.lower(Shop.shop_number) == number.lower())
        if exclude_id:
            q = q.filter(Shop.id != exclude_id)
        if q.first():
            raise HTTPException(409, f"Shop {number} already exists")

    def create(self, data: ShopCreate, user: User, request=None) -> Shop:
        society_id = resolve_create_society_id(user, data.society_id)
        self._number_free(society_id, data.shop_number)
        assert_meter_free(self.db, society_id, data.electric_meter_no)
        fields = data.model_dump(exclude={"society_id"})
        fields["occupancy"] = fields.get("occupancy") or "vacant"
        shop = Shop(society_id=society_id, created_by=user.id, **fields)
        self.db.add(shop)
        self.db.flush()
        self._audit(AuditAction.CREATE, shop, user, request, new_values={"shop": shop.shop_number})
        self.db.commit()
        self.db.refresh(shop)
        return shop

    def update(self, shop_id: UUID, data: ShopUpdate, user: User, request=None) -> Shop:
        shop = self.get(shop_id, user)
        patch = {k: getattr(data, k) for k in data.model_fields_set}
        for required in ("shop_number", "owner_name", "occupancy"):
            if required in patch and patch[required] is None:
                patch.pop(required)                        # these can't be cleared
        if "shop_number" in patch and patch["shop_number"].lower() != shop.shop_number.lower():
            self._number_free(shop.society_id, patch["shop_number"], exclude_id=shop.id)
        if patch.get("electric_meter_no"):
            assert_meter_free(self.db, shop.society_id, patch["electric_meter_no"], exclude_shop_id=shop.id)
        for key, value in patch.items():
            setattr(shop, key, value)
        self._audit(AuditAction.UPDATE, shop, user, request, new_values={k: str(v) for k, v in patch.items()})
        self.db.commit()
        self.db.refresh(shop)
        return shop

    def delete(self, shop_id: UUID, user: User, request=None) -> None:
        shop = self.get(shop_id, user)
        shop.is_active = False
        self._audit(AuditAction.DELETE, shop, user, request, old_values={"shop": shop.shop_number})
        self.db.commit()

    # ── bulk import ──────────────────────────────────────────────────────────

    def import_rows(self, society_id: Optional[UUID], rows: List[ShopImportRow], dry_run: bool, user: User,
                    request=None) -> List[ShopImportResult]:
        """Add shops from a file, or — when a shop number already exists — fill in what the file gives for it
        (a corrected file can be imported again). Each row stands alone: a bad row is reported and skipped, the
        rest go in. With `dry_run` nothing is written."""
        society_id = resolve_create_society_id(user, society_id)
        by_number: Dict[str, Shop] = {s.shop_number.lower(): s for s in self.db.query(Shop).filter(
            Shop.society_id == society_id, Shop.is_active == True)}                              # noqa: E712
        meters_in_file: Dict[str, str] = {}
        seen_numbers: Dict[str, int] = {}
        out: List[ShopImportResult] = []

        for row in rows:
            number = _clean(row.shop_number)
            try:
                if not number:
                    raise ValueError("Shop number is required")
                key = number.lower()
                if key in seen_numbers:
                    raise ValueError(f"Shop {number} appears again (line {seen_numbers[key]} of the file)")
                seen_numbers[key] = row.line or 0

                values = {
                    "owner_name": _clean(row.owner_name), "owner_phone": _clean(row.owner_phone),
                    "owner_email": _clean(row.owner_email), "location": _clean(row.location),
                    "business_name": _clean(row.business_name), "tenant_name": _clean(row.tenant_name),
                    "tenant_phone": _clean(row.tenant_phone), "remarks": _clean(row.remarks),
                    "electric_meter_no": _clean(row.electric_meter_no),
                    "electric_consumer_no": _clean(row.electric_consumer_no),
                    "floor": parse_floor(row.floor), "area_sqft": parse_area(row.area_sqft),
                    "occupancy": parse_occupancy(row.occupancy), "possession_date": parse_date(row.possession_date),
                }
                values = {k: v for k, v in values.items() if v is not None}
                meter = values.get("electric_meter_no")
                existing = by_number.get(key)
                if meter:
                    mkey = meter.lower()
                    if mkey in meters_in_file and meters_in_file[mkey] != key:
                        raise ValueError(f"Meter {meter} is on more than one shop in this file")
                    meters_in_file[mkey] = key
                    assert_meter_free(self.db, society_id, meter, exclude_shop_id=existing.id if existing else None)

                if existing is None:
                    try:
                        data = ShopCreate.model_validate({"shop_number": number, **values})
                    except ValidationError as exc:
                        raise ValueError(_first_error(exc))
                    if not dry_run:
                        fields = data.model_dump(exclude={"society_id"})
                        fields["occupancy"] = fields.get("occupancy") or "vacant"
                        shop = Shop(society_id=society_id, created_by=user.id, **fields)
                        self.db.add(shop)
                        self.db.flush()
                        by_number[key] = shop
                    out.append(ShopImportResult(line=row.line, shop_number=number, status="created"))
                else:
                    try:
                        data = ShopUpdate.model_validate(values)
                    except ValidationError as exc:
                        raise ValueError(_first_error(exc))
                    if not dry_run:
                        for k in data.model_fields_set:
                            setattr(existing, k, getattr(data, k))
                    out.append(ShopImportResult(line=row.line, shop_number=number, status="updated"))
            except HTTPException as exc:
                out.append(ShopImportResult(line=row.line, shop_number=number, status="error", message=str(exc.detail)))
            except ValueError as exc:
                out.append(ShopImportResult(line=row.line, shop_number=number, status="error", message=str(exc)))

        if not dry_run:
            created = sum(1 for r in out if r.status == "created")
            updated = sum(1 for r in out if r.status == "updated")
            AuditService.log(db=self.db, action=AuditAction.CREATE, module="shops", entity_type="Shop",
                             user=user, request=request,
                             new_values={"import": True, "created": created, "updated": updated,
                                         "errors": sum(1 for r in out if r.status == "error")})
            self.db.commit()
        return out
