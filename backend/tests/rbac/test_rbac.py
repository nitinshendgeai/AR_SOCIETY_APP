"""RBAC tests — role-based access control enforcement."""
import pytest
from tests.conftest import make_user, make_society


def test_admin_can_create_society(client, db):
    admin = make_user(db, "admin@rbac.com", role="Admin")
    r = client.post("/api/v1/societies/", json={
        "name": "Test Society RBAC"
    }, headers=admin["headers"])
    assert r.status_code == 201


def test_resident_cannot_create_society(client, db):
    res = make_user(db, "resident@rbac.com", role="Resident")
    r = client.post("/api/v1/societies/", json={
        "name": "Resident Society"
    }, headers=res["headers"])
    assert r.status_code == 403


def test_committee_can_update_society(client, db):
    admin    = make_user(db, "admin2@rbac.com", role="Admin")
    society  = make_society(db, "Update Society")
    committee = make_user(db, "committee@rbac.com", role="Committee")
    r = client.patch(f"/api/v1/societies/{society.id}", json={
        "city": "Pune"
    }, headers=committee["headers"])
    assert r.status_code == 200


def test_security_cannot_update_society(client, db):
    society = make_society(db, "Security Society")
    security = make_user(db, "security@rbac.com", role="Security")
    r = client.patch(f"/api/v1/societies/{society.id}", json={
        "city": "Delhi"
    }, headers=security["headers"])
    assert r.status_code == 403


def test_unauthenticated_cannot_access_protected(client):
    r = client.get("/api/v1/societies/")
    assert r.status_code == 403


def test_admin_can_list_users(client, db):
    admin = make_user(db, "admin3@rbac.com", role="Admin")
    r = client.get("/api/v1/users/", headers=admin["headers"])
    assert r.status_code == 200


def test_resident_cannot_list_users(client, db):
    res = make_user(db, "res2@rbac.com", role="Resident")
    r   = client.get("/api/v1/users/", headers=res["headers"])
    assert r.status_code == 403


def test_any_authenticated_can_view_society(client, db):
    res     = make_user(db, "res3@rbac.com", role="Resident")
    society = make_society(db, "View Society")
    r = client.get(f"/api/v1/societies/{society.id}", headers=res["headers"])
    assert r.status_code == 200


def test_admin_dashboard_requires_admin(client, db):
    res = make_user(db, "res4@rbac.com", role="Resident")
    r   = client.get("/api/v1/users/admin/dashboard", headers=res["headers"])
    assert r.status_code == 403

    admin = make_user(db, "admin4@rbac.com", role="Admin")
    r2    = client.get("/api/v1/users/admin/dashboard", headers=admin["headers"])
    assert r2.status_code == 200


def test_multi_role_access(client, db):
    """User with Committee role should pass committee_or_admin guard."""
    from app.models.user import User, UserRole
    from app.models.role import Role
    from app.core.security import create_access_token

    r_admin = db.query(Role).filter(Role.name == "Admin").first()
    r_comm  = db.query(Role).filter(Role.name == "Committee").first()
    if not r_admin:
        r_admin = Role(name="Admin"); db.add(r_admin); db.flush()
    if not r_comm:
        r_comm = Role(name="Committee"); db.add(r_comm); db.flush()

    from app.core.security import hash_password
    from app.models.user import UserStatus
    user = User(email="multi@rbac.com", full_name="Multi",
                hashed_password=hash_password("Test@1234"), status=UserStatus.ACTIVE)
    db.add(user); db.flush()
    db.add(UserRole(user_id=user.id, role_id=r_admin.id))
    db.add(UserRole(user_id=user.id, role_id=r_comm.id))
    db.commit()

    token   = create_access_token(str(user.id), {"roles": ["Admin", "Committee"]})
    headers = {"Authorization": f"Bearer {token}"}
    society = make_society(db, "Multi Role Society")
    r = client.patch(f"/api/v1/societies/{society.id}", json={"city": "Chennai"},
                     headers=headers)
    assert r.status_code == 200
