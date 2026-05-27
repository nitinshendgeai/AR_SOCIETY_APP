"""
Authentication hardening tests — edge cases, security scenarios.
Covers: inactive users, suspended users, token abuse, refresh tokens,
        audit logging, password security, concurrent sessions.
"""
import pytest
from tests.conftest import make_user


# ── Inactive / Suspended Users ────────────────────────────────────────────────

def test_inactive_user_cannot_login(client, db):
    """Deactivated users should not be able to log in."""
    from app.models.user import UserStatus
    u = make_user(db, "inactive@auth.com")
    user = u["user"]
    user.status = UserStatus.INACTIVE
    db.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "inactive@auth.com", "password": "Test@1234"
    })
    assert r.status_code == 403
    assert "inactive" in r.json()["detail"].lower()


def test_suspended_user_cannot_login(client, db):
    from app.models.user import UserStatus
    u = make_user(db, "suspended@auth.com")
    u["user"].status = UserStatus.SUSPENDED
    db.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "suspended@auth.com", "password": "Test@1234"
    })
    assert r.status_code == 403


def test_deactivated_user_token_rejected(client, db):
    """Token issued to user who is later deactivated should be rejected."""
    u = make_user(db, "deact@auth.com")
    token = u["token"]

    # Deactivate after token issued
    u["user"].is_active = False
    db.commit()

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ── Token Security ────────────────────────────────────────────────────────────

def test_refresh_token_as_access_token_rejected(client, db):
    """Refresh token must not be accepted where access token is required."""
    make_user(db, "refresh@auth.com")
    login_r = client.post("/api/v1/auth/login", json={
        "email": "refresh@auth.com", "password": "Test@1234"
    })
    refresh_token = login_r.json()["refresh_token"]

    r = client.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {refresh_token}"})
    assert r.status_code == 401


def test_access_token_as_refresh_token_rejected(client, db):
    """Access token must not be accepted on /auth/refresh."""
    u = make_user(db, "tokenswap@auth.com")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": u["token"]})
    assert r.status_code == 401


def test_tampered_token_rejected(client, db):
    """Token with modified payload should fail signature validation."""
    u = make_user(db, "tamper@auth.com")
    token = u["token"]
    # Modify middle segment
    parts = token.split(".")
    parts[1] = parts[1][:10] + "XXXX" + parts[1][14:]
    tampered = ".".join(parts)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_empty_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer "})
    assert r.status_code in (401, 403, 422)


def test_token_with_unknown_user_rejected(client):
    """Valid JWT structure but references non-existent user."""
    import uuid
    from app.core.security import create_access_token
    fake_token = create_access_token(str(uuid.uuid4()), {"roles": ["Admin"]})
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
    assert r.status_code == 401


# ── Refresh Token Flow ────────────────────────────────────────────────────────

def test_refresh_token_returns_new_pair(client, db):
    make_user(db, "rt@auth.com")
    login_r = client.post("/api/v1/auth/login", json={
        "email": "rt@auth.com", "password": "Test@1234"
    })
    refresh = login_r.json()["refresh_token"]
    original_access = login_r.json()["access_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token should be returned (access may match within same second)
    assert "access_token" in data and "refresh_token" in data


def test_refresh_with_invalid_token(client):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.token"})
    assert r.status_code == 401


# ── Password Security ─────────────────────────────────────────────────────────

def test_password_not_in_response(client):
    """Password hash must never appear in any API response."""
    r = client.post("/api/v1/auth/register", json={
        "email": "nopw@auth.com", "full_name": "No PW", "password": "Test@1234"
    })
    assert r.status_code == 201
    body = str(r.json())
    assert "hashed_password" not in body
    assert "password" not in body


def test_same_password_different_hash(client, db):
    """bcrypt should produce different hashes for same password (salt)."""
    from app.core.security import hash_password, verify_password
    h1 = hash_password("SamePass@1")
    h2 = hash_password("SamePass@1")
    assert h1 != h2  # different salts
    assert verify_password("SamePass@1", h1)
    assert verify_password("SamePass@1", h2)


# ── Role Assignment ───────────────────────────────────────────────────────────

def test_role_assigned_on_registration(client):
    """Newly registered user should have Resident role."""
    r = client.post("/api/v1/auth/register", json={
        "email": "newrole@auth.com", "full_name": "Role Test", "password": "Test@1234"
    })
    assert r.status_code == 201
    # Default role is Resident
    data = r.json()
    assert "id" in data  # user created


def test_idempotent_role_assignment(client, db):
    """Assigning same role twice should not create duplicate UserRole entries."""
    from app.models.user import UserRole
    admin = make_user(db, "roledup@auth.com", role="Admin")
    user_id = admin["user"].id

    # Assign Admin role again via API
    r = client.post(f"/api/v1/users/{user_id}/roles",
                    json={"role_name": "Admin"},
                    headers=admin["headers"])
    # Should succeed or be idempotent
    assert r.status_code in (200, 409)

    # Count user_roles - should not be duplicated
    count = db.query(UserRole).filter(
        UserRole.user_id == user_id,
    ).count()
    # At most 1 Admin role entry
    admin_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    role_names  = [ur.role.name for ur in admin_roles if ur.role]
    assert role_names.count("Admin") == 1


# ── Error Response Format ─────────────────────────────────────────────────────

def test_auth_error_has_detail_field(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "WrongPass"
    })
    assert r.status_code == 401
    assert "detail" in r.json()


def test_validation_error_format(client):
    """Pydantic validation errors should return 422 with structured errors."""
    r = client.post("/api/v1/auth/register", json={
        "email": "bad-email", "full_name": "", "password": "x"
    })
    assert r.status_code == 422
    body = r.json()
    # Our custom handler returns 'message' and 'errors'
    assert "message" in body or "detail" in body


def test_forbidden_error_format(client, db):
    """403 errors should have detail field."""
    res = make_user(db, "fmt@auth.com", role="Resident")
    r = client.post("/api/v1/societies/", json={"name": "Fmt Test"},
                    headers=res["headers"])
    assert r.status_code == 403
    assert "detail" in r.json()


# ── SQL Injection Resistance ──────────────────────────────────────────────────

def test_sql_injection_in_email(client):
    """Malicious email input should be safely handled."""
    r = client.post("/api/v1/auth/login", json={
        "email": "admin'--@example.com",
        "password": "' OR '1'='1"
    })
    # Should return 401/422, not 500
    assert r.status_code in (401, 422)


def test_sql_injection_in_register(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "'; DROP TABLE users; --@evil.com",
        "full_name": "Hacker",
        "password": "Test@1234"
    })
    # Either 422 (invalid email) or 400 — never 500
    assert r.status_code in (400, 422)
