"""
Setting off members' payments against their maintenance bills.

A payment recorded for a flat (OnlinePaymentSubmission) settles the flat's
open bills — issued and not fully paid — oldest first (by due date, then
bill date), the way a society appropriates a member's payment towards the
oldest dues. Each set-off is a PaymentAllocation and is applied to the bill
and the flat's DueTracker exactly like a payment against that bill.

Whatever is left over is the member's advance (credit): it is set off
automatically against the next bill issued to the flat.

- A payment recorded against a chosen bill is allocated to that bill only.
- A rejected payment (reconciliation) releases its allocations: the bills
  are unpaid again by those amounts. If it is un-rejected later, it is set
  off again.
- A cancelled bill releases its allocations; the money goes back to the
  member's credit and is set off against the flat's other open bills.

Rejected and deactivated payments have no credit. Released allocations stay
on record with the reason.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.billing.models.billing import (
    BillStatus, DueTracker, MaintenanceBill, OnlinePaymentSubmission, PaymentAllocation, ReconciliationStatus,
)

ZERO = Decimal("0.00")
OPEN_STATUSES = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE)


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def payment_counts(sub: OnlinePaymentSubmission) -> bool:
    """A payment that stands: not rejected, not deactivated."""
    return sub.is_active and sub.status != ReconciliationStatus.REJECTED


def allocated(sub: OnlinePaymentSubmission) -> Decimal:
    return sum((_money(a.amount) for a in sub.allocations if a.is_live), ZERO)


def unapplied(sub: OnlinePaymentSubmission) -> Decimal:
    """What is left of a payment after its set-offs — the member's advance."""
    return max(_money(sub.amount) - allocated(sub), ZERO) if payment_counts(sub) else ZERO


