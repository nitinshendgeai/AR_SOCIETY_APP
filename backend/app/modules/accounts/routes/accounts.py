from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_current_user, require_admin_committee, require_manager_above
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.db.session import get_db
from app.models.flat import Flat
from app.models.society import Society
from app.models.user import User
from app.modules.accounts.models.accounts import VOUCHER_TYPES, Account, Voucher
from app.modules.accounts.models.posting_errors import AccountingPostingError
from app.modules.accounts.services.accounts_service import AccountsService, dr_cr, fiscal_year, money
from app.modules.accounts.services.expense_by_element import expenses_by_element
from app.modules.accounts.services.recurring_expenses import RecurringExpenseService, first_of
from app.modules.accounts.services.postings import AccountPostings
from app.modules.accounts.services.posting_errors import AccountingPostingErrorService
from app.modules.accounts.services.member_ar import MemberARService
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
        "approval_status": v.approval_status,
        "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
        "submitted_by_name": v.submitter.full_name if v.submitter else None,
        "approved_at": v.approved_at.isoformat() if v.approved_at else None,
        "approved_by_name": v.approver.full_name if v.approver else None,
        "approval_note": v.approval_note,
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


class RecurringExpenseCreate(BaseModel):
    society_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=150)
    expense_account_id: UUID
    paid_from_id: Optional[UUID] = None
    amount: Optional[Decimal] = Field(default=None, ge=0)     # blank: it changes every month
    day_of_month: int = Field(default=1, ge=1, le=31)
    start_month: Optional[date] = None
    end_month: Optional[date] = None
    payee: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = None


class RecurringExpenseUpdate(BaseModel):
    """Only fields sent change; send null to clear an optional one."""
    name: Optional[str] = Field(default=None, max_length=150)
    expense_account_id: Optional[UUID] = None
    paid_from_id: Optional[UUID] = None
    amount: Optional[Decimal] = Field(default=None, ge=0)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    start_month: Optional[date] = None
    end_month: Optional[date] = None
    payee: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = None
    is_active: Optional[bool] = None


class RecurringRecordIn(BaseModel):
    month: date
    amount: Optional[Decimal] = Field(default=None, ge=0)     # needed when the expense has no fixed amount
    voucher_date: Optional[date] = None                         # default: today
    paid_from_id: Optional[UUID] = None                         # default: the expense's, else cash in hand
    reference: Optional[str] = Field(default=None, max_length=100)
    note: Optional[str] = None


class RecurringSkipIn(BaseModel):
    month: date
    reason: Optional[str] = None


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3)


