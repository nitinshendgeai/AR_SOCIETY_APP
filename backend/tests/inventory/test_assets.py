"""Asset register: scoping between societies, the service schedule, summary and filters, and the
stores (items) now that they are scoped too."""
from datetime import date, timedelta

import pytest

from tests.conftest import make_society, make_user

API = "/api/v1/inventory"


def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who


@pytest.fixture
def two(db):
    """Two societies, each with an admin."""
    a, b = make_society(db, "Asset Society A"), make_society(db, "Asset Society B")
    return {
        "a": a, "b": b,
        "admin_a": _member(db, "adm.a@assets.test", "Society Admin", a),
        "admin_b": _member(db, "adm.b@assets.test", "Society Admin", b),
    }


def _asset(client, who, **over):
    body = {"name": "Terrace water pump", "asset_category": "pump", "location": "Terrace, Wing A",
            **over}
    return client.post(f"{API}/assets", json=body, headers=who["headers"])


def _today(days=0):
    return (date.today() + timedelta(days=days)).isoformat()


# ── Register ─────────────────────────────────────────────────────────────────

def test_register_uses_the_callers_society_and_numbers_assets(client, two):
    r = _asset(client, two["admin_a"], asset_category="air_conditioner", name="Office AC")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["society_id"] == str(two["a"].id)
    assert body["asset_code"] == "AST-0001"
    assert body["asset_category"] == "air_conditioner"
    assert _asset(client, two["admin_a"]).json()["asset_code"] == "AST-0002"
    # numbering runs per society
    assert _asset(client, two["admin_b"]).json()["asset_code"] == "AST-0001"


def test_register_in_another_society_refused(client, two):
    r = _asset(client, two["admin_a"], society_id=str(two["b"].id))
    assert r.status_code == 403


def test_register_validates_input(client, two):
    assert _asset(client, two["admin_a"], name="   ").status_code == 422
    assert _asset(client, two["admin_a"], purchase_cost="-5").status_code == 422
    assert _asset(client, two["admin_a"], service_interval_months=0).status_code == 422
    assert _asset(client, two["admin_a"], asset_category="spaceship").status_code == 422


def test_resident_and_staff_cannot_register(client, db, two):
    resident = _member(db, "res@assets.test", "Resident", two["a"])
    guard = _member(db, "guard@assets.test", "Security Staff", two["a"])
    assert _asset(client, resident).status_code == 403
    assert _asset(client, guard).status_code == 403
    # staff can look, residents can't
    assert client.get(f"{API}/assets/society/{two['a'].id}", headers=guard["headers"]).status_code == 200
    assert client.get(f"{API}/assets/society/{two['a'].id}", headers=resident["headers"]).status_code == 403


def test_manager_keeps_the_register(client, db, two):
    manager = _member(db, "mgr@assets.test", "Manager", two["a"])
    assert _asset(client, manager).status_code == 201


def test_next_service_worked_out_from_interval(client, two):
    # no service yet: the interval counts from purchase
    r = _asset(client, two["admin_a"], purchase_date="2026-01-31", service_interval_months=1)
    assert r.json()["next_service_due"] == "2026-02-28"           # month end is respected
    # serviced since: the interval counts from the last service
    r = _asset(client, two["admin_a"], purchase_date="2025-01-10", last_serviced_on="2026-03-15",
               service_interval_months=6)
    assert r.json()["next_service_due"] == "2026-09-15"
    # a date given is kept
    r = _asset(client, two["admin_a"], service_interval_months=6, next_service_due="2027-01-01")
    assert r.json()["next_service_due"] == "2027-01-01"


# ── Between societies ────────────────────────────────────────────────────────

