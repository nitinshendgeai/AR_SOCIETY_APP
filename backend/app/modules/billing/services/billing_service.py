"""
BillingService — maintenance billing workflow engine.

Workflow:
  Create FinancialPeriod → Create BillingCycle → Generate Bills per flat
  → Issue Bills → Record Payment → Update DueTracker → Generate Receipt
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.billing.models.billing import (
    FinancialPeriod, MaintenanceChargeConfig, BillingCycle,
    MaintenanceBill, InvoiceLineItem, PaymentReceipt, DueTracker, PenaltyRule,
    BillStatus, ChargeType,
)
from app.modules.billing.repositories.billing_repo import (
    FinancialPeriodRepo, ChargeConfigRepo, BillingCycleRepo,
    MaintenanceBillRepo, PaymentReceiptRepo, DueTrackerRepo, PenaltyRuleRepo,
)
from app.models.flat import Flat
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class BillingService:

    def __init__(self, db: Session):
        self.db           = db
        self.period_repo  = FinancialPeriodRepo(db)
        self.charge_repo  = ChargeConfigRepo(db)
        self.cycle_repo   = BillingCycleRepo(db)
        self.bill_repo    = MaintenanceBillRepo(db)
        self.receipt_repo = PaymentReceiptRepo(db)
        self.due_repo     = DueTrackerRepo(db)
        self.penalty_repo = PenaltyRuleRepo(db)

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="billing",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Financial Periods ─────────────────────────────────────────────────────

    def create_period(self, data: dict, user: User) -> FinancialPeriod:
        period = FinancialPeriod(**data)
        return self.period_repo.create(period)

    def close_period(self, period_id: UUID, user: User) -> FinancialPeriod:
        p = self.period_repo.get(period_id)
        if not p: raise HTTPException(404, "Period not found")
        if p.is_closed: raise HTTPException(409, "Period already closed")
        p.is_closed = True; p.closed_by = user.id
        self.db.commit(); self.db.refresh(p)
        return p

    def list_periods(self, society_id: UUID) -> List[FinancialPeriod]:
        return self.period_repo.get_by_society(society_id)

    # ── Charge Configuration ──────────────────────────────────────────────────

    def create_charge_config(self, data: dict, user: User) -> MaintenanceChargeConfig:
        config = MaintenanceChargeConfig(**data)
        self.charge_repo.create(config)
        self._audit(AuditAction.CREATE, config, "ChargeConfig", user,
                    new_values={"name": data.get("name"), "amount": str(data.get("default_amount"))})
        return config

    def list_charge_configs(self, society_id: UUID) -> List[MaintenanceChargeConfig]:
        return self.charge_repo.get_by_society(society_id)

    # ── Billing Cycle ─────────────────────────────────────────────────────────

    def create_cycle(self, data: dict, user: User, request=None) -> BillingCycle:
        cycle = BillingCycle(**data, created_by=user.id)
        self.cycle_repo.create(cycle)
        self._audit(AuditAction.CREATE, cycle, "BillingCycle", user, request,
                    new_values={"name": data.get("name"), "due_date": str(data.get("due_date"))})
        return cycle

    def list_cycles(self, society_id: UUID) -> List[BillingCycle]:
        return self.cycle_repo.get_by_society(society_id)

    # ── Bill Generation ───────────────────────────────────────────────────────

    def generate_bills_for_cycle(self, cycle_id: UUID, user: User,
                                  request=None) -> List[MaintenanceBill]:
        """
        Generate one MaintenanceBill per flat for a billing cycle.
        Uses active charge configs for the society.
        Prevents duplicate generation.
        """
        cycle = self.cycle_repo.get(cycle_id)
        if not cycle: raise HTTPException(404, "Billing cycle not found")
        if cycle.is_finalized:
            raise HTTPException(409, "Billing cycle already finalized")

        # Check already generated
        existing = self.bill_repo.get_by_cycle(cycle_id)
        if existing:
            raise HTTPException(409, f"Bills already generated for this cycle ({len(existing)} bills)")

        # Get charge configs
        charges = self.charge_repo.get_by_society(cycle.society_id)
        if not charges:
            raise HTTPException(422, "No charge configs found for this society. Add charges first.")

        # Get all active flats
        flats = self.db.query(Flat).filter(
            Flat.wing.has(society_id=cycle.society_id),
            Flat.is_active == True,
        ).all()
        if not flats:
            raise HTTPException(422, "No active flats found for this society")

        bills = []
        for flat in flats:
            invoice_number = self.bill_repo.next_invoice_number(cycle.society_id)
            bill = MaintenanceBill(
                society_id=cycle.society_id, cycle_id=cycle_id,
                flat_id=flat.id, generated_by=user.id,
                invoice_number=invoice_number,
                bill_status=BillStatus.GENERATED,
                bill_date=date.today(), due_date=cycle.due_date,
            )
            self.db.add(bill)
            self.db.flush()

            # Generate line items from charge configs
            subtotal = Decimal(0)
            tax_total = Decimal(0)
            for charge in charges:
                unit_rate = charge.default_amount or Decimal(0)
                if charge.is_per_sqft and flat.area_sqft:
                    unit_rate = unit_rate * Decimal(str(flat.area_sqft))
                qty = Decimal(1)
                amount = unit_rate * qty
                tax = (amount * charge.tax_percent / 100).quantize(Decimal("0.01"))
                total = amount + tax

                line = InvoiceLineItem(
                    bill_id=bill.id, charge_type=charge.charge_type,
                    description=charge.name, quantity=float(qty),
                    unit_rate=unit_rate, amount=amount,
                    tax_percent=charge.tax_percent, tax_amount=tax, total=total,
                )
                self.db.add(line)
                subtotal  += amount
                tax_total += tax

            bill.subtotal     = subtotal
            bill.tax_amount   = tax_total
            bill.total_amount = subtotal + tax_total
            bill.outstanding  = bill.total_amount

            # Update due tracker
            tracker = self.due_repo.get_or_create(flat.id, cycle.society_id)
            tracker.total_billed  += bill.total_amount
            tracker.outstanding   += bill.total_amount
            tracker.last_bill_date = date.today()

            bills.append(bill)

        cycle.is_finalized          = True
        cycle.total_flats_billed    = len(bills)
        cycle.total_amount_generated = sum(b.total_amount for b in bills)

        self._audit(AuditAction.CREATE, cycle, "BillingCycle", user, request,
                    new_values={"bills_generated": len(bills),
                                "total": str(cycle.total_amount_generated)})
        self.db.commit()
        return bills

    def issue_bill(self, bill_id: UUID, user: User, request=None) -> MaintenanceBill:
        bill = self.bill_repo.get(bill_id)
        if not bill: raise HTTPException(404, "Bill not found")
        if bill.bill_status != BillStatus.GENERATED:
            raise HTTPException(409, f"Bill cannot be issued (status: {bill.bill_status.value})")

        bill.bill_status = BillStatus.ISSUED
        bill.issued_at   = datetime.utcnow()

        # Notify resident
        if bill.resident_id:
            res = bill.resident
            if res and res.user_id:
                NotificationService.send(
                    db=self.db, user_id=res.user_id,
                    title=f"Maintenance Bill Generated — {bill.invoice_number}",
                    body=f"Bill of ₹{bill.total_amount} due by {bill.due_date}. Please pay on time.",
                    type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                    module="billing", entity_id=str(bill.id),
                )

        self._audit(AuditAction.UPDATE, bill, "MaintenanceBill", user, request,
                    new_values={"status": "issued", "amount": str(bill.total_amount)})
        self.db.commit()
        self.db.refresh(bill)
        return bill

    def cancel_bill(self, bill_id: UUID, reason: str, user: User) -> MaintenanceBill:
        bill = self.bill_repo.get(bill_id)
        if not bill: raise HTTPException(404, "Bill not found")
        if bill.bill_status == BillStatus.PAID:
            raise HTTPException(409, "Cannot cancel a paid bill")

        # Reverse due tracker
        tracker = self.due_repo.get_by_flat(bill.flat_id)
        if tracker:
            tracker.total_billed -= bill.total_amount
            tracker.outstanding  -= bill.outstanding

        bill.bill_status        = BillStatus.CANCELLED
        bill.cancelled_at       = datetime.utcnow()
        bill.cancellation_reason = reason
        self.db.commit()
        self.db.refresh(bill)
        return bill

    # ── Payment Recording ─────────────────────────────────────────────────────

    def record_payment(self, data: dict, user: User, request=None) -> PaymentReceipt:
        bill = self.bill_repo.get(data["bill_id"])
        if not bill: raise HTTPException(404, "Bill not found")
        if bill.bill_status == BillStatus.PAID:
            raise HTTPException(409, "Bill is already fully paid")
        if bill.bill_status == BillStatus.CANCELLED:
            raise HTTPException(409, "Cannot record payment for cancelled bill")

        amount = Decimal(str(data["amount"]))

        # Over-payment prevention
        if amount > bill.outstanding:
            raise HTTPException(422,
                f"Payment amount ₹{amount} exceeds outstanding ₹{bill.outstanding}")

        receipt_number = self.receipt_repo.next_receipt_number(bill.society_id)
        receipt = PaymentReceipt(
            **data,
            society_id=bill.society_id,
            flat_id=bill.flat_id,
            receipt_number=receipt_number,
            received_by=user.id,
        )
        self.db.add(receipt)
        self.db.flush()

        # Update bill
        bill.paid_amount += amount
        bill.outstanding  = bill.total_amount + bill.penalty_amount - bill.paid_amount

        if bill.outstanding <= 0:
            bill.bill_status = BillStatus.PAID
            bill.paid_at     = datetime.utcnow()
        else:
            bill.bill_status = BillStatus.PARTIALLY_PAID

        # Update due tracker
        tracker = self.due_repo.get_or_create(bill.flat_id, bill.society_id)
        tracker.total_paid      += amount
        tracker.outstanding     -= amount
        tracker.last_payment_date = data["payment_date"]
        tracker.last_updated_by   = user.id

        self._audit(AuditAction.CREATE, receipt, "PaymentReceipt", user, request,
                    new_values={"amount": str(amount), "mode": data.get("payment_mode"),
                                "bill": bill.invoice_number})
        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_bill(self, bill_id: UUID) -> MaintenanceBill:
        b = self.bill_repo.get(bill_id)
        if not b: raise HTTPException(404, "Bill not found")
        return b

    def get_flat_bills(self, flat_id: UUID, skip=0, limit=50) -> List[MaintenanceBill]:
        return self.bill_repo.get_by_flat(flat_id, skip, limit)

    def get_overdue_bills(self, society_id: UUID) -> List[MaintenanceBill]:
        return self.bill_repo.get_overdue(society_id)

    def get_outstanding_bills(self, society_id: UUID) -> List[MaintenanceBill]:
        return self.bill_repo.get_outstanding_by_society(society_id)

    def get_flat_receipts(self, flat_id: UUID, skip=0, limit=50) -> List[PaymentReceipt]:
        return self.receipt_repo.get_by_flat(flat_id, skip, limit)

    def get_flat_due(self, flat_id: UUID, society_id: UUID) -> DueTracker:
        return self.due_repo.get_or_create(flat_id, society_id)

    def get_all_outstanding_dues(self, society_id: UUID) -> List[DueTracker]:
        return self.due_repo.get_all_outstanding(society_id)

    # ── Penalty Rules ─────────────────────────────────────────────────────────

    def create_penalty_rule(self, data: dict, user: User) -> PenaltyRule:
        rule = PenaltyRule(**data)
        return self.penalty_repo.create(rule)

    def list_penalty_rules(self, society_id: UUID) -> List[PenaltyRule]:
        return self.penalty_repo.get_active(society_id)
