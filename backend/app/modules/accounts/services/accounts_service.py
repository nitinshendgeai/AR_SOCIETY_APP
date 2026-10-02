"""
AccountsService — the society's books: chart of accounts, vouchers,
balances, ledger statements and the members' (flat-wise) ledger.

Balances are signed debit-positive throughout: a positive balance is a
debit (Dr) balance, a negative one a credit (Cr) balance. Cancelled
vouchers never count.

Closed financial years are locked: no voucher can be entered in them or
cancelled. Automatic postings dated in a closed year are made on the first
day of the next open year, and a posting of a closed year whose bill or
payment is later cancelled is reversed in the open year.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.user import User
from app.models.wing import Wing
from app.modules.accounts.models.accounts import (
    DEBIT_NATURES, MANUAL_VOUCHER_TYPES, VOUCHER_TYPES, Account, AccountGroup, FinancialYearClosing, Voucher,
    VoucherEntry,
)
from app.modules.accounts.services.chart_of_accounts import seed_chart_of_accounts
from app.modules.billing.models.billing import MaintenanceSettings
from app.services.audit_service import AuditService

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(str(v if v is not None else 0)).quantize(CENT)


def fiscal_year_start(d: date) -> date:
    """Indian financial year: 1 April to 31 March."""
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1)


def fiscal_year(d: date) -> str:
    """'2026-27' for any date from 1 Apr 2026 to 31 Mar 2027."""
    start = fiscal_year_start(d).year
    return f"{start}-{str(start + 1)[-2:]}"


def fiscal_year_bounds(fy: str) -> tuple:
    """(1 April, 31 March) of '2026-27'."""
    try:
        start = int(fy.split("-")[0])
        if len(fy) != 7 or fy[4] != "-" or fy[5:] != str(start + 1)[-2:]:
            raise ValueError
    except (ValueError, IndexError):
        raise HTTPException(422, "Financial year must look like 2026-27")
    return date(start, 4, 1), date(start + 1, 3, 31)


def previous_fiscal_year(fy: str) -> str:
    start = int(fy[:4]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def live_posting():
    """A voucher still in effect for its source: neither cancelled nor
    reversed in a later year."""
    return (Voucher.is_cancelled == False) & Voucher.reversed_at.is_(None)  # noqa: E712


def signed_opening(account: Account) -> Decimal:
    amt = money(account.opening_balance)
    return amt if account.opening_type == "dr" else -amt


def dr_cr(balance: Decimal) -> dict:
    """{'amount': '1500.00', 'type': 'Dr'} for a signed balance."""
    balance = money(balance)
    return {"amount": str(abs(balance)), "type": "Dr" if balance >= 0 else "Cr"}


@dataclass
class Line:
    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    flat_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    narration: Optional[str] = None


class AccountsService:

    def __init__(self, db: Session):
        self.db = db
        self._charts: Dict[UUID, Dict[str, Account]] = {}
        self._closed: Dict[UUID, set] = {}

    def _audit(self, action, entity, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="accounts",
                         entity_id=str(entity.id), entity_type=type(entity).__name__,
                         user=user, request=request, **kw)

    # ── Closed years ──────────────────────────────────────────────────────────

    def closed_years(self, society_id: UUID) -> set:
        """Financial years ('2025-26') whose books are closed."""
        if society_id not in self._closed:
            self._closed[society_id] = {fy for (fy,) in self.db.query(FinancialYearClosing.fiscal_year).filter(
                FinancialYearClosing.society_id == society_id, FinancialYearClosing.reopened_at.is_(None),
                FinancialYearClosing.is_active == True)}  # noqa: E712
        return self._closed[society_id]

    def forget_closed_years(self, society_id: UUID) -> None:
        self._closed.pop(society_id, None)

    def is_closed(self, society_id: UUID, d: date) -> bool:
        return fiscal_year(d) in self.closed_years(society_id)

    def open_posting_date(self, society_id: UUID, d: date) -> date:
        """`d`, or — when its year's books are closed — the first day of the
        next year that is open."""
        while self.is_closed(society_id, d):
            d = date(fiscal_year_start(d).year + 1, 4, 1)
        return d

    def assert_open(self, society_id: UUID, d: date) -> None:
        if self.is_closed(society_id, d):
            raise HTTPException(409, f"The books for FY {fiscal_year(d)} are closed — "
                                     "enter it in the current year, or reopen that year first")

    # ── Chart of accounts ─────────────────────────────────────────────────────

    def ensure_chart(self, society_id: UUID) -> Dict[str, Account]:
        """{system_key: Account} — seeding the standard chart the first time
        a society's books are opened."""
        if society_id not in self._charts:
            accounts = {a.system_key: a for a in self.db.query(Account).filter(
                Account.society_id == society_id, Account.system_key.isnot(None)).all()}
            if not accounts:
                settings = self.db.query(MaintenanceSettings).filter(
                    MaintenanceSettings.society_id == society_id).first()
                accounts = seed_chart_of_accounts(self.db, society_id, settings)
            self._charts[society_id] = accounts
        return self._charts[society_id]

    def system_account(self, society_id: UUID, key: str) -> Account:
        chart = self.ensure_chart(society_id)
        if key not in chart:  # a standard ledger added after this society's chart was seeded
            settings = self.db.query(MaintenanceSettings).filter(
                MaintenanceSettings.society_id == society_id).first()
            chart.update(seed_chart_of_accounts(self.db, society_id, settings))
        return chart[key]

    def default_bank(self, society_id: UUID) -> Account:
        self.ensure_chart(society_id)
        bank = self.db.query(Account).filter(
            Account.society_id == society_id, Account.is_default_bank == True,
            Account.is_bank == True, Account.is_active == True,
        ).order_by(Account.created_at).first()
        return bank or self.system_account(society_id, "bank")

    def list_groups(self, society_id: UUID) -> List[AccountGroup]:
        self.ensure_chart(society_id)
        return self.db.query(AccountGroup).filter(
            AccountGroup.society_id == society_id, AccountGroup.is_active == True,
        ).order_by(AccountGroup.sort_order, AccountGroup.name).all()

    def list_accounts(self, society_id: UUID, include_inactive: bool = False) -> List[Account]:
        self.ensure_chart(society_id)
        q = self.db.query(Account).options(joinedload(Account.group)).filter(Account.society_id == society_id)
        if not include_inactive:
            q = q.filter(Account.is_active == True)
        return q.order_by(Account.code, Account.name).all()

    def get_account(self, account_id: UUID) -> Account:
        a = self.db.query(Account).filter(Account.id == account_id).first()
        if not a:
            raise HTTPException(404, "Ledger not found")
        return a

    def _group_for(self, society_id: UUID, group_id: UUID) -> AccountGroup:
        g = self.db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not g or g.society_id != society_id:
            raise HTTPException(422, "Account group not found in this society")
        return g

    def _name_free(self, society_id: UUID, name: str, exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Account).filter(Account.society_id == society_id,
                                          func.lower(Account.name) == name.strip().lower())
        if exclude_id:
            q = q.filter(Account.id != exclude_id)
        if q.first():
            raise HTTPException(409, f"A ledger named '{name.strip()}' already exists")

    def _clear_default_bank(self, society_id: UUID, keep: Account) -> None:
        for other in self.db.query(Account).filter(Account.society_id == society_id,
                                                   Account.is_default_bank == True, Account.id != keep.id):
            other.is_default_bank = False

    def _check_opening(self, society_id: UUID, nature: str, amount, changing: bool) -> None:
        """Income and expenditure ledgers start every year at nil — a
        surplus brought forward belongs on the Income & Expenditure Account
        ledger. Opening balances are fixed once a year's books are closed,
        since every later year is built on them."""
        if money(amount) and nature in ("income", "expense"):
            raise HTTPException(422, "Income and expenditure ledgers have no opening balance — put the surplus "
                                     "brought forward on the Income & Expenditure Account ledger")
        if changing and self.closed_years(society_id):
            raise HTTPException(409, "Opening balances can't change once a year's books are closed")

    def create_account(self, data: dict, user: User) -> Account:
        society_id = data["society_id"]
        self.ensure_chart(society_id)
        group = self._group_for(society_id, data["group_id"])
        self._check_opening(society_id, group.nature, data.get("opening_balance"),
                            changing=bool(money(data.get("opening_balance"))))
        self._name_free(society_id, data["name"])
        if data.get("is_bank") and data.get("is_cash"):
            raise HTTPException(422, "A ledger is either a cash or a bank account, not both")
        if (data.get("is_bank") or data.get("is_cash")) and group.nature != "asset":
            raise HTTPException(422, "Cash and bank ledgers belong under an asset group")
        account = Account(
            society_id=society_id, group_id=group.id, name=data["name"].strip(), code=data.get("code"),
            description=data.get("description"),
            opening_balance=money(data.get("opening_balance")), opening_type=data.get("opening_type") or (
                "dr" if group.nature in DEBIT_NATURES else "cr"),
            is_cash=bool(data.get("is_cash")), is_bank=bool(data.get("is_bank")),
            is_default_bank=bool(data.get("is_bank") and data.get("is_default_bank")),
            bank_name=data.get("bank_name"), bank_account_number=data.get("bank_account_number"),
            bank_ifsc=data.get("bank_ifsc"), bank_branch=data.get("bank_branch"),
            sort_order=9000,
        )
        self.db.add(account)
        self.db.flush()
        if account.is_default_bank:
            self._clear_default_bank(society_id, account)
        self._audit(AuditAction.CREATE, account, user, new_values={"name": account.name, "group": group.name})
        self.db.commit()
        self.db.refresh(account)
        return account

    def update_account(self, account_id: UUID, data: dict, user: User) -> Account:
        account = self.get_account(account_id)
        if "name" in data and data["name"]:
            self._name_free(account.society_id, data["name"], exclude_id=account.id)
            account.name = data["name"].strip()
        if "group_id" in data and data["group_id"] and data["group_id"] != account.group_id:
            if account.is_system:
                raise HTTPException(409, "A standard ledger stays in its group")
            account.group_id = self._group_for(account.society_id, data["group_id"]).id
        for field in ("code", "description", "bank_name", "bank_account_number", "bank_ifsc", "bank_branch"):
            if field in data:
                setattr(account, field, data[field])
        new_amount = (money(data["opening_balance"]) if data.get("opening_balance") is not None
                      else money(account.opening_balance))
        nature = self._group_for(account.society_id, account.group_id).nature
        new_type = (data["opening_type"] if data.get("opening_type") in ("dr", "cr")
                    else account.opening_type if money(account.opening_balance)
                    else "dr" if nature in DEBIT_NATURES else "cr")   # a new balance sits on the ledger's usual side
        changing = new_amount != money(account.opening_balance) or bool(
            new_amount and new_type != account.opening_type)
        self._check_opening(account.society_id, nature, new_amount, changing)
        account.opening_balance, account.opening_type = new_amount, new_type
        if data.get("is_default_bank"):
            if not account.is_bank:
                raise HTTPException(422, "Only a bank ledger can be the default bank")
            account.is_default_bank = True
            self._clear_default_bank(account.society_id, account)
        if "is_active" in data and data["is_active"] is not None:
            if not data["is_active"] and account.is_system:
                raise HTTPException(409, "Standard ledgers can't be deactivated")
            account.is_active = data["is_active"]
        self._audit(AuditAction.UPDATE, account, user,
                    new_values={k: str(v) for k, v in data.items() if v is not None})
        self.db.commit()
        self.db.refresh(account)
        return account

    # ── Vouchers ──────────────────────────────────────────────────────────────

    def _next_number(self, society_id: UUID, voucher_type: str, voucher_date: date) -> str:
        prefix = VOUCHER_TYPES[voucher_type][0]
        fy = fiscal_year(voucher_date)
        n = self.db.query(func.count(Voucher.id)).filter(
            Voucher.society_id == society_id, Voucher.voucher_type == voucher_type,
            Voucher.fiscal_year == fy).scalar() + 1
        while True:
            number = f"{prefix}/{fy}/{n:04d}"
            if not self.db.query(Voucher.id).filter(Voucher.society_id == society_id,
                                                    Voucher.voucher_number == number).first():
                return number
            n += 1

    def build_voucher(self, society_id: UUID, voucher_type: str, voucher_date: date, lines: List[Line], *,
                      narration: Optional[str] = None, reference: Optional[str] = None,
                      source_type: Optional[str] = None, source_id: Optional[UUID] = None,
                      reversal_of_id: Optional[UUID] = None, user: Optional[User] = None) -> Voucher:
        """Validate that `lines` balance and record the voucher (flushed, not
        committed)."""
        lines = [l for l in lines if money(l.debit) or money(l.credit)]
        if len(lines) < 2:
            raise HTTPException(422, "A voucher needs at least one debit and one credit line")
        for l in lines:
            l.debit, l.credit = money(l.debit), money(l.credit)
            if l.debit < 0 or l.credit < 0 or (l.debit and l.credit):
                raise HTTPException(422, "Each line is either a debit or a credit, of a positive amount")
            if l.account.society_id != society_id:
                raise HTTPException(422, "Ledger belongs to a different society")
        total_dr = sum((l.debit for l in lines), ZERO)
        total_cr = sum((l.credit for l in lines), ZERO)
        if total_dr != total_cr:
            raise HTTPException(422, f"Debits (₹{total_dr}) and credits (₹{total_cr}) must be equal")
        if voucher_type != "closing":
            self.assert_open(society_id, voucher_date)

        voucher = Voucher(
            society_id=society_id, voucher_type=voucher_type,
            voucher_number=self._next_number(society_id, voucher_type, voucher_date),
            voucher_date=voucher_date, fiscal_year=fiscal_year(voucher_date), amount=total_dr,
            narration=narration, reference=reference, source_type=source_type, source_id=source_id,
            reversal_of_id=reversal_of_id, created_by=user.id if user else None,
        )
        for i, l in enumerate(lines):
            voucher.entries.append(VoucherEntry(
                account_id=l.account.id, line_no=i + 1, debit=l.debit, credit=l.credit,
                flat_id=l.flat_id, vendor_id=l.vendor_id, narration=l.narration,
            ))
        self.db.add(voucher)
        self.db.flush()
        return voucher

    def _flat_in_society(self, flat_id: UUID, society_id: UUID) -> Flat:
        flat = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
                .filter(Flat.id == flat_id, Wing.society_id == society_id).first())
        if not flat:
            raise HTTPException(422, "Flat not found in this society")
        return flat

    def create_manual_voucher(self, data: dict, user: User, request=None) -> Voucher:
        """Receipt, Payment, Journal or Contra entered by the society. The
        usual rules: a Receipt brings money into cash/bank (debit cash/bank,
        credit the rest), a Payment takes it out (credit cash/bank, debit the
        rest), a Contra moves it between cash and bank only, and a Journal
        never touches cash or bank."""
        society_id, vtype = data["society_id"], data["voucher_type"]
        if vtype not in MANUAL_VOUCHER_TYPES:
            raise HTTPException(422, f"Voucher type must be one of: {', '.join(MANUAL_VOUCHER_TYPES)}")
        chart = self.ensure_chart(society_id)
        members_dues, creditors = chart["members_dues"], chart["sundry_creditors"]

        lines = []
        for e in data["entries"]:
            account = self.get_account(e["account_id"])
            if account.society_id != society_id or not account.is_active:
                raise HTTPException(422, "Ledger not found in this society")
            if account.id == members_dues.id:
                if not e.get("flat_id"):
                    raise HTTPException(422, f"Choose the flat for the {account.name} line")
                self._flat_in_society(e["flat_id"], society_id)
            elif e.get("flat_id"):
                raise HTTPException(422, f"A flat can only be tagged on {members_dues.name}")
            if e.get("vendor_id"):
                if account.id != creditors.id:
                    raise HTTPException(422, f"A vendor can only be tagged on {creditors.name}")
                from app.modules.vendor.models.vendor import Vendor
                vendor = self.db.query(Vendor).filter(Vendor.id == e["vendor_id"]).first()
                if not vendor or vendor.society_id != society_id:
                    raise HTTPException(422, "Vendor not found in this society")
            lines.append(Line(account, money(e.get("debit")), money(e.get("credit")),
                              e.get("flat_id"), e.get("vendor_id"), e.get("narration")))

        debits = [l for l in lines if l.debit]
        credits = [l for l in lines if l.credit]
        if vtype == "receipt" and not (all(l.account.is_cash_or_bank for l in debits)
                                       and not any(l.account.is_cash_or_bank for l in credits)):
            raise HTTPException(422, "A receipt debits cash or bank and credits the ledger money came from")
        if vtype == "payment" and not (all(l.account.is_cash_or_bank for l in credits)
                                       and not any(l.account.is_cash_or_bank for l in debits)):
            raise HTTPException(422, "A payment credits cash or bank and debits the ledger money went to")
        if vtype == "contra" and not all(l.account.is_cash_or_bank for l in lines):
            raise HTTPException(422, "A contra moves money between cash and bank ledgers only")
        if vtype == "journal" and any(l.account.is_cash_or_bank for l in lines):
            raise HTTPException(422, "A journal doesn't touch cash or bank — use a receipt, payment or contra")

        voucher = self.build_voucher(society_id, vtype, data["voucher_date"], lines,
                                     narration=data.get("narration"), reference=data.get("reference"),
                                     user=user)
        self._audit(AuditAction.CREATE, voucher, user, request,
                    new_values={"number": voucher.voucher_number, "amount": str(voucher.amount)})
        self.db.commit()
        self.db.refresh(voucher)
        return voucher

    @staticmethod
    def _voucher_loads():
        return (selectinload(Voucher.entries).joinedload(VoucherEntry.account),
                selectinload(Voucher.entries).joinedload(VoucherEntry.flat).joinedload(Flat.wing),
                selectinload(Voucher.entries).joinedload(VoucherEntry.vendor),
                joinedload(Voucher.creator))

    def get_voucher(self, voucher_id: UUID) -> Voucher:
        v = self.db.query(Voucher).options(*self._voucher_loads()).filter(Voucher.id == voucher_id).first()
        if not v:
            raise HTTPException(404, "Voucher not found")
        return v

    def cancel(self, voucher: Voucher, reason: str, user: Optional[User]) -> Voucher:
        voucher.is_cancelled = True
        voucher.cancelled_at = datetime.utcnow()
        voucher.cancelled_by = user.id if user else None
        voucher.cancel_reason = reason
        return voucher

    def reverse(self, voucher: Voucher, reason: str, user: Optional[User]) -> Voucher:
        """Undo a voucher of a closed year by posting its mirror image in
        the open year; the original stays in that year's books."""
        lines = [Line(e.account, debit=money(e.credit), credit=money(e.debit), flat_id=e.flat_id,
                      vendor_id=e.vendor_id, narration=e.narration) for e in voucher.entries]
        reversal = self.build_voucher(
            voucher.society_id, "journal", self.open_posting_date(voucher.society_id, date.today()), lines,
            narration=f"Reversal of {voucher.voucher_number} (FY {voucher.fiscal_year}, books closed): {reason}",
            reference=voucher.voucher_number, reversal_of_id=voucher.id, user=user)
        voucher.reversed_at = datetime.utcnow()
        return reversal

    def void(self, voucher: Voucher, reason: str, user: Optional[User]) -> None:
        """Cancel a voucher, or reverse it if its year's books are closed."""
        if self.is_closed(voucher.society_id, voucher.voucher_date):
            self.reverse(voucher, reason, user)
        else:
            self.cancel(voucher, reason, user)

    def cancel_manual_voucher(self, voucher_id: UUID, reason: str, user: User, request=None) -> Voucher:
        voucher = self.get_voucher(voucher_id)
        if voucher.is_cancelled:
            raise HTTPException(409, "Voucher is already cancelled")
        if voucher.source_type:
            raise HTTPException(409, "This voucher was posted from a bill or payment — cancel that instead")
        if voucher.voucher_type == "closing":
            raise HTTPException(409, "A year-end closing voucher is undone by reopening the year")
        if voucher.reversal_of_id:
            raise HTTPException(409, "A reversal entry can't be cancelled")
        self.assert_open(voucher.society_id, voucher.voucher_date)
        self.cancel(voucher, reason, user)
        self._audit(AuditAction.UPDATE, voucher, user, request,
                    new_values={"cancelled": True, "reason": reason, "number": voucher.voucher_number})
        self.db.commit()
        self.db.refresh(voucher)
        return voucher

    def list_vouchers(self, society_id: UUID, voucher_type: Optional[str] = None,
                      date_from: Optional[date] = None, date_to: Optional[date] = None,
                      include_cancelled: bool = True, skip: int = 0, limit: int = 100) -> List[Voucher]:
        q = self.db.query(Voucher).options(*self._voucher_loads()).filter(Voucher.society_id == society_id)
        if voucher_type:
            q = q.filter(Voucher.voucher_type == voucher_type)
        if date_from:
            q = q.filter(Voucher.voucher_date >= date_from)
        if date_to:
            q = q.filter(Voucher.voucher_date <= date_to)
        if not include_cancelled:
            q = q.filter(Voucher.is_cancelled == False)
        return (q.order_by(Voucher.voucher_date.desc(), Voucher.created_at.desc())
                .offset(skip).limit(limit).all())

    # ── Balances & statements ─────────────────────────────────────────────────

    def _movements(self, society_id: UUID, *, before: Optional[date] = None, upto: Optional[date] = None,
                   group_by=VoucherEntry.account_id, **filters):
        q = (self.db.query(group_by, func.coalesce(func.sum(VoucherEntry.debit), 0),
                           func.coalesce(func.sum(VoucherEntry.credit), 0))
             .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
             .filter(Voucher.society_id == society_id, Voucher.is_cancelled == False))
        if before:
            q = q.filter(Voucher.voucher_date < before)
        if upto:
            q = q.filter(Voucher.voucher_date <= upto)
        for column, value in filters.items():
            q = q.filter(getattr(VoucherEntry, column) == value)
        return {key: money(dr) - money(cr) for key, dr, cr in q.group_by(group_by).all()}

    def balances(self, society_id: UUID, as_of: Optional[date] = None) -> Dict[UUID, Decimal]:
        """{account_id: signed balance} including opening balances."""
        moves = self._movements(society_id, upto=as_of)
        return {a.id: signed_opening(a) + moves.get(a.id, ZERO) for a in self.list_accounts(society_id, True)}

    def chart(self, society_id: UUID, as_of: Optional[date] = None) -> List[dict]:
        balances = self.balances(society_id, as_of)
        accounts = self.list_accounts(society_id)
        out = []
        for g in self.list_groups(society_id):
            rows = [a for a in accounts if a.group_id == g.id]
            total = sum((balances.get(a.id, ZERO) for a in rows), ZERO)
            out.append({"group": g, "accounts": [(a, balances.get(a.id, ZERO)) for a in rows], "total": total})
        return out

    def ledger_statement(self, account_id: UUID, date_from: Optional[date] = None,
                         date_to: Optional[date] = None, flat_id: Optional[UUID] = None,
                         vendor_id: Optional[UUID] = None) -> dict:
        """Opening balance, each posting in the period with the ledgers on
        the other side of it and the running balance, and the closing
        balance. With `flat_id` (Members' Dues) or `vendor_id` (Sundry
        Creditors): that member's or vendor's own account."""
        account = self.get_account(account_id)
        filters = {"account_id": account.id}
        if flat_id:
            filters["flat_id"] = flat_id
        if vendor_id:
            filters["vendor_id"] = vendor_id
        opening = ZERO if (flat_id or vendor_id) else signed_opening(account)
        if date_from:
            opening += self._movements(account.society_id, before=date_from, group_by=VoucherEntry.account_id,
                                       **filters).get(account.id, ZERO)

        q = (self.db.query(VoucherEntry, Voucher)
             .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
             .options(selectinload(Voucher.entries).joinedload(VoucherEntry.account))
             .filter(Voucher.society_id == account.society_id, Voucher.is_cancelled == False))
        for column, value in filters.items():
            q = q.filter(getattr(VoucherEntry, column) == value)
        if date_from:
            q = q.filter(Voucher.voucher_date >= date_from)
        if date_to:
            q = q.filter(Voucher.voucher_date <= date_to)
        rows = q.order_by(Voucher.voucher_date, Voucher.created_at, VoucherEntry.line_no).all()

        running, lines = opening, []
        total_dr = total_cr = ZERO
        for entry, voucher in rows:
            running += money(entry.debit) - money(entry.credit)
            total_dr += money(entry.debit)
            total_cr += money(entry.credit)
            others = [e.account.name for e in voucher.entries if e.account_id != account.id]
            lines.append({
                "voucher_id": voucher.id, "voucher_number": voucher.voucher_number,
                "voucher_type": voucher.voucher_type, "date": voucher.voucher_date,
                "particulars": ", ".join(dict.fromkeys(others)) or account.name,
                "narration": entry.narration or voucher.narration,
                "debit": money(entry.debit), "credit": money(entry.credit), "balance": running,
            })
        return {"account": account, "opening": opening, "lines": lines,
                "total_debit": total_dr, "total_credit": total_cr, "closing": running}

    def member_balances(self, society_id: UUID, as_of: Optional[date] = None) -> List[dict]:
        """Each flat's balance on Members' Dues — Dr: the member owes the
        society, Cr: paid in advance."""
        dues = self.system_account(society_id, "members_dues")
        moves = self._movements(society_id, upto=as_of, group_by=VoucherEntry.flat_id, account_id=dues.id)
        flats = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
                 .filter(Wing.society_id == society_id, Flat.is_active == True)
                 .options(joinedload(Flat.wing), selectinload(Flat.residents)).all())
        rows = [{"flat": f, "balance": moves.get(f.id, ZERO)} for f in flats]
        rows.sort(key=lambda r: ((r["flat"].wing.name if r["flat"].wing else ""), r["flat"].flat_number))
        return rows

    def summary(self, society_id: UUID) -> dict:
        balances = self.balances(society_id)
        accounts = self.list_accounts(society_id)
        chart = self.ensure_chart(society_id)
        fy_from = fiscal_year_start(date.today())
        year = (self.db.query(Account.id, AccountGroup.nature,
                              func.coalesce(func.sum(VoucherEntry.debit), 0),
                              func.coalesce(func.sum(VoucherEntry.credit), 0))
                .join(VoucherEntry, VoucherEntry.account_id == Account.id)
                .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .join(AccountGroup, AccountGroup.id == Account.group_id)
                .filter(Voucher.society_id == society_id, Voucher.is_cancelled == False,
                        Voucher.voucher_date >= fy_from,
                        AccountGroup.nature.in_(("income", "expense")))
                .group_by(Account.id, AccountGroup.nature).all())
        income = sum((money(cr) - money(dr) for _, n, dr, cr in year if n == "income"), ZERO)
        expense = sum((money(dr) - money(cr) for _, n, dr, cr in year if n == "expense"), ZERO)
        return {
            "cash": sum((balances.get(a.id, ZERO) for a in accounts if a.is_cash), ZERO),
            "bank": sum((balances.get(a.id, ZERO) for a in accounts if a.is_bank), ZERO),
            "members_dues": balances.get(chart["members_dues"].id, ZERO),
            "creditors": -balances.get(chart["sundry_creditors"].id, ZERO),
            "fy": fiscal_year(date.today()), "fy_income": income, "fy_expense": expense,
            "cash_bank_accounts": [(a, balances.get(a.id, ZERO)) for a in accounts if a.is_cash_or_bank],
        }
