"""Removing a master record entered by mistake: vendors, assets, store items, parking zones and slots, amenities.
A removed record leaves every list and its name or number can be used again; it is refused while something depends on it,
with the reason; only the committee does it, and only in its own society."""
from datetime import date, timedelta
from uuid import UUID

import pytest

from app.modules.parking.models.parking import AllocationStatus, ParkingAllocation, SlotType
from tests.conftest import make_society, make_user, place_in


@pytest.fixture
def rig(db):
    one, two = make_society(db, "Removal Society One"), make_society(db, "Removal Society Two")
    admin = place_in(db, make_user(db, "admin@removal.test", role="Society Admin"), one)
    other = place_in(db, make_user(db, "admin2@removal.test", role="Society Admin"), two)
    manager = place_in(db, make_user(db, "mgr@removal.test", role="Manager"), one)
    resident = place_in(db, make_user(db, "res@removal.test", role="Resident"), one)
    return {"soc": one, "sid": str(one.id), "admin": admin["headers"], "other": other["headers"],
            "manager": manager["headers"], "resident": resident}


# ── Vendors ───────────────────────────────────────────────────────────────────

def _vendor(client, rig, name="CleanPro"):
    r = client.post("/api/v1/vendors/", headers=rig["admin"], json={
        "society_id": rig["sid"], "company_name": name, "mobile": "9876543210", "category": "housekeeping"})
    assert r.status_code == 201, r.text
    return r.json()


def _vendors(client, rig):
    return [v["company_name"] for v in client.get(f"/api/v1/vendors/society/{rig['sid']}", headers=rig["admin"]).json()]


def test_a_vendor_entered_by_mistake_is_removed_and_its_name_can_be_used_again(client, rig):
    v = _vendor(client, rig)
    assert client.delete(f"/api/v1/vendors/{v['id']}", headers=rig["admin"]).status_code == 204
    assert "CleanPro" not in _vendors(client, rig)
    again = _vendor(client, rig)                                # the same name is free again, with the next code
    assert again["vendor_code"] != v["vendor_code"]


def test_a_vendor_with_a_bill_is_not_removed_and_is_told_why(client, rig):
    v = _vendor(client, rig)
    r = client.post("/api/v1/vendors/invoices", headers=rig["admin"], json={
        "society_id": rig["sid"], "vendor_id": v["id"], "invoice_number": "B-1", "invoice_date": str(date.today()),
        "amount": "1000", "gst_amount": "0", "total_amount": "1000"})
    assert r.status_code == 201, r.text
    gone = client.delete(f"/api/v1/vendors/{v['id']}", headers=rig["admin"])
    assert gone.status_code == 409
    assert "1 bill" in gone.json()["detail"] and "Inactive" in gone.json()["detail"]
    assert "CleanPro" in _vendors(client, rig)


def test_only_the_committee_removes_a_vendor_and_only_in_its_society(client, rig):
    v = _vendor(client, rig)
    assert client.delete(f"/api/v1/vendors/{v['id']}", headers=rig["manager"]).status_code == 403
    assert client.delete(f"/api/v1/vendors/{v['id']}", headers=rig["other"]).status_code == 404
    assert "CleanPro" in _vendors(client, rig)


# ── Store items ───────────────────────────────────────────────────────────────

def _item(client, rig, name="Mop"):
    r = client.post("/api/v1/inventory/items", headers=rig["admin"], json={
        "society_id": rig["sid"], "name": name, "category": "cleaning", "unit_type": "piece", "minimum_stock": 5})
    assert r.status_code == 201, r.text
    return r.json()


def _items(client, rig):
    return [i["name"] for i in client.get(f"/api/v1/inventory/items/society/{rig['sid']}", headers=rig["admin"]).json()]


def test_a_store_item_never_stocked_is_removed_and_its_name_freed(client, rig):
    item = _item(client, rig)
    assert client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["admin"]).status_code == 204
    assert "Mop" not in _items(client, rig)
    assert _item(client, rig)["name"] == "Mop"


