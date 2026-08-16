"""
Resident CRUD — Phase M1.2.

Covers: create/read/list/update, cross-society denial, flat immutability,
primary-resident rules (application AND database level, kept distinct),
duplicate warnings, inactive-resident exclusion, computed
family_member_count, RBAC, platform-admin behavior, and composition with
the existing (P0-fixed) OccupancyService on create.
"""
import pytest
from uuid import UUID as _UUID
from datetime import date
from sqlalchemy.exc import IntegrityError
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def society_a(db):
    society = make_society(db, "Resident Test Society A")
    admin = make_user(db, "residadmA@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing R1")
    flat = make_flat(db, wing.id, "R-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


@pytest.fixture
def society_b(db):
    society = make_society(db, "Resident Test Society B")
    admin = make_user(db, "residadmB@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing R2")
    flat = make_flat(db, wing.id, "R-201")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


# ── CREATE / READ / LIST / UPDATE ────────────────────────────────────────────

def test_create_resident(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Alice Owner",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["full_name"] == "Alice Owner"
    assert body["is_primary"] is True
    assert body["family_member_count"] == 0
    assert body["warnings"] == []


def test_read_one_resident(client, db, society_a):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Bob Owner",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.get(f"/api/v1/residents/{created['id']}", headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["full_name"] == "Bob Owner"


def test_read_one_resident_still_accessible_after_move_out(client, db, society_a):
    """Regression for a real bug found in M1.4-R Postgres E2E verification:
    ResidentRepository.get() filters is_active=True, and move-out sets
    Resident.is_active=False — so GET /residents/{id} 404'd for every
    moved-out resident, making their detail page (and occupancy history)
    completely unreachable. get_or_404() must use get_any() instead."""
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Moved Out Owner",
        "move_in_date": str(date.today()),
    }, headers=society_a["admin"]["headers"]).json()

    r = client.post("/api/v1/occupancy/resident/move-out", json={
        "flat_id": str(society_a["flat"].id), "resident_id": created["id"],
        "move_out_date": str(date.today()),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 200

    detail = client.get(f"/api/v1/residents/{created['id']}", headers=society_a["admin"]["headers"])
    assert detail.status_code == 200, detail.text
    assert detail.json()["is_active"] is False


def test_list_residents_by_flat(client, db, society_a):
    for name in ("Carol", "Dave"):
        client.post("/api/v1/residents/", json={
            "flat_id": str(society_a["flat"].id), "full_name": name, "resident_type": "family",
        }, headers=society_a["admin"]["headers"])
    r = client.get(f"/api/v1/residents/?flat_id={society_a['flat'].id}", headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    names = {x["full_name"] for x in r.json()}
    assert {"Carol", "Dave"} <= names


def test_list_residents_society_scoped(client, db, society_a, society_b):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Only In A",
    }, headers=society_a["admin"]["headers"])
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Only In B",
    }, headers=society_b["admin"]["headers"])
    r = client.get("/api/v1/residents/", headers=society_a["admin"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "Only In A" in names
    assert "Only In B" not in names


def test_update_resident(client, db, society_a):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Eve Owner", "phone": "9000000001",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"phone": "9000000002"},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["phone"] == "9000000002"


# ── CROSS-SOCIETY DENIAL ──────────────────────────────────────────────────────

def test_cross_society_read_denied(client, db, society_a, society_b):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Society A Resident",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.get(f"/api/v1/residents/{created['id']}", headers=society_b["admin"]["headers"])
    assert r.status_code == 404


def test_cross_society_update_denied(client, db, society_a, society_b):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Society A Resident 2",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"phone": "9111111111"},
                      headers=society_b["admin"]["headers"])
    assert r.status_code == 404


def test_create_resident_into_other_societys_flat_denied(client, db, society_a, society_b):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Cross Tenant Attempt",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 404


def test_own_society_resident_list_excludes_other_society(client, db, society_a, society_b):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "B Only",
    }, headers=society_b["admin"]["headers"])
    r = client.get(f"/api/v1/residents/?flat_id={society_b['flat'].id}", headers=society_a["admin"]["headers"])
    # Flat itself isn't in caller's society -> 404, not a filtered empty list
    # (avoids leaking whether the flat exists in another society).
    assert r.status_code == 404


