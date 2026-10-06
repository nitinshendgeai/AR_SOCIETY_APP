from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_current_user, require_admin_committee, require_manager_above
from app.core.tenant_scope import assert_society_access
from app.db.session import get_db
from app.models.flat import Flat
from app.models.society import Society
from app.models.user import User
from app.modules.accounts.models.accounts import VOUCHER_TYPES, Account, Voucher
from app.modules.accounts.services.accounts_service import AccountsService, dr_cr, fiscal_year, money
from app.modules.accounts.services.expense_by_element import expenses_by_element
from app.modules.accounts.services.postings import AccountPostings
from app.modules.accounts.services.reports import REPORTS, FinancialReports
from app.modules.accounts.services.documents_pdf import (
    render_day_book_pdf, render_ledger_pdf, render_members_ledger_pdf, render_voucher_pdf,
)
from app.modules.accounts.services.reports_pdf import render_report_pdf
from app.modules.billing.services.bill_pdf import flat_label, member_name

# The society's books are kept by those who run it: Admin, the committee
# (Treasurer, Secretary, Chairman…) and the Manager.
router = APIRouter(prefix="/accounts", tags=["Accounts"], dependencies=[Depends(require_manager_above)])


def _amount(v) -> str:
    return str(money(v))


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={filename}"})


def _society(db: Session, society_id) -> Optional[Society]:
    return db.query(Society).filter(Society.id == society_id).first()


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text).strip("-")


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
        "maintenance_element_id": str(a.maintenance_element_id) if a.maintenance_element_id else None,
        "maintenance_element_name": a.maintenance_element_name,
    }
    if balance is not None:
        out["balance"] = _amount(balance)
        out["balance_dr_cr"] = dr_cr(balance)
    return out


def _voucher_out(v: Voucher, closed_years: frozenset = frozenset()) -> dict:
    locked = v.fiscal_year in closed_years
    return {
        "id": str(v.id), "society_id": str(v.society_id), "voucher_type": v.voucher_type,
        "voucher_type_label": VOUCHER_TYPES[v.voucher_type][1], "voucher_number": v.voucher_number,
        "voucher_date": v.voucher_date.isoformat(), "fiscal_year": v.fiscal_year,
        "amount": _amount(v.amount), "narration": v.narration, "reference": v.reference,
        "source_type": v.source_type, "source_id": str(v.source_id) if v.source_id else None,
        "is_auto": v.source_type is not None or v.voucher_type == "closing" or v.reversal_of_id is not None,
        "is_locked": locked, "is_reversed": v.reversed_at is not None,
        "reversal_of_id": str(v.reversal_of_id) if v.reversal_of_id else None,
        "is_cancelled": v.is_cancelled, "cancel_reason": v.cancel_reason,
        "cancelled_at": v.cancelled_at.isoformat() if v.cancelled_at else None,
        "created_by_name": v.creator.full_name if v.creator else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "edited_by_name": v.editor.full_name if v.editor else None,
        "edited_at": v.edited_at.isoformat() if v.edited_at else None,
        "revisions": [{
            "revision_no": r.revision_no, "reason": r.reason,
            "edited_at": r.created_at.isoformat() if r.created_at else None,
            "edited_by_name": r.editor.full_name if r.editor else None,
            "before": r.snapshot,
        } for r in reversed(v.revisions)],
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
    maintenance_element_id: Optional[UUID] = None


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
    maintenance_element_id: Optional[UUID] = None   # null clears the link


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


class VoucherUpdate(BaseModel):
    voucher_date: date
    narration: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=100)
    entries: List[VoucherLineIn] = Field(min_length=2)
    reason: str = Field(min_length=3)


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
                     format: str = Query("json", pattern="^(json|pdf)$"),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A ledger's postings in a period with the running balance — or, with
    `flat_id` / `vendor_id`, a member's or vendor's account. ?format=pdf: the
    printed ledger account."""
    svc = AccountsService(db)
    account = svc.get_account(account_id)
    assert_society_access(user, account.society_id)
    st = svc.ledger_statement(account_id, date_from, date_to, flat_id, vendor_id)
    out = _statement_out(st, date_from, date_to)
    if format == "pdf":
        title = None
        if flat_id:
            flat = (db.query(Flat).options(joinedload(Flat.wing), selectinload(Flat.residents))
                    .filter(Flat.id == flat_id).first())
            title = f"{flat_label(flat)} · {member_name(flat)}" if flat else None
        elif vendor_id:
            from app.modules.vendor.models.vendor import Vendor
            vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
            title = vendor.company_name if vendor else None
        heading = title or account.name
        return _pdf(render_ledger_pdf(out, _society(db, account.society_id), title=title),
                    f"Ledger-{_slug(heading)}.pdf")
    return out


def _statement_out(st: dict, date_from: Optional[date], date_to: Optional[date]) -> dict:
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
def member_balances(society_id: UUID, as_of: Optional[date] = None,
                    format: str = Query("json", pattern="^(json|pdf)$"),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every flat's balance on Members' Dues (Dr: owes the society).
    ?format=pdf: the printed list with totals."""
    assert_society_access(user, society_id)
    svc = AccountsService(db)
    rows = svc.member_balances(society_id, as_of)
    dues = svc.system_account(society_id, "members_dues")
    db.commit()
    if format == "pdf":
        members = [{"flat_label": flat_label(r["flat"]), "member_name": member_name(r["flat"]),
                    "balance": _amount(r["balance"])} for r in rows]
        as_of = as_of or date.today()
        return _pdf(render_members_ledger_pdf(members, _society(db, society_id), as_of),
                    f"Members-Ledger-{as_of.isoformat()}.pdf")
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
    svc = AccountsService(db)
    rows = svc.list_vouchers(society_id, voucher_type, date_from, date_to, include_cancelled, skip, limit)
    closed = frozenset(svc.closed_years(society_id))
    return [_voucher_out(v, closed) for v in rows]


