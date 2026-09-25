"""Maintenance bill module — charge heads, cycles, generation, bulk issue,
bill detail/PDF, and the resident's own-bills view."""
from datetime import date, timedelta
from app.models.resident import Resident
from app.models.notification import Notification
from tests.conftest import make_user, make_society, make_wing, make_flat


def _rig(db, tag):
    society = make_society(db, f"MB Society {tag}")
    wing = make_wing(db, society.id, "Tower A")
    flat1 = make_flat(db, wing.id, "101")
    flat2 = make_flat(db, wing.id, "102")
    manager = make_user(db, f"mgr@mb{tag}.com", role="Manager")
    resident = make_user(db, f"res@mb{tag}.com", role="Resident")
    other_resident = make_user(db, f"res2@mb{tag}.com", role="Resident")
    db.add(Resident(full_name="Asha Rao", flat_id=flat1.id, user_id=resident["user"].id, is_primary=True))
    db.add(Resident(full_name="Vik Mehta", flat_id=flat2.id, user_id=other_resident["user"].id, is_primary=True))
    db.commit()
    return society, flat1, flat2, manager, resident, other_resident


def _charge(client, headers, society_id, name="Maintenance", amount="2500.00", tax="0", **extra):
    return client.post("/api/v1/billing/charges", json={
        "society_id": str(society_id), "charge_type": "maintenance", "name": name,
        "default_amount": amount, "tax_percent": tax, **extra,
    }, headers=headers)


def _cycle(client, headers, society_id, name="Oct 2026"):
    today = date.today()
    return client.post("/api/v1/billing/cycles", json={
        "society_id": str(society_id), "name": name,
        "cycle_start": str(today), "cycle_end": str(today + timedelta(days=30)),
        "due_date": str(today + timedelta(days=10)),
    }, headers=headers)


def _generated_cycle(client, db, tag):
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    _charge(client, manager["headers"], society.id, amount="2500.00")
    _charge(client, manager["headers"], society.id, name="Water", amount="300.00", tax="18")
    cycle_id = _cycle(client, manager["headers"], society.id).json()["id"]
    r = client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=manager["headers"])
    assert r.status_code == 200, r.text
    return society, flat1, flat2, manager, resident, other, cycle_id


def test_manager_can_create_and_list_charge_heads(client, db):
    society, *_ , manager, resident, other = _rig(db, "c1")
    r = _charge(client, manager["headers"], society.id)
    assert r.status_code == 201, r.text
    assert r.json()["default_amount"] == "2500.00"
    r = client.get(f"/api/v1/billing/charges/{society.id}", headers=manager["headers"])
    assert [c["name"] for c in r.json()] == ["Maintenance"]


def test_resident_cannot_manage_charge_heads(client, db):
    society, *_ , manager, resident, other = _rig(db, "c2")
    assert _charge(client, resident["headers"], society.id).status_code == 403


def test_update_and_deactivate_charge_head(client, db):
    society, *_ , manager, resident, other = _rig(db, "c3")
    cid = _charge(client, manager["headers"], society.id).json()["id"]
    r = client.patch(f"/api/v1/billing/charges/{cid}", json={"default_amount": "2750.00"},
                     headers=manager["headers"])
    assert r.status_code == 200 and r.json()["default_amount"] == "2750.00"
    r = client.patch(f"/api/v1/billing/charges/{cid}", json={"is_active": False},
                     headers=manager["headers"])
    assert r.json()["is_active"] is False
    assert client.get(f"/api/v1/billing/charges/{society.id}", headers=manager["headers"]).json() == []


def test_cycle_end_before_start_rejected(client, db):
    society, *_ , manager, resident, other = _rig(db, "c4")
    today = date.today()
    r = client.post("/api/v1/billing/cycles", json={
        "society_id": str(society.id), "name": "Bad",
        "cycle_start": str(today), "cycle_end": str(today - timedelta(days=1)),
        "due_date": str(today),
    }, headers=manager["headers"])
    assert r.status_code == 422


