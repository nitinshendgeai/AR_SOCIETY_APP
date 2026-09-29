from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_manager_above
from app.core.tenant_scope import assert_society_access
from app.db.session import get_db
from app.models.user import User
from app.modules.accounts.models.accounts import VOUCHER_TYPES, Account, Voucher
from app.modules.accounts.services.accounts_service import AccountsService, dr_cr, money
from app.modules.accounts.services.postings import AccountPostings
from app.modules.billing.services.bill_pdf import flat_label, member_name

# The society's books are kept by those who run it: Admin, the committee
# (Treasurer, Secretary, Chairman…) and the Manager.
router = APIRouter(prefix="/accounts", tags=["Accounts"], dependencies=[Depends(require_manager_above)])


def _amount(v) -> str:
    return str(money(v))


def _account_out(a: Account, balance: Optional[Decimal] = None) -> dict:
    out = {
        "id": str(a.id), "society_id": str(a.society_id), "group_id": str(a.group_id),
        "group_name": a.group.name if a.group else None, "nature": a.group.nature if a.group else None,
        "code": a.code, "name": a.name, "system_key": a.system_key, "description": a.description,
        "is_system": a.is_system, "is_active": a.is_active,
        "opening_balance": _amount(a.opening_balance), "opening_type": a.opening_type,
        "is_cash": a.is_cash, "is_bank": a.is_bank, "is_default_bank": a.is_default_bank,
        "bank_name": a.bank_name, "bank_account_number": a.bank_account_number,
        "bank_ifsc": a.bank_ifsc, "bank_branch": a.bank_branch,
    }
    if balance is not None:
        out["balance"] = _amount(balance)
        out["balance_dr_cr"] = dr_cr(balance)
    return out


def _voucher_out(v: Voucher) -> dict:
    return {
        "id": str(v.id), "society_id": str(v.society_id), "voucher_type": v.voucher_type,
        "voucher_type_label": VOUCHER_TYPES[v.voucher_type][1], "voucher_number": v.voucher_number,
        "voucher_date": v.voucher_date.isoformat(), "fiscal_year": v.fiscal_year,
        "amount": _amount(v.amount), "narration": v.narration, "reference": v.reference,
        "source_type": v.source_type, "source_id": str(v.source_id) if v.source_id else None,
        "is_auto": v.source_type is not None,
        "is_cancelled": v.is_cancelled, "cancel_reason": v.cancel_reason,
        "cancelled_at": v.cancelled_at.isoformat() if v.cancelled_at else None,
        "created_by_name": v.creator.full_name if v.creator else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "entries": [{
            "id": str(e.id), "account_id": str(e.account_id),
            "account_name": e.account.name if e.account else None,
            "debit": _amount(e.debit), "credit": _amount(e.credit),
            "flat_id": str(e.flat_id) if e.flat_id else None,
            "flat_label": flat_label(e.flat) if e.flat else None,
            "vendor_id": str(e.vendor_id) if e.vendor_id else None,
            "vendor_name": e.vendor.company_name if e.vendor else None,
            "narration": e.narration,
        } for e in v.entries],
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    society_id: UUID
    group_id: UUID
    name: str = Field(min_length=1, max_length=150)
    code: Optional[str] = Field(default=None, max_length=20)
    description: Optional[str] = None
    opening_balance: Decimal = Field(default=Decimal(0), ge=0)
    opening_type: Optional[str] = Field(default=None, pattern="^(dr|cr)$")
    is_cash: bool = False
    is_bank: bool = False
    is_default_bank: bool = False
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None


class AccountUpdate(BaseModel):
    group_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    code: Optional[str] = Field(default=None, max_length=20)
    description: Optional[str] = None
    opening_balance: Optional[Decimal] = Field(default=None, ge=0)
    opening_type: Optional[str] = Field(default=None, pattern="^(dr|cr)$")
    is_default_bank: Optional[bool] = None
    is_active: Optional[bool] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None


class VoucherLineIn(BaseModel):
    account_id: UUID
    debit: Decimal = Field(default=Decimal(0), ge=0)
    credit: Decimal = Field(default=Decimal(0), ge=0)
    flat_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    narration: Optional[str] = None


class VoucherCreate(BaseModel):
    society_id: UUID
    voucher_type: str
    voucher_date: date
    narration: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=100)
    entries: List[VoucherLineIn] = Field(min_length=2)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3)


# ── Chart of accounts ─────────────────────────────────────────────────────────

