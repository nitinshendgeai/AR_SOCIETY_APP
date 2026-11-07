"""
Resident payment claims: a resident reports a payment they made (with the reference and a screenshot); the office checks
it against the bank and confirms or rejects it. Confirming records the payment through the office's own path
(BillingService.create_online_payment_submission), so receipts, allocation and the books behave exactly as for a payment
the office entered itself.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.notification import NotificationType
from app.models.role import Role
from app.models.user import User, UserRole, UserStatus
from app.modules.billing.models.billing import (
    MaintenanceBill, OnlinePaymentSubmission, PaymentClaim, PaymentMode,
)
from app.modules.billing.services.billing_service import (
    ALLOWED_SCREENSHOT_MIME_TYPES, MAX_SCREENSHOT_BYTES, BillingService, RESIDENT_VISIBLE_BILL_STATUSES,
)
from app.services.notification_service import NotificationService

# Who is told when a resident reports a payment: the people who record payments.
OFFICE_ROLES = {"Manager", "Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer"}
MAX_PENDING_PER_FLAT = 10


class PaymentClaimService:
    def __init__(self, db: Session):
        self.db = db
        self.billing = BillingService(db)

    # ── Where to pay ──────────────────────────────────────────────────────────

    def payment_info(self, user: User) -> dict:
        """The society's UPI id and bank details, as printed on every bill, for a resident who is about to pay."""
        if user.society_id is None:
            raise HTTPException(403, "Not part of a society")
        s = self.billing.get_maintenance_settings(user.society_id)
        return {
            "upi_id": s.upi_id, "bank_account_name": s.bank_account_name, "bank_name": s.bank_name,
            "bank_account_number": s.bank_account_number, "bank_ifsc": s.bank_ifsc, "notes": s.bill_notes,
        }

    # ── The resident's side ───────────────────────────────────────────────────

    def create(self, user: User, *, amount: Decimal, payment_date: date, payment_mode: PaymentMode,
               flat_id: Optional[UUID] = None, bill_id: Optional[UUID] = None,
               transaction_ref: Optional[str] = None, bank_name: Optional[str] = None, notes: Optional[str] = None,
               screenshot_bytes: Optional[bytes] = None, screenshot_mime_type: Optional[str] = None,
               screenshot_file_name: Optional[str] = None) -> PaymentClaim:
        if user.society_id is None:
            raise HTTPException(403, "Not part of a society")
        own = self.billing.resident_flat_ids(user)
        if not own:
            raise HTTPException(403, "Only a resident of a flat can report a payment")
        flat_id = flat_id or (next(iter(own)) if len(own) == 1 else None)
        if flat_id is None:
            raise HTTPException(422, "Say which flat the payment is for")
        if flat_id not in own:
            raise HTTPException(403, "You can report payments only for your own flat")

        if amount <= 0:
            raise HTTPException(422, "Amount must be greater than zero")
        today = date.today()
        if payment_date > today:
            raise HTTPException(422, "The payment date cannot be in the future")
        if payment_date < today - timedelta(days=366):
            raise HTTPException(422, "That payment date is too old to report here; ask the society office")

        if payment_mode == PaymentMode.ONLINE_GATEWAY:
            raise HTTPException(422, "Choose how you paid: UPI, bank transfer, NEFT, RTGS, cheque or cash")
        if screenshot_bytes:
            if len(screenshot_bytes) > MAX_SCREENSHOT_BYTES:
                raise HTTPException(422, f"Screenshot exceeds the {MAX_SCREENSHOT_BYTES // (1024 * 1024)}MB limit")
            if screenshot_mime_type not in ALLOWED_SCREENSHOT_MIME_TYPES:
                raise HTTPException(422, f"Unsupported image type: {screenshot_mime_type}")
        elif payment_mode in BillingService.SCREENSHOT_REQUIRED_MODES:
            raise HTTPException(422, f"A screenshot of the payment is required for {payment_mode.value.replace('_', ' ')}")

        ref = (transaction_ref or "").strip() or None
        if payment_mode in BillingService.SCREENSHOT_REQUIRED_MODES and not ref:
            raise HTTPException(422, "Enter the UPI or bank reference (UTR) of the payment")

        if bill_id is not None:
            bill = self.db.query(MaintenanceBill).filter(MaintenanceBill.id == bill_id).first()
            if bill is None or bill.flat_id != flat_id or bill.bill_status not in RESIDENT_VISIBLE_BILL_STATUSES:
                raise HTTPException(404, "Bill not found")
            self.billing._validate_bill_for_payment(bill, amount)

        if ref:
            if self.db.query(PaymentClaim).filter(
                    PaymentClaim.society_id == user.society_id, PaymentClaim.transaction_ref == ref,
                    PaymentClaim.status != "rejected").first() or self.db.query(OnlinePaymentSubmission).filter(
                    OnlinePaymentSubmission.society_id == user.society_id,
                    OnlinePaymentSubmission.transaction_ref == ref).first():
                raise HTTPException(409, "A payment with that reference has already been reported or recorded")
        waiting = self.db.query(PaymentClaim).filter(
            PaymentClaim.flat_id == flat_id, PaymentClaim.status == "pending").count()
        if waiting >= MAX_PENDING_PER_FLAT:
            raise HTTPException(409, "Too many payments are waiting for the office to check. Wait for those first")

        claim = PaymentClaim(
            society_id=user.society_id, flat_id=flat_id, bill_id=bill_id, claimed_by=user.id, amount=amount,
            payment_date=payment_date, payment_mode=payment_mode.value, transaction_ref=ref,
            bank_name=(bank_name or "").strip() or None, notes=(notes or "").strip() or None, status="pending",
            screenshot_data=screenshot_bytes or None, screenshot_mime_type=screenshot_mime_type if screenshot_bytes else None,
            screenshot_file_name=screenshot_file_name if screenshot_bytes else None)
        self.db.add(claim)
        self.db.flush()
        flat = self.db.query(Flat).filter(Flat.id == flat_id).first()
        label = self._flat_label(flat)
        for uid in self._office_user_ids(user.society_id):
            NotificationService.send(
                db=self.db, user_id=uid, title="Payment reported",
                body=f"{label} reports ₹{amount} paid by {payment_mode.value.replace('_', ' ')}. Check it and confirm.",
                type=NotificationType.INFO, module="payment_claim", entity_id=str(claim.id))
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def mine(self, user: User) -> List[PaymentClaim]:
        own = self.billing.resident_flat_ids(user)
        if not own:
            return []
        return (self.db.query(PaymentClaim).filter(PaymentClaim.flat_id.in_(own))
                .order_by(PaymentClaim.created_at.desc()).limit(100).all())

    # ── The office's side ─────────────────────────────────────────────────────

    def list_for_society(self, society_id: UUID, user: User, status: Optional[str] = None) -> List[PaymentClaim]:
        assert_society_access(user, society_id)
        q = self.db.query(PaymentClaim).filter(PaymentClaim.society_id == society_id)
        if status:
            q = q.filter(PaymentClaim.status == status)
        return q.order_by(PaymentClaim.created_at.desc()).limit(200).all()

    def get_for(self, claim_id: UUID, user: User, *, office: bool) -> PaymentClaim:
        """The claim, if the caller may see it: the office for its society, or the resident of its flat. 404 otherwise."""
        claim = self.db.query(PaymentClaim).filter(PaymentClaim.id == claim_id).first()
        if claim is None:
            raise HTTPException(404, "Payment claim not found")
        if office:
            assert_society_access(user, claim.society_id)
        elif claim.flat_id not in self.billing.resident_flat_ids(user):
            raise HTTPException(404, "Payment claim not found")
        return claim

    def confirm(self, claim_id: UUID, user: User, *, deposit_account_id: Optional[UUID] = None,
                notes: Optional[str] = None) -> PaymentClaim:
        claim = self.get_for(claim_id, user, office=True)
        if claim.status != "pending":
            raise HTTPException(409, f"This claim is already {claim.status}")
        if claim.transaction_ref and self.db.query(OnlinePaymentSubmission).filter(
                OnlinePaymentSubmission.society_id == claim.society_id,
                OnlinePaymentSubmission.transaction_ref == claim.transaction_ref).first():
            raise HTTPException(409, "A payment with this reference is already recorded. Reject this claim instead")
        submission = self.billing.create_online_payment_submission(
            flat_id=claim.flat_id, amount=claim.amount, payment_date=claim.payment_date,
            payment_mode=PaymentMode(claim.payment_mode), transaction_ref=claim.transaction_ref,
            bank_name=claim.bank_name,
            notes=" · ".join(x for x in ("Reported by the resident", claim.notes) if x),
            user=user, bill_id=claim.bill_id,
            screenshot_bytes=claim.screenshot_data, screenshot_mime_type=claim.screenshot_mime_type,
            screenshot_file_name=claim.screenshot_file_name, deposit_account_id=deposit_account_id,
            require_screenshot=False)
        claim = self.db.query(PaymentClaim).filter(PaymentClaim.id == claim_id).first()
        claim.status = "confirmed"
        claim.reviewed_by = user.id
        claim.reviewed_at = datetime.utcnow()
        claim.review_notes = (notes or "").strip() or None
        claim.submission_id = submission.id
        self._tell_resident(claim, "Payment confirmed",
                            f"The office confirmed your payment of ₹{claim.amount}. Receipt {submission.receipt_number}.")
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def reject(self, claim_id: UUID, user: User, reason: str) -> PaymentClaim:
        reason = (reason or "").strip()
        if not reason:
            raise HTTPException(422, "Give the resident a reason")
        claim = self.get_for(claim_id, user, office=True)
        if claim.status != "pending":
            raise HTTPException(409, f"This claim is already {claim.status}")
        claim.status = "rejected"
        claim.reviewed_by = user.id
        claim.reviewed_at = datetime.utcnow()
        claim.review_notes = reason
        self._tell_resident(claim, "Payment not confirmed",
                            f"The office could not confirm your payment of ₹{claim.amount}: {reason}")
        self.db.commit()
        self.db.refresh(claim)
        return claim

    # ── Output ────────────────────────────────────────────────────────────────

    @staticmethod
    def _flat_label(flat) -> str:
        if flat is None:
            return "A flat"
        wing = flat.wing.name if getattr(flat, "wing", None) else None
        return f"{wing}-{flat.flat_number}" if wing else flat.flat_number

    def out(self, c: PaymentClaim) -> dict:
        return {
            "id": str(c.id), "status": c.status, "society_id": str(c.society_id), "flat_id": str(c.flat_id),
            "flat_label": self._flat_label(c.flat), "bill_id": str(c.bill_id) if c.bill_id else None,
            "bill_invoice_number": c.bill.invoice_number if c.bill else None,
            "amount": str(c.amount), "payment_date": c.payment_date.isoformat(), "payment_mode": c.payment_mode,
            "transaction_ref": c.transaction_ref, "bank_name": c.bank_name, "notes": c.notes,
            "claimed_by_name": c.claimer.full_name if c.claimer else None,
            "has_screenshot": bool(c.screenshot_data), "screenshot_mime_type": c.screenshot_mime_type,
            "review_notes": c.review_notes, "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            "receipt_number": c.submission.receipt_number if c.submission else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }

    # ── Notifications ─────────────────────────────────────────────────────────

    def _office_user_ids(self, society_id: UUID) -> List[UUID]:
        rows = (self.db.query(User.id).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
                .filter(User.society_id == society_id, User.status == UserStatus.ACTIVE, Role.name.in_(OFFICE_ROLES))
                .distinct().all())
        return [r[0] for r in rows]

    def _tell_resident(self, claim: PaymentClaim, title: str, body: str) -> None:
        if claim.claimed_by:
            NotificationService.send(db=self.db, user_id=claim.claimed_by, title=title, body=body,
                                     type=NotificationType.INFO, module="payment_claim", entity_id=str(claim.id))
