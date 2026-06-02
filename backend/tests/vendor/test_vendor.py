"""Vendor & AMC management tests — vendor CRUD, service requests, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _create_vendor(client, headers, society_id, name="CleanPro"):
    r = client.post(
        "/api/v1/vendors/",
        json={
            "society_id":   str(society_id),
            "company_name": name,
            "mobile":       "9876543210",
            "category":     "housekeeping",
        },
        headers=headers,
    )
    return r


def test_create_vendor_success(client, db):
    admin   = make_user(db, "adm@vendor.com", role="Admin")
    society = make_society(db, "Vendor Society")
    r = _create_vendor(client, admin["headers"], society.id)
    assert r.status_code == 201
    assert r.json()["company_name"] == "CleanPro"


def test_create_vendor_requires_admin_or_committee(client, db):
    resident = make_user(db, "res@vendor.com", role="Resident")
    society  = make_society(db, "Vendor Society 2")
    r = _create_vendor(client, resident["headers"], society.id, "MyVendor")
    assert r.status_code == 403


def test_list_vendors_by_society(client, db):
    admin   = make_user(db, "adm2@vendor.com", role="Admin")
    society = make_society(db, "Vendor Society 3")
    _create_vendor(client, admin["headers"], society.id, "ElectraFix")
    _create_vendor(client, admin["headers"], society.id, "PlumPros")
    r = client.get(f"/api/v1/vendors/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_get_vendor_by_id(client, db):
    admin   = make_user(db, "adm3@vendor.com", role="Admin")
    society = make_society(db, "Vendor Society 4")
    cr = _create_vendor(client, admin["headers"], society.id, "FixAll")
    vendor_id = cr.json()["id"]
    r = client.get(f"/api/v1/vendors/{vendor_id}", headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["id"] == vendor_id


def test_create_service_request(client, db):
    admin   = make_user(db, "adm4@vendor.com", role="Admin")
    society = make_society(db, "Vendor Society 5")
    r = client.post(
        "/api/v1/vendors/service-requests",
        json={
            "society_id":  str(society.id),
            "title":       "Electrical wiring check",
            "category":    "electrical",
            "description": "Check wiring in lobby",
            "priority":    "medium",
        },
        headers=admin["headers"],
    )
    assert r.status_code == 201
    assert r.json()["title"] == "Electrical wiring check"
    assert r.json()["status"] == "open"


def test_list_open_service_requests(client, db):
    admin   = make_user(db, "adm5@vendor.com", role="Admin")
    society = make_society(db, "Vendor Society 6")
    client.post(
        "/api/v1/vendors/service-requests",
        json={"society_id": str(society.id), "title": "SR 1", "category": "plumbing"},
        headers=admin["headers"],
    )
    client.post(
        "/api/v1/vendors/service-requests",
        json={"society_id": str(society.id), "title": "SR 2", "category": "housekeeping"},
        headers=admin["headers"],
    )
    r = client.get(f"/api/v1/vendors/service-requests/open/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_unauthenticated_cannot_access_vendors(client, db):
    r = client.get("/api/v1/vendors/society/00000000-0000-0000-0000-000000000001")
    assert r.status_code in (401, 403)
