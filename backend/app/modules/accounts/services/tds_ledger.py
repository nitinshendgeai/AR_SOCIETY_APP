"""
The TDS ledger report: what the society owes the government and what it can claim back.

Read-only. It reads the two TDS ledgers the books already keep and adds nothing to them:

- **TDS Payable** (a liability): credited when TDS is held back from a vendor, debited when it is deposited with the
  government. A credit balance is what is still to be deposited; a debit balance means more was deposited than held.
- **TDS Receivable** (an asset): TDS others deducted from the society's income (bank interest, for instance) and
  booked by a voucher. A debit balance is what can be claimed in the income-tax return.

The two are shown side by side and are never netted against each other: the amount payable is deposited with a
challan, the amount receivable is claimed in a return.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.services.accounts_service import AccountsService, dr_cr, fiscal_year_start, money

ZERO = Decimal("0.00")


def quarter_of(d: date) -> tuple:
    """(financial year start year, quarter 1-4, label) — Q1 is April–June."""
    fy_start = fiscal_year_start(d).year
    q = ((d.month - 4) % 12) // 3 + 1
    months = {1: "Apr–Jun", 2: "Jul–Sep", 3: "Oct–Dec", 4: "Jan–Mar"}[q]
    return fy_start, q, f"Q{q} {months} {fy_start}-{str(fy_start + 1)[-2:]}"


def _quarters(lines: List[dict]) -> List[dict]:
    """The ledger's postings grouped by financial-year quarter: what was credited (held back) and debited (deposited)."""
    buckets: Dict[tuple, dict] = {}
    for l in lines:
        fy, q, label = quarter_of(l["date"])
        b = buckets.setdefault((fy, q), {"quarter": label, "credit": ZERO, "debit": ZERO})
        b["credit"] += money(l["credit"])
        b["debit"] += money(l["debit"])
    return [{"quarter": b["quarter"], "credit": str(b["credit"]), "debit": str(b["debit"]), "net": str(b["credit"] - b["debit"])}
            for _, b in sorted(buckets.items())]


class TdsLedgerService:
    def __init__(self, db: Session):
        self.db = db
        self.accounts = AccountsService(db)

    def report(self, society_id: UUID, date_from: Optional[date], date_to: Optional[date]) -> dict:
        """The raw statements of the two ledgers, and the amounts to pay and to receive at the end of the period."""
        payable = self.accounts.ledger_statement(self.accounts.system_account(society_id, "tds_payable").id,
                                                 date_from, date_to)
        receivable = self.accounts.ledger_statement(self.accounts.system_account(society_id, "tds_receivable").id,
                                                    date_from, date_to)
        # Payable is a credit-balance ledger: a negative (credit) closing is money owed. Receivable is a
        # debit-balance ledger: a positive (debit) closing is money to claim.
        owed = -money(payable["closing"])
        claim = money(receivable["closing"])
        return {
            "payable": payable,
            "receivable": receivable,
            "to_pay": str(max(owed, ZERO)),
            "excess_deposited": str(max(-owed, ZERO)),
            "to_receive": str(max(claim, ZERO)),
            "receivable_over_adjusted": str(max(-claim, ZERO)),
            "payable_quarters": _quarters(payable["lines"]),
            "receivable_quarters": _quarters(receivable["lines"]),
        }


def summary_out(rep: dict, date_from: Optional[date], date_to: Optional[date]) -> dict:
    """The JSON the app and the printout read: the headline amounts, the quarter tables and both statements."""
    def statement(st: dict) -> dict:
        return {
            "account": {"id": str(st["account"].id), "name": st["account"].name, "code": st["account"].code},
            "opening": dr_cr(st["opening"]), "closing": dr_cr(st["closing"]),
            "total_debit": str(money(st["total_debit"])), "total_credit": str(money(st["total_credit"])),
            "lines": [{
                "date": l["date"].isoformat(), "voucher_number": l["voucher_number"],
                "voucher_id": str(l["voucher_id"]) if l.get("voucher_id") else None,
                "particulars": l["particulars"], "narration": l.get("narration"),
                "debit": str(money(l["debit"])), "credit": str(money(l["credit"])),
                "balance": dr_cr(l["balance"]),
            } for l in st["lines"]],
        }

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "to_pay": rep["to_pay"], "excess_deposited": rep["excess_deposited"],
        "to_receive": rep["to_receive"], "receivable_over_adjusted": rep["receivable_over_adjusted"],
        "payable_quarters": rep["payable_quarters"], "receivable_quarters": rep["receivable_quarters"],
        "payable": statement(rep["payable"]), "receivable": statement(rep["receivable"]),
    }