class PaymentAllocator:

    def __init__(self, db: Session, billing=None):
        self.db = db
        if billing is None:
            from app.modules.billing.services.billing_service import BillingService
            billing = BillingService(db)
        self.billing = billing

    # ── Reading ───────────────────────────────────────────────────────────────

    def open_bills(self, flat_id: UUID) -> List[MaintenanceBill]:
        """The flat's bills still to be paid, oldest first."""
        return (self.db.query(MaintenanceBill)
                .filter(MaintenanceBill.flat_id == flat_id, MaintenanceBill.bill_status.in_(OPEN_STATUSES),
                        MaintenanceBill.outstanding > 0)
                .order_by(MaintenanceBill.due_date, MaintenanceBill.bill_date, MaintenanceBill.created_at)
                .all())

    def credits(self, flat_id: UUID) -> List[OnlinePaymentSubmission]:
        """The flat's payments with money not yet set off, oldest first."""
        subs = (self.db.query(OnlinePaymentSubmission)
                .filter(OnlinePaymentSubmission.flat_id == flat_id,
                        OnlinePaymentSubmission.is_active == True,  # noqa: E712
                        OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED)
                .order_by(OnlinePaymentSubmission.payment_date, OnlinePaymentSubmission.created_at)
                .all())
        return [s for s in subs if unapplied(s) > 0]

    def advance(self, flat_id: UUID) -> Decimal:
        return sum((unapplied(s) for s in self.credits(flat_id)), ZERO)

    def society_unapplied(self, society_id: UUID) -> Dict[UUID, Decimal]:
        """{flat_id: advance} for every flat with money not yet set off."""
        subs = (self.db.query(OnlinePaymentSubmission)
                .filter(OnlinePaymentSubmission.society_id == society_id,
                        OnlinePaymentSubmission.is_active == True,  # noqa: E712
                        OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED)
                .all())
        out: Dict[UUID, Decimal] = defaultdict(lambda: ZERO)
        for s in subs:
            left = unapplied(s)
            if left > 0:
                out[s.flat_id] += left
        return dict(out)

    # ── Setting off ───────────────────────────────────────────────────────────

    def allocate(self, sub: OnlinePaymentSubmission, bill: MaintenanceBill, amount: Decimal,
                 user: Optional[User]) -> PaymentAllocation:
        """Set `amount` of `sub` off against `bill` (validated by the caller)."""
        alloc = PaymentAllocation(society_id=sub.society_id, flat_id=sub.flat_id, payment_id=sub.id,
                                  bill_id=bill.id, amount=amount, allocated_by=user.id if user else None)
        sub.allocations.append(alloc)
        self.db.add(alloc)
        self.billing._apply_payment_to_bill(bill, amount, sub.payment_date, user)
        return alloc

    def apply_credit(self, flat_id: UUID, user: Optional[User]) -> List[PaymentAllocation]:
        """Set the flat's unapplied payments off against its open bills,
        oldest payment against oldest bill. Flushed, not committed."""
        made: List[PaymentAllocation] = []
        bills = self.open_bills(flat_id)
        if bills:
            for sub in self.credits(flat_id):
                left = unapplied(sub)
                for bill in bills:
                    if left <= 0:
                        break
                    due = _money(bill.outstanding)
                    if due <= 0:
                        continue
                    take = min(left, due)
                    alloc = self.allocate(sub, bill, take, user)
                    made.append(alloc)
                    # If the receipt was already posted as an advance, record
                    # the appropriation from ADVANCE into member AR.
                    from app.modules.accounts.services.postings import AccountPostings
                    postings = AccountPostings(self.db)
                    if postings.active_voucher("online_payment", sub.id):
                        postings.post_advance_allocation(alloc, user)
                    left -= take
                bills = [b for b in bills if _money(b.outstanding) > 0]
                if not bills:
                    break
        self._sync_advance(flat_id, user)
        self.db.flush()
        return made

    def apply_society(self, society_id: UUID, user: Optional[User]) -> dict:
        """Set off every flat's unapplied payments; returns what was done."""
        flats = list(self.society_unapplied(society_id))
        made = []
        for flat_id in flats:
            made += self.apply_credit(flat_id, user)
        return {"flats": len({a.flat_id for a in made}), "bills": len({a.bill_id for a in made}),
                "amount": str(sum((_money(a.amount) for a in made), ZERO))}

    # ── Releasing ─────────────────────────────────────────────────────────────

    def _release(self, allocations: Iterable[PaymentAllocation], reason: str, user: Optional[User]) -> List[UUID]:
        flats = []
        for a in allocations:
            if not a.is_live:
                continue
            a.released_at = datetime.utcnow()
            a.released_reason = reason
            bill, amount = a.bill, _money(a.amount)
            from app.modules.accounts.services.postings import AccountPostings
            AccountPostings(self.db)._cancel_source(
                "advance_allocation", a.id,
                f"Released allocation for {bill.invoice_number}: {reason}", user)
            bill.paid_amount = _money(bill.paid_amount) - amount
            bill.outstanding = _money(bill.total_amount) + _money(bill.penalty_amount) - _money(bill.paid_amount)
            if bill.bill_status in (BillStatus.PAID, BillStatus.PARTIALLY_PAID):
                bill.bill_status = BillStatus.PARTIALLY_PAID if _money(bill.paid_amount) > 0 else BillStatus.ISSUED
                bill.paid_at = None
            tracker = self.billing.due_repo.get_or_create(bill.flat_id, bill.society_id)
            tracker.total_paid -= amount
            tracker.outstanding += amount
            if user:
                tracker.last_updated_by = user.id
            flats.append(bill.flat_id)
        self.db.flush()
        return flats

    def release_payment(self, sub: OnlinePaymentSubmission, reason: str, user: Optional[User]) -> None:
        """A rejected payment: its bills are unpaid again by what it settled."""
        self._release(list(sub.allocations), reason, user)
        self._sync_advance(sub.flat_id, user)

    def release_bill(self, bill: MaintenanceBill, reason: str, user: Optional[User]) -> None:
        """A cancelled bill: what was set off against it goes back to the
        member's credit."""
        self._release(list(bill.allocations), reason, user)

    def _sync_advance(self, flat_id: UUID, user: Optional[User]) -> None:
        tracker = self.db.query(DueTracker).filter(DueTracker.flat_id == flat_id).first()
        if tracker is None:
            return
        self.db.flush()
        tracker.advance_balance = self.advance(flat_id)
