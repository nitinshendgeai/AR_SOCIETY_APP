"""
Tenant CRUD — Phase M1.3. Mirrors backend/tests/master/test_resident.py
(Phase M1.2) as closely as the domain allows.

Covers: create/read/list/update, RBAC, tenant isolation, flat immutability,
invalid flat, inactive tenant, duplicate warnings, agreement date
validation, agreement creation on move-in, move-in, move-out.
"""
import pytest
from uuid import UUID as _UUID
from datetime import date, timedelta
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def society_a(db):
    society = make_society(db, "Tenant Test Society A")
    admin = make_user(db, "tenadmA@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing T1")
    flat = make_flat(db, wing.id, "T-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


@pytest.fixture
def society_b(db):
    society = make_society(db, "Tenant Test Society B")
    admin = make_user(db, "tenadmB@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing T2")
    flat = make_flat(db, wing.id, "T-201")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


# ── CREATE / READ / LIST / UPDATE ────────────────────────────────────────────

def test_create_tenant(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Alice Tenant",
        "phone": "9000000001",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["full_name"] == "Alice Tenant"
    assert body["warnings"] == []
    assert body["active_agreement_id"] is None


def test_read_one_tenant(client, db, society_a):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Bob Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.get(f"/api/v1/tenants/{created['id']}", headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["full_name"] == "Bob Tenant"


def test_read_one_tenant_still_accessible_after_move_out(client, db, society_a):
    """Regression for a real bug found in M1.4-R Postgres E2E verification:
    TenantRepository.get() filters is_active=True, and move-out sets
    Tenant.is_active=False — so GET /tenants/{id} 404'd for every moved-out
    tenant, making their detail page (and agreement/occupancy history)
    completely unreachable. get_or_404() must use get_any() instead."""
    from datetime import date
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Moved Out Tenant",
        "move_in_date": str(date.today()),
    }, headers=society_a["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(society_a["flat"].id), "tenant_id": created["id"],
        "move_out_date": str(date.today()),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 200

    detail = client.get(f"/api/v1/tenants/{created['id']}", headers=society_a["admin"]["headers"])
    assert detail.status_code == 200, detail.text
    assert detail.json()["is_active"] is False


def test_list_tenants_by_flat(client, db, society_a):
    other_flat = make_flat(db, society_a["wing"].id, "T-102")
    client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "In Flat 101",
    }, headers=society_a["admin"]["headers"])
    client.post("/api/v1/tenants/", json={
        "flat_id": str(other_flat.id), "full_name": "In Flat 102",
    }, headers=society_a["admin"]["headers"])
    r = client.get(f"/api/v1/tenants/?flat_id={society_a['flat'].id}", headers=society_a["admin"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "In Flat 101" in names
    assert "In Flat 102" not in names


def test_list_tenants_society_scoped(client, db, society_a, society_b):
    client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Only In A",
    }, headers=society_a["admin"]["headers"])
    client.post("/api/v1/tenants/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Only In B",
    }, headers=society_b["admin"]["headers"])
    r = client.get("/api/v1/tenants/", headers=society_a["admin"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "Only In A" in names
    assert "Only In B" not in names


def test_update_tenant(client, db, society_a):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Eve Tenant", "phone": "9000000001",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"phone": "9000000002"},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["phone"] == "9000000002"


def test_update_cannot_change_financial_terms_directly(client, db, society_a):
    """monthly_rent/security_deposit/agreement dates aren't fields on
    TenantUpdate at all — only the renewal endpoint can change them, so
    they stay in sync with the active AgreementTracker row."""
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Rent Tenant",
        "agreement_start_date": str(date.today()),
        "agreement_end_date": str(date.today() + timedelta(days=180)),
        "monthly_rent": "15000.00",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"monthly_rent": "99999.00"},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    unchanged = client.get(f"/api/v1/tenants/{created['id']}", headers=society_a["admin"]["headers"]).json()
    assert unchanged["monthly_rent"] == "15000.00", "monthly_rent must not be editable via generic PATCH"


# ── RBAC ───────────────────────────────────────────────────────────────────

def test_resident_role_cannot_create_tenant(client, db, society_a):
    resident_user = make_user(db, "plainresident2@test.com", role="Resident")
    _set_society(db, resident_user["user"], society_a["society"].id)
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Should Be Blocked",
    }, headers=resident_user["headers"])
    assert r.status_code == 403


