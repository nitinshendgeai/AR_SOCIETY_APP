"""Fixtures for the legal & compliance engine: a Maharashtra housing society with wings, flats, charge heads, bills,
documents and resolutions, built directly on the real models (bills are inserted as the billing module stores them)."""
from datetime import date, timedelta
from decimal import Decimal

from app.modules.accounts_agent.legal import compliance, documents, registry
from app.modules.accounts_agent.legal import resolutions as res_svc
from app.modules.accounts_agent.models.agent import AgentFinding
from app.modules.billing.models.billing import (
    BillingCycle, BillStatus, ChargeBasis, ChargeType, InvoiceLineItem, MaintenanceBill, MaintenanceChargeConfig,
    MaintenanceElement, MaintenanceSettings,
)
from tests.accounts_agent.helpers import Rig
from tests.conftest import make_flat, make_wing

D = Decimal


class LRig(Rig):
    def __init__(self, db, tag):
        super().__init__(db, tag)
        self.tag = tag
        self._bill_no = 0
        self.wing = make_wing(db, self.sid, "A Wing")
        self.flat_rows = [make_flat(db, self.wing.id, f"{100 + i}") for i in range(1, 6)]
        registry.ensure_jurisdiction_pack(db)
        db.commit()

    # Billing configuration ---------------------------------------------------------------------------------------
    def settings(self, **kw):
        s = self.db.query(MaintenanceSettings).filter(MaintenanceSettings.society_id == self.sid).first()
        if s is None:
            s = MaintenanceSettings(society_id=self.sid, interest_rate_pct=12, non_occupancy_pct=0)
            self.db.add(s)
        for k, v in kw.items():
            setattr(s, k, v)
        self.db.commit()
        return s

    def config(self, name, ctype, basis, amount, element_code=None, service=False):
        el = None
        if element_code:
            el = self.db.query(MaintenanceElement).filter(MaintenanceElement.society_id == self.sid,
                                                          MaintenanceElement.code == element_code).first()
        if element_code and el is None:
            el = MaintenanceElement(society_id=self.sid, code=element_code, name=name, category=ctype, default_basis=basis)
            self.db.add(el)
            self.db.flush()
        c = MaintenanceChargeConfig(society_id=self.sid, charge_type=ctype, name=name, basis=basis,
                                    default_amount=D(str(amount)), is_service_charge=service,
                                    element_id=el.id if el else None)
        self.db.add(c)
        self.db.commit()
        return c

    def cycle(self, start, end, due=None, name=None):
        c = BillingCycle(society_id=self.sid, name=name or f"{start:%b %Y}", cycle_start=start, cycle_end=end,
                         due_date=due or end)
        self.db.add(c)
        self.db.commit()
        return c

    def bill(self, flat, cycle, lines, *, previous_dues=0, bill_date=None, due_date=None, paid=0, outstanding=None,
             status=BillStatus.ISSUED):
        self._bill_no += 1
        total = sum((D(str(a)) for _, _, _, a in lines), D("0"))
        b = MaintenanceBill(society_id=self.sid, cycle_id=cycle.id, flat_id=flat.id,
                            invoice_number=f"INV-{self.tag}-{self._bill_no:04d}", bill_status=status,
                            bill_date=bill_date or cycle.cycle_start, due_date=due_date or cycle.due_date,
                            subtotal=total, total_amount=total, paid_amount=D(str(paid)),
                            outstanding=D(str(outstanding)) if outstanding is not None else total - D(str(paid)),
                            previous_dues=D(str(previous_dues)))
        for ctype, desc, rate, amount in lines:
            b.line_items.append(InvoiceLineItem(charge_type=ctype, description=desc, unit_rate=D(str(rate)),
                                                amount=D(str(amount)), total=D(str(amount))))
        self.db.add(b)
        self.db.commit()
        return b

    # Legal --------------------------------------------------------------------------------------------------------
    def upload(self, text, document_type="REGISTERED_BYELAWS", title="Registered bye-laws", file_name="bylaws.txt",
               requested_status=None, society=True, user=None, primary=False, data=None):
        return documents.upload(self.db, society_id=self.sid if society else None, user=user or self.admin["user"],
                                file_name=file_name, data=data if data is not None else text.encode("utf-8"),
                                mime_type=None, document_type=document_type, title=title,
                                requested_status=requested_status, is_primary_source=primary)

    def resolution(self, **kw):
        base = dict(resolution_number=f"R-{self._n}", meeting_type="COMMITTEE", meeting_date=self.today - timedelta(days=120),
                    purpose="Approval", category="expense")
        base.update(kw)
        self._n += 1
        r = res_svc.create(self.db, self.sid, self.admin["user"], base)
        self.db.commit()
        return r

    def scan(self):
        out = compliance.run_scan(self.db, self.sid, self.admin["user"].id)
        out.pop("_created")
        self.db.commit()
        return out

    def findings(self, rule_code=None, open_only=True):
        q = self.db.query(AgentFinding).filter(AgentFinding.society_id == self.sid)
        if rule_code:
            q = q.filter(AgentFinding.rule_code == rule_code)
        if open_only:
            q = q.filter(AgentFinding.status.in_(("NEW", "UNDER_REVIEW", "APPROVED")))
        return q.all()


def days_ago(rig, n) -> date:
    return rig.today - timedelta(days=n)


__all__ = ["LRig", "D", "ChargeType", "ChargeBasis", "BillStatus", "days_ago"]
