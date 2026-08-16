"""
Vehicle hardening — Phase M1.2.

Covers the six Phase M1.1-identified Vehicle gaps this tranche addresses:
resident/tenant XOR ownership, move-out cleanup (wired into the existing
P0-fixed OccupancyService, not duplicated), create-time flat/resident/tenant
cross-society validation, and the parking-module vehicle-number normalizer
drift (previously ViolationCreate/AccessLogCreate had no normalizer at all).

DB-level uniqueness/CHECK constraints for Vehicle were explicitly deferred
out of this phase (see the M1.2 report) since — unlike Resident — Vehicle
has real existing data in this system, and adding those constraints safely
requires a pre-flight violation check not scoped into this tranche.
"""
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
    society = make_society(db, "Vehicle Hardening Society")
    admin = make_user(db, "vhadm@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing V1")
    flat = make_flat(db, wing.id, "V-101")

    from app.models.resident import Resident
    from app.models.tenant import Tenant
    resident = Resident(flat_id=flat.id, full_name="Vehicle Owner Resident")
    tenant = Tenant(flat_id=flat.id, full_name="Vehicle Owner Tenant")
    db.add_all([resident, tenant])
    db.commit()
    db.refresh(resident)
    db.refresh(tenant)

    return {"society": society, "admin": admin, "wing": wing, "flat": flat,
            "resident": resident, "tenant": tenant}


# 1. resident-linked vehicle works
def test_resident_linked_vehicle(client, db, rig):
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12AA0001",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["resident_id"] == str(rig["resident"].id)
    assert r.json()["tenant_id"] is None


# 2. tenant-linked vehicle works
def test_tenant_linked_vehicle(client, db, rig):
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "tenant_id": str(rig["tenant"].id), "vehicle_number": "MH12AA0002",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["tenant_id"] == str(rig["tenant"].id)
    assert r.json()["resident_id"] is None


# 3. unassigned vehicle remains possible (backend permits "neither" by design —
#    Phase M1.1 §9: "unassigned" is a legitimate transient state)
def test_unassigned_vehicle_allowed(client, db, rig):
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "vehicle_number": "MH12AA0003",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["resident_id"] is None
    assert r.json()["tenant_id"] is None


# 4. resident_id + tenant_id simultaneously -> rejected
def test_resident_and_tenant_both_set_rejected(client, db, rig):
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "tenant_id": str(rig["tenant"].id),
        "vehicle_number": "MH12AA0004",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 422


# 5. cross-society vehicle access rejected (re-verifying the P0 fix still
#    holds, plus the NEW flat_id cross-society validation added this phase)
def test_create_with_cross_society_flat_id_rejected(client, db, rig):
    other_society = make_society(db, "Other Vehicle Society")
    other_wing = make_wing(db, other_society.id, "Other Wing")
    other_flat = make_flat(db, other_wing.id, "Other-101")
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id),  # correctly own society
        "flat_id": str(other_flat.id),          # but a flat from a different one
        "vehicle_number": "MH12AA0005",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 404, "flat_id from another society must be rejected, not silently accepted"


def test_create_with_cross_society_resident_id_rejected(client, db, rig):
    other_society = make_society(db, "Other Vehicle Society 2")
    other_wing = make_wing(db, other_society.id, "Other Wing 2")
    other_flat = make_flat(db, other_wing.id, "Other-102")
    from app.models.resident import Resident
    other_resident = Resident(flat_id=other_flat.id, full_name="Other Society Resident")
    db.add(other_resident); db.commit(); db.refresh(other_resident)

    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "resident_id": str(other_resident.id),
        "vehicle_number": "MH12AA0006",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 404


# 6. move-out cleanup behaves correctly — wired into OccupancyService, not duplicated
def test_resident_move_out_unassigns_vehicle(client, db, rig):
    veh = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "resident_id": str(rig["resident"].id), "vehicle_number": "MH12AA0007",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(rig["flat"].id), "resident_id": str(rig["resident"].id),
        "move_out_date": "2026-08-15",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text

    from app.models.vehicle import Vehicle
    v = db.query(Vehicle).filter(Vehicle.id == _to_uuid(veh["id"])).first()
    assert v.resident_id is None, "vehicle must be unassigned after its resident moves out"
    assert v.is_active is True, "the vehicle itself must NOT be deactivated, only unlinked"
    assert v.flat_id == rig["flat"].id, "flat_id is untouched by move-out cleanup"


def test_tenant_move_out_unassigns_vehicle(client, db, rig):
    veh = client.post("/api/v1/vehicles/", json={
        "society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id),
        "tenant_id": str(rig["tenant"].id), "vehicle_number": "MH12AA0008",
    }, headers=rig["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(rig["flat"].id), "tenant_id": str(rig["tenant"].id),
        "move_out_date": "2026-08-15",
    }, headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text

    from app.models.vehicle import Vehicle
    v = db.query(Vehicle).filter(Vehicle.id == _to_uuid(veh["id"])).first()
    assert v.tenant_id is None
    assert v.is_active is True


# 7. parking-module lookup/normalization now finds the same vehicle correctly
#    (previously ViolationCreate/AccessLogCreate had NO normalizer at all,
#    so the same physical number could be stored two different ways)
def test_parking_schemas_normalize_consistently_with_vehicle_master():
    from app.api.routes.vehicle import VehicleCreate
    from app.modules.parking.schemas.parking import (
        VisitorParkingCreate, ViolationCreate, AccessLogCreate,
    )
    from app.modules.parking.models.parking import ViolationType, AccessType
    from uuid import uuid4

    raw_variants = ["mh-01 ab 1234", "MH01AB1234", "mh01-ab-1234", "Mh 01 Ab 1234"]

    vehicle = VehicleCreate(society_id=uuid4(), vehicle_number=raw_variants[0])
    visitor_parking = VisitorParkingCreate(society_id=uuid4(), vehicle_number=raw_variants[1])
    violation = ViolationCreate(society_id=uuid4(), vehicle_number=raw_variants[2],
                                 violation_type=ViolationType.UNAUTHORIZED)
    access_log = AccessLogCreate(society_id=uuid4(), vehicle_number=raw_variants[3],
                                  access_type=AccessType.ENTRY)

    normalized = {vehicle.vehicle_number, visitor_parking.vehicle_number,
                  violation.vehicle_number, access_log.vehicle_number}
    assert normalized == {"MH01AB1234"}, (
        "all four schemas must normalize the same physical vehicle number identically "
        f"— got {normalized}"
    )
