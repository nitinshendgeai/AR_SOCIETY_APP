"""Master module tests — society, wing, flat, resident, tenant, vehicle."""
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


# ── Society ───────────────────────────────────────────────────────────────────

def test_create_society(client, db):
    admin = make_user(db, "adm@master.com", role="Society Admin")
    r = client.post("/api/v1/societies/", json={"name": "AR Society"},
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "AR Society"


def test_duplicate_society_name(client, db):
    admin = make_user(db, "adm2@master.com", role="Society Admin")
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
    admin   = make_user(db, "adm3@master.com", role="Society Admin")
    society = make_society(db, "Wing Society")
    r = client.post("/api/v1/wings/", json={
        "name": "Wing A", "society_id": str(society.id)
    }, headers=admin["headers"])
    assert r.status_code == 201


def test_wing_invalid_society(client, db):
    admin = make_user(db, "adm4@master.com", role="Society Admin")
    import uuid
    r = client.post("/api/v1/wings/", json={
        "name": "Wing X", "society_id": str(uuid.uuid4())
    }, headers=admin["headers"])
    assert r.status_code == 404


def test_duplicate_active_wing_name_rejected(client, db):
    admin   = make_user(db, "adm-wdup@master.com", role="Society Admin")
    society = make_society(db, "Wing Dup Society")
    payload = {"name": "A Wing", "society_id": str(society.id)}
    r1 = client.post("/api/v1/wings/", json=payload, headers=admin["headers"])
    assert r1.status_code == 201
    r2 = client.post("/api/v1/wings/", json=payload, headers=admin["headers"])
    assert r2.status_code == 409


def test_wing_name_reusable_after_delete(client, db):
    """A soft-deleted wing must free up its name/code for reuse — the DB-level
    constraint used to be a plain UniqueConstraint (not scoped to is_active),
    so re-creating a wing with the same name after deleting the old one
    raised a raw IntegrityError -> generic 409, even though the app-level
    duplicate check (which only looks at active rows) would have allowed it.
    """
    admin   = make_user(db, "adm-wdel@master.com", role="Society Admin")
    society = make_society(db, "Wing Reuse Society")
    payload = {"name": "A Wing", "code": "A", "society_id": str(society.id)}

    r1 = client.post("/api/v1/wings/", json=payload, headers=admin["headers"])
    assert r1.status_code == 201
    wing_id = r1.json()["id"]

    r_del = client.delete(f"/api/v1/wings/{wing_id}", headers=admin["headers"])
    assert r_del.status_code == 204

    r2 = client.post("/api/v1/wings/", json=payload, headers=admin["headers"])
    assert r2.status_code == 201
    assert r2.json()["id"] != wing_id


# ── Flat ──────────────────────────────────────────────────────────────────────

def test_create_flat(client, db):
    admin   = make_user(db, "adm5@master.com", role="Society Admin")
    society = make_society(db, "Flat Society")
    wing    = make_wing(db, society.id)
    r = client.post("/api/v1/flats/", json={
        "flat_number": "101", "wing_id": str(wing.id)
    }, headers=admin["headers"])
    assert r.status_code == 201


def test_flat_invalid_wing(client, db):
    admin = make_user(db, "adm6@master.com", role="Society Admin")
    import uuid
    r = client.post("/api/v1/flats/", json={
        "flat_number": "202", "wing_id": str(uuid.uuid4())
    }, headers=admin["headers"])
    assert r.status_code == 404


# ── Floor ─────────────────────────────────────────────────────────────────────

def test_floor_number_reusable_after_delete(client, db):
    """Same soft-delete/unique-index bug as wings — see
    test_wing_name_reusable_after_delete."""
    admin   = make_user(db, "adm-fdel@master.com", role="Society Admin")
    society = make_society(db, "Floor Reuse Society")
    wing    = make_wing(db, society.id, "Floor Reuse Wing")
    payload = {"floor_number": 1, "wing_id": str(wing.id), "society_id": str(society.id)}

    r1 = client.post("/api/v1/floors/", json=payload, headers=admin["headers"])
    assert r1.status_code == 201
    floor_id = r1.json()["id"]

    r_del = client.delete(f"/api/v1/floors/{floor_id}", headers=admin["headers"])
    assert r_del.status_code == 204

    r2 = client.post("/api/v1/floors/", json=payload, headers=admin["headers"])
    assert r2.status_code == 201
    assert r2.json()["id"] != floor_id


# ── Vehicle ───────────────────────────────────────────────────────────────────

def test_register_vehicle(client, db):
    admin   = make_user(db, "adm7@master.com", role="Society Admin")
    society = make_society(db, "Vehicle Society")
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(society.id), "vehicle_number": "MH01AB1234",
        "vehicle_type": "car"
    }, headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["vehicle_number"] == "MH01AB1234"


def test_duplicate_vehicle(client, db):
    admin   = make_user(db, "adm8@master.com", role="Society Admin")
    society = make_society(db, "Vehicle Society 2")
    data    = {"society_id": str(society.id), "vehicle_number": "MH02CD5678", "vehicle_type": "car"}
    client.post("/api/v1/vehicles/", json=data, headers=admin["headers"])
    r2 = client.post("/api/v1/vehicles/", json=data, headers=admin["headers"])
    assert r2.status_code == 409


def test_vehicle_number_normalized(client, db):
    """Vehicle numbers should be uppercased and stripped."""
    admin   = make_user(db, "adm9@master.com", role="Society Admin")
    society = make_society(db, "Vehicle Society 3")
    r = client.post("/api/v1/vehicles/", json={
        "society_id": str(society.id), "vehicle_number": "mh-03-ef-9012",
        "vehicle_type": "motorcycle"
    }, headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["vehicle_number"] == "MH03EF9012"
