"""
BillingService — maintenance billing workflow engine.

Workflow:
  Create FinancialPeriod → Create BillingCycle → Generate Bills per flat
  → Issue Bills → Record Payment → Update DueTracker → Generate Receipt
"""
import json
import re
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.billing.models.billing import (
    FinancialPeriod, MaintenanceChargeConfig, BillingCycle,
    MaintenanceBill, InvoiceLineItem, PaymentReceipt, DueTracker, PenaltyRule, FlatCharge, FlatChargeStatus,
    OnlinePaymentSubmission, ReconciliationStatus,
    BankStatementEntry, BankStatementMatchStatus,
    BillStatus, ChargeType, PaymentMode, ChargeBasis, MaintenanceSettings,
    MaintenanceElement, BillingExpenseAllocation, BillingExpenseSource,
)
from app.modules.billing.repositories.billing_repo import (
    FinancialPeriodRepo, ChargeConfigRepo, BillingCycleRepo,
    MaintenanceBillRepo, PaymentReceiptRepo, DueTrackerRepo, PenaltyRuleRepo,
    OnlinePaymentSubmissionRepo, BankStatementEntryRepo,
)
from app.models.flat import Flat
from app.models.wing import Wing
from app.models.resident import Resident
from app.modules.billing.services.bill_pdf import generate_bills_pdf, generate_maintenance_bill_pdf
from app.modules.billing.services.receipt_pdf import generate_payment_receipt_pdf
from app.modules.billing.services.maintenance_calculator import MaintenanceCalculator, default_settings
from app.modules.billing.services.period_expenses import (
    EXPENSE_MODES, MODE_PERIOD, PERIOD_BASES, is_period_head, overlapping_allocations,
)
from app.modules.billing.services.standard_elements import seed_standard_elements
from app.models.user import User
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel

ALLOWED_SCREENSHOT_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024  # 8 MB

RESIDENT_VISIBLE_BILL_STATUSES = (
    BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE,
)