def test_other_society_cannot_see_or_change_an_asset(client, two):
    asset = _asset(client, two["admin_a"]).json()
    other = two["admin_b"]["headers"]
    assert client.get(f"{API}/assets/{asset['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/assets/{asset['id']}/history", headers=other).status_code == 404
    assert client.patch(f"{API}/assets/{asset['id']}", json={"name": "Mine now"}, headers=other).status_code == 404
    assert client.post(f"{API}/assets/{asset['id']}/assign", json={}, headers=other).status_code == 404
    assert client.get(f"{API}/maintenance/asset/{asset['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/amc/asset/{asset['id']}", headers=other).status_code == 404
    assert client.post(f"{API}/maintenance", headers=other, json={
        "asset_id": asset["id"], "maintenance_type": "preventive", "scheduled_date": _today(5)}).status_code == 404
    assert client.post(f"{API}/amc", headers=other, json={
        "asset_id": asset["id"], "vendor_name": "X", "start_date": _today(), "end_date": _today(365)}).status_code == 404
    # nothing changed
    assert client.get(f"{API}/assets/{asset['id']}", headers=two["admin_a"]["headers"]).json()["name"] == asset["name"]


def test_society_wide_lists_are_confined(client, two):
    _asset(client, two["admin_a"])
    other = two["admin_b"]["headers"]
    sid = two["a"].id
    for path in (f"/assets/society/{sid}", f"/assets/summary/{sid}", f"/assets/society/{sid}/expiring-warranty",
                 f"/maintenance/scheduled/{sid}", f"/amc/expiring/{sid}", f"/items/society/{sid}",
                 f"/items/society/{sid}/low-stock", f"/issues/society/{sid}", f"/categories/{sid}"):
        assert client.get(API + path, headers=other).status_code == 403, path


def test_maintenance_cannot_be_filed_under_another_society(client, two):
    asset = _asset(client, two["admin_a"]).json()
    r = client.post(f"{API}/maintenance", headers=two["admin_a"]["headers"], json={
        "asset_id": asset["id"], "society_id": str(two["b"].id),
        "maintenance_type": "preventive", "scheduled_date": _today(10)})
    assert r.status_code == 201
    assert r.json()["society_id"] == str(two["a"].id)              # the asset's society, whatever was sent


def test_assignee_must_be_in_the_same_society(client, db, two):
    asset = _asset(client, two["admin_a"]).json()
    r = client.post(f"{API}/assets/{asset['id']}/assign", headers=two["admin_a"]["headers"],
                    json={"assigned_to_user": str(two["admin_b"]["user"].id)})
    assert r.status_code == 422
    r = client.post(f"{API}/assets/{asset['id']}/assign", headers=two["admin_a"]["headers"],
                    json={"assigned_to_user": str(two["admin_a"]["user"].id)})
    assert r.status_code == 200


# ── Editing ──────────────────────────────────────────────────────────────────

def test_edit_changes_only_what_is_sent_and_can_clear(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"], serial_number="SN-1", warranty_expiry=_today(200)).json()
    r = client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"location": "Basement"})
    assert r.status_code == 200
    assert r.json()["location"] == "Basement" and r.json()["serial_number"] == "SN-1"
    r = client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"warranty_expiry": None})
    assert r.json()["warranty_expiry"] is None and r.json()["warranty_status"] == "none"
    assert client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"name": "  "}).status_code == 422
    assert client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"service_interval_months": 500}).status_code == 422


def test_changing_the_interval_reworks_the_due_date(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"], last_serviced_on="2026-01-15", service_interval_months=3).json()
    assert asset["next_service_due"] == "2026-04-15"
    r = client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"service_interval_months": 12})
    assert r.json()["next_service_due"] == "2027-01-15"


def test_status_change_is_logged(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"]).json()
    client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"status": "retired"})
    log = client.get(f"{API}/assets/{asset['id']}/history", headers=h).json()["log"]
    assert any(l["action"] == "STATUS_CHANGED" and "active to retired" in l["notes"] for l in log)


# ── Service status ───────────────────────────────────────────────────────────

