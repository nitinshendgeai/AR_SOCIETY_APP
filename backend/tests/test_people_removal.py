"""Removing a resident or tenant entered by mistake: hidden from every list, refused with the reason once there is real
history (bills, a move-out, renewed agreements), their unused login switched off, only the committee, only their society."""
from datetime import date

import pytest

from app.models.user import User, UserStatus
from tests.conftest import make_flat, make_society, make_user, make_wing, place_in


@pytest.fixture
def rig(db):
    one, two = make_society(db, "People One"), make_society(db, "People Two")
    wing = make_wing(db, one.id)
    admin = place_in(db, make_user(db, "admin@people.test", role="Society Admin"), one)
    other = place_in(db, make_user(db, "admin2@people.test", role="Society Admin"), two)
    resident = place_in(db, make_user(db, "res@people.test", role="Resident"), one)
    return {"soc": one, "flat": make_flat(db, wing.id, "101"), "admin": admin["headers"], "other": other["headers"],
            "resident": resident["headers"]}


def _resident(client, rig, name="Wrong Person", phone="9811111111", **extra):
    r = client.post("/api/v1/residents/", headers=rig["admin"], json={
        "flat_id": str(rig["flat"].id), "full_name": name, "resident_type": "owner", "is_primary": True,
        "phone": phone, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _tenant(client, rig, name="Wrong Tenant", **extra):
    r = client.post("/api/v1/tenants/", headers=rig["admin"], json={
        "flat_id": str(rig["flat"].id), "full_name": name, "phone": "9822222222", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_resident_removed_and_login_switched_off(client, db, rig):
    r = _resident(client, rig)
    assert client.delete(f"/api/v1/residents/{r['id']}", headers=rig["admin"]).status_code == 204
    names = [x["full_name"] for x in client.get("/api/v1/residents/", headers=rig["admin"]).json()]
    assert "Wrong Person" not in names
    user = db.query(User).filter(User.phone == "9811111111").one()
    assert user.is_active is False and user.status == UserStatus.INACTIVE
    # the same person can be entered again, primary again
    assert _resident(client, rig)["id"] != r["id"]


def test_resident_who_moved_out_is_refused(client, db, rig):
    r = _resident(client, rig, move_in_date="2025-01-01")
    m = client.post("/api/v1/occupancy/resident/move-out", headers=rig["admin"], json={
        "flat_id": str(rig["flat"].id), "resident_id": r["id"], "move_out_date": date.today().isoformat()})
    assert m.status_code == 200, m.text
    d = client.delete(f"/api/v1/residents/{r['id']}", headers=rig["admin"])
    assert d.status_code == 409 and "moved out" in d.json()["detail"]


def test_resident_with_a_bill_is_refused(client, db, rig):
    from app.modules.billing.models.billing import BillingCycle, MaintenanceBill
    r = _resident(client, rig)
    cycle = BillingCycle(society_id=rig["soc"].id, name="Apr", start_date=date(2026, 4, 1), end_date=date(2026, 4, 30),
                         due_date=date(2026, 5, 10))
    db.add(cycle); db.commit()
    db.add(MaintenanceBill(society_id=rig["soc"].id, cycle_id=cycle.id, flat_id=rig["flat"].id, resident_id=r["id"],
                           invoice_number="INV-1", bill_date=date(2026, 4, 1), due_date=date(2026, 5, 10)))
    db.commit()
    d = client.delete(f"/api/v1/residents/{r['id']}", headers=rig["admin"])
    assert d.status_code == 409 and "1 bill" in d.json()["detail"] and "Move out" in d.json()["detail"]


def test_login_that_has_been_used_is_kept(client, db, rig):
    r = _resident(client, rig)
    user = db.query(User).filter(User.phone == "9811111111").one()
    user.last_login = __import__("datetime").datetime.utcnow()
    db.commit()
    assert client.delete(f"/api/v1/residents/{r['id']}", headers=rig["admin"]).status_code == 204
    db.refresh(user)
    assert user.is_active is True


def test_resident_removal_guards(client, db, rig):
    r = _resident(client, rig)
    assert client.delete(f"/api/v1/residents/{r['id']}", headers=rig["resident"]).status_code == 403
    assert client.delete(f"/api/v1/residents/{r['id']}", headers=rig["other"]).status_code == 404


def test_tenant_removed_with_agreement_and_flat_freed(client, db, rig):
    t = _tenant(client, rig, move_in_date="2026-01-01", agreement_start_date="2026-01-01", agreement_end_date="2026-12-31")
    assert client.delete(f"/api/v1/tenants/{t['id']}", headers=rig["admin"]).status_code == 204
    assert "Wrong Tenant" not in [x["full_name"] for x in client.get("/api/v1/tenants/", headers=rig["admin"]).json()]
    db.refresh(rig["flat"])
    assert rig["flat"].occupancy_status.value != "tenant_occupied"


def test_tenant_who_moved_out_is_refused(client, db, rig):
    t = _tenant(client, rig, move_in_date="2025-01-01")
    m = client.post("/api/v1/occupancy/tenant/move-out", headers=rig["admin"], json={
        "flat_id": str(rig["flat"].id), "tenant_id": t["id"], "move_out_date": date.today().isoformat()})
    assert m.status_code == 200, m.text
    d = client.delete(f"/api/v1/tenants/{t['id']}", headers=rig["admin"])
    assert d.status_code == 409 and "moved out" in d.json()["detail"]


def test_tenant_with_renewed_agreement_is_refused(client, db, rig):
    t = _tenant(client, rig, move_in_date="2026-01-01", agreement_start_date="2026-01-01", agreement_end_date="2026-12-31")
    rn = client.post(f"/api/v1/tenants/{t['id']}/renew-agreement", headers=rig["admin"],
                     json={"start_date": "2027-01-01", "end_date": "2027-12-31"})
    assert rn.status_code in (200, 201), rn.text
    d = client.delete(f"/api/v1/tenants/{t['id']}", headers=rig["admin"])
    assert d.status_code == 409 and "agreement" in d.json()["detail"]


def test_tenant_removal_guards(client, db, rig):
    t = _tenant(client, rig)
    assert client.delete(f"/api/v1/tenants/{t['id']}", headers=rig["resident"]).status_code == 403
    assert client.delete(f"/api/v1/tenants/{t['id']}", headers=rig["other"]).status_code == 404
