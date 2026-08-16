"""
Phase M1.4-R — seed-role / RBAC contract regression.

app/utils/seed.py previously created a role literally named "Admin" (and
"Committee"/"Security"/"Staff"), while require_admin_committee /
require_any_member check literal role names from the canonical set defined
in app/core/dependencies.py (mirroring EXTENDED_DEFAULT_ROLES in
onboarding_service.py) — "Society Admin", "Committee Member" (etc.),
"Security Staff", "Housekeeping Staff", "Resident". The mismatch meant every
seeded "admin" account got 403s on legitimate Resident Master operations.

These tests lock the seed script's role names to the canonical contract and
prove the fixed names actually satisfy the auth dependencies used by the
Resident Master API — using the exact same user-creation pattern as
app/utils/seed.py's create_user() (see conftest.make_user).
"""
import pytest
from app.utils.seed import ROLES as SEED_ROLES
from app.modules.onboarding.services.onboarding_service import EXTENDED_DEFAULT_ROLES
from tests.conftest import make_user, make_society, make_wing, make_flat

_CANONICAL_ROLE_NAMES = {name for name, _ in EXTENDED_DEFAULT_ROLES}


def test_seed_roles_are_all_canonical():
    """Every role name the seed script assigns must exist in the canonical
    role set — otherwise require_admin_committee/require_any_member silently
    reject the seeded account, exactly as happened before this fix."""
    for role_name in SEED_ROLES:
        assert role_name in _CANONICAL_ROLE_NAMES, (
            f"Seed role {role_name!r} is not a canonical role name "
            f"(see EXTENDED_DEFAULT_ROLES in onboarding_service.py)"
        )


def test_seed_no_longer_uses_stale_role_names():
    """Regression guard for the exact bug found in M1.4 live verification —
    the old invented names must never reappear in the seed script."""
    stale = {"Admin", "Committee", "Security", "Staff"}
    assert not (set(SEED_ROLES) & stale), (
        f"Seed script regressed to stale/non-canonical role names: "
        f"{set(SEED_ROLES) & stale}"
    )


@pytest.fixture
def rig(db):
    society = make_society(db, "Seed Role Test Society")
    wing = make_wing(db, society.id, "Wing S1")
    flat = make_flat(db, wing.id, "S-101")
    return {"society": society, "wing": wing, "flat": flat}


def test_seeded_society_admin_can_create_and_list_residents(client, db, rig):
    """Uses the exact role name app.utils.seed.py now assigns to the
    admin account ("Society Admin") — proves the fixed seed contract
    actually satisfies require_admin_committee for Resident Master writes."""
    assert "Society Admin" in SEED_ROLES
    admin = make_user(db, "seedadmin@test.com", role="Society Admin")

    create = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Seed Verified Resident",
        "resident_type": "owner", "is_primary": True,
    }, headers=admin["headers"])
    assert create.status_code == 201, create.text

    listing = client.get("/api/v1/residents/", headers=admin["headers"])
    assert listing.status_code == 200
    assert any(r["full_name"] == "Seed Verified Resident" for r in listing.json())


def test_seeded_society_admin_can_create_and_list_tenants(client, db, rig):
    assert "Society Admin" in SEED_ROLES
    admin = make_user(db, "seedadmin2@test.com", role="Society Admin")

    create = client.post("/api/v1/tenants/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Seed Verified Tenant",
    }, headers=admin["headers"])
    assert create.status_code == 201, create.text

    listing = client.get("/api/v1/tenants/", headers=admin["headers"])
    assert listing.status_code == 200
    assert any(t["full_name"] == "Seed Verified Tenant" for t in listing.json())


def test_seeded_society_admin_can_access_vehicles(client, db, rig):
    """GET /vehicles/society/{id} uses require_any_member — confirms the
    Society Admin role (not just require_admin_committee-gated writes)
    also satisfies the broader any-member dependency."""
    admin = make_user(db, "seedadmin3@test.com", role="Society Admin")
    r = client.get(f"/api/v1/vehicles/society/{rig['society'].id}", headers=admin["headers"])
    assert r.status_code == 200, r.text


def test_seeded_security_staff_role_is_recognized(db):
    """Security Staff is one of the roles _ROLES_SUPERVISORS/_ROLES_STAFF
    (via require_any_staff/require_security) — confirm the seed script's
    replacement for the old stale "Security" role name is a real role."""
    assert "Security Staff" in SEED_ROLES
    make_user(db, "seedsecurity@test.com", role="Security Staff")


def test_stale_admin_role_name_is_rejected(client, db, rig):
    """The exact bug this phase fixes: a user seeded with the OLD literal
    role name "Admin" must NOT be able to perform admin-gated Resident
    Master operations — proving the mismatch was real and the fix matters."""
    stale_admin = make_user(db, "staleadmin@test.com", role="Admin")
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Should Be Rejected",
        "resident_type": "owner",
    }, headers=stale_admin["headers"])
    assert r.status_code == 403


def test_normal_resident_member_retains_read_access_only(client, db, rig):
    """A normal "Resident"-roled member must keep read access (GET) but must
    NOT gain write access (POST) — the seed-role fix must not elevate
    ordinary member permissions."""
    member = make_user(db, "seedmember@test.com", role="Resident")

    read = client.get("/api/v1/residents/", headers=member["headers"])
    assert read.status_code == 200

    write = client.post("/api/v1/residents/", json={
        "flat_id": str(rig["flat"].id), "full_name": "Should Not Be Allowed",
        "resident_type": "owner",
    }, headers=member["headers"])
    assert write.status_code == 403
