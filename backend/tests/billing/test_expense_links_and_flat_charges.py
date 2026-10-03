"""Expense ledgers linked to maintenance elements (and a charge head that bills
from their spend), and fines / additional charges on one flat."""
from datetime import date, timedelta
from uuid import UUID

from app.models.notification import Notification
from app.modules.accounts.models.accounts import Account
from app.modules.billing.models.billing import FlatCharge, InvoiceLineItem, MaintenanceBill
from tests.billing.test_budget_suggestions import _bill, _charge_from_element, _rig as _budget_rig
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
from tests.conftest import make_society, make_user

B = "/api/v1/billing"
L = "/api/v1/accounts/ledgers"


def _ledgers(client, h, society_id):
    r = client.get(f"/api/v1/accounts/ledgers/{society_id}", headers=h)
    assert r.status_code == 200, r.text
    return {a["system_key"] or a["name"]: a for a in r.json()}


def _element(client, h, society_id, code):
    return next(e for e in client.get(f"{B}/elements/{society_id}", headers=h).json() if e["code"] == code)


def _fine(client, h, society, flat, **kw):
    body = {"society_id": str(society.id), "flat_id": str(flat.id), "kind": "fine", "title": "Late parking",
            "reason": "Parked in visitor bay", "amount": "500.00", "effective_date": str(date.today()), **kw}
    return client.post(f"{B}/flat-charges", json=body, headers=h)


def _generate(client, h, cycle_id):
    r = client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=h)
    assert r.status_code == 200, r.text


def _lines(db, flat):
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat.id).one()
    return bill, {l.description: l for l in db.query(InvoiceLineItem).filter_by(bill_id=bill.id)}


# ── Ledger → element links ────────────────────────────────────────────────────

def test_standard_expense_ledgers_come_linked_to_their_elements(client, db):
    society, admin, manager, _ = _budget_rig(db, "l1")
    ledgers = _ledgers(client, admin, society.id)
    security = _element(client, manager, society.id, "security")
    assert ledgers["security_charges"]["maintenance_element_id"] == security["id"]
    assert ledgers["cctv_maintenance"]["maintenance_element_name"] == security["name"]
    assert ledgers["repairs_plumbing"]["maintenance_element_id"] is None


def test_a_ledger_can_be_linked_changed_and_cleared(client, db):
    society, admin, manager, _ = _budget_rig(db, "l2")
    ledger = _ledgers(client, admin, society.id)["repairs_plumbing"]
    water = _element(client, manager, society.id, "water_charges")
    r = client.patch(f"{L}/{ledger['id']}", json={"maintenance_element_id": water["id"]}, headers=admin)
    assert r.status_code == 200 and r.json()["maintenance_element_name"] == water["name"]
    r = client.patch(f"{L}/{ledger['id']}", json={"description": "x"}, headers=admin)
    assert r.json()["maintenance_element_id"] == water["id"]          # untouched when not sent
    r = client.patch(f"{L}/{ledger['id']}", json={"maintenance_element_id": None}, headers=admin)
    assert r.status_code == 200 and r.json()["maintenance_element_id"] is None


def test_only_an_expense_ledger_links_and_only_to_its_own_societys_element(client, db):
    society, admin, manager, _ = _budget_rig(db, "l3")
    other, oadmin, omanager, _ = _budget_rig(db, "l3b")
    ledgers = _ledgers(client, admin, society.id)
    mine = _element(client, manager, society.id, "security")["id"]
    theirs = _element(client, omanager, other.id, "security")["id"]
    assert client.patch(f"{L}/{ledgers['repairs_plumbing']['id']}", json={"maintenance_element_id": theirs},
                        headers=admin).status_code == 422
    income = next(a for a in ledgers.values() if a["nature"] == "income")
    assert client.patch(f"{L}/{income['id']}", json={"maintenance_element_id": mine}, headers=admin).status_code == 422
    group = ledgers["repairs_plumbing"]["group_id"]
    r = client.post(L, json={"society_id": str(society.id), "group_id": group, "name": "Lift AMC extra",
                             "maintenance_element_id": mine}, headers=admin)
    assert r.status_code == 201 and r.json()["maintenance_element_id"] == mine


