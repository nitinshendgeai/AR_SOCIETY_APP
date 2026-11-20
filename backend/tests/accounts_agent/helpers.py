"""Fixtures for Accounts Agent tests: a society with its chart of accounts, an admin and a manager, vendors, and a
realistic three months of vouchers built through the real AccountsService (so they obey the real accounting rules)."""
from datetime import date, timedelta
from decimal import Decimal

from app.models.permission import Permission  # noqa: F401
from app.modules.accounts.services.accounts_service import AccountsService, Line
from app.modules.accounts_agent.services import engine, learning
from app.modules.vendor.models.vendor import Vendor, VendorCategory
from app.utils.local_time import society_today
from tests.conftest import make_society, make_user, place_in

D = Decimal


class Rig:
    def __init__(self, db, tag):
        self.db = db
        self.society = make_society(db, f"Agent Society {tag}")
        self.sid = self.society.id
        self.svc = AccountsService(db)
        self.chart = self.svc.ensure_chart(self.sid)
        db.commit()
        self.admin = place_in(db, make_user(db, f"admin@agent{tag}.com", role="Society Admin"), self.society)
        self.manager = place_in(db, make_user(db, f"mgr@agent{tag}.com", role="Manager"), self.society)
        # A second authorised person: the checker for corrections the admin proposes (maker–checker).
        self.chair = place_in(db, make_user(db, f"chair@agent{tag}.com", role="Committee Chairman"), self.society)
        self.today = society_today(db, self.sid)
        self._n = 0

    def vendor(self, name="SecureCo"):
        self._n += 1
        v = Vendor(society_id=self.sid, vendor_code=f"V{self._n:03d}", company_name=name, mobile="9999999999",
                   category=VendorCategory.SECURITY if hasattr(VendorCategory, "SECURITY") else list(VendorCategory)[0])
        self.db.add(v)
        self.db.commit()
        return v

    def payment(self, days_ago, key, amount, vendor=None, reference=None, narration="Monthly bill", approved=True):
        """A payment voucher (Dr expense ledger, Cr bank) as a person would enter and an approver approve."""
        d = self.today - timedelta(days=days_ago)
        lines = [Line(self.chart[key], debit=D(str(amount))), Line(self.chart["bank"], credit=D(str(amount)))]
        v = self.svc.build_voucher(self.sid, "payment", d, lines, narration=narration, reference=reference,
                                   vendor_id=vendor.id if vendor else None, user=self.manager["user"])
        if approved:
            v.approved_by, v.approval_status = self.admin["user"].id, "approved"
        self.db.commit()
        return v

    def journal(self, days_ago, dr_key, cr_key, amount, narration="Adjustment"):
        d = self.today - timedelta(days=days_ago)
        lines = [Line(self.chart[dr_key], debit=D(str(amount))), Line(self.chart[cr_key], credit=D(str(amount)))]
        v = self.svc.build_voucher(self.sid, "journal", d, lines, narration=narration, user=self.manager["user"])
        v.approved_by = self.admin["user"].id
        self.db.commit()
        return v

    def learn(self):
        run = learning.learn_society(self.db, self.sid)
        self.db.commit()
        return run

    def analyse(self, voucher, event="voucher.created"):
        self.db.refresh(voucher)
        return engine.analyse(self.db, voucher, event)

    def seed_history(self):
        """~3 months of ordinary activity: office expenses of ~₹1,000 (8 postings), a monthly security bill of ₹25,000
        to one vendor, and a vendor whose expenses always go to Housekeeping."""
        self.sec, self.clean = self.vendor("SecureCo"), self.vendor("CleanCo")
        for i, amt in enumerate([1000, 1100, 950, 1050, 1020, 980, 1080, 1010]):
            self.payment(80 - i * 9, "office_expenses", amt, narration="Stationery")
        for days in (75, 45, 16):
            self.payment(days, "security_charges", 25000, vendor=self.sec, reference=f"SEC-{days}")
        for days in (70, 55, 40, 25):
            self.payment(days, "housekeeping", 6000 + days, vendor=self.clean, reference=f"CLN-{days}")
        return self.learn()


def codes(drafts):
    return sorted(d.rule_code for d in drafts)
