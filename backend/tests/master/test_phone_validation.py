"""
API-level phone validation for Resident and Tenant (M1.9-R3 Gap C).

M1.9-R2 found that "abc123" reached the backend and was stored as a
tenant's mobile number — no format validation existed anywhere in the
stack. app/utils/phone.py now backs both ResidentCreate/Update and
TenantCreate/Update via the same field_validator; this module verifies the
API surface: clean 422s, no partial mutation, normalization on write, and
that the rule applies identically on create and edit for both entities.
"""
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


@pytest.fixture
def rig(db):
    society = make_society(db, "Phone Validation Society")
    admin = make_user(db, "phoneadm@test.com", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    wing = make_wing(db, society.id, "Wing P1")
    flat = make_flat(db, wing.id, "P-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


@pytest.mark.parametrize("entity,path", [("residents", "/api/v1/residents/"), ("tenants", "/api/v1/tenants/")])
class TestPhoneValidationOnCreate:
    def test_alphabetic_garbage_rejected_with_clean_422(self, client, db, rig, entity, path):
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Phone Test Person",
            "phone": "abc123",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 422, r.text
        body = r.json()
        assert "DioException" not in r.text and "Traceback" not in r.text
        assert body.get("code") == "VALIDATION_ERROR" or "errors" in body

    def test_too_short_rejected(self, client, db, rig, entity, path):
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Phone Test Person",
            "phone": "12345",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 422

    def test_valid_number_is_normalized(self, client, db, rig, entity, path):
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Phone Test Person",
            "phone": "+91 98765-43210",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 201, r.text
        assert r.json()["phone"] == "9876543210"

    def test_omitted_phone_stays_optional(self, client, db, rig, entity, path):
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Phone Test Person",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 201, r.text
        assert r.json()["phone"] is None

    def test_rejected_create_writes_nothing(self, client, db, rig, entity, path):
        before = client.get(f"{path}?flat_id={rig['flat'].id}", headers=rig["admin"]["headers"]).json()
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Should Not Exist",
            "phone": "abc123",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 422
        after = client.get(f"{path}?flat_id={rig['flat'].id}", headers=rig["admin"]["headers"]).json()
        assert len(after) == len(before), "a rejected create must not persist a partial row"
        assert all(p["full_name"] != "Should Not Exist" for p in after)


@pytest.mark.parametrize("entity,path", [("residents", "/api/v1/residents/"), ("tenants", "/api/v1/tenants/")])
class TestPhoneValidationOnEdit:
    def _create(self, client, rig, path):
        r = client.post(path, json={
            "flat_id": str(rig["flat"].id), "full_name": "Edit Phone Person",
        }, headers=rig["admin"]["headers"])
        assert r.status_code == 201, r.text
        return r.json()

    def test_edit_rejects_invalid_phone_and_keeps_prior_value(self, client, db, rig, entity, path):
        created = self._create(client, rig, path)
        r = client.patch(f"{path}{created['id']}", json={"phone": "not-a-number"},
                          headers=rig["admin"]["headers"])
        assert r.status_code == 422

        fetched = client.get(f"{path}{created['id']}", headers=rig["admin"]["headers"]).json()
        assert fetched["phone"] is None, "a rejected PATCH must not mutate the stored phone"

    def test_edit_accepts_and_normalizes_a_valid_phone(self, client, db, rig, entity, path):
        created = self._create(client, rig, path)
        r = client.patch(f"{path}{created['id']}", json={"phone": "09876543210"},
                          headers=rig["admin"]["headers"])
        assert r.status_code == 200, r.text
        assert r.json()["phone"] == "9876543210"