def test_any_member_can_read_tenant(client, db, society_a):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Readable Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    resident_user = make_user(db, "readertenant@test.com", role="Resident")
    _set_society(db, resident_user["user"], society_a["society"].id)
    r = client.get(f"/api/v1/tenants/{created['id']}", headers=resident_user["headers"])
    assert r.status_code == 200


# ── TENANT ISOLATION ───────────────────────────────────────────────────────

def test_cross_society_read_denied(client, db, society_a, society_b):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Society A Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.get(f"/api/v1/tenants/{created['id']}", headers=society_b["admin"]["headers"])
    assert r.status_code == 404


def test_cross_society_update_denied(client, db, society_a, society_b):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Society A Tenant 2",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"phone": "9111111111"},
                      headers=society_b["admin"]["headers"])
    assert r.status_code == 404


def test_create_tenant_into_other_societys_flat_denied(client, db, society_a, society_b):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Cross Tenant Attempt",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 404


# ── FLAT IMMUTABILITY ─────────────────────────────────────────────────────────

def test_flat_id_not_accepted_on_update(client, db, society_a):
    other_flat = make_flat(db, society_a["wing"].id, "T-103")
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Immutable Flat Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"flat_id": str(other_flat.id)},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    unchanged = client.get(f"/api/v1/tenants/{created['id']}", headers=society_a["admin"]["headers"]).json()
    assert unchanged["flat_id"] == str(society_a["flat"].id)


# ── INVALID FLAT ───────────────────────────────────────────────────────────

def test_create_tenant_with_nonexistent_flat_denied(client, db, society_a):
    import uuid
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(uuid.uuid4()), "full_name": "Ghost Flat Tenant",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 404


# ── INACTIVE TENANT ────────────────────────────────────────────────────────

def test_inactive_tenant_excluded_from_default_list(client, db, society_a):
    from app.models.tenant import Tenant
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Soon Inactive Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    row = db.query(Tenant).filter(Tenant.id == _to_uuid(created["id"])).first()
    row.is_active = False
    db.commit()

    r = client.get(f"/api/v1/tenants/?flat_id={society_a['flat'].id}", headers=society_a["admin"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "Soon Inactive Tenant" not in names

    r2 = client.get(f"/api/v1/tenants/?flat_id={society_a['flat'].id}&is_active=false",
                     headers=society_a["admin"]["headers"])
    names2 = {x["full_name"] for x in r2.json()}
    assert "Soon Inactive Tenant" in names2


# ── DUPLICATE WARNING ─────────────────────────────────────────────────────

def test_duplicate_phone_returns_warning_not_block(client, db, society_a):
    client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Original Phone Tenant",
        "phone": "9876500000",
    }, headers=society_a["admin"]["headers"])
    other_flat = make_flat(db, society_a["wing"].id, "T-104")
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(other_flat.id), "full_name": "Duplicate Phone Tenant",
        "phone": "9876500000",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, "duplicate phone must NOT block creation"
    assert any("9876500000" in w for w in r.json()["warnings"])


def test_tenant_duplicate_against_resident_warns(client, db, society_a):
    """A tenant whose phone matches an existing RESIDENT (not another
    tenant) in the same society must still warn — cross-entity, same
    society (Phase M1.3 §10 example)."""
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Existing Resident",
        "phone": "9876511111",
    }, headers=society_a["admin"]["headers"])
    other_flat = make_flat(db, society_a["wing"].id, "T-105")
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(other_flat.id), "full_name": "New Tenant Same Phone",
        "phone": "9876511111",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    assert any("resident" in w.lower() for w in r.json()["warnings"])


