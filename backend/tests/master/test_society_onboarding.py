"""Society onboarding workflow tests."""
import pytest
from tests.conftest import make_user, make_society


def test_register_and_initialize(client, db):
    admin = make_user(db, "setup@onboard.com", role="Admin")
    r = client.post("/api/v1/societies/register-and-initialize", json={
        "name": "Setup Test Society", "society_code": "STS001"
    }, headers=admin["headers"])
    assert r.status_code == 201
    data = r.json()
    assert "credentials" in data
    assert len(data["credentials"]) == 3
    roles = data["roles_created"]
    assert "Society Admin" in roles
    assert "Security" in roles
    assert "Resident" in roles


def test_initialize_creates_default_users(client, db):
    admin   = make_user(db, "adm@onboard.com", role="Admin")
    society = make_society(db, "Init Society")
    # Set society_code for predictable email
    society.society_code = "INITS"
    db.commit()

    r = client.post(f"/api/v1/societies/{society.id}/initialize",
                    headers=admin["headers"])
    assert r.status_code == 200
    creds = r.json()["credentials"]
    emails = [c["email"] for c in creds]
    assert any("admin@" in e for e in emails)
    assert any("security@" in e for e in emails)


def test_initialize_idempotent(client, db):
    """Running initialize twice should not duplicate users/roles."""
    admin   = make_user(db, "adm2@onboard.com", role="Admin")
    society = make_society(db, "Idem Society")
    society.society_code = "IDEMS"
    db.commit()

    r1 = client.post(f"/api/v1/societies/{society.id}/initialize",
                     headers=admin["headers"])
    r2 = client.post(f"/api/v1/societies/{society.id}/initialize",
                     headers=admin["headers"])
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second run creates 0 new users (idempotent)
    assert r2.json()["users_created"] == 0


def test_default_user_must_change_password(client, db):
    """Default users should have must_change_password=True."""
    from app.models.user import User
    admin   = make_user(db, "adm3@onboard.com", role="Admin")
    society = make_society(db, "PWD Society")
    society.society_code = "PWDS"
    db.commit()

    client.post(f"/api/v1/societies/{society.id}/initialize",
                headers=admin["headers"])

    admin_user = db.query(User).filter(
        User.email == "admin@pwds.arsociety.com"
    ).first()
    assert admin_user is not None
    assert admin_user.must_change_password is True


def test_only_admin_can_initialize(client, db):
    society = make_society(db, "Perm Society")
    resident = make_user(db, "res@onboard.com", role="Resident")
    r = client.post(f"/api/v1/societies/{society.id}/initialize",
                    headers=resident["headers"])
    assert r.status_code == 403


def test_initialize_nonexistent_society(client, db):
    import uuid
    admin = make_user(db, "adm4@onboard.com", role="Admin")
    r = client.post(f"/api/v1/societies/{uuid.uuid4()}/initialize",
                    headers=admin["headers"])
    assert r.status_code == 404