def test_a_store_item_with_stock_is_refused_until_counted_down(client, rig):
    item = _item(client, rig)
    client.post("/api/v1/inventory/stock/in", json={"item_id": item["id"], "quantity": 20}, headers=rig["admin"])
    r = client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["admin"])
    assert r.status_code == 409 and "20 unit(s) in stock" in r.json()["detail"]
    adj = client.post("/api/v1/inventory/stock/adjust", headers=rig["admin"],
                      json={"item_id": item["id"], "new_quantity": 0, "notes": "entered by mistake"})
    assert adj.status_code == 200, adj.text
    # once counted down, the stock history stays and the item can go
    assert client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["admin"]).status_code == 204


def test_store_items_are_removed_by_those_who_keep_the_stores_in_their_society_only(client, rig):
    item = _item(client, rig)
    assert client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["resident"]["headers"]).status_code == 403
    assert client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["other"]).status_code == 404
    assert client.delete(f"/api/v1/inventory/items/{item['id']}", headers=rig["manager"]).status_code == 204   # the manager keeps the stores


# ── Assets ────────────────────────────────────────────────────────────────────

def _asset(client, rig, name="Lift A"):
    r = client.post("/api/v1/inventory/assets", headers=rig["admin"], json={
        "society_id": rig["sid"], "name": name, "asset_category": "lift"})
    assert r.status_code == 201, r.text
    return r.json()


def _assets(client, rig):
    return [a["name"] for a in client.get(f"/api/v1/inventory/assets/society/{rig['sid']}?limit=500",
                                          headers=rig["admin"]).json()]


def test_an_asset_entered_by_mistake_is_removed(client, rig):
    asset = _asset(client, rig)
    assert client.delete(f"/api/v1/inventory/assets/{asset['id']}", headers=rig["admin"]).status_code == 204
    assert "Lift A" not in _assets(client, rig)
    again = _asset(client, rig)
    assert client.delete(f"/api/v1/inventory/assets/{again['id']}", headers=rig["resident"]["headers"]).status_code == 403
    assert client.delete(f"/api/v1/inventory/assets/{again['id']}", headers=rig["manager"]).status_code == 204  # keeps the register


def test_an_asset_with_a_service_record_is_not_removed(client, rig):
    asset = _asset(client, rig)
    r = client.post("/api/v1/inventory/maintenance", headers=rig["admin"], json={
        "asset_id": asset["id"], "maintenance_type": "preventive",
        "scheduled_date": str(date.today() + timedelta(days=10))})
    assert r.status_code == 201, r.text
    gone = client.delete(f"/api/v1/inventory/assets/{asset['id']}", headers=rig["admin"])
    assert gone.status_code == 409 and "service record" in gone.json()["detail"] and "Retire" in gone.json()["detail"]
    assert "Lift A" in _assets(client, rig)


def test_another_societys_asset_is_not_found(client, rig):
    asset = _asset(client, rig)
    assert client.delete(f"/api/v1/inventory/assets/{asset['id']}", headers=rig["other"]).status_code == 404


# ── Parking ───────────────────────────────────────────────────────────────────

def _zone(client, rig, name="Block A"):
    r = client.post("/api/v1/parking/zones", headers=rig["admin"],
                    json={"society_id": rig["sid"], "name": name, "code": name[:2].upper()})
    assert r.status_code == 201, r.text
    return r.json()


def _slot(client, rig, zone_id, number="P-001"):
    r = client.post("/api/v1/parking/slots", headers=rig["admin"], json={
        "society_id": rig["sid"], "zone_id": zone_id, "slot_number": number, "slot_type": "resident"})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_slot_is_removed_its_number_freed_and_the_zone_count_drops(client, rig):
    zone = _zone(client, rig)
    slot = _slot(client, rig, zone["id"])
    assert client.delete(f"/api/v1/parking/slots/{slot['id']}", headers=rig["admin"]).status_code == 204
    zones = client.get(f"/api/v1/parking/zones/{rig['sid']}", headers=rig["admin"]).json()
    assert next(z for z in zones if z["id"] == zone["id"])["total_slots"] == 0
    assert _slot(client, rig, zone["id"])["slot_number"] == "P-001"                 # the number is free again