@router.get("/chart/{society_id}")
def chart_of_accounts(society_id: UUID, as_of: Optional[date] = None, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Groups with their ledgers and balances, in Balance Sheet then
    Income & Expenditure order."""
    assert_society_access(user, society_id)
    svc = AccountsService(db)
    rows = svc.chart(society_id, as_of)
    db.commit()  # the standard chart, if this was the first visit
    return [{
        "id": str(r["group"].id), "name": r["group"].name, "nature": r["group"].nature,
        "system_key": r["group"].system_key, "total": _amount(r["total"]), "total_dr_cr": dr_cr(r["total"]),
        "accounts": [_account_out(a, bal) for a, bal in r["accounts"]],
    } for r in rows]


@router.get("/ledgers/{society_id}")
def list_ledgers(society_id: UUID, include_inactive: bool = False, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    rows = AccountsService(db).list_accounts(society_id, include_inactive)
    db.commit()
    return [_account_out(a) for a in rows]


@router.post("/ledgers", status_code=201)
def create_ledger(data: AccountCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, data.society_id)
    return _account_out(AccountsService(db).create_account(data.model_dump(), user))


@router.patch("/ledgers/{account_id}")
def update_ledger(account_id: UUID, data: AccountUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    assert_society_access(user, svc.get_account(account_id).society_id)
    return _account_out(svc.update_account(account_id, data.model_dump(exclude_unset=True), user))


@router.get("/ledgers/{account_id}/statement")
def ledger_statement(account_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                     flat_id: Optional[UUID] = None, vendor_id: Optional[UUID] = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    account = svc.get_account(account_id)
    assert_society_access(user, account.society_id)
    st = svc.ledger_statement(account_id, date_from, date_to, flat_id, vendor_id)
    return {
        "account": _account_out(st["account"]),
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "opening": _amount(st["opening"]), "opening_dr_cr": dr_cr(st["opening"]),
        "total_debit": _amount(st["total_debit"]), "total_credit": _amount(st["total_credit"]),
        "closing": _amount(st["closing"]), "closing_dr_cr": dr_cr(st["closing"]),
        "lines": [{
            **{k: (str(v) if k == "voucher_id" else v) for k, v in l.items()
               if k not in ("debit", "credit", "balance", "date")},
            "date": l["date"].isoformat(), "debit": _amount(l["debit"]), "credit": _amount(l["credit"]),
            "balance": _amount(l["balance"]), "balance_dr_cr": dr_cr(l["balance"]),
        } for l in st["lines"]],
    }


# ── Members' ledger ───────────────────────────────────────────────────────────

@router.get("/members/{society_id}")
def member_balances(society_id: UUID, as_of: Optional[date] = None, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Every flat's balance on Members' Dues (Dr: owes the society)."""
    assert_society_access(user, society_id)
    svc = AccountsService(db)
    rows = svc.member_balances(society_id, as_of)
    dues = svc.system_account(society_id, "members_dues")
    db.commit()
    return {
        "account_id": str(dues.id),
        "members": [{
            "flat_id": str(r["flat"].id), "flat_label": flat_label(r["flat"]),
            "member_name": member_name(r["flat"]),
            "balance": _amount(r["balance"]), "balance_dr_cr": dr_cr(r["balance"]),
        } for r in rows],
    }


# ── Vouchers ──────────────────────────────────────────────────────────────────

@router.get("/vouchers/society/{society_id}")
def list_vouchers(society_id: UUID, voucher_type: Optional[str] = None,
                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                  include_cancelled: bool = True, skip: int = 0, limit: int = Query(100, le=500),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The day book."""
    assert_society_access(user, society_id)
    rows = AccountsService(db).list_vouchers(society_id, voucher_type, date_from, date_to,
                                             include_cancelled, skip, limit)
    return [_voucher_out(v) for v in rows]


@router.post("/vouchers", status_code=201)
def create_voucher(data: VoucherCreate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    assert_society_access(user, data.society_id)
    v = AccountsService(db).create_manual_voucher(data.model_dump(), user, request)
    return _voucher_out(v)


@router.get("/vouchers/{voucher_id}")
def get_voucher(voucher_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    v = AccountsService(db).get_voucher(voucher_id)
    assert_society_access(user, v.society_id)
    return _voucher_out(v)


@router.post("/vouchers/{voucher_id}/cancel")
def cancel_voucher(voucher_id: UUID, data: CancelRequest, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    assert_society_access(user, svc.get_voucher(voucher_id).society_id)
    return _voucher_out(svc.cancel_manual_voucher(voucher_id, data.reason, user, request))


# ── Summary & automatic postings ──────────────────────────────────────────────

@router.get("/summary/{society_id}")
def accounts_summary(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    svc = AccountsService(db)
    s = svc.summary(society_id)
    pending = AccountPostings(db, svc).pending_count(society_id)
    db.commit()
    return {
        "fy": s["fy"],
        "cash": _amount(s["cash"]), "bank": _amount(s["bank"]),
        "members_dues": _amount(s["members_dues"]), "members_dues_dr_cr": dr_cr(s["members_dues"]),
        "creditors": _amount(s["creditors"]),
        "fy_income": _amount(s["fy_income"]), "fy_expense": _amount(s["fy_expense"]),
        "fy_surplus": _amount(s["fy_income"] - s["fy_expense"]),
        "cash_bank_accounts": [_account_out(a, bal) for a, bal in s["cash_bank_accounts"]],
        "pending_postings": pending,
    }


@router.post("/sync/{society_id}")
def sync_postings(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Post every bill, payment and vendor bill not yet in the books."""
    assert_society_access(user, society_id)
    counts = AccountPostings(db).sync_society(society_id, user)
    db.commit()
    return counts
