"""Deleting a billing cycle that has not been billed: nothing issued, so nothing owed and nothing posted."""
from uuid import UUID

from app.modules.billing.models.billing import BillingCycle, DueTracker, InvoiceLineItem, MaintenanceBill
from tests.conftest import place_in
from tests.billing.test_maintenance_billing import _charge, _cycle, _generated_cycle, _rig

B = "/api/v1/billing"


def _listed(client, h, society_id):
    return {c["id"]: c for c in client.get(f"{B}/cycles/{society_id}", headers=h).json()}


def test_a_cycle_with_no_bills_is_deleted(client, db):
    society, _f1, _f2, manager, _r, _o = _rig(db, "dc1")
    h = manager["headers"]
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert _listed(client, h, society.id)[cycle_id]["can_delete"] is True
    r = client.delete(f"{B}/cycles/{cycle_id}", headers=h)
    assert r.status_code == 200 and r.json()["deleted"] and r.json()["bills_removed"] == 0
    assert cycle_id not in _listed(client, h, society.id)
    assert client.delete(f"{B}/cycles/{cycle_id}", headers=h).status_code == 404


def test_bills_made_but_never_issued_go_with_the_cycle(client, db):
    society, flat1, _f2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "dc2")
    h = manager["headers"]
    assert _listed(client, h, society.id)[cycle_id]["can_delete"] is True
    r = client.delete(f"{B}/cycles/{cycle_id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["bills_removed"] == 2
    db.expire_all()
    assert db.query(BillingCycle).filter_by(id=UUID(cycle_id)).count() == 0
    assert db.query(MaintenanceBill).filter_by(society_id=society.id).count() == 0
    assert db.query(InvoiceLineItem).count() == 0
    for t in db.query(DueTracker).filter_by(flat_id=flat1.id):          # what generating counted is given back
        assert t.outstanding == 0 and t.total_billed == 0
    # the cycle can be made and billed again
    again = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"{B}/cycles/{again}/generate-bills", headers=h).status_code == 200


def test_a_cycle_with_issued_bills_cannot_be_deleted(client, db):
    society, _f1, _f2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "dc3")
    h = manager["headers"]
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    assert _listed(client, h, society.id)[cycle_id]["can_delete"] is False
    r = client.delete(f"{B}/cycles/{cycle_id}", headers=h)
    assert r.status_code == 409 and "issued" in r.json()["detail"]
    db.expire_all()
    assert db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id)).count() == 2


def test_only_the_committee_and_manager_delete_and_only_in_their_society(client, db):
    society, _f1, _f2, manager, resident, _o = _rig(db, "dc4")
    cycle_id = _cycle(client, manager["headers"], society.id).json()["id"]
    assert client.delete(f"{B}/cycles/{cycle_id}", headers=resident["headers"]).status_code == 403
    society2, _a, _b, other_manager, _r2, _o2 = _rig(db, "dc5")
    place_in(db, other_manager, society2)                        # a manager of another society
    assert client.delete(f"{B}/cycles/{cycle_id}", headers=other_manager["headers"]).status_code == 403
    assert cycle_id in _listed(client, manager["headers"], society.id)