def test_service_and_warranty_status(client, two):
    h = two["admin_a"]["headers"]
    over = _asset(client, two["admin_a"], name="Overdue", next_service_due=_today(-3)).json()
    soon = _asset(client, two["admin_a"], name="Soon", next_service_due=_today(10), warranty_expiry=_today(10)).json()
    fine = _asset(client, two["admin_a"], name="Fine", next_service_due=_today(90), warranty_expiry=_today(400)).json()
    none = _asset(client, two["admin_a"], name="Unscheduled", warranty_expiry=_today(-1)).json()
    assert (over["service_status"], over["days_to_service"]) == ("overdue", -3)
    assert (soon["service_status"], soon["warranty_status"]) == ("due_soon", "expiring")
    assert (fine["service_status"], fine["warranty_status"]) == ("ok", "active")
    assert (none["service_status"], none["warranty_status"]) == ("none", "expired")
    # a retired asset needs no service
    client.patch(f"{API}/assets/{over['id']}", headers=h, json={"status": "retired"})
    assert client.get(f"{API}/assets/{over['id']}", headers=h).json()["service_status"] == "none"


def test_list_filters_and_due_list(client, two):
    h = two["admin_a"]["headers"]
    sid = two["a"].id
    _asset(client, two["admin_a"], name="Lift motor", asset_category="lift", location="Wing B", next_service_due=_today(5))
    _asset(client, two["admin_a"], name="Gym treadmill", asset_category="gym_equipment", next_service_due=_today(-2))
    _asset(client, two["admin_a"], name="Garden mower", asset_category="garden_equipment", next_service_due=_today(200))
    names = lambda r: [a["name"] for a in r.json()]
    assert names(client.get(f"{API}/assets/society/{sid}?category=lift", headers=h)) == ["Lift motor"]
    assert names(client.get(f"{API}/assets/society/{sid}?q=treadmill", headers=h)) == ["Gym treadmill"]
    assert names(client.get(f"{API}/assets/society/{sid}?q=wing b", headers=h)) == ["Lift motor"]
    assert len(client.get(f"{API}/assets/society/{sid}", headers=h).json()) == 3
    # due: overdue first, then soonest; the one 200 days away is left out
    assert names(client.get(f"{API}/assets/society/{sid}?due=true", headers=h)) == ["Gym treadmill", "Lift motor"]


def test_summary_counts(client, two):
    h = two["admin_a"]["headers"]
    sid = two["a"].id
    _asset(client, two["admin_a"], purchase_cost="10000", next_service_due=_today(-1), warranty_expiry=_today(5))
    _asset(client, two["admin_a"], purchase_cost="5000", asset_category="lift", next_service_due=_today(7))
    old = _asset(client, two["admin_a"], purchase_cost="999").json()
    client.patch(f"{API}/assets/{old['id']}", headers=h, json={"status": "retired"})
    s = client.get(f"{API}/assets/summary/{sid}", headers=h).json()
    assert s["total"] == 3 and s["active"] == 2 and s["retired"] == 1
    assert float(s["total_purchase_cost"]) == 15000          # retired assets don't count towards the value
    assert s["service_overdue"] == 1 and s["service_due_soon"] == 1
    assert s["warranty_expiring"] == 1
    assert s["by_category"] == {"pump": 2, "lift": 1}


# ── Servicing ────────────────────────────────────────────────────────────────

def _schedule(client, who, asset_id, when=None, **over):
    return client.post(f"{API}/maintenance", headers=who["headers"], json={
        "asset_id": asset_id, "maintenance_type": "preventive", "scheduled_date": when or _today(2), **over})


def test_completing_a_service_moves_the_schedule_on(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"], service_interval_months=3, next_service_due=_today(-10),
                   status="active").json()
    client.patch(f"{API}/assets/{asset['id']}", headers=h, json={"status": "under_maintenance"})
    m = _schedule(client, two["admin_a"], asset["id"], vendor_name="CoolAir").json()
    done = client.post(f"{API}/maintenance/{m['id']}/complete", headers=h,
                       json={"cost": "1500.50", "findings": "Gas topped up", "completed_date": _today(-1)})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed" and body["completed_date"] == _today(-1)
    after = client.get(f"{API}/assets/{asset['id']}", headers=h).json()
    assert after["last_serviced_on"] == _today(-1)
    assert after["next_service_due"] == body["next_due_date"] is not None      # an interval of 3 months from then
    assert after["next_service_due"] > _today()
    assert after["status"] == "active"                                         # back in service
    assert after["service_status"] == "ok"
    hist = client.get(f"{API}/assets/{asset['id']}/history", headers=h).json()
    assert float(hist["total_service_cost"]) == 1500.5
    assert hist["maintenance"][0]["vendor_name"] == "CoolAir"