class ApprovalNote(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


class RejectVoucherRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class ResolvePostingErrorRequest(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


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




# ── Member AR subledger & reconciliation ─────────────────────────────────────

@router.get("/members/{society_id}/ar-reconciliation")
def member_ar_reconciliation(society_id: UUID, date_from: Optional[date] = None,
                            date_to: Optional[date] = None,
                            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Society-wide reconciliation of formal member AR against billing outstanding."""
    assert_society_access(user, society_id)
    return MemberARService(db).society_reconciliation(society_id, date_from, date_to)


@router.get("/members/{society_id}/{flat_id}/ar-statement")
def member_ar_statement(society_id: UUID, flat_id: UUID,
                        date_from: Optional[date] = None, date_to: Optional[date] = None,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Formal member AR ledger with bill-wise operational reconciliation."""
    assert_society_access(user, society_id)
    try:
        return MemberARService(db).statement(society_id, flat_id, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


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


@router.get("/vouchers/{society_id}/pending-approvals")
def pending_voucher_approvals(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    rows = db.query(Voucher).filter(
        Voucher.society_id == society_id,
        Voucher.approval_status == "pending",
        Voucher.is_cancelled == False,
    ).order_by(Voucher.voucher_date, Voucher.created_at).all()
    return [_voucher_out(v) for v in rows]


@router.post("/vouchers/{voucher_id}/approve", dependencies=[Depends(require_admin_committee)])
def approve_voucher(voucher_id: UUID, data: ApprovalNote, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    v = svc.get_voucher(voucher_id)
    assert_society_access(user, v.society_id)
    return _voucher_out(svc.approve_manual_voucher(voucher_id, user, data.note))


@router.post("/vouchers/{voucher_id}/reject", dependencies=[Depends(require_admin_committee)])
def reject_voucher(voucher_id: UUID, data: RejectVoucherRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = AccountsService(db)
    v = svc.get_voucher(voucher_id)
    assert_society_access(user, v.society_id)
    return _voucher_out(svc.reject_manual_voucher(voucher_id, user, data.reason))


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


@router.get("/posting-errors/{society_id}")
def posting_errors(society_id: UUID, status: Optional[str] = None, limit: int = Query(100, le=500),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    try:
        rows = AccountingPostingErrorService(db).list(society_id, status, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return [{
        "id": str(r.id), "society_id": str(r.society_id), "source_type": r.source_type,
        "source_id": str(r.source_id), "operation": r.operation, "error_code": r.error_code,
        "error_message": r.error_message, "first_failed_at": r.first_failed_at.isoformat(),
        "last_failed_at": r.last_failed_at.isoformat(), "retry_count": r.retry_count,
        "status": r.status, "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "resolution_note": r.resolution_note, "last_voucher_id": str(r.last_voucher_id) if r.last_voucher_id else None,
    } for r in rows]


@router.post("/posting-errors/{error_id}/resolve", dependencies=[Depends(require_admin_committee)])
def resolve_posting_error(error_id: UUID, data: ResolvePostingErrorRequest,
                          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(AccountingPostingError).filter(AccountingPostingError.id == error_id).first()
    if not row:
        raise HTTPException(404, "Posting exception not found")
    assert_society_access(user, row.society_id)
    if row.status == "RESOLVED":
        raise HTTPException(409, "Posting exception is already resolved")
    row.status = "RESOLVED"
    row.resolved_at = datetime.utcnow()
    row.resolved_by = user.id
    row.resolution_note = data.note
    db.commit()
    return {"id": str(row.id), "status": row.status, "resolution_note": row.resolution_note}


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


# ── Recurring monthly expenses ────────────────────────────────────────────────

def _element_name(db: Session, account) -> Optional[str]:
    if account is None or account.maintenance_element_id is None:
        return None
    from app.modules.billing.models.billing import MaintenanceElement
    el = db.query(MaintenanceElement).filter(MaintenanceElement.id == account.maintenance_element_id).first()
    return el.name if el else None


def _recurring_out(db: Session, r, today_months: int = 0) -> dict:
    return {
        "id": str(r.id), "society_id": str(r.society_id), "name": r.name,
        "expense_account_id": str(r.expense_account_id),
        "expense_account_name": r.expense_account.name if r.expense_account else None,
        "element_name": _element_name(db, r.expense_account),
        "paid_from_id": str(r.paid_from_id) if r.paid_from_id else None,
        "paid_from_name": r.paid_from.name if r.paid_from else None,
        "amount": _amount(r.amount) if r.amount is not None else None,
        "day_of_month": r.day_of_month,
        "start_month": r.start_month.isoformat(),
        "end_month": r.end_month.isoformat() if r.end_month else None,
        "payee": r.payee, "note": r.note, "is_active": r.is_active,
        "due_months": today_months,
    }


@router.post("/recurring-expenses", status_code=201)
def create_recurring_expense(data: RecurringExpenseCreate, request: Request, db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    body = data.model_dump()
    body["society_id"] = resolve_create_society_id(user, data.society_id)
    svc = RecurringExpenseService(db)
    r = svc.create(body, user, request)
    return _recurring_out(db, r, len(svc.due_months(r, svc._today(r.society_id))))


@router.get("/recurring-expenses/{society_id}")
def list_recurring_expenses(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    svc = RecurringExpenseService(db)
    today = svc._today(society_id)
    return [_recurring_out(db, r, len(svc.due_months(r, today))) for r in svc.list(society_id)]


@router.get("/recurring-expenses/{society_id}/due")
def recurring_expenses_due(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The months that have come due and nobody has recorded or skipped, oldest first."""
    assert_society_access(user, society_id)
    out = []
    for row in RecurringExpenseService(db).due(society_id):
        r = row["recurring"]
        out.append({
            "recurring_id": str(r.id), "name": r.name, "month": row["month"].isoformat(),
            "due_date": row["due_date"].isoformat(), "days_late": row["days_late"],
            "amount": _amount(r.amount) if r.amount is not None else None,
            "expense_account_id": str(r.expense_account_id),
            "expense_account_name": r.expense_account.name if r.expense_account else None,
            "element_name": _element_name(db, r.expense_account),
            "paid_from_id": str(r.paid_from_id) if r.paid_from_id else None,
            "payee": r.payee,
        })
    return out


@router.patch("/recurring-expenses/{recurring_id}")
def update_recurring_expense(recurring_id: UUID, data: RecurringExpenseUpdate, request: Request,
                             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = RecurringExpenseService(db)
    r = svc.update(recurring_id, data.model_dump(exclude_unset=True), user, request)
    return _recurring_out(db, r, len(svc.due_months(r, svc._today(r.society_id))))


@router.post("/recurring-expenses/{recurring_id}/record", status_code=201)
def record_recurring_expense(recurring_id: UUID, data: RecurringRecordIn, request: Request,
                             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Record a due month as a payment voucher."""
    v = RecurringExpenseService(db).record(recurring_id, data.model_dump(), user, request)
    return _voucher_out(v)


@router.post("/recurring-expenses/{recurring_id}/skip")
def skip_recurring_expense(recurring_id: UUID, data: RecurringSkipIn, request: Request,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    RecurringExpenseService(db).skip(recurring_id, data.month, data.reason, user, request)
    return {"skipped": first_of(data.month).isoformat()}
