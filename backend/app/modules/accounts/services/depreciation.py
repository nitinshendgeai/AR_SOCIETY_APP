"""
Depreciation of the society's fixed assets: the setup and the yearly calculation.

The calculation is a pure function of an asset's cost, method, rate, residual value and dates, so any figure on the
schedule can be re-worked by hand:

- **Reducing balance (WDV)**: each year, the book value at the start of the year x rate x the share of the year the
  asset was in use.
- **Straight line (SLM)**: each year, cost x rate x the share of the year in use, where the rate is the one entered or
  100 / life in years.
- The share of a year is the days in use / days in the financial year (1 April to 31 March), counting the day put to
  use and the day it stopped. An asset bought mid-year is therefore depreciated for the part of the year it was held.
- Depreciation stops at the residual value (never below it), and every year is rounded to the paisa before it carries
  into the next.

The schedule reads the asset register and the setup and **posts nothing**. It ends with the journal that would book
the year's depreciation, for the Treasurer to review and enter as a voucher.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts.models.depreciation import METHODS, AssetDepreciation, DepreciationRule
from app.modules.accounts.services.accounts_service import AccountsService, fiscal_year, fiscal_year_bounds, fiscal_year_start
from app.modules.inventory.models.inventory import Asset, AssetCategory, AssetStatus

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal(100)


def money(v) -> Decimal:
    return Decimal(v or 0).quantize(CENT, rounding=ROUND_HALF_UP)


# Starting rules by asset category: (method, % a year, life in years, residual %, fixed-asset ledger). They are the usual
# income-tax block rates on a reducing balance and are only a starting point: the society and its auditor confirm them.
DEFAULT_RULES: Dict[str, Tuple[str, str, Optional[int], str, str]] = {
    "lift":             ("wdv", "15", None, "0", "plant_machinery"),
    "generator":        ("wdv", "15", None, "0", "plant_machinery"),
    "pump":             ("wdv", "15", None, "0", "plant_machinery"),
    "water_treatment":  ("wdv", "15", None, "0", "plant_machinery"),
    "water_tank":       ("wdv", "10", None, "0", "land_building"),
    "electrical":       ("wdv", "10", None, "0", "plant_machinery"),
    "solar":            ("wdv", "40", None, "0", "plant_machinery"),
    "cctv":             ("wdv", "15", None, "0", "plant_machinery"),
    "intercom":         ("wdv", "15", None, "0", "plant_machinery"),
    "biometric":        ("wdv", "15", None, "0", "plant_machinery"),
    "fire_safety":      ("wdv", "15", None, "0", "plant_machinery"),
    "hvac":             ("wdv", "15", None, "0", "plant_machinery"),
    "air_conditioner":  ("wdv", "15", None, "0", "plant_machinery"),
    "gym_equipment":    ("wdv", "15", None, "0", "plant_machinery"),
    "garden_equipment": ("wdv", "15", None, "0", "plant_machinery"),
    "furniture":        ("wdv", "10", None, "0", "furniture"),
    "it_equipment":     ("wdv", "40", None, "0", "office_equipment"),
    "vehicle":          ("wdv", "15", None, "0", "plant_machinery"),
    "other":            ("wdv", "15", None, "0", "plant_machinery"),
}
CATEGORY_ORDER = [c.value for c in AssetCategory]
NOT_DEPRECIATED_STATUSES = (AssetStatus.DISPOSED, AssetStatus.LOST)


# ── The calculation ──────────────────────────────────────────────────────────────────────────────────────────────────

def _year_share(fy_start: date, start: date, stop: Optional[date]) -> Tuple[int, Decimal]:
    """(days in use in the financial year beginning `fy_start`, share of the year)."""
    fy_end = date(fy_start.year + 1, 3, 31)
    first = max(start, fy_start)
    last = min(stop, fy_end) if stop else fy_end
    days = max((last - first).days + 1, 0)
    year_days = (fy_end - fy_start).days + 1
    return days, Decimal(days) / Decimal(year_days)


def effective_rate(method: str, rate, life_years: Optional[int]) -> Decimal:
    """The yearly percentage: the one entered, or for straight line without one, 100 / life."""
    r = Decimal(rate or 0)
    if r > 0:
        return r
    if method == "slm" and life_years:
        return HUNDRED / Decimal(life_years)
    return Decimal(0)


def work_out(cost, method: str, rate, salvage, start: date, stop: Optional[date], upto_fy: int) -> List[dict]:
    """Year by year from the financial year the asset was put to use up to the one beginning in April of `upto_fy`:
    [{fy_start, days, opening, depreciation, closing}]. Book values, not accumulated depreciation."""
    cost, salvage, pct = money(cost), money(salvage), Decimal(rate or 0)
    book, rows = cost, []
    year = fiscal_year_start(start).year
    while year <= upto_fy:
        fy_start = date(year, 4, 1)
        days, share = _year_share(fy_start, start, stop)
        base = book if method == "wdv" else cost
        dep = money(base * pct / HUNDRED * share) if days else ZERO
        dep = max(min(dep, book - salvage), ZERO)
        rows.append({"fy_start": fy_start, "days": days, "opening": book, "depreciation": dep, "closing": book - dep})
        book -= dep
        year += 1
    return rows


# ── The setup ────────────────────────────────────────────────────────────────────────────────────────────────────────

class DepreciationService:
    def __init__(self, db: Session):
        self.db = db
        self.accounts = AccountsService(db)

    def ensure_default_rules(self, society_id: UUID) -> None:
        """Fill in a rule for every asset category the first time the setup is opened. Rows already there are left alone."""
        have = {r.asset_category for r in self.db.query(DepreciationRule.asset_category).filter(
            DepreciationRule.society_id == society_id)}
        for category in CATEGORY_ORDER:
            if category in have:
                continue
            method, rate, life, salvage, ledger = DEFAULT_RULES.get(category, DEFAULT_RULES["other"])
            self.db.add(DepreciationRule(society_id=society_id, asset_category=category, method=method,
                                         rate=Decimal(rate), life_years=life, salvage_percent=Decimal(salvage),
                                         ledger_system_key=ledger))
        self.db.flush()

    def rules(self, society_id: UUID) -> List[DepreciationRule]:
        self.ensure_default_rules(society_id)
        order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
        return sorted(self.db.query(DepreciationRule).filter(DepreciationRule.society_id == society_id).all(),
                      key=lambda r: order.get(r.asset_category, 99))

    def update_rule(self, rule: DepreciationRule, changes: dict) -> DepreciationRule:
        method = changes.get("method", rule.method)
        if method not in METHODS:
            raise HTTPException(422, "Method must be reducing balance or straight line")
        rate = Decimal(changes.get("rate", rule.rate) or 0)
        life = changes.get("life_years", rule.life_years)
        if rate < 0 or rate > 100:
            raise HTTPException(422, "The rate is a percentage from 0 to 100")
        if method == "slm" and rate == 0 and not life:
            raise HTTPException(422, "Straight line needs a rate or a life in years")
        salvage = Decimal(changes.get("salvage_percent", rule.salvage_percent) or 0)
        if salvage < 0 or salvage >= 100:
            raise HTTPException(422, "The residual value is a percentage of cost, from 0 to under 100")
        if life is not None and not (1 <= life <= 100):
            raise HTTPException(422, "Life is 1 to 100 years")
        rule.method, rule.rate, rule.life_years, rule.salvage_percent = method, rate, life, salvage
        if "notes" in changes:
            rule.notes = changes["notes"]
        self.db.flush()
        return rule

    def set_asset(self, asset: Asset, changes: dict) -> AssetDepreciation:
        row = self.db.query(AssetDepreciation).filter(AssetDepreciation.asset_id == asset.id).first()
        if not row:
            row = AssetDepreciation(society_id=asset.society_id, asset_id=asset.id)
            self.db.add(row)
        for k in ("depreciate", "method", "rate", "life_years", "salvage_value", "start_on", "stop_on"):
            if k in changes:
                setattr(row, k, changes[k])
        if row.method is not None and row.method not in METHODS:
            raise HTTPException(422, "Method must be reducing balance or straight line")
        if row.rate is not None and not (0 <= Decimal(row.rate) <= 100):
            raise HTTPException(422, "The rate is a percentage from 0 to 100")
        if row.salvage_value is not None and Decimal(row.salvage_value) < 0:
            raise HTTPException(422, "The residual value can't be negative")
        if row.start_on and row.stop_on and row.stop_on < row.start_on:
            raise HTTPException(422, "The stop date is before the start date")
        self.db.flush()
        return row

    # ── What applies to one asset ─────────────────────────────────────────────────────────────────────────────────────

    def _effective(self, asset: Asset, own: Optional[AssetDepreciation], rule: Optional[DepreciationRule]) -> dict:
        cost = money(asset.purchase_cost)
        method = (own.method if own and own.method else None) or (rule.method if rule else "wdv")
        rate_in = own.rate if own and own.rate is not None else (rule.rate if rule else 0)
        life = (own.life_years if own and own.life_years else None) or (rule.life_years if rule else None)
        salvage = (money(own.salvage_value) if own and own.salvage_value is not None
                   else money(cost * Decimal(rule.salvage_percent or 0) / HUNDRED) if rule else ZERO)
        return {
            "depreciate": own.depreciate if own else True,
            "method": method, "rate": effective_rate(method, rate_in, life), "life_years": life,
            "salvage": salvage, "cost": cost,
            "start": (own.start_on if own and own.start_on else None) or asset.purchase_date,
            "stop": own.stop_on if own else None,
            "ledger_key": rule.ledger_system_key if rule else "plant_machinery",
        }

    def _problems(self, asset: Asset, eff: dict) -> List[str]:
        out = []
        if not eff["depreciate"]:
            return out
        if eff["cost"] <= 0:
            out.append("No purchase cost")
        if not eff["start"]:
            out.append("No purchase or start date")
        if eff["rate"] <= 0:
            out.append("No depreciation rate")
        if asset.status in NOT_DEPRECIATED_STATUSES and not eff["stop"]:
            out.append("Disposed or lost: set the date it stopped being used")
        return out

    def _assets(self, society_id: UUID) -> List[Tuple[Asset, Optional[AssetDepreciation]]]:
        own = {d.asset_id: d for d in self.db.query(AssetDepreciation).filter(AssetDepreciation.society_id == society_id)}
        assets = (self.db.query(Asset).filter(Asset.society_id == society_id, Asset.is_active == True)  # noqa: E712
                  .order_by(Asset.asset_code).all())
        return [(a, own.get(a.id)) for a in assets]

    def asset_settings(self, society_id: UUID) -> List[dict]:
        """Every asset with what applies to it, and anything that stops it being depreciated."""
        rules = {r.asset_category: r for r in self.rules(society_id)}
        rows = []
        for a, own in self._assets(society_id):
            cat = a.asset_category.value if hasattr(a.asset_category, "value") else str(a.asset_category)
            eff = self._effective(a, own, rules.get(cat))
            rows.append({"asset": a, "category": cat, "own": own, "effective": eff, "problems": self._problems(a, eff)})
        return rows

    # ── The schedule ─────────────────────────────────────────────────────────────────────────────────────────────────

    def schedule(self, society_id: UUID, fy: str) -> dict:
        fy_from, fy_to = fiscal_year_bounds(fy)
        rows, problems = [], []
        for item in self.asset_settings(society_id):
            a, eff = item["asset"], item["effective"]
            if not eff["depreciate"]:
                continue
            if item["problems"]:
                problems.append({"asset_id": str(a.id), "asset_code": a.asset_code, "name": a.name,
                                 "issues": item["problems"]})
                continue                                    # left out until its setup is complete; the schedule says so
            start, stop = eff["start"], eff["stop"]
            if start > fy_to or (stop and stop < fy_from):
                continue                                    # not yet in use, or finished before this year
            years = work_out(eff["cost"], eff["method"], eff["rate"], eff["salvage"], start, stop, fy_from.year)
            this = years[-1]
            rows.append({
                "asset_id": str(a.id), "asset_code": a.asset_code, "name": a.name, "category": item["category"],
                "ledger_key": eff["ledger_key"], "method": eff["method"], "rate": eff["rate"],
                "start": start, "stop": stop, "days": this["days"], "cost": eff["cost"],
                "additions": eff["cost"] if fy_from <= start <= fy_to else ZERO,
                "opening_wdv": this["opening"], "depreciation": this["depreciation"], "closing_wdv": this["closing"],
                "opening_accumulated": eff["cost"] - this["opening"],
                "closing_accumulated": eff["cost"] - this["closing"],
            })
        totals = {k: sum((r[k] for r in rows), ZERO) for k in
                  ("cost", "additions", "opening_wdv", "depreciation", "closing_wdv", "opening_accumulated",
                   "closing_accumulated")}
        by_ledger: Dict[str, Decimal] = {}
        for r in rows:
            by_ledger[r["ledger_key"]] = by_ledger.get(r["ledger_key"], ZERO) + r["depreciation"]
        ledgers = []
        for key, amount in by_ledger.items():
            ledgers.append({"ledger_key": key, "ledger": self.accounts.system_account(society_id, key).name,
                            "depreciation": amount})
        expense = self.accounts.system_account(society_id, "depreciation")
        return {"fy": fy, "from": fy_from, "to": fy_to, "rows": rows, "totals": totals, "ledgers": ledgers,
                "journal": {"debit": {"ledger": expense.name, "amount": totals["depreciation"]},
                            "credits": [{"ledger": l["ledger"], "amount": l["depreciation"]} for l in ledgers
                                        if l["depreciation"] > 0]},
                "problems": problems}


def current_fy(today: date) -> str:
    return fiscal_year(today)
