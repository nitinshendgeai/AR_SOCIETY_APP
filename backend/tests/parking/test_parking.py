"""Parking management tests — zone, slot, allocation workflow, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _create_zone(client, headers, society_id, name="Block A"):
    r = client.post(
        "/api/v1/parking/zones",
        json={"society_id": str(society_id), "name": name, "code": name[:2].upper()},
        headers=headers,
    )
    return r


def _create_slot(client, headers, society_id, zone_id, slot_num="P-001"):
    r = client.post(
        "/api/v1/parking/slots",
        json={
            "society_id": str(society_id),
            "zone_id":    str(zone_id),
            "slot_number": slot_num,
            "slot_type":  "resident",
        },
        headers=headers,
    )
    return r


def test_create_zone_success(client, db):
    admin   = make_user(db, "adm@park.com", role="Society Admin")
    society = make_society(db, "Parking Society")
    r = _create_zone(client, admin["headers"], society.id)
    assert r.status_code == 201
    assert r.json()["name"] == "Block A"


def test_create_zone_requires_admin_or_committee(client, db):
    resident = make_user(db, "res@park.com", role="Resident")
    society  = make_society(db, "Parking Society 2")
    r = _create_zone(client, resident["headers"], society.id, "Resident Zone")
    assert r.status_code == 403


def test_create_slot_success(client, db):
    admin   = make_user(db, "adm2@park.com", role="Society Admin")
    society = make_society(db, "Parking Society 3")
    zr      = _create_zone(client, admin["headers"], society.id, "Zone C")
    zone_id = zr.json()["id"]
    r = _create_slot(client, admin["headers"], society.id, zone_id)
    assert r.status_code == 201
    assert r.json()["slot_number"] == "P-001"
    assert r.json()["status"] == "available"


def test_list_slots_by_zone(client, db):
    admin   = make_user(db, "adm3@park.com", role="Society Admin")
    society = make_society(db, "Parking Society 4")
    zr      = _create_zone(client, admin["headers"], society.id, "Zone D")
    zone_id = zr.json()["id"]
    _create_slot(client, admin["headers"], society.id, zone_id, "P-101")
    _create_slot(client, admin["headers"], society.id, zone_id, "P-102")
    r = client.get(f"/api/v1/parking/slots/zone/{zone_id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_allocate_slot_to_resident(client, db):
    admin    = make_user(db, "adm4@park.com", role="Society Admin")
    resident = make_user(db, "res2@park.com", role="Resident")
    society  = make_society(db, "Parking Society 5")
    zr       = _create_zone(client, admin["headers"], society.id, "Zone E")
    zone_id  = zr.json()["id"]
    sr       = _create_slot(client, admin["headers"], society.id, zone_id, "P-201")
    slot_id  = sr.json()["id"]
    from datetime import date
    r = client.post(
        "/api/v1/parking/allocations",
        json={
            "society_id":        str(society.id),
            "slot_id":           slot_id,
            "allocated_to_user": str(resident["user"].id),
            "allocation_type":   "resident",
            "start_date":        str(date.today()),
        },
        headers=admin["headers"],
    )
    assert r.status_code == 201
    assert r.json()["slot_id"] == slot_id


def test_duplicate_allocation_rejected(client, db):
    admin   = make_user(db, "adm5@park.com", role="Society Admin")
    society = make_society(db, "Parking Society 6")
    zr      = _create_zone(client, admin["headers"], society.id, "Zone F")
    zone_id = zr.json()["id"]
    sr      = _create_slot(client, admin["headers"], society.id, zone_id, "P-301")
    slot_id = sr.json()["id"]
    from datetime import date
    payload = {
        "society_id":      str(society.id),
        "slot_id":         slot_id,
        "allocation_type": "resident",
        "start_date":      str(date.today()),
    }
    r1 = client.post("/api/v1/parking/allocations", json=payload,
                     headers=admin["headers"])
    assert r1.status_code == 201
    r2 = client.post("/api/v1/parking/allocations", json=payload,
                     headers=admin["headers"])
    assert r2.status_code in (400, 409)


def test_list_all_slots_by_society(client, db):
    admin   = make_user(db, "adm7@park.com", role="Society Admin")
    society = make_society(db, "Parking Society 8")
    zr      = _create_zone(client, admin["headers"], society.id, "Zone H")
    zone_id = zr.json()["id"]
    _create_slot(client, admin["headers"], society.id, zone_id, "H-01")
    _create_slot(client, admin["headers"], society.id, zone_id, "H-02")
    r = client.get(f"/api/v1/parking/slots/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 2


def test_unauthenticated_cannot_create_zone(client, db):
    r = client.post("/api/v1/parking/zones", json={"name": "Sneaky"})
    assert r.status_code in (401, 403)


def test_allocation_out_includes_slot_flat_vehicle_details(client, db):
    """AllocationOut enriches the raw slot_id/flat_id/vehicle_id with their
    human-readable slot number, flat number, wing name, and vehicle number
    (via read-only model properties) — the mobile allocations screen
    displays these directly without an extra per-row lookup."""
    from tests.conftest import make_wing, make_flat
    admin   = make_user(db, "adm6@park.com", role="Society Admin")
    society = make_society(db, "Parking Society 7")
    wing    = make_wing(db, society.id, "Wing P")
    flat    = make_flat(db, wing.id, "P-101")

    vr = client.post("/api/v1/vehicles/", json={
        "society_id": str(society.id), "flat_id": str(flat.id),
        "vehicle_number": "MH12CC0001",
    }, headers=admin["headers"])
    vehicle_id = vr.json()["id"]

    zr      = _create_zone(client, admin["headers"], society.id, "Zone P")
    zone_id = zr.json()["id"]
    sr      = _create_slot(client, admin["headers"], society.id, zone_id, "P-P1")
    slot_id = sr.json()["id"]

    from datetime import date
    r = client.post("/api/v1/parking/allocations", json={
        "society_id": str(society.id), "slot_id": slot_id,
        "flat_id": str(flat.id), "vehicle_id": vehicle_id,
        "allocation_type": "resident", "start_date": str(date.today()),
    }, headers=admin["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slot_number"] == "P-P1"
    assert body["flat_number"] == "P-101"
    assert body["wing_name"] == "Wing P"
    assert body["vehicle_number"] == "MH12CC0001"
