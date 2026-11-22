"""The people who live with a tenant: add, list, remove; refused duplicates; committee only, own society only; they go
when the tenant is removed."""
import pytest

from tests.conftest import make_flat, make_society, make_user, make_wing, place_in


@pytest.fixture
def rig(db):
    one, two = make_society(db, "Family One"), make_society(db, "Family Two")
    flat = make_flat(db, make_wing(db, one.id).id, "201")
    admin = place_in(db, make_user(db, "admin@family.test", role="Society Admin"), one)
    other = place_in(db, make_user(db, "admin2@family.test", role="Society Admin"), two)
    resident = place_in(db, make_user(db, "res@family.test", role="Resident"), one)
    return {"flat": flat, "admin": admin["headers"], "other": other["headers"], "resident": resident["headers"]}


def _tenant(client, rig):
    r = client.post("/api/v1/tenants/", headers=rig["admin"], json={"flat_id": str(rig["flat"].id), "full_name": "Tina Tenant"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_add_list_and_remove(client, rig):
    t = _tenant(client, rig)
    a = client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"],
                    json={"full_name": "Sam Tenant", "relation": "spouse", "phone": "9876543210", "date_of_birth": "1990-05-01"})
    assert a.status_code == 201, a.text
    assert a.json()["relation"] == "spouse"
    client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"], json={"full_name": "Kid Tenant", "relation": "child"})
    names = [m["full_name"] for m in client.get(f"/api/v1/tenants/{t}/family", headers=rig["admin"]).json()]
    assert names == ["Sam Tenant", "Kid Tenant"]
    assert client.delete(f"/api/v1/tenants/{t}/family/{a.json()['id']}", headers=rig["admin"]).status_code == 204
    names = [m["full_name"] for m in client.get(f"/api/v1/tenants/{t}/family", headers=rig["admin"]).json()]
    assert names == ["Kid Tenant"]
    assert client.delete(f"/api/v1/tenants/{t}/family/{a.json()['id']}", headers=rig["admin"]).status_code == 404


def test_duplicate_and_bad_input_refused(client, rig):
    t = _tenant(client, rig)
    body = {"full_name": "Sam Tenant", "relation": "spouse"}
    assert client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"], json=body).status_code == 201
    d = client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"], json={**body, "full_name": "sam  tenant"})
    assert d.status_code == 409
    assert client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"], json={"full_name": "  "}).status_code == 422
    assert client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"],
                       json={"full_name": "X", "relation": "cousin"}).status_code == 422


def test_guards(client, rig):
    t = _tenant(client, rig)
    body = {"full_name": "Sam Tenant"}
    assert client.post(f"/api/v1/tenants/{t}/family", headers=rig["resident"], json=body).status_code == 403
    assert client.post(f"/api/v1/tenants/{t}/family", headers=rig["other"], json=body).status_code == 404
    assert client.get(f"/api/v1/tenants/{t}/family", headers=rig["other"]).status_code == 404


def test_removed_with_the_tenant(client, db, rig):
    from app.models.tenant_family import TenantFamilyMember
    t = _tenant(client, rig)
    client.post(f"/api/v1/tenants/{t}/family", headers=rig["admin"], json={"full_name": "Sam Tenant"})
    assert client.delete(f"/api/v1/tenants/{t}", headers=rig["admin"]).status_code == 204
    assert db.query(TenantFamilyMember).filter(TenantFamilyMember.is_active == True).count() == 0  # noqa: E712
