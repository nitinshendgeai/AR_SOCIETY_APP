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
    OnlinePaymentSubmission, ReconciliationStatus,
    BankStatementEntry, BankStatementMatchStatus,
    BillStatus, ChargeType, PaymentMode,
)
from app.modules.billing.repositories.billing_repo import (
    FinancialPeriodRepo, ChargeConfigRepo, BillingCycleRepo,
    MaintenanceBillRepo, PaymentReceiptRepo, DueTrackerRepo, PenaltyRuleRepo,
    OnlinePaymentSubmissionRepo, BankStatementEntryRepo,
)
from app.models.flat import Flat
from app.models.wing import Wing
from app.models.resident import Resident
from app.modules.billing.services.bill_pdf import generate_maintenance_bill_pdf
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel

ALLOWED_SCREENSHOT_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024  # 8 MB

RESIDENT_VISIBLE_BILL_STATUSES = (
    BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE,
)


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
        self.online_payment_repo = OnlinePaymentSubmissionRepo(db)
        self.bank_statement_repo = BankStatementEntryRepo(db)

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
        self.db.refresh(config)
        return config

    def list_charge_configs(self, society_id: UUID) -> List[MaintenanceChargeConfig]:
        return self.charge_repo.get_by_society(society_id)

    def update_charge_config(self, config_id: UUID, data: dict, user: User) -> MaintenanceChargeConfig:
        # Only affects bills generated afterwards — existing bills keep their
        # own InvoiceLineItem copies of the rate/tax at generation time.
        config = self.db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.id == config_id).first()
        if not config: raise HTTPException(404, "Charge head not found")
        old = {"name": config.name, "amount": str(config.default_amount), "active": config.is_active}
        for field, value in data.items():
            setattr(config, field, value)
        self._audit(AuditAction.UPDATE, config, "ChargeConfig", user, old_values=old,
                    new_values={k: str(v) for k, v in data.items()})
        self.db.commit(); self.db.refresh(config)
        return config

    # ── Billing Cycle ─────────────────────────────────────────────────────────

    def create_cycle(self, data: dict, user: User, request=None) -> BillingCycle:
        cycle = BillingCycle(**data, created_by=user.id)
        self.cycle_repo.create(cycle)
        self._audit(AuditAction.CREATE, cycle, "BillingCycle", user, request,
                    new_values={"name": data.get("name"), "due_date": str(data.get("due_date"))})
        self.db.refresh(cycle)
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
            resident = self.db.query(Resident).filter(
                Resident.flat_id == flat.id, Resident.is_active == True,
            ).order_by(Resident.is_primary.desc()).first()
            bill = MaintenanceBill(
                society_id=cycle.society_id, cycle_id=cycle_id,
                flat_id=flat.id, generated_by=user.id,
                resident_id=resident.id if resident else None,
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

    def _issue(self, bill: MaintenanceBill, user: User, request=None) -> None:
        bill.bill_status = BillStatus.ISSUED
        bill.issued_at   = datetime.utcnow()

        # Every active resident of the flat with an app login is notified,
        # not only bill.resident — the primary owner often has no account
        # while a co-owner or family member does.
        residents = self.db.query(Resident).filter(
            Resident.flat_id == bill.flat_id, Resident.is_active == True,
            Resident.user_id.isnot(None),
        ).all()
        for user_id in {r.user_id for r in residents}:
            NotificationService.send(
                db=self.db, user_id=user_id,
                title=f"Maintenance Bill Issued — {bill.invoice_number}",
                body=f"Bill of ₹{bill.total_amount} due by {bill.due_date}. Please pay on time.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="billing", entity_id=str(bill.id),
            )

        self._audit(AuditAction.UPDATE, bill, "MaintenanceBill", user, request,
                    new_values={"status": "issued", "amount": str(bill.total_amount)})

    def issue_bill(self, bill_id: UUID, user: User, request=None) -> MaintenanceBill:
        bill = self.bill_repo.get(bill_id)
        if not bill: raise HTTPException(404, "Bill not found")
        if bill.bill_status != BillStatus.GENERATED:
            raise HTTPException(409, f"Bill cannot be issued (status: {bill.bill_status.value})")
        self._issue(bill, user, request)
        self.db.commit()
        self.db.refresh(bill)
        return bill

    def issue_all_bills(self, cycle_id: UUID, user: User, request=None) -> int:
        cycle = self.cycle_repo.get(cycle_id)
        if not cycle: raise HTTPException(404, "Billing cycle not found")
        pending = [b for b in self.bill_repo.get_by_cycle(cycle_id)
                   if b.bill_status == BillStatus.GENERATED]
        if not pending:
            raise HTTPException(409, "No generated bills left to issue in this cycle")
        for bill in pending:
            self._issue(bill, user, request)
        self.db.commit()
        return len(pending)

    def list_cycle_bills(self, cycle_id: UUID) -> List[MaintenanceBill]:
        if not self.cycle_repo.get(cycle_id):
            raise HTTPException(404, "Billing cycle not found")
        return self.bill_repo.get_by_cycle(cycle_id)

    def get_cycle(self, cycle_id: UUID) -> BillingCycle:
        cycle = self.cycle_repo.get(cycle_id)
        if not cycle: raise HTTPException(404, "Billing cycle not found")
        return cycle

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

    def _validate_bill_for_payment(self, bill: MaintenanceBill, amount: Decimal) -> None:
        """Shared by record_payment() and the on-bill path of
        create_online_payment_submission() — both apply a payment to a bill
        and must reject the same invalid states before touching anything."""
        if bill.bill_status == BillStatus.PAID:
            raise HTTPException(409, "Bill is already fully paid")
        if bill.bill_status == BillStatus.CANCELLED:
            raise HTTPException(409, "Cannot record payment for cancelled bill")
        if amount > bill.outstanding:
            raise HTTPException(422,
                f"Payment amount ₹{amount} exceeds outstanding ₹{bill.outstanding}")

    def _apply_payment_to_bill(self, bill: MaintenanceBill, amount: Decimal,
                                payment_date: date, user: User) -> None:
        """Mutates `bill` and its DueTracker in place — caller must have
        already validated via _validate_bill_for_payment() and is
        responsible for the commit."""
        bill.paid_amount += amount
        bill.outstanding  = bill.total_amount + bill.penalty_amount - bill.paid_amount

        if bill.outstanding <= 0:
            bill.bill_status = BillStatus.PAID
            bill.paid_at     = datetime.utcnow()
        else:
            bill.bill_status = BillStatus.PARTIALLY_PAID

        tracker = self.due_repo.get_or_create(bill.flat_id, bill.society_id)
        tracker.total_paid      += amount
        tracker.outstanding     -= amount
        tracker.last_payment_date = payment_date
        tracker.last_updated_by   = user.id

    def record_payment(self, data: dict, user: User, request=None) -> PaymentReceipt:
        bill = self.bill_repo.get(data["bill_id"])
        if not bill: raise HTTPException(404, "Bill not found")
        amount = Decimal(str(data["amount"]))
        self._validate_bill_for_payment(bill, amount)

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

        self._apply_payment_to_bill(bill, amount, data["payment_date"], user)

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

    def resident_flat_ids(self, user: User) -> set:
        return {r.flat_id for r in self.db.query(Resident).filter(
            Resident.user_id == user.id, Resident.is_active == True)}

    def get_my_bills(self, user: User) -> List[MaintenanceBill]:
        """Bills for every flat the user is an active resident of. Bills
        still at GENERATED haven't been released by the society yet, so
        they're hidden from residents along with cancelled ones."""
        flat_ids = self.resident_flat_ids(user)
        if not flat_ids:
            return []
        return self.db.query(MaintenanceBill).filter(
            MaintenanceBill.flat_id.in_(flat_ids),
            MaintenanceBill.is_active == True,
            MaintenanceBill.bill_status.in_(RESIDENT_VISIBLE_BILL_STATUSES),
        ).order_by(MaintenanceBill.bill_date.desc()).all()

    def generate_bill_pdf(self, bill_id: UUID) -> bytes:
        bill = self.get_bill(bill_id)
        society_name = bill.society.name if bill.society else "Society"
        return generate_maintenance_bill_pdf(bill, society_name)

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

    # ── Payment receipts (on-bill or on-account, single entry point) ─────────
    #
    # Screenshot proof is only meaningful — and only required — for the
    # modes where a resident actually has something to show (a UPI/bank
    # app screen); cash and cheque have no such artifact.
    SCREENSHOT_REQUIRED_MODES = {
        PaymentMode.UPI, PaymentMode.BANK_TRANSFER, PaymentMode.NEFT,
        PaymentMode.RTGS, PaymentMode.ONLINE_GATEWAY,
    }

    def create_online_payment_submission(
        self, *, flat_id: UUID, amount: Decimal, payment_date: date,
        payment_mode, transaction_ref: Optional[str], bank_name: Optional[str],
        notes: Optional[str], user: User,
        bill_id: Optional[UUID] = None,
        screenshot_bytes: Optional[bytes] = None, screenshot_mime_type: Optional[str] = None,
        screenshot_file_name: Optional[str] = None,
        purpose: ChargeType = ChargeType.MAINTENANCE,
    ) -> OnlinePaymentSubmission:
        flat = self.db.query(Flat).filter(Flat.id == flat_id, Flat.is_active == True).first()
        if not flat:
            raise HTTPException(404, "Flat not found")
        wing = self.db.query(Wing).filter(Wing.id == flat.wing_id).first()
        if not wing:
            raise HTTPException(404, "Wing not found for this flat")

        if amount <= 0:
            raise HTTPException(422, "Amount must be greater than zero")

        if screenshot_bytes:
            if len(screenshot_bytes) > MAX_SCREENSHOT_BYTES:
                raise HTTPException(422, f"Screenshot exceeds the {MAX_SCREENSHOT_BYTES // (1024*1024)}MB limit")
            if screenshot_mime_type not in ALLOWED_SCREENSHOT_MIME_TYPES:
                raise HTTPException(422, f"Unsupported image type: {screenshot_mime_type}")
        elif payment_mode in self.SCREENSHOT_REQUIRED_MODES:
            raise HTTPException(422, f"Payment screenshot is required for {payment_mode.value}")

        # On-bill: apply immediately, same accounting path as record_payment().
        # Reconciliation (below) is a separate, later check — it doesn't gate
        # the bill being marked paid or the receipt being issued.
        bill = None
        if bill_id is not None:
            bill = self.bill_repo.get(bill_id)
            if not bill:
                raise HTTPException(404, "Bill not found")
            if bill.flat_id != flat.id:
                raise HTTPException(422, "Bill does not belong to this flat")
            self._validate_bill_for_payment(bill, amount)

        # Cash has no bank statement to reconcile against — treat it as
        # settled immediately. Every other mode, cheque included (can still
        # bounce), starts PENDING for a manager to clear later.
        status = (ReconciliationStatus.RECONCILED if payment_mode == PaymentMode.CASH
                  else ReconciliationStatus.PENDING)

        receipt_number = self.online_payment_repo.next_receipt_number(wing.society_id)
        submission = OnlinePaymentSubmission(
            society_id=wing.society_id, wing_id=wing.id, flat_id=flat.id,
            bill_id=bill.id if bill else None,
            recorded_by=user.id, receipt_number=receipt_number,
            amount=amount, payment_date=payment_date, payment_mode=payment_mode,
            transaction_ref=transaction_ref, bank_name=bank_name, notes=notes,
            purpose=purpose,
            status=status,
            screenshot_data=screenshot_bytes, screenshot_mime_type=screenshot_mime_type,
            screenshot_file_name=screenshot_file_name,
        )
        self.db.add(submission)
        self.db.flush()

        if bill is not None:
            self._apply_payment_to_bill(bill, amount, payment_date, user)

        self._audit(AuditAction.CREATE, submission, "OnlinePaymentSubmission", user,
                    new_values={"amount": str(amount), "flat": flat.flat_number,
                                "receipt_number": receipt_number,
                                "bill": bill.invoice_number if bill else None})
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def get_online_payment_submission(self, submission_id: UUID) -> OnlinePaymentSubmission:
        s = self.online_payment_repo.get(submission_id)
        if not s: raise HTTPException(404, "Payment submission not found")
        return s

    def list_online_payment_submissions(self, society_id: UUID, status=None,
                                         wing_id=None, flat_id=None,
                                         skip=0, limit=50) -> List[OnlinePaymentSubmission]:
        return self.online_payment_repo.get_by_society(
            society_id, status=status, wing_id=wing_id, flat_id=flat_id, skip=skip, limit=limit)

    def update_online_payment_status(self, submission_id: UUID, status: ReconciliationStatus,
                                      review_notes: Optional[str], user: User) -> OnlinePaymentSubmission:
        submission = self.get_online_payment_submission(submission_id)
        submission.status = status
        submission.reviewed_by = user.id
        submission.reviewed_at = datetime.utcnow()
        if review_notes is not None:
            submission.review_notes = review_notes
        self._audit(AuditAction.UPDATE, submission, "OnlinePaymentSubmission", user,
                    new_values={"status": status.value, "receipt_number": submission.receipt_number})
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def export_online_payments_csv(self, society_id: UUID, status=None,
                                    wing_id=None, flat_id=None) -> str:
        import csv, io
        rows = self.online_payment_repo.get_by_society(
            society_id, status=status, wing_id=wing_id, flat_id=flat_id, skip=0, limit=10000)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Receipt Number", "Wing", "Flat", "Amount", "Bill No", "On Account Of", "Payment Date",
            "Payment Mode", "Transaction Ref", "Bank Name", "Status", "Recorded At", "Reviewed At", "Notes",
        ])
        for r in rows:
            writer.writerow([
                r.receipt_number,
                r.wing.name if r.wing else "",
                r.flat.flat_number if r.flat else "",
                str(r.amount), r.bill.invoice_number if r.bill else "",
                r.purpose.value.replace("_", " ").title(),
                r.payment_date.isoformat(), r.payment_mode.value,
                r.transaction_ref or "", r.bank_name or "", r.status.value,
                r.created_at.isoformat() if r.created_at else "",
                r.reviewed_at.isoformat() if r.reviewed_at else "",
                (r.notes or "").replace("\n", " "),
            ])
        return buf.getvalue()

    # ── Bank Reconciliation ──────────────────────────────────────────────────
    #
    # The other half of the loop from update_online_payment_status() above:
    # instead of a manager eyeballing a bank statement outside the app and
    # manually flipping each submission to RECONCILED, they import the
    # statement here and the system suggests matches by amount + nearby
    # date. A match is only ever applied via confirm_bank_match() — import
    # alone never changes a submission's status, so nothing about a bill's
    # paid state can be affected by a bad statement upload.

    MATCH_DATE_WINDOW_DAYS = 5

    def import_bank_statement_csv(self, society_id: UUID, csv_text: str, user: User) -> List[BankStatementEntry]:
        """Expects a header row with columns Date, Description, Amount, and
        optionally Reference (case-insensitive, any order) — a generic
        format the admin prepares from whatever their bank's own export
        looks like, since every bank's raw CSV differs. Date accepts
        YYYY-MM-DD or DD-MM-YYYY. Only positive (credit) amounts are kept;
        debits/withdrawals are irrelevant to resident-payment reconciliation."""
        import csv, io
        from decimal import InvalidOperation

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise HTTPException(422, "CSV has no header row")
        columns = {f.strip().lower(): f for f in reader.fieldnames if f}
        missing = [c for c in ("date", "description", "amount") if c not in columns]
        if missing:
            raise HTTPException(
                422,
                f"CSV missing required column(s): {', '.join(missing)}. "
                "Expected headers: Date, Description, Amount, and optionally Reference.",
            )

        rows = []
        for i, raw in enumerate(reader, start=2):  # row 1 is the header
            date_str   = (raw.get(columns["date"]) or "").strip()
            desc       = (raw.get(columns["description"]) or "").strip()
            amount_str = (raw.get(columns["amount"]) or "").strip()
            ref        = (raw.get(columns["reference"]) or "").strip() if "reference" in columns else ""
            if not date_str and not amount_str:
                continue  # skip blank rows
            txn_date = None
            for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                try:
                    txn_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            if txn_date is None:
                raise HTTPException(422, f"Row {i}: unrecognized date {date_str!r} — use YYYY-MM-DD or DD-MM-YYYY")
            try:
                amount = Decimal(amount_str.replace(",", ""))
            except InvalidOperation:
                raise HTTPException(422, f"Row {i}: unrecognized amount {amount_str!r}")
            if amount <= 0:
                continue  # debit/zero row — nothing to reconcile against
            rows.append({
                "txn_date": txn_date,
                "description": desc or "(no description)",
                "reference": ref or None,
                "amount": amount,
            })

        if not rows:
            raise HTTPException(422, "No valid credit rows found in the uploaded statement")
        return self.import_bank_statement(society_id, rows, user)

    def import_bank_statement(self, society_id: UUID, rows: List[dict], user: User) -> List[BankStatementEntry]:
        entries = []
        for row in rows:
            entry = BankStatementEntry(
                society_id=society_id, imported_by=user.id,
                txn_date=row["txn_date"], description=row["description"],
                reference=row.get("reference"), amount=row["amount"],
            )
            self.db.add(entry)
            entries.append(entry)
        self.db.flush()
        for e in entries:
            self._audit(AuditAction.CREATE, e, "BankStatementEntry", user,
                        new_values={"amount": str(e.amount), "date": e.txn_date.isoformat()})
        self.db.commit()
        for e in entries:
            self.db.refresh(e)
        return entries

    def list_bank_statement_entries(self, society_id: UUID, match_status: Optional[BankStatementMatchStatus] = None,
                                     skip=0, limit=100) -> List[BankStatementEntry]:
        return self.bank_statement_repo.get_by_society(society_id, match_status=match_status, skip=skip, limit=limit)

    def get_bank_statement_entry(self, entry_id: UUID) -> BankStatementEntry:
        e = self.bank_statement_repo.get(entry_id)
        if not e: raise HTTPException(404, "Bank statement entry not found")
        return e

    def suggest_matches(self, entry_id: UUID) -> List[OnlinePaymentSubmission]:
        """Candidate PENDING submissions for this entry: same society, exact
        amount match, payment_date within MATCH_DATE_WINDOW_DAYS of the
        statement date. Amount must match exactly — reconciliation is not
        the place to guess at partial/rounded amounts."""
        from datetime import timedelta
        entry = self.get_bank_statement_entry(entry_id)
        window_start = entry.txn_date - timedelta(days=self.MATCH_DATE_WINDOW_DAYS)
        window_end   = entry.txn_date + timedelta(days=self.MATCH_DATE_WINDOW_DAYS)
        return self.db.query(OnlinePaymentSubmission).filter(
            OnlinePaymentSubmission.society_id==entry.society_id,
            OnlinePaymentSubmission.status==ReconciliationStatus.PENDING,
            OnlinePaymentSubmission.amount==entry.amount,
            OnlinePaymentSubmission.payment_date>=window_start,
            OnlinePaymentSubmission.payment_date<=window_end,
            OnlinePaymentSubmission.is_active==True,
        ).order_by(OnlinePaymentSubmission.payment_date.asc()).all()

    def confirm_bank_match(self, entry_id: UUID, submission_id: UUID, user: User) -> BankStatementEntry:
        entry = self.get_bank_statement_entry(entry_id)
        if entry.match_status != BankStatementMatchStatus.UNMATCHED:
            raise HTTPException(409, f"Entry is already {entry.match_status.value}")
        submission = self.get_online_payment_submission(submission_id)
        if submission.society_id != entry.society_id:
            raise HTTPException(400, "Payment submission belongs to a different society")
        if submission.status != ReconciliationStatus.PENDING:
            raise HTTPException(409, f"Payment is already {submission.status.value}, not pending")
        if submission.amount != entry.amount:
            raise HTTPException(422, "Amount mismatch between bank entry and payment submission")

        now = datetime.utcnow()
        entry.match_status = BankStatementMatchStatus.MATCHED
        entry.matched_submission_id = submission.id
        entry.matched_by = user.id
        entry.matched_at = now

        submission.status = ReconciliationStatus.RECONCILED
        submission.reviewed_by = user.id
        submission.reviewed_at = now

        self._audit(AuditAction.UPDATE, entry, "BankStatementEntry", user,
                    new_values={"matched_submission": submission.receipt_number, "amount": str(entry.amount)})
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def ignore_bank_entry(self, entry_id: UUID, reason: Optional[str], user: User) -> BankStatementEntry:
        entry = self.get_bank_statement_entry(entry_id)
        if entry.match_status != BankStatementMatchStatus.UNMATCHED:
            raise HTTPException(409, f"Entry is already {entry.match_status.value}")
        entry.match_status = BankStatementMatchStatus.IGNORED
        entry.ignore_reason = reason
        entry.matched_by = user.id
        entry.matched_at = datetime.utcnow()
        self._audit(AuditAction.UPDATE, entry, "BankStatementEntry", user,
                    new_values={"ignored": True, "reason": reason})
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def generate_online_payment_receipt_pdf(self, submission_id: UUID) -> bytes:
        from app.modules.billing.services.receipt_pdf import generate_online_payment_receipt_pdf
        submission = self.get_online_payment_submission(submission_id)
        society_name = submission.society.name if submission.society else "Society"
        return generate_online_payment_receipt_pdf(submission, society_name)
