"""Inventory management tests — item CRUD, stock-in, issue workflow, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _create_item(client, headers, society_id, name="Mop"):
    r = client.post(
        "/api/v1/inventory/items",
        json={
            "society_id":    str(society_id),
            "name":          name,
            "category":      "cleaning",
            "unit_type":     "piece",
            "minimum_stock": 5,
        },
        headers=headers,
    )
    return r


def test_create_item_success(client, db):
    admin   = make_user(db, "adm@inv.com", role="Admin")
    society = make_society(db, "Inventory Society")
    r = _create_item(client, admin["headers"], society.id)
    assert r.status_code == 201
    assert r.json()["name"] == "Mop"
    assert r.json()["category"] == "cleaning"


def test_create_item_requires_admin_or_committee(client, db):
    resident = make_user(db, "res@inv.com", role="Resident")
    society  = make_society(db, "Inventory Society 2")
    r = _create_item(client, resident["headers"], society.id, "Bucket")
    assert r.status_code == 403


def test_list_items_by_society(client, db):
    admin   = make_user(db, "adm2@inv.com", role="Admin")
    society = make_society(db, "Inventory Society 3")
    _create_item(client, admin["headers"], society.id, "Broom")
    _create_item(client, admin["headers"], society.id, "Dustpan")
    r = client.get(f"/api/v1/inventory/items/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_stock_in_increases_stock(client, db):
    admin   = make_user(db, "adm3@inv.com", role="Admin")
    society = make_society(db, "Inventory Society 4")
    ir      = _create_item(client, admin["headers"], society.id, "Gloves")
    item_id = ir.json()["id"]
    r = client.post(
        "/api/v1/inventory/stock/in",
        json={"item_id": item_id, "quantity": 20},
        headers=admin["headers"],
    )
    assert r.status_code == 200
    assert r.json()["current_quantity"] == 20


def test_issue_item_to_staff(client, db):
    admin    = make_user(db, "adm4@inv.com", role="Admin")
    staff_u  = make_user(db, "stf@inv.com", role="Staff")
    society  = make_society(db, "Inventory Society 5")
    ir       = _create_item(client, admin["headers"], society.id, "Cleaning Kit")
    item_id  = ir.json()["id"]
    # Stock in first
    client.post("/api/v1/inventory/stock/in",
                json={"item_id": item_id, "quantity": 10},
                headers=admin["headers"])
    # Issue
    r = client.post(
        "/api/v1/inventory/issues",
        json={
            "society_id":     str(society.id),
            "item_id":        item_id,
            "quantity_issued": 3,
            "issued_to_user": str(staff_u["user"].id),
            "purpose":        "Daily cleaning",
        },
        headers=admin["headers"],
    )
    assert r.status_code == 201
    assert r.json()["quantity_issued"] == 3


def test_stock_in_zero_quantity_rejected(client, db):
    admin   = make_user(db, "adm5@inv.com", role="Admin")
    society = make_society(db, "Inventory Society 6")
    ir      = _create_item(client, admin["headers"], society.id, "Cloth")
    item_id = ir.json()["id"]
    r = client.post(
        "/api/v1/inventory/stock/in",
        json={"item_id": item_id, "quantity": 0},
        headers=admin["headers"],
    )
    assert r.status_code == 422


def test_unauthenticated_cannot_access_inventory(client, db):
    r = client.get("/api/v1/inventory/items/00000000-0000-0000-0000-000000000001")
    assert r.status_code in (401, 403)
