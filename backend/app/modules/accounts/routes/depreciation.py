"""Depreciation: the category rules, each asset's own setting, and the yearly schedule. Nothing here posts to the books."""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee, require_manager_above
from app.core.tenant_scope import assert_society_access
from app.db.session import get_db
from app.models.society import Society
from app.models.user import User
from app.modules.accounts.models.depreciation import METHOD_LABELS, DepreciationRule
from app.modules.accounts.services.accounts_service import fiscal_year
from app.modules.accounts.services.depreciation import DepreciationService
from app.modules.accounts.services.depreciation_pdf import render_depreciation_pdf
from app.modules.inventory.models.inventory import Asset
from app.utils.local_time import society_today

router = APIRouter(prefix="/accounts/depreciation", tags=["Depreciation"], dependencies=[Depends(require_manager_above)])


def _s(v) -> Optional[str]:
    return None if v is None else str(v)


def _rule_out(r: DepreciationRule) -> dict:
    return {"id": str(r.id), "asset_category": r.asset_category, "method": r.method,
            "method_label": METHOD_LABELS.get(r.method, r.method), "rate": str(r.rate), "life_years": r.life_years,
            "salvage_percent": str(r.salvage_percent), "ledger_system_key": r.ledger_system_key, "notes": r.notes}


class RuleUpdate(BaseModel):
    method: Optional[str] = None
    rate: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=4)
    life_years: Optional[int] = Field(default=None, ge=1, le=100)
    salvage_percent: Optional[Decimal] = Field(default=None, ge=0, lt=100, max_digits=5, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=300)


class AssetSettingIn(BaseModel):
    depreciate: Optional[bool] = None
    method: Optional[str] = None
    rate: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=4)
    life_years: Optional[int] = Field(default=None, ge=1, le=100)
    salvage_value: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    start_on: Optional[date] = None
    stop_on: Optional[date] = None


@router.get("/rules/{society_id}")
def list_rules(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """How each kind of asset is depreciated (filled in with starting values the first time)."""
    assert_society_access(user, society_id)
    rules = DepreciationService(db).rules(society_id)
    db.commit()
    return [_rule_out(r) for r in rules]


@router.patch("/rules/{rule_id}", dependencies=[Depends(require_admin_committee)])
def update_rule(rule_id: UUID, data: RuleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = db.query(DepreciationRule).filter(DepreciationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    assert_society_access(user, rule.society_id)
    DepreciationService(db).update_rule(rule, data.model_dump(exclude_unset=True))
    db.commit()
    return _rule_out(rule)


def _asset_out(item: dict) -> dict:
    a, eff, own = item["asset"], item["effective"], item["own"]
    return {
        "asset_id": str(a.id), "asset_code": a.asset_code, "name": a.name, "category": item["category"],
        "status": a.status.value if hasattr(a.status, "value") else str(a.status),
        "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None, "cost": _s(eff["cost"]),
        "depreciate": eff["depreciate"], "method": eff["method"], "rate": _s(eff["rate"].quantize(Decimal("0.01"))),
        "life_years": eff["life_years"], "salvage": _s(eff["salvage"]),
        "start_on": eff["start"].isoformat() if eff["start"] else None,
        "stop_on": eff["stop"].isoformat() if eff["stop"] else None,
        "own": None if own is None else {
            "depreciate": own.depreciate, "method": own.method, "rate": _s(own.rate), "life_years": own.life_years,
            "salvage_value": _s(own.salvage_value), "start_on": own.start_on.isoformat() if own.start_on else None,
            "stop_on": own.stop_on.isoformat() if own.stop_on else None},
        "problems": item["problems"],
    }


@router.get("/assets/{society_id}")
def asset_settings(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every asset with the setting that applies to it (its own, else its category's) and what is missing."""
    assert_society_access(user, society_id)
    rows = DepreciationService(db).asset_settings(society_id)
    db.commit()
    return [_asset_out(r) for r in rows]


@router.put("/assets/{asset_id}", dependencies=[Depends(require_admin_committee)])
def set_asset(asset_id: UUID, data: AssetSettingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """An asset's own depreciation setting. Send null to go back to the category's value for a field."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    assert_society_access(user, asset.society_id)
    svc = DepreciationService(db)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("depreciate") is None:
        changes.pop("depreciate", None)
    svc.set_asset(asset, changes)
    db.commit()
    item = next(i for i in svc.asset_settings(asset.society_id) if i["asset"].id == asset.id)
    return _asset_out(item)


def _money(v) -> str:
    return str(v)


@router.get("/schedule/{society_id}")
def schedule(society_id: UUID, fy: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
             format: str = Query("json", pattern="^(json|pdf)$"),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The year's depreciation asset by asset: cost, opening book value, depreciation, closing book value, and the
    journal that would book it. Read-only: it posts nothing. ?format=pdf: the printed schedule."""
    assert_society_access(user, society_id)
    fy = fy or fiscal_year(society_today(db, society_id))
    sch = DepreciationService(db).schedule(society_id, fy)
    db.commit()
    out = {
        "fy": sch["fy"], "from": sch["from"].isoformat(), "to": sch["to"].isoformat(),
        "rows": [{**{k: v for k, v in r.items() if k not in ("start", "stop", "rate", "cost", "additions", "opening_wdv",
                                                           "depreciation", "closing_wdv", "opening_accumulated",
                                                           "closing_accumulated")},
                  "rate": str(r["rate"].quantize(Decimal("0.01"))),
                  "start": r["start"].isoformat(), "stop": r["stop"].isoformat() if r["stop"] else None,
                  **{k: _money(r[k]) for k in ("cost", "additions", "opening_wdv", "depreciation", "closing_wdv",
                                              "opening_accumulated", "closing_accumulated")}} for r in sch["rows"]],
        "totals": {k: _money(v) for k, v in sch["totals"].items()},
        "ledgers": [{"ledger_key": l["ledger_key"], "ledger": l["ledger"], "depreciation": _money(l["depreciation"])}
                    for l in sch["ledgers"]],
        "journal": {"debit": {"ledger": sch["journal"]["debit"]["ledger"], "amount": _money(sch["journal"]["debit"]["amount"])},
                    "credits": [{"ledger": c["ledger"], "amount": _money(c["amount"])} for c in sch["journal"]["credits"]]},
        "problems": sch["problems"],
    }
    if format == "pdf":
        society = db.query(Society).filter(Society.id == society_id).first()
        return Response(content=render_depreciation_pdf(out, society), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename=Depreciation-{fy}.pdf"})
    return out
