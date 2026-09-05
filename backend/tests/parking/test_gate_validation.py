"""Gate vehicle validation — the pre-entry lookup a security guard runs
before opening the barrier, plus the access-log endpoint that now derives
authorization server-side instead of trusting the client."""
import pytest
from uuid import UUID as _UUID
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def rig(db):
    society = make_society(db, "Gate Validation Society")
    admin = make_user(db, "gvadm@test.com", role="Society Admin")
    guard = make_user(db, "gvguard@test.com", role="Security Staff")
    _set_society(db, admin["user"], society.id)
    _set_society(db, guard["user"], society.id)
    wing = make_wing(db, society.id, "Wing G")
    flat = make_flat(db, wing.id, "G-101")

    from app.models.resident import Resident
    from app.models.tenant import Tenant
    resident = Resident(flat_id=flat.id, full_name="Gate Resident")
    tenant = Tenant(flat_id=flat.id, full_name="Gate Tenant")
    db.add_all([resident, tenant])
    db.commit()
    db.refresh(resident)
    db.refresh(tenant)

    return {"society": society, "admin": admin, "guard": guard, "wing": wing,
            "flat": flat, "resident": resident, "tenant": tenant}


def _validate(client, guard_headers, society_id, vehicle_number):
    return client.get(
        f"/api/v1/parking/gate/validate/{society_id}/{vehicle_number}",
        headers=guard_headers,
    )


# 1. Registered resident vehicle WITH allotted parking → authorized, category resident, flat/owner/slot details
def test_resident_vehicle_with_allotment_authorized(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0001",
        "parking_slot": "P-101",
    }, headers=rig["admin"]["headers"])

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH12BB0001")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is True
    assert body["category"] == "resident"
    assert body["flat_number"] == "G-101"
    assert body["wing_name"] == "Wing G"
    assert body["owner_name"] == "Gate Resident"
    assert body["parking_slot"] == "P-101"


# 2. Registered tenant vehicle WITH allotted parking → category tenant
def test_tenant_vehicle_with_allotment_authorized(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "tenant_id": str(rig["tenant"].id), "vehicle_number": "MH12BB0002",
        "parking_slot": "P-102",
    }, headers=rig["admin"]["headers"])

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH12BB0002")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is True
    assert body["category"] == "tenant"
    assert body["owner_name"] == "Gate Tenant"


# 3. A vehicle number with spaces/hyphens matches its normalized stored form
def test_lookup_normalizes_vehicle_number(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0003",
        "parking_slot": "P-103",
    }, headers=rig["admin"]["headers"])

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "mh12-bb 0003")
    assert r.status_code == 200, r.text
    assert r.json()["authorized"] is True
    assert r.json()["vehicle_number"] == "MH12BB0003"


# 3b. Registered vehicle WITHOUT any allotted/rented parking → not authorized,
#     even though it belongs to a known resident — a household's un-allotted
#     second car should be flagged, not waved through.
def test_registered_vehicle_without_allotment_not_authorized(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0009",
    }, headers=rig["admin"]["headers"])

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH12BB0009")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is False
    assert body["category"] == "resident"
    assert body["owner_name"] == "Gate Resident"
    assert body["parking_slot"] is None


# 3c. A formal ParkingAllocation (no Vehicle.parking_slot set directly) also
#     counts as "allotted" — the two mechanisms are equivalent.
def test_active_allocation_counts_as_allotted(client, db, rig):
    vr = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0010",
    }, headers=rig["admin"]["headers"])
    vehicle_id = vr.json()["id"]

    zr = client.post("/api/v1/parking/zones", json={
        "society_id": str(rig["society"].id), "name": "Zone G",
    }, headers=rig["admin"]["headers"])
    zone_id = zr.json()["id"]
    sr = client.post("/api/v1/parking/slots", json={
        "society_id": str(rig["society"].id), "zone_id": zone_id, "slot_number": "G-P1",
    }, headers=rig["admin"]["headers"])
    slot_id = sr.json()["id"]

    from datetime import date
    ar = client.post("/api/v1/parking/allocations", json={
        "society_id": str(rig["society"].id), "slot_id": slot_id,
        "flat_id": str(rig["flat"].id), "vehicle_id": vehicle_id,
        "allocation_type": "resident", "start_date": str(date.today()),
    }, headers=rig["admin"]["headers"])
    assert ar.status_code == 201, ar.text

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH12BB0010")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is True
    assert body["parking_slot"] == "G-P1"


# 4. Active visitor parking vehicle → authorized, category visitor
def test_active_visitor_parking_authorized(client, db, rig):
    client.post("/api/v1/parking/visitor", json={
        "society_id": str(rig["society"].id),
        "vehicle_number": "MH12BB0004",
        "host_flat_id": str(rig["flat"].id),
        "purpose": "Guest",
    }, headers=rig["guard"]["headers"])

    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH12BB0004")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is True
    assert body["category"] == "visitor"
    assert body["flat_number"] == "G-101"


# 5. Unregistered vehicle → not authorized
def test_unregistered_vehicle_not_authorized(client, db, rig):
    r = _validate(client, rig["guard"]["headers"], rig["society"].id, "MH99ZZ9999")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorized"] is False
    assert body["category"] == "unregistered"


# 6. A resident (not security/admin) cannot call the gate validation endpoint
def test_resident_cannot_validate_gate(client, db, rig):
    resident_user = make_user(db, "gvres@test.com", role="Resident")
    _set_society(db, resident_user["user"], rig["society"].id)
    r = _validate(client, resident_user["headers"], rig["society"].id, "MH12BB0001")
    assert r.status_code == 403


# 7. A guard from a different society cannot validate against this one
def test_cross_society_validation_denied(client, db, rig):
    other_society = make_society(db, "Other Gate Society")
    other_guard = make_user(db, "othergvguard@test.com", role="Security Staff")
    _set_society(db, other_guard["user"], other_society.id)
    r = _validate(client, other_guard["headers"], rig["society"].id, "MH12BB0001")
    assert r.status_code == 403


# 8. POST /access-log ignores a spoofed authorization — it always re-derives
#    is_authorized/vehicle_id server-side from the same lookup as validate.
def test_access_log_derives_authorization_serverside(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0005",
        "parking_slot": "P-105",
    }, headers=rig["admin"]["headers"])

    # Registered vehicle with allotted parking -> log should be authorized
    r1 = client.post("/api/v1/parking/access-log", json={
        "society_id": str(rig["society"].id),
        "vehicle_number": "MH12BB0005",
        "access_type": "entry",
    }, headers=rig["guard"]["headers"])
    assert r1.status_code == 201, r1.text
    assert r1.json()["is_authorized"] is True

    # Unregistered vehicle -> log should be unauthorized even though the
    # client cannot even supply is_authorized/vehicle_id any more (the
    # schema no longer accepts those fields).
    r2 = client.post("/api/v1/parking/access-log", json={
        "society_id": str(rig["society"].id),
        "vehicle_number": "MH00UNKNOWN",
        "access_type": "entry",
    }, headers=rig["guard"]["headers"])
    assert r2.status_code == 201, r2.text
    assert r2.json()["is_authorized"] is False


# Registered vehicle with NO allotted parking -> log should be unauthorized too.
def test_access_log_unauthorized_when_no_allotment(client, db, rig):
    client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12BB0011",
    }, headers=rig["admin"]["headers"])

    r = client.post("/api/v1/parking/access-log", json={
        "society_id": str(rig["society"].id),
        "vehicle_number": "MH12BB0011",
        "access_type": "entry",
    }, headers=rig["guard"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["is_authorized"] is False
