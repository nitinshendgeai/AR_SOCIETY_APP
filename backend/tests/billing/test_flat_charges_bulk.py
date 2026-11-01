"""The same fine or additional charge on many flats at once (named flats, or every let-out flat)."""
from datetime import date

from app.models.flat import OccupancyStatus
from app.modules.billing.models.billing import FlatCharge, FlatChargeStatus, InvoiceLineItem, MaintenanceBill
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
from tests.conftest import make_flat, make_society, make_wing

B = "/api/v1/billing"


def _body(society, **kw):
    return {"society_id": str(society.id), "kind": "extra", "title": "Non-occupancy charges", "amount": "200.00",
            "effective_date": str(date.today()), **kw}


def _rented_rig(db, tag):
    """Flats 101 and 102 let out, 103 owner occupied (and one let-out flat in another wing)."""
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    from app.models.wing import Wing
    wing_b = Wing(society_id=society.id, name="Tower B", code="TB")
    db.add(wing_b)
    db.flush()
    flat3 = make_flat(db, flat1.wing_id, "103")
    flat4 = make_flat(db, wing_b.id, "201")
    flat1.occupancy_status = flat2.occupancy_status = flat4.occupancy_status = OccupancyStatus.TENANT_OCCUPIED
    flat3.occupancy_status = OccupancyStatus.OWNER_OCCUPIED
    db.commit()
    return society, (flat1, flat2, flat3, flat4), manager, resident


def test_all_rented_flats_get_the_charge_and_owner_occupied_ones_do_not(client, db):
    society, (f1, f2, f3, f4), manager, _ = _rented_rig(db, "bk1")
    r = client.post(f"{B}/flat-charges/bulk", headers=manager["headers"], json=_body(society, rented=True))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == 3 and out["skipped"] == 0 and not out["dry_run"]
    assert out["flat_labels"] == ["Tower A / 101", "Tower A / 102", "Tower B / 201"]
    got = {c.flat_id for c in db.query(FlatCharge).filter_by(society_id=society.id)}
    assert got == {f1.id, f2.id, f4.id}
    assert all(c.status == FlatChargeStatus.ACTIVE and c.title == "Non-occupancy charges"
               for c in db.query(FlatCharge).filter_by(society_id=society.id))


def test_a_dry_run_writes_nothing_and_sending_it_twice_does_not_double_it(client, db):
    society, flats, manager, _ = _rented_rig(db, "bk2")
    h = manager["headers"]
    dry = client.post(f"{B}/flat-charges/bulk", headers=h, json=_body(society, rented=True, dry_run=True)).json()
    assert dry["dry_run"] and dry["created"] == 3
    assert db.query(FlatCharge).filter_by(society_id=society.id).count() == 0
    client.post(f"{B}/flat-charges/bulk", headers=h, json=_body(society, rented=True))
    again = client.post(f"{B}/flat-charges/bulk", headers=h, json=_body(society, rented=True)).json()
    assert again["created"] == 0 and again["skipped"] == 3
    assert db.query(FlatCharge).filter_by(society_id=society.id).count() == 3
    other = client.post(f"{B}/flat-charges/bulk", headers=h, json=_body(society, rented=True, amount="250.00")).json()
    assert other["created"] == 3                                        # a different amount is a different charge


def test_one_wing_or_named_flats(client, db):
    society, (f1, f2, f3, f4), manager, _ = _rented_rig(db, "bk3")
    h = manager["headers"]
    wing = client.post(f"{B}/flat-charges/bulk", headers=h,
                       json=_body(society, rented=True, wing_id=str(f4.wing_id))).json()
    assert wing["flat_labels"] == ["Tower B / 201"]
    named = client.post(f"{B}/flat-charges/bulk", headers=h,
                        json=_body(society, flat_ids=[str(f3.id), str(f1.id)], title="Hall booking")).json()
    assert named["created"] == 2 and named["flat_labels"] == ["Tower A / 101", "Tower A / 103"]


def test_the_flats_must_be_chosen_one_way_and_belong_to_the_society(client, db):
    society, (f1, f2, f3, f4), manager, resident = _rented_rig(db, "bk4")
    h = manager["headers"]
    url = f"{B}/flat-charges/bulk"
    assert client.post(url, headers=h, json=_body(society)).status_code == 422                       # neither
    assert client.post(url, headers=h, json=_body(society, rented=True, flat_ids=[str(f1.id)])).status_code == 422
    rival = make_society(db, "Rival bk4")
    rival_flat = make_flat(db, make_wing(db, rival.id, "R").id, "1")
    assert client.post(url, headers=h, json=_body(society, flat_ids=[str(rival_flat.id)])).status_code == 422
    assert client.post(url, headers=h, json=_body(society, rented=True, amount="0")).status_code == 422
    assert client.post(url, headers=h, json=_body(society, rented=True, end_date=str(date.today()))).status_code == 422
    assert client.post(url, headers=resident["headers"], json=_body(society, rented=True)).status_code == 403
    assert db.query(FlatCharge).filter_by(society_id=society.id).count() == 0


def test_the_charge_goes_on_the_next_bill_as_non_occupancy_income(client, db):
    society, (f1, f2, f3, f4), manager, _ = _rented_rig(db, "bk5")
    h = manager["headers"]
    _charge(client, h, society.id)
    client.post(f"{B}/flat-charges/bulk", headers=h, json=_body(society, rented=True))
    cycle = _cycle(client, h, society.id).json()
    assert client.post(f"{B}/cycles/{cycle['id']}/generate-bills", headers=h).status_code == 200
    for flat, expected in ((f1, True), (f3, False)):
        bill = db.query(MaintenanceBill).filter_by(flat_id=flat.id).one()
        lines = {l.description: l.amount for l in db.query(InvoiceLineItem).filter_by(bill_id=bill.id)}
        assert ("Non-occupancy charges" in lines) is expected
    from app.modules.accounts.services.chart_of_accounts import bill_line_ledger_key
    from types import SimpleNamespace
    line = SimpleNamespace(description="Non-occupancy charges", charge_type=None)
    assert bill_line_ledger_key(line) == "non_occupancy"