def test_given_next_due_date_wins_and_must_be_later(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"], service_interval_months=3).json()
    m = _schedule(client, two["admin_a"], asset["id"]).json()
    bad = client.post(f"{API}/maintenance/{m['id']}/complete", headers=h,
                      json={"completed_date": _today(-1), "next_due_date": _today(-5)})
    assert bad.status_code == 422
    ok = client.post(f"{API}/maintenance/{m['id']}/complete", headers=h,
                     json={"completed_date": _today(-1), "next_due_date": _today(45)})
    assert ok.json()["next_due_date"] == _today(45)
    assert client.get(f"{API}/assets/{asset['id']}", headers=h).json()["next_service_due"] == _today(45)


def test_service_cannot_be_dated_in_the_future_or_completed_twice(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"]).json()
    m = _schedule(client, two["admin_a"], asset["id"]).json()
    assert client.post(f"{API}/maintenance/{m['id']}/complete", headers=h,
                       json={"completed_date": _today(3)}).status_code == 422
    assert client.post(f"{API}/maintenance/{m['id']}/complete", headers=h, json={}).status_code == 200
    assert client.post(f"{API}/maintenance/{m['id']}/complete", headers=h, json={}).status_code == 409


def test_an_older_service_does_not_pull_the_schedule_back(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"], service_interval_months=6, last_serviced_on=_today(-5),
                   next_service_due=_today(170)).json()
    m = _schedule(client, two["admin_a"], asset["id"], when=_today(-60)).json()
    client.post(f"{API}/maintenance/{m['id']}/complete", headers=h, json={"completed_date": _today(-60)})
    after = client.get(f"{API}/assets/{asset['id']}", headers=h).json()
    assert after["last_serviced_on"] == _today(-5) and after["next_service_due"] == _today(170)


def test_cancel_a_scheduled_service(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"]).json()
    m = _schedule(client, two["admin_a"], asset["id"]).json()
    assert client.post(f"{API}/maintenance/{m['id']}/cancel", headers=h).json()["status"] == "cancelled"
    assert client.post(f"{API}/maintenance/{m['id']}/cancel", headers=h).status_code == 409
    assert client.post(f"{API}/maintenance/{m['id']}/complete", headers=h, json={}).status_code == 409
    assert client.get(f"{API}/maintenance/scheduled/{two['a'].id}", headers=h).json() == []
    # another society can't cancel or complete it
    other = two["admin_b"]["headers"]
    m2 = _schedule(client, two["admin_a"], asset["id"]).json()
    assert client.post(f"{API}/maintenance/{m2['id']}/cancel", headers=other).status_code == 404
    assert client.post(f"{API}/maintenance/{m2['id']}/complete", headers=other, json={}).status_code == 404


def test_amc_and_history(client, two):
    h = two["admin_a"]["headers"]
    asset = _asset(client, two["admin_a"]).json()
    r = client.post(f"{API}/amc", headers=h, json={
        "asset_id": asset["id"], "vendor_name": "PumpCare", "start_date": _today(-300), "end_date": _today(20),
        "annual_cost": "12000"})
    assert r.status_code == 201 and r.json()["society_id"] == str(two["a"].id)
    assert client.post(f"{API}/amc", headers=h, json={
        "asset_id": asset["id"], "vendor_name": "X", "start_date": _today(5), "end_date": _today(1)}).status_code == 422
    expiring = client.get(f"{API}/amc/expiring/{two['a'].id}", headers=h).json()
    assert [a["vendor_name"] for a in expiring] == ["PumpCare"]
    s = client.get(f"{API}/assets/summary/{two['a'].id}", headers=h).json()
    assert s["amc_expiring"] == 1
    hist = client.get(f"{API}/assets/{asset['id']}/history", headers=h).json()
    assert [a["vendor_name"] for a in hist["amc"]] == ["PumpCare"]
    assert hist["asset"]["id"] == asset["id"] and hist["contracts"] == [] and hist["work_orders"] == []


# ── Stores (items), now confined to a society ─────────────────────────────────

def _item(client, who, name="Phenyl", **over):
    return client.post(f"{API}/items", headers=who["headers"], json={
        "name": name, "category": "cleaning", "unit_type": "litre", "minimum_stock": 5, **over})


def test_items_are_confined_and_show_stock(client, two):
    h = two["admin_a"]["headers"]
    item = _item(client, two["admin_a"]).json()
    assert item["society_id"] == str(two["a"].id) and item["current_stock"] == 0
    client.post(f"{API}/stock/in", headers=h, json={"item_id": item["id"], "quantity": 12})
    listed = client.get(f"{API}/items/society/{two['a'].id}", headers=h).json()
    assert listed[0]["current_stock"] == 12
    assert client.get(f"{API}/items/{item['id']}", headers=h).json()["current_stock"] == 12
    other = two["admin_b"]["headers"]
    assert client.get(f"{API}/items/{item['id']}", headers=other).status_code == 404
    assert client.patch(f"{API}/items/{item['id']}", headers=other, json={"name": "x"}).status_code == 404
    assert client.get(f"{API}/stock/{item['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/transactions/{item['id']}", headers=other).status_code == 404
    assert client.post(f"{API}/stock/in", headers=other, json={"item_id": item["id"], "quantity": 1}).status_code == 404
    assert client.post(f"{API}/stock/adjust", headers=other,
                       json={"item_id": item["id"], "new_quantity": 0, "notes": "x"}).status_code == 404
    assert _item(client, two["admin_a"], society_id=str(two["b"].id)).status_code == 403
    # search
    assert len(client.get(f"{API}/items/society/{two['a'].id}?q=phen", headers=h).json()) == 1
    assert client.get(f"{API}/items/society/{two['a'].id}?q=zzz", headers=h).json() == []


def test_issue_and_return_are_confined_and_damaged_goods_are_not_restocked(client, db, two):
    h = two["admin_a"]["headers"]
    guard = _member(db, "guard2@assets.test", "Security Staff", two["a"])
    item = _item(client, two["admin_a"], name="Torch", unit_type="piece").json()
    client.post(f"{API}/stock/in", headers=h, json={"item_id": item["id"], "quantity": 10})
    issue = lambda who, **o: client.post(f"{API}/issues", headers=who["headers"], json={
        "society_id": str(two["a"].id), "item_id": item["id"], "quantity_issued": 4, **o})
    # to someone from another society: refused
    assert issue(two["admin_a"], issued_to_user=str(two["admin_b"]["user"].id)).status_code == 422
    # another society can't issue its way into this stock
    assert issue(two["admin_b"]).status_code == 404
    r = issue(two["admin_a"], issued_to_user=str(guard["user"].id))
    assert r.status_code == 201 and r.json()["society_id"] == str(two["a"].id)
    issue_id = r.json()["id"]
    stock = lambda: client.get(f"{API}/stock/{item['id']}", headers=h).json()["current_quantity"]
    assert stock() == 6
    assert client.post(f"{API}/returns", headers=two["admin_b"]["headers"],
                       json={"issue_id": issue_id, "quantity": 1}).status_code == 404
    # two come back fine, one broken, one lost
    assert client.post(f"{API}/returns", headers=h, json={"issue_id": issue_id, "quantity": 2, "condition": "good"}).status_code == 200
    assert stock() == 8
    assert client.post(f"{API}/returns", headers=h, json={"issue_id": issue_id, "quantity": 1, "condition": "Damaged"}).status_code == 200
    r = client.post(f"{API}/returns", headers=h, json={"issue_id": issue_id, "quantity": 1, "condition": "lost"})
    assert r.status_code == 200 and r.json()["status"] == "returned"
    assert stock() == 8                                       # the broken and lost ones never went back on the shelf


def test_stock_cannot_be_adjusted_below_zero(client, two):
    h = two["admin_a"]["headers"]
    item = _item(client, two["admin_a"]).json()
    r = client.post(f"{API}/stock/adjust", headers=h, json={"item_id": item["id"], "new_quantity": -1, "notes": "x"})
    assert r.status_code == 422