# ── FLAT IMMUTABILITY ─────────────────────────────────────────────────────────

def test_flat_id_not_accepted_on_update(client, db, society_a):
    # Reuse the fixture's existing wing (make_wing() hardcodes code="A", so a
    # second call in the same society would collide with the (society_id,
    # code) unique constraint) — a second flat under it is all that's needed.
    other_flat = make_flat(db, society_a["wing"].id, "R-102")
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Immutable Flat Resident",
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"flat_id": str(other_flat.id)},
                      headers=society_a["admin"]["headers"])
    # flat_id isn't a field on ResidentUpdate at all -> Pydantic silently
    # ignores the unknown key; the resident's flat_id must be unchanged.
    assert r.status_code == 200
    unchanged = client.get(f"/api/v1/residents/{created['id']}", headers=society_a["admin"]["headers"]).json()
    assert unchanged["flat_id"] == str(society_a["flat"].id)


# ── PRIMARY RESIDENT RULES (application layer — schema/service 422/409) ─────

def test_primary_owner_allowed(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Primary Owner",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201


def test_primary_co_owner_allowed(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Primary Co-Owner",
        "resident_type": "co_owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201


def test_primary_family_rejected(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Invalid Primary Family",
        "resident_type": "family", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_primary_dependent_rejected(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Invalid Primary Dependent",
        "resident_type": "dependent", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_second_active_primary_rejected_with_clean_409(client, db, society_a):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "First Primary",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Second Primary Attempt",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 409


def test_inactive_primary_does_not_block_new_primary(client, db, society_a):
    from app.models.resident import Resident
    old = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Old Primary",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"]).json()
    # Deactivate directly (no move-out endpoint composition needed for this test)
    row = db.query(Resident).filter(Resident.id == _to_uuid(old["id"])).first()
    row.is_active = False
    db.commit()

    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "New Primary",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201


def test_update_can_promote_to_primary_if_slot_free(client, db, society_a):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Promotable Co-owner",
        "resident_type": "co_owner", "is_primary": False,
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"is_primary": True},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["is_primary"] is True


def test_update_promote_to_primary_rejected_when_type_wrong(client, db, society_a):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Family trying to be primary",
        "resident_type": "family", "is_primary": False,
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{created['id']}", json={"is_primary": True},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 422


def test_update_promote_to_primary_rejected_when_slot_taken(client, db, society_a):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Existing Primary",
        "resident_type": "owner", "is_primary": True,
    }, headers=society_a["admin"]["headers"])
    other = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Wants To Be Primary Too",
        "resident_type": "co_owner", "is_primary": False,
    }, headers=society_a["admin"]["headers"]).json()
    r = client.patch(f"/api/v1/residents/{other['id']}", json={"is_primary": True},
                      headers=society_a["admin"]["headers"])
    assert r.status_code == 409


# ── DUPLICATE WARNINGS (non-blocking) ────────────────────────────────────────

def test_duplicate_phone_returns_warning_not_block(client, db, society_a):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Original Phone Owner",
        "phone": "9876543210",
    }, headers=society_a["admin"]["headers"])
    other_flat = make_flat(db, society_a["wing"].id, "R-103")
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(other_flat.id), "full_name": "Duplicate Phone Resident",
        "phone": "9876543210",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201, "duplicate phone must NOT block creation"
    assert any("9876543210" in w for w in r.json()["warnings"])


