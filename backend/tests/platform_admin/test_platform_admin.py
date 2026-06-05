"""Tests for platform admin endpoints."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User, UserStatus
from app.models.society import Society, AccountStatus
from app.core.security import hash_password


def make_superadmin(db: Session):
    user = User(
        email="superadmin@arsociety.com",
        full_name="Platform Admin",
        hashed_password=hash_password("Admin@1234"),
        status=UserStatus.ACTIVE,
        is_superadmin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), {"roles": ["Platform Admin"]})
    return user, {"Authorization": f"Bearer {token}"}


def make_trial_society(db: Session, name: str = "Test Trial Society",
                        code: str = "TTS01") -> Society:
    s = Society(
        name             = name,
        society_code     = code,
        city             = "Pune",
        state            = "Maharashtra",
        account_status   = AccountStatus.TRIAL,
        is_trial         = True,
        trial_start_date = date.today(),
        trial_end_date   = date.today() + timedelta(days=30),
        allowed_users    = 50,
        allowed_flats    = 100,
        allowed_storage_mb = 1024,
        setup_completed  = False,
        setup_completion_percentage = 0,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ── List societies ─────────────────────────────────────────────────────────────

class TestListSocieties:

    def test_list_requires_superadmin(self, client: TestClient, db: Session):
        from tests.conftest import make_user
        u = make_user(db, "regular@test.com", role="Resident")
        resp = client.get("/api/v1/platform-admin/societies", headers=u["headers"])
        assert resp.status_code == 403

    def test_list_societies_success(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        make_trial_society(db)
        resp = client.get("/api/v1/platform-admin/societies", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "account_status" in data[0]
        assert "trial_days_remaining" in data[0]

    def test_list_societies_unauthenticated(self, client: TestClient):
        resp = client.get("/api/v1/platform-admin/societies")
        assert resp.status_code == 403


# ── Platform stats ─────────────────────────────────────────────────────────────

class TestPlatformStats:

    def test_stats_structure(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        make_trial_society(db, name="Stats Society", code="STS01")
        resp = client.get("/api/v1/platform-admin/stats", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_societies" in data
        assert "trial_societies" in data
        assert "active_societies" in data
        assert "expired_societies" in data
        assert "suspended_societies" in data
        assert "expiring_soon" in data
        assert data["total_societies"] >= 1
        assert data["trial_societies"] >= 1


# ── Extend trial ───────────────────────────────────────────────────────────────

class TestExtendTrial:

    def test_extend_trial_success(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Extend Trial Soc", code="ETS01")
        original_end = society.trial_end_date  # capture before endpoint mutates it

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/extend-trial",
            json={"extend_days": 15},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["account_status"] == "TRIAL"
        expected_end = (original_end + timedelta(days=15)).isoformat()
        assert data["trial_end_date"] == expected_end

    def test_extend_trial_invalid_days(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Bad Days Society", code="BDS01")

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/extend-trial",
            json={"extend_days": 0},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_extend_trial_active_society_rejected(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Active Soc", code="ACS01")
        society.account_status = AccountStatus.ACTIVE
        db.commit()

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/extend-trial",
            json={"extend_days": 10},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_extend_trial_not_found(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = client.post(
            f"/api/v1/platform-admin/societies/{fake_id}/extend-trial",
            json={"extend_days": 10},
            headers=headers,
        )
        assert resp.status_code == 404


# ── Suspend society ────────────────────────────────────────────────────────────

class TestSuspendSociety:

    def test_suspend_trial_society(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Suspend Me", code="SUS01")

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/suspend",
            json={"reason": "Non-payment of fees"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["account_status"] == "SUSPENDED"

    def test_suspend_cancelled_society_rejected(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Cancelled Soc", code="CAN01")
        society.account_status = AccountStatus.CANCELLED
        db.commit()

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/suspend",
            json={"reason": "Test"},
            headers=headers,
        )
        assert resp.status_code == 400


# ── Activate society ───────────────────────────────────────────────────────────

class TestActivateSociety:

    def test_activate_trial_society(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Activate Me", code="ACT01")

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/activate",
            json={"plan": "growth"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["account_status"] == "ACTIVE"
        assert data["subscription_plan"] == "growth"

    def test_activate_invalid_plan(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Invalid Plan Soc", code="IPS01")

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/activate",
            json={"plan": "ultra"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_activate_suspended_society(self, client: TestClient, db: Session):
        _, headers = make_superadmin(db)
        society = make_trial_society(db, name="Reactivate Soc", code="RES01")
        society.account_status = AccountStatus.SUSPENDED
        db.commit()

        resp = client.post(
            f"/api/v1/platform-admin/societies/{society.id}/activate",
            json={"plan": "starter"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["account_status"] == "ACTIVE"
