"""A parking charge head can charge slots held for two-wheelers at a rate of their own."""
from datetime import date

from app.models.vehicle import Vehicle, VehicleType
from app.modules.parking.models.parking import (
    AllocationStatus, ParkingAllocation, ParkingSlot, ParkingZone, SlotType,
)
from tests.billing.test_maintenance_calculation import _charge, _cycle, _preview, _rig

B = "/api/v1/billing"


def _slot(db, society, zone, flat, number, vehicle_type=None, own_charge=None):
    slot = ParkingSlot(society_id=society.id, zone_id=zone.id, slot_number=number, slot_type=SlotType.RESIDENT)
    db.add(slot)
    db.flush()
    vehicle = None
    if vehicle_type:
        vehicle = Vehicle(society_id=society.id, flat_id=flat.id, vehicle_number=f"MH12{number}", vehicle_type=vehicle_type)
        db.add(vehicle)
        db.flush()
    db.add(ParkingAllocation(society_id=society.id, slot_id=slot.id, flat_id=flat.id, vehicle_id=vehicle.id if vehicle else None,
                             allocation_type=SlotType.RESIDENT, status=AllocationStatus.ACTIVE,
                             start_date=date.today(), monthly_charge=own_charge))


def _rig_slots(db, tag):
    society, flats, h = _rig(db, tag)
    zone = ParkingZone(society_id=society.id, name="Basement")
    db.add(zone)
    db.flush()
    return society, flats, h, zone


def _lines(preview, flat_index=0):
    return {l["description"]: l["amount"] for l in preview["flats"][flat_index]["lines"]}


def test_two_wheelers_pay_their_own_rate_on_their_own_line(client, db):
    society, flats, h, zone = _rig_slots(db, "tw1")
    _slot(db, society, zone, flats[0], "C1", VehicleType.CAR)
    _slot(db, society, zone, flats[0], "C2", VehicleType.CAR)
    _slot(db, society, zone, flats[0], "B1", VehicleType.MOTORCYCLE)
    _slot(db, society, zone, flats[0], "B2", VehicleType.SCOOTER)
    db.commit()
    _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking", two_wheeler_rate="150")
    lines = _lines(_preview(client, h, _cycle(client, h, society.id)))
    assert lines == {"Parking — cars": "1000.00", "Parking — two-wheelers": "300.00"}   # 2 × 500 and 2 × 150


def test_without_a_two_wheeler_rate_every_slot_pays_the_heads_rate_on_one_line(client, db):
    society, flats, h, zone = _rig_slots(db, "tw2")
    _slot(db, society, zone, flats[0], "C1", VehicleType.CAR)
    _slot(db, society, zone, flats[0], "B1", VehicleType.MOTORCYCLE)
    db.commit()
    _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking")
    assert _lines(_preview(client, h, _cycle(client, h, society.id))) == {"Parking": "1000.00"}


def test_a_flat_with_only_cars_keeps_the_single_line(client, db):
    society, flats, h, zone = _rig_slots(db, "tw3")
    _slot(db, society, zone, flats[0], "C1", VehicleType.CAR)
    _slot(db, society, zone, flats[0], "C2", None)                     # no vehicle on it: treated as a car's
    db.commit()
    _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking", two_wheeler_rate="150")
    assert _lines(_preview(client, h, _cycle(client, h, society.id))) == {"Parking": "1000.00"}


def test_a_slots_own_charge_still_wins_over_both_rates(client, db):
    society, flats, h, zone = _rig_slots(db, "tw4")
    _slot(db, society, zone, flats[0], "B1", VehicleType.MOTORCYCLE, own_charge=400)
    _slot(db, society, zone, flats[0], "B2", VehicleType.MOTORCYCLE)
    db.commit()
    _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking", two_wheeler_rate="150")
    # one two-wheeler slot at its own ₹400, the other at the two-wheeler rate ₹150; no cars, so no car line
    assert _lines(_preview(client, h, _cycle(client, h, society.id))) == {"Parking — two-wheelers": "550.00"}


def test_the_rate_is_only_for_a_parking_head_and_can_be_changed_and_cleared(client, db):
    society, flats, h, zone = _rig_slots(db, "tw5")
    bad = client.post(f"{B}/charges", headers=h, json={
        "society_id": str(society.id), "charge_type": "maintenance", "name": "Service", "basis": "fixed",
        "default_amount": "100", "two_wheeler_rate": "50"})
    assert bad.status_code == 422
    head = _charge(client, h, society.id, "Parking", "parking", "500", charge_type="parking", two_wheeler_rate="150")
    assert head["two_wheeler_rate"] == "150.00"
    r = client.patch(f"{B}/charges/{head['id']}", headers=h, json={"two_wheeler_rate": "200"})
    assert r.status_code == 200 and r.json()["two_wheeler_rate"] == "200.00"
    r = client.patch(f"{B}/charges/{head['id']}", headers=h, json={"two_wheeler_rate": None})
    assert r.json()["two_wheeler_rate"] is None
    r = client.patch(f"{B}/charges/{head['id']}", headers=h, json={"two_wheeler_rate": "120"})
    assert r.json()["two_wheeler_rate"] == "120.00"
    # moving the head off parking drops the rate; setting one on a non-parking head is refused
    r = client.patch(f"{B}/charges/{head['id']}", headers=h, json={"basis": "fixed"})
    assert r.status_code == 200 and r.json()["two_wheeler_rate"] is None
    assert client.patch(f"{B}/charges/{head['id']}", headers=h, json={"two_wheeler_rate": "90"}).status_code == 422