def test_no_warning_for_unique_contact_info(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Unique Contact",
        "phone": "9000009999", "email": "unique-contact@example.com",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    assert r.json()["warnings"] == []


# ── INACTIVE RESIDENT ─────────────────────────────────────────────────────────

def test_inactive_resident_excluded_from_default_list(client, db, society_a):
    from app.models.resident import Resident
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Soon Inactive",
    }, headers=society_a["admin"]["headers"]).json()
    row = db.query(Resident).filter(Resident.id == _to_uuid(created["id"])).first()
    row.is_active = False
    db.commit()

    r = client.get(f"/api/v1/residents/?flat_id={society_a['flat'].id}", headers=society_a["admin"]["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "Soon Inactive" not in names

    r2 = client.get(f"/api/v1/residents/?flat_id={society_a['flat'].id}&is_active=false",
                     headers=society_a["admin"]["headers"])
    names2 = {x["full_name"] for x in r2.json()}
    assert "Soon Inactive" in names2


# ── FAMILY MEMBER COUNT (computed, not client-settable) ─────────────────────

def test_family_member_count_is_computed(client, db, society_a):
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Owner With Family",
        "resident_type": "owner", "family_member_count": 999,  # must be ignored/rejected
    }, headers=society_a["admin"]["headers"])
    assert r.status_code in (201, 422)  # either silently ignored or rejected as unknown field
    if r.status_code == 201:
        assert r.json()["family_member_count"] == 0

    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Family Member 1", "resident_type": "family",
    }, headers=society_a["admin"]["headers"])
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Dependent 1", "resident_type": "dependent",
    }, headers=society_a["admin"]["headers"])

    owner = client.get(f"/api/v1/residents/?flat_id={society_a['flat'].id}&resident_type=owner",
                        headers=society_a["admin"]["headers"]).json()[0]
    assert owner["family_member_count"] == 2


# ── RBAC ───────────────────────────────────────────────────────────────────

def test_resident_cannot_create_resident(client, db, society_a):
    resident_user = make_user(db, "plainresident@test.com", role="Resident")
    _set_society(db, resident_user["user"], society_a["society"].id)
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Should Be Blocked",
    }, headers=resident_user["headers"])
    assert r.status_code == 403


def test_any_member_can_read(client, db, society_a):
    created = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Readable By Anyone",
    }, headers=society_a["admin"]["headers"]).json()
    resident_user = make_user(db, "readerresident@test.com", role="Resident")
    _set_society(db, resident_user["user"], society_a["society"].id)
    r = client.get(f"/api/v1/residents/{created['id']}", headers=resident_user["headers"])
    assert r.status_code == 200


# ── PLATFORM ADMIN ────────────────────────────────────────────────────────────

def test_platform_admin_can_create_across_societies(client, db, society_a, society_b):
    platform_admin = make_user(db, "platformadm@test.com", role="Platform Admin")
    # society_id intentionally left None (unset) — matches the codebase's
    # established platform-admin convention (see UserRepository/tenant_scope).
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Platform Admin Created",
    }, headers=platform_admin["headers"])
    assert r.status_code == 201


def test_platform_admin_list_sees_all_societies(client, db, society_a, society_b):
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Visible To Platform A",
    }, headers=society_a["admin"]["headers"])
    client.post("/api/v1/residents/", json={
        "flat_id": str(society_b["flat"].id), "full_name": "Visible To Platform B",
    }, headers=society_b["admin"]["headers"])
    platform_admin = make_user(db, "platformadm2@test.com", role="Platform Admin")
    r = client.get("/api/v1/residents/", headers=platform_admin["headers"])
    names = {x["full_name"] for x in r.json()}
    assert "Visible To Platform A" in names
    assert "Visible To Platform B" in names


# ── OCCUPANCY INTEGRATION (composes with the P0-fixed OccupancyService) ─────

def test_create_with_move_in_date_triggers_occupancy(client, db, society_a):
    from app.models.flat import Flat, OccupancyStatus
    from app.models.occupancy_log import OccupancyLog, OccupancyEventType

    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Moving In Today",
        "resident_type": "owner", "is_primary": True,
        "move_in_date": str(date.today()),
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    body = r.json()
    assert body["move_in_date"] == str(date.today())

    flat = db.query(Flat).filter(Flat.id == society_a["flat"].id).first()
    assert flat.occupancy_status == OccupancyStatus.OWNER_OCCUPIED

    log = db.query(OccupancyLog).filter(
        OccupancyLog.flat_id == society_a["flat"].id,
        OccupancyLog.event_type == OccupancyEventType.RESIDENT_MOVE_IN,
    ).first()
    assert log is not None, "OccupancyService.resident_move_in must have been called, not re-implemented"


