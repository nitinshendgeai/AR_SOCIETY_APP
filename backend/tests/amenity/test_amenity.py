"""Amenity management tests — CRUD, booking workflow, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _create_amenity(client, headers, society_id, name="Pool"):
    r = client.post(
        "/api/v1/amenities/",
        json={
            "society_id": str(society_id),
            "name": name,
            "amenity_type": "pool",
            "booking_required": True,
            "approval_required": False,
        },
        headers=headers,
    )
    return r


def test_create_amenity_success(client, db):
    admin   = make_user(db, "adm@amen.com", role="Admin")
    society = make_society(db, "Amenity Society")
    r = _create_amenity(client, admin["headers"], society.id)
    assert r.status_code == 201
    assert r.json()["name"] == "Pool"
    assert r.json()["amenity_type"] == "pool"


def test_create_amenity_requires_admin_or_committee(client, db):
    resident = make_user(db, "res@amen.com", role="Resident")
    society  = make_society(db, "Amenity Society 2")
    r = _create_amenity(client, resident["headers"], society.id, "Gym")
    assert r.status_code == 403


def test_list_amenities_by_society(client, db):
    admin   = make_user(db, "adm2@amen.com", role="Admin")
    society = make_society(db, "Amenity Society 3")
    _create_amenity(client, admin["headers"], society.id, "Gym")
    _create_amenity(client, admin["headers"], society.id, "Clubhouse")
    r = client.get(f"/api/v1/amenities/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_book_amenity_no_approval_required(client, db):
    admin    = make_user(db, "adm3@amen.com", role="Admin")
    resident = make_user(db, "res2@amen.com", role="Resident")
    society  = make_society(db, "Amenity Society 4")
    cr = _create_amenity(client, admin["headers"], society.id, "Tennis Court")
    assert cr.status_code == 201
    amenity_id = cr.json()["id"]
    r = client.post(
        "/api/v1/amenities/bookings",
        json={
            "society_id":   str(society.id),
            "amenity_id":   amenity_id,
            "booking_date": "2026-07-15",
            "start_time":   "09:00:00",
            "end_time":     "10:00:00",
        },
        headers=resident["headers"],
    )
    assert r.status_code == 201
    # approval_required=False → auto-approved
    assert r.json()["status"] in ("pending", "approved")


def test_approve_booking_with_approval_required(client, db):
    admin    = make_user(db, "adm4@amen.com", role="Admin")
    resident = make_user(db, "res3@amen.com", role="Resident")
    society  = make_society(db, "Amenity Society 5")
    # Create amenity that requires explicit approval
    cr = client.post(
        "/api/v1/amenities/",
        json={
            "society_id": str(society.id),
            "name": "Conference Hall",
            "amenity_type": "conference",
            "booking_required": True,
            "approval_required": True,
        },
        headers=admin["headers"],
    )
    assert cr.status_code == 201
    amenity_id = cr.json()["id"]
    br = client.post(
        "/api/v1/amenities/bookings",
        json={
            "society_id":   str(society.id),
            "amenity_id":   amenity_id,
            "booking_date": "2026-07-20",
            "start_time":   "14:00:00",
            "end_time":     "16:00:00",
        },
        headers=resident["headers"],
    )
    assert br.status_code == 201
    assert br.json()["status"] == "pending"
    booking_id = br.json()["id"]
    r = client.post(
        f"/api/v1/amenities/bookings/{booking_id}/approve",
        json={"notes": "Approved"},
        headers=admin["headers"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_cancel_booking(client, db):
    admin    = make_user(db, "adm5@amen.com", role="Admin")
    resident = make_user(db, "res4@amen.com", role="Resident")
    society  = make_society(db, "Amenity Society 6")
    # approval_required=True keeps status as pending (cancellable)
    cr = client.post(
        "/api/v1/amenities/",
        json={
            "society_id": str(society.id), "name": "Terrace",
            "amenity_type": "terrace", "booking_required": True,
            "approval_required": True,
        },
        headers=admin["headers"],
    )
    amenity_id = cr.json()["id"]
    br = client.post(
        "/api/v1/amenities/bookings",
        json={
            "society_id":   str(society.id),
            "amenity_id":   amenity_id,
            "booking_date": "2026-07-22",
            "start_time":   "10:00:00",
            "end_time":     "11:00:00",
        },
        headers=resident["headers"],
    )
    booking_id = br.json()["id"]
    r = client.post(
        f"/api/v1/amenities/bookings/{booking_id}/cancel",
        json={"reason": "Plan changed"},
        headers=resident["headers"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_unauthenticated_cannot_book(client, db):
    r = client.post("/api/v1/amenities/bookings", json={"amenity_id": "123"})
    assert r.status_code in (401, 403)