def test_a_relinked_ledger_moves_its_spend_to_the_new_element(client, db):
    society, admin, manager, _ = _budget_rig(db, "l4")
    security = _charge_from_element(client, manager, society.id, "security", default_amount="1")
    _bill(client, admin, society.id, "security", "12000.00", date.today())
    _bill(client, admin, society.id, "cctv", "6000.00", date.today())
    s = client.get(f"{B}/charges/{society.id}/budget-suggestions", headers=manager).json()["suggestions"][0]
    assert s["spent"] == "18000.00"
    cctv = _ledgers(client, admin, society.id)["cctv_maintenance"]
    client.patch(f"{L}/{cctv['id']}", json={"maintenance_element_id": None}, headers=admin)
    s = client.get(f"{B}/charges/{society.id}/budget-suggestions", headers=manager).json()
    assert s["suggestions"][0]["spent"] == "12000.00" and s["suggestions"][0]["charge_id"] == security["id"]
    assert [u["name"] for u in s["unlinked"]] == ["CCTV & Security Systems Maintenance"]


# ── A charge head that bills from expenses ────────────────────────────────────

def _auto_rig(client, db, tag):
    society, flat1, flat2, manager, *_ = _rig(db, tag)
    admin = make_user(db, f"adm@auto{tag}.com", role="Society Admin")
    h = manager["headers"]
    return society, flat1, flat2, h, admin["headers"]


def test_budget_from_expenses_needs_an_element_and_a_suggestible_basis(client, db):
    society, flat1, flat2, h, _ = _auto_rig(client, db, "a1")
    r = _charge(client, h, society.id, auto_from_expenses=True)
    assert r.status_code == 422                                           # not made from an element
    for bad in (0, 37):
        assert _charge(client, h, society.id, expense_months=bad).status_code == 422
    sinking = _charge_from_element(client, h, society.id, "sinking_fund")
    r = client.patch(f"{B}/charges/{sinking['id']}", json={"auto_from_expenses": True}, headers=h)
    assert r.status_code == 422
    water = _charge_from_element(client, h, society.id, "water_charges", auto_from_expenses=True, expense_months=6)
    assert water["auto_from_expenses"] is True and water["expense_months"] == 6
    r = client.patch(f"{B}/charges/{water['id']}", json={"auto_from_expenses": None}, headers=h)
    assert r.status_code == 200 and r.json()["auto_from_expenses"] is True      # null is ignored


def test_bills_use_the_spend_when_budget_from_expenses_is_on(client, db):
    society, flat1, flat2, h, admin = _auto_rig(client, db, "a2")
    _charge_from_element(client, h, society.id, "housekeeping", basis="fixed", default_amount="1",
                         auto_from_expenses=True)
    _bill(client, admin, society.id, "housekeeping", "6000.00", date.today())   # this month only
    cycle_id = _cycle(client, h, society.id).json()["id"]
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h).json()
    # 6,000 in 1 month → 72,000 a year ÷ 2 flats ÷ 12 = ₹3,000 per flat per month
    line = pv["flats"][0]["lines"][0]
    assert line["amount"] == "3000.00"
    _generate(client, h, cycle_id)
    bill, lines = _lines(db, flat1)
    assert [l.amount for l in lines.values()] == [3000]


def test_a_head_with_no_spend_is_billed_at_its_typed_amount_with_a_warning(client, db):
    society, flat1, flat2, h, admin = _auto_rig(client, db, "a3")
    _charge_from_element(client, h, society.id, "housekeeping", basis="fixed", default_amount="450",
                         auto_from_expenses=True)
    cycle_id = _cycle(client, h, society.id).json()["id"]
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h).json()
    assert pv["flats"][0]["lines"][0]["amount"] == "450.00"
    assert any("no expenses are recorded" in w for w in pv["warnings"])


def test_without_the_switch_the_typed_amount_is_used_whatever_was_spent(client, db):
    society, flat1, flat2, h, admin = _auto_rig(client, db, "a4")
    _charge_from_element(client, h, society.id, "housekeeping", basis="fixed", default_amount="450")
    _bill(client, admin, society.id, "housekeeping", "6000.00", date.today())
    cycle_id = _cycle(client, h, society.id).json()["id"]
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h).json()
    assert pv["flats"][0]["lines"][0]["amount"] == "450.00"


# ── Fines and additional charges ──────────────────────────────────────────────

def test_a_fine_lands_on_the_flats_next_bill_and_only_there(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "f1")
    h = manager["headers"]
    _charge(client, h, society.id)
    r = _fine(client, h, society, flat1)
    assert r.status_code == 201, r.text
    fine = r.json()
    assert fine["status"] == "active" and fine["flat_number"] == "101" and fine["amount"] == "500.00"
    cycle_id = _cycle(client, h, society.id).json()["id"]
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h).json()
    by_flat = {f["flat_label"]: f for f in pv["flats"]}
    assert [l["description"] for l in by_flat["Tower A / 101"]["lines"]] == ["Maintenance", "Fine — Late parking"]
    assert by_flat["Tower A / 101"]["total"] == "3000.00" and by_flat["Tower A / 102"]["total"] == "2500.00"
    _generate(client, h, cycle_id)
    bill, lines = _lines(db, flat1)
    assert lines["Fine — Late parking"].amount == 500 and lines["Fine — Late parking"].tax_amount == 0
    assert bill.total_amount == 3000
    done = client.get(f"{B}/flat-charges/society/{society.id}", headers=h).json()[0]
    assert done["status"] == "billed" and done["bill_id"] == str(bill.id) and done["invoice_number"] == bill.invoice_number


