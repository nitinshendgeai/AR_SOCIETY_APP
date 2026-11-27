"""Entries the agent drafts follow the society's books (no income or expense counted twice), and the agent's element
review sets each element's ledger by the bye-laws and the society's own rule — applied only by admin / committee."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.models.accounts import Account, Voucher
from app.modules.accounts.services.postings import AccountPostings
from app.modules.accounts_agent.assist import element_setup, entries
from app.modules.accounts_agent.services.engine import get_settings
from app.modules.billing.models.billing import ChargeType, MaintenanceElement
from app.modules.vendor.models.vendor import VendorInvoice
from tests.accounts_agent.legal_helpers import D, ChargeBasis, LRig

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return LRig(db, "ent")


def _draft(rig, db, body):
    return entries.draft(db, rig.sid, rig.admin["user"], body, get_settings(db, rig.sid), save=False)


def _vouchers(db, rig):
    return db.query(Voucher).filter(Voucher.society_id == rig.sid).count()


# ── Entries ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_members_payment_is_handed_to_billing_not_booked_as_income(rig, db):
    flat = rig.flat_rows[0]
    before = _vouchers(db, rig)
    out = _draft(rig, db, {"text": f"received 3,500 cash from A-{flat.flat_number} for november",
                           "voucher_type": "receipt"})
    r = out["redirect"]
    assert r["kind"] == "member_receipt" and r["flat_id"] == str(flat.id) and r["amount"] == "3500.00"
    assert "Members' Dues" in r["accounting"] and out["lines"] == [] and _vouchers(db, rig) == before
    assert _draft(rig, db, {"text": f"recd 3500 from {rig.wing.name} {flat.flat_number}",
                            "voucher_type": "receipt"})["redirect"]["flat_id"] == str(flat.id)
    # no flat named, but clearly maintenance from a member
    out = _draft(rig, db, {"text": "maintenance received 2000 upi", "voucher_type": "receipt"})
    assert out["redirect"]["kind"] == "member_receipt" and out["redirect"]["flat_id"] is None


def test_a_receipt_never_credits_a_ledger_only_bills_credit(rig, db):
    receipt_ledgers = {x["name"] for x in entries._ledgers(db, rig.sid, ("income",))}
    for key in ("service_charges", "sinking_fund", "interest_on_arrears", "non_occupancy", "water_recovered"):
        if key in rig.chart:
            assert rig.chart[key].name not in receipt_ledgers, key
    assert rig.chart["amenities_income"].name in receipt_ledgers          # hall rent etc. may be received directly
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _draft(rig, db, {"amount": "500", "voucher_type": "receipt", "ledger_id": str(rig.chart["service_charges"].id)})


def test_a_payment_against_a_booked_bill_settles_the_bill(rig, db):
    v = rig.vendor("CleanPro")
    db.add(VendorInvoice(society_id=rig.sid, vendor_id=v.id, invoice_number="CP-NOV", invoice_date=rig.today,
                         amount=D("12000"), total_amount=D("12000"), paid_amount=D("0"), is_paid=False))
    db.commit()
    body = {"amount": "12000", "vendor_id": v.id, "ledger_id": str(rig.chart["housekeeping"].id)}
    out = _draft(rig, db, body)
    r = out["redirect"]
    assert r["kind"] == "vendor_bill_payment" and r["bills"][0]["invoice_number"] == "CP-NOV" and r["bills"][0]["due"] == "12000.00"
    assert "Sundry Creditors" in r["accounting"]
    out = _draft(rig, db, {**body, "not_against_bill": True})                 # an advance / other purchase: drafted
    assert "redirect" not in out and out["lines"][0]["account"] == rig.chart["housekeeping"].name


def test_other_income_is_still_drafted(rig, db):
    out = _draft(rig, db, {"amount": "1500", "voucher_type": "receipt", "ledger_id": str(rig.chart["amenities_income"].id),
                           "text": "club house booking by an outsider"})
    assert "redirect" not in out and out["lines"][1]["account"] == rig.chart["amenities_income"].name


# ── Element review ─────────────────────────────────────────────────────────────────────────────────────────────────

def _element(db, rig, code):
    return db.query(MaintenanceElement).filter(MaintenanceElement.society_id == rig.sid,
                                               MaintenanceElement.code == code).first()


def _rec(review, kind, code):
    return next(r for r in review["recommendations"] if r["kind"] == kind and r["element_code"] == code)


def test_a_fund_credited_to_income_is_caught_and_fixed(rig, db):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.FIXED, 100, "sinking_fund")
    el = _element(db, rig, "sinking_fund")
    el.credit_ledger_id = rig.chart["service_charges"].id                     # a fund put in income: wrong
    db.commit()
    rev = element_setup.review(db, rig.sid, rig.today)
    r = _rec(rev, "wrong_ledger_nature", "sinking_fund")
    assert r["severity"] == "HIGH" and r["proposed_ledger"] == rig.chart["sinking_fund"].name and r["in_use"]
    out = element_setup.apply(db, rig.sid, [r["id"]], rig.admin["user"], rig.today)
    db.commit()
    assert out["applied"] and db.get(MaintenanceElement, el.id).credit_ledger_id == rig.chart["sinking_fund"].id
    assert not [x for x in element_setup.review(db, rig.sid, rig.today)["recommendations"]
                if x["element_code"] == "sinking_fund" and x["kind"] != "link_expense"]


def test_bills_follow_the_ledger_set_for_the_element(rig, db):
    rig.config("Lift Maintenance", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 300, "lift_maintenance", service=True)
    custom = Account(society_id=rig.sid, group_id=rig.chart["service_charges"].group_id, name="Lift Charges Recovered")
    db.add(custom)
    db.flush()
    _element(db, rig, "lift_maintenance").credit_ledger_id = custom.id
    db.commit()
    cy = rig.cycle(rig.today - timedelta(days=30), rig.today - timedelta(days=1))
    b = rig.bill(rig.flat_rows[0], cy, [(ChargeType.MAINTENANCE, "Lift Maintenance", 300, 300)])
    v = AccountPostings(db, rig.svc).post_bill(b)
    db.commit()
    credited = {e.account_id: e.credit for e in v.entries if e.credit}
    assert credited.get(custom.id) == Decimal("300.00") and rig.chart["service_charges"].id not in credited
    from app.modules.accounts_agent.legal import ledger_mapping as lm
    row = next(x for x in lm.mapping(db, rig.sid, rig.today)["rows"] if x["element_code"] == "lift_maintenance")
    assert row["posted_ledger"] == "Lift Charges Recovered" and row["source"] == "configured"


def test_a_societys_own_charge_gets_its_own_ledger(rig, db):
    rig.config("Club House Fee", ChargeType.OTHER, ChargeBasis.FIXED, 200, "club_house_fee")
    r = _rec(element_setup.review(db, rig.sid, rig.today), "own_ledger_needed", "club_house_fee")
    assert r["fix"]["action"] == "create_and_set" and r["fix"]["group_key"] == "income_members"
    element_setup.apply(db, rig.sid, [r["id"]], rig.admin["user"], rig.today)
    db.commit()
    acc = db.get(Account, _element(db, rig, "club_house_fee").credit_ledger_id)
    assert acc.name == "Club House Fee" and acc.group.nature == "income"


def test_expense_ledgers_are_linked_to_their_elements(rig, db):
    lift = rig.chart["lift_maintenance"]
    el = db.get(MaintenanceElement, lift.maintenance_element_id) if lift.maintenance_element_id else None
    lift.maintenance_element_id = None
    db.commit()
    if el is None:
        pytest.skip("the standard chart has no lift expense element link to restore")
    r = next(x for x in element_setup.review(db, rig.sid, rig.today)["recommendations"]
             if x["kind"] == "link_expense" and x["current_ledger"] == lift.name)
    element_setup.apply(db, rig.sid, [r["id"]], rig.admin["user"], rig.today)
    db.commit()
    assert db.get(Account, lift.id).maintenance_element_id == el.id


def test_review_api_and_only_admin_or_committee_may_apply(client, rig, db):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.FIXED, 100, "sinking_fund")
    _element(db, rig, "sinking_fund").credit_ledger_id = rig.chart["service_charges"].id
    db.commit()
    rev = client.get(f"{API}/ledger-mapping/element-review", headers=rig.manager["headers"])
    assert rev.status_code == 200 and rev.json()["summary"]["high"] >= 1
    rid = _rec(rev.json(), "wrong_ledger_nature", "sinking_fund")["id"]
    assert client.post(f"{API}/ledger-mapping/element-review/apply", json={"ids": [rid]},
                       headers=rig.manager["headers"]).status_code == 403
    r = client.post(f"{API}/ledger-mapping/element-review/apply", json={"ids": [rid, "nope"]},
                    headers=rig.admin["headers"])
    assert r.status_code == 200 and len(r.json()["applied"]) == 1 and r.json()["skipped"][0]["id"] == "nope"
