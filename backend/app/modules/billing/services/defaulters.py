"""
Members' dues and the list of defaulters.

For every flat: what is outstanding on its issued maintenance bills, less
any amount the member paid "on account" (applied to the oldest bills
first), aged by how long each bill has been past its due date — not yet
due, up to 3 months, 3–6 months, 6–12 months, over a year.

A member is a defaulter when some part of the dues has been outstanding
for longer than the society's limit after the due date — three months,
as the model bye-laws treat a member who doesn't pay within three months,
unless the society picks another limit. The list is what the committee
reviews, puts up for the general body and sends reminders from; the
statutory recovery steps are the committee's to take.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.flat import Flat
from app.models.notification import Notification, NotificationType
from app.models.resident import Resident
from app.models.user import User
from app.models.wing import Wing
from app.modules.billing.models.billing import (
    BillStatus, MaintenanceBill, OnlinePaymentSubmission, PaymentReceipt, ReconciliationStatus,
)
from app.modules.billing.services.bill_pdf import _bill_month, flat_label, member

ZERO = Decimal("0.00")
UNPAID_STATUSES = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE)
REMINDER_MODULE = "billing_dues"

# key, label, upper bound in months past the due date (None: no bound)
AGE_BUCKETS = [
    ("not_due", "Not yet due", 0),
    ("upto_3", "Up to 3 months", 3),
    ("m3_6", "3–6 months", 6),
    ("m6_12", "6–12 months", 12),
    ("over_12", "Over 1 year", None),
]


def months_before(d: date, months: int) -> date:
    """The same day `months` calendar months earlier (clamped to month end)."""
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    m += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, 28)


def _bucket(due: date, as_of: date) -> str:
    if due >= as_of:
        return "not_due"
    for key, _, months in AGE_BUCKETS[1:]:
        if months is None or due >= months_before(as_of, months):
            return key
    return "over_12"


@dataclass
class UnpaidBill:
    bill: MaintenanceBill
    outstanding: Decimal
    days_overdue: int
    bucket: str


@dataclass
class FlatDues:
    flat: Flat
    bills: List[UnpaidBill] = field(default_factory=list)
    on_account: Decimal = ZERO
    last_payment_date: Optional[date] = None
    last_payment_amount: Optional[Decimal] = None
    last_reminded_at: Optional[datetime] = None

    @property
    def total(self) -> Decimal:
        return sum((b.outstanding for b in self.bills), ZERO)

    def by_bucket(self) -> Dict[str, Decimal]:
        out = {k: ZERO for k, _, _ in AGE_BUCKETS}
        for b in self.bills:
            out[b.bucket] += b.outstanding
        return out

    def overdue_beyond(self, cutoff: date) -> Decimal:
        """Dues whose due date is before `cutoff`."""
        return sum((b.outstanding for b in self.bills if b.bill.due_date < cutoff), ZERO)

    @property
    def oldest(self) -> Optional[UnpaidBill]:
        return self.bills[0] if self.bills else None


class MemberDues:

    def __init__(self, db: Session):
        self.db = db

    def flats(self, society_id: UUID, as_of: Optional[date] = None,
              flat_ids: Optional[Iterable[UUID]] = None) -> List[FlatDues]:
        """Every flat with dues outstanding, oldest dues first within a flat."""
        as_of = as_of or date.today()
        q = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
             .filter(Wing.society_id == society_id, Flat.is_active == True)  # noqa: E712
             .options(joinedload(Flat.wing), selectinload(Flat.residents)))
        if flat_ids is not None:
            q = q.filter(Flat.id.in_(list(flat_ids)))
        flats = {f.id: FlatDues(f) for f in q.all()}
        if not flats:
            return []

        bills = (self.db.query(MaintenanceBill)
                 .options(joinedload(MaintenanceBill.cycle))
                 .filter(MaintenanceBill.society_id == society_id, MaintenanceBill.is_active == True,  # noqa: E712
                         MaintenanceBill.bill_status.in_(UNPAID_STATUSES), MaintenanceBill.outstanding > 0,
                         MaintenanceBill.flat_id.in_(list(flats)))
                 .order_by(MaintenanceBill.due_date, MaintenanceBill.bill_date, MaintenanceBill.created_at)
                 .all())
        # Money paid but not yet set off against a bill (an advance, or a
        # payment recorded before set-off) goes against the oldest dues.
        from app.modules.billing.services.allocations import PaymentAllocator
        for flat_id, amount in PaymentAllocator(self.db).society_unapplied(society_id).items():
            if flat_id in flats:
                flats[flat_id].on_account = Decimal(amount)

        credit = {fid: fd.on_account for fid, fd in flats.items()}
        for b in bills:
            remaining = Decimal(b.outstanding)
            used = min(credit.get(b.flat_id, ZERO), remaining)
            credit[b.flat_id] = credit.get(b.flat_id, ZERO) - used
            remaining -= used
            if remaining > 0:
                flats[b.flat_id].bills.append(UnpaidBill(
                    b, remaining, max(0, (as_of - b.due_date).days), _bucket(b.due_date, as_of)))

        self._last_payments(society_id, flats)
        self._last_reminders(flats)
        return [fd for fd in flats.values() if fd.bills]

    def _last_payments(self, society_id: UUID, flats: Dict[UUID, FlatDues]) -> None:
        payments = (
            [(p.flat_id, p.payment_date, p.amount) for p in self.db.query(PaymentReceipt).filter(
                PaymentReceipt.society_id == society_id, PaymentReceipt.is_reversed == False,  # noqa: E712
                PaymentReceipt.flat_id.in_(list(flats)))]
            + [(p.flat_id, p.payment_date, p.amount) for p in self.db.query(OnlinePaymentSubmission).filter(
                OnlinePaymentSubmission.society_id == society_id, OnlinePaymentSubmission.is_active == True,  # noqa: E712
                OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED,
                OnlinePaymentSubmission.flat_id.in_(list(flats)))]
        )
        for flat_id, paid_on, amount in payments:
            fd = flats.get(flat_id)
            if fd and (fd.last_payment_date is None or paid_on > fd.last_payment_date):
                fd.last_payment_date, fd.last_payment_amount = paid_on, Decimal(amount)

    def _last_reminders(self, flats: Dict[UUID, FlatDues]) -> None:
        rows = (self.db.query(Notification.entity_id, func.max(Notification.created_at))
                .filter(Notification.module == REMINDER_MODULE,
                        Notification.entity_id.in_([str(fid) for fid in flats]))
                .group_by(Notification.entity_id).all())
        for entity_id, at in rows:
            fd = flats.get(UUID(entity_id))
            if fd:
                fd.last_reminded_at = at

    # ── Reminders ─────────────────────────────────────────────────────────────

    def remind(self, society_id: UUID, flat_ids: Optional[List[UUID]], min_months: int, user: Optional[User],
               not_reminded_within_days: Optional[int] = None) -> dict:
        """Send each flat's members (those with an app login) a reminder of
        the dues outstanding. `flat_ids` None: every defaulter. `user` None: sent by the
        automatic task. `not_reminded_within_days`: skip flats reminded more recently."""
        from app.services.notification_service import NotificationService

        as_of = date.today()
        dues = self.flats(society_id, as_of, flat_ids)
        if flat_ids is None:
            cutoff = months_before(as_of, min_months)
            dues = [fd for fd in dues if fd.overdue_beyond(cutoff) > 0]
        if not_reminded_within_days:
            self._last_reminders({fd.flat.id: fd for fd in dues})
            recent = datetime.utcnow() - timedelta(days=not_reminded_within_days)
            dues = [fd for fd in dues if fd.last_reminded_at is None or fd.last_reminded_at < recent]
        reminded, notifications, no_login = 0, 0, []
        for fd in dues:
            users = {r.user_id for r in fd.flat.residents if r.is_active and r.user_id}
            if not users:
                no_login.append(flat_label(fd.flat))
                continue
            oldest = fd.oldest.bill
            body = (f"₹{fd.total:,.2f} is outstanding on {flat_label(fd.flat)} "
                    f"({len(fd.bills)} bill{'s' if len(fd.bills) != 1 else ''}, the oldest "
                    f"{oldest.invoice_number} due on {oldest.due_date:%d %b %Y}). Please pay at the earliest — "
                    f"interest is charged on arrears as per the society's bye-laws.")
            for uid in users:
                NotificationService.send(
                    db=self.db, user_id=uid, title="Maintenance dues reminder", body=body,
                    type=NotificationType.REMINDER, module=REMINDER_MODULE, entity_id=str(fd.flat.id), push=True,
                )
                notifications += 1
            reminded += 1
        from app.models.audit_log import AuditAction
        from app.services.audit_service import AuditService
        AuditService.log(db=self.db, action=AuditAction.CREATE, module="billing", entity_type="DuesReminder",
                         entity_id=str(society_id), user=user,
                         new_values={"flats": reminded, "notifications": notifications,
                                     "automatic": user is None})
        self.db.commit()
        return {"flats_reminded": reminded, "notifications": notifications, "flats_without_app_login": no_login}


def member_contact(flat: Flat) -> tuple:
    """(name, phone) of the member a flat's dues are addressed to."""
    m = member(flat)
    if not m:
        return "-", None
    return m.full_name, getattr(m, "phone", None)


def bill_label(b: MaintenanceBill) -> str:
    return _bill_month(b).replace("Bill for the Month of ", "").replace("Bill for the Period ", "")
