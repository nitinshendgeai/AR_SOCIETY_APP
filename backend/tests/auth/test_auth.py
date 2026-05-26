"""Authentication system tests — registration, login, JWT, RBAC."""
import pytest
from tests.conftest import make_user


# ── Registration ──────────────────────────────────────────────────────────────

def test_register_success(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "new@test.com", "full_name": "New User", "password": "Test@1234"
    })
    assert r.status_code == 201
    assert r.json()["email"] == "new@test.com"


def test_register_duplicate_email(client, db):
    make_user(db, "dup@test.com")
    r = client.post("/api/v1/auth/register", json={
        "email": "dup@test.com", "full_name": "Dup User", "password": "Test@1234"
    })
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"].lower()


def test_register_weak_password(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@test.com", "full_name": "Weak", "password": "123"
    })
    assert r.status_code == 422


def test_register_invalid_email(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "not-an-email", "full_name": "Bad", "password": "Test@1234"
    })
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(client, db):
    make_user(db, "login@test.com")
    r = client.post("/api/v1/auth/login", json={
        "email": "login@test.com", "password": "Test@1234"
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db):
    make_user(db, "loginwrong@test.com")
    r = client.post("/api/v1/auth/login", json={
        "email": "loginwrong@test.com", "password": "WrongPass!"
    })
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com", "password": "Test@1234"
    })
    assert r.status_code == 401


# ── JWT Validation ────────────────────────────────────────────────────────────

def test_me_with_valid_token(client, db):
    u = make_user(db, "me@test.com")
    r = client.get("/api/v1/auth/me", headers=u["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == "me@test.com"


def test_me_no_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 403  # HTTPBearer returns 403 when no credentials


def test_me_invalid_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_me_malformed_bearer(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "NotBearer abc"})
    assert r.status_code == 403


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "database" in data
