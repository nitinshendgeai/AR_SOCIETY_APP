"""Tests for self-service society onboarding."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import make_user


REGISTER_URL = "/api/v1/public/register"

VALID_PAYLOAD = {
    "society_name":        "Sunrise Heights",
    "society_code":        "SRH001",
    "contact_person_name": "John Doe",
    "contact_email":       "john@srh001.arsociety.com",
    "contact_mobile":      "9876543210",
    "city":                "Mumbai",
    "state":               "Maharashtra",
    "country":             "India",
    "total_wings":         2,
    "total_flats":         50,
    "terms_accepted":      True,
}


# ── Self-registration ─────────────────────────────────────────────────────────

class TestSelfRegistration:

    def test_register_success(self, client: TestClient):
        resp = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["society_code"] == "SRH001"
        assert data["trial_days"] == 30
        assert len(data["credentials"]) == 4
        roles = {c["role"] for c in data["credentials"]}
        assert "Society Admin" in roles
        assert "Committee Chairman" in roles

    def test_register_auto_uppercases_code(self, client: TestClient):
        payload = {**VALID_PAYLOAD,
                   "society_name": "Lower Code Society",
                   "society_code": "low1",
                   "contact_email": "lower@low1.arsociety.com",
                   "contact_mobile": "8000000001"}
        resp = client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 201, resp.text
        assert resp.json()["society_code"] == "LOW1"

    def test_register_rejects_terms_false(self, client: TestClient):
        payload = {**VALID_PAYLOAD, "terms_accepted": False,
                   "society_name": "No Terms Society", "society_code": "NTS01",
                   "contact_email": "nts@test.com", "contact_mobile": "8000000002"}
        resp = client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    def test_register_rejects_invalid_code(self, client: TestClient):
        payload = {**VALID_PAYLOAD, "society_code": "AB",  # too short
                   "society_name": "Bad Code Society",
                   "contact_email": "bad@test.com", "contact_mobile": "8000000003"}
        resp = client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    def test_register_rejects_invalid_mobile(self, client: TestClient):
        payload = {**VALID_PAYLOAD, "contact_mobile": "123",  # not 10 digits
                   "society_name": "Bad Mobile Society", "society_code": "BMS01",
                   "contact_email": "badm@test.com"}
        resp = client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    def test_register_duplicate_name_returns_409(self, client: TestClient):
        client.post(REGISTER_URL, json=VALID_PAYLOAD)
        payload2 = {**VALID_PAYLOAD,
                    "society_code": "SRH002",
                    "contact_email": "john2@srh002.arsociety.com",
                    "contact_mobile": "9876543211"}
        resp = client.post(REGISTER_URL, json=payload2)
        assert resp.status_code == 409
        assert "Society name" in resp.json()["detail"]

    def test_register_duplicate_code_returns_409(self, client: TestClient):
        client.post(REGISTER_URL, json=VALID_PAYLOAD)
        payload2 = {**VALID_PAYLOAD,
                    "society_name": "Other Society",
                    "contact_email": "other@other.com",
                    "contact_mobile": "9876543212"}
        resp = client.post(REGISTER_URL, json=payload2)
        assert resp.status_code == 409
        assert "society code" in resp.json()["detail"].lower()

    def test_register_duplicate_email_returns_409(self, client: TestClient):
        client.post(REGISTER_URL, json=VALID_PAYLOAD)
        payload2 = {**VALID_PAYLOAD,
                    "society_name": "Another Society",
                    "society_code": "ANS01",
                    "contact_mobile": "9876543213"}
        resp = client.post(REGISTER_URL, json=payload2)
        assert resp.status_code == 409


# ── Trial status ──────────────────────────────────────────────────────────────

class TestTrialStatus:

    def _register_and_login(self, client: TestClient, db: Session):
        resp = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        society_id = data["society_id"]

        admin_cred = next(c for c in data["credentials"] if c["role"] == "Society Admin")
        login_resp = client.post("/api/v1/auth/login", json={
            "email":    admin_cred["email"],
            "password": admin_cred["password"],
        })
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["access_token"]
        return society_id, {"Authorization": f"Bearer {token}"}

    def test_trial_status_returns_correct_days(self, client: TestClient, db: Session):
        society_id, headers = self._register_and_login(client, db)
        resp = client.get(f"/api/v1/societies/{society_id}/trial-status", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["is_trial"] is True
        assert data["trial_days_remaining"] == 30
        assert data["account_status"] == "TRIAL"
        assert data["trial_expired"] is False

    def test_trial_status_requires_auth(self, client: TestClient, db: Session):
        resp_reg = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        society_id = resp_reg.json()["society_id"]
        resp = client.get(f"/api/v1/societies/{society_id}/trial-status")
        assert resp.status_code == 403


# ── Setup progress ────────────────────────────────────────────────────────────

class TestSetupProgress:

    def test_update_setup_progress(self, client: TestClient, db: Session):
        resp = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        society_id = data["society_id"]

        admin_cred = next(c for c in data["credentials"] if c["role"] == "Society Admin")
        login_resp = client.post("/api/v1/auth/login", json={
            "email":    admin_cred["email"],
            "password": admin_cred["password"],
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.patch(
            f"/api/v1/societies/{society_id}/setup-progress",
            json={"setup_completion_percentage": 50, "setup_completed": False},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["setup_completion_percentage"] == 50

    def test_complete_setup(self, client: TestClient, db: Session):
        resp = client.post(REGISTER_URL, json={
            **VALID_PAYLOAD,
            "society_name":   "Setup Complete Society",
            "society_code":   "SCS01",
            "contact_email":  "setup@scs01.arsociety.com",
            "contact_mobile": "7000000001",
        })
        assert resp.status_code == 201
        data = resp.json()
        society_id = data["society_id"]

        admin_cred = next(c for c in data["credentials"] if c["role"] == "Society Admin")
        token = client.post("/api/v1/auth/login", json={
            "email": admin_cred["email"], "password": admin_cred["password"]
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.patch(
            f"/api/v1/societies/{society_id}/setup-progress",
            json={"setup_completion_percentage": 80, "setup_completed": True},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["setup_completed"] is True
        assert resp.json()["setup_completion_percentage"] == 100


# ── Accept terms ──────────────────────────────────────────────────────────────

class TestAcceptTerms:

    def test_accept_terms(self, client: TestClient, db: Session):
        resp = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201
        cred = next(c for c in resp.json()["credentials"] if c["role"] == "Society Admin")
        token = client.post("/api/v1/auth/login", json={
            "email": cred["email"], "password": cred["password"]
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/auth/accept-terms",
                           json={"terms_accepted": True},
                           headers=headers)
        assert resp.status_code == 200
        assert resp.json()["terms_accepted"] is True

    def test_reject_terms_false(self, client: TestClient, db: Session):
        resp = client.post(REGISTER_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201
        cred = next(c for c in resp.json()["credentials"] if c["role"] == "Society Admin")
        token = client.post("/api/v1/auth/login", json={
            "email": cred["email"], "password": cred["password"]
        }).json()["access_token"]

        resp = client.post("/api/v1/auth/accept-terms",
                           json={"terms_accepted": False},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422
