from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from app.modules.billing.models.billing import (
    FinancialPeriod, MaintenanceChargeConfig, BillingCycle,
    MaintenanceBill, InvoiceLineItem, PaymentReceipt,
    DueTracker, PenaltyRule, BillStatus,
)
from app.repositories.base import BaseRepository


class FinancialPeriodRepo(BaseRepository[FinancialPeriod]):
    def __init__(self, db): super().__init__(FinancialPeriod, db)
    def get_by_society(self, sid: UUID) -> List[FinancialPeriod]:
        return self.db.query(FinancialPeriod).filter(
            FinancialPeriod.society_id==sid, FinancialPeriod.is_active==True
        ).order_by(FinancialPeriod.period_start.desc()).all()


class ChargeConfigRepo(BaseRepository[MaintenanceChargeConfig]):
    def __init__(self, db): super().__init__(MaintenanceChargeConfig, db)
    def get_by_society(self, sid: UUID) -> List[MaintenanceChargeConfig]:
        return self.db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.society_id==sid, MaintenanceChargeConfig.is_active==True
        ).all()


class BillingCycleRepo(BaseRepository[BillingCycle]):
    def __init__(self, db): super().__init__(BillingCycle, db)
    def get_by_society(self, sid: UUID, skip=0, limit=20) -> List[BillingCycle]:
        return self.db.query(BillingCycle).filter(
            BillingCycle.society_id==sid, BillingCycle.is_active==True
        ).order_by(BillingCycle.cycle_start.desc()).offset(skip).limit(limit).all()


class MaintenanceBillRepo(BaseRepository[MaintenanceBill]):
    def __init__(self, db): super().__init__(MaintenanceBill, db)

    def get_by_flat(self, flat_id: UUID, skip=0, limit=50) -> List[MaintenanceBill]:
        return self.db.query(MaintenanceBill).filter(
            MaintenanceBill.flat_id==flat_id, MaintenanceBill.is_active==True
        ).order_by(MaintenanceBill.bill_date.desc()).offset(skip).limit(limit).all()

    def get_by_cycle(self, cycle_id: UUID) -> List[MaintenanceBill]:
        return self.db.query(MaintenanceBill).filter(
            MaintenanceBill.cycle_id==cycle_id, MaintenanceBill.is_active==True
        ).all()

    def get_overdue(self, sid: UUID) -> List[MaintenanceBill]:
        return self.db.query(MaintenanceBill).filter(
            MaintenanceBill.society_id==sid,
            MaintenanceBill.bill_status.in_([BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE]),
            MaintenanceBill.due_date < date.today(),
            MaintenanceBill.is_active==True,
        ).all()

    def get_outstanding_by_society(self, sid: UUID) -> List[MaintenanceBill]:
        return self.db.query(MaintenanceBill).filter(
            MaintenanceBill.society_id==sid,
            MaintenanceBill.bill_status.in_([BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE]),
            MaintenanceBill.is_active==True,
        ).order_by(MaintenanceBill.due_date).all()

    def next_invoice_number(self, sid: UUID) -> str:
        from sqlalchemy import func
        count = self.db.query(func.count(MaintenanceBill.id)).filter(
            MaintenanceBill.society_id==sid
        ).scalar() or 0
        from datetime import date as dt
        y = dt.today().year
        return f"INV-{y}-{str(count+1).zfill(5)}"


class PaymentReceiptRepo(BaseRepository[PaymentReceipt]):
    def __init__(self, db): super().__init__(PaymentReceipt, db)

    def get_by_bill(self, bill_id: UUID) -> List[PaymentReceipt]:
        return self.db.query(PaymentReceipt).filter(
            PaymentReceipt.bill_id==bill_id, PaymentReceipt.is_reversed==False
        ).order_by(PaymentReceipt.payment_date.asc()).all()

    def get_by_flat(self, flat_id: UUID, skip=0, limit=50) -> List[PaymentReceipt]:
        return self.db.query(PaymentReceipt).filter(
            PaymentReceipt.flat_id==flat_id
        ).order_by(PaymentReceipt.payment_date.desc()).offset(skip).limit(limit).all()

    def next_receipt_number(self, sid: UUID) -> str:
        from sqlalchemy import func
        from datetime import date as dt
        count = self.db.query(func.count(PaymentReceipt.id)).filter(
            PaymentReceipt.society_id==sid
        ).scalar() or 0
        y = dt.today().year
        return f"RCP-{y}-{str(count+1).zfill(5)}"


class DueTrackerRepo(BaseRepository[DueTracker]):
    def __init__(self, db): super().__init__(DueTracker, db)

    def get_by_flat(self, flat_id: UUID) -> Optional[DueTracker]:
        return self.db.query(DueTracker).filter(DueTracker.flat_id==flat_id).first()

    def get_or_create(self, flat_id: UUID, society_id: UUID) -> DueTracker:
        t = self.get_by_flat(flat_id)
        if not t:
            t = DueTracker(flat_id=flat_id, society_id=society_id)
            self.db.add(t); self.db.flush()
        return t

    def get_all_outstanding(self, sid: UUID) -> List[DueTracker]:
        from decimal import Decimal
        return self.db.query(DueTracker).filter(
            DueTracker.society_id==sid, DueTracker.outstanding > 0
        ).order_by(DueTracker.outstanding.desc()).all()


class PenaltyRuleRepo(BaseRepository[PenaltyRule]):
    def __init__(self, db): super().__init__(PenaltyRule, db)
    def get_active(self, sid: UUID) -> List[PenaltyRule]:
        return self.db.query(PenaltyRule).filter(
            PenaltyRule.society_id==sid, PenaltyRule.is_active==True
        ).all()
