"""Member AR subledger ledger and billing reconciliation.

The accounting AR balance is derived from live VoucherEntry rows linked to a
member EntityAccount(subledger_type='AR').  Operational outstanding is derived
from issued maintenance bills.  The two are deliberately reported separately
and reconciled rather than silently making one source overwrite the other.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.wing import Wing
from app.modules.accounts.models.accounts import Account, Voucher, VoucherEntry
from app.modules.accounts.models.entities import Entity, EntityAccount
from app.modules.billing.models.billing import BillStatus, MaintenanceBill

ZERO = Decimal("0.00")
LIVE = (Voucher.is_cancelled == False) & Voucher.reversed_at.is_(None)  # noqa: E712


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def _signed_entry(debit, credit) -> Decimal:
    return _money(debit) - _money(credit)


def _flat_label(flat: Optional[Flat]) -> Optional[str]:
    if not flat:
        return None
    wing = getattr(flat, "wing", None)
    wing_name = getattr(wing, "name", None) if wing else None
    number = getattr(flat, "flat_number", None) or getattr(flat, "flat_no", None) or str(flat.id)
    return f"{wing_name}-{number}" if wing_name else str(number)


class MemberARService:
    """Read-only AR statement and reconciliation service."""

    def __init__(self, db: Session):
        self.db = db

    def _accounts(self, society_id: UUID, flat_id: Optional[UUID] = None):
        q = (
            self.db.query(Entity, EntityAccount, Flat)
            .join(EntityAccount, EntityAccount.entity_id == Entity.id)
            .outerjoin(Flat, Flat.id == Entity.source_id)
            .filter(
                Entity.society_id == society_id,
                Entity.entity_type == "member",
                EntityAccount.society_id == society_id,
                EntityAccount.subledger_type == "AR",
                EntityAccount.is_active.is_(True),
            )
        )
        if flat_id:
            q = q.filter(Entity.source_type == "flat", Entity.source_id == flat_id)
        return q.order_by(Entity.display_name).all()

    def _entity_ledger(self, entity_account_id: UUID, date_from: Optional[date],
                       date_to: Optional[date]):
        q = (
            self.db.query(Voucher, VoucherEntry)
            .join(VoucherEntry, VoucherEntry.voucher_id == Voucher.id)
            .filter(
                VoucherEntry.entity_account_id == entity_account_id,
                LIVE,
            )
        )
        if date_from:
            q = q.filter(Voucher.voucher_date >= date_from)
        if date_to:
            q = q.filter(Voucher.voucher_date <= date_to)
        return q.order_by(Voucher.voucher_date, Voucher.created_at, VoucherEntry.line_no).all()

    def _opening(self, entity_account_id: UUID, date_from: Optional[date]) -> Decimal:
        if not date_from:
            return ZERO
        rows = (
            self.db.query(
                func.coalesce(func.sum(VoucherEntry.debit), 0),
                func.coalesce(func.sum(VoucherEntry.credit), 0),
            )
            .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(
                VoucherEntry.entity_account_id == entity_account_id,
                LIVE,
                Voucher.voucher_date < date_from,
            )
            .one()
        )
        return _signed_entry(rows[0], rows[1])

    def _operational(self, society_id: UUID, flat_id: UUID,
                     date_from: Optional[date], date_to: Optional[date]):
        q = self.db.query(MaintenanceBill).filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.flat_id == flat_id,
            MaintenanceBill.bill_status != BillStatus.CANCELLED,
        )
        if date_from:
            q = q.filter(MaintenanceBill.bill_date >= date_from)
        if date_to:
            q = q.filter(MaintenanceBill.bill_date <= date_to)
        bills = q.order_by(MaintenanceBill.bill_date, MaintenanceBill.created_at).all()

        demand = sum((_money(b.total_amount) for b in bills), ZERO)
        outstanding = sum((_money(b.outstanding) for b in bills), ZERO)
        paid = sum((_money(b.paid_amount) for b in bills), ZERO)
        return bills, demand, paid, outstanding

    def statement(self, society_id: UUID, flat_id: UUID,
                  date_from: Optional[date] = None,
                  date_to: Optional[date] = None) -> dict:
        rows = self._accounts(society_id, flat_id)
        if not rows:
            raise ValueError("Member AR subledger not found for this flat")

        entity, ar, flat = rows[0]
        entries = self._entity_ledger(ar.id, date_from, date_to)
        opening = self._opening(ar.id, date_from)
        balance = opening
        lines = []
        total_debit = ZERO
        total_credit = ZERO

        for voucher, entry in entries:
            debit = _money(entry.debit)
            credit = _money(entry.credit)
            total_debit += debit
            total_credit += credit
            balance += debit - credit
            lines.append({
                "voucher_id": str(voucher.id),
                "voucher_number": voucher.voucher_number,
                "date": voucher.voucher_date.isoformat(),
                "voucher_type": voucher.voucher_type,
                "source_type": voucher.source_type,
                "source_id": str(voucher.source_id) if voucher.source_id else None,
                "narration": entry.narration or voucher.narration,
                "debit": str(debit),
                "credit": str(credit),
                "balance": str(_money(balance)),
                "balance_dr_cr": "Dr" if balance >= 0 else "Cr",
            })

        bills, demand, paid, outstanding = self._operational(
            society_id, flat.id, date_from, date_to
        )
        advance = self._advance_balance(entity.id, society_id)

        return {
            "flat_id": str(flat.id),
            "flat_label": _flat_label(flat),
            "member_entity_id": str(entity.id),
            "member_account_number": ar.account_number,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "opening_ar": str(_money(opening)),
            "total_debit": str(_money(total_debit)),
            "total_credit": str(_money(total_credit)),
            "closing_ar": str(_money(balance)),
            "closing_ar_dr_cr": "Dr" if balance >= 0 else "Cr",
            "operational_demand": str(_money(demand)),
            "operational_collected": str(_money(paid)),
            "operational_outstanding": str(_money(outstanding)),
            "reconciliation_difference": str(_money(balance - outstanding)),
            "reconciled": abs(_money(balance - outstanding)) < Decimal("0.01"),
            "advance_balance": str(_money(advance)),
            "lines": lines,
            "bill_count": len(bills),
            "bills": [{
                "bill_id": str(b.id),
                "invoice_number": b.invoice_number,
                "bill_date": b.bill_date.isoformat(),
                "due_date": b.due_date.isoformat(),
                "status": b.bill_status.value if hasattr(b.bill_status, "value") else str(b.bill_status),
                "demand": str(_money(b.total_amount)),
                "collected": str(_money(b.paid_amount)),
                "outstanding": str(_money(b.outstanding)),
            } for b in bills],
        }

    def _advance_balance(self, entity_id: UUID, society_id: UUID) -> Decimal:
        ea = self.db.query(EntityAccount).filter(
            EntityAccount.entity_id == entity_id,
            EntityAccount.society_id == society_id,
            EntityAccount.subledger_type == "ADVANCE",
            EntityAccount.is_active.is_(True),
        ).first()
        if not ea:
            return ZERO
        row = (
            self.db.query(
                func.coalesce(func.sum(VoucherEntry.debit), 0),
                func.coalesce(func.sum(VoucherEntry.credit), 0),
            )
            .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(VoucherEntry.entity_account_id == ea.id, LIVE)
            .one()
        )
        # Advance is a credit-balance liability subledger: receipts credit it,
        # later allocations debit it.
        return _money(row[1] - row[0])

    def society_reconciliation(self, society_id: UUID,
                               date_from: Optional[date] = None,
                               date_to: Optional[date] = None) -> dict:
        members = []
        totals = {
            "gl_closing_ar": ZERO,
            "operational_demand": ZERO,
            "operational_collected": ZERO,
            "operational_outstanding": ZERO,
            "advance_balance": ZERO,
        }
        for entity, ar, flat in self._accounts(society_id):
            if not flat:
                continue
            statement = self.statement(society_id, flat.id, date_from, date_to)
            members.append({
                "flat_id": statement["flat_id"],
                "flat_label": statement["flat_label"],
                "member_entity_id": statement["member_entity_id"],
                "member_account_number": statement["member_account_number"],
                "closing_ar": statement["closing_ar"],
                "closing_ar_dr_cr": statement["closing_ar_dr_cr"],
                "operational_demand": statement["operational_demand"],
                "operational_collected": statement["operational_collected"],
                "operational_outstanding": statement["operational_outstanding"],
                "reconciliation_difference": statement["reconciliation_difference"],
                "reconciled": statement["reconciled"],
                "advance_balance": statement["advance_balance"],
            })
            for key, target in totals.items():
                target += _money(statement[key])
            # keep assignment explicit because Decimal is immutable
            totals["gl_closing_ar"] = _money(totals["gl_closing_ar"])
            totals["operational_demand"] = _money(totals["operational_demand"])
            totals["operational_collected"] = _money(totals["operational_collected"])
            totals["operational_outstanding"] = _money(totals["operational_outstanding"])
            totals["advance_balance"] = _money(totals["advance_balance"])

        difference = _money(totals["gl_closing_ar"] - totals["operational_outstanding"])
        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "members": members,
            "totals": {
                **{k: str(v) for k, v in totals.items()},
                "reconciliation_difference": str(difference),
                "reconciled": abs(difference) < Decimal("0.01"),
            },
        }
