"""Member AR subledger ledger and billing reconciliation.

The accounting AR balance is derived from live VoucherEntry rows linked to a
member EntityAccount(subledger_type='AR'). Operational outstanding is derived
from maintenance bills plus their dated collections. The two sources remain
separate so reconciliation differences are visible rather than hidden.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.modules.accounts.models.accounts import Voucher, VoucherEntry
from app.modules.accounts.models.entities import Entity, EntityAccount
from app.modules.billing.models.billing import (
    BillStatus,
    MaintenanceBill,
    OnlinePaymentSubmission,
    PaymentAllocation,
    PaymentReceipt,
    ReconciliationStatus,
)

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
            .filter(VoucherEntry.entity_account_id == entity_account_id, LIVE)
        )
        if date_from:
            q = q.filter(Voucher.voucher_date >= date_from)
        if date_to:
            q = q.filter(Voucher.voucher_date <= date_to)
        return q.order_by(Voucher.voucher_date, Voucher.created_at, VoucherEntry.line_no).all()

    def _opening(self, entity_account_id: UUID, date_from: Optional[date]) -> Decimal:
        if not date_from:
            return ZERO
        row = (
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
        return _signed_entry(row[0], row[1])

    def _operational_bulk(self, society_id: UUID, flat_ids, as_of: Optional[date] = None):
        """Return {flat_id: (demand, collected, outstanding)}.

        With no as_of, use the current billing snapshot. With an as_of date,
        reconstruct the billing position from bills and dated receipts/
        allocations so a historical report is not compared with today's
        mutable bill.paid_amount/outstanding fields.
        """
        if not flat_ids:
            return {}

        bill_q = self.db.query(MaintenanceBill).filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.flat_id.in_(flat_ids),
            MaintenanceBill.bill_status != BillStatus.CANCELLED,
        )
        if as_of:
            bill_q = bill_q.filter(MaintenanceBill.bill_date <= as_of)
            # A bill cancelled after the requested date existed at that date.
            bill_q = bill_q.filter(
                (MaintenanceBill.cancelled_at.is_(None))
                | (func.date(MaintenanceBill.cancelled_at) > as_of)
            )
        bills = bill_q.all()

        if not as_of:
            out: Dict[UUID, list] = {}
            for bill in bills:
                row = out.setdefault(bill.flat_id, [ZERO, ZERO, ZERO])
                row[0] += _money(bill.total_amount)
                row[1] += _money(bill.paid_amount)
                row[2] += _money(bill.outstanding)
            return {k: tuple(_money(v) for v in vals) for k, vals in out.items()}

        bill_ids = [b.id for b in bills]
        if not bill_ids:
            return {}

        demand_by_bill = {
            b.id: _money(b.total_amount) + _money(b.penalty_amount)
            for b in bills
        }
        collected_by_bill: Dict[UUID, Decimal] = {}

        receipt_rows = (
            self.db.query(
                PaymentReceipt.bill_id,
                func.coalesce(func.sum(PaymentReceipt.amount), 0),
            )
            .filter(
                PaymentReceipt.society_id == society_id,
                PaymentReceipt.bill_id.in_(bill_ids),
                PaymentReceipt.payment_date <= as_of,
                PaymentReceipt.is_reversed == False,  # noqa: E712
            )
            .group_by(PaymentReceipt.bill_id)
            .all()
        )
        for bill_id, amount in receipt_rows:
            collected_by_bill[bill_id] = _money(amount)

        allocation_rows = (
            self.db.query(
                PaymentAllocation.bill_id,
                func.coalesce(func.sum(PaymentAllocation.amount), 0),
            )
            .join(
                OnlinePaymentSubmission,
                OnlinePaymentSubmission.id == PaymentAllocation.payment_id,
            )
            .filter(
                PaymentAllocation.society_id == society_id,
                PaymentAllocation.bill_id.in_(bill_ids),
                OnlinePaymentSubmission.payment_date <= as_of,
                OnlinePaymentSubmission.is_active == True,  # noqa: E712
                OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED,
                func.date(PaymentAllocation.created_at) <= as_of,
                (
                    PaymentAllocation.released_at.is_(None)
                    | (func.date(PaymentAllocation.released_at) > as_of)
                ),
            )
            .group_by(PaymentAllocation.bill_id)
            .all()
        )
        for bill_id, amount in allocation_rows:
            collected_by_bill[bill_id] = (
                collected_by_bill.get(bill_id, ZERO) + _money(amount)
            )

        out: Dict[UUID, list] = {}
        for bill in bills:
            demand = demand_by_bill[bill.id]
            collected = min(collected_by_bill.get(bill.id, ZERO), demand)
            outstanding = max(demand - collected, ZERO)
            row = out.setdefault(bill.flat_id, [ZERO, ZERO, ZERO])
            row[0] += demand
            row[1] += collected
            row[2] += outstanding

        return {k: tuple(_money(v) for v in vals) for k, vals in out.items()}

    def _operational(self, society_id: UUID, flat_id: UUID,
                     date_from: Optional[date], date_to: Optional[date]):
        # A date_from-only statement still reports the current closing
        # position; date_to gives an explicit historical as-of snapshot.
        return self._operational_bulk(
            society_id, [flat_id], as_of=date_to
        ).get(flat_id, (ZERO, ZERO, ZERO))

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

        demand, paid, outstanding = self._operational(
            society_id, flat.id, date_from, date_to
        )
        advance = self._advance_balance(entity.id, society_id, date_to)

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
        }

    def _advance_balance(self, entity_id: UUID, society_id: UUID,
                         as_of: Optional[date] = None) -> Decimal:
        ea = self.db.query(EntityAccount).filter(
            EntityAccount.entity_id == entity_id,
            EntityAccount.society_id == society_id,
            EntityAccount.subledger_type == "ADVANCE",
            EntityAccount.is_active.is_(True),
        ).first()
        if not ea:
            return ZERO
        q = (
            self.db.query(
                func.coalesce(func.sum(VoucherEntry.debit), 0),
                func.coalesce(func.sum(VoucherEntry.credit), 0),
            )
            .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(VoucherEntry.entity_account_id == ea.id, LIVE)
        )
        if as_of:
            q = q.filter(Voucher.voucher_date <= as_of)
        row = q.one()
        # Advance is a credit-balance liability subledger: receipts credit it,
        # later allocations debit it.
        return _money(row[1] - row[0])

    def society_reconciliation(self, society_id: UUID,
                               date_from: Optional[date] = None,
                               date_to: Optional[date] = None) -> dict:
        """Reconcile all member AR accounts using bulk aggregates."""
        accounts = self._accounts(society_id)
        ar_ids = [ar.id for _, ar, _ in accounts]
        entity_ids = [entity.id for entity, _, _ in accounts]
        flat_ids = [flat.id for _, _, flat in accounts if flat]

        gl_rows = []
        if ar_ids:
            q = (
                self.db.query(
                    VoucherEntry.entity_account_id,
                    func.coalesce(func.sum(VoucherEntry.debit), 0),
                    func.coalesce(func.sum(VoucherEntry.credit), 0),
                )
                .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .filter(VoucherEntry.entity_account_id.in_(ar_ids), LIVE)
            )
            if date_from:
                q = q.filter(Voucher.voucher_date >= date_from)
            if date_to:
                q = q.filter(Voucher.voucher_date <= date_to)
            gl_rows = q.group_by(VoucherEntry.entity_account_id).all()
        gl = {row[0]: (_money(row[1]), _money(row[2])) for row in gl_rows}

        # The AR closing balance must include the opening balance before
        # date_from. Bulk reports therefore aggregate through date_to, not only
        # the selected period, when an as-of snapshot is requested.
        if date_from:
            opening_rows = (
                self.db.query(
                    VoucherEntry.entity_account_id,
                    func.coalesce(func.sum(VoucherEntry.debit), 0),
                    func.coalesce(func.sum(VoucherEntry.credit), 0),
                )
                .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .filter(
                    VoucherEntry.entity_account_id.in_(ar_ids),
                    LIVE,
                    Voucher.voucher_date < date_from,
                )
                .group_by(VoucherEntry.entity_account_id)
                .all()
            )
            for entity_account_id, debit, credit in opening_rows:
                prior = gl.get(entity_account_id, (ZERO, ZERO))
                gl[entity_account_id] = (
                    _money(prior[0] + debit),
                    _money(prior[1] + credit),
                )

        advance_rows = []
        if entity_ids:
            q = (
                self.db.query(
                    EntityAccount.entity_id,
                    func.coalesce(func.sum(VoucherEntry.debit), 0),
                    func.coalesce(func.sum(VoucherEntry.credit), 0),
                )
                .join(VoucherEntry, VoucherEntry.entity_account_id == EntityAccount.id)
                .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .filter(
                    EntityAccount.society_id == society_id,
                    EntityAccount.entity_id.in_(entity_ids),
                    EntityAccount.subledger_type == "ADVANCE",
                    EntityAccount.is_active.is_(True),
                    LIVE,
                )
            )
            if date_to:
                q = q.filter(Voucher.voucher_date <= date_to)
            advance_rows = q.group_by(EntityAccount.entity_id).all()
        advances = {row[0]: _money(row[2] - row[1]) for row in advance_rows}

        operational = self._operational_bulk(society_id, flat_ids, as_of=date_to)

        members = []
        totals = {
            "gl_closing_ar": ZERO,
            "operational_demand": ZERO,
            "operational_collected": ZERO,
            "operational_outstanding": ZERO,
            "advance_balance": ZERO,
        }
        for entity, ar, flat in accounts:
            if not flat:
                continue
            debit, credit = gl.get(ar.id, (ZERO, ZERO))
            closing = _money(debit - credit)
            demand, collected, outstanding = operational.get(flat.id, (ZERO, ZERO, ZERO))
            advance = advances.get(entity.id, ZERO)
            difference = _money(closing - outstanding)
            members.append({
                "flat_id": str(flat.id),
                "flat_label": _flat_label(flat),
                "member_entity_id": str(entity.id),
                "member_account_number": ar.account_number,
                "closing_ar": str(closing),
                "closing_ar_dr_cr": "Dr" if closing >= 0 else "Cr",
                "operational_demand": str(demand),
                "operational_collected": str(collected),
                "operational_outstanding": str(outstanding),
                "reconciliation_difference": str(difference),
                "reconciled": abs(difference) < Decimal("0.01"),
                "advance_balance": str(_money(advance)),
            })
            totals["gl_closing_ar"] += closing
            totals["operational_demand"] += demand
            totals["operational_collected"] += collected
            totals["operational_outstanding"] += outstanding
            totals["advance_balance"] += advance

        difference = _money(totals["gl_closing_ar"] - totals["operational_outstanding"])
        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "members": members,
            "totals": {
                **{k: str(_money(v)) for k, v in totals.items()},
                "reconciliation_difference": str(difference),
                "reconciled": abs(difference) < Decimal("0.01"),
            },
        }