def _flat_sort_key(number: str) -> tuple:
    """101 before 1001, 2A before 10: digits compare as numbers."""
    parts = re.findall(r"\d+|\D+", str(number or ""))
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in parts)


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

    @property
    def postings(self):
        """The society's books — every issued bill, cancellation and payment
        is posted to the accounts as it happens (see accounts/services/postings.py)."""
        if not hasattr(self, "_postings"):
            from app.modules.accounts.services.postings import AccountPostings
            self._postings = AccountPostings(self.db)
        return self._postings

    def _post(self, hook: str, *args) -> None:
        self.postings.run(hook, *args)

    @property
    def allocator(self):
        """Sets members' payments off against their open bills (see
        services/allocations.py)."""
        if not hasattr(self, "_allocator"):
            from app.modules.billing.services.allocations import PaymentAllocator
            self._allocator = PaymentAllocator(self.db, self)
        return self._allocator

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="billing",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Financial Periods ─────────────────────────────────────────────────────

    def create_period(self, data: dict, user: User) -> FinancialPeriod:
        assert_society_access(user, data.get("society_id"))
        period = FinancialPeriod(**data)
        return self.period_repo.create(period)

    def close_period(self, period_id: UUID, user: User) -> FinancialPeriod:
        p = self.period_repo.get(period_id)
        if not p: raise HTTPException(404, "Period not found")
        assert_society_access(user, p.society_id)
        if p.is_closed: raise HTTPException(409, "Period already closed")
        p.is_closed = True; p.closed_by = user.id
        self.db.commit(); self.db.refresh(p)
        return p

    def list_periods(self, society_id: UUID) -> List[FinancialPeriod]:
        return self.period_repo.get_by_society(society_id)

    # ── Charge Configuration ──────────────────────────────────────────────────

    @staticmethod
    def _sync_basis(data: dict) -> dict:
        """`is_per_sqft` predates `basis`; accept either and keep both
        columns consistent."""
        if data.get("basis") is not None:
            data["is_per_sqft"] = data["basis"] == ChargeBasis.PER_SQFT
        elif data.get("is_per_sqft") is not None:
            data["basis"] = ChargeBasis.PER_SQFT if data["is_per_sqft"] else ChargeBasis.FIXED
        return data

    def create_charge_config(self, data: dict, user: User) -> MaintenanceChargeConfig:
        assert_society_access(user, data.get("society_id"))
        data = {k: v for k, v in data.items() if v is not None}
        if data.get("element_id"):
            element = self.get_element(data["element_id"])
            if element.society_id != data["society_id"]:
                raise HTTPException(422, "That element belongs to a different society")
            for key, value in self._element_defaults(element).items():
                data.setdefault(key, value)
        if not data.get("charge_type") or not data.get("name"):
            raise HTTPException(422, "Pick an element, or give the charge head a type and name")
        data = self._sync_basis(data)
        self._check_auto_budget(data.get("auto_from_expenses"), data.get("element_id"), data.get("basis"),
                                data.get("expense_mode"))
        self._check_one_auto_head(data["society_id"], data.get("auto_from_expenses"), data.get("element_id"))
        self._check_two_wheeler(data.get("two_wheeler_rate"), data.get("basis"))
        config = MaintenanceChargeConfig(**data)
        self.charge_repo.create(config)
        self._audit(AuditAction.CREATE, config, "ChargeConfig", user,
                    new_values={"name": data.get("name"), "amount": str(data.get("default_amount"))})
        self.db.refresh(config)
        return config

    @staticmethod
    def _check_two_wheeler(rate, basis):
        """A separate two-wheeler rate belongs to a parking head, which charges per allotted slot."""
        if rate is not None and (basis or ChargeBasis.FIXED) != ChargeBasis.PARKING:
            raise HTTPException(422, "A two-wheeler rate is only for a parking charge head")

    @staticmethod
    def _check_auto_budget(auto, element_id, basis, mode=None):
        """"Budget from expenses" needs an element whose linked ledgers supply
        the spend, and a basis that can be worked out from spend. The mode is "trailing" (the last N months,
        annualised) or "period" (the cycle's own approved expenses, shared out exactly - fixed, per sq ft and the
        two budget bases only)."""
        if mode is not None and mode not in EXPENSE_MODES:
            raise HTTPException(422, "Expense mode must be 'trailing' or 'period'")
        if not auto:
            return
        from app.modules.billing.services.budget_suggestions import SUGGESTIBLE_BASES
        if not element_id:
            raise HTTPException(422, "Budget from expenses needs a charge head made from a maintenance element")
        if (basis or ChargeBasis.FIXED) not in SUGGESTIBLE_BASES:
            raise HTTPException(422, "Budget from expenses works for fixed, per sq ft and budget-based charge heads")
        if mode == MODE_PERIOD and (basis or ChargeBasis.FIXED) not in PERIOD_BASES:
            raise HTTPException(422, "Actual expenses of the period work for fixed, per sq ft and budget-based "
                                     "charge heads")

    def _check_one_auto_head(self, society_id, auto, element_id, exclude_id=None):
        """Two heads that both take an element's expenses would each bill the whole spend - the members would pay it
        twice. One 'budget from expenses' head per element."""
        if not auto or not element_id:
            return
        q = self.db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.society_id == society_id, MaintenanceChargeConfig.element_id == element_id,
            MaintenanceChargeConfig.auto_from_expenses == True,  # noqa: E712
            MaintenanceChargeConfig.is_active == True)  # noqa: E712
        if exclude_id:
            q = q.filter(MaintenanceChargeConfig.id != exclude_id)
        other = q.first()
        if other is not None:
            raise HTTPException(422, f"“{other.name}” already bills this element's expenses. Turn that one off first - "
                                     "two heads would charge the same spend twice.")

    def bill_actual_expenses(self, society_id: UUID, charge_ids: List[UUID], user: User,
                             element_ids: Optional[List[UUID]] = None):
        """Put the chosen heads on 'actual expenses of each billing cycle'. Returns (changed heads, skipped as
        [{id, name, reason}]). `element_ids` names elements that have spend but no head: an element with no active
        head gets one made from its standard calculation; one that has a head has that head switched. One head per
        element: a head is skipped when another head already bills that element's expenses (or was chosen earlier
        in this same request)."""
        assert_society_access(user, society_id)
        charge_ids = list(charge_ids)
        skipped = []
        for eid in (element_ids or []):
            el = self.get_element(eid)
            if el.society_id != society_id or not el.is_active:
                skipped.append({"id": str(eid), "name": "", "reason": "Not an active element of this society"})
                continue
            existing = self.db.query(MaintenanceChargeConfig).filter(
                MaintenanceChargeConfig.society_id == society_id, MaintenanceChargeConfig.element_id == el.id,
                MaintenanceChargeConfig.is_active == True).order_by(  # noqa: E712
                MaintenanceChargeConfig.auto_from_expenses.desc(), MaintenanceChargeConfig.created_at).first()
            if existing is not None:
                charge_ids.append(existing.id)
                continue
            if (el.default_basis or ChargeBasis.FIXED) not in PERIOD_BASES:
                skipped.append({"id": str(el.id), "name": el.name,
                                "reason": "Its standard calculation is not spend-based (percentage of construction "
                                          "cost or parking), so a head for it cannot follow expenses"})
                continue
            data = self._sync_basis({**self._element_defaults(el), "auto_from_expenses": True,
                                     "expense_mode": MODE_PERIOD})
            head = MaintenanceChargeConfig(**data, society_id=society_id, element_id=el.id)
            self.db.add(head)
            self.db.flush()
            self._audit(AuditAction.CREATE, head, "ChargeConfig", user,
                        new_values={"name": head.name, "expense_mode": MODE_PERIOD})
            charge_ids.append(head.id)
        heads = {c.id: c for c in self.db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.society_id == society_id, MaintenanceChargeConfig.id.in_(charge_ids))}
        taken = {}                                         # element id -> head already billing its expenses
        for c in self.db.query(MaintenanceChargeConfig).filter(
                MaintenanceChargeConfig.society_id == society_id, MaintenanceChargeConfig.is_active == True,  # noqa: E712
                MaintenanceChargeConfig.auto_from_expenses == True):  # noqa: E712
            taken[c.element_id] = c
        changed, seen = [], set()
        for cid in charge_ids:
            if cid in seen:
                continue
            seen.add(cid)
            c = heads.get(cid)
            if c is None:
                skipped.append({"id": str(cid), "name": "", "reason": "Not a charge head of this society"})
                continue
            reason = None
            if not c.is_active:
                reason = "This head is switched off"
            elif not c.element_id:
                reason = "Not made from a maintenance element, so there are no expenses to follow"
            elif (c.basis or ChargeBasis.FIXED) not in PERIOD_BASES:
                reason = "Its basis is not spend-based (percentage of construction cost or parking)"
            elif taken.get(c.element_id) is not None and taken[c.element_id].id != c.id:
                reason = f"“{taken[c.element_id].name}” already bills this element's expenses"
            if reason:
                skipped.append({"id": str(c.id), "name": c.name, "reason": reason})
                continue
            if not (c.auto_from_expenses and c.expense_mode == MODE_PERIOD):
                c.auto_from_expenses, c.expense_mode = True, MODE_PERIOD
                self._audit(AuditAction.UPDATE, c, "ChargeConfig", user,
                            new_values={"auto_from_expenses": "True", "expense_mode": MODE_PERIOD})
            taken[c.element_id] = c
            changed.append(c)
        self.db.commit()
        for c in changed:
            self.db.refresh(c)
        return changed, skipped

    def list_charge_configs(self, society_id: UUID) -> List[MaintenanceChargeConfig]:
        return self.charge_repo.get_by_society(society_id)

    def update_charge_config(self, config_id: UUID, data: dict, user: User) -> MaintenanceChargeConfig:
        # Only affects bills generated afterwards — existing bills keep their
        # own InvoiceLineItem copies of the rate/tax at generation time.
        config = self.db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.id == config_id).first()
        if not config: raise HTTPException(404, "Charge head not found")
        assert_society_access(user, config.society_id)
        old = {"name": config.name, "amount": str(config.default_amount), "active": config.is_active}
        data = self._sync_basis(dict(data))
        auto_after = data.get("auto_from_expenses", config.auto_from_expenses)
        self._check_auto_budget(auto_after, config.element_id, data.get("basis", config.basis),
                                data.get("expense_mode", config.expense_mode))
        if "auto_from_expenses" in data or "expense_mode" in data:
            self._check_one_auto_head(config.society_id, auto_after, config.element_id, exclude_id=config.id)
        new_basis = data.get("basis", config.basis) or ChargeBasis.FIXED
        self._check_two_wheeler(data.get("two_wheeler_rate"), new_basis)
        if new_basis != ChargeBasis.PARKING:
            data["two_wheeler_rate"] = None                # a head that leaves parking drops its two-wheeler rate
        for field, value in data.items():
            setattr(config, field, value)
        self._audit(AuditAction.UPDATE, config, "ChargeConfig", user, old_values=old,
                    new_values={k: str(v) for k, v in data.items()})
        self.db.commit(); self.db.refresh(config)
        return config

    # ── Maintenance element master ────────────────────────────────────────────

    @staticmethod
    def _element_defaults(element: MaintenanceElement) -> dict:
        return {
            "charge_type": element.category, "name": element.name,
            "basis": element.default_basis, "default_amount": element.default_amount,
            "is_service_charge": element.is_service_charge,
            "gst_applicable": element.gst_applicable,
        }

    def list_elements(self, society_id: UUID, include_inactive: bool = False) -> List[MaintenanceElement]:
        """The first read for a society seeds the standard bye-law elements,
        so every society starts with a ready-made master."""
        q = self.db.query(MaintenanceElement).filter(MaintenanceElement.society_id == society_id)
        if q.count() == 0:
            seed_standard_elements(self.db, society_id)
            self.db.commit()
        if not include_inactive:
            q = q.filter(MaintenanceElement.is_active == True)
        return q.order_by(MaintenanceElement.sort_order, MaintenanceElement.name).all()

    def get_element(self, element_id: UUID) -> MaintenanceElement:
        el = self.db.query(MaintenanceElement).filter(MaintenanceElement.id == element_id).first()
        if not el: raise HTTPException(404, "Maintenance element not found")
        return el

    def create_element(self, data: dict, user: User) -> MaintenanceElement:
        society_id = data["society_id"]
        assert_society_access(user, society_id)
        self.list_elements(society_id)  # make sure the standard set exists first
        existing = self.db.query(MaintenanceElement).filter(MaintenanceElement.society_id == society_id).all()
        base = re.sub(r"[^a-z0-9]+", "_", data["name"].lower()).strip("_")[:40] or "element"
        codes = {e.code for e in existing}
        code, n = base, 2
        while code in codes:
            code, n = f"{base}_{n}", n + 1
        data = {k: v for k, v in data.items() if v is not None}
        data.setdefault("sort_order", max((e.sort_order for e in existing), default=0) + 10)
        el = MaintenanceElement(**data, code=code, is_system=False)
        self.db.add(el)
        self.db.flush()
        self._audit(AuditAction.CREATE, el, "MaintenanceElement", user, new_values={"name": el.name})
        self.db.commit(); self.db.refresh(el)
        return el

    def update_element(self, element_id: UUID, data: dict, user: User) -> MaintenanceElement:
        el = self.get_element(element_id)
        assert_society_access(user, el.society_id)
        for field, value in data.items():
            setattr(el, field, value)
        self._audit(AuditAction.UPDATE, el, "MaintenanceElement", user,
                    new_values={k: str(v) for k, v in data.items()})
        self.db.commit(); self.db.refresh(el)
        return el

    def create_charges_from_elements(self, society_id: UUID, items: List[dict],
                                      user: User) -> List[MaintenanceChargeConfig]:
        assert_society_access(user, society_id)
        """Bulk "load standard charge heads": one charge head per chosen
        element, using the element's defaults unless an amount is given.
        Elements that already have an active charge head are skipped."""
        in_use = {c.element_id for c in self.charge_repo.get_by_society(society_id) if c.element_id}
        to_create, missing = [], []
        for item in items:
            el = self.get_element(item["element_id"])
            if el.society_id != society_id or not el.is_active:
                raise HTTPException(422, f"'{el.name}' is not an active element of this society")
            if el.id in in_use:
                continue
            amount = item.get("amount") if item.get("amount") is not None else el.default_amount
            if amount is None:
                missing.append(el.name)
            else:
                to_create.append((el, amount))
                in_use.add(el.id)
        if missing:
            raise HTTPException(422, "Enter an amount for: " + ", ".join(missing))

        created = []
        for el, amount in to_create:
            data = self._sync_basis({**self._element_defaults(el), "default_amount": amount})
            config = MaintenanceChargeConfig(**data, society_id=society_id, element_id=el.id)
            self.db.add(config)
            created.append(config)
        self.db.flush()
        for c in created:
            self._audit(AuditAction.CREATE, c, "ChargeConfig", user,
                        new_values={"name": c.name, "amount": str(c.default_amount)})
        self.db.commit()
        for c in created:
            self.db.refresh(c)
        return created

    # ── Billing Cycle ─────────────────────────────────────────────────────────

    def create_cycle(self, data: dict, user: User, request=None) -> BillingCycle:
        assert_society_access(user, data.get("society_id"))
        cycle = BillingCycle(**data, created_by=user.id)
        self.cycle_repo.create(cycle)
        self._audit(AuditAction.CREATE, cycle, "BillingCycle", user, request,
                    new_values={"name": data.get("name"), "due_date": str(data.get("due_date"))})
        self.db.refresh(cycle)
        return cycle

    def list_cycles(self, society_id: UUID) -> List[BillingCycle]:
        return self.cycle_repo.get_by_society(society_id)

    # ── Bill Generation ───────────────────────────────────────────────────────

    def _period_overlaps(self, calc: MaintenanceCalculator, cycle: BillingCycle) -> List[str]:
        """Period-expense heads whose dates overlap a period another cycle has already billed (its bills still
        stand): the same days' expenses would be charged twice. Checked on the dates alone, so it holds whether or
        not anything has been spent in the overlap yet."""
        out = []
        for charge in (c for c in calc.charges if is_period_head(c)):
            for prior in overlapping_allocations(self.db, cycle.society_id, charge.element_id,
                                                 cycle.cycle_start, cycle.cycle_end, cycle.id):
                prior_cycle = self.db.get(BillingCycle, prior.cycle_id)
                out.append(
                    f"{charge.name}: the expenses of {prior.period_start:%d %b %Y} – {prior.period_end:%d %b %Y} "
                    f"were already billed in “{prior_cycle.name if prior_cycle else 'another cycle'}”.")
        return out

    def generate_bills_for_cycle(self, cycle_id: UUID, user: User,
                                  request=None) -> List[MaintenanceBill]:
        """
        Generate one MaintenanceBill per flat for a billing cycle.
        Uses active charge configs for the society.
        Prevents duplicate generation.
        """
        cycle = self.cycle_repo.get(cycle_id)
        if not cycle: raise HTTPException(404, "Billing cycle not found")
        assert_society_access(user, cycle.society_id)
        if cycle.is_finalized:
            raise HTTPException(409, "Billing cycle already finalized")

        # Check already generated
        existing = self.bill_repo.get_by_cycle(cycle_id)
        if existing:
            raise HTTPException(409, f"Bills already generated for this cycle ({len(existing)} bills)")

        calc = MaintenanceCalculator(self.db, cycle.society_id)
        if not calc.charges:
            raise HTTPException(422, "No charge configs found for this society. Add charges first.")
        if not calc.flats:
            raise HTTPException(422, "No active flats found for this society")

        today = date.today()
        drafts = calc.calculate(cycle, today)
        overlaps = self._period_overlaps(calc, cycle)
        if overlaps:
            raise HTTPException(409, "These expenses are already billed - " + " ".join(overlaps))
        if not drafts:
            raise HTTPException(422, "Nothing to bill: " + " ".join(calc.warnings))

        # The working of each period-expense head is kept with the bills: what was in the pool, how it was shared and
        # the rate, so a line on a bill can always be traced back and re-added.
        allocation_rows = self._record_allocations(calc, cycle, drafts)

        bills = []
        for draft in drafts:
            flat = draft.flat
            resident = self.db.query(Resident).filter(
                Resident.flat_id == flat.id, Resident.is_active == True,
            ).order_by(Resident.is_primary.desc()).first()
            bill = MaintenanceBill(
                society_id=cycle.society_id, cycle_id=cycle_id,
                flat_id=flat.id, generated_by=user.id,
                resident_id=resident.id if resident else None,
                invoice_number=self.bill_repo.next_invoice_number(cycle.society_id),
                bill_status=BillStatus.GENERATED,
                bill_date=today, due_date=cycle.due_date,
                period_start=draft.period_start or cycle.cycle_start, period_end=draft.period_end or cycle.cycle_end,
                subtotal=draft.subtotal, tax_amount=draft.tax,
                total_amount=draft.total, outstanding=draft.total, round_off=draft.round_off,
                previous_dues=draft.previous_dues,
                interest_working=json.dumps(draft.interest_working) if draft.interest_working else None,
            )
            self.db.add(bill)
            self.db.flush()
            for l in draft.lines:
                if l.flat_charge_id:
                    # A one-off fine / additional charge is now on a bill; a recurring one stays active.
                    fc = self.db.get(FlatCharge, l.flat_charge_id)
                    if fc is not None and not fc.recurring:
                        fc.status = FlatChargeStatus.BILLED
                        fc.bill_id = bill.id
                alloc_row = allocation_rows.get(l.allocation_charge_id) if l.allocation_charge_id else None
                self.db.add(InvoiceLineItem(
                    bill_id=bill.id, charge_type=l.charge_type, description=l.description,
                    quantity=1.0, unit_rate=l.amount, amount=l.amount,
                    tax_percent=l.tax_percent, tax_amount=l.tax_amount, total=l.total,
                    allocation_id=alloc_row.id if alloc_row is not None else None,
                ))
            for earlier in draft.interest_bills:
                earlier.arrears_interest_upto = today

            tracker = self.due_repo.get_or_create(flat.id, cycle.society_id)
            tracker.total_billed  += bill.total_amount
            tracker.outstanding   += bill.total_amount
            tracker.last_bill_date = today
            bills.append(bill)

        cycle.is_finalized          = True
        cycle.total_flats_billed    = len(bills)
        cycle.total_amount_generated = sum(b.total_amount for b in bills)

        self._audit(AuditAction.CREATE, cycle, "BillingCycle", user, request,
                    new_values={"bills_generated": len(bills),
                                "total": str(cycle.total_amount_generated)})
        self.db.commit()
        return bills

    def _record_allocations(self, calc: MaintenanceCalculator, cycle: BillingCycle, drafts) -> dict:
        """Write the snapshot of every period-expense head (the pool, its vouchers, the method, the rate) and prove
        that the lines on the bills add up to the pool to the paisa; if they do not, nothing is written."""
        rows = {}
        for charge_id, alloc in calc.allocations.items():
            lines = [l.amount for d in drafts for l in d.lines if l.allocation_charge_id == charge_id]
            allocated = sum(lines, Decimal(0))
            if allocated != alloc.pool:
                raise HTTPException(500, f"{alloc.charge.name}: the shares (₹{allocated}) do not add up to the "
                                         f"expenses (₹{alloc.pool}); nothing was generated.")
            row = BillingExpenseAllocation(
                society_id=cycle.society_id, cycle_id=cycle.id, charge_id=charge_id,
                element_id=alloc.charge.element_id, charge_name=alloc.charge.name, element_name=alloc.element_name,
                method=alloc.method, period_start=alloc.period_start, period_end=alloc.period_end,
                pool_amount=alloc.pool, allocated_amount=allocated, eligible_flats=len(lines),
                total_weight=alloc.total_weight, rate=alloc.rate,
            )
            row.sources = [BillingExpenseSource(
                voucher_id=s.voucher_id, account_id=s.account_id, voucher_number=s.voucher_number,
                voucher_date=s.voucher_date, ledger_name=s.ledger_name, amount=s.amount) for s in alloc.sources]
            self.db.add(row)
            rows[charge_id] = row
        if rows:
            self.db.flush()
        return rows

    def _issue(self, bill: MaintenanceBill, user: User, request=None) -> None:
        bill.bill_status = BillStatus.ISSUED
        bill.issued_at   = datetime.utcnow()
        self._post("post_bill", bill, user)
        # An advance the member has paid is set off against the new bill.
        self.db.flush()
        self.allocator.apply_credit(bill.flat_id, user)

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
        assert_society_access(user, bill.society_id)
        if bill.bill_status != BillStatus.GENERATED:
            raise HTTPException(409, f"Bill cannot be issued (status: {bill.bill_status.value})")
        self._issue(bill, user, request)
        self.db.commit()
        self.db.refresh(bill)
        return bill

    def issue_all_bills(self, cycle_id: UUID, user: User, request=None) -> int:
        cycle = self.cycle_repo.get(cycle_id)
        if not cycle: raise HTTPException(404, "Billing cycle not found")
        assert_society_access(user, cycle.society_id)
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

    def preview_cycle(self, cycle_id: UUID) -> MaintenanceCalculator:
        """Dry run of generate_bills_for_cycle — nothing is written."""
        cycle = self.get_cycle(cycle_id)
        calc = MaintenanceCalculator(self.db, cycle.society_id)
        calc.drafts = calc.calculate(cycle, date.today())
        calc.cycle = cycle
        calc.warnings.extend(self._period_overlaps(calc, cycle))
        return calc

    # ── Maintenance rules ─────────────────────────────────────────────────────

    def get_maintenance_settings(self, society_id: UUID) -> MaintenanceSettings:
        return self.db.query(MaintenanceSettings).filter(
            MaintenanceSettings.society_id == society_id).first() or default_settings(society_id)

    def update_maintenance_settings(self, society_id: UUID, data: dict, user: User) -> MaintenanceSettings:
        assert_society_access(user, society_id)
        if "auto_approve_admin_expenses" in data:
            from app.core.dependencies import _user_has_permission
            if not _user_has_permission(user, "admin_committee"):
                raise HTTPException(403, "Only an admin or committee member can change who approves payments")
        settings = self.db.query(MaintenanceSettings).filter(
            MaintenanceSettings.society_id == society_id).first()
        if not settings:
            settings = default_settings(society_id)
            self.db.add(settings)
        for field, value in data.items():
            setattr(settings, field, value)
        self.db.flush()
        self._audit(AuditAction.UPDATE, settings, "MaintenanceSettings", user,
                    new_values={k: str(v) for k, v in data.items()})
        self.db.commit(); self.db.refresh(settings)
        return settings

    def cancel_bill(self, bill_id: UUID, reason: str, user: User) -> MaintenanceBill:
        bill = self.bill_repo.get(bill_id)
        if not bill: raise HTTPException(404, "Bill not found")
        assert_society_access(user, bill.society_id)
        if bill.bill_status == BillStatus.PAID:
            raise HTTPException(409, "Cannot cancel a paid bill")

        # Payments set off against it go back to the member's credit
        self.allocator.release_bill(bill, f"Bill {bill.invoice_number} cancelled: {reason}", user)

        # Reverse due tracker
        tracker = self.due_repo.get_by_flat(bill.flat_id)
        if tracker:
            tracker.total_billed -= bill.total_amount
            tracker.outstanding  -= bill.outstanding

        # One-off fines / charges that were on this bill go back to waiting for the next one
        for fc in self.db.query(FlatCharge).filter(FlatCharge.bill_id == bill.id,
                                                   FlatCharge.status == FlatChargeStatus.BILLED):
            fc.status = FlatChargeStatus.ACTIVE
            fc.bill_id = None

        bill.bill_status        = BillStatus.CANCELLED
        bill.cancelled_at       = datetime.utcnow()
        bill.cancellation_reason = reason
        self._post("cancel_bill", bill, user)
        self.db.flush()
        self.allocator.apply_credit(bill.flat_id, user)
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
        assert_society_access(user, bill.society_id)
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
        self._post("post_receipt", receipt, user)

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

    def generate_bill_pdf(self, bill_id: UUID, with_receipts: bool = True) -> bytes:
        bill = self.get_bill(bill_id)
        return generate_maintenance_bill_pdf(bill, self.get_maintenance_settings(bill.society_id),
                                             **self._bill_print_context(bill, with_receipts=with_receipts))

    def generate_cycle_bills_pdf(self, cycle_id: UUID, wing_id: Optional[UUID] = None,
                                 status: Optional[str] = None, with_receipts: bool = True) -> tuple:
        """Every bill of a cycle in one PDF, a bill to a page (more where a bill runs on), flat by flat in wing
        order — what a society prints and hands round. Cancelled bills are left out unless asked for with `status`.
        Returns (pdf bytes, number of bills)."""
        cycle = self.get_cycle(cycle_id)
        bills = self.list_cycle_bills(cycle_id)
        if status:
            try:
                wanted = BillStatus(status)
            except ValueError:
                raise HTTPException(400, "Unknown bill status")
            bills = [b for b in bills if b.bill_status == wanted]
        else:
            bills = [b for b in bills if b.bill_status != BillStatus.CANCELLED]
        if wing_id:
            bills = [b for b in bills if b.flat is not None and b.flat.wing_id == wing_id]
        if not bills:
            raise HTTPException(404, "There are no bills to print for this selection")
        bills.sort(key=lambda b: (b.flat.wing.name if b.flat and b.flat.wing else "",
                                  _flat_sort_key(b.flat.flat_number if b.flat else "")))
        settings = self.get_maintenance_settings(cycle.society_id)
        heads = self._element_heads(cycle.society_id)
        items = [{"bill": b, "settings": settings, **self._bill_print_context(b, heads, with_receipts)} for b in bills]
        society = bills[0].society
        author = (society.name if society else None) or "Society"
        return generate_bills_pdf(items, title=f"Maintenance bills — {cycle.name}", author=author), len(bills)

    def _element_heads(self, society_id: UUID) -> dict:
        """{charge head name: standard element code} for a society."""
        rows = (
            self.db.query(MaintenanceChargeConfig.name, MaintenanceElement.code)
            .join(MaintenanceElement, MaintenanceElement.id == MaintenanceChargeConfig.element_id)
            .filter(MaintenanceChargeConfig.society_id == society_id)
            .all()
        )
        return {name: code for name, code in rows}

    def _bill_print_context(self, bill: MaintenanceBill, heads: Optional[dict] = None,
                            with_receipts: bool = True) -> dict:
        """What the printed bill needs beyond the bill itself: which standard
        element each charge head came from (decides the bill head it's shown
        under), the unpaid interest inside the arrears, and the flat's
        previous bill (its receipts are listed at the foot, unless `with_receipts` is off)."""
        if heads is None:
            heads = self._element_heads(bill.society_id)
        earlier = (
            self.db.query(MaintenanceBill)
            .filter(MaintenanceBill.flat_id == bill.flat_id, MaintenanceBill.id != bill.id,
                    MaintenanceBill.cycle_id != bill.cycle_id, MaintenanceBill.is_active == True,
                    MaintenanceBill.bill_status != BillStatus.CANCELLED,
                    MaintenanceBill.bill_date <= bill.bill_date,
                    MaintenanceBill.created_at < bill.created_at)
            .order_by(MaintenanceBill.bill_date.desc(), MaintenanceBill.created_at.desc())
            .all()
        )
        # Interest is billed as a PENALTY line; what's still unpaid of it is
        # at most the bill's outstanding (payments settle the bill as a whole).
        interest = sum((
            min(Decimal(b.outstanding), sum((Decimal(li.total) for li in b.line_items
                                             if li.charge_type == ChargeType.PENALTY), Decimal(0)))
            for b in earlier if b.outstanding and b.outstanding > 0), Decimal(0))
        return {
            "element_codes": heads,
            "accumulated_interest": interest,
            "previous_bill": earlier[0] if earlier and with_receipts else None,
        }

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
        # The rule belongs to the caller's own society; a society named in the request is checked, never trusted.
        data["society_id"] = resolve_create_society_id(user, data.get("society_id"))
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
        deposit_account_id: Optional[UUID] = None,
    ) -> OnlinePaymentSubmission:
        flat = self.db.query(Flat).filter(Flat.id == flat_id, Flat.is_active == True).first()
        if not flat:
            raise HTTPException(404, "Flat not found")
        wing = self.db.query(Wing).filter(Wing.id == flat.wing_id).first()
        if not wing:
            raise HTTPException(404, "Wing not found for this flat")
        assert_society_access(user, wing.society_id)

        if amount <= 0:
            raise HTTPException(422, "Amount must be greater than zero")

        if deposit_account_id is not None:
            from app.modules.accounts.models.accounts import Account
            ledger = self.db.query(Account).filter(Account.id == deposit_account_id).first()
            if not ledger or ledger.society_id != wing.society_id or not ledger.is_active or not (
                    ledger.is_cash or ledger.is_bank):
                raise HTTPException(422, "Choose a cash or bank ledger of this society for the money to go into")
            if (payment_mode == PaymentMode.CASH) != bool(ledger.is_cash):
                raise HTTPException(422, "Cash goes into a cash ledger, and any other payment into a bank ledger")

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
            purpose=purpose, deposit_account_id=deposit_account_id,
            status=status,
            screenshot_data=screenshot_bytes, screenshot_mime_type=screenshot_mime_type,
            screenshot_file_name=screenshot_file_name,
        )
        self.db.add(submission)
        self.db.flush()

        # Against the chosen bill, or set off against the flat's open bills
        # oldest first; anything left is the member's advance.
        if bill is not None:
            self.allocator.allocate(submission, bill, amount, user)
            self.allocator._sync_advance(flat.id, user)
        else:
            self.allocator.apply_credit(flat.id, user)
        self._post("post_online_payment", submission, user)

        self._audit(AuditAction.CREATE, submission, "OnlinePaymentSubmission", user,
                    new_values={"amount": str(amount), "flat": flat.flat_number,
                                "receipt_number": receipt_number,
                                "bills": [a.bill.invoice_number for a in submission.allocations]})
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def get_online_payment_submission(self, submission_id: UUID, user: Optional[User] = None) -> OnlinePaymentSubmission:
        s = self.online_payment_repo.get(submission_id)
        if not s: raise HTTPException(404, "Payment submission not found")
        if user is not None:
            assert_society_access(user, s.society_id)
        return s

    def list_online_payment_submissions(self, society_id: UUID, status=None,
                                         wing_id=None, flat_id=None,
                                         skip=0, limit=50) -> List[OnlinePaymentSubmission]:
        return self.online_payment_repo.get_by_society(
            society_id, status=status, wing_id=wing_id, flat_id=flat_id, skip=skip, limit=limit)

    def update_online_payment_status(self, submission_id: UUID, status: ReconciliationStatus,
                                      review_notes: Optional[str], user: User) -> OnlinePaymentSubmission:
        submission = self.get_online_payment_submission(submission_id, user)
        was_rejected = submission.status == ReconciliationStatus.REJECTED
        submission.status = status
        if status == ReconciliationStatus.REJECTED and not was_rejected:
            # The bills it settled are unpaid again
            self.allocator.release_payment(
                submission, f"Payment {submission.receipt_number} rejected: {review_notes or ''}".strip(), user)
        elif was_rejected and status != ReconciliationStatus.REJECTED:
            self.db.flush()
            self.allocator.apply_credit(submission.flat_id, user)
        submission.reviewed_by = user.id
        submission.reviewed_at = datetime.utcnow()
        if review_notes is not None:
            submission.review_notes = review_notes
        self._post("online_payment_status_changed", submission, user)
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

    def import_bank_statement_csv(self, society_id: UUID, csv_text: str, user: User,
                                  include_debits: bool = False,
                                  bank_account_id: Optional[UUID] = None) -> List[BankStatementEntry]:
        assert_society_access(user, society_id)
        """Expects a header row with columns Date, Description, and either Amount or Debit / Credit columns, and
        optionally Reference (case-insensitive, any order) — a generic format the admin prepares from whatever their
        bank's own export looks like, since every bank's raw CSV differs. Date accepts YYYY-MM-DD or DD-MM-YYYY.

        With an Amount column, a positive amount is a credit and a negative one a debit. By default only credits are
        kept (resident payments are all that is reconciled against online payments); with include_debits, the
        statement's debits (cheques cleared, transfers paid out) are kept too, so they can be matched to the books'
        payments. Debit / Credit columns always give both. `bank_account_id` names the society's bank ledger the
        statement belongs to."""
        import csv, io
        from decimal import InvalidOperation

        if bank_account_id is not None:
            from app.modules.accounts.services.bank_reconciliation import BankReconciliationService
            BankReconciliationService(self.db).bank_account(society_id, bank_account_id)

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise HTTPException(422, "CSV has no header row")
        columns = {f.strip().lower(): f for f in reader.fieldnames if f}
        split = "amount" not in columns and ("debit" in columns or "credit" in columns)
        missing = [c for c in ("date", "description") if c not in columns] + (
            [] if "amount" in columns or split else ["amount"])
        if missing:
            raise HTTPException(
                422,
                f"CSV missing required column(s): {', '.join(missing)}. "
                "Expected headers: Date, Description, Amount (or Debit and Credit), and optionally Reference.",
            )

        def number(raw: str, i: int, label: str) -> Decimal:
            raw = (raw or "").strip().replace(",", "")
            if not raw:
                return Decimal(0)
            try:
                return Decimal(raw)
            except InvalidOperation:
                raise HTTPException(422, f"Row {i}: unrecognized {label} {raw!r}")

        rows = []
        for i, raw in enumerate(reader, start=2):  # row 1 is the header
            date_str   = (raw.get(columns["date"]) or "").strip()
            desc       = (raw.get(columns["description"]) or "").strip()
            ref        = (raw.get(columns["reference"]) or "").strip() if "reference" in columns else ""
            amount_cells = ([raw.get(columns[c]) for c in ("debit", "credit") if c in columns] if split
                            else [raw.get(columns["amount"])])
            if not date_str and not any((c or "").strip() for c in amount_cells):
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
            if split:
                debit = number(raw.get(columns["debit"]) if "debit" in columns else "", i, "debit")
                credit = number(raw.get(columns["credit"]) if "credit" in columns else "", i, "credit")
                amount, direction = (credit, "credit") if credit > 0 else (debit, "debit")
            else:
                signed = number(raw.get(columns["amount"]), i, "amount")
                amount, direction = (signed, "credit") if signed > 0 else (-signed, "debit")
            if amount <= 0:
                continue  # an empty row — nothing to reconcile against
            if direction == "debit" and not (include_debits or split):
                continue  # a withdrawal: not a resident payment
            rows.append({
                "txn_date": txn_date,
                "description": desc or "(no description)",
                "reference": ref or None,
                "amount": amount,
                "direction": direction,
                "bank_account_id": bank_account_id,
            })

        if not rows:
            raise HTTPException(422, "No valid credit rows found in the uploaded statement")
        return self.import_bank_statement(society_id, rows, user)

    def import_bank_statement(self, society_id: UUID, rows: List[dict], user: User) -> List[BankStatementEntry]:
        assert_society_access(user, society_id)
        entries = []
        for row in rows:
            entry = BankStatementEntry(
                society_id=society_id, imported_by=user.id,
                txn_date=row["txn_date"], description=row["description"],
                reference=row.get("reference"), amount=row["amount"],
                direction=row.get("direction") or "credit", bank_account_id=row.get("bank_account_id"),
            )
            self.db.add(entry)
            entries.append(entry)
        self.db.flush()
        for e in entries:
            self._audit(AuditAction.CREATE, e, "BankStatementEntry", user,
                        new_values={"amount": str(e.amount), "date": e.txn_date.isoformat(),
                                    "direction": e.direction})
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

    def suggest_matches(self, entry_id: UUID, user: Optional[User] = None) -> List[OnlinePaymentSubmission]:
        """Candidate PENDING submissions for this entry: same society, exact
        amount match, payment_date within MATCH_DATE_WINDOW_DAYS of the
        statement date. Amount must match exactly — reconciliation is not
        the place to guess at partial/rounded amounts."""
        from datetime import timedelta
        entry = self.get_bank_statement_entry(entry_id)
        if user is not None:
            assert_society_access(user, entry.society_id)
        if entry.direction != "credit":
            return []                  # a payment the bank made is never a resident's payment
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
        assert_society_access(user, entry.society_id)
        if entry.match_status != BankStatementMatchStatus.UNMATCHED:
            raise HTTPException(409, f"Entry is already {entry.match_status.value}")
        if entry.direction != "credit":
            raise HTTPException(422, "Only money the bank received can be matched to a resident's payment")
        submission = self.get_online_payment_submission(submission_id, user)
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
        # The money is in the bank: the same line of the books is cleared on the bank reconciliation statement
        from app.modules.accounts.services.bank_reconciliation import BankReconciliationService
        account_id = BankReconciliationService(self.db).clear_for_source(
            "online_payment", submission.id, entry.txn_date, user)
        if entry.bank_account_id is None:
            entry.bank_account_id = account_id

        self._audit(AuditAction.UPDATE, entry, "BankStatementEntry", user,
                    new_values={"matched_submission": submission.receipt_number, "amount": str(entry.amount)})
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def ignore_bank_entry(self, entry_id: UUID, reason: Optional[str], user: User) -> BankStatementEntry:
        entry = self.get_bank_statement_entry(entry_id)
        assert_society_access(user, entry.society_id)
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
        return generate_payment_receipt_pdf(self.get_online_payment_submission(submission_id))

    def get_payment_by_receipt_number(self, receipt_number: str, society_id: Optional[UUID] = None):
        """The payment a receipt number belongs to — a PaymentReceipt, or an
        OnlinePaymentSubmission from the Record Payment form. Receipt numbers run per society (every society has an
        RCP-2026-00001), so a society-confined caller's lookup is confined to their own society."""
        r = self.db.query(PaymentReceipt).filter(PaymentReceipt.receipt_number == receipt_number)
        o = self.db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.receipt_number == receipt_number)
        if society_id is not None:
            r = r.filter(PaymentReceipt.society_id == society_id)
            o = o.filter(OnlinePaymentSubmission.society_id == society_id)
        payment = r.first() or o.first()
        if not payment:
            raise HTTPException(404, "Receipt not found")
        return payment

    def generate_receipt_pdf(self, payment) -> bytes:
        return generate_payment_receipt_pdf(payment)