def test_no_cross_society_warning_leakage(client, db, society_a, society_b):
    """Society A tenant matches Society B resident's phone -> NO warning
    (Phase M1.3 §10 — must not leak cross-society information)."""
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Society B Resident",
        "phone": "9876522222",
    }, headers=society_b["admin"]["headers"])
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Society A Tenant Same Phone",
        "phone": "9876522222",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    assert r.json()["warnings"] == [], "must not leak a match against another society's data"


# ── AGREEMENT DATE VALIDATION ──────────────────────────────────────────────

def test_agreement_end_before_start_rejected(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Bad Dates Tenant",
        "agreement_start_date": str(date.today()),
        "agreement_end_date": str(date.today() - timedelta(days=1)),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_agreement_dates_must_be_paired(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Half Dates Tenant",
        "agreement_start_date": str(date.today()),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_negative_monthly_rent_rejected(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Negative Rent Tenant",
        "monthly_rent": "-100",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


# ── PHONE VALIDATION (certification gap: "abc123" previously accepted) ──────

@pytest.mark.parametrize("bad_phone", ["abc123", "12345", "12345678901", "0123456789", "98765abcde"])
def test_create_tenant_rejects_malformed_phone(client, db, society_a, bad_phone):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Bad Phone Tenant",
        "phone": bad_phone,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_create_tenant_accepts_valid_phone(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Good Phone Tenant",
        "phone": "9876543210",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["phone"] == "9876543210"


def test_update_tenant_rejects_malformed_phone(client, db, society_a):
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Update Phone Tenant",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/tenants/{created['id']}", json={"phone": "abc123"},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_create_tenant_allows_omitted_phone(client, db, society_a):
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "No Phone Tenant",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["phone"] is None


# ── AGREEMENT CREATION / MOVE-IN / MOVE-OUT ──────────────────────────────

def test_create_with_move_in_date_and_agreement_dates_creates_agreement(client, db, society_a):
    from app.models.flat import Flat, OccupancyStatus
    from app.models.agreement_tracker import AgreementTracker, AgreementStatus

    start = date.today()
    end = start + timedelta(days=180)
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Moving In Tenant",
        "agreement_start_date": str(start), "agreement_end_date": str(end),
        "monthly_rent": "20000.00",
        "move_in_date": str(start),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["active_agreement_id"] is not None

    flat = db.query(Flat).filter(Flat.id == society_a["flat"].id).first()
    assert flat.occupancy_status == OccupancyStatus.TENANT_OCCUPIED

    agr = db.query(AgreementTracker).filter(AgreementTracker.id == _to_uuid(body["active_agreement_id"])).first()
    assert agr is not None
    assert agr.status == AgreementStatus.ACTIVE
    assert agr.society_id == society_a["society"].id


def test_create_without_move_in_date_does_not_touch_occupancy(client, db, society_a):
    from app.models.flat import Flat, OccupancyStatus
    r = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Pre-registered Tenant, not moved in",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    flat = db.query(Flat).filter(Flat.id == society_a["flat"].id).first()
    assert flat.occupancy_status == OccupancyStatus.VACANT


def test_tenant_move_out_via_occupancy_endpoint(client, db, society_a):
    from app.models.tenant import Tenant
    from app.models.flat import Flat, OccupancyStatus

    start = date.today()
    end = start + timedelta(days=180)
    created = client.post("/api/v1/tenants/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Moving Out Tenant",
        "agreement_start_date": str(start), "agreement_end_date": str(end),
        "move_in_date": str(start),
    }, headers=society_a["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/tenant/move-out", json={
        "flat_id": str(society_a["flat"].id), "tenant_id": created["id"],
        "move_out_date": str(date.today()),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 200, r.text

    tenant = db.query(Tenant).filter(Tenant.id == _to_uuid(created["id"])).first()
    assert tenant.is_active is False
    flat = db.query(Flat).filter(Flat.id == society_a["flat"].id).first()
    assert flat.occupancy_status == OccupancyStatus.VACANT
