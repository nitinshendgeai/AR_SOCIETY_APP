"""
Fines and additional charges on one flat (FlatCharge).

The committee or manager adds one with a reason; the maintenance calculator
puts it on the flat's next bill (see maintenance_calculator.py), and the member
is told when it is added. A one-off is marked billed against its bill and goes
back to waiting if that bill is cancelled; a recurring one goes on every bill
until it ends or is cancelled. Only a charge that is not on a bill yet can be
cancelled — one that is billed is reversed by cancelling the bill.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.notification import NotificationChannel, NotificationType
from app.models.resident import Resident
from app.models.user import User
from app.modules.billing.models.billing import ChargeType, FlatCharge, FlatChargeKind, FlatChargeStatus
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class FlatChargeService:

    def __init__(self, db: Session):
        self.db = db

    def _scoped(self, user: Optional[User], charge: FlatCharge) -> FlatCharge:
        if user is not None and user.society_id is not None and charge.society_id != user.society_id:
            raise HTTPException(404, "Charge not found")
        return charge

    def get(self, charge_id: UUID, user: Optional[User] = None) -> FlatCharge:
        charge = self.db.get(FlatCharge, charge_id)
        if charge is None or not charge.is_active:
            raise HTTPException(404, "Charge not found")
        return self._scoped(user, charge)

    def create(self, data: dict, user: User, request=None) -> FlatCharge:
        society_id = resolve_create_society_id(user, data["society_id"])
        flat = self.db.get(Flat, data["flat_id"])
        if flat is None or not flat.is_active or not flat.wing or flat.wing.society_id != society_id:
            raise HTTPException(422, "Flat not found in this society")
        if data.get("end_date") and not data.get("recurring"):
            raise HTTPException(422, "An end date is for a recurring charge")
        charge = FlatCharge(
            society_id=society_id, flat_id=flat.id, created_by=user.id,
            kind=data["kind"], title=data["title"], reason=data.get("reason"),
            amount=data["amount"], gst_applicable=bool(data.get("gst_applicable")) and data["kind"] == FlatChargeKind.EXTRA,
            effective_date=data["effective_date"], recurring=bool(data.get("recurring")),
            end_date=data.get("end_date"),
        )
        self.db.add(charge)
        self.db.flush()
        AuditService.log(db=self.db, action=AuditAction.CREATE, module="billing", entity_id=str(charge.id),
                         entity_type="FlatCharge", user=user, request=request,
                         new_values={"flat": str(flat.id), "kind": charge.kind.value, "title": charge.title,
                                     "amount": str(charge.amount), "recurring": charge.recurring})
        self.notify_flat(charge)
        self.db.commit()
        self.db.refresh(charge)
        return charge

    def notify_flat(self, charge: FlatCharge) -> None:
        """Everyone in the flat with a login is told."""
        what = "fine" if charge.kind == FlatChargeKind.FINE else "additional charge"
        residents = self.db.query(Resident).filter(Resident.flat_id == charge.flat_id, Resident.is_active == True,  # noqa: E712
                                                   Resident.user_id.isnot(None)).all()
        for uid in {r.user_id for r in residents}:
            NotificationService.send(
                db=self.db, user_id=uid, title=f"A {what} has been added to your flat",
                body=f"₹{charge.amount} — {charge.title}. It will appear on your next maintenance bill.",
                type=NotificationType.WARNING if charge.kind == FlatChargeKind.FINE else NotificationType.INFO,
                channel=NotificationChannel.IN_APP, module="billing", entity_id=str(charge.id))

    # ── Charges raised by other modules (amenity bookings, parking violations) ───────────────────────────────────────

    def raise_for_source(self, *, society_id: UUID, flat_id: UUID, kind: FlatChargeKind, title: str, amount,
                         source_type: str, source_id: UUID, user: Optional[User], reason: Optional[str] = None,
                         charge_type: Optional[ChargeType] = None, effective_date: Optional[date] = None,
                         notify: bool = False) -> Optional[FlatCharge]:
        """A fine or additional charge on a flat for something another module recorded, to go on the flat's next bill.
        One per source and type: asked again for the same source it returns the one already there. Nothing for a nil
        amount. Flushed, not committed — the caller's own action commits it."""
        amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
        if amount <= 0:
            return None
        existing = self.for_source(source_type, source_id)
        if existing is not None and existing.status != FlatChargeStatus.CANCELLED:
            return existing
        flat = self.db.get(Flat, flat_id)
        if flat is None or not flat.is_active or not flat.wing or flat.wing.society_id != society_id:
            raise HTTPException(422, "Flat not found in this society")
        charge = FlatCharge(
            society_id=society_id, flat_id=flat.id, created_by=user.id if user else None, kind=kind, title=title[:150],
            reason=reason, amount=amount, gst_applicable=False, effective_date=effective_date or date.today(),
            recurring=False, charge_type=charge_type if kind == FlatChargeKind.EXTRA else None,
            source_type=source_type, source_id=source_id)
        self.db.add(charge)
        self.db.flush()
        if notify:
            self.notify_flat(charge)
        return charge

    def for_source(self, source_type: str, source_id: UUID) -> Optional[FlatCharge]:
        """The charge raised for a source — the latest, if one was withdrawn and raised again."""
        return (self.db.query(FlatCharge).filter(
            FlatCharge.source_type == source_type, FlatCharge.source_id == source_id,
            FlatCharge.is_active == True)  # noqa: E712
            .order_by(FlatCharge.created_at.desc()).first())

    def withdraw_for_source(self, source_type: str, source_id: UUID, reason: str, user: Optional[User]) -> Optional[str]:
        """Take back the charge raised for a source while it is not on a bill. Returns what became of it: 'cancelled',
        'billed' (already on a bill: that bill's cancellation reverses it), or None when there was none. Not committed."""
        charge = self.for_source(source_type, source_id)
        if charge is None or charge.status == FlatChargeStatus.CANCELLED:
            return None
        if charge.status == FlatChargeStatus.BILLED:
            return "billed"
        charge.status = FlatChargeStatus.CANCELLED
        charge.cancelled_at = datetime.utcnow()
        charge.cancelled_by = user.id if user else None
        charge.cancel_reason = reason
        return "cancelled"

    def list_for_society(self, society_id: UUID, status: Optional[FlatChargeStatus] = None,
                         flat_id: Optional[UUID] = None, skip: int = 0, limit: int = 100) -> List[FlatCharge]:
        q = self.db.query(FlatCharge).filter(FlatCharge.society_id == society_id, FlatCharge.is_active == True)  # noqa: E712
        if status is not None:
            q = q.filter(FlatCharge.status == status)
        if flat_id is not None:
            q = q.filter(FlatCharge.flat_id == flat_id)
        return q.order_by(FlatCharge.created_at.desc()).offset(skip).limit(limit).all()

    def list_for_flat(self, flat_id: UUID) -> List[FlatCharge]:
        return self.db.query(FlatCharge).filter(
            FlatCharge.flat_id == flat_id, FlatCharge.is_active == True,  # noqa: E712
            FlatCharge.status != FlatChargeStatus.CANCELLED,
        ).order_by(FlatCharge.created_at.desc()).all()

    def cancel(self, charge_id: UUID, reason: str, user: User, request=None) -> FlatCharge:
        charge = self.get(charge_id, user)
        if charge.status == FlatChargeStatus.CANCELLED:
            raise HTTPException(409, "This charge is already cancelled")
        if charge.status == FlatChargeStatus.BILLED:
            raise HTTPException(409, "This charge is already on a bill — cancel that bill to reverse it")
        charge.status = FlatChargeStatus.CANCELLED
        charge.cancelled_at = datetime.utcnow()
        charge.cancelled_by = user.id
        charge.cancel_reason = reason
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="billing", entity_id=str(charge.id),
                         entity_type="FlatCharge", user=user, request=request,
                         old_values={"status": "active"}, new_values={"status": "cancelled", "reason": reason})
        self.db.commit()
        self.db.refresh(charge)
        return charge
