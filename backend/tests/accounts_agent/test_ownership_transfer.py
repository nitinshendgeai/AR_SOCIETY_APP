"""Recording an ownership transfer (Occupancy) and the Accounts Agent's handover checks reading it."""
from datetime import timedelta

import pytest

from app.models.occupancy_log import OccupancyEventType, OccupancyLog
from app.models.resident import Resident, ResidentType
from app.models.vehicle import Vehicle, VehicleType
from tests.accounts_agent.legal_helpers import ChargeType, LRig

API = "/api/v1/occupancy/ownership-transfer"


@pytest.fixture
def rig(db):
    return LRig(db, "own")


def _people(rig, flat):
    old = Resident(flat_id=flat.id, full_name="Asha Old", resident_type=ResidentType.OWNER, is_primary=True,
                   move_in_date=rig.today - timedelta(days=3000))
    new = Resident(flat_id=flat.id, full_name="Ravi New", resident_type=ResidentType.OWNER)
    rig.db.add_all([old, new])
    rig.db.commit()
    return old, new


def test_transfer_moves_owners_and_writes_the_event(client, rig, db):
    fl = rig.flat_rows[0]
    old, new = _people(rig, fl)
    car = Vehicle(society_id=rig.sid, flat_id=fl.id, resident_id=old.id, vehicle_number="MH12AB1111", vehicle_type=VehicleType.CAR)
    db.add(car)
    db.commit()
    when = rig.today - timedelta(days=10)
    r = client.post(API, headers=rig.admin["headers"], json={
        "flat_id": str(fl.id), "new_owner_id": str(new.id), "transfer_date": when.isoformat(),
        "share_certificate_no": "SC-101", "deed_reference": "REG/2026/4411"})
    assert r.status_code == 200, r.text
    db.expire_all()
    o, n = db.get(Resident, old.id), db.get(Resident, new.id)
    assert o.move_out_date == when and not o.is_active and not o.is_primary
    assert n.is_primary and n.move_in_date == when
    ev = db.query(OccupancyLog).filter(OccupancyLog.flat_id == fl.id,
                                       OccupancyLog.event_type == OccupancyEventType.OWNERSHIP_TRANSFER).one()
    assert ev.resident_id == new.id and "Asha Old" in ev.notes and "SC-101" in ev.notes and "REG/2026/4411" in ev.notes
    assert db.get(Vehicle, car.id).resident_id is None          # the old owner's vehicle is unassigned, as on any move-out


def test_transfer_validation_and_permissions(client, rig, db):
    fl, other_fl = rig.flat_rows[0], rig.flat_rows[1]
    old, new = _people(rig, fl)
    fam = Resident(flat_id=fl.id, full_name="Child", resident_type=ResidentType.FAMILY)
    stranger = Resident(flat_id=other_fl.id, full_name="Elsewhere", resident_type=ResidentType.OWNER)
    db.add_all([fam, stranger])
    db.commit()
    body = lambda **kw: {"flat_id": str(fl.id), "new_owner_id": str(new.id), "transfer_date": rig.today.isoformat(), **kw}
    assert client.post(API, headers=rig.manager["headers"], json=body()).status_code == 403
    assert client.post(API, headers=rig.admin["headers"], json=body(new_owner_id=str(fam.id))).status_code == 422
    assert client.post(API, headers=rig.admin["headers"], json=body(new_owner_id=str(stranger.id))).status_code == 404
    assert client.post(API, headers=rig.admin["headers"], json=body(
        transfer_date=(rig.today + timedelta(days=5)).isoformat())).status_code == 422
    assert client.post(API, headers=rig.admin["headers"], json=body(
        transfer_date=(old.move_in_date - timedelta(days=1)).isoformat())).status_code == 422
    other = LRig(db, "own2")
    assert client.post(API, headers=other.admin["headers"], json=body()).status_code == 404      # another society's flat


def test_agent_uses_the_recorded_transfer(client, rig, db):
    fl = rig.flat_rows[2]
    old, new = _people(rig, fl)
    when = rig.today - timedelta(days=30)
    cy = rig.cycle(when - timedelta(days=60), when - timedelta(days=31), due=when - timedelta(days=20), name="Before")
    rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 3000, 3000)])
    assert client.post(API, headers=rig.admin["headers"], json={
        "flat_id": str(fl.id), "new_owner_id": str(new.id), "transfer_date": when.isoformat(),
        "share_certificate_no": "SC-7"}).status_code == 200
    rig.scan()
    f = [x for x in rig.findings("A-HND-01") if x.flat_id == fl.id]
    assert len(f) == 1 and f[0].evidence["transfer_recorded"] is True and "SC-7" in f[0].evidence["transfer_notes"]
    assert "Asha Old" in f[0].explanation and "Ravi New" in f[0].explanation
    assert not [x for x in rig.findings("A-HND-04") if x.flat_id == fl.id]       # previous owner closed out properly