def test_cancelling_the_bill_releases_the_fine_for_the_next_one(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f2")
    h = manager["headers"]
    _charge(client, h, society.id)
    _fine(client, h, society, flat1)
    cycle_id = _cycle(client, h, society.id).json()["id"]
    _generate(client, h, cycle_id)
    bill, _ = _lines(db, flat1)
    assert client.post(f"{B}/bills/{bill.id}/cancel", json={"reason": "Wrong amount"}, headers=h).status_code == 200
    fine = client.get(f"{B}/flat-charges/society/{society.id}", headers=h).json()[0]
    assert fine["status"] == "active" and fine["bill_id"] is None


def test_a_billed_fine_cannot_be_cancelled_but_an_unbilled_one_can(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f3")
    h = manager["headers"]
    _charge(client, h, society.id)
    first = _fine(client, h, society, flat1).json()
    second = _fine(client, h, society, flat2, title="Noise").json()
    r = client.post(f"{B}/flat-charges/{second['id']}/cancel", json={"reason": " "}, headers=h)
    assert r.status_code == 422                                                     # reason needed
    r = client.post(f"{B}/flat-charges/{second['id']}/cancel", json={"reason": "Waived by committee"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.post(f"{B}/flat-charges/{second['id']}/cancel", json={"reason": "again"}, headers=h).status_code == 409
    cycle_id = _cycle(client, h, society.id).json()["id"]
    _generate(client, h, cycle_id)
    assert not db.query(InvoiceLineItem).filter(InvoiceLineItem.description == "Fine — Noise").count()
    r = client.post(f"{B}/flat-charges/{first['id']}/cancel", json={"reason": "oops"}, headers=h)
    assert r.status_code == 409 and "cancel that bill" in r.json()["detail"]


def test_a_recurring_charge_is_billed_every_cycle_until_it_ends(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f4")
    h = manager["headers"]
    _charge(client, h, society.id)
    today = date.today()
    r = _fine(client, h, society, flat1, kind="extra", title="Club fee", amount="200.00", recurring=True,
              gst_applicable=True)
    assert r.status_code == 201 and r.json()["gst_applicable"] is True
    c1 = _cycle(client, h, society.id, name="Cycle 1").json()["id"]
    _generate(client, h, c1)
    assert client.get(f"{B}/flat-charges/society/{society.id}", headers=h).json()[0]["status"] == "active"
    cycle2 = client.post(f"{B}/cycles", json={
        "society_id": str(society.id), "name": "Cycle 2", "cycle_start": str(today + timedelta(days=31)),
        "cycle_end": str(today + timedelta(days=60)), "due_date": str(today + timedelta(days=70))}, headers=h)
    assert cycle2.status_code == 201, cycle2.text
    pv = client.get(f"{B}/cycles/{cycle2.json()['id']}/preview", headers=h).json()
    line = next(l for f in pv["flats"] for l in f["lines"] if l["description"] == "Club fee")
    assert line["tax_percent"] != "0" or line["tax_amount"] != "0.00"              # an extra may carry GST
    ended = _fine(client, h, society, flat2, kind="extra", title="Old fee", amount="50.00", recurring=True,
                  effective_date=str(today - timedelta(days=90)), end_date=str(today - timedelta(days=30)))
    assert ended.status_code == 201
    pv = client.get(f"{B}/cycles/{cycle2.json()['id']}/preview", headers=h).json()
    assert not any(l["description"] == "Old fee" for f in pv["flats"] for l in f["lines"])


def test_a_future_dated_charge_waits_for_its_cycle(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f5")
    h = manager["headers"]
    _charge(client, h, society.id)
    _fine(client, h, society, flat1, effective_date=str(date.today() + timedelta(days=90)))
    cycle_id = _cycle(client, h, society.id).json()["id"]
    pv = client.get(f"{B}/cycles/{cycle_id}/preview", headers=h).json()
    assert all(len(f["lines"]) == 1 for f in pv["flats"])


def test_a_fine_posts_to_the_fines_ledger_not_interest(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f6")
    h = manager["headers"]
    _charge(client, h, society.id)
    _fine(client, h, society, flat1)
    cycle_id = _cycle(client, h, society.id).json()["id"]
    _generate(client, h, cycle_id)
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    from app.modules.accounts.models.accounts import VoucherEntry
    fines = db.query(Account).filter_by(society_id=society.id, system_key="fines_penalties").one()
    credited = sum(e.credit for e in db.query(VoucherEntry).filter_by(account_id=fines.id))
    interest = db.query(Account).filter_by(society_id=society.id, system_key="interest_on_arrears").first()
    assert credited == 500
    if interest is not None:
        assert not sum(e.credit for e in db.query(VoucherEntry).filter_by(account_id=interest.id))


def test_flat_charge_input_is_checked(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f7")
    other = make_society(db, "Elsewhere")
    from tests.conftest import make_wing, make_flat
    foreign = make_flat(db, make_wing(db, other.id, "Z").id, "Z-1")
    h = manager["headers"]
    for bad in ({"amount": "0"}, {"amount": "-5"}, {"amount": "10000000000"}, {"amount": "1.234"},
                {"title": "  "}, {"title": "t" * 151}, {"reason": "r" * 1001}, {"kind": "tax"},
                {"effective_date": "1899-12-31"}, {"end_date": "2000-01-01", "recurring": True},
                {"end_date": str(date.today() + timedelta(days=5))}):          # an end date needs recurring
        assert _fine(client, h, society, flat1, **bad).status_code == 422, bad
    assert _fine(client, h, society, foreign).status_code == 422                # another society's flat
    ok = _fine(client, h, society, flat1, title="  Late   parking ", reason="  Bay  ")
    assert ok.status_code == 201 and ok.json()["title"] == "Late parking" and ok.json()["reason"] == "Bay"


def test_who_can_add_and_see_flat_charges(client, db):
    society, flat1, flat2, manager, resident, other_res = _rig(db, "f8")
    other = make_society(db, "Rival Society")
    oadmin = make_user(db, "oadm@f8.com", role="Society Admin")
    oadmin["user"].society_id = other.id
    manager["user"].society_id = society.id
    db.commit()
    h = manager["headers"]
    assert _fine(client, resident["headers"], society, flat1).status_code == 403
    fine = _fine(client, h, society, flat1).json()
    assert _fine(client, oadmin["headers"], society, flat1).status_code == 403
    assert client.get(f"{B}/flat-charges/society/{society.id}", headers=resident["headers"]).status_code == 403
    assert client.get(f"{B}/flat-charges/society/{society.id}", headers=oadmin["headers"]).status_code == 403
    assert client.post(f"{B}/flat-charges/{fine['id']}/cancel", json={"reason": "x"},
                       headers=oadmin["headers"]).status_code == 404
    # A member sees their own flat's charges, not a neighbour's
    mine = client.get(f"{B}/flat-charges/flat/{flat1.id}", headers=resident["headers"])
    assert mine.status_code == 200 and [c["title"] for c in mine.json()] == ["Late parking"]
    assert client.get(f"{B}/flat-charges/flat/{flat1.id}", headers=other_res["headers"]).status_code == 404
    assert client.get(f"{B}/flat-charges/flat/{flat1.id}", headers=oadmin["headers"]).status_code == 404


def test_the_flats_member_is_told_about_a_fine(client, db):
    society, flat1, flat2, manager, resident, other_res = _rig(db, "f9")
    _fine(client, manager["headers"], society, flat1)
    mine = db.query(Notification).filter_by(user_id=resident["user"].id).all()
    assert len(mine) == 1 and "fine" in mine[0].title.lower() and "500" in mine[0].body
    assert not db.query(Notification).filter_by(user_id=other_res["user"].id).count()


def test_list_filters_and_paging(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "f10")
    h = manager["headers"]
    _fine(client, h, society, flat1)
    cancelled = _fine(client, h, society, flat2).json()
    client.post(f"{B}/flat-charges/{cancelled['id']}/cancel", json={"reason": "waived"}, headers=h)
    url = f"{B}/flat-charges/society/{society.id}"
    assert len(client.get(url, headers=h).json()) == 2
    assert [c["flat_number"] for c in client.get(url, params={"status": "active"}, headers=h).json()] == ["101"]
    assert [c["flat_number"] for c in client.get(url, params={"flat_id": str(flat2.id)}, headers=h).json()] == ["102"]
    assert client.get(url, params={"limit": 0}, headers=h).status_code == 422
    assert client.get(url, params={"skip": -1}, headers=h).status_code == 422
    assert len(client.get(f"{B}/flat-charges/flat/{flat2.id}", headers=h).json()) == 0   # cancelled ones are hidden
