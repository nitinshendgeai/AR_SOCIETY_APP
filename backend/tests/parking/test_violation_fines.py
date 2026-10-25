"""A parking fine is owed by a flat: it goes on the flat's next maintenance bill, as a fine (Fines & Penalties). The manager
or the committee charges it; a guard only records the violation."""
from decimal import Decimal
from uuid import UUID

import pytest

from app.models.vehicle import Vehicle
from app.modules.billing.models.billing import FlatCharge, FlatChargeKind, FlatChargeStatus
from tests.billing.test_maintenance_billing import _charge, _cycle
from tests.conftest import make_flat, make_society, make_user, make_wing

P = "/api/v1/parking"


@pytest.fixture
def soc(db):
    society = make_society(db, "Parking Fines Society")
    wing = make_wing(db, society.id, "A")
    flat, other_flat = make_flat(db, wing.id, "101"), make_flat(db, wing.id, "102")
    people = {}
    for key, role in (("admin", "Society Admin"), ("manager", "Manager"), ("guard", "Security Staff")):
        who = make_user(db, f"{key}@pf.test", role=role)
        who["user"].society_id = society.id
        people[key] = who
    db.add(Vehicle(society_id=society.id, flat_id=flat.id, vehicle_number="MH12AB1234"))
    db.commit()
    return {"society": society, "flat": flat, "other_flat": other_flat, **people}


def _report(client, who, soc, number="MH12AB1234", fine=500, **extra):
    r = client.post(f"{P}/violations", headers=who["headers"], json={
        "society_id": str(soc["society"].id), "vehicle_number": number, "violation_type": "wrong_slot",
        "fine_amount": fine, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _charges(db, violation_id):
    return db.query(FlatCharge).filter(FlatCharge.source_type == "parking_violation",
                                       FlatCharge.source_id == UUID(violation_id)).all()


def _balance(client, soc, key):
    r = client.get(f"/api/v1/accounts/chart/{soc['society'].id}", headers=soc["admin"]["headers"])
    for group in r.json():
        for acc in group["accounts"]:
            if acc["system_key"] == key:
                return Decimal(acc["balance"])
    raise AssertionError(key)


def _issue_bills(client, soc):
    h, sid = soc["admin"]["headers"], soc["society"].id
    assert _charge(client, h, sid, amount="1000.00").status_code == 201
    cycle_id = _cycle(client, h, sid).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200


def test_a_fine_the_manager_records_goes_on_the_flats_next_bill(client, soc, db):
    v = _report(client, soc["manager"], soc)
    assert v["fine_status"] == "active"
    (fc,) = _charges(db, v["id"])
    assert (fc.kind, fc.amount, fc.flat_id, fc.charge_type) == (FlatChargeKind.FINE, 500, soc["flat"].id, None)
    assert "MH12AB1234" in fc.title and "wrong slot" in fc.title

    _issue_bills(client, soc)
    db.refresh(fc)
    assert fc.status == FlatChargeStatus.BILLED
    assert _balance(client, soc, "fines_penalties") == Decimal("-500")          # income, in Fines & Penalties
    assert _balance(client, soc, "members_dues") == Decimal("2500")             # both flats owe 1000 maintenance; one also owes the 500 fine


def test_a_fine_a_guard_records_waits_for_the_manager_to_charge_it(client, soc, db):
    v = _report(client, soc["guard"], soc)
    assert v["fine_amount"] == 500 and v["fine_status"] is None and _charges(db, v["id"]) == []
    assert client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=soc["guard"]["headers"]).status_code == 403

    r = client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=soc["manager"]["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["fine_status"] == "active" and len(_charges(db, v["id"])) == 1
    again = client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=soc["manager"]["headers"])
    assert again.status_code == 409                                              # not charged twice
    assert len(_charges(db, v["id"])) == 1


def test_a_vehicle_not_registered_to_a_flat_needs_the_flat_chosen(client, soc, db):
    v = _report(client, soc["manager"], soc, number="KA01XY9999")
    assert v["fine_status"] is None and _charges(db, v["id"]) == []
    h = soc["manager"]["headers"]
    assert client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=h).status_code == 422
    r = client.post(f"{P}/violations/{v['id']}/fine", json={"flat_id": str(soc["other_flat"].id), "amount": 300}, headers=h)
    assert r.status_code == 200, r.text
    (fc,) = _charges(db, v["id"])
    assert (fc.flat_id, fc.amount) == (soc["other_flat"].id, 300)


def test_a_violation_with_no_fine_charges_nothing_and_needs_an_amount_to_be_charged(client, soc, db):
    v = _report(client, soc["manager"], soc, fine=None)
    assert v["fine_status"] is None and _charges(db, v["id"]) == []
    h = soc["manager"]["headers"]
    assert client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=h).status_code == 422
    assert client.post(f"{P}/violations/{v['id']}/fine", json={"amount": 250}, headers=h).status_code == 200


def test_a_fine_can_be_waived_until_it_is_on_a_bill(client, soc, db):
    h = soc["manager"]["headers"]
    v = _report(client, soc["manager"], soc)
    assert client.post(f"{P}/violations/{v['id']}/waive-fine", json={"reason": "x"}, headers=h).status_code == 422
    r = client.post(f"{P}/violations/{v['id']}/waive-fine", json={"reason": "First offence"}, headers=h)
    assert r.status_code == 200 and r.json()["fine_status"] == "cancelled"
    assert client.post(f"{P}/violations/{v['id']}/waive-fine", json={"reason": "First offence"}, headers=h).status_code == 409
    _issue_bills(client, soc)
    assert _balance(client, soc, "fines_penalties") == 0                         # nothing was billed
    # A waived fine can be charged again
    assert client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=h).status_code == 200

    billed = _report(client, soc["manager"], soc, number="MH12AB1234")
    cycle_two = _cycle(client, soc["admin"]["headers"], soc["society"].id, name="Nov 2026").json()["id"]
    client.post(f"/api/v1/billing/cycles/{cycle_two}/generate-bills", headers=soc["admin"]["headers"])
    client.post(f"/api/v1/billing/cycles/{cycle_two}/issue-all", headers=soc["admin"]["headers"])
    gone = client.post(f"{P}/violations/{billed['id']}/waive-fine", json={"reason": "Too late"}, headers=h)
    assert gone.status_code == 409 and "bill" in gone.json()["detail"]


def test_the_violation_list_shows_where_each_fine_stands(client, soc):
    _report(client, soc["manager"], soc)
    _report(client, soc["guard"], soc, number="KA01XY9999")
    rows = client.get(f"{P}/violations/society/{soc['society'].id}", headers=soc["manager"]["headers"]).json()
    assert {r["vehicle_number"]: r["fine_status"] for r in rows} == {"MH12AB1234": "active", "KA01XY9999": None}


def test_other_societies_violations_are_out_of_reach(client, soc, db):
    v = _report(client, soc["manager"], soc)
    other = make_society(db, "Another Society")
    stranger = make_user(db, "mgr2@pf.test", role="Manager")
    stranger["user"].society_id = other.id
    db.commit()
    assert client.post(f"{P}/violations/{v['id']}/fine", json={}, headers=stranger["headers"]).status_code == 404
    assert client.post(f"{P}/violations/{v['id']}/waive-fine", json={"reason": "Not yours"},
                       headers=stranger["headers"]).status_code == 404