def test_generation_builds_line_items_totals_and_links_resident(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "g1")
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    assert len(bills) == 2
    assert [b["flat_number"] for b in bills] == ["101", "102"]
    b = bills[0]
    assert b["wing_name"] == "Tower A"
    assert b["resident_name"] == "Asha Rao"
    assert b["bill_status"] == "generated"
    # 2500 + 300 + 18% of 300 (54) = 2854
    assert b["total_amount"] == "2854.00"

    detail = client.get(f"/api/v1/billing/bills/{b['id']}", headers=manager["headers"]).json()
    assert {li["description"] for li in detail["line_items"]} == {"Maintenance", "Water"}
    assert detail["payments"] == []

    cycle = client.get(f"/api/v1/billing/cycles/detail/{cycle_id}", headers=manager["headers"]).json()
    assert cycle["bills_count"] == 2
    assert cycle["generated_count"] == 2
    assert cycle["total_billed"] == "5708.00"
    assert cycle["is_finalized"] is True


def test_issue_all_issues_every_generated_bill_and_notifies_residents(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "i1")
    r = client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    assert r.status_code == 200 and r.json()["bills_issued"] == 2
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    assert {b["bill_status"] for b in bills} == {"issued"}
    notes = db.query(Notification).filter(Notification.user_id == resident["user"].id).all()
    assert any("Maintenance Bill Issued" in n.title for n in notes)

    r2 = client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    assert r2.status_code == 409


def test_resident_sees_only_own_issued_bills(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "r1")

    # Not issued yet → hidden from the resident
    mine = client.get("/api/v1/billing/bills/me", headers=resident["headers"]).json()
    assert mine["bills"] == [] and mine["total_outstanding"] == "0"

    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    mine = client.get("/api/v1/billing/bills/me", headers=resident["headers"]).json()
    assert len(mine["bills"]) == 1
    assert mine["bills"][0]["flat_number"] == "101"
    assert mine["total_outstanding"] == "2854.00"
    assert mine["open_count"] == 1


def test_resident_cannot_view_another_flats_bill(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "r2")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    theirs = next(b for b in bills if b["flat_number"] == "102")
    mine = next(b for b in bills if b["flat_number"] == "101")

    assert client.get(f"/api/v1/billing/bills/{theirs['id']}", headers=resident["headers"]).status_code == 404
    assert client.get(f"/api/v1/billing/bills/{theirs['id']}/pdf", headers=resident["headers"]).status_code == 404
    assert client.get(f"/api/v1/billing/bills/flat/{flat2.id}", headers=resident["headers"]).status_code == 404
    assert client.get(f"/api/v1/billing/bills/{mine['id']}", headers=resident["headers"]).status_code == 200


def test_resident_cannot_list_cycle_bills(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "r3")
    assert client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=resident["headers"]).status_code == 403


def test_bill_pdf_downloads(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "p1")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bill_id = client.get("/api/v1/billing/bills/me", headers=resident["headers"]).json()["bills"][0]["id"]
    r = client.get(f"/api/v1/billing/bills/{bill_id}/pdf", headers=resident["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_on_bill_payment_shows_in_bill_detail_and_cycle_totals(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "pay1")
    client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    bill = bills[0]
    r = client.post("/api/v1/billing/online-payments", data={
        "flat_id": bill["flat_id"], "amount": "1000.00", "payment_date": str(date.today()),
        "payment_mode": "cash", "bill_id": bill["id"],
    }, headers=manager["headers"])
    assert r.status_code == 201, r.text

    detail = client.get(f"/api/v1/billing/bills/{bill['id']}", headers=manager["headers"]).json()
    assert detail["bill_status"] == "partially_paid"
    assert len(detail["payments"]) == 1 and detail["payments"][0]["amount"] == "1000.00"

    cycle = client.get(f"/api/v1/billing/cycles/detail/{cycle_id}", headers=manager["headers"]).json()
    assert cycle["total_collected"] == "1000.00"
    assert cycle["total_outstanding"] == "4708.00"


def test_cancelled_bill_excluded_from_cycle_totals(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "cx1")
    bills = client.get(f"/api/v1/billing/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    r = client.post(f"/api/v1/billing/bills/{bills[0]['id']}/cancel", json={"reason": "Flat vacant"},
                    headers=manager["headers"])
    assert r.status_code == 200 and r.json()["bill_status"] == "cancelled"
    cycle = client.get(f"/api/v1/billing/cycles/detail/{cycle_id}", headers=manager["headers"]).json()
    assert cycle["bills_count"] == 1
    assert cycle["total_billed"] == "2854.00"
