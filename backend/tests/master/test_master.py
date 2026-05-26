"""Master module tests — society, wing, flat, resident, tenant, vehicle."""
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


# ── Society ───────────────────────────────────────────────────────────────────

def test_create_society(client, db):
    admin = make_user(db, "adm@master.com", role="Admin")
    r = client.post("/api/v1/societies/", json={"name": "AR Society"},
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "AR Society"


def test_duplicate_society_name(client, db):
    admin = make_user(db, "adm2@master.com", role="Admin")
    make_society(db, "Duplicate Society")
    r = client.post("/api/v1/societies/", json={"name": "Duplicate Society"},
                    headers=admin["headers"])
    assert r.status_code == 400


def test_get_society_not_found(client, db):
    res = make_user(db, "res@master.com", role="Resident")
    import uuid
    r = client.get(f"/api/v1/societies/{uuid.uuid4()}", headers=res["headers"])
    assert r.status_code == 404


# ── Wing ──────────────────────────────────────────────────────────────────────

def test_create_wing(client, db):
    admin   = make_user(db, "adm3@master.com", role="Admin")
    society = make_society(db, "Wing Society")
    r = client.post("/api/v1/wings/", json={
        "name": "Wing A", "society_id": str(society.id)
    }, headers=admin["headers"])
    assert r.status_code == 201


def test_wing_invalid_society(client, db):
    admin = make_user(db, "adm4@master.com", role="Admin")
    import uuid
    r = client.post("/api/v1/wings/", json={
        "name": "Wing X", "society_id": str(uuid.uuid4())
    }, headers=admin["headers"])
    assert r.status_code == 404


# ── Flat ──────────────────────────────────────────────────────────────────────

def test_create_flat(client, db):
    admin   = make_user(db, "adm5@master.com", role="Admin")
    society = make_society(db, "Flat Society")
    wing    = make_wing(db, society.id)
    r = client.post("/api/v1/flats/", json={
        "flat_number": "101", "wing_id": str(wing.id)
    }, headers=admin["headers"])
    assert r.status_code == 201


def test_flat_invalid_wing(client, db):
    admin = make_user(db, "adm6@master.com", role="Admin")
    import uuid
    r = client.post("/api/v1/flats/", json={
        "flat_number": "202", "wing_id": str(uuid.uuid4())
    }, headers=admin["headers"])
    assert r.status_code == 404


# ── Vehicle ───────────────────────────────────────────────────────────────────

def test_register_vehicle(client, db):
    admin   = make_user(db, "adm7@master.com", role="Admin")
    society = make_society(db, "Vehicle Society")
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(society.id), "vehicle_number": "MH01AB1234",
        "vehicle_type": "car"
    }, headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["vehicle_number"] == "MH01AB1234"


def test_duplicate_vehicle(client, db):
    admin   = make_user(db, "adm8@master.com", role="Admin")
    society = make_society(db, "Vehicle Society 2")
    data    = {"society_id": str(society.id), "vehicle_number": "MH02CD5678", "vehicle_type": "car"}
    client.post("/api/v1/vehicles/", json=data, headers=admin["headers"])
    r2 = client.post("/api/v1/vehicles/", json=data, headers=admin["headers"])
    assert r2.status_code == 409


def test_vehicle_number_normalized(client, db):
    """Vehicle numbers should be uppercased and stripped."""
    admin   = make_user(db, "adm9@master.com", role="Admin")
    society = make_society(db, "Vehicle Society 3")
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(society.id), "vehicle_number": "mh-03-ef-9012",
        "vehicle_type": "motorcycle"
    }, headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["vehicle_number"] == "MH03EF9012"