@router.get("/day-book/{society_id}/pdf")
def day_book_pdf(society_id: UUID, voucher_type: Optional[str] = None,
                 date_from: Optional[date] = None, date_to: Optional[date] = None,
                 include_cancelled: bool = True, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """The printed day book: every voucher of the period, oldest first,
    with its lines."""
    assert_society_access(user, society_id)
    svc = AccountsService(db)
    rows = svc.list_vouchers(society_id, voucher_type, date_from, date_to, include_cancelled, 0, None)
    rows.sort(key=lambda v: (v.voucher_date, v.created_at or datetime.min))
    label = VOUCHER_TYPES[voucher_type][1] if voucher_type in VOUCHER_TYPES else None
    pdf = render_day_book_pdf([_voucher_out(v) for v in rows], _society(db, society_id), date_from, date_to,
                              type_label=label)
    span = "-".join(d.isoformat() for d in (date_from, date_to) if d) or "all"
    return _pdf(pdf, f"Day-Book-{span}.pdf")


@router.post("/vouchers", status_code=201)
def create_voucher(data: VoucherCreate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    assert_society_access(user, data.society_id)
    v = AccountsService(db).create_manual_voucher(data.model_dump(), user, request)
    return _voucher_out(v)


@router.get("/vouchers/{voucher_id}")
def get_voucher(voucher_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    v = svc.get_voucher(voucher_id)
    assert_society_access(user, v.society_id)
    return _voucher_out(v, frozenset(svc.closed_years(v.society_id)))


@router.get("/vouchers/{voucher_id}/pdf")
def voucher_pdf(voucher_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The voucher printed on half a sheet, with signature boxes."""
    svc = AccountsService(db)
    v = svc.get_voucher(voucher_id)
    assert_society_access(user, v.society_id)
    return _pdf(render_voucher_pdf(_voucher_out(v), _society(db, v.society_id)),
                f"{_slug(v.voucher_number)}.pdf")


@router.put("/vouchers/{voucher_id}")
def update_voucher(voucher_id: UUID, data: VoucherUpdate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Correct a voucher the society entered, in an open year. The version
    before the edit is kept in the voucher's history."""
    svc = AccountsService(db)
    assert_society_access(user, svc.get_voucher(voucher_id).society_id)
    v = svc.update_manual_voucher(voucher_id, data.model_dump(), user, request)
    return _voucher_out(v, frozenset(svc.closed_years(v.society_id)))


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


@router.get("/expenses-by-element/{society_id}")
def expenses_by_element_report(society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """What was spent on each maintenance element between two dates (default: this month): per element and
    ledger, plus spend on expense ledgers that no element covers. Reads the books, so every voucher, vendor bill and
    journal counts."""
    assert_society_access(user, society_id)
    today = date.today()
    start = date_from or today.replace(day=1)
    end = date_to or today
    if end < start:
        raise HTTPException(status_code=422, detail="The end date can't be before the start date")
    AccountsService(db).ensure_chart(society_id)        # the books are opened the first time anyone looks
    db.commit()
    return expenses_by_element(db, society_id, start, end)


@router.post("/sync/{society_id}")
def sync_postings(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Post every bill, payment and vendor bill not yet in the books."""
    assert_society_access(user, society_id)
    counts = AccountPostings(db).sync_society(society_id, user)
    db.commit()
    return counts


# ── Financial statements & year-end closing ───────────────────────────────────

class CloseYearRequest(BaseModel):
    reserve_pct: Decimal = Field(default=Decimal(0), ge=0, le=100)
    notes: Optional[str] = None


class ReopenYearRequest(BaseModel):
    reason: str = Field(min_length=3)


@router.get("/reports/{society_id}/{report}")
def financial_report(society_id: UUID, report: str, fy: Optional[str] = None,
                     format: str = Query("json", pattern="^(json|pdf)$"),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Trial Balance, Income & Expenditure, Balance Sheet, Receipts &
    Payments or Schedule of Funds for a financial year ('2026-27'; default:
    the current one) — as data, or ?format=pdf in the printed format."""
    assert_society_access(user, society_id)
    fy = fy or fiscal_year(date.today())
    data = FinancialReports(db).report(society_id, report, fy)
    if format == "pdf":
        society = db.query(Society).filter(Society.id == society_id).first()
        name = REPORTS[report].replace("&", "and").replace(" ", "-")
        return Response(content=render_report_pdf(data, society), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename={name}-FY-{fy}.pdf"})
    return data


@router.get("/years/{society_id}")
def financial_years(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    years = FinancialReports(db).years(society_id)
    db.commit()
    return years


@router.post("/years/{society_id}/{fy}/close", dependencies=[Depends(require_admin_committee)])
def close_financial_year(society_id: UUID, fy: str, data: CloseYearRequest, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """Close the books of a year that is over: transfer income and
    expenditure to the Income & Expenditure Account, carry the chosen share
    of a surplus to the Reserve Fund, and lock the year. Admin and the
    committee only."""
    assert_society_access(user, society_id)
    rec = FinancialReports(db).close_year(society_id, fy, data.reserve_pct, data.notes, user)
    return {"fy": rec.fiscal_year, "surplus": str(rec.surplus), "reserve_transfer": str(rec.reserve_transfer),
            "closing_voucher_id": str(rec.closing_voucher_id) if rec.closing_voucher_id else None}


@router.post("/years/{society_id}/{fy}/reopen", dependencies=[Depends(require_admin_committee)])
def reopen_financial_year(society_id: UUID, fy: str, data: ReopenYearRequest, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    rec = FinancialReports(db).reopen_year(society_id, fy, data.reason, user)
    return {"fy": rec.fiscal_year, "reopened_at": rec.reopened_at.isoformat()}