def test_create_without_move_in_date_does_not_touch_occupancy(client, db, society_a):
    from app.models.flat import Flat, OccupancyStatus
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(society_a["flat"].id), "full_name": "Pre-registered, not moved in yet",
    }, headers=society_a["admin"]["headers"])
    assert r.status_code == 201
    flat = db.query(Flat).filter(Flat.id == society_a["flat"].id).first()
    assert flat.occupancy_status == OccupancyStatus.VACANT


# ── DATABASE CONSTRAINT ENFORCEMENT (bypasses the API/service entirely) ─────
# These prove the DATABASE itself rejects invalid rows, independent of any
# application-layer validation — required distinction per Phase M1.2 §14.

class TestResidentDatabaseConstraints:

    def test_db_rejects_second_active_primary_via_raw_orm_insert(self, db, society_a):
        from app.models.resident import Resident, ResidentType
        r1 = Resident(flat_id=society_a["flat"].id, full_name="DB Test Primary 1",
                       resident_type=ResidentType.OWNER, is_primary=True)
        db.add(r1)
        db.commit()

        r2 = Resident(flat_id=society_a["flat"].id, full_name="DB Test Primary 2",
                       resident_type=ResidentType.OWNER, is_primary=True)
        db.add(r2)
        with pytest.raises(IntegrityError):
            db.commit()
        # No explicit db.rollback() here — the `db` fixture's own teardown
        # (tests/conftest.py) already rolls back this connection's outer
        # transaction; calling rollback() again here is harmless but
        # produces a "transaction already deassociated" SAWarning.

    def test_db_rejects_primary_family_via_raw_sql(self, db, society_a):
        """Bypasses the ORM model entirely (raw SQL), not just the Pydantic
        schema — proves the CHECK constraint, not application code, is what
        actually stops this."""
        from sqlalchemy import text
        with pytest.raises(IntegrityError):
            db.execute(text("""
                INSERT INTO residents (id, created_at, updated_at, is_active, flat_id,
                                        full_name, resident_type, is_primary,
                                        family_member_count, kyc_verified)
                VALUES (lower(hex(randomblob(16))), datetime('now'), datetime('now'), 1,
                        :flat_id, 'Raw SQL Sneaky Family Primary', 'family', 1, 0, 0)
            """), {"flat_id": society_a["flat"].id.hex})
            db.commit()

    def test_db_rejects_primary_dependent_via_raw_sql(self, db, society_a):
        from sqlalchemy import text
        with pytest.raises(IntegrityError):
            db.execute(text("""
                INSERT INTO residents (id, created_at, updated_at, is_active, flat_id,
                                        full_name, resident_type, is_primary,
                                        family_member_count, kyc_verified)
                VALUES (lower(hex(randomblob(16))), datetime('now'), datetime('now'), 1,
                        :flat_id, 'Raw SQL Sneaky Dependent Primary', 'dependent', 1, 0, 0)
            """), {"flat_id": society_a["flat"].id.hex})
            db.commit()

    def test_db_allows_non_primary_family_via_raw_sql(self, db, society_a):
        from sqlalchemy import text
        db.execute(text("""
            INSERT INTO residents (id, created_at, updated_at, is_active, flat_id,
                                    full_name, resident_type, is_primary,
                                    family_member_count, kyc_verified)
            VALUES (lower(hex(randomblob(16))), datetime('now'), datetime('now'), 1,
                    :flat_id, 'Legit Family Member', 'family', 0, 0, 0)
        """), {"flat_id": society_a["flat"].id.hex})
        db.commit()  # must not raise
