"""Flat-wise ledger consistency: each element on a flat's bill is posted to the same ledger as on its previous bill.
(Elements dropped/added and amount changes are S-BILLMOM-*, tested in test_bill_month_change.py.)"""
from datetime import date, timedelta
from uuid import UUID

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.models.agent import AgentFinding
from app.modules.accounts_agent.services import engine
from app.modules.billing.models.billing import (
    MaintenanceBill, MaintenanceChargeConfig, MaintenanceElement,
)
from tests.billing.test_maintenance_billing import _charge, _rig

RULES = ("R-BILL-06",)


def _run_cycle(client, db, h, sid, start: date, name: str):
    r = client.post("/api/v1/billing/cycles", json={
        "society_id": str(sid), "name": name, "cycle_start": str(start),
        "cycle_end": str(start + timedelta(days=29)), "due_date": str(start + timedelta(days=10))}, headers=h)
    assert r.status_code in (200, 201), r.text
    cid = r.json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cid}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cid}/issue-all", headers=h).status_code == 200
    return UUID(cid)


@pytest.fixture
def society(client, db):
    """Two flats with Service Charges, Sinking Fund and Water; last month's cycle already issued and posted."""
    soc, flat1, flat2, manager, resident, other = _rig(db, "bc")
    h = manager["headers"]
    _charge(client, h, soc.id, name="Service Charges", amount="2500.00")
    _charge(client, h, soc.id, name="Sinking Fund", amount="500.00", charge_type="sinking_fund")
    _charge(client, h, soc.id, name="Water", amount="300.00", charge_type="water")
    today = date.today()
    _run_cycle(client, db, h, soc.id, today - timedelta(days=30), "Last month")
    return {"client": client, "db": db, "h": h, "soc": soc, "flats": (flat1, flat2), "today": today}


def this_month(s):
    return _run_cycle(s["client"], s["db"], s["h"], s["soc"].id, s["today"], "This month")


def voucher_of(db, cycle_id, flat):
    bill = db.query(MaintenanceBill).filter_by(cycle_id=cycle_id, flat_id=flat.id).one()
    return bill, db.query(Voucher).filter(Voucher.source_type == "maintenance_bill", Voucher.source_id == bill.id).one()


def drafts(db, v):
    db.refresh(v)
    return [d for d in engine.analyse(db, v) if d.rule_code in RULES]


def stored(db, sid):
    return db.query(AgentFinding).filter(AgentFinding.society_id == sid, AgentFinding.rule_code.in_(RULES)).all()


def test_same_elements_and_ledgers_as_last_month_raise_nothing(society):
    db = society["db"]
    cid = this_month(society)
    for flat in society["flats"]:
        assert drafts(db, voucher_of(db, cid, flat)[1]) == []


def test_a_flats_first_bill_has_nothing_to_compare_with(society):
    db = society["db"]
    first = db.query(MaintenanceBill).filter_by(flat_id=society["flats"][0].id).one()
    v = db.query(Voucher).filter(Voucher.source_type == "maintenance_bill", Voucher.source_id == first.id).one()
    assert drafts(db, v) == []





def test_element_moved_to_another_ledger_is_flagged_once_with_old_and_new_ledger(society):
    db, sid = society["db"], society["soc"].id
    sinking = db.query(MaintenanceChargeConfig).filter_by(society_id=sid, name="Sinking Fund").one()
    repair = db.query(MaintenanceElement).filter_by(society_id=sid, code="repair_fund").one()
    sinking.element_id = repair.id                              # re-mapped: Sinking Fund now posts to Repair Fund
    db.commit()
    cid = this_month(society)
    (d,) = drafts(db, voucher_of(db, cid, society["flats"][0])[1])
    assert d.rule_code == "R-BILL-06"
    (ch,) = d.evidence["changes"]
    assert ch["element"] == "Sinking Fund" and ch["old"] == "sinking_fund" and ch["new"] == "repair_fund"
    assert "Sinking Fund" in d.explanation and ch["old_ledger"] in d.explanation and ch["new_ledger"] in d.explanation
    worker.run_once(db, "w", limit=500)                         # both flats' bills processed: one finding per cycle
    found = [f for f in stored(db, sid) if f.rule_code == "R-BILL-06"]
    assert len(found) == 1


def test_the_month_after_a_remap_is_clean_again(society):
    """The new mapping becomes the baseline: next month compares with this month, so nothing is flagged again."""
    db, sid = society["db"], society["soc"].id
    sinking = db.query(MaintenanceChargeConfig).filter_by(society_id=sid, name="Sinking Fund").one()
    sinking.element_id = db.query(MaintenanceElement).filter_by(society_id=sid, code="repair_fund").one().id
    db.commit()
    this_month(society)
    nxt = _run_cycle(society["client"], db, society["h"], sid, society["today"] + timedelta(days=30), "Next month")
    for flat in society["flats"]:
        assert drafts(db, voucher_of(db, nxt, flat)[1]) == []


def test_an_element_dropped_for_one_flat_is_not_a_ledger_finding(society):
    """Elements dropped/added belong to S-BILLMOM-02/03; the ledger check must not report them a second time."""
    from app.modules.billing.models.billing import InvoiceLineItem
    db = society["db"]
    cid = this_month(society)
    bill, v = voucher_of(db, cid, society["flats"][0])
    db.query(InvoiceLineItem).filter_by(bill_id=bill.id, description="Sinking Fund").delete()
    db.commit()
    db.expire_all()
    assert drafts(db, v) == []
