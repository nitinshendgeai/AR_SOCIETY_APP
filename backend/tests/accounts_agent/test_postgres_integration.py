"""Real-PostgreSQL checks (outbox atomicity under true transactions, FOR UPDATE SKIP LOCKED claiming).

Skipped unless AGENT_TEST_PG_URL points at a THROWAWAY PostgreSQL database, e.g.
    AGENT_TEST_PG_URL=postgresql://postgres@localhost:5432/agent_test pytest tests/accounts_agent/test_postgres_integration.py
The schema is created (and dropped) by the test run."""
import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PG = os.environ.get("AGENT_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG, reason="AGENT_TEST_PG_URL not set")


@pytest.fixture(scope="module")
def pg():
    import app.models  # noqa: F401
    from app.core.rbac_seed import seed_form_definitions, seed_permission_definitions
    from app.db.base import Base
    engine = create_engine(PG)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        seed_permission_definitions(conn)
        seed_form_definitions(conn)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def _setup(pg):
    from app.models.society import Society
    from app.modules.accounts.services.accounts_service import AccountsService
    with Session(pg) as s:
        soc = Society(name=f"PG {uuid.uuid4().hex[:8]}", city="Pune", state="MH")
        s.add(soc); s.commit()
        chart = AccountsService(s).ensure_chart(soc.id); s.commit()
        return soc.id, {k: a.id for k, a in chart.items()}


def _post(s, sid, ids, amount="100.00"):
    from decimal import Decimal
    from datetime import date
    from app.modules.accounts.models.accounts import Account
    from app.modules.accounts.services.accounts_service import AccountsService, Line
    a, b = s.get(Account, ids["office_expenses"]), s.get(Account, ids["bank"])
    return AccountsService(s).build_voucher(sid, "payment", date.today(), [Line(a, debit=Decimal(amount)), Line(b, credit=Decimal(amount))])


def _events(pg, sid):
    with pg.connect() as c:
        return c.execute(text("select count(*) from accounts_agent_events where society_id=:s"), {"s": sid}).scalar()


def test_event_commits_with_the_voucher_and_vanishes_on_rollback(pg):
    sid, ids = _setup(pg)
    with Session(pg) as s:
        _post(s, sid, ids); s.commit()
    assert _events(pg, sid) == 1
    with Session(pg) as s:
        _post(s, sid, ids); s.rollback()
    assert _events(pg, sid) == 1                      # the rolled-back posting left no event
    with Session(pg) as s:
        try:
            with s.begin_nested():
                _post(s, sid, ids)
                raise RuntimeError("posting hook failed")
        except RuntimeError:
            pass
        s.commit()
    assert _events(pg, sid) == 1


def test_broken_agent_table_cannot_abort_a_posting(pg, monkeypatch):
    from app.modules.accounts_agent.services import outbox
    sid, ids = _setup(pg)
    real = outbox._insert_ignoring_duplicates

    def bad(connection, rows):                        # a failing SQL statement inside the savepoint
        connection.execute(text("insert into accounts_agent_events (id) values (null)"))
    monkeypatch.setattr(outbox, "_insert_ignoring_duplicates", bad)
    with Session(pg) as s:
        v = _post(s, sid, ids); s.commit()            # PostgreSQL would normally mark the transaction aborted
        vid = v.id
    from app.modules.accounts.models.accounts import Voucher
    with Session(pg) as s:
        assert s.get(Voucher, vid) is not None
    assert _events(pg, sid) == 0


def test_two_workers_claim_disjoint_batches(pg):
    from app.modules.accounts_agent import worker
    sid, ids = _setup(pg)
    with Session(pg) as s:
        for _ in range(6):
            _post(s, sid, ids)
        s.commit()
    s1, s2 = Session(pg), Session(pg)
    try:
        q = lambda s: s.query(worker.AgentEvent).filter(worker.AgentEvent.society_id == sid, worker.AgentEvent.status == "pending") \
            .order_by(worker.AgentEvent.created_at).limit(3).with_for_update(skip_locked=True)   # noqa: E731
        a = {e.id for e in q(s1).all()}
        b = {e.id for e in q(s2).all()}                # s1 still holds its row locks
        assert len(a) == 3 and len(b) == 3 and not a & b
    finally:
        s1.rollback(); s2.rollback(); s1.close(); s2.close()
    # and the real claim function is usable end to end
    with Session(pg) as s:
        got = worker.claim_batch(s, "pgw", limit=10)
        assert len(got) >= 6                       # earlier tests left their own events pending too
        assert worker.claim_batch(s, "pgw2", limit=10) == []


def test_compliance_scan_end_to_end_on_postgres(pg):
    """Engine B on real PostgreSQL: rule pack seeding, date-based rule resolution, a scan storing legal findings
    (JSON legal_source, LIKE on dedupe keys), idempotent re-scan, and strict per-society results."""
    from datetime import timedelta
    from decimal import Decimal
    from app.modules.accounts.services.accounts_service import AccountsService, Line
    from app.modules.accounts_agent import worker
    from app.modules.accounts_agent.legal import compliance, registry
    from app.modules.accounts_agent.models.agent import AgentFinding
    from app.modules.accounts_agent.services.engine import get_settings
    from app.modules.billing.models.billing import MaintenanceSettings
    from app.models.society import Society
    from app.utils.local_time import society_today
    with Session(pg) as s:
        socs = []
        for tag in ("a", "b"):
            soc = Society(name=f"PG legal {tag} {uuid.uuid4().hex[:6]}", city="Mumbai", state="Maharashtra")
            s.add(soc); s.commit()
            chart = AccountsService(s).ensure_chart(soc.id)
            socs.append((soc, chart))
        (a, chart_a), (b, _) = socs
        s.add(MaintenanceSettings(society_id=a.id, interest_rate_pct=18, non_occupancy_pct=0))
        today = society_today(s, a.id)
        svc = AccountsService(s)
        v = svc.build_voucher(a.id, "payment", today - timedelta(days=5),
                              [Line(chart_a["sinking_fund"], debit=Decimal("40000")), Line(chart_a["bank"], credit=Decimal("40000"))],
                              narration="Sinking fund use", reference="SF-PG")
        v.approval_status = "approved"
        s.commit()
        out = compliance.run_scan(s, a.id); out.pop("_created"); s.commit()
        assert not out["failed_checks"], out
        codes = {f.rule_code: f for f in s.query(AgentFinding).filter(AgentFinding.society_id == a.id)}
        assert {"L-CHG-INT-01", "L-FND-USE-01", "A-FND-BAL-01", "L-SRC-CON-01"} <= set(codes)
        assert codes["L-CHG-INT-01"].legal_source["verified"] is False
        assert codes["L-CHG-INT-01"].finding_class == "POTENTIAL_NON_COMPLIANCE"
        again = compliance.run_scan(s, a.id); again.pop("_created"); s.commit()
        assert again["new_findings"] == 0
        assert s.query(AgentFinding).filter(AgentFinding.society_id == b.id, AgentFinding.rule_code == "L-CHG-INT-01").count() == 0
        assert registry.resolve(s, a.id, "charges.interest_on_arrears.max_rate_pct", today).effective_value == 12
        get_settings(s, b.id); s.commit()
        assert worker.scan_due(s) >= 1          # b is due; a was scanned just now


def test_approval_holds_the_voucher_row_lock(pg):
    """approve_proposal loads the voucher with lock=True: until it finishes, nobody else can edit that voucher, so the
    stale-state check cannot be overtaken by a concurrent edit."""
    from sqlalchemy.exc import OperationalError
    from app.modules.accounts.models.accounts import Voucher
    from app.modules.accounts_agent.services import engine
    sid, ids = _setup(pg)
    with Session(pg) as s:
        vid = _post(s, sid, ids).id
        s.commit()
    holder, other = Session(pg), Session(pg)
    try:
        assert engine.load_voucher(holder, sid, vid, lock=True) is not None
        with pytest.raises(OperationalError):          # NOWAIT: the row is locked by the approving transaction
            other.query(Voucher).filter(Voucher.id == vid).with_for_update(nowait=True).one()
        other.rollback()
        holder.rollback()                              # lock released
        assert other.query(Voucher).filter(Voucher.id == vid).with_for_update(nowait=True).one().id == vid
    finally:
        holder.rollback(); other.rollback(); holder.close(); other.close()


# ── Remediation (functional audit D-02 / D-04 / D-14) on real PostgreSQL ────────────────────────────────────────────

def _worker_drain(s):
    from app.modules.accounts_agent import worker
    while worker.run_once(s, "pg-w", limit=500).get("claimed", 0):
        pass


def test_vendor_tag_removal_keeps_the_confirmed_duplicate_on_postgres(pg):
    """The edit goes through AccountsService → outbox (voucher.edited) → real worker; the R-DUP-02 finding survives and
    the partner's pair finding is re-checked in the same transaction as the event."""
    from datetime import timedelta
    from decimal import Decimal
    from app.modules.accounts.models.accounts import Account
    from app.modules.accounts.services.accounts_service import AccountsService, Line
    from app.modules.accounts_agent.models.agent import AgentFinding
    from app.modules.vendor.models.vendor import Vendor, VendorCategory
    from app.utils.local_time import society_today
    sid, ids = _setup(pg)
    with Session(pg) as s:
        ven = Vendor(society_id=sid, vendor_code="PG1", company_name="SecureCo", mobile="9999999999",
                     category=list(VendorCategory)[0])
        s.add(ven); s.commit()
        svc, day = AccountsService(s), society_today(s, sid)
        sec, bank = s.get(Account, ids["security_charges"]), s.get(Account, ids["bank"])
        made = []
        for ref, vend in (("SG-1", ven.id), ("SG-1", ven.id), (None, ven.id)):
            v = svc.build_voucher(sid, "payment", day - timedelta(days=1),
                                  [Line(sec, debit=Decimal("25000")), Line(bank, credit=Decimal("25000"))],
                                  reference=ref, vendor_id=vend, narration="Security")
            v.approval_status = "approved"
            s.commit()
            made.append(v)
        _worker_drain(s); s.commit()
        first, dup, noref = made
        f02 = s.query(AgentFinding).filter(AgentFinding.voucher_id == dup.id, AgentFinding.rule_code == "R-DUP-02").one()
        f04 = next(f for f in s.query(AgentFinding).filter(AgentFinding.voucher_id == noref.id,
                                                           AgentFinding.rule_code == "R-DUP-04")
                   if f.evidence["other_voucher_id"] == str(dup.id))
        svc.update_manual_voucher(dup.id, {
            "voucher_date": dup.voucher_date, "narration": dup.narration, "reference": dup.reference, "vendor_id": None,
            "entries": [{"account_id": e.account_id, "debit": e.debit, "credit": e.credit} for e in dup.entries],
            "reason": "vendor tag removed"}, None)
        s.commit()
        _worker_drain(s); s.commit()
        s.refresh(f02); s.refresh(f04)
        assert f02.status in ("NEW", "UNDER_REVIEW")                     # the genuine duplicate is not hidden
        assert f04.status == "RESOLVED" and f04.resolution_note.startswith("Re-classified as R-DUP-03")
        assert s.query(AgentFinding).filter(AgentFinding.voucher_id == noref.id, AgentFinding.rule_code == "R-DUP-03",
                                            AgentFinding.status == "NEW").count() == 1


def test_receipt_on_the_wrong_flat_on_postgres_and_rollback_leaves_nothing(pg):
    from datetime import timedelta
    from decimal import Decimal
    from app.models.society import Society
    from app.models.wing import Wing
    from app.models.flat import Flat
    from app.modules.accounts.services.accounts_service import AccountsService, Line
    from app.modules.accounts.services.postings import AccountPostings
    from app.modules.accounts_agent.legal import compliance
    from app.modules.accounts_agent.models.agent import AgentFinding
    from app.modules.billing.models.billing import (BillingCycle, BillStatus, ChargeType, InvoiceLineItem,
                                                    MaintenanceBill)
    from app.utils.local_time import society_today
    with Session(pg) as s:
        soc = Society(name=f"PG mar {uuid.uuid4().hex[:6]}", city="Pune", state="Maharashtra")
        s.add(soc); s.commit()
        chart = AccountsService(s).ensure_chart(soc.id); s.commit()
        w = Wing(society_id=soc.id, name="A"); s.add(w); s.commit()
        f1, f5 = Flat(wing_id=w.id, flat_number="101"), Flat(wing_id=w.id, flat_number="105")
        s.add_all([f1, f5]); s.commit()
        day = society_today(s, soc.id)
        cy = BillingCycle(society_id=soc.id, name="Oct", cycle_start=day - timedelta(days=40),
                          cycle_end=day - timedelta(days=10), due_date=day - timedelta(days=10))
        s.add(cy); s.commit()
        b = MaintenanceBill(society_id=soc.id, cycle_id=cy.id, flat_id=f5.id, invoice_number="INV-PG-1",
                            bill_status=BillStatus.ISSUED, bill_date=cy.cycle_start, due_date=cy.due_date,
                            subtotal=Decimal("2020"), total_amount=Decimal("2020"), paid_amount=Decimal("0"),
                            outstanding=Decimal("2020"), previous_dues=Decimal("0"))
        b.line_items.append(InvoiceLineItem(charge_type=ChargeType.MAINTENANCE, description="Service Charges",
                                            unit_rate=Decimal("2020"), amount=Decimal("2020"), total=Decimal("2020")))
        s.add(b); s.commit()
        svc = AccountsService(s)
        AccountPostings(s, svc).post_bill(b); s.commit()

        def receipt():
            v = svc.build_voucher(soc.id, "receipt", day - timedelta(days=1),
                                  [Line(chart["bank"], debit=Decimal("2020")),
                                   Line(chart["members_dues"], credit=Decimal("2020"), flat_id=f1.id)])
            v.approval_status = "approved"
            return v
        receipt(); s.rollback()                                           # never committed: nothing to find
        out = compliance.run_scan(s, soc.id); out.pop("_created"); s.commit()
        assert not out["failed_checks"]
        assert s.query(AgentFinding).filter(AgentFinding.society_id == soc.id, AgentFinding.rule_code.like("A-MAR%")).count() == 0
        rv = receipt(); s.commit()
        out = compliance.run_scan(s, soc.id); out.pop("_created"); s.commit()
        f = s.query(AgentFinding).filter(AgentFinding.society_id == soc.id, AgentFinding.rule_code == "A-MAR-01").one()
        assert f.flat_id == f1.id and f.voucher_id == rv.id and f.evidence["manual_receipts"][0]["voucher"] == rv.voucher_number