def test_an_allocated_slot_is_refused_until_released(client, rig, db):
    zone = _zone(client, rig)
    slot = _slot(client, rig, zone["id"])
    alloc = ParkingAllocation(society_id=rig["soc"].id, slot_id=UUID(slot["id"]), allocation_type=SlotType.RESIDENT,
                              start_date=date.today(), status=AllocationStatus.ACTIVE)
    db.add(alloc)
    db.commit()
    r = client.delete(f"/api/v1/parking/slots/{slot['id']}", headers=rig["admin"])
    assert r.status_code == 409 and "1 current allocation" in r.json()["detail"]
    alloc.status = AllocationStatus.RELEASED
    db.commit()
    assert client.delete(f"/api/v1/parking/slots/{slot['id']}", headers=rig["admin"]).status_code == 204


def test_a_zone_goes_only_when_it_has_no_slots(client, rig):
    zone = _zone(client, rig)
    slot = _slot(client, rig, zone["id"])
    r = client.delete(f"/api/v1/parking/zones/{zone['id']}", headers=rig["admin"])
    assert r.status_code == 409 and "1 slot" in r.json()["detail"]
    client.delete(f"/api/v1/parking/slots/{slot['id']}", headers=rig["admin"])
    assert client.delete(f"/api/v1/parking/zones/{zone['id']}", headers=rig["admin"]).status_code == 204
    zones = client.get(f"/api/v1/parking/zones/{rig['sid']}", headers=rig["admin"]).json()
    assert zone["id"] not in [z["id"] for z in zones]


def test_parking_is_removed_by_the_committee_of_its_society_only(client, rig):
    zone = _zone(client, rig)
    assert client.delete(f"/api/v1/parking/zones/{zone['id']}", headers=rig["manager"]).status_code == 403
    assert client.delete(f"/api/v1/parking/zones/{zone['id']}", headers=rig["other"]).status_code == 404


# ── Amenities ─────────────────────────────────────────────────────────────────

def _amenity(client, rig, name="Pool"):
    r = client.post("/api/v1/amenities/", headers=rig["admin"], json={
        "society_id": rig["sid"], "name": name, "amenity_type": "pool",
        "booking_required": True, "approval_required": False})
    assert r.status_code == 201, r.text
    return r.json()


def _amenities(client, rig):
    return [a["name"] for a in client.get(f"/api/v1/amenities/society/{rig['sid']}", headers=rig["admin"]).json()]


def test_an_amenity_entered_by_mistake_is_removed_and_its_name_freed(client, rig):
    a = _amenity(client, rig)
    assert client.delete(f"/api/v1/amenities/{a['id']}", headers=rig["admin"]).status_code == 204
    assert "Pool" not in _amenities(client, rig)
    assert _amenity(client, rig)["name"] == "Pool"


def test_an_amenity_with_a_booking_to_come_is_refused_until_it_is_cancelled(client, rig):
    a = _amenity(client, rig)
    book = client.post("/api/v1/amenities/bookings", headers=rig["resident"]["headers"], json={
        "society_id": rig["sid"], "amenity_id": a["id"], "booking_date": str(date.today() + timedelta(days=7)),
        "start_time": "09:00:00", "end_time": "10:00:00"})
    assert book.status_code == 201, book.text
    r = client.delete(f"/api/v1/amenities/{a['id']}", headers=rig["admin"])
    assert r.status_code == 409 and "1 upcoming booking" in r.json()["detail"]
    assert client.post(f"/api/v1/amenities/bookings/{book.json()['id']}/cancel", json={},
                       headers=rig["resident"]["headers"]).status_code == 200
    assert client.delete(f"/api/v1/amenities/{a['id']}", headers=rig["admin"]).status_code == 204


def test_amenities_are_removed_by_the_committee_of_their_society_only(client, rig):
    a = _amenity(client, rig)
    assert client.delete(f"/api/v1/amenities/{a['id']}", headers=rig["manager"]).status_code == 403
    assert client.delete(f"/api/v1/amenities/{a['id']}", headers=rig["other"]).status_code == 404
